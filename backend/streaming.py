import asyncio
import base64
import json
import re
from pathlib import Path
from time import time
from uuid import uuid4

from backend.conversation import ConversationBrain
from backend.config import (
    get_max_active_streams_per_user,
    get_max_audio_seconds,
    get_min_speech_bytes,
    get_near_zero_latency_mode,
    get_partial_stt_interval_ms,
    get_partial_stt_min_bytes,
    get_speech_merge_ms,
    get_stream_buffer_max_mb,
    get_stream_hot_path_logging,
    get_tts_chunk_chars,
    get_vad_force_final_seconds,
    get_vad_recent_chunks,
    get_vad_silent_checks,
)
from backend.observability import observability
from backend.pipeline import TranslationResult
from backend.security import usage_limiter
from backend.sessions import session_registry
from backend.tts_pacing import build_tts_pacing
from fastapi import WebSocket
from fastapi.concurrency import run_in_threadpool
from starlette.websockets import WebSocketDisconnect

from backend.pipeline import UniversalTranslatorPipeline
from speech import SileroVoiceActivityDetector


def chunk_text_for_tts(text: str, max_chars: int | None = None) -> list[str]:
    max_chars = max_chars or get_tts_chunk_chars()
    parts = re.split(r"(?<=[.!?;:])\s+", text.strip())
    chunks = []
    current = ""

    for part in parts:
        if not part:
            continue
        if len(current) + len(part) + 1 <= max_chars:
            current = f"{current} {part}".strip()
        else:
            if current:
                chunks.append(current)
            current = part

    if current:
        chunks.append(current)

    return chunks or [text]


async def websocket_text_translation(websocket: WebSocket, pipeline: UniversalTranslatorPipeline):
    await websocket.accept()
    await websocket.send_json({"type": "ready", "message": "Streaming text translation connected."})

    while True:
        payload = await websocket.receive_json()
        text = payload.get("text", "")
        source_language = payload.get("source_language", "en")
        target_language = payload.get("target_language", "es")

        if not text.strip():
            await websocket.send_json({"type": "error", "message": "Text is required."})
            continue

        result = pipeline.translate_text(
            text=text,
            source_language=source_language,
            target_language=target_language,
            synthesize_audio=False,
        )
        await websocket.send_json({"type": "translation", **result.__dict__})


