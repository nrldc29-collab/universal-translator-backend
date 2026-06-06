import asyncio
import base64
import json
import logging
import re
import unicodedata
from contextlib import suppress
from pathlib import Path
from time import time
from uuid import uuid4

logger = logging.getLogger("anai_translator")

from backend.conversation import ConversationBrain
from backend.memory import ConversationMemory
from backend.speakers import (
    SpeakerMemory,
    detect_language_heuristic,
    detect_language_in_pair,
    language_pair_has_ht,
    opposite_language_in_pair,
    resolve_active_languages_in_pair,
    resolve_whisper_language,
)
from backend.refine import refine_translation
from backend.latency import LatencyEngine
from backend.stream_session import StreamSessionState
from backend.audio import process_wav_for_stt, compute_rms
from backend.cip_bridge import choose_translation, get_cip_confidence, get_cip_decision, is_cip_clarification, resolve_translation_text
from backend.confidence import (
    ConfidenceEngine,
    assess_translation_confidence,
    estimate_stt_confidence,
    estimate_translation_confidence,
    detect_ambiguities,
    clarification_for,
)
from backend.communication_brain import detect_domains
from backend.api_health import runtime_state
from backend.glossary import get_session_glossary, glossary_coverage_score, glossary_blocks_clarification
from backend.config import (
    get_client_vad_mode,
    get_client_vad_threshold,
    get_max_active_streams_per_user,
    get_max_audio_seconds,
    get_min_speech_bytes,
    get_near_zero_latency_mode,
    get_partial_tts_mode,
    get_partial_stt_interval_ms,
    get_partial_stt_min_bytes,
    get_partial_translation_min_words,
    get_speech_merge_ms,
    get_stream_buffer_max_mb,
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

from backend.pipeline import AnaiTranslatorPipeline
from speech import SileroVoiceActivityDetector

# Circuit breaker for resilient service calls
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30.0, half_open_max_calls=3):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.failures = 0
        self.last_failure_time = 0.0
        self.state = 'closed'  # closed, open, half_open
        self.half_open_calls = 0
        self._lock = asyncio.Lock()
    
    async def call(self, func, *args, **kwargs):
        async with self._lock:
            if self.state == 'open':
                if time() - self.last_failure_time >= self.recovery_timeout:
                    self.state = 'half_open'
                    self.half_open_calls = 0
                else:
                    raise Exception(f"Circuit breaker open - service temporarily unavailable")
            
            if self.state == 'half_open' and self.half_open_calls >= self.half_open_max_calls:
                raise Exception(f"Circuit breaker half-open limit reached")
            
            if self.state == 'half_open':
                self.half_open_calls += 1
        
        try:
            result = await func(*args, **kwargs)
            async with self._lock:
                if self.state == 'half_open':
                    self.state = 'closed'
                    self.failures = 0
                    self.half_open_calls = 0
            return result
        except Exception as e:
            async with self._lock:
                self.failures += 1
                self.last_failure_time = time()
                if self.failures >= self.failure_threshold:
                    self.state = 'open'
            raise e

# Global circuit breakers for critical services
tts_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=15.0)
translation_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=10.0)
stt_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=5.0)
from speech.audio_decode import transcode_to_wav

# Pure helpers + pipeline-step plumbing live in a sibling module so this
# file can focus on the WebSocket handlers below.
from backend.streaming_helpers import (
    PipelineStepTimeout,
    audio_suffix_for_mime,
    call_cip_brain,
    chunk_text_for_tts,
    extract_client_voice_active,
    folded_live_text,
    is_speakable_live_delta,
    live_translation_delta,
    looks_like_container_audio,
    normalize_live_text,
    normalized_word,
    parse_provider_event,
    run_pipeline_step,
    should_translate_partial,
    stream_debug_log,
)


