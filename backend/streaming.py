import asyncio
import base64
import json
import re
from contextlib import suppress
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
    get_pipeline_step_timeout_seconds,
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
    parts = re.split(r"(?<=[.!?;:,])\s+", text.strip())
    chunks = []
    current = ""

    for part in parts:
        if not part:
            continue
        words = part.split()
        for word in words or [part]:
            if len(current) + len(word) + 1 <= max_chars:
                current = f"{current} {word}".strip()
                continue
            if current:
                chunks.append(current)
            current = word

    if current:
        chunks.append(current)

    return chunks or [text]


def should_translate_partial(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    return bool(re.search(r"[.!?;:,]\s*$", normalized)) or len(normalized.split()) >= 2


def audio_suffix_for_mime(mime_type: str | None) -> str:
    value = (mime_type or "").lower()
    if "mp4" in value or "aac" in value or "m4a" in value:
        return ".m4a"
    if "ogg" in value:
        return ".ogg"
    if "wav" in value:
        return ".wav"
    return ".webm"


class PipelineStepTimeout(RuntimeError):
    pass


async def run_pipeline_step(label: str, call, *args):
    timeout = get_pipeline_step_timeout_seconds()
    try:
        return await asyncio.wait_for(run_in_threadpool(call, *args), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise PipelineStepTimeout(f"{label} timed out after {timeout:g}s.") from exc


async def websocket_text_translation(websocket: WebSocket, pipeline: UniversalTranslatorPipeline):
    await websocket.accept()
    await websocket.send_json({"type": "ready", "message": "Streaming text translation connected."})

    while True:
        payload = await websocket.receive_json()
        if payload.get("type") == "ping":
            await websocket.send_json({"type": "pong"})
            continue
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
    speaker_mode = "manual"
    session_id = "default"
    audio_chunks = bytearray()
    recent_chunks = []
    speech_started = False
    finalizing = False
    silent_checks = 0
    vad_error_count = 0
    max_buffer_bytes = get_stream_buffer_max_mb() * 1024 * 1024
    last_chunk_meta = {}
    client_mime_type = "audio/webm"
    audio_suffix = ".webm"
    last_speech_at = 0.0
    last_partial_at = 0.0
    partial_text = ""
    partial_task = None
    pipeline_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=1)

    def reset_segment_state() -> None:
        nonlocal audio_chunks, recent_chunks, speech_started, silent_checks, last_speech_at, vad_error_count, partial_text, last_partial_at
        audio_chunks = bytearray()
        recent_chunks = []
        speech_started = False
        silent_checks = 0
        vad_error_count = 0
        last_speech_at = 0.0
        partial_text = ""
        last_partial_at = 0.0

    async def enqueue_finalize(reason: str) -> None:
        nonlocal audio_chunks, recent_chunks, speech_started, silent_checks, last_speech_at, vad_error_count
        if pipeline_queue.full():
            await websocket.send_json({"type": "stage", "stage": "queued", "message": "Already processing audio. Please wait..."})
            return

        if not audio_chunks:
            if finalizing or not pipeline_queue.empty():
                await websocket.send_json({"type": "stage", "stage": "queued", "message": "Already processing audio. Please wait..."})
                return
            await websocket.send_json({"type": "error", "message": "No audio received."})
            reset_segment_state()
            return

        segment = {
            "audio_bytes": bytes(audio_chunks),
            "speaker": speaker,
            "speaker_mode": speaker_mode,
            "session_id": session_id,
            "source_language": source_language,
            "target_language": target_language,
            "client_mime_type": client_mime_type,
            "audio_suffix": audio_suffix,
            "partial_text": partial_text,
            "queued_at": time(),
            "reason": reason,
        }
        reset_segment_state()
        await pipeline_queue.put(segment)
        await websocket.send_json({"type": "stage", "stage": "queued", "message": "Audio queued for translation..."})

    async def emit_partial_pipeline() -> None:
        nonlocal last_partial_at, partial_task
        if not get_near_zero_latency_mode():
            return
        if len(audio_chunks) < get_partial_stt_min_bytes():
            return
        if (time() - last_partial_at) * 1000 < get_partial_stt_interval_ms():
            return
        if partial_task is not None and not partial_task.done():
            return
        partial_started_at = time()
        last_partial_at = partial_started_at
        partial_audio = bytes(audio_chunks)
        partial_suffix = audio_suffix
        partial_source_language = source_language
        partial_target_language = target_language
        partial_speaker = speaker
        partial_task = asyncio.create_task(run_partial_pipeline(
            partial_audio,
            partial_suffix,
            partial_source_language,
            partial_target_language,
            partial_speaker,
            partial_started_at,
        ))

    async def run_partial_pipeline(
        partial_audio: bytes,
        partial_suffix: str,
        partial_source_language: str,
        partial_target_language: str,
        partial_speaker: str,
        partial_started_at: float,
    ) -> None:
        nonlocal partial_text
        upload_dir = Path("models/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        partial_audio_path = upload_dir / f"{uuid4()}-partial{partial_suffix}"
        partial_audio_path.write_bytes(partial_audio)
        try:
            try:
                next_partial_text = await run_pipeline_step("partial STT", pipeline.stt.transcribe, str(partial_audio_path), partial_source_language)
            except PipelineStepTimeout as exc:
                if not finalizing:
                    await websocket.send_json({"type": "stage", "stage": "partial_timeout", "message": str(exc)})
                return
            except Exception:
                return
        finally:
            partial_audio_path.unlink(missing_ok=True)
        if finalizing or not next_partial_text or next_partial_text == partial_text:
            return
        partial_text = next_partial_text
        await websocket.send_json({"type": "partial_transcription", "text": partial_text})
        if should_translate_partial(partial_text):
            try:
                partial_translation = await run_pipeline_step("partial translation", pipeline.translator.translate, partial_text, partial_source_language, partial_target_language)
            except PipelineStepTimeout as exc:
                if not finalizing:
                    await websocket.send_json({"type": "stage", "stage": "partial_timeout", "message": str(exc)})
                return
            except Exception:
                return
            if finalizing:
                return
            await websocket.send_json({"type": "partial_translation", "text": partial_translation})
            observability.record_event("near_zero_partial", identity=identity, speaker=partial_speaker, latency_seconds=time() - partial_started_at)

    async def finalize_segment(segment: dict):
        nonlocal speaker, finalizing
        if finalizing:
            return
        finalizing = True
        segment_started_at = time()
        audio_path = None

        try:
            audio_bytes = segment["audio_bytes"]
            segment_speaker_mode = segment["speaker_mode"]
            segment_session_id = segment["session_id"]
            segment_source_language = segment["source_language"]
            segment_target_language = segment["target_language"]
            segment_mime_type = segment["client_mime_type"]
            segment_audio_suffix = segment["audio_suffix"]
            segment_partial_text = segment.get("partial_text", "")
            speaker = segment["speaker"]
            if not audio_bytes:
                await websocket.send_json({"type": "error", "message": "No audio received."})
                return

            if len(audio_bytes) < get_min_speech_bytes():
                await websocket.send_json({"type": "stage", "stage": "smoothing", "message": "Ignoring very short speech burst."})
                return

            estimated_seconds = max(1, len(audio_bytes) / 16000)
            if estimated_seconds > get_max_audio_seconds():
                await websocket.send_json({"type": "error", "message": f"Audio segment exceeds {get_max_audio_seconds()} second limit."})
                return
            quota_allowed, remaining_seconds = usage_limiter.check_audio_seconds(identity, estimated_seconds)
            if not quota_allowed:
                await websocket.send_json({"type": "error", "message": f"Daily audio quota exceeded. Remaining seconds: {int(remaining_seconds)}"})
                return

            if segment_speaker_mode == "auto":
                speaker = session_registry.next_auto_speaker(segment_session_id, identity)
                session_registry.bind(segment_session_id, speaker, identity, segment_source_language, segment_target_language)

            active_source_language = segment_target_language if segment_speaker_mode == "auto" and speaker == "B" else segment_source_language
            active_target_language = segment_source_language if segment_speaker_mode == "auto" and speaker == "B" else segment_target_language
            await websocket.send_json({
                "type": "speaker_detected",
                "speaker": speaker,
                "mode": segment_speaker_mode,
                "source_language": active_source_language,
                "target_language": active_target_language,
            })

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
                return

            upload_dir = Path("models/uploads")
            upload_dir.mkdir(parents=True, exist_ok=True)
            audio_path = upload_dir / f"{uuid4()}{segment_audio_suffix}"
            audio_path.write_bytes(audio_bytes)

            await websocket.send_json({"type": "stage", "stage": "stt", "message": "Speech finalized. Transcribing now..."})
            observability.record_event("mobile_stream_checkpoint", identity=identity, speaker=speaker, checkpoint="stt_start", audio_bytes=len(audio_bytes), mime_type=segment_mime_type)
            source_text = await run_pipeline_step("STT", pipeline.stt.transcribe, str(audio_path), active_source_language)
            if not source_text.strip() and segment_partial_text.strip():
                source_text = segment_partial_text
            print("STT:", source_text, flush=True)
            observability.record_event("mobile_stream_checkpoint", identity=identity, speaker=speaker, checkpoint="stt_done", source_text=source_text)
            if not source_text.strip():
                await websocket.send_json({"type": "error", "message": "No clear speech recognized. Try speaking closer to the mic."})
                return
            await websocket.send_json({"type": "final_transcription", "speaker": speaker, "text": source_text})
            semantic_context = conversation_brain.analyze_semantics(speaker, source_text)
            await websocket.send_json({"type": "semantic_context", "speaker": speaker, **semantic_context})
            await websocket.send_json({"type": "stage", "stage": "translation", "message": "Transcription ready. Translating..."})

            improved_text = await run_pipeline_step(
                "context improvement",
                pipeline.context_layer.improve,
                source_text,
                active_source_language,
                active_target_language,
                None,
            )
            translated_text = await run_pipeline_step(
                "translation",
                pipeline.translator.translate,
                improved_text,
                active_source_language,
                active_target_language,
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
            for tts_segment in tts_pacing["segments"]:
                tts_chunks.extend(chunk_text_for_tts(tts_segment))
            await websocket.send_json({"type": "tts_start", "chunks": len(tts_chunks)})

            for index, chunk in enumerate(tts_chunks, start=1):
                chunk_output_path = await run_pipeline_step(
                    "TTS",
                    pipeline.tts.synthesize,
                    chunk,
                    f"models/tts/{uuid4()}-{index}.wav",
                )
                if audio_output_path is None:
                    audio_output_path = chunk_output_path
                tts_audio_bytes = Path(chunk_output_path).read_bytes()
                observability.record_event("mobile_stream_checkpoint", identity=identity, speaker=speaker, checkpoint="tts_chunk", index=index, total=len(tts_chunks), audio_bytes=len(tts_audio_bytes))
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
                    "audio_base64": base64.b64encode(tts_audio_bytes).decode("ascii"),
                    "mime_type": "audio/wav",
                })

            await websocket.send_json({"type": "tts_end"})
            result = TranslationResult(
                source_text=source_text,
                improved_text=improved_text,
                translated_text=translated_text,
                audio_output_path=audio_output_path,
            )
            shared_session = session_registry.record_turn(segment_session_id, identity, speaker, source_text, translated_text, semantic_context)
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

        except PipelineStepTimeout as exc:
            observability.increment("pipeline_timeouts_total")
            await websocket.send_json({"type": "error", "message": str(exc), "recoverable": True})
            conversation_brain.cancel(speaker)
        finally:
            if audio_path is not None:
                audio_path.unlink(missing_ok=True)
            finalizing = False

    async def process_pipeline_queue() -> None:
        while True:
            segment = await pipeline_queue.get()
            try:
                await finalize_segment(segment)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                observability.increment("pipeline_errors_total")
                await websocket.send_json({"type": "error", "message": f"Pipeline recovered after error: {exc}", "recoverable": True})
                conversation_brain.cancel(segment.get("speaker", speaker))
            finally:
                pipeline_queue.task_done()

    pipeline_worker = asyncio.create_task(process_pipeline_queue())

    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=0.08)
            except asyncio.TimeoutError:
                if speech_started and audio_chunks and last_speech_at and time() - last_speech_at > get_vad_force_final_seconds():
                    print("FORCE FINAL", flush=True)
                    await enqueue_finalize("force_timeout")
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
                    if payload.get("mime_type"):
                        client_mime_type = payload.get("mime_type")
                        audio_suffix = audio_suffix_for_mime(client_mime_type)
                    last_chunk_meta = {
                        "sent_at_ms": payload.get("sent_at_ms"),
                        "bytes": payload.get("bytes"),
                        "mime_type": payload.get("mime_type") or client_mime_type,
                        "received_at": time(),
                    }
                    continue

                if message_type == "start":
                    if session_registry.active_stream_count(identity) >= get_max_active_streams_per_user():
                        await websocket.send_json({"type": "error", "message": "Too many active streams for this user."})
                        continue
                    speaker_mode = payload.get("speaker_mode", "manual")
                    session_id = payload.get("session_id", "default")
                    speaker = session_registry.next_auto_speaker(session_id, identity) if speaker_mode == "auto" else payload.get("speaker", "speaker")
                    client_mime_type = payload.get("mime_type") or client_mime_type
                    audio_suffix = audio_suffix_for_mime(client_mime_type)
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
                    await websocket.send_json({"type": "listening", "speaker": speaker, "speaker_mode": speaker_mode, "message": "Receiving audio chunks with Silero VAD."})

                if message_type == "finalize":
                    await enqueue_finalize("client_finalize")

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
                    vad_result = await run_in_threadpool(vad.detect_bytes, b"".join(recent_chunks), audio_suffix)
                except Exception as exc:
                    observability.increment("vad_errors_total")
                    vad_error_count += 1
                    if len(audio_chunks) >= get_min_speech_bytes():
                        speech_started = True
                        last_speech_at = time()
                        await websocket.send_json({"type": "stage", "stage": "listening", "message": "Audio buffered. Keep talking..."})
                    elif vad_error_count == 1:
                        await websocket.send_json({"type": "partial_transcription", "text": f"Preparing audio stream ({len(audio_chunks)} bytes)..."})
                    if vad_error_count in {1, 5}:
                        await websocket.send_json({"type": "vad_error", "message": str(exc), "fallback": "byte_buffer"})
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
                        await enqueue_finalize("vad_silence")
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
    finally:
        if partial_task is not None:
            partial_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await partial_task
        pipeline_worker.cancel()
        with suppress(asyncio.CancelledError):
            await pipeline_worker