async def websocket_audio_translation(
    websocket: WebSocket,
    pipeline: UniversalTranslatorPipeline,
    vad: SileroVoiceActivityDetector,
    conversation_brain: ConversationBrain,
    identity: str = "anonymous",
):
    await websocket.accept()
    observability.increment("websocket_connects_total")
    await websocket.send_json({"type": "ready", "message": "Audio streaming connected."})

    source_language = "en"
    target_language = "es"
    speaker = "speaker"
    session_id = "default"
    audio_chunks = bytearray()
    recent_chunks = []
    speech_started = False
    silent_checks = 0
    max_buffer_bytes = get_stream_buffer_max_mb() * 1024 * 1024
    last_chunk_meta = {}
    last_speech_at = 0.0
    last_partial_at = 0.0
    partial_text = ""

    def reset_segment_state() -> None:
        nonlocal audio_chunks, recent_chunks, speech_started, silent_checks, last_speech_at
        audio_chunks = bytearray()
        recent_chunks = []
        speech_started = False
        silent_checks = 0
        last_speech_at = 0.0

    async def emit_partial_pipeline() -> None:
        nonlocal last_partial_at, partial_text
        if not get_near_zero_latency_mode():
            return
        if len(audio_chunks) < get_partial_stt_min_bytes():
            return
        if (time() - last_partial_at) * 1000 < get_partial_stt_interval_ms():
            return
        partial_started_at = time()
        last_partial_at = partial_started_at
        upload_dir = Path("models/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        partial_audio_path = upload_dir / f"{uuid4()}-partial.webm"
        partial_audio_path.write_bytes(audio_chunks)
        try:
            next_partial_text = await run_in_threadpool(pipeline.stt.transcribe, str(partial_audio_path), source_language)
        finally:
            partial_audio_path.unlink(missing_ok=True)
        if not next_partial_text or next_partial_text == partial_text:
            return
        partial_text = next_partial_text
        await websocket.send_json({"type": "partial_transcription", "text": partial_text})
        if len(partial_text.split()) >= 3:
            partial_translation = await run_in_threadpool(pipeline.translator.translate, partial_text, source_language, target_language)
            await websocket.send_json({"type": "partial_translation", "text": partial_translation})
            observability.record_event("near_zero_partial", identity=identity, speaker=speaker, latency_seconds=time() - partial_started_at)

    async def finalize_segment():
        nonlocal speaker
        segment_started_at = time()

        if not audio_chunks:
            await websocket.send_json({"type": "error", "message": "No audio received."})
            reset_segment_state()
            return

        if len(audio_chunks) < get_min_speech_bytes():
            await websocket.send_json({"type": "stage", "stage": "smoothing", "message": "Ignoring very short speech burst."})
            reset_segment_state()
            return

        estimated_seconds = max(1, len(audio_chunks) / 16000)
        if estimated_seconds > get_max_audio_seconds():
            await websocket.send_json({"type": "error", "message": f"Audio segment exceeds {get_max_audio_seconds()} second limit."})
            reset_segment_state()
            return
        quota_allowed, remaining_seconds = usage_limiter.check_audio_seconds(identity, estimated_seconds)
        if not quota_allowed:
            await websocket.send_json({"type": "error", "message": f"Daily audio quota exceeded. Remaining seconds: {int(remaining_seconds)}"})
            reset_segment_state()
            return

        decision = conversation_brain.request_turn(speaker)
        await websocket.send_json({
            "type": "turn",
            "speaker": speaker,
            "allowed": decision.allowed,
            "reason": decision.reason,
            "behavior": decision.behavior,
            "active_speaker": decision.active_speaker,
            "playback_owner": decision.playback_owner,
        })
        if not decision.allowed:
            reset_segment_state()
            return

        upload_dir = Path("models/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        audio_path = upload_dir / f"{uuid4()}.webm"
        audio_path.write_bytes(audio_chunks)

        await websocket.send_json({"type": "stage", "stage": "stt", "message": "Speech finalized. Transcribing now..."})
        observability.record_event("mobile_stream_checkpoint", identity=identity, speaker=speaker, checkpoint="stt_start", audio_bytes=len(audio_chunks))
        source_text = await run_in_threadpool(pipeline.stt.transcribe, str(audio_path), source_language)
        print("STT:", source_text, flush=True)
        observability.record_event("mobile_stream_checkpoint", identity=identity, speaker=speaker, checkpoint="stt_done", source_text=source_text)
        await websocket.send_json({"type": "final_transcription", "speaker": speaker, "text": source_text})
        semantic_context = conversation_brain.analyze_semantics(speaker, source_text)
        await websocket.send_json({"type": "semantic_context", "speaker": speaker, **semantic_context})
        await websocket.send_json({"type": "stage", "stage": "translation", "message": "Transcription ready. Translating..."})

        improved_text = await run_in_threadpool(
            pipeline.context_layer.improve,
            source_text,
            source_language,
            target_language,
            None,
        )
        translated_text = await run_in_threadpool(
            pipeline.translator.translate,
            improved_text,
            source_language,
            target_language,
        )
        intent = semantic_context.get("last_intent") or semantic_context.get("intent") or "statement"
        urgency = "high" if semantic_context.get("conversation_mood") == "urgent" else None
        tts_pacing = build_tts_pacing(translated_text, intent, urgency)
        print("TRANSLATION:", translated_text, flush=True)
        await websocket.send_json({"type": "live_translation", "speaker": speaker, "text": translated_text})
        await websocket.send_json({"type": "tts_style", "speaker": speaker, **tts_pacing})
        observability.record_event("mobile_stream_checkpoint", identity=identity, speaker=speaker, checkpoint="translation_done", translated_text=translated_text)
        await websocket.send_json({"type": "stage", "stage": "tts", "message": "Translation ready. Streaming voice..."})
        playback_decision = conversation_brain.begin_playback(speaker)
        await websocket.send_json({
            "type": "turn",
            "speaker": speaker,
            "allowed": playback_decision.allowed,
            "reason": playback_decision.reason,
            "behavior": playback_decision.behavior,
            "active_speaker": playback_decision.active_speaker,
            "playback_owner": playback_decision.playback_owner,
        })

        audio_output_path = None
        tts_chunks = []
        for segment in tts_pacing["segments"]:
            tts_chunks.extend(chunk_text_for_tts(segment))
        await websocket.send_json({"type": "tts_start", "chunks": len(tts_chunks)})

        for index, chunk in enumerate(tts_chunks, start=1):
            chunk_output_path = await run_in_threadpool(
                pipeline.tts.synthesize,
                chunk,
                f"models/tts/{uuid4()}-{index}.wav",
            )
            if audio_output_path is None:
                audio_output_path = chunk_output_path
            audio_bytes = Path(chunk_output_path).read_bytes()
            observability.record_event("mobile_stream_checkpoint", identity=identity, speaker=speaker, checkpoint="tts_chunk", index=index, total=len(tts_chunks), audio_bytes=len(audio_bytes))
            observability.increment("tts_playback_chunks_total")
            await websocket.send_json({
                "type": "tts_audio_chunk",
                "speaker": speaker,
                "index": index,
                "total": len(tts_chunks),
                "text": chunk,
                "tts_style": tts_pacing["style"],
                "emotion": tts_pacing["emotion"],
                "intent": tts_pacing["intent"],
                "urgency": tts_pacing["urgency"],
                "audio_base64": base64.b64encode(audio_bytes).decode("ascii"),
                "mime_type": "audio/wav",
            })

        await websocket.send_json({"type": "tts_end"})
        result = TranslationResult(
            source_text=source_text,
            improved_text=improved_text,
            translated_text=translated_text,
            audio_output_path=audio_output_path,
        )
        shared_session = session_registry.record_turn(session_id, identity, speaker, source_text, translated_text, semantic_context)
        await websocket.send_json({"type": "session_sync", "session": shared_session})
        print("FINAL TRIGGERED", flush=True)
        await websocket.send_json({"type": "final", "speaker": speaker, "semantic_context": semantic_context, "session": shared_session, **result.__dict__})
        observability.observe_latency("streaming_segment", time() - segment_started_at)
        observability.record_event("streaming_segment", identity=identity, speaker=speaker, latency_seconds=time() - segment_started_at)
        await websocket.send_json({"type": "latency", "metric": "backend_response", "ms": round((time() - segment_started_at) * 1000)})
        usage_limiter.track_audio(identity, estimated_seconds, "streaming_segments")
        complete_decision = conversation_brain.end_turn(speaker)
        await websocket.send_json({
            "type": "turn",
            "speaker": speaker,
            "allowed": complete_decision.allowed,
            "reason": complete_decision.reason,
            "behavior": complete_decision.behavior,
            "active_speaker": complete_decision.active_speaker,
            "playback_owner": complete_decision.playback_owner,
        })

        reset_segment_state()
        audio_path.unlink(missing_ok=True)

    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=0.25)
            except asyncio.TimeoutError:
                if speech_started and audio_chunks and last_speech_at and time() - last_speech_at > get_vad_force_final_seconds():
                    print("FORCE FINAL", flush=True)
                    await finalize_segment()
                continue

            if message.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect(message.get("code", 1000))

            if "text" in message:
                payload = json.loads(message["text"])
                message_type = payload.get("type")

                if message_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                if message_type == "chunk_meta":
                    last_chunk_meta = {
                        "sent_at_ms": payload.get("sent_at_ms"),
                        "bytes": payload.get("bytes"),
                        "received_at": time(),
                    }
                    continue

                if message_type == "start":
                    if session_registry.active_stream_count(identity) >= get_max_active_streams_per_user():
                        await websocket.send_json({"type": "error", "message": "Too many active streams for this user."})
                        continue
                    speaker = payload.get("speaker", "speaker")
                    session_id = payload.get("session_id", "default")
                    decision = conversation_brain.request_turn(speaker)
                    await websocket.send_json({
                        "type": "turn",
                        "speaker": speaker,
                        "allowed": decision.allowed,
                        "reason": decision.reason,
                        "behavior": decision.behavior,
                        "active_speaker": decision.active_speaker,
                        "playback_owner": decision.playback_owner,
                    })
                    source_language = payload.get("source_language", "en")
                    target_language = payload.get("target_language", "es")
                    session_state = session_registry.bind(session_id, speaker, identity, source_language, target_language)
                    reset_segment_state()
                    await websocket.send_json({
                        "type": "session_restored",
                        "session": session_state,
                        "message": "Speaker stream bound to session.",
                    })
                    await websocket.send_json({"type": "listening", "message": "Receiving audio chunks with Silero VAD."})

                if message_type == "finalize":
                    await finalize_segment()

                if message_type == "cancel":
                    conversation_brain.cancel(speaker)
                    reset_segment_state()
                    await websocket.send_json({"type": "cancelled"})

            if "bytes" in message:
                chunk = message["bytes"]
                if get_stream_hot_path_logging():
                    print("AUDIO RECEIVED:", len(chunk), flush=True)
                if last_chunk_meta.get("sent_at_ms"):
                    mic_to_backend_ms = round(time() * 1000 - float(last_chunk_meta["sent_at_ms"]))
                    await websocket.send_json({"type": "latency", "metric": "mic_to_backend", "ms": mic_to_backend_ms})
                    observability.record_event("mobile_latency", identity=identity, metric="mic_to_backend", ms=mic_to_backend_ms, chunk_bytes=len(chunk))
                audio_chunks.extend(chunk)
                observability.record_event("mobile_stream_checkpoint", identity=identity, speaker=speaker, checkpoint="audio_chunk", chunk_bytes=len(chunk), total_audio_bytes=len(audio_chunks))
                if len(audio_chunks) > max_buffer_bytes:
                    await websocket.send_json({"type": "error", "message": "Audio buffer limit reached. Please speak in shorter turns."})
                    reset_segment_state()
                    continue
                recent_chunks.append(chunk)
                recent_chunks = recent_chunks[-get_vad_recent_chunks():]

                try:
                    vad_result = await run_in_threadpool(vad.detect_bytes, b"".join(recent_chunks), ".webm")
                except Exception as exc:
                    observability.increment("vad_errors_total")
                    await websocket.send_json({"type": "vad_error", "message": str(exc)})
                    await websocket.send_json({"type": "partial_transcription", "text": f"Buffered {len(audio_chunks)} bytes..."})
                    continue

                if vad_result["speech_detected"]:
                    if get_stream_hot_path_logging():
                        print("VAD:", True, flush=True)
                    observability.increment("vad_speech_total")
                    speech_started = True
                    last_speech_at = time()
                    silent_checks = 0
                    await emit_partial_pipeline()
                    observability.record_event("mobile_stream_checkpoint", identity=identity, speaker=speaker, checkpoint="vad_speech", speech_seconds=vad_result["speech_seconds"])
                    await websocket.send_json({
                        "type": "vad",
                        "speech_detected": True,
                        "speech_seconds": vad_result["speech_seconds"],
                    })
                    await websocket.send_json({"type": "stage", "stage": "listening", "message": "Speech detected. Keep talking..."})
                elif speech_started:
                    if get_stream_hot_path_logging():
                        print("VAD:", False, flush=True)
                    observability.increment("vad_silence_total")
                    silent_checks += 1
                    if (time() - last_speech_at) * 1000 < get_speech_merge_ms():
                        await websocket.send_json({"type": "stage", "stage": "smoothing", "message": "Merging short speech gap..."})
                        continue
                    observability.record_event("mobile_stream_checkpoint", identity=identity, speaker=speaker, checkpoint="vad_silence", silent_checks=silent_checks)
                    await websocket.send_json({
                        "type": "vad",
                        "speech_detected": False,
                        "silent_checks": silent_checks,
                    })
                    if silent_checks >= get_vad_silent_checks():
                        await finalize_segment()
                else:
                    if get_stream_hot_path_logging():
                        print("VAD:", False, flush=True)
                    observability.increment("vad_silence_total")
                    await websocket.send_json({"type": "partial_transcription", "text": "Waiting for speech..."})

    except WebSocketDisconnect:
        observability.increment("websocket_disconnects_total")
        session_registry.disconnect(session_id, speaker, identity)
        return
    except Exception:
        observability.increment("websocket_errors_total")
        raise