async def websocket_text_translation(websocket: WebSocket, pipeline: AnaiTranslatorPipeline):
    await websocket.accept()
    await websocket.send_json({"type": "ready", "message": "Streaming text translation connected."})

    while True:
        payload = await websocket.receive_json()
        if payload.get("type") == "ping":
            await websocket.send_json({"type": "pong"})
            continue
        text = payload.get("text", "")
        source_language = payload.get("source_language", "en")
        target_language = payload.get("target_language", "ht")

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
    pipeline: AnaiTranslatorPipeline,
    vad: SileroVoiceActivityDetector,
    conversation_brain: ConversationBrain,
    memory: ConversationMemory | None = None,
    speaker_memory: SpeakerMemory | None = None,
    identity: str = "anonymous",
):
    await websocket.accept()
    observability.increment("websocket_connects_total")
    logger.info("websocket_audio_connected partial_tts_mode=%s", get_partial_tts_mode())
    await websocket.send_json({"type": "ready", "message": "Audio streaming connected."})
    memory = memory or ConversationMemory()
    speaker_memory = speaker_memory or SpeakerMemory()

    source_language = "en"
    target_language = "ht"
    speaker = "speaker"
    speaker_label = "Person 1"
    speaker_index = 1
    speaker_mode = "manual"
    speaker_detection = "manual"
    device_id = None
    session_id = "default"
    stt_only = False
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
    partial_buffer = ""
    partial_tts_text = ""
    last_sent_translation = ""
    last_active_speaker = None
    segment_generation = 0
    partial_task = None
    live_text_task = None
    live_text_pending = None
    live_text_revision = 0
    live_text_active_until = 0.0
    live_text_final_until = 0.0
    latency_engine = LatencyEngine()
    confidence_engine = ConfidenceEngine()
    pipeline_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=1)
    tts_active = False
    partial_tts_active = False
    last_partial_tts_at = 0.0
    phrase_accumulation_buffer = ""
    phrase_accumulation_start = 0.0   # when accumulation began (never reset mid-speech)
    PARTIAL_TTS_MIN_INTERVAL = 0.8    # fire at most every 800ms
    PARTIAL_TTS_MIN_WORDS = 2         # need at least 2 words before speaking
    PARTIAL_TTS_MAX_WORDS = 15        # cap phrase length
    turn_announced_for_segment = False
    active_speaker_notice_at = 0.0

    def reset_segment_state() -> None:
        nonlocal audio_chunks, recent_chunks, speech_started, silent_checks, last_speech_at, vad_error_count, partial_text, partial_buffer, partial_tts_text, last_partial_at, last_sent_translation, last_active_speaker, turn_announced_for_segment, segment_generation, phrase_accumulation_buffer, phrase_accumulation_start
        audio_chunks = bytearray()
        recent_chunks = []
        speech_started = False
        silent_checks = 0
        vad_error_count = 0
        last_speech_at = 0.0
        partial_text = ""
        partial_buffer = ""
        partial_tts_text = ""
        last_partial_at = 0.0
        last_sent_translation = ""
        last_active_speaker = None
        turn_announced_for_segment = False
        segment_generation += 1
        phrase_accumulation_buffer = ""
        phrase_accumulation_start = 0.0

    async def announce_active_speaker(reason: str, audio_level: float | None = None) -> bool:
        nonlocal turn_announced_for_segment, active_speaker_notice_at
        if turn_announced_for_segment:
            return True
        decision = conversation_brain.request_turn(speaker)
        turn_announced_for_segment = decision.allowed
        active_speaker_notice_at = time()
        await websocket.send_json({
            "type": "active_speaker",
            "speaker": speaker,
            "speaker_label": speaker_label,
            "speaker_index": speaker_index,
            "device_id": device_id,
            "detection": speaker_detection,
            "reason": reason,
            "audio_level": audio_level,
            "allowed": decision.allowed,
            "behavior": decision.behavior,
            "active_speaker": decision.active_speaker,
            "playback_owner": decision.playback_owner,
        })
        await websocket.send_json({
            "type": "turn",
            "speaker": speaker,
            "speaker_label": speaker_label,
            "allowed": decision.allowed,
            "reason": decision.reason,
            "behavior": decision.behavior,
            "active_speaker": decision.active_speaker,
            "playback_owner": decision.playback_owner,
        })
        return decision.allowed

    async def enqueue_finalize(reason: str) -> None:
        nonlocal audio_chunks, recent_chunks, speech_started, silent_checks, last_speech_at, vad_error_count
        if live_text_active_until and time() < live_text_active_until:
            audio_chunks.clear()
            recent_chunks.clear()
            reset_segment_state()
            return
        if live_text_final_until and time() < live_text_final_until:
            audio_chunks.clear()
            recent_chunks.clear()
            reset_segment_state()
            return
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
            "speaker_label": speaker_label,
            "speaker_index": speaker_index,
            "speaker_mode": speaker_mode,
            "speaker_detection": speaker_detection,
            "device_id": device_id,
            "session_id": session_id,
            "source_language": source_language,
            "target_language": target_language,
            "client_mime_type": client_mime_type,
            "audio_suffix": audio_suffix,
            "partial_text": partial_text,
            "partial_translation": last_sent_translation,
            "partial_tts_text": partial_tts_text,
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
        if live_text_active_until and time() < live_text_active_until:
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
        partial_speaker_label = speaker_label
        partial_generation = segment_generation
        partial_task = asyncio.create_task(run_partial_pipeline(
            partial_audio,
            partial_suffix,
            partial_source_language,
            partial_target_language,
            partial_speaker,
            partial_speaker_label,
            partial_generation,
            partial_started_at,
        ))

    async def run_partial_pipeline(
        partial_audio: bytes,
        partial_suffix: str,
        partial_source_language: str,
        partial_target_language: str,
        partial_speaker: str,
        partial_speaker_label: str,
        partial_generation: int,
        partial_started_at: float,
    ) -> None:
        nonlocal partial_text, partial_buffer, partial_tts_text, last_sent_translation, last_active_speaker, tts_active, partial_tts_active
        upload_dir = Path("models/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        partial_audio_path = upload_dir / f"{uuid4()}-partial{partial_suffix}"
        partial_audio_path.write_bytes(partial_audio)
        transcoded_partial_path = None
        processed_partial_path = None
        stt_input_path = str(partial_audio_path)
        try:
            if partial_suffix.lower() in {".webm", ".m4a", ".mp4", ".ogg", ".aac"}:
                transcoded_partial_path = await run_in_threadpool(transcode_to_wav, str(partial_audio_path))
                if transcoded_partial_path:
                    stt_input_path = transcoded_partial_path
            # Denoise/normalize partial audio if possible
            processed_partial_path, metrics = process_wav_for_stt(stt_input_path)
            stt_input_path = processed_partial_path or stt_input_path
            try:
                partial_stt_language = resolve_whisper_language(
                    partial_source_language,
                    partial_target_language,
                    stt_only=stt_only,
                )
                next_partial_text = await run_pipeline_step(
                    "partial STT",
                    pipeline.stt.transcribe,
                    stt_input_path,
                    partial_stt_language,
                )
            except PipelineStepTimeout as exc:
                if partial_generation == segment_generation:
                    await websocket.send_json({"type": "stage", "stage": "partial_timeout", "message": str(exc)})
                return
            except (RuntimeError, ValueError, OSError) as exc:
                if partial_generation == segment_generation:
                    await websocket.send_json({
                        "type": "stage",
                        "stage": "partial_stt_failed",
                        "message": str(exc) or "Partial speech recognition failed.",
                    })
                return
        finally:
            partial_audio_path.unlink(missing_ok=True)
            if transcoded_partial_path:
                Path(transcoded_partial_path).unlink(missing_ok=True)
            if processed_partial_path and processed_partial_path != str(partial_audio_path):
                Path(processed_partial_path).unlink(missing_ok=True)
        if partial_generation != segment_generation or not next_partial_text or next_partial_text == partial_text:
            return
        partial_text = next_partial_text
        # Accumulate into partial_buffer conservatively to reduce flicker
        if len(next_partial_text) > len(partial_buffer):
            partial_buffer = next_partial_text
        await websocket.send_json({"type": "partial_transcription", "speaker": partial_speaker, "speaker_label": partial_speaker_label, "text": partial_text})
        if stt_only:
            return
        # Adaptive thresholds: interruption and current system speed
        interrupted = last_active_speaker is not None and last_active_speaker != partial_speaker
        total_latency = latency_engine.total()
        fast_system = total_latency <= 0 or total_latency < 1.3
        min_words_base = get_partial_translation_min_words() if fast_system else max(3, get_partial_translation_min_words() + 1)
        min_words = (min_words_base - 1) if interrupted else min_words_base
        if bool(re.search(r"[.!?;:,]\s*$", partial_buffer.strip())) or len(partial_buffer.split()) >= min_words:
            partial_active_src = partial_source_language
            partial_active_tgt = partial_target_language
            if language_pair_has_ht(partial_source_language, partial_target_language):
                partial_active_src = detect_language_in_pair(
                    partial_buffer,
                    partial_source_language,
                    partial_target_language,
                )
                partial_active_tgt = opposite_language_in_pair(
                    partial_active_src,
                    partial_source_language,
                    partial_target_language,
                )
            try:
                partial_translation_raw = await run_pipeline_step(
                    "partial translation",
                    lambda: pipeline.translate_local(
                        partial_buffer,
                        partial_active_src,
                        partial_active_tgt,
                        session_id=session_id,
                        original_source_text=partial_buffer,
                    ),
                )
            except PipelineStepTimeout as exc:
                if partial_generation == segment_generation:
                    await websocket.send_json({"type": "stage", "stage": "partial_timeout", "message": str(exc)})
                return
            except (RuntimeError, ValueError, OSError) as exc:
                if partial_generation == segment_generation:
                    await websocket.send_json({
                        "type": "stage",
                        "stage": "partial_translation_failed",
                        "message": str(exc) or "Partial translation failed.",
                    })
                return
            if partial_generation != segment_generation:
                return
            # Lock or auto-detect language for this speaker once
            if not speaker_memory.get_language(partial_speaker):
                if language_pair_has_ht(partial_source_language, partial_target_language):
                    speaker_memory.register(partial_speaker, language=partial_active_src)
                else:
                    auto_lang = detect_language_heuristic(partial_text)
                    speaker_memory.register(partial_speaker, language=partial_source_language or auto_lang)
            refined_partial = refine_translation(partial_buffer, partial_translation_raw, memory.get_context(), speaker_memory.get_context(partial_speaker))
            # Confidence and ambiguity checks for partials
            stt_conf = estimate_stt_confidence(partial_text)
            tr_conf = estimate_translation_confidence(partial_buffer, refined_partial)
            conf_score = confidence_engine.evaluate(stt_conf, tr_conf)
            if conf_score < 0.4:
                await websocket.send_json({"type": "clarify", "message": clarification_for(partial_buffer, detect_ambiguities(partial_buffer)), "stage": "partial_low_confidence"})
            # Adaptive partial update suppression if under heavy load
            allow_partial_updates = latency_engine.total() <= 2.5
            if allow_partial_updates and refined_partial and refined_partial != last_sent_translation:
                last_sent_translation = refined_partial
                await websocket.send_json({"type": "partial_translation", "speaker": partial_speaker, "speaker_label": partial_speaker_label, "text": refined_partial, "source_language": partial_active_src, "target_language": partial_active_tgt})
                await websocket.send_json({"type": "live_translation", "speaker": partial_speaker, "speaker_label": partial_speaker_label, "text": refined_partial, "source_language": partial_active_src, "target_language": partial_active_tgt})
            live_tts_delta = live_translation_delta(partial_tts_text, refined_partial)
            tts_text_to_speak = live_tts_delta if is_speakable_live_delta(live_tts_delta) else (refined_partial if refined_partial != partial_tts_text else "")
            if get_partial_tts_mode() and is_speakable_live_delta(tts_text_to_speak):
                try:
                    partial_tts_path = await run_pipeline_step(
                        "partial TTS",
                        lambda: pipeline.tts.synthesize(
                            tts_text_to_speak,
                            f"models/tts/{uuid4()}-partial.wav",
                            language=partial_active_tgt,
                        ),
                    )
                except Exception as exc:
                    logger.debug("partial_tts_failed error=%s", exc)
                    partial_tts_path = None
                if partial_tts_path:
                    try:
                        if partial_generation == segment_generation:
                            partial_tts_text = refined_partial
                            partial_tts_active = True
                            partial_tts_audio = Path(partial_tts_path).read_bytes()
                            await websocket.send_json({"type": "tts_start", "speaker": partial_speaker, "speaker_label": partial_speaker_label, "chunks": 1, "partial": True})
                            await websocket.send_json({
                                "type": "tts_audio_chunk",
                                "speaker": partial_speaker,
                                "speaker_label": partial_speaker_label,
                                "index": 1,
                                "total": 1,
                                "text": tts_text_to_speak,
                                "live_translation_text": refined_partial,
                                "audio_base64": base64.b64encode(partial_tts_audio).decode("ascii"),
                                "mime_type": "audio/wav",
                                "partial": True,
                            })
                            await websocket.send_json({"type": "tts_end", "speaker": partial_speaker, "speaker_label": partial_speaker_label, "partial": True})
                    finally:
                        partial_tts_active = False
                        Path(partial_tts_path).unlink(missing_ok=True)
            observability.record_event("near_zero_partial", identity=identity, speaker=partial_speaker, latency_seconds=time() - partial_started_at)

    async def schedule_live_text(payload: dict) -> None:
        nonlocal live_text_pending, live_text_task, live_text_revision, live_text_active_until, live_text_final_until, speech_started, last_speech_at, silent_checks, partial_text, partial_buffer, audio_chunks, recent_chunks
        live_text = normalize_live_text(payload.get("text", ""))
        if not live_text:
            return
        live_text_revision += 1
        is_final = bool(payload.get("final"))
        if is_final:
            live_text_active_until = time() + 4.0
            live_text_final_until = time() + 5.0
            audio_chunks.clear()
            recent_chunks.clear()
            speech_started = False
        else:
            live_text_active_until = time() + 1.6
        speech_started = True
        last_speech_at = time()
        silent_checks = 0
        partial_text = live_text
        partial_buffer = live_text
        await announce_active_speaker("browser_live_text", None)
        await websocket.send_json({
            "type": "partial_transcription",
            "speaker": speaker,
            "speaker_label": speaker_label,
            "text": live_text,
            "source": "browser_live_text",
            "final": bool(payload.get("final")),
        })
        live_text_pending = {
            "revision": live_text_revision,
            "text": live_text,
            "final": bool(payload.get("final")),
            "source_language": payload.get("source_language") or source_language,
            "target_language": payload.get("target_language") or target_language,
            "speaker": speaker,
            "speaker_label": speaker_label,
            "started_at": time(),
        }
        if live_text_task is None or live_text_task.done():
            live_text_task = asyncio.create_task(process_live_text_queue())

    async def process_live_text_queue() -> None:
        nonlocal live_text_pending
        while live_text_pending is not None:
            payload = live_text_pending
            live_text_pending = None
            try:
                await run_live_text_pipeline(payload)
            except Exception as exc:
                logger.warning("live_text_queue_error error=%s", exc)

    async def run_live_text_pipeline(payload: dict) -> None:
        nonlocal last_sent_translation, partial_tts_text, tts_active, partial_tts_active, last_partial_tts_at, phrase_accumulation_buffer, phrase_accumulation_start
        text_value = payload["text"]
        payload_revision = payload["revision"]
        live_source_language = payload["source_language"]
        live_target_language = payload["target_language"]
        if language_pair_has_ht(live_source_language, live_target_language) and text_value.strip():
            live_source_language = detect_language_in_pair(
                text_value,
                live_source_language,
                live_target_language,
            )
            live_target_language = opposite_language_in_pair(
                live_source_language,
                payload["source_language"],
                payload["target_language"],
            )
        live_speaker = payload["speaker"]
        live_speaker_label = payload["speaker_label"]
        try:
            raw_translation = await run_pipeline_step(
                "live text translation",
                lambda: pipeline.translate_local(
                    text_value,
                    live_source_language,
                    live_target_language,
                    session_id=session_id,
                    original_source_text=text_value,
                ),
            )
        except PipelineStepTimeout as exc:
            if payload_revision == live_text_revision:
                await websocket.send_json({"type": "stage", "stage": "live_text_timeout", "message": str(exc)})
            return
        except Exception as exc:
            logger.warning("live_text_translation_failed error=%s", exc)
            if payload_revision == live_text_revision:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Translation failed: {exc}",
                    "recoverable": True,
                    "source": "browser_live_text",
                })
            return

        if not speaker_memory.get_language(live_speaker):
            speaker_memory.register(live_speaker, language=live_source_language or detect_language_heuristic(text_value))
        refined = refine_translation(text_value, raw_translation, memory.get_context(), speaker_memory.get_context(live_speaker))
        if not refined:
            if payload_revision == live_text_revision:
                await websocket.send_json({
                    "type": "error",
                    "message": "Translation empty",
                    "recoverable": True,
                    "source": "browser_live_text",
                })
            return
        if payload_revision != live_text_revision:
            return

        if refined != last_sent_translation:
            last_sent_translation = refined
            await websocket.send_json({
                "type": "partial_translation",
                "speaker": live_speaker,
                "speaker_label": live_speaker_label,
                "text": refined,
                "source": "browser_live_text",
                "final": payload["final"],
                "source_language": live_source_language,
                "target_language": live_target_language,
            })
            await websocket.send_json({
                "type": "live_translation",
                "speaker": live_speaker,
                "speaker_label": live_speaker_label,
                "text": refined,
                "source": "browser_live_text",
                "final": payload["final"],
                "source_language": live_source_language,
                "target_language": live_target_language,
            })

        is_final = bool(payload.get("final"))

        async def emit_live_tts(live_tts_to_speak: str, *, partial: bool) -> bool:
            nonlocal partial_tts_text, last_partial_tts_at, partial_tts_active
            if payload_revision != live_text_revision:
                return False
            if not live_tts_to_speak or not is_speakable_live_delta(live_tts_to_speak):
                return False
            live_tts_path = None
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    live_tts_path = await tts_circuit_breaker.call(
                        run_pipeline_step,
                        "live text TTS",
                        lambda text=live_tts_to_speak: pipeline.tts.synthesize(
                            text,
                            f"models/tts/{uuid4()}-live-text.wav",
                            language=live_target_language,
                        ),
                    )
                    break
                except Exception as exc:
                    logger.warning("live_tts_failed attempt=%d/%d error=%s", attempt + 1, max_retries, exc)
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.1 * (2 ** attempt))
                    else:
                        logger.error("live_tts_failed_all_attempts error=%s", exc)
                        live_tts_path = None
            if not live_tts_path:
                return False
            try:
                partial_tts_text = refined
                last_partial_tts_at = time()
                partial_tts_active = True
                audio_bytes = Path(live_tts_path).read_bytes()
                if len(audio_bytes) < 100:
                    return False
                await websocket.send_json({
                    "type": "tts_start",
                    "speaker": live_speaker,
                    "speaker_label": live_speaker_label,
                    "chunks": 1,
                    "partial": partial,
                    "source": "browser_live_text",
                })
                await websocket.send_json({
                    "type": "tts_audio_chunk",
                    "speaker": live_speaker,
                    "speaker_label": live_speaker_label,
                    "index": 1,
                    "total": 1,
                    "text": live_tts_to_speak,
                    "live_translation_text": refined,
                    "audio_base64": base64.b64encode(audio_bytes).decode("ascii"),
                    "mime_type": "audio/wav",
                    "partial": partial,
                    "source": "browser_live_text",
                })
                await websocket.send_json({
                    "type": "tts_end",
                    "speaker": live_speaker,
                    "speaker_label": live_speaker_label,
                    "partial": partial,
                    "source": "browser_live_text",
                })
                await websocket.send_json({
                    "type": "latency",
                    "metric": "live_text_voice",
                    "ms": round((time() - payload["started_at"]) * 1000),
                })
                return True
            finally:
                partial_tts_active = False
                Path(live_tts_path).unlink(missing_ok=True)

        if is_final:
            pending_tail = phrase_accumulation_buffer.strip()
            live_tail = live_translation_delta(partial_tts_text, refined)
            if is_speakable_live_delta(live_tail):
                tts_playback_text = live_tail
            elif pending_tail:
                tts_playback_text = pending_tail
            elif not partial_tts_text or folded_live_text(refined) != folded_live_text(partial_tts_text):
                tts_playback_text = refined
            else:
                tts_playback_text = ""
            phrase_accumulation_buffer = ""
            phrase_accumulation_start = 0.0
            if tts_playback_text:
                await emit_live_tts(tts_playback_text, partial=False)
            else:
                await websocket.send_json({
                    "type": "tts_end",
                    "speaker": live_speaker,
                    "speaker_label": live_speaker_label,
                    "partial": False,
                    "source": "browser_live_text",
                })
            if payload_revision != live_text_revision:
                return
            memory.add(live_speaker, text_value, refined, {"source": "browser_live_text"})
            speaker_memory.add_message(live_speaker, text_value)
            shared_session = session_registry.record_turn(
                session_id,
                identity,
                live_speaker,
                text_value,
                refined,
                {},
                device_id=device_id,
                speaker_label=live_speaker_label,
            )
            result = TranslationResult(
                source_text=text_value,
                improved_text=text_value,
                translated_text=refined,
                audio_output_path=None,
            )
            await websocket.send_json({"type": "session_sync", "session": shared_session})
            await websocket.send_json({
                "type": "final",
                "speaker": live_speaker,
                "speaker_label": live_speaker_label,
                "speaker_index": speaker_index,
                "device_id": device_id,
                "detection": speaker_detection,
                "source": "browser_live_text",
                "translated_by": "UT",
                "clarify": False,
                "session": shared_session,
                **result.__dict__,
            })
            complete_decision = conversation_brain.end_turn(live_speaker)
            await websocket.send_json({
                "type": "turn",
                "speaker": live_speaker,
                "speaker_label": live_speaker_label,
                "allowed": complete_decision.allowed,
                "reason": complete_decision.reason,
                "behavior": complete_decision.behavior,
                "active_speaker": complete_decision.active_speaker,
                "playback_owner": complete_decision.playback_owner,
            })
            return

        live_tts_delta = live_translation_delta(partial_tts_text, refined)
        # Only speak new words (real delta). Never fall back to full sentence —
        # that causes repeating from the start when translation rewrites itself.
        if not get_partial_tts_mode() or not is_speakable_live_delta(live_tts_delta):
            return
        candidate = live_tts_delta

        # Accumulate into buffer — only start the clock on first text, never reset mid-speech
        now = time()
        if not phrase_accumulation_buffer:
            phrase_accumulation_start = now
        phrase_accumulation_buffer = candidate

        # Fire when: interval elapsed OR enough words accumulated
        elapsed = now - last_partial_tts_at
        word_count = len(phrase_accumulation_buffer.split())
        time_accumulating = now - phrase_accumulation_start

        too_soon = elapsed < PARTIAL_TTS_MIN_INTERVAL
        too_short = word_count < PARTIAL_TTS_MIN_WORDS
        # Force fire if we've been accumulating > 2s regardless of word count
        force = time_accumulating >= 1.5 and word_count >= 2

        if too_soon and not force:
            return
        if too_short and not force:
            return

        words = phrase_accumulation_buffer.split()
        live_tts_to_speak = " ".join(words[:PARTIAL_TTS_MAX_WORDS])
        logger.info("live_tts_firing words=%d elapsed=%.1fs text=%r", word_count, elapsed, live_tts_to_speak[:60])
        phrase_accumulation_buffer = ""
        phrase_accumulation_start = 0.0
        await emit_live_tts(live_tts_to_speak, partial=True)

    async def finalize_segment(segment: dict):
        nonlocal speaker, speaker_label, speaker_index, speaker_detection, device_id, finalizing, last_active_speaker, tts_active
        if finalizing:
            return
        finalizing = True
        segment_started_at = time()
        audio_path = None

        try:
            audio_bytes = segment["audio_bytes"]
            segment_speaker_mode = segment["speaker_mode"]
            segment_speaker_detection = segment.get("speaker_detection", "manual")
            segment_session_id = segment["session_id"]
            segment_source_language = segment["source_language"]
            segment_target_language = segment["target_language"]
            segment_mime_type = segment["client_mime_type"]
            segment_audio_suffix = segment["audio_suffix"]
            segment_partial_text = segment.get("partial_text", "")
            segment_partial_tts_text = segment.get("partial_tts_text", "")
            speaker = segment["speaker"]
            speaker_label = segment.get("speaker_label") or speaker
            speaker_index = segment.get("speaker_index") or speaker_index
            device_id = segment.get("device_id")
            speaker_detection = segment_speaker_detection
            if not audio_bytes:
                await websocket.send_json({"type": "error", "message": "No audio received."})
                return
            # mark active speaker for interruption heuristics
            last_active_speaker = speaker

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
                speaker_profile = session_registry.resolve_auto_speaker(
                    segment_session_id,
                    identity,
                    device_id,
                    segment_source_language,
                    segment_target_language,
                    speaker_label,
                )
                speaker = speaker_profile["speaker"]
                speaker_label = speaker_profile["speaker_label"]
                speaker_index = speaker_profile["speaker_index"]
                device_id = speaker_profile["device_id"]
                speaker_detection = speaker_profile["detection"]
            else:
                session_registry.bind(
                    segment_session_id,
                    speaker,
                    identity,
                    segment_source_language,
                    segment_target_language,
                    device_id=device_id,
                    speaker_label=speaker_label,
                    speaker_index=speaker_index,
                    detection=speaker_detection,
                )

            # Speaker memory: lock language per speaker unless HT/auto STT is active
            auto_stt = stt_only or language_pair_has_ht(segment_source_language, segment_target_language)
            if auto_stt:
                active_source_language = segment_source_language
            else:
                speaker_memory.register(speaker, language=segment_source_language)
                active_source_language = speaker_memory.get_language(speaker) or segment_source_language
            active_target_language = segment_target_language
            await websocket.send_json({
                "type": "speaker_detected",
                "speaker": speaker,
                "speaker_label": speaker_label,
                "speaker_index": speaker_index,
                "mode": segment_speaker_mode,
                "detection": speaker_detection,
                "confidence": 1.0 if speaker_detection == "device_source" else None,
                "device_id": device_id,
                "source_language": active_source_language,
                "target_language": active_target_language,
            })

            decision = conversation_brain.request_turn(speaker)
            await websocket.send_json({
                "type": "turn",
                "speaker": speaker,
                "speaker_label": speaker_label,
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

            # Re-mux iOS Safari WebM/MP4 chunks to clean PCM WAV before decoding
            stt_input_path = str(audio_path)
            transcoded_path = None
            if segment_audio_suffix.lower() in {".webm", ".m4a", ".mp4", ".ogg", ".aac"}:
                try:
                    transcoded_path = await run_in_threadpool(transcode_to_wav, str(audio_path))
                except (RuntimeError, ValueError, OSError) as transcode_exc:
                    observability.record_event(
                        "audio_transcode_failed",
                        identity=identity,
                        speaker=speaker,
                        error=str(transcode_exc),
                    )
                    transcoded_path = None
                if transcoded_path:
                    stt_input_path = transcoded_path

            await websocket.send_json({"type": "stage", "stage": "stt", "message": "Speech finalized. Transcribing now..."})
            observability.record_event("mobile_stream_checkpoint", identity=identity, speaker=speaker, checkpoint="stt_start", audio_bytes=len(audio_bytes), mime_type=segment_mime_type)
            stt_started_at = time()
            # Denoise/normalize audio if possible
            processed_path, proc_metrics = process_wav_for_stt(str(stt_input_path))
            stt_call_input = processed_path or str(stt_input_path)
            try:
                stt_language = resolve_whisper_language(
                    segment_source_language,
                    segment_target_language,
                    stt_only=stt_only,
                )
                source_text = await run_pipeline_step("STT", pipeline.stt.transcribe, stt_call_input, stt_language)
            except (RuntimeError, ValueError, OSError) as stt_exc:
                message = str(stt_exc)
                if "Invalid data found" in message or "1094995529" in message:
                    message = "Could not decode that audio clip. Try speaking again - hold the button a moment longer."
                await websocket.send_json({"type": "error", "message": message, "recoverable": True})
                observability.record_event("stt_failed", identity=identity, speaker=speaker, error=str(stt_exc), mime_type=segment_mime_type)
                return
            finally:
                if transcoded_path:
                    Path(transcoded_path).unlink(missing_ok=True)
                if processed_path and processed_path != str(stt_input_path):
                    Path(processed_path).unlink(missing_ok=True)
            stt_ms = round((time() - stt_started_at) * 1000)
            if not source_text.strip() and segment_partial_text.strip():
                source_text = segment_partial_text
            stream_debug_log("STT:", stt_ms, "ms", source_text)
            await websocket.send_json({"type": "latency", "metric": "stt", "ms": stt_ms})
            observability.record_event("mobile_stream_checkpoint", identity=identity, speaker=speaker, checkpoint="stt_done", source_text=source_text)
            # Weak audio guidance (distance-aware)
            try:
                rms_after = (proc_metrics or {}).get("rms_after")
                if (rms_after is not None) and rms_after < 0.02 and len(source_text.split()) < 2:
                    await websocket.send_json({"type": "stage", "stage": "weak_audio", "message": "Move closer to the microphone or reduce noise."})
            except (ConnectionError, RuntimeError, KeyError) as exc:
                logger.debug("weak_audio_hint_send_failed error=%s", exc)
            if not source_text.strip():
                await websocket.send_json({"type": "error", "message": "No clear speech recognized. Try speaking closer to the mic."})
                return
            if auto_stt:
                active_source_language = detect_language_in_pair(
                    source_text,
                    segment_source_language,
                    segment_target_language,
                )
                active_target_language = opposite_language_in_pair(
                    active_source_language,
                    segment_source_language,
                    segment_target_language,
                )
                speaker_memory.register(speaker, language=active_source_language)
            await websocket.send_json({"type": "final_transcription", "speaker": speaker, "speaker_label": speaker_label, "text": source_text})
            if stt_only:
                await websocket.send_json({
                    "type": "stt_only",
                    "speaker": speaker,
                    "speaker_label": speaker_label,
                    "text": source_text,
                    "source_language": active_source_language,
                    "target_language": active_target_language,
                })
                complete_decision = conversation_brain.end_turn(speaker)
                await websocket.send_json({
                    "type": "turn",
                    "speaker": speaker,
                    "speaker_label": speaker_label,
                    "allowed": complete_decision.allowed,
                    "reason": complete_decision.reason,
                    "behavior": complete_decision.behavior,
                    "active_speaker": complete_decision.active_speaker,
                    "playback_owner": complete_decision.playback_owner,
                })
                return
            semantic_context = conversation_brain.analyze_semantics(speaker, source_text)
            await websocket.send_json({"type": "semantic_context", "speaker": speaker, "speaker_label": speaker_label, **semantic_context})
            await websocket.send_json({"type": "stage", "stage": "translation", "message": "Transcription ready. Translating..."})

            translation_started_at = time()
            # Use raw source_text for context improvement; refinement applies after translation
            ref_source_text = source_text
            improved_text = await run_pipeline_step(
                "context improvement",
                pipeline.context_layer.improve,
                ref_source_text,
                active_source_language,
                active_target_language,
                None,
            )
            raw_translated_text = await run_pipeline_step(
                "translation",
                lambda: pipeline.translate_local(
                    improved_text,
                    active_source_language,
                    active_target_language,
                    session_id=segment_session_id,
                    original_source_text=source_text,
                ),
            )
            memory_context = memory.get_context()
            speaker_context = speaker_memory.get_context(speaker)
            translated_text = refine_translation(source_text, raw_translated_text, memory_context, speaker_context)
            # CIP override and decision
            cip = None
            stt_conf = estimate_stt_confidence(source_text)
            tr_conf = estimate_translation_confidence(source_text, translated_text)
            try:
                cip = await call_cip_brain(
                    source_text,
                    active_target_language,
                    identity,
                    fallback_translation=translated_text,
                    source_language=active_source_language,
                    stt_confidence=stt_conf,
                    translation_confidence=tr_conf,
                    context=memory_context,
                    speaker_context=speaker_context,
                    semantic_context=semantic_context,
                )
            except (RuntimeError, ValueError, ConnectionError):
                cip = None
            cip_decision = get_cip_decision(cip)
            cip_clarify = is_cip_clarification(cip)
            pre_cip_translation = translated_text
            segment_glossary = get_session_glossary(segment_session_id)
            if cip_clarify and glossary_blocks_clarification(
                source_text,
                pre_cip_translation,
                segment_glossary,
                active_source_language,
                active_target_language,
            ):
                cip_clarify = False
            cip_response_plan = cip.get("response_plan") if isinstance(cip, dict) and isinstance(cip.get("response_plan"), dict) else {}
            cip_turn_policy = cip_response_plan.get("turn_policy") if isinstance(cip_response_plan.get("turn_policy"), dict) else {}
            cip_client_hints = cip_response_plan.get("client_hints") if isinstance(cip_response_plan.get("client_hints"), dict) else {}
            translated_text = resolve_translation_text(cip_clarify, cip, translated_text)
            # Confidence and ambiguity checks for final
            tr_conf = estimate_translation_confidence(source_text, translated_text)
            cip_conf = get_cip_confidence(cip)
            domains = detect_domains(source_text)
            glossary_cov = glossary_coverage_score(
                source_text,
                translated_text,
                segment_glossary,
                active_source_language,
                active_target_language,
            )
            assessment = assess_translation_confidence(
                source_text,
                translated_text,
                stt_confidence=stt_conf,
                domains=domains,
                glossary_coverage=glossary_cov,
            )
            conf_score = cip_conf if cip_conf is not None else assessment["confidence"]
            if assessment["low_confidence"] and not cip_clarify:
                await websocket.send_json({
                    "type": "confidence_warning",
                    "confidence": assessment["confidence"],
                    "threshold": assessment["confidence_threshold"],
                    "high_stakes": assessment["high_stakes"],
                    "needs_confirmation": assessment["needs_confirmation"],
                    "message": assessment["confidence_message"],
                    "domains": assessment["high_stakes"],
                })
            if conf_score < 0.4 and not cip_clarify:
                await websocket.send_json({"type": "clarify", "message": clarification_for(source_text, detect_ambiguities(source_text)), "stage": "final_low_confidence"})
            translation_ms = round((time() - translation_started_at) * 1000)
            intent = semantic_context.get("last_intent") or semantic_context.get("intent") or "statement"
            urgency = "high" if semantic_context.get("conversation_mood") == "urgent" else None
            tts_playback_text = translated_text
            live_spoken_text = normalize_live_text(segment_partial_tts_text)
            if live_spoken_text:
                live_tail = live_translation_delta(live_spoken_text, translated_text)
                if is_speakable_live_delta(live_tail):
                    tts_playback_text = live_tail
                elif folded_live_text(translated_text).startswith(folded_live_text(live_spoken_text)):
                    tts_playback_text = ""
            tts_pacing = build_tts_pacing(tts_playback_text or translated_text, intent, urgency)
            stream_debug_log("Translate:", translation_ms, "ms", translated_text)
            await websocket.send_json({"type": "latency", "metric": "translation", "ms": translation_ms})
            if cip:
                await websocket.send_json({
                    "type": "cip",
                    "speaker": speaker,
                    "speaker_label": speaker_label,
                    "provider": cip.get("provider"),
                    "confidence": cip.get("confidence"),
                    "decision": cip_decision,
                    "analysis": cip.get("analysis"),
                    "response_plan": cip_response_plan,
                    "turn_policy": cip_turn_policy,
                    "client_hints": cip_client_hints,
                    "translated_by": cip.get("translation_source"),
                })
            if translated_text.strip():
                await websocket.send_json({"type": "live_translation", "speaker": speaker, "speaker_label": speaker_label, "text": translated_text})
            if not cip_clarify:
                await websocket.send_json({"type": "tts_style", "speaker": speaker, "speaker_label": speaker_label, **tts_pacing})
            observability.record_event("mobile_stream_checkpoint", identity=identity, speaker=speaker, checkpoint="translation_done", translated_text=translated_text)
            # If CIP requested clarification, inform client and skip TTS
            skip_tts = bool(cip_client_hints.get("skip_tts")) or not is_speakable_live_delta(tts_playback_text)
            if cip_clarify:
                msg = cip_decision.get("message") or "Can you rephrase that?"
                await websocket.send_json({"type": "clarify", "message": msg, "stage": "cip_clarification"})
                skip_tts = True
            skip_message = "Clarification requested. Skipping TTS." if cip_clarify else "Live voice already streamed."
            await websocket.send_json({"type": "stage", "stage": "tts" if not skip_tts else "tts_skipped", "message": "Translation ready. Streaming voice..." if not skip_tts else skip_message})
            playback_decision = conversation_brain.begin_playback(speaker)
            await websocket.send_json({
                "type": "turn",
                "speaker": speaker,
                "speaker_label": speaker_label,
                "allowed": playback_decision.allowed,
                "reason": playback_decision.reason,
                "behavior": playback_decision.behavior,
                "active_speaker": playback_decision.active_speaker,
                "playback_owner": playback_decision.playback_owner,
                "cip_turn_policy": cip_turn_policy,
                "cip_client_hints": cip_client_hints,
                "cip_repair_options": cip_response_plan.get("repair_options") if cip_response_plan else None,
                "meaning_risk_score": cip_response_plan.get("meaning_risk_score") if cip_response_plan else None,
            })

            audio_output_path = None
            tts_chunks = []
            if not skip_tts:
                for tts_segment in tts_pacing["segments"]:
                    tts_chunks.extend(chunk_text_for_tts(tts_segment))
                await websocket.send_json({
                    "type": "tts_start",
                    "speaker": speaker,
                    "speaker_label": speaker_label,
                    "chunks": len(tts_chunks),
                    "cip_turn_policy": cip_turn_policy,
                    "latency_budget_ms": cip_client_hints.get("latency_budget_ms"),
                })

            tts_started_at = time()
            tts_active = True
            for index, chunk in enumerate(tts_chunks if not skip_tts else [], start=1):
                try:
                    chunk_output_path = await run_pipeline_step(
                        "TTS",
                        lambda c=chunk, idx=index: pipeline.tts.synthesize(
                            c,
                            f"models/tts/{uuid4()}-{idx}.wav",
                            language=active_target_language,
                        ),
                    )
                    if audio_output_path is None:
                        audio_output_path = chunk_output_path
                    tts_audio_bytes = Path(chunk_output_path).read_bytes()
                    # Validate audio data is not empty or too small
                    if len(tts_audio_bytes) < 100:
                        stream_debug_log(f"TTS chunk {index} too small ({len(tts_audio_bytes)} bytes), skipping")
                        continue
                    observability.record_event("mobile_stream_checkpoint", identity=identity, speaker=speaker, checkpoint="tts_chunk", index=index, total=len(tts_chunks), audio_bytes=len(tts_audio_bytes))
                    observability.increment("tts_playback_chunks_total")
                    tts_ms = round((time() - tts_started_at) * 1000)
                    stream_debug_log("TTS:", tts_ms, "ms", "chunk", index, "of", len(tts_chunks))
                    await websocket.send_json({"type": "latency", "metric": "tts", "ms": tts_ms})
                    await websocket.send_json({
                        "type": "tts_audio_chunk",
                        "speaker": speaker,
                        "speaker_label": speaker_label,
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
                except (RuntimeError, ValueError, OSError, base64.Error) as e:
                    stream_debug_log(f"TTS synthesis failed for chunk {index}: {e}")
                    observability.record_event("mobile_stream_error", identity=identity, speaker=speaker, error=str(e), chunk_index=index)
                    # Send error message to frontend instead of invalid audio
                    await websocket.send_json({
                        "type": "error",
                        "message": f"TTS synthesis failed for chunk {index}: {str(e)}"
                    })
                    break

            await websocket.send_json({"type": "tts_end", "speaker": speaker, "speaker_label": speaker_label})
            tts_active = False
            memory.add(speaker, source_text, translated_text, {"cip": cip})
            speaker_memory.add_message(speaker, source_text)
            result = TranslationResult(
                source_text=source_text,
                improved_text=improved_text,
                translated_text=translated_text,
                audio_output_path=audio_output_path,
            )
            shared_session = session_registry.record_turn(
                segment_session_id,
                identity,
                speaker,
                source_text,
                translated_text,
                semantic_context,
                device_id=device_id,
                speaker_label=speaker_label,
            )
            await websocket.send_json({"type": "session_sync", "session": shared_session})
            stream_debug_log("FINAL TRIGGERED")
            await websocket.send_json({
                "type": "final",
                "speaker": speaker,
                "speaker_label": speaker_label,
                "speaker_index": speaker_index,
                "device_id": device_id,
                "detection": speaker_detection,
                "source_language": active_source_language,
                "target_language": active_target_language,
                "semantic_context": semantic_context,
                "cip_decision": cip_decision,
                "cip_analysis": cip.get("analysis") if isinstance(cip, dict) else None,
                "cip_confidence": cip.get("confidence") if isinstance(cip, dict) else None,
                "cip_provider": cip.get("provider") if isinstance(cip, dict) else None,
                "cip_response_plan": cip_response_plan if cip_response_plan else None,
                "cip_turn_policy": cip_turn_policy if cip_turn_policy else None,
                "cip_client_hints": cip_client_hints if cip_client_hints else None,
                "translated_by": cip.get("translation_source") if isinstance(cip, dict) and cip.get("translated") and cip.get("translation_source") else "UT",
                "clarify": cip_clarify or assessment["low_confidence"] or conf_score < 0.4,
                "confidence": assessment["confidence"],
                "confidence_threshold": assessment["confidence_threshold"],
                "low_confidence": assessment["low_confidence"],
                "needs_confirmation": assessment["needs_confirmation"],
                "confidence_message": assessment["confidence_message"],
                "high_stakes_domains": assessment["high_stakes"],
                "session": shared_session,
                **result.__dict__,
            })
            observability.observe_latency("streaming_segment", time() - segment_started_at)
            observability.record_event("streaming_segment", identity=identity, speaker=speaker, latency_seconds=time() - segment_started_at)
            total_ms = round((time() - segment_started_at) * 1000)
            await websocket.send_json({"type": "latency", "metric": "backend_response", "ms": total_ms})
            # Update latency engine for adaptive decisions next turns
            latency_engine.update(stt=stt_ms / 1000.0, translate=translation_ms / 1000.0, tts=(0.0))
            usage_limiter.track_audio(identity, estimated_seconds, "streaming_segments")
            complete_decision = conversation_brain.end_turn(speaker)
            await websocket.send_json({
                "type": "turn",
                "speaker": speaker,
                "speaker_label": speaker_label,
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
            except (RuntimeError, ValueError, KeyError) as exc:
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
                if (
                    speech_started
                    and audio_chunks
                    and last_speech_at
                    and time() - last_speech_at > get_vad_force_final_seconds()
                    and not (live_text_active_until and time() < live_text_active_until)
                    and not (live_text_final_until and time() < live_text_final_until)
                ):
                    stream_debug_log("FORCE FINAL")
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

                if message_type == "live_text":
                    await schedule_live_text(payload)
                    continue

                if message_type == "chunk_meta":
                    if payload.get("mime_type"):
                        client_mime_type = payload.get("mime_type")
                        audio_suffix = audio_suffix_for_mime(client_mime_type)
                    last_chunk_meta = {
                        "sent_at_ms": payload.get("sent_at_ms"),
                        "bytes": payload.get("bytes"),
                        "mime_type": payload.get("mime_type") or client_mime_type,
                        "audio_level": payload.get("audio_level"),
                        "client_voice_active": extract_client_voice_active(payload),
                        "received_at": time(),
                    }
                    continue

                if message_type == "start":
                    if not runtime_state.get("ready"):
                        await websocket.send_json({
                            "type": "error",
                            "message": "Models still loading. Wait for LIVE.",
                            "recoverable": True,
                            "warming": True,
                        })
                        continue
                    previous_session_id = session_id
                    previous_speaker = speaker
                    previous_device_id = device_id
                    speaker_mode = payload.get("speaker_mode", "manual")
                    session_id = payload.get("session_id", "default")
                    source_language = payload.get("source_language", "en")
                    target_language = payload.get("target_language", "ht")
                    stt_only = bool(payload.get("stt_only"))
                    device_id = payload.get("device_id")
                    requested_speaker_label = payload.get("speaker_name") or payload.get("speaker_label")
                    if previous_device_id:
                        session_registry.disconnect(previous_session_id, previous_speaker, identity, previous_device_id)
                    if session_registry.active_stream_count(identity) >= get_max_active_streams_per_user():
                        await websocket.send_json({"type": "error", "message": "Too many active streams for this user.", "recoverable": True})
                        continue
                    if speaker_mode == "auto":
                        speaker_profile = session_registry.resolve_auto_speaker(
                            session_id,
                            identity,
                            device_id,
                            source_language,
                            target_language,
                            requested_speaker_label,
                        )
                        speaker = speaker_profile["speaker"]
                        speaker_label = speaker_profile["speaker_label"]
                        speaker_index = speaker_profile["speaker_index"]
                        device_id = speaker_profile["device_id"]
                        speaker_detection = speaker_profile["detection"]
                        session_state = speaker_profile["session"]
                    else:
                        speaker = payload.get("speaker", "speaker")
                        speaker_label = requested_speaker_label or f"Speaker {speaker}"
                        speaker_detection = "manual"
                        session_state = session_registry.bind(
                            session_id,
                            speaker,
                            identity,
                            source_language,
                            target_language,
                            device_id=device_id,
                            speaker_label=speaker_label,
                            detection=speaker_detection,
                        )
                        speaker_index = session_state.get("speaker_index", speaker_index)
                        device_id = session_state.get("device_id")
                    client_mime_type = payload.get("mime_type") or client_mime_type
                    audio_suffix = audio_suffix_for_mime(client_mime_type)
                    await websocket.send_json({
                        "type": "speaker_detected",
                        "speaker": speaker,
                        "speaker_label": speaker_label,
                        "speaker_index": speaker_index,
                        "mode": speaker_mode,
                        "detection": speaker_detection,
                        "confidence": 1.0 if speaker_detection == "device_source" else None,
                        "device_id": device_id,
                        "source_language": source_language,
                        "target_language": target_language,
                    })
                    await websocket.send_json({
                        "type": "turn",
                        "speaker": speaker,
                        "speaker_label": speaker_label,
                        "allowed": True,
                        "reason": "Speaker connected",
                        "behavior": "ready",
                        "active_speaker": conversation_brain.active_speaker,
                        "playback_owner": conversation_brain.playback_owner,
                    })
                    reset_segment_state()
                    await websocket.send_json({
                        "type": "session_restored",
                        "session": session_state,
                        "message": "Speaker stream bound to session.",
                    })
                    await websocket.send_json({
                        "type": "listening",
                        "speaker": speaker,
                        "speaker_label": speaker_label,
                        "speaker_mode": speaker_mode,
                        "detection": speaker_detection,
                        "device_id": device_id,
                        "message": "Receiving audio for transcription only." if stt_only else "Receiving audio chunks with Silero VAD.",
                    })

                if message_type == "finalize":
                    await enqueue_finalize("client_finalize")

                if message_type == "cancel":
                    conversation_brain.cancel(speaker)
                    reset_segment_state()
                    await websocket.send_json({"type": "cancelled"})

            if "bytes" in message:
                chunk = message["bytes"]
                stream_debug_log("AUDIO RECEIVED:", len(chunk))
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

                client_vad_available = get_client_vad_mode() and last_chunk_meta.get("client_voice_active") is not None
                if client_vad_available:
                    try:
                        audio_level = float(last_chunk_meta.get("audio_level") or 0.0)
                    except (TypeError, ValueError):
                        audio_level = 0.0
                    voice_active = bool(last_chunk_meta.get("client_voice_active")) or audio_level >= get_client_vad_threshold()
                    if voice_active:
                        speech_started = True
                        last_speech_at = time()
                        silent_checks = 0
                        await announce_active_speaker("client_vad", audio_level)
                        await emit_partial_pipeline()
                        await websocket.send_json({
                            "type": "vad",
                            "speech_detected": True,
                            "source": "client",
                            "audio_level": audio_level,
                        })
                        continue
                    if speech_started:
                        silent_checks += 1
                        if (time() - last_speech_at) * 1000 < get_speech_merge_ms():
                            continue
                        await websocket.send_json({
                            "type": "vad",
                            "speech_detected": False,
                            "source": "client",
                            "silent_checks": silent_checks,
                            "audio_level": audio_level,
                        })
                        if silent_checks >= get_vad_silent_checks():
                            await enqueue_finalize("client_vad_silence")
                        continue
                    audio_chunks = bytearray()
                    recent_chunks = []
                    continue

                try:
                    vad_result = await run_in_threadpool(vad.detect_bytes, b"".join(recent_chunks), audio_suffix)
                except (RuntimeError, ValueError, OSError) as exc:
                    observability.increment("vad_errors_total")
                    vad_error_count += 1
                    if len(audio_chunks) >= get_min_speech_bytes():
                        speech_started = True
                        last_speech_at = time()
                        await announce_active_speaker("byte_buffer", None)
                        await websocket.send_json({"type": "stage", "stage": "listening", "message": "Audio buffered. Keep talking..."})
                    elif vad_error_count == 1:
                        await websocket.send_json({"type": "partial_transcription", "text": f"Preparing audio stream ({len(audio_chunks)} bytes)..."})
                    if vad_error_count in {1, 5}:
                        await websocket.send_json({"type": "vad_error", "message": str(exc), "fallback": "byte_buffer"})
                    continue

                if vad_result["speech_detected"]:
                    stream_debug_log("VAD:", True)
                    observability.increment("vad_speech_total")
                    speech_started = True
                    last_speech_at = time()
                    silent_checks = 0
                    await announce_active_speaker("server_vad", None)
                    await emit_partial_pipeline()
                    observability.record_event("mobile_stream_checkpoint", identity=identity, speaker=speaker, checkpoint="vad_speech", speech_seconds=vad_result["speech_seconds"])
                    await websocket.send_json({
                        "type": "vad",
                        "speech_detected": True,
                        "speech_seconds": vad_result["speech_seconds"],
                    })
                    await websocket.send_json({"type": "stage", "stage": "listening", "message": "Speech detected. Keep talking..."})
                elif speech_started:
                    stream_debug_log("VAD:", False)
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
                    stream_debug_log("VAD:", False)
                    observability.increment("vad_silence_total")
                    await websocket.send_json({"type": "partial_transcription", "text": "Waiting for speech..."})

    except WebSocketDisconnect:
        observability.increment("websocket_disconnects_total")
        session_registry.disconnect(session_id, speaker, identity, device_id)
        return
    except (RuntimeError, ValueError, ConnectionError, TimeoutError):
        observability.increment("websocket_errors_total")
        raise
    finally:
        session_registry.disconnect(session_id, speaker, identity, device_id)
        if partial_task is not None:
            partial_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await partial_task
        if live_text_task is not None:
            live_text_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await live_text_task
        pipeline_worker.cancel()
        with suppress(asyncio.CancelledError):
            await pipeline_worker


# ---------------------------------------------------------------------------
# Streaming STT Provider — real-time transcription via the STT provider
# ---------------------------------------------------------------------------


async def websocket_streaming_stt_translation(
    websocket: WebSocket,
    pipeline: AnaiTranslatorPipeline,
    conversation_brain: ConversationBrain,
    memory: ConversationMemory | None = None,
    speaker_memory: SpeakerMemory | None = None,
    identity: str = "anonymous",
):
    """WebSocket handler that proxies audio to the streaming STT provider.

    When ``STT_PROVIDER=streaming``, this handler replaces the local
    VAD + Whisper pipeline with the STT provider's WebSocket streaming
    API.  The browser sends PCM16 audio frames; we forward them to the
    STT provider and receive ``transcript.partial`` / ``transcript.final``
    events.  Final transcripts are then sent through the translator pipeline.
    """
    import websockets

    await websocket.accept()
    observability.increment("websocket_connects_total")

    memory = memory or ConversationMemory()
    speaker_memory = speaker_memory or SpeakerMemory()
    source_language = "en"
    target_language = "ht"
    speaker = "speaker"
    speaker_label = "Person 1"
    speaker_index = 1
    speaker_mode = "manual"
    speaker_detection = "manual"
    session_id = "default"
    device_id = None
    provider_ws = None
    provider_receiver_task = None
    provider_language = None
    send_lock = asyncio.Lock()
    container_audio_warned = False

    async def send_json(payload: dict) -> None:
        async with send_lock:
            await websocket.send_json(payload)

    await send_json({"type": "ready", "message": "Streaming STT connected."})

    async def close_provider() -> None:
        nonlocal provider_ws, provider_receiver_task, provider_language
        if provider_receiver_task is not None:
            provider_receiver_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await provider_receiver_task
            provider_receiver_task = None
        if provider_ws is not None:
            with suppress(Exception):
                await provider_ws.close()
            provider_ws = None
        provider_language = None

    async def emit_translated_final(
        source_text: str,
        *,
        src_lang: str | None = None,
        tgt_lang: str | None = None,
        live_text_source: bool = False,
    ) -> None:
        source_text = normalize_live_text(source_text)
        if not source_text:
            return
        pair_src = src_lang or source_language
        pair_tgt = tgt_lang or target_language
        active_src, active_tgt = resolve_active_languages_in_pair(source_text, pair_src, pair_tgt)

        if live_text_source:
            await send_json({
                "type": "partial_transcription",
                "speaker": speaker,
                "speaker_label": speaker_label,
                "text": source_text,
                "source": "browser_live_text",
                "final": True,
            })
        else:
            await send_json({
                "type": "final_transcription",
                "speaker": speaker,
                "speaker_label": speaker_label,
                "text": source_text,
            })
        semantic_context = conversation_brain.analyze_semantics(speaker, source_text)
        await send_json({"type": "semantic_context", "speaker": speaker, "speaker_label": speaker_label, **semantic_context})
        await send_json({"type": "stage", "stage": "translation", "message": "Transcription ready. Translating..."})

        translation_started_at = time()
        improved_text = await run_pipeline_step(
            "context improvement",
            pipeline.context_layer.improve,
            source_text,
            active_src,
            active_tgt,
            None,
        )
        raw_translated_text = await run_pipeline_step(
            "translation",
            lambda: pipeline.translate_local(
                improved_text,
                active_src,
                active_tgt,
                session_id=session_id,
                original_source_text=source_text,
            ),
        )
        memory_context = memory.get_context()
        speaker_context = speaker_memory.get_context(speaker)
        translated_text = refine_translation(source_text, raw_translated_text, memory_context, speaker_context)
        stt_conf = estimate_stt_confidence(source_text)
        tr_conf = estimate_translation_confidence(source_text, translated_text)
        cip = None
        try:
            cip = await call_cip_brain(
                source_text,
                active_tgt,
                identity,
                fallback_translation=translated_text,
                source_language=active_src,
                stt_confidence=stt_conf,
                translation_confidence=tr_conf,
                context=memory_context,
                speaker_context=speaker_context,
                semantic_context=semantic_context,
            )
        except (ConnectionError, TimeoutError, RuntimeError, ValueError):
            cip = None
        cip_decision = get_cip_decision(cip)
        cip_clarify = is_cip_clarification(cip)
        pre_cip_translation = translated_text
        text_glossary = get_session_glossary(session_id)
        if cip_clarify and glossary_blocks_clarification(
            source_text,
            pre_cip_translation,
            text_glossary,
            active_src,
            active_tgt,
        ):
            cip_clarify = False
        cip_response_plan = cip.get("response_plan") if isinstance(cip, dict) and isinstance(cip.get("response_plan"), dict) else {}
        cip_turn_policy = cip_response_plan.get("turn_policy") if isinstance(cip_response_plan.get("turn_policy"), dict) else {}
        cip_client_hints = cip_response_plan.get("client_hints") if isinstance(cip_response_plan.get("client_hints"), dict) else {}
        translated_text = resolve_translation_text(cip_clarify, cip, translated_text)
        tr_conf = estimate_translation_confidence(source_text, translated_text)
        cip_conf = get_cip_confidence(cip)
        domains = detect_domains(source_text)
        glossary_cov = glossary_coverage_score(
            source_text,
            translated_text,
            text_glossary,
            active_src,
            active_tgt,
        )
        assessment = assess_translation_confidence(
            source_text,
            translated_text,
            stt_confidence=stt_conf,
            domains=domains,
            glossary_coverage=glossary_cov,
        )
        conf_score = cip_conf if cip_conf is not None else assessment["confidence"]
        translation_ms = round((time() - translation_started_at) * 1000)
        await send_json({"type": "latency", "metric": "translation", "ms": translation_ms})
        if cip:
            await send_json({
                "type": "cip",
                "speaker": speaker,
                "speaker_label": speaker_label,
                "provider": cip.get("provider"),
                "confidence": cip.get("confidence"),
                "decision": cip_decision,
                "analysis": cip.get("analysis"),
                "response_plan": cip_response_plan,
                "turn_policy": cip_turn_policy,
                "client_hints": cip_client_hints,
                "translated_by": cip.get("translation_source"),
            })
        if assessment["low_confidence"] and not cip_clarify:
            await send_json({
                "type": "confidence_warning",
                "confidence": assessment["confidence"],
                "threshold": assessment["confidence_threshold"],
                "high_stakes": assessment["high_stakes"],
                "needs_confirmation": assessment["needs_confirmation"],
                "message": assessment["confidence_message"],
                "domains": assessment["high_stakes"],
            })
        if translated_text.strip():
            live_payload = {
                "type": "live_translation",
                "speaker": speaker,
                "speaker_label": speaker_label,
                "text": translated_text,
                "final": True,
                "confidence": assessment["confidence"],
                "low_confidence": assessment["low_confidence"],
                "source_language": active_src,
                "target_language": active_tgt,
            }
            if live_text_source:
                live_payload["source"] = "browser_live_text"
            await send_json(live_payload)
        if cip_clarify:
            await send_json({"type": "clarify", "message": cip_decision.get("message") or "Can you rephrase that?", "stage": "cip_clarification"})
        elif conf_score < 0.4:
            await send_json({"type": "clarify", "message": clarification_for(source_text, detect_ambiguities(source_text)), "stage": "final_low_confidence"})

        tts_meta = {"source": "browser_live_text"} if live_text_source else {}
        if translated_text.strip() and not cip_clarify:
            tts_path = None
            try:
                tts_path = await run_pipeline_step(
                    "streaming STT TTS",
                    lambda: pipeline.tts.synthesize(
                        translated_text,
                        f"models/tts/{uuid4()}-streaming-stt.wav",
                        language=active_tgt,
                    ),
                )
                audio_bytes = Path(tts_path).read_bytes()
                if len(audio_bytes) >= 100:
                    await send_json({
                        "type": "tts_start",
                        "speaker": speaker,
                        "speaker_label": speaker_label,
                        "chunks": 1,
                        "partial": False,
                        **tts_meta,
                    })
                    await send_json({
                        "type": "tts_audio_chunk",
                        "speaker": speaker,
                        "speaker_label": speaker_label,
                        "index": 1,
                        "total": 1,
                        "text": translated_text,
                        "audio_base64": base64.b64encode(audio_bytes).decode("ascii"),
                        "mime_type": "audio/wav",
                        "partial": False,
                        **tts_meta,
                    })
            except Exception as exc:
                logger.warning("streaming_stt_tts_failed error=%s", exc)
            finally:
                if tts_path:
                    Path(tts_path).unlink(missing_ok=True)
        await send_json({
            "type": "tts_end",
            "speaker": speaker,
            "speaker_label": speaker_label,
            "partial": False,
            **tts_meta,
        })

        memory.add(speaker, source_text, translated_text, {"cip": cip})
        speaker_memory.add_message(speaker, source_text)
        shared_session = session_registry.record_turn(
            session_id,
            identity,
            speaker,
            source_text,
            translated_text,
            semantic_context,
            device_id=device_id,
            speaker_label=speaker_label,
        )
        result = TranslationResult(
            source_text=source_text,
            improved_text=improved_text,
            translated_text=translated_text,
            audio_output_path=None,
        )
        await send_json({"type": "session_sync", "session": shared_session})
        final_payload = {
            "type": "final",
            "speaker": speaker,
            "speaker_label": speaker_label,
            "speaker_index": speaker_index,
            "device_id": device_id,
            "detection": speaker_detection,
            "source_language": active_src,
            "target_language": active_tgt,
            "semantic_context": semantic_context,
            "cip_decision": cip_decision,
            "cip_analysis": cip.get("analysis") if isinstance(cip, dict) else None,
            "cip_confidence": cip.get("confidence") if isinstance(cip, dict) else None,
            "cip_provider": cip.get("provider") if isinstance(cip, dict) else None,
            "cip_response_plan": cip_response_plan if cip_response_plan else None,
            "cip_turn_policy": cip_turn_policy if cip_turn_policy else None,
            "cip_client_hints": cip_client_hints if cip_client_hints else None,
            "translated_by": cip.get("translation_source") if isinstance(cip, dict) and cip.get("translated") and cip.get("translation_source") else "UT",
            "clarify": cip_clarify or assessment["low_confidence"] or conf_score < 0.4,
            "confidence": assessment["confidence"],
            "confidence_threshold": assessment["confidence_threshold"],
            "low_confidence": assessment["low_confidence"],
            "needs_confirmation": assessment["needs_confirmation"],
            "confidence_message": assessment["confidence_message"],
            "high_stakes_domains": assessment["high_stakes"],
            "session": shared_session,
            **result.__dict__,
        }
        if live_text_source:
            final_payload["source"] = "browser_live_text"
        await send_json(final_payload)
        complete_decision = conversation_brain.end_turn(speaker)
        await send_json({
            "type": "turn",
            "speaker": speaker,
            "speaker_label": speaker_label,
            "allowed": complete_decision.allowed,
            "reason": complete_decision.reason,
            "behavior": complete_decision.behavior,
            "active_speaker": complete_decision.active_speaker,
            "playback_owner": complete_decision.playback_owner,
        })

    async def handle_provider_event(raw_message) -> None:
        if isinstance(raw_message, bytes):
            raw_message = raw_message.decode("utf-8", errors="ignore")
        try:
            event = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            return
        event_type = event.get("type", "unknown")
        if event_type == "transcript" and event.get("is_final") is True:
            event_type = "transcript.final"
        elif event_type == "transcript" and event.get("is_final") is False:
            event_type = "transcript.partial"
        text = normalize_live_text(event.get("text") or event.get("data", {}).get("text") or "")
        if event_type == "session.started":
            await send_json({"type": "stage", "stage": "stt_provider_connected", "message": "Streaming STT provider connected."})
        elif event_type == "transcript.partial":
            if text:
                await send_json({"type": "partial_transcription", "speaker": speaker, "speaker_label": speaker_label, "text": text})
        elif event_type == "transcript.final":
            if text:
                await emit_translated_final(text)
        elif event_type == "session.flushed":
            await send_json({"type": "stage", "stage": "stt_provider_flushed", "message": "Streaming STT provider flushed."})
        elif event_type == "error":
            await send_json({"type": "error", "message": event.get("message") or "Streaming STT provider error.", "recoverable": True})

    async def provider_receive_loop(active_provider_ws) -> None:
        try:
            async for raw_message in active_provider_ws:
                try:
                    await handle_provider_event(raw_message)
                except Exception as exc:
                    logger.warning("provider_event_error error=%s", exc)
                    await send_json({
                        "type": "error",
                        "message": f"STT provider event error: {exc}",
                        "recoverable": True,
                    })
        except Exception as exc:
            logger.warning("provider_receive_loop_failed error=%s", exc)
            await send_json({
                "type": "error",
                "message": f"STT provider disconnected: {exc}",
                "recoverable": True,
            })

    async def ensure_provider_connected() -> None:
        nonlocal provider_ws, provider_receiver_task, provider_language
        if provider_ws is not None and provider_language == resolve_whisper_language(source_language, target_language):
            return
        await close_provider()
        stt_bridge = pipeline.stt
        if not hasattr(stt_bridge, "is_streaming") or not stt_bridge.is_streaming:
            raise RuntimeError("STT provider is not configured for streaming mode.")
        client = stt_bridge.get_streaming_client()
        whisper_lang = resolve_whisper_language(source_language, target_language)
        provider_url = client._stream_url(language=whisper_lang)
        provider_ws = await websockets.connect(
            provider_url,
            max_size=8 * 1024 * 1024,
            close_timeout=client.connection_timeout,
            ping_timeout=client.connection_timeout,
            ping_interval=20,
        )
        provider_language = whisper_lang
        provider_receiver_task = asyncio.create_task(provider_receive_loop(provider_ws))

    try:
        while True:
            message = await websocket.receive()

            if "text" in message and message["text"] is not None:
                try:
                    data = json.loads(message["text"])
                except (json.JSONDecodeError, TypeError):
                    continue

                msg_type = data.get("type")

                if msg_type == "ping":
                    await send_json({"type": "pong"})
                    continue

                if msg_type in {"config", "start"}:
                    if not runtime_state.get("ready"):
                        await send_json({
                            "type": "error",
                            "message": "Models still loading. Wait for LIVE.",
                            "recoverable": True,
                            "warming": True,
                        })
                        continue
                    previous_session_id = session_id
                    previous_speaker = speaker
                    previous_device_id = device_id
                    previous_source_language = source_language
                    source_language = data.get("source_language", source_language)
                    target_language = data.get("target_language", target_language)
                    speaker_mode = data.get("speaker_mode", speaker_mode)
                    session_id = data.get("session_id", session_id)
                    device_id = data.get("device_id", device_id)
                    requested_speaker_label = data.get("speaker_name") or data.get("speaker_label")
                    if previous_device_id:
                        session_registry.disconnect(previous_session_id, previous_speaker, identity, previous_device_id)
                    if session_registry.active_stream_count(identity) >= get_max_active_streams_per_user():
                        await send_json({"type": "error", "message": "Too many active streams for this user.", "recoverable": True})
                        continue
                    if speaker_mode == "auto":
                        speaker_profile = session_registry.resolve_auto_speaker(
                            session_id,
                            identity,
                            device_id,
                            source_language,
                            target_language,
                            requested_speaker_label,
                        )
                        speaker = speaker_profile["speaker"]
                        speaker_label = speaker_profile["speaker_label"]
                        speaker_index = speaker_profile["speaker_index"]
                        device_id = speaker_profile["device_id"]
                        speaker_detection = speaker_profile["detection"]
                        session_state = speaker_profile["session"]
                    else:
                        speaker = data.get("speaker", speaker)
                        speaker_label = requested_speaker_label or data.get("speaker_label") or speaker_label
                        speaker_detection = "manual"
                        session_state = session_registry.bind(
                            session_id,
                            speaker,
                            identity,
                            source_language,
                            target_language,
                            device_id=device_id,
                            speaker_label=speaker_label,
                            detection=speaker_detection,
                        )
                        speaker_index = session_state.get("speaker_index", speaker_index)
                        device_id = session_state.get("device_id")
                    if previous_source_language != source_language:
                        await close_provider()
                    await send_json({
                        "type": "speaker_detected",
                        "speaker": speaker,
                        "speaker_label": speaker_label,
                        "speaker_index": speaker_index,
                        "mode": speaker_mode,
                        "detection": speaker_detection,
                        "confidence": 1.0 if speaker_detection == "device_source" else None,
                        "device_id": device_id,
                        "source_language": source_language,
                        "target_language": target_language,
                    })
                    await send_json({
                        "type": "turn",
                        "speaker": speaker,
                        "speaker_label": speaker_label,
                        "allowed": True,
                        "reason": "Speaker connected",
                        "behavior": "ready",
                        "active_speaker": conversation_brain.active_speaker,
                        "playback_owner": conversation_brain.playback_owner,
                    })
                    await send_json({"type": "session_restored", "session": session_state, "message": "Speaker stream bound to session."})
                    await send_json({
                        "type": "listening",
                        "speaker": speaker,
                        "speaker_label": speaker_label,
                        "speaker_mode": speaker_mode,
                        "detection": speaker_detection,
                        "device_id": device_id,
                        "message": "Receiving PCM16 audio chunks via streaming STT provider.",
                    })
                    await send_json({"type": "config_ack", "source_language": source_language, "target_language": target_language})

                elif msg_type == "translate" and data.get("text"):
                    text = data["text"].strip()
                    if text:
                        result = await run_pipeline_step(
                            "text translation",
                            pipeline.translate_text,
                            text,
                            source_language,
                            target_language,
                        )
                        await send_json({
                            "type": "translation",
                            **result.__dict__,
                        })

                elif msg_type == "live_text" and data.get("text"):
                    if not runtime_state.get("ready"):
                        await send_json({
                            "type": "error",
                            "message": "Models still loading. Wait for LIVE.",
                            "recoverable": True,
                            "warming": True,
                        })
                        continue
                    if bool(data.get("final")):
                        await emit_translated_final(
                            data.get("text", ""),
                            src_lang=data.get("source_language") or source_language,
                            tgt_lang=data.get("target_language") or target_language,
                            live_text_source=True,
                        )

                elif msg_type == "finalize":
                    if provider_ws is not None:
                        await provider_ws.send(json.dumps({"type": "flush"}))

                elif msg_type == "cancel":
                    conversation_brain.cancel(speaker)
                    await close_provider()
                    await send_json({"type": "cancelled"})

                continue

            if "bytes" not in message or message["bytes"] is None:
                continue
            pcm16_audio = message["bytes"]
            if not pcm16_audio:
                continue

            if looks_like_container_audio(pcm16_audio):
                if not container_audio_warned:
                    container_audio_warned = True
                    await send_json({
                        "type": "error",
                        "message": (
                            "Container audio (WebM/WAV) is not supported on streaming STT. "
                            "Use STT_PROVIDER=local or browser speech recognition."
                        ),
                        "recoverable": True,
                    })
                continue

            try:
                await ensure_provider_connected()
                await provider_ws.send(pcm16_audio)
            except (ConnectionError, TimeoutError, RuntimeError) as exc:
                logger.warning("Streaming STT error: %s", exc)
                await send_json({"type": "error", "message": f"STT error: {exc}", "recoverable": True})

    except WebSocketDisconnect:
        observability.increment("websocket_disconnects_total")
    except (RuntimeError, ValueError, ConnectionError, TimeoutError):
        observability.increment("websocket_errors_total")
        raise
    finally:
        await close_provider()
        session_registry.disconnect(session_id, speaker, identity, device_id)
