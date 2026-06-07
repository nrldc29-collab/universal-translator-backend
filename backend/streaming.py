import asyncio
import base64
import json
import logging
import os
import re
import unicodedata
from contextlib import suppress
from pathlib import Path
from time import time
from uuid import uuid4

logger = logging.getLogger("anai_translator")

from backend.conversation import ConversationBrain
from backend.memory import ConversationMemory
from backend.speakers import SpeakerMemory, detect_language_heuristic, resolve_barrier_route
from backend.refine import refine_translation

# AILang enhancement — optional, degrades gracefully if ailang is not installed
try:
    from ailang_integration.runtime.backend_hook import enhance_translation_v2 as _ailang_enhance_v2
    _AILANG_AVAILABLE = True
except ImportError:
    _AILANG_AVAILABLE = False
from backend.latency import LatencyEngine
from backend.stream_session import StreamSessionState
from backend.audio import process_wav_for_stt, compute_rms
from backend.cip_bridge import choose_translation, get_cip_confidence, get_cip_decision, should_block_translation_for_cip
from backend.confidence import ConfidenceEngine, estimate_stt_confidence, estimate_translation_confidence, detect_ambiguities, clarification_for
from backend.config import (
    LANGUAGES,
    get_client_vad_mode,
    get_client_vad_threshold,
    get_max_active_streams_per_user,
    get_max_audio_seconds,
    get_min_speech_bytes,
    get_near_zero_latency_mode,
    get_natural_tts_mode,
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
from backend.tts_pacing import build_tts_pacing, emotion_config_from_style, resolve_tts_emotion_config
from backend.tts_cache import cached_tts_payload as _cached_tts_payload_impl
from fastapi import WebSocket
from fastapi.concurrency import run_in_threadpool
from starlette.websockets import WebSocketDisconnect

from backend.pipeline import AnaiTranslatorPipeline
from speech import SileroVoiceActivityDetector
from tts import PiperTextToSpeech

BACKEND_LIVE_TTS_LANGS = {"en", "es", "ht", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja", "ko", "ar", "hi"}


def _language_code(language: str | None) -> str:
    if not language:
        return "en"
    return str(language).strip().lower().replace("_", "-").split("-")[0] or "en"


def _sanitize_language_code(language: str | None, default: str) -> str:
    """Clamp WebSocket language codes to supported pipeline languages."""
    code = _language_code(language or default)
    fallback = _language_code(default) if _language_code(default) in LANGUAGES else "en"
    return code if code in LANGUAGES else fallback


def _sanitize_session_id(session_id: str | None, default: str = "default") -> str:
    """Bound session identifiers from client config messages."""
    if not session_id:
        return default
    cleaned = re.sub(r"[^\w\-.:]", "", str(session_id).strip())[:128]
    return cleaned or default


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "auto", "barrier"}


def _should_use_backend_live_tts(language: str | None) -> bool:
    return _language_code(language) in BACKEND_LIVE_TTS_LANGS


def _ailang_enhancement_provider_enabled() -> bool:
    explicit = os.getenv("AILANG_ENHANCEMENTS_ENABLED")
    if explicit is not None:
        return explicit.strip().lower() in {"1", "true", "yes", "on"}

    def real_api_key(name: str) -> bool:
        value = os.getenv(name, "").strip()
        if not value:
            return False
        lowered = value.lower()
        return lowered not in {"replace-this", "your_api_key_here", "your-api-key-here"} and not lowered.startswith("your_api")

    ollama_enabled = os.getenv("OLLAMA_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    return bool(ollama_enabled or real_api_key("OPENAI_API_KEY") or real_api_key("ANTHROPIC_API_KEY"))


# Advanced optimization modules - optional, degrades gracefully
try:
    from backend.adaptive_vad import AdaptiveVAD
    _ADAPTIVE_VAD_AVAILABLE = True
except ImportError:
    _ADAPTIVE_VAD_AVAILABLE = False

try:
    from backend.smart_buffer import SmartBuffer, Priority
    _SMART_BUFFER_AVAILABLE = True
except ImportError:
    _SMART_BUFFER_AVAILABLE = False

try:
    from backend.audio_enhancer import AudioEnhancer
    _AUDIO_ENHANCER_AVAILABLE = True
except ImportError:
    _AUDIO_ENHANCER_AVAILABLE = False

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


def _tts_file_ready(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size >= 100
    except OSError:
        return False


def _unlink_temp_tts_file(path: str | Path | None) -> None:
    if not path:
        return
    tts_path = Path(path)
    try:
        cache_dir = Path("models/tts/cache").resolve()
        if tts_path.resolve().parent == cache_dir:
            return
        tts_path.unlink(missing_ok=True)
    except (OSError, PermissionError):
        pass


def _synthesize_tts_resilient(
    tts_engine,
    text: str,
    output_path: str | Path,
    language: str,
    google_api_key: str | None = None,
    emotion_config: dict | None = None,
) -> str:
    output_path = Path(output_path)
    first_error: Exception | None = None

    try:
        rendered = tts_engine.synthesize(
            text,
            str(output_path),
            language=language,
            google_api_key=google_api_key,
            emotion_config=emotion_config,
        )
        rendered_path = Path(rendered or output_path)
        if _tts_file_ready(rendered_path):
            return str(rendered_path)
        first_error = RuntimeError(f"TTS returned empty audio at {rendered_path}.")
    except Exception as exc:
        first_error = exc

    logger.warning("stream_tts_primary_failed_retrying_fresh language=%s error=%s", language, first_error)
    try:
        rendered = PiperTextToSpeech().synthesize(
            text,
            str(output_path),
            language=language,
            google_api_key=google_api_key,
            emotion_config=emotion_config,
        )
        rendered_path = Path(rendered or output_path)
        if _tts_file_ready(rendered_path):
            return str(rendered_path)
    except Exception as exc:
        raise RuntimeError(f"TTS failed after fresh retry: {exc}") from first_error

    raise RuntimeError("TTS returned empty audio after fresh retry.") from first_error


def _synthesize_live_tts_chunk(
    tts_engine,
    text: str,
    output_path: str | Path,
    language: str,
    google_api_key: str | None = None,
    emotion_config: dict | None = None,
) -> str:
    effective_emotion = resolve_tts_emotion_config(text, emotion_config)

    def _render(temp_path):
        return _synthesize_tts_resilient(
            tts_engine,
            text,
            temp_path,
            language=language,
            google_api_key=google_api_key,
            emotion_config=effective_emotion,
        )

    if emotion_config:
        return _render(output_path)

    payload = _cached_tts_payload_impl(text, language, "url", _render)
    return payload["audio_output_path"]


_TTS_PREWARM_PHRASES = {
    "en": "Okay.",
    "es": "Hola.",
    "ht": "Bonjou.",
    "fr": "Bonjour.",
    "de": "Hallo.",
    "it": "Ciao.",
    "pt": "Olá.",
    "nl": "Hallo.",
    "ru": "Привет.",
    "zh": "你好。",
    "ja": "こんにちは。",
    "ko": "안녕하세요.",
    "ar": "مرحبا.",
    "hi": "नमस्ते.",
}


async def _prewarm_target_language_tts(pipeline: AnaiTranslatorPipeline, language: str) -> None:
    """Prime Edge neural TTS so the first real translation sounds immediate."""
    normalized = _language_code(language)
    if not _should_use_backend_live_tts(normalized):
        return
    phrase = _TTS_PREWARM_PHRASES.get(normalized, "Okay.")
    try:
        await run_in_threadpool(
            lambda: _synthesize_live_tts_chunk(
                pipeline.tts,
                phrase,
                f"models/tts/prewarm-{uuid4()}.wav",
                language=normalized,
            )
        )
        logger.info("neural_tts_prewarm_complete language=%s", normalized)
    except Exception as exc:
        logger.debug("neural_tts_prewarm_failed language=%s error=%s", normalized, exc)


def _apply_ailang_enhancements(
    translated_text: str,
    source_text: str,
    source_lang: str,
    target_lang: str,
    speaker: str,
    memory=None,
    speaker_memory=None,
    tr_conf: float = 0.9,
    session_context: dict = None,
) -> str:
    """Run AILang enhancement agents on an already-translated string.

    Applies: confidence fallback, back-translation verify, dialect adapt,
    speaker style, glossary injection, and context memory — in a single call.
    Always returns a string; never raises.

    session_context supports:
        glossary         — list of {source, target, lang_pair, context} overrides
        target_dialect   — e.g. 'es-MX'
        quality_mode     — defaults to 'enhanced'
        speaker_registry — dict, persisted across turns (pass by reference)
        conversation_history — list of past turns
    """
    if not _AILANG_AVAILABLE or not translated_text or not _ailang_enhancement_provider_enabled():
        return translated_text
    try:
        ctx = dict(session_context or {})
        ctx["current_speaker"] = speaker
        ctx["source_lang"] = source_lang
        ctx["target_lang"] = target_lang
        ctx.setdefault("quality_mode", "enhanced")
        # Pull history from memory object if available
        if memory is not None and not ctx.get("conversation_history"):
            raw = memory.get_context()
            if isinstance(raw, list):
                ctx["conversation_history"] = raw
        # stt_confidence feeds the confidence_fallback agent
        ctx["stt_confidence"] = tr_conf
        result = _ailang_enhance_v2(
            text=source_text,
            source_lang=source_lang,
            target_lang=target_lang,
            context=ctx,
        )
        enhanced = result.get("translated_text") or translated_text
        if is_internal_translation_artifact(enhanced):
            logger.warning(
                "AILang enhancement returned internal artifact; keeping base translation source=%s target=%s artifact=%r",
                source_lang,
                target_lang,
                str(enhanced)[:120],
            )
            return translated_text
        return enhanced if enhanced else translated_text
    except Exception as exc:
        logger.debug("AILang enhancement skipped: %s", exc)
        return translated_text

# Pure helpers + pipeline-step plumbing live in a sibling module so this
# file can focus on the WebSocket handlers below.
from backend.streaming_helpers import (
    PipelineStepTimeout,
    audio_suffix_for_bytes,
    audio_suffix_for_mime,
    call_cip_brain,
    chunk_text_for_tts,
    extract_client_voice_active,
    folded_live_text,
    is_internal_translation_artifact,
    is_speakable_live_delta,
    live_translation_redundant,
    live_translation_delta,
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
        source_language = payload.get("source_language") or "en"
        target_language = payload.get("target_language") or "es"

        if not text.strip():
            await websocket.send_json({"type": "error", "message": "Text is required."})
            continue

        result = pipeline.translate_text(
            text=text,
            source_language=source_language,
            target_language=target_language,
            synthesize_audio=False,
        )
        # AILang enhancement for text translation
        enhanced_text = _apply_ailang_enhancements(
            result.translated_text, text, source_language, target_language,
            "speaker",
        )
        if enhanced_text and enhanced_text != result.translated_text:
            result.translated_text = enhanced_text
        await websocket.send_json({"type": "translation", **result.__dict__})


async def websocket_audio_translation(
    websocket: WebSocket,
    pipeline: AnaiTranslatorPipeline,
    vad: SileroVoiceActivityDetector,
    conversation_brain: ConversationBrain,
    memory: ConversationMemory | None = None,
    speaker_memory: SpeakerMemory | None = None,
    identity: str = "anonymous",
    global_latency_engine: LatencyEngine | None = None,
):
    await websocket.accept()
    observability.increment("websocket_connects_total")
    logger.info("websocket_audio_connected partial_tts_mode=%s", get_partial_tts_mode())
    await websocket.send_json({"type": "ready", "message": "Audio streaming connected."})
    asyncio.create_task(_prewarm_target_language_tts(pipeline, target_language))
    memory = memory or ConversationMemory()
    speaker_memory = speaker_memory or SpeakerMemory()

    # Initialize advanced optimization modules if available
    adaptive_vad = AdaptiveVAD() if _ADAPTIVE_VAD_AVAILABLE else None
    smart_buffer = SmartBuffer(max_size_mb=get_stream_buffer_max_mb()) if _SMART_BUFFER_AVAILABLE else None
    audio_enhancer = AudioEnhancer() if _AUDIO_ENHANCER_AVAILABLE else None

    source_language = "en"
    target_language = "es"
    speaker = "speaker"
    speaker_label = "Person 1"
    speaker_index = 1
    speaker_mode = "manual"
    speaker_detection = "manual"
    barrier_mode = False
    device_id = None
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
    partial_buffer = ""
    partial_tts_text = ""
    last_live_tts_source_text = ""
    last_live_tts_utterance_id = None
    last_sent_translation = ""
    last_active_speaker = None
    segment_generation = 0
    partial_task = None
    live_text_task = None
    live_text_pending = None
    live_text_revision = 0
    live_text_active_until = 0.0
    latency_engine = LatencyEngine()
    confidence_engine = ConfidenceEngine()
    pipeline_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=1)
    tts_active = False
    partial_tts_active = False
    last_partial_tts_at = 0.0
    recent_audio_tts_texts: list[str] = []
    phrase_accumulation_buffer = ""
    phrase_accumulation_start = 0.0   # when accumulation began (never reset mid-speech)
    try:
        PARTIAL_TTS_MIN_INTERVAL = max(0.1, float(os.getenv("PARTIAL_TTS_MIN_INTERVAL", "0.45")))
    except (TypeError, ValueError):
        PARTIAL_TTS_MIN_INTERVAL = 0.45
    try:
        PARTIAL_TTS_MIN_WORDS = max(1, int(os.getenv("PARTIAL_TTS_MIN_WORDS", "1")))
    except (TypeError, ValueError):
        PARTIAL_TTS_MIN_WORDS = 1
    try:
        PARTIAL_TTS_MAX_WORDS = max(1, int(os.getenv("PARTIAL_TTS_MAX_WORDS", "15")))
    except (TypeError, ValueError):
        PARTIAL_TTS_MAX_WORDS = 15
    turn_announced_for_segment = False
    active_speaker_notice_at = 0.0

    def remember_audio_tts(text: str) -> None:
        spoken = normalize_live_text(text)
        if not spoken:
            return
        recent_audio_tts_texts.append(spoken)
        del recent_audio_tts_texts[:-6]

    def recently_spoken_audio_tts(text: str) -> bool:
        spoken = normalize_live_text(text)
        if not spoken:
            return True
        return any(live_translation_redundant(previous, spoken) for previous in recent_audio_tts_texts)

    # Advanced optimization tracking
    environment = "quiet" if adaptive_vad else "unknown"
    cache_hits = 0
    cache_misses = 0

    # Sync cache stats from pipeline
    if pipeline.enable_predictive_cache and pipeline.predictive_cache:
        cache_stats = pipeline.get_cache_statistics()
        cache_hits = cache_stats.get("hits", 0)
        cache_misses = cache_stats.get("misses", 0)

    def reset_segment_state() -> None:
        nonlocal audio_chunks, recent_chunks, speech_started, silent_checks, last_speech_at, vad_error_count, partial_text, partial_buffer, partial_tts_text, last_live_tts_source_text, last_live_tts_utterance_id, last_partial_at, last_sent_translation, last_active_speaker, turn_announced_for_segment, segment_generation, phrase_accumulation_buffer, phrase_accumulation_start
        audio_chunks = bytearray()
        recent_chunks = []
        speech_started = False
        silent_checks = 0
        vad_error_count = 0
        last_speech_at = 0.0
        partial_text = ""
        partial_buffer = ""
        partial_tts_text = ""
        last_live_tts_source_text = ""
        last_live_tts_utterance_id = None
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
            "optimization": {
                "environment": environment,
                "cache_hits": cache_hits,
                "cache_misses": cache_misses,
            } if adaptive_vad or pipeline.predictive_cache else None,
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
            "barrier_mode": barrier_mode,
            "device_id": device_id,
            "session_id": session_id,
            "source_language": source_language,
            "target_language": target_language,
            "client_mime_type": client_mime_type,
            "audio_suffix": audio_suffix_for_bytes(audio_chunks, client_mime_type),
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
        partial_suffix = audio_suffix_for_bytes(partial_audio, client_mime_type)
        partial_source_language = source_language
        partial_target_language = target_language
        partial_speaker = speaker
        partial_speaker_label = speaker_label
        partial_barrier_mode = barrier_mode
        partial_generation = segment_generation
        partial_task = asyncio.create_task(run_partial_pipeline(
            partial_audio,
            partial_suffix,
            partial_source_language,
            partial_target_language,
            partial_speaker,
            partial_speaker_label,
            partial_barrier_mode,
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
        partial_barrier_mode: bool,
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
            if partial_suffix.lower() in {".webm", ".m4a", ".mp4", ".ogg", ".aac", ".mp3"}:
                transcoded_partial_path = await run_in_threadpool(transcode_to_wav, str(partial_audio_path))
                if transcoded_partial_path:
                    stt_input_path = transcoded_partial_path
            # Denoise/normalize partial audio if possible
            processed_partial_path, metrics = process_wav_for_stt(stt_input_path)
            stt_input_path = processed_partial_path or stt_input_path

            # Apply advanced audio enhancement if available
            if audio_enhancer and processed_partial_path:
                try:
                    import numpy as np
                    audio_data, sr = await run_in_threadpool(lambda: np.fromfile(processed_partial_path, dtype=np.int16))
                    audio_float = audio_data.astype(np.float32) / 32768.0
                    enhanced_audio = audio_enhancer.process(audio_float)
                    enhanced_int16 = (enhanced_audio * 32768.0).astype(np.int16)
                    enhanced_path = upload_dir / f"{uuid4()}-enhanced.wav"
                    await run_in_threadpool(lambda: enhanced_int16.tofile(str(enhanced_path)))
                    stt_input_path = str(enhanced_path)
                except Exception as exc:
                    logger.debug(f"Audio enhancement skipped: {exc}")
            try:
                stt_language_hint = None if partial_barrier_mode else partial_source_language
                next_partial_text = await run_pipeline_step("partial STT", pipeline.stt.transcribe, stt_input_path, stt_language_hint)
            except PipelineStepTimeout as exc:
                if partial_generation == segment_generation:
                    await websocket.send_json({"type": "stage", "stage": "partial_timeout", "message": str(exc)})
                return
            except (RuntimeError, ValueError, OSError):
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
        partial_route = resolve_barrier_route(
            partial_text,
            partial_source_language,
            partial_target_language,
            enabled=partial_barrier_mode,
        )
        effective_source_language = partial_route["source_language"]
        effective_target_language = partial_route["target_language"]
        effective_speaker = partial_route["speaker"] if partial_barrier_mode else partial_speaker
        effective_speaker_label = partial_route["speaker_label"] if partial_barrier_mode else partial_speaker_label
        await websocket.send_json({
            "type": "partial_transcription",
            "speaker": effective_speaker,
            "speaker_label": effective_speaker_label,
            "text": partial_text,
            "source_language": effective_source_language,
            "target_language": effective_target_language,
            "detected_language": partial_route["detected_language"],
            "detected_language_confidence": partial_route["detected_language_confidence"],
            "route_confidence": partial_route["route_confidence"],
            "barrier_mode": partial_barrier_mode,
        })
        # Adaptive thresholds: interruption and current system speed
        interrupted = last_active_speaker is not None and last_active_speaker != effective_speaker
        total_latency = latency_engine.total()
        fast_system = total_latency <= 0 or total_latency < 1.3
        min_words_base = get_partial_translation_min_words() if fast_system else max(3, get_partial_translation_min_words() + 1)
        min_words = (min_words_base - 1) if interrupted else min_words_base
        if bool(re.search(r"[.!?;:,]\s*$", partial_buffer.strip())) or len(partial_buffer.split()) >= min_words:
            try:
                partial_translation_raw = await run_pipeline_step("partial translation", pipeline.translator.translate, partial_buffer, effective_source_language, effective_target_language)
            except PipelineStepTimeout as exc:
                if partial_generation == segment_generation:
                    await websocket.send_json({"type": "stage", "stage": "partial_timeout", "message": str(exc)})
                return
            except (RuntimeError, ValueError, OSError):
                return
            if partial_generation != segment_generation:
                return
            # Lock or auto-detect language for this speaker once
            if not speaker_memory.get_language(effective_speaker):
                auto_lang = detect_language_heuristic(partial_text)
                speaker_memory.register(effective_speaker, language=effective_source_language or auto_lang)
            refined_partial = refine_translation(partial_buffer, partial_translation_raw, memory.get_context(), speaker_memory.get_context(effective_speaker))
            # AILang enhancement for partials (lightweight — context memory, glossary, dialect)
            stt_conf = estimate_stt_confidence(partial_text)
            tr_conf = estimate_translation_confidence(partial_buffer, refined_partial)
            refined_partial = await run_in_threadpool(
                _apply_ailang_enhancements,
                refined_partial, partial_buffer, effective_source_language, effective_target_language,
                effective_speaker, memory=memory, speaker_memory=speaker_memory, tr_conf=tr_conf,
            )
            # Confidence and ambiguity checks for partials
            conf_score = confidence_engine.evaluate(stt_conf, tr_conf)
            if conf_score < 0.4:
                await websocket.send_json({"type": "clarify", "message": clarification_for(partial_buffer, detect_ambiguities(partial_buffer)), "stage": "partial_low_confidence"})
            # Adaptive partial update suppression if under heavy load
            allow_partial_updates = latency_engine.total() <= 2.5
            if allow_partial_updates and refined_partial and refined_partial != last_sent_translation:
                last_sent_translation = refined_partial
                await websocket.send_json({
                    "type": "partial_translation",
                    "speaker": effective_speaker,
                    "speaker_label": effective_speaker_label,
                    "text": refined_partial,
                    "source_text": partial_buffer,
                    "source_language": effective_source_language,
                    "target_language": effective_target_language,
                    "detected_language": partial_route["detected_language"],
                    "detected_language_confidence": partial_route["detected_language_confidence"],
                    "route_confidence": partial_route["route_confidence"],
                    "barrier_mode": partial_barrier_mode,
                })
                await websocket.send_json({
                    "type": "live_translation",
                    "speaker": effective_speaker,
                    "speaker_label": effective_speaker_label,
                    "text": refined_partial,
                    "source_text": partial_buffer,
                    "source_language": effective_source_language,
                    "target_language": effective_target_language,
                    "detected_language": partial_route["detected_language"],
                    "detected_language_confidence": partial_route["detected_language_confidence"],
                    "route_confidence": partial_route["route_confidence"],
                    "barrier_mode": partial_barrier_mode,
                })
            live_tts_delta = live_translation_delta(partial_tts_text, refined_partial)
            tts_text_to_speak = live_tts_delta if is_speakable_live_delta(live_tts_delta) else (refined_partial if refined_partial != partial_tts_text else "")
            if get_partial_tts_mode() and is_speakable_live_delta(tts_text_to_speak):
                if recently_spoken_audio_tts(tts_text_to_speak):
                    return
                try:
                    partial_tts_path = await run_pipeline_step(
                        "partial TTS",
                        lambda: _synthesize_live_tts_chunk(
                            pipeline.tts,
                            tts_text_to_speak,
                            f"models/tts/{uuid4()}-partial.wav",
                            language=effective_target_language,
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
                            await websocket.send_json({
                                "type": "tts_start",
                                "speaker": effective_speaker,
                                "speaker_label": effective_speaker_label,
                                "chunks": 1,
                                "partial": True,
                                "source_language": effective_source_language,
                                "target_language": effective_target_language,
                                "barrier_mode": partial_barrier_mode,
                            })
                            await websocket.send_json({
                                "type": "tts_audio_chunk",
                                "speaker": effective_speaker,
                                "speaker_label": effective_speaker_label,
                                "index": 1,
                                "total": 1,
                                "text": tts_text_to_speak,
                                "live_translation_text": refined_partial,
                                "source_text": partial_buffer,
                                "source_language": effective_source_language,
                                "target_language": effective_target_language,
                                "audio_base64": base64.b64encode(partial_tts_audio).decode("ascii"),
                                "mime_type": "audio/wav",
                                "partial": True,
                                "barrier_mode": partial_barrier_mode,
                            })
                            remember_audio_tts(tts_text_to_speak)
                            await websocket.send_json({
                                "type": "tts_end",
                                "speaker": effective_speaker,
                                "speaker_label": effective_speaker_label,
                                "partial": True,
                                "source_language": effective_source_language,
                                "target_language": effective_target_language,
                                "barrier_mode": partial_barrier_mode,
                            })
                    finally:
                        partial_tts_active = False
                        _unlink_temp_tts_file(partial_tts_path)
            observability.record_event("near_zero_partial", identity=identity, speaker=effective_speaker, latency_seconds=time() - partial_started_at)

    async def schedule_live_text(payload: dict) -> None:
        nonlocal live_text_pending, live_text_task, live_text_revision, live_text_active_until, speech_started, last_speech_at, silent_checks, partial_text, partial_buffer
        live_text = normalize_live_text(payload.get("text", ""))
        if not live_text:
            return
        live_text_revision += 1
        live_text_active_until = time() + 1.6
        speech_started = True
        last_speech_at = time()
        silent_checks = 0
        partial_text = live_text
        partial_buffer = live_text
        live_barrier_mode = _truthy(payload.get("barrier_mode")) if "barrier_mode" in payload else barrier_mode
        base_source_language = payload.get("source_language") or source_language
        base_target_language = payload.get("target_language") or target_language
        live_route = resolve_barrier_route(
            live_text,
            base_source_language,
            base_target_language,
            enabled=live_barrier_mode,
        )
        live_source_language = live_route["source_language"]
        live_target_language = live_route["target_language"]
        live_speaker = live_route["speaker"] if live_barrier_mode else speaker
        live_speaker_label = live_route["speaker_label"] if live_barrier_mode else speaker_label
        await announce_active_speaker("browser_live_text", None)
        await websocket.send_json({
            "type": "partial_transcription",
            "speaker": live_speaker,
            "speaker_label": live_speaker_label,
            "text": live_text,
            "source_language": live_source_language,
            "target_language": live_target_language,
            "detected_language": live_route["detected_language"],
            "detected_language_confidence": live_route["detected_language_confidence"],
            "route_confidence": live_route["route_confidence"],
            "barrier_mode": live_barrier_mode,
            "source": "browser_live_text",
            "utterance_id": payload.get("utterance_id"),
            "final": bool(payload.get("final")),
        })
        live_text_pending = {
            "revision": live_text_revision,
            "text": live_text,
            "final": bool(payload.get("final")),
            "source_language": live_source_language,
            "target_language": live_target_language,
            "speaker": live_speaker,
            "speaker_label": live_speaker_label,
            "route": live_route,
            "barrier_mode": live_barrier_mode,
            "utterance_id": payload.get("utterance_id"),
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
        nonlocal last_sent_translation, partial_tts_text, last_live_tts_source_text, last_live_tts_utterance_id, tts_active, partial_tts_active, last_partial_tts_at, phrase_accumulation_buffer, phrase_accumulation_start
        text_value = payload["text"]
        payload_revision = payload["revision"]
        live_source_language = payload["source_language"]
        live_target_language = payload["target_language"]
        live_speaker = payload["speaker"]
        live_speaker_label = payload["speaker_label"]
        live_route = payload.get("route") or {}
        live_barrier_mode = bool(payload.get("barrier_mode"))
        try:
            raw_translation = await run_pipeline_step(
                "live text translation",
                pipeline.translator.translate,
                text_value,
                live_source_language,
                live_target_language,
            )
        except PipelineStepTimeout as exc:
            if payload_revision == live_text_revision:
                await websocket.send_json({"type": "stage", "stage": "live_text_timeout", "message": str(exc)})
            return
        except Exception as exc:
            logger.warning("live_text_translation_failed error=%s", exc)
            return

        if not speaker_memory.get_language(live_speaker):
            speaker_memory.register(live_speaker, language=live_source_language or detect_language_heuristic(text_value))
        refined = refine_translation(text_value, raw_translation, memory.get_context(), speaker_memory.get_context(live_speaker))
        if not refined:
            return
        refined = _apply_ailang_enhancements(
            refined, text_value, live_source_language, live_target_language,
            live_speaker, memory=memory, speaker_memory=speaker_memory,
        )

        live_utterance_id = payload.get("utterance_id")
        normalized_live_utterance_id = str(live_utterance_id) if live_utterance_id is not None else None
        previous_live_source = folded_live_text(last_live_tts_source_text)
        current_live_source = folded_live_text(text_value)
        utterance_changed = normalized_live_utterance_id is not None and last_live_tts_utterance_id is not None and normalized_live_utterance_id != last_live_tts_utterance_id
        source_changed = bool(previous_live_source and current_live_source and not current_live_source.startswith(previous_live_source))
        new_live_utterance = utterance_changed or source_changed

        if refined != last_sent_translation or new_live_utterance:
            last_sent_translation = refined
            await websocket.send_json({
                "type": "partial_translation",
                "speaker": live_speaker,
                "speaker_label": live_speaker_label,
                "text": refined,
                "source_text": text_value,
                "source_language": live_source_language,
                "target_language": live_target_language,
                "detected_language": live_route.get("detected_language"),
                "detected_language_confidence": live_route.get("detected_language_confidence"),
                "route_confidence": live_route.get("route_confidence"),
                "barrier_mode": live_barrier_mode,
                "utterance_id": live_utterance_id,
                "source": "browser_live_text",
                "final": payload["final"],
            })
            await websocket.send_json({
                "type": "live_translation",
                "speaker": live_speaker,
                "speaker_label": live_speaker_label,
                "text": refined,
                "source_text": text_value,
                "source_language": live_source_language,
                "target_language": live_target_language,
                "detected_language": live_route.get("detected_language"),
                "detected_language_confidence": live_route.get("detected_language_confidence"),
                "route_confidence": live_route.get("route_confidence"),
                "barrier_mode": live_barrier_mode,
                "utterance_id": live_utterance_id,
                "source": "browser_live_text",
            })

        if new_live_utterance:
            live_tts_delta = refined
            phrase_accumulation_buffer = ""
            phrase_accumulation_start = 0.0
            last_partial_tts_at = 0.0
        else:
            live_tts_delta = live_translation_delta(partial_tts_text, refined)
        # Only speak new words (real delta). Never fall back to full sentence —
        # that causes repeating from the start when translation rewrites itself.
        if not get_partial_tts_mode() or not is_speakable_live_delta(live_tts_delta):
            return
        if not _should_use_backend_live_tts(live_target_language):
            logger.info(
                "live_tts_browser_fallback target=%s text=%r",
                live_target_language,
                refined[:60],
            )
            return
        candidate = live_tts_delta

        # Accumulate into buffer — only start the clock on first text, never reset mid-speech
        now = time()
        if not phrase_accumulation_buffer:
            phrase_accumulation_start = now
        phrase_accumulation_buffer = candidate

        # Fire when: interval elapsed OR enough words accumulated.
        elapsed = now - last_partial_tts_at if last_partial_tts_at else None
        word_count = len(phrase_accumulation_buffer.split())
        time_accumulating = now - phrase_accumulation_start

        too_soon = elapsed is not None and elapsed < PARTIAL_TTS_MIN_INTERVAL
        too_short = word_count < PARTIAL_TTS_MIN_WORDS
        # Force fire if we've been accumulating > 2s regardless of word count
        force = bool(payload.get("final") and word_count >= 1) or (new_live_utterance and word_count >= 1) or (time_accumulating >= 1.5 and word_count >= 2)

        if too_soon and not force:
            return
        if too_short and not force:
            return

        words = phrase_accumulation_buffer.split()
        live_tts_to_speak = " ".join(words[:PARTIAL_TTS_MAX_WORDS])
        logger.info("live_tts_firing words=%d elapsed=%.1fs text=%r", word_count, elapsed or 0.0, live_tts_to_speak[:60])
        phrase_accumulation_buffer = ""
        phrase_accumulation_start = 0.0

        # TTS with circuit breaker and retry logic
        live_tts_path = None
        max_retries = 2
        for attempt in range(max_retries):
            try:
                live_tts_path = await tts_circuit_breaker.call(
                    run_pipeline_step,
                    "live text TTS",
                    lambda: _synthesize_live_tts_chunk(
                        pipeline.tts,
                        live_tts_to_speak,
                        f"models/tts/{uuid4()}-live-text.wav",
                        language=live_target_language,
                    ),
                )
                break  # Success - exit retry loop
            except Exception as exc:
                logger.warning("live_tts_failed attempt=%d/%d error=%s", attempt + 1, max_retries, exc)
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.1 * (2 ** attempt))  # Exponential backoff: 100ms, 200ms
                else:
                    logger.error("live_tts_failed_all_attempts error=%s", exc)
                    live_tts_path = None
        if not live_tts_path:
            return

        try:
            partial_tts_text = refined
            last_live_tts_source_text = text_value
            last_live_tts_utterance_id = normalized_live_utterance_id
            last_partial_tts_at = time()
            partial_tts_active = True
            audio_bytes = Path(live_tts_path).read_bytes()
            if len(audio_bytes) < 100:
                return
            await websocket.send_json({
                "type": "tts_start",
                "speaker": live_speaker,
                "speaker_label": live_speaker_label,
                "chunks": 1,
                "partial": True,
                "source_language": live_source_language,
                "target_language": live_target_language,
                "barrier_mode": live_barrier_mode,
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
                "source_text": text_value,
                "source_language": live_source_language,
                "target_language": live_target_language,
                "utterance_id": live_utterance_id,
                "detected_language": live_route.get("detected_language"),
                "detected_language_confidence": live_route.get("detected_language_confidence"),
                "route_confidence": live_route.get("route_confidence"),
                "barrier_mode": live_barrier_mode,
                "audio_base64": base64.b64encode(audio_bytes).decode("ascii"),
                "mime_type": "audio/wav",
                "partial": True,
                "source": "browser_live_text",
            })
            await websocket.send_json({
                "type": "tts_end",
                "speaker": live_speaker,
                "speaker_label": live_speaker_label,
                "partial": True,
                "source_language": live_source_language,
                "target_language": live_target_language,
                "barrier_mode": live_barrier_mode,
                "source": "browser_live_text",
            })
            await websocket.send_json({
                "type": "latency",
                "metric": "live_text_voice",
                "ms": round((time() - payload["started_at"]) * 1000),
            })
        finally:
            partial_tts_active = False
            _unlink_temp_tts_file(live_tts_path)

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
            segment_barrier_mode = bool(segment.get("barrier_mode"))
            segment_session_id = segment["session_id"]
            segment_source_language = segment["source_language"]
            segment_target_language = segment["target_language"]
            segment_mime_type = segment["client_mime_type"]
            segment_audio_suffix = audio_suffix_for_bytes(audio_bytes, segment.get("client_mime_type") or segment.get("mime_type"))
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

            # In Barrier Mode, STT should not be locked to the previous turn's language.
            active_source_language = segment_source_language
            active_target_language = segment_target_language
            if not segment_barrier_mode:
                speaker_memory.register(speaker, language=segment_source_language)
                active_source_language = speaker_memory.get_language(speaker) or segment_source_language
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
                "barrier_mode": segment_barrier_mode,
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
            if segment_audio_suffix.lower() in {".webm", ".m4a", ".mp4", ".ogg", ".aac", ".mp3"}:
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
                stt_language_hint = None if segment_barrier_mode else active_source_language
                source_text = await run_pipeline_step("STT", pipeline.stt.transcribe, stt_call_input, stt_language_hint)
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
            barrier_route = resolve_barrier_route(
                source_text,
                segment_source_language,
                segment_target_language,
                enabled=segment_barrier_mode,
            )
            if segment_barrier_mode:
                speaker = barrier_route["speaker"]
                speaker_label = barrier_route["speaker_label"]
                speaker_index = barrier_route["speaker_index"]
                speaker_detection = barrier_route["detection"]
                active_source_language = barrier_route["source_language"]
                active_target_language = barrier_route["target_language"]
                session_registry.bind(
                    segment_session_id,
                    speaker,
                    identity,
                    active_source_language,
                    active_target_language,
                    device_id=device_id,
                    speaker_label=speaker_label,
                    speaker_index=speaker_index,
                    detection=speaker_detection,
                )
                speaker_memory.register(speaker, language=active_source_language)
                await websocket.send_json({
                    "type": "speaker_detected",
                    "speaker": speaker,
                    "speaker_label": speaker_label,
                    "speaker_index": speaker_index,
                    "mode": segment_speaker_mode,
                    "detection": speaker_detection,
                    "confidence": barrier_route["route_confidence"],
                    "device_id": device_id,
                    "source_language": active_source_language,
                    "target_language": active_target_language,
                    "detected_language": barrier_route["detected_language"],
                    "detected_language_confidence": barrier_route["detected_language_confidence"],
                    "route_confidence": barrier_route["route_confidence"],
                    "route_reason": barrier_route["route_reason"],
                    "needs_confirmation": barrier_route["needs_confirmation"],
                    "listener_label": barrier_route["listener_label"],
                    "barrier_mode": segment_barrier_mode,
                })
            else:
                barrier_route = {
                    "detected_language": active_source_language,
                    "detected_language_confidence": 1.0,
                    "route_confidence": 1.0,
                    "needs_confirmation": False,
                    "listener_label": None,
                    "barrier_mode": False,
                }
            await websocket.send_json({
                "type": "final_transcription",
                "speaker": speaker,
                "speaker_label": speaker_label,
                "text": source_text,
                "source_language": active_source_language,
                "target_language": active_target_language,
                "detected_language": barrier_route["detected_language"],
                "detected_language_confidence": barrier_route["detected_language_confidence"],
                "route_confidence": barrier_route["route_confidence"],
                "needs_confirmation": barrier_route["needs_confirmation"],
                "listener_label": barrier_route["listener_label"],
                "barrier_mode": segment_barrier_mode,
            })
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
                pipeline.translator.translate,
                improved_text,
                active_source_language,
                active_target_language,
            )
            memory_context = memory.get_context()
            speaker_context = speaker_memory.get_context(speaker)
            translated_text = refine_translation(source_text, raw_translated_text, memory_context, speaker_context)
            stt_conf = estimate_stt_confidence(source_text)
            tr_conf = estimate_translation_confidence(source_text, translated_text)
            translated_text = await run_in_threadpool(
                _apply_ailang_enhancements,
                translated_text, source_text, active_source_language, active_target_language,
                speaker, memory, speaker_memory, tr_conf,
            )
            tr_conf = estimate_translation_confidence(source_text, translated_text)
            # CIP override and decision
            cip = None
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
            cip_clarify = should_block_translation_for_cip(cip, translated_text, tr_conf)
            cip_response_plan = cip.get("response_plan") if isinstance(cip, dict) and isinstance(cip.get("response_plan"), dict) else {}
            cip_turn_policy = cip_response_plan.get("turn_policy") if isinstance(cip_response_plan.get("turn_policy"), dict) else {}
            cip_client_hints = cip_response_plan.get("client_hints") if isinstance(cip_response_plan.get("client_hints"), dict) else {}
            if not cip_clarify and cip_client_hints.get("skip_tts"):
                cip_response_plan = dict(cip_response_plan)
                cip_turn_policy = dict(cip_turn_policy)
                cip_client_hints = dict(cip_client_hints)
                cip_client_hints["skip_tts"] = False
                cip_client_hints["tts_mode"] = "speak"
                cip_client_hints["ask_before_speaking"] = False
                cip_turn_policy["tts"] = "speak"
                cip_turn_policy["speak_to_listener"] = True
                cip_response_plan["client_hints"] = cip_client_hints
                cip_response_plan["turn_policy"] = cip_turn_policy
            translated_text = "" if cip_clarify else choose_translation(cip, translated_text)
            # Confidence and ambiguity checks for final
            tr_conf = estimate_translation_confidence(source_text, translated_text)
            cip_conf = get_cip_confidence(cip)
            conf_score = cip_conf if cip_conf is not None else confidence_engine.evaluate(stt_conf, tr_conf)
            if conf_score < 0.4 and not cip_clarify:
                await websocket.send_json({
                    "type": "clarify",
                    "message": clarification_for(source_text, detect_ambiguities(source_text)),
                    "stage": "final_low_confidence",
                    "speaker": speaker,
                    "speaker_label": speaker_label,
                    "source_language": active_source_language,
                    "target_language": active_target_language,
                    "detected_language": barrier_route["detected_language"],
                    "route_confidence": barrier_route["route_confidence"],
                    "barrier_mode": segment_barrier_mode,
                })
            translation_ms = round((time() - translation_started_at) * 1000)
            intent = semantic_context.get("last_intent") or semantic_context.get("intent") or "statement"
            urgency = "high" if semantic_context.get("conversation_mood") == "urgent" else None
            # Lifelike voice: one full neural pass per sentence (not choppy partial clips).
            tts_playback_text = translated_text
            if get_partial_tts_mode() and not get_natural_tts_mode():
                live_spoken_text = normalize_live_text(segment_partial_tts_text)
                if live_spoken_text:
                    live_tail = live_translation_delta(live_spoken_text, translated_text)
                    if is_speakable_live_delta(live_tail):
                        tts_playback_text = live_tail
                    elif folded_live_text(translated_text).startswith(folded_live_text(live_spoken_text)):
                        tts_playback_text = ""
            tts_pacing = build_tts_pacing(tts_playback_text or translated_text, intent, urgency)
            tts_emotion_config = emotion_config_from_style(tts_pacing.get("style"))
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
            if not cip_clarify:
                await websocket.send_json({
                    "type": "live_translation",
                    "speaker": speaker,
                    "speaker_label": speaker_label,
                    "text": translated_text,
                    "source_text": source_text,
                    "source_language": active_source_language,
                    "target_language": active_target_language,
                    "detected_language": barrier_route["detected_language"],
                    "detected_language_confidence": barrier_route["detected_language_confidence"],
                    "route_confidence": barrier_route["route_confidence"],
                    "needs_confirmation": barrier_route["needs_confirmation"],
                    "listener_label": barrier_route["listener_label"],
                    "barrier_mode": segment_barrier_mode,
                })
                await websocket.send_json({"type": "tts_style", "speaker": speaker, "speaker_label": speaker_label, **tts_pacing})
            observability.record_event("mobile_stream_checkpoint", identity=identity, speaker=speaker, checkpoint="translation_done", translated_text=translated_text)
            # If CIP requested clarification, inform client and skip TTS
            browser_voice_target = not _should_use_backend_live_tts(active_target_language)
            final_tts_text = tts_playback_text or translated_text
            skip_tts = (
                bool(cip_client_hints.get("skip_tts"))
                or browser_voice_target
                or not is_speakable_live_delta(final_tts_text)
            )
            if cip_clarify:
                msg = cip_decision.get("message") or "Can you rephrase that?"
                await websocket.send_json({
                    "type": "clarify",
                    "message": msg,
                    "stage": "cip_clarification",
                    "speaker": speaker,
                    "speaker_label": speaker_label,
                    "source_language": active_source_language,
                    "target_language": active_target_language,
                    "detected_language": barrier_route["detected_language"],
                    "route_confidence": barrier_route["route_confidence"],
                    "barrier_mode": segment_barrier_mode,
                })
                skip_tts = True
            if cip_clarify:
                skip_message = "Clarification requested. Skipping TTS."
            elif browser_voice_target:
                skip_message = "Browser voice handles this language."
            else:
                skip_message = "Live voice already streamed."
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
                if get_natural_tts_mode():
                    tts_chunks = [chunk for chunk in tts_chunks if is_speakable_live_delta(chunk)]
                else:
                    tts_chunks = [chunk for chunk in tts_chunks if not recently_spoken_audio_tts(chunk)]
                if not tts_chunks:
                    skip_tts = True
                    await websocket.send_json({
                        "type": "stage",
                        "stage": "tts_skipped",
                        "message": "Live voice already streamed.",
                    })
                else:
                    await websocket.send_json({
                        "type": "tts_start",
                        "speaker": speaker,
                        "speaker_label": speaker_label,
                        "chunks": len(tts_chunks),
                        "source_language": active_source_language,
                        "target_language": active_target_language,
                        "detected_language": barrier_route["detected_language"],
                        "detected_language_confidence": barrier_route["detected_language_confidence"],
                        "route_confidence": barrier_route["route_confidence"],
                        "needs_confirmation": barrier_route["needs_confirmation"],
                        "listener_label": barrier_route["listener_label"],
                        "barrier_mode": segment_barrier_mode,
                        "cip_turn_policy": cip_turn_policy,
                        "latency_budget_ms": cip_client_hints.get("latency_budget_ms"),
                    })

            tts_started_at = time()
            tts_active = True
            for index, chunk in enumerate(tts_chunks if not skip_tts else [], start=1):
                try:
                    chunk_output_path = await run_pipeline_step(
                        "TTS",
                        lambda c=chunk, idx=index: _synthesize_live_tts_chunk(
                            pipeline.tts,
                            c,
                            f"models/tts/{uuid4()}-{idx}.wav",
                            language=active_target_language,
                            emotion_config=tts_emotion_config,
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
                        "source_text": source_text,
                        "source_language": active_source_language,
                        "target_language": active_target_language,
                        "detected_language": barrier_route["detected_language"],
                        "detected_language_confidence": barrier_route["detected_language_confidence"],
                        "route_confidence": barrier_route["route_confidence"],
                        "needs_confirmation": barrier_route["needs_confirmation"],
                        "listener_label": barrier_route["listener_label"],
                        "barrier_mode": segment_barrier_mode,
                        "tts_style": tts_pacing["style"],
                        "emotion": tts_pacing["emotion"],
                        "intent": tts_pacing["intent"],
                        "urgency": tts_pacing["urgency"],
                        "audio_base64": base64.b64encode(tts_audio_bytes).decode("ascii"),
                        "mime_type": "audio/wav",
                    })
                    remember_audio_tts(chunk)
                except (RuntimeError, ValueError, OSError, base64.Error) as e:
                    stream_debug_log(f"TTS synthesis failed for chunk {index}: {e}")
                    observability.record_event("mobile_stream_error", identity=identity, speaker=speaker, error=str(e), chunk_index=index)
                    # Send error message to frontend instead of invalid audio
                    await websocket.send_json({
                        "type": "error",
                        "message": f"TTS synthesis failed for chunk {index}: {str(e)}"
                    })
                    break

            if not skip_tts:
                await websocket.send_json({
                    "type": "tts_end",
                    "speaker": speaker,
                    "speaker_label": speaker_label,
                    "source_language": active_source_language,
                    "target_language": active_target_language,
                    "barrier_mode": segment_barrier_mode,
                })
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
                "semantic_context": semantic_context,
                "cip_decision": cip_decision,
                "cip_analysis": cip.get("analysis") if isinstance(cip, dict) else None,
                "cip_confidence": cip.get("confidence") if isinstance(cip, dict) else None,
                "cip_provider": cip.get("provider") if isinstance(cip, dict) else None,
                "cip_response_plan": cip_response_plan if cip_response_plan else None,
                "cip_turn_policy": cip_turn_policy if cip_turn_policy else None,
                "cip_client_hints": cip_client_hints if cip_client_hints else None,
                "translated_by": cip.get("translation_source") if isinstance(cip, dict) and cip.get("translated") and cip.get("translation_source") else "UT",
                "clarify": cip_clarify or conf_score < 0.4,
                "session": shared_session,
                "source_language": active_source_language,
                "target_language": active_target_language,
                "detected_language": barrier_route["detected_language"],
                "detected_language_confidence": barrier_route["detected_language_confidence"],
                "route_confidence": barrier_route["route_confidence"],
                "needs_confirmation": barrier_route["needs_confirmation"],
                "listener_label": barrier_route["listener_label"],
                "barrier_mode": segment_barrier_mode,
                **result.__dict__,
            })
            observability.observe_latency("streaming_segment", time() - segment_started_at)
            observability.record_event("streaming_segment", identity=identity, speaker=speaker, latency_seconds=time() - segment_started_at)
            total_ms = round((time() - segment_started_at) * 1000)
            await websocket.send_json({"type": "latency", "metric": "backend_response", "ms": total_ms})
            # Update latency engine for adaptive decisions next turns
            latency_engine.update(stt=stt_ms / 1000.0, translate=translation_ms / 1000.0, tts=(0.0))
            # Feed global latency engine for /latency dashboard
            if global_latency_engine:
                run = global_latency_engine.begin_run(
                    f"ws-{identity}-{segment_generation}",
                    speaker=speaker, source_lang=source_language, target_lang=target_language,
                )
                global_latency_engine.record_stage("stt", stt_ms)
                global_latency_engine.record_stage("translation", translation_ms)
                global_latency_engine.record_stage("tts", total_ms - stt_ms - translation_ms)
                global_latency_engine.end_run()
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
            recent_audio_tts_texts.clear()
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
                if speech_started and audio_chunks and last_speech_at and time() - last_speech_at > get_vad_force_final_seconds():
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

                if message_type == "config":
                    next_source_language = _sanitize_language_code(
                        payload.get("source_language"), source_language,
                    )
                    next_target_language = _sanitize_language_code(
                        payload.get("target_language"), target_language,
                    )
                    if "barrier_mode" in payload:
                        barrier_mode = _truthy(payload.get("barrier_mode"))
                    changed_language = (
                        next_source_language != source_language
                        or next_target_language != target_language
                    )
                    source_language = next_source_language
                    target_language = next_target_language
                    speaker_mode = payload.get("speaker_mode") or speaker_mode
                    if payload.get("session_id"):
                        session_id = _sanitize_session_id(payload.get("session_id"), session_id)
                    if payload.get("device_id"):
                        device_id = payload.get("device_id")
                    requested_speaker_label = payload.get("speaker_name") or payload.get("speaker_label") or speaker_label
                    if payload.get("speaker") and payload.get("speaker") != "auto":
                        speaker = payload.get("speaker")
                        speaker_label = requested_speaker_label or speaker_label or f"Speaker {speaker}"
                    if changed_language:
                        last_sent_translation = ""
                        partial_tts_text = ""
                        last_live_tts_source_text = ""
                        last_live_tts_utterance_id = None
                        phrase_accumulation_buffer = ""
                        phrase_accumulation_start = 0.0
                        last_partial_tts_at = 0.0
                        asyncio.create_task(_prewarm_target_language_tts(pipeline, target_language))
                    await websocket.send_json({
                        "type": "config_ack",
                        "source_language": source_language,
                        "target_language": target_language,
                        "speaker_mode": speaker_mode,
                        "speaker": speaker,
                        "speaker_label": speaker_label,
                        "session_id": session_id,
                        "barrier_mode": barrier_mode,
                    })
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
                    previous_session_id = session_id
                    previous_speaker = speaker
                    previous_device_id = device_id
                    speaker_mode = payload.get("speaker_mode") or "manual"
                    barrier_mode = _truthy(payload.get("barrier_mode"))
                    session_id = payload.get("session_id") or "default"
                    source_language = payload.get("source_language") or "en"
                    target_language = payload.get("target_language") or "es"
                    device_id = payload.get("device_id")
                    requested_speaker_label = payload.get("speaker_name") or payload.get("speaker_label")
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
                    if previous_device_id and (
                        previous_session_id != session_id or previous_speaker != speaker or previous_device_id != device_id
                    ):
                        session_registry.disconnect(previous_session_id, previous_speaker, identity, previous_device_id)
                    if session_registry.active_stream_count(identity) > get_max_active_streams_per_user():
                        session_registry.disconnect(session_id, speaker, identity, device_id)
                        await websocket.send_json({"type": "error", "message": "Too many active streams for this user."})
                        continue
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
                        "barrier_mode": barrier_mode,
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
                        "barrier_mode": barrier_mode,
                        "message": "Receiving audio chunks with Silero VAD.",
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
                audio_suffix = audio_suffix_for_bytes(audio_chunks, client_mime_type)
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
    target_language = "es"
    speaker = "speaker"
    speaker_label = "Person 1"
    speaker_index = 1
    speaker_mode = "manual"
    speaker_detection = "manual"
    barrier_mode = False
    session_id = "default"
    device_id = None
    provider_ws = None
    provider_receiver_task = None
    provider_language = None
    send_lock = asyncio.Lock()

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

    async def emit_translated_final(source_text: str) -> None:
        source_text = normalize_live_text(source_text)
        if not source_text:
            return

        barrier_route = resolve_barrier_route(
            source_text,
            source_language,
            target_language,
            enabled=barrier_mode,
        )
        effective_source_language = barrier_route["source_language"]
        effective_target_language = barrier_route["target_language"]
        effective_speaker = barrier_route["speaker"] if barrier_mode else speaker
        effective_speaker_label = barrier_route["speaker_label"] if barrier_mode else speaker_label
        effective_speaker_index = barrier_route["speaker_index"] if barrier_mode else speaker_index
        effective_detection = barrier_route["detection"] if barrier_mode else speaker_detection

        await send_json({
            "type": "final_transcription",
            "speaker": effective_speaker,
            "speaker_label": effective_speaker_label,
            "text": source_text,
            "source_language": effective_source_language,
            "target_language": effective_target_language,
            "detected_language": barrier_route["detected_language"],
            "detected_language_confidence": barrier_route["detected_language_confidence"],
            "route_confidence": barrier_route["route_confidence"],
            "needs_confirmation": barrier_route["needs_confirmation"],
            "listener_label": barrier_route["listener_label"],
            "barrier_mode": barrier_mode,
        })
        semantic_context = conversation_brain.analyze_semantics(effective_speaker, source_text)
        await send_json({"type": "semantic_context", "speaker": effective_speaker, "speaker_label": effective_speaker_label, **semantic_context})
        await send_json({"type": "stage", "stage": "translation", "message": "Transcription ready. Translating..."})

        translation_started_at = time()
        improved_text = await run_pipeline_step(
            "context improvement",
            pipeline.context_layer.improve,
            source_text,
            effective_source_language,
            effective_target_language,
            None,
        )
        raw_translated_text = await run_pipeline_step(
            "translation",
            pipeline.translator.translate,
            improved_text,
            effective_source_language,
            effective_target_language,
        )
        memory_context = memory.get_context()
        speaker_context = speaker_memory.get_context(effective_speaker)
        translated_text = refine_translation(source_text, raw_translated_text, memory_context, speaker_context)
        stt_conf = estimate_stt_confidence(source_text)
        tr_conf = estimate_translation_confidence(source_text, translated_text)
        translated_text = await run_in_threadpool(
            _apply_ailang_enhancements,
            translated_text, source_text, effective_source_language, effective_target_language,
            effective_speaker, memory, speaker_memory, tr_conf,
        )
        tr_conf = estimate_translation_confidence(source_text, translated_text)
        cip = None
        try:
            cip = await call_cip_brain(
                source_text,
                effective_target_language,
                identity,
                fallback_translation=translated_text,
                source_language=effective_source_language,
                stt_confidence=stt_conf,
                translation_confidence=tr_conf,
                context=memory_context,
                speaker_context=speaker_context,
                semantic_context=semantic_context,
            )
        except (ConnectionError, TimeoutError, RuntimeError, ValueError):
            cip = None
        cip_decision = get_cip_decision(cip)
        cip_clarify = should_block_translation_for_cip(cip, translated_text, tr_conf)
        cip_response_plan = cip.get("response_plan") if isinstance(cip, dict) and isinstance(cip.get("response_plan"), dict) else {}
        cip_turn_policy = cip_response_plan.get("turn_policy") if isinstance(cip_response_plan.get("turn_policy"), dict) else {}
        cip_client_hints = cip_response_plan.get("client_hints") if isinstance(cip_response_plan.get("client_hints"), dict) else {}
        if not cip_clarify and cip_client_hints.get("skip_tts"):
            cip_response_plan = dict(cip_response_plan)
            cip_turn_policy = dict(cip_turn_policy)
            cip_client_hints = dict(cip_client_hints)
            cip_client_hints["skip_tts"] = False
            cip_client_hints["tts_mode"] = "speak"
            cip_client_hints["ask_before_speaking"] = False
            cip_turn_policy["tts"] = "speak"
            cip_turn_policy["speak_to_listener"] = True
            cip_response_plan["client_hints"] = cip_client_hints
            cip_response_plan["turn_policy"] = cip_turn_policy
        translated_text = "" if cip_clarify else choose_translation(cip, translated_text)
        tr_conf = estimate_translation_confidence(source_text, translated_text)
        cip_conf = get_cip_confidence(cip)
        conf_score = cip_conf if cip_conf is not None else ConfidenceEngine().evaluate(stt_conf, tr_conf)
        translation_ms = round((time() - translation_started_at) * 1000)
        await send_json({"type": "latency", "metric": "translation", "ms": translation_ms})
        if cip:
            await send_json({
                "type": "cip",
                "speaker": effective_speaker,
                "speaker_label": effective_speaker_label,
                "provider": cip.get("provider"),
                "confidence": cip.get("confidence"),
                "decision": cip_decision,
                "analysis": cip.get("analysis"),
                "response_plan": cip_response_plan,
                "turn_policy": cip_turn_policy,
                "client_hints": cip_client_hints,
                "translated_by": cip.get("translation_source"),
            })
        if cip_clarify:
            await send_json({
                "type": "clarify",
                "message": cip_decision.get("message") or "Can you rephrase that?",
                "stage": "cip_clarification",
                "speaker": effective_speaker,
                "speaker_label": effective_speaker_label,
                "source_language": effective_source_language,
                "target_language": effective_target_language,
                "detected_language": barrier_route["detected_language"],
                "route_confidence": barrier_route["route_confidence"],
                "barrier_mode": barrier_mode,
            })
        elif conf_score < 0.4:
            await send_json({
                "type": "clarify",
                "message": clarification_for(source_text, detect_ambiguities(source_text)),
                "stage": "final_low_confidence",
                "speaker": effective_speaker,
                "speaker_label": effective_speaker_label,
                "source_language": effective_source_language,
                "target_language": effective_target_language,
                "detected_language": barrier_route["detected_language"],
                "route_confidence": barrier_route["route_confidence"],
                "barrier_mode": barrier_mode,
            })
        else:
            await send_json({
                "type": "live_translation",
                "speaker": effective_speaker,
                "speaker_label": effective_speaker_label,
                "text": translated_text,
                "source_text": source_text,
                "source_language": effective_source_language,
                "target_language": effective_target_language,
                "detected_language": barrier_route["detected_language"],
                "detected_language_confidence": barrier_route["detected_language_confidence"],
                "route_confidence": barrier_route["route_confidence"],
                "needs_confirmation": barrier_route["needs_confirmation"],
                "listener_label": barrier_route["listener_label"],
                "barrier_mode": barrier_mode,
            })

        memory.add(effective_speaker, source_text, translated_text, {"cip": cip})
        speaker_memory.register(effective_speaker, language=effective_source_language)
        speaker_memory.add_message(effective_speaker, source_text)
        shared_session = session_registry.record_turn(
            session_id,
            identity,
            effective_speaker,
            source_text,
            translated_text,
            semantic_context,
            device_id=device_id,
            speaker_label=effective_speaker_label,
        )
        result = TranslationResult(
            source_text=source_text,
            improved_text=improved_text,
            translated_text=translated_text,
            audio_output_path=None,
        )
        await send_json({"type": "session_sync", "session": shared_session})
        await send_json({
            "type": "final",
            "speaker": effective_speaker,
            "speaker_label": effective_speaker_label,
            "speaker_index": effective_speaker_index,
            "device_id": device_id,
            "detection": effective_detection,
            "semantic_context": semantic_context,
            "cip_decision": cip_decision,
            "cip_analysis": cip.get("analysis") if isinstance(cip, dict) else None,
            "cip_confidence": cip.get("confidence") if isinstance(cip, dict) else None,
            "cip_provider": cip.get("provider") if isinstance(cip, dict) else None,
            "cip_response_plan": cip_response_plan if cip_response_plan else None,
            "cip_turn_policy": cip_turn_policy if cip_turn_policy else None,
            "cip_client_hints": cip_client_hints if cip_client_hints else None,
            "translated_by": cip.get("translation_source") if isinstance(cip, dict) and cip.get("translated") and cip.get("translation_source") else "UT",
            "clarify": cip_clarify or conf_score < 0.4,
            "session": shared_session,
            "source_language": effective_source_language,
            "target_language": effective_target_language,
            "detected_language": barrier_route["detected_language"],
            "detected_language_confidence": barrier_route["detected_language_confidence"],
            "route_confidence": barrier_route["route_confidence"],
            "needs_confirmation": barrier_route["needs_confirmation"],
            "listener_label": barrier_route["listener_label"],
            "barrier_mode": barrier_mode,
            **result.__dict__,
        })
        complete_decision = conversation_brain.end_turn(effective_speaker)
        await send_json({
            "type": "turn",
            "speaker": effective_speaker,
            "speaker_label": effective_speaker_label,
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
                partial_route = resolve_barrier_route(text, source_language, target_language, enabled=barrier_mode)
                partial_speaker = partial_route["speaker"] if barrier_mode else speaker
                partial_speaker_label = partial_route["speaker_label"] if barrier_mode else speaker_label
                await send_json({
                    "type": "partial_transcription",
                    "speaker": partial_speaker,
                    "speaker_label": partial_speaker_label,
                    "text": text,
                    "source_language": partial_route["source_language"],
                    "target_language": partial_route["target_language"],
                    "detected_language": partial_route["detected_language"],
                    "detected_language_confidence": partial_route["detected_language_confidence"],
                    "route_confidence": partial_route["route_confidence"],
                    "needs_confirmation": partial_route["needs_confirmation"],
                    "listener_label": partial_route["listener_label"],
                    "barrier_mode": barrier_mode,
                })
        elif event_type == "transcript.final":
            if text:
                await emit_translated_final(text)
        elif event_type == "session.flushed":
            await send_json({"type": "stage", "stage": "stt_provider_flushed", "message": "Streaming STT provider flushed."})
        elif event_type == "error":
            await send_json({"type": "error", "message": event.get("message") or "Streaming STT provider error.", "recoverable": True})

    async def provider_receive_loop(active_provider_ws) -> None:
        async for raw_message in active_provider_ws:
            await handle_provider_event(raw_message)

    async def ensure_provider_connected() -> None:
        nonlocal provider_ws, provider_receiver_task, provider_language
        provider_language_hint = None if barrier_mode else source_language
        provider_language_key = "auto" if barrier_mode else source_language
        if provider_ws is not None and provider_language == provider_language_key:
            return
        await close_provider()
        stt_bridge = pipeline.stt
        if not hasattr(stt_bridge, "is_streaming") or not stt_bridge.is_streaming:
            raise RuntimeError("STT provider is not configured for streaming mode.")
        client = stt_bridge.get_streaming_client()
        provider_url = client._stream_url(language=provider_language_hint)
        provider_ws = await websockets.connect(
            provider_url,
            max_size=8 * 1024 * 1024,
            close_timeout=client.connection_timeout,
            ping_timeout=client.connection_timeout,
            ping_interval=20,
        )
        provider_language = provider_language_key
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
                    previous_source_language = source_language
                    previous_barrier_mode = barrier_mode
                    source_language = _sanitize_language_code(
                        data.get("source_language"), source_language,
                    )
                    target_language = _sanitize_language_code(
                        data.get("target_language"), target_language,
                    )
                    if "barrier_mode" in data:
                        barrier_mode = _truthy(data.get("barrier_mode"))
                    speaker_mode = data.get("speaker_mode", speaker_mode)
                    session_id = _sanitize_session_id(data.get("session_id"), session_id)
                    device_id = data.get("device_id", device_id)
                    requested_speaker_label = data.get("speaker_name") or data.get("speaker_label")
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
                    if previous_source_language != source_language or previous_barrier_mode != barrier_mode:
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
                        "barrier_mode": barrier_mode,
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
                        "message": "Receiving audio chunks with Silero VAD.",
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
                audio_suffix = audio_suffix_for_bytes(audio_chunks, client_mime_type)
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
    target_language = "es"
    speaker = "speaker"
    speaker_label = "Person 1"
    speaker_index = 1
    speaker_mode = "manual"
    speaker_detection = "manual"
    barrier_mode = False
    session_id = "default"
    device_id = None
    provider_ws = None
    provider_receiver_task = None
    provider_language = None
    send_lock = asyncio.Lock()

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

    async def emit_translated_final(source_text: str) -> None:
        source_text = normalize_live_text(source_text)
        if not source_text:
            return

        barrier_route = resolve_barrier_route(
            source_text,
            source_language,
            target_language,
            enabled=barrier_mode,
        )
        effective_source_language = barrier_route["source_language"]
        effective_target_language = barrier_route["target_language"]
        effective_speaker = barrier_route["speaker"] if barrier_mode else speaker
        effective_speaker_label = barrier_route["speaker_label"] if barrier_mode else speaker_label
        effective_speaker_index = barrier_route["speaker_index"] if barrier_mode else speaker_index
        effective_detection = barrier_route["detection"] if barrier_mode else speaker_detection

        await send_json({
            "type": "final_transcription",
            "speaker": effective_speaker,
            "speaker_label": effective_speaker_label,
            "text": source_text,
            "source_language": effective_source_language,
            "target_language": effective_target_language,
            "detected_language": barrier_route["detected_language"],
            "detected_language_confidence": barrier_route["detected_language_confidence"],
            "route_confidence": barrier_route["route_confidence"],
            "needs_confirmation": barrier_route["needs_confirmation"],
            "listener_label": barrier_route["listener_label"],
            "barrier_mode": barrier_mode,
        })
        semantic_context = conversation_brain.analyze_semantics(effective_speaker, source_text)
        await send_json({"type": "semantic_context", "speaker": effective_speaker, "speaker_label": effective_speaker_label, **semantic_context})
        await send_json({"type": "stage", "stage": "translation", "message": "Transcription ready. Translating..."})

        translation_started_at = time()
        improved_text = await run_pipeline_step(
            "context improvement",
            pipeline.context_layer.improve,
            source_text,
            effective_source_language,
            effective_target_language,
            None,
        )
        raw_translated_text = await run_pipeline_step(
            "translation",
            pipeline.translator.translate,
            improved_text,
            effective_source_language,
            effective_target_language,
        )
        memory_context = memory.get_context()
        speaker_context = speaker_memory.get_context(effective_speaker)
        translated_text = refine_translation(source_text, raw_translated_text, memory_context, speaker_context)
        stt_conf = estimate_stt_confidence(source_text)
        tr_conf = estimate_translation_confidence(source_text, translated_text)
        translated_text = await run_in_threadpool(
            _apply_ailang_enhancements,
            translated_text, source_text, effective_source_language, effective_target_language,
            effective_speaker, memory, speaker_memory, tr_conf,
        )
        tr_conf = estimate_translation_confidence(source_text, translated_text)
        cip = None
        try:
            cip = await call_cip_brain(
                source_text,
                effective_target_language,
                identity,
                fallback_translation=translated_text,
                source_language=effective_source_language,
                stt_confidence=stt_conf,
                translation_confidence=tr_conf,
                context=memory_context,
                speaker_context=speaker_context,
                semantic_context=semantic_context,
            )
        except (ConnectionError, TimeoutError, RuntimeError, ValueError):
            cip = None
        cip_decision = get_cip_decision(cip)
        cip_clarify = should_block_translation_for_cip(cip, translated_text, tr_conf)
        cip_response_plan = cip.get("response_plan") if isinstance(cip, dict) and isinstance(cip.get("response_plan"), dict) else {}
        cip_turn_policy = cip_response_plan.get("turn_policy") if isinstance(cip_response_plan.get("turn_policy"), dict) else {}
        cip_client_hints = cip_response_plan.get("client_hints") if isinstance(cip_response_plan.get("client_hints"), dict) else {}
        if not cip_clarify and cip_client_hints.get("skip_tts"):
            cip_response_plan = dict(cip_response_plan)
            cip_turn_policy = dict(cip_turn_policy)
            cip_client_hints = dict(cip_client_hints)
            cip_client_hints["skip_tts"] = False
            cip_client_hints["tts_mode"] = "speak"
            cip_client_hints["ask_before_speaking"] = False
            cip_turn_policy["tts"] = "speak"
            cip_turn_policy["speak_to_listener"] = True
            cip_response_plan["client_hints"] = cip_client_hints
            cip_response_plan["turn_policy"] = cip_turn_policy
        translated_text = "" if cip_clarify else choose_translation(cip, translated_text)
        tr_conf = estimate_translation_confidence(source_text, translated_text)
        cip_conf = get_cip_confidence(cip)
        conf_score = cip_conf if cip_conf is not None else ConfidenceEngine().evaluate(stt_conf, tr_conf)
        translation_ms = round((time() - translation_started_at) * 1000)
        await send_json({"type": "latency", "metric": "translation", "ms": translation_ms})
        if cip:
            await send_json({
                "type": "cip",
                "speaker": effective_speaker,
                "speaker_label": effective_speaker_label,
                "provider": cip.get("provider"),
                "confidence": cip.get("confidence"),
                "decision": cip_decision,
                "analysis": cip.get("analysis"),
                "response_plan": cip_response_plan,
                "turn_policy": cip_turn_policy,
                "client_hints": cip_client_hints,
                "translated_by": cip.get("translation_source"),
            })
        if cip_clarify:
            await send_json({
                "type": "clarify",
                "message": cip_decision.get("message") or "Can you rephrase that?",
                "stage": "cip_clarification",
                "speaker": effective_speaker,
                "speaker_label": effective_speaker_label,
                "source_language": effective_source_language,
                "target_language": effective_target_language,
                "detected_language": barrier_route["detected_language"],
                "route_confidence": barrier_route["route_confidence"],
                "barrier_mode": barrier_mode,
            })
        elif conf_score < 0.4:
            await send_json({
                "type": "clarify",
                "message": clarification_for(source_text, detect_ambiguities(source_text)),
                "stage": "final_low_confidence",
                "speaker": effective_speaker,
                "speaker_label": effective_speaker_label,
                "source_language": effective_source_language,
                "target_language": effective_target_language,
                "detected_language": barrier_route["detected_language"],
                "route_confidence": barrier_route["route_confidence"],
                "barrier_mode": barrier_mode,
            })
        else:
            await send_json({
                "type": "live_translation",
                "speaker": effective_speaker,
                "speaker_label": effective_speaker_label,
                "text": translated_text,
                "source_text": source_text,
                "source_language": effective_source_language,
                "target_language": effective_target_language,
                "detected_language": barrier_route["detected_language"],
                "detected_language_confidence": barrier_route["detected_language_confidence"],
                "route_confidence": barrier_route["route_confidence"],
                "needs_confirmation": barrier_route["needs_confirmation"],
                "listener_label": barrier_route["listener_label"],
                "barrier_mode": barrier_mode,
            })

        memory.add(effective_speaker, source_text, translated_text, {"cip": cip})
        speaker_memory.register(effective_speaker, language=effective_source_language)
        speaker_memory.add_message(effective_speaker, source_text)
        shared_session = session_registry.record_turn(
            session_id,
            identity,
            effective_speaker,
            source_text,
            translated_text,
            semantic_context,
            device_id=device_id,
            speaker_label=effective_speaker_label,
        )
        result = TranslationResult(
            source_text=source_text,
            improved_text=improved_text,
            translated_text=translated_text,
            audio_output_path=None,
        )
        await send_json({"type": "session_sync", "session": shared_session})
        await send_json({
            "type": "final",
            "speaker": effective_speaker,
            "speaker_label": effective_speaker_label,
            "speaker_index": effective_speaker_index,
            "device_id": device_id,
            "detection": effective_detection,
            "semantic_context": semantic_context,
            "cip_decision": cip_decision,
            "cip_analysis": cip.get("analysis") if isinstance(cip, dict) else None,
            "cip_confidence": cip.get("confidence") if isinstance(cip, dict) else None,
            "cip_provider": cip.get("provider") if isinstance(cip, dict) else None,
            "cip_response_plan": cip_response_plan if cip_response_plan else None,
            "cip_turn_policy": cip_turn_policy if cip_turn_policy else None,
            "cip_client_hints": cip_client_hints if cip_client_hints else None,
            "translated_by": cip.get("translation_source") if isinstance(cip, dict) and cip.get("translated") and cip.get("translation_source") else "UT",
            "clarify": cip_clarify or conf_score < 0.4,
            "session": shared_session,
            "source_language": effective_source_language,
            "target_language": effective_target_language,
            "detected_language": barrier_route["detected_language"],
            "detected_language_confidence": barrier_route["detected_language_confidence"],
            "route_confidence": barrier_route["route_confidence"],
            "needs_confirmation": barrier_route["needs_confirmation"],
            "listener_label": barrier_route["listener_label"],
            "barrier_mode": barrier_mode,
            **result.__dict__,
        })
        complete_decision = conversation_brain.end_turn(effective_speaker)
        await send_json({
            "type": "turn",
            "speaker": effective_speaker,
            "speaker_label": effective_speaker_label,
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
                partial_route = resolve_barrier_route(text, source_language, target_language, enabled=barrier_mode)
                partial_speaker = partial_route["speaker"] if barrier_mode else speaker
                partial_speaker_label = partial_route["speaker_label"] if barrier_mode else speaker_label
                await send_json({
                    "type": "partial_transcription",
                    "speaker": partial_speaker,
                    "speaker_label": partial_speaker_label,
                    "text": text,
                    "source_language": partial_route["source_language"],
                    "target_language": partial_route["target_language"],
                    "detected_language": partial_route["detected_language"],
                    "detected_language_confidence": partial_route["detected_language_confidence"],
                    "route_confidence": partial_route["route_confidence"],
                    "needs_confirmation": partial_route["needs_confirmation"],
                    "listener_label": partial_route["listener_label"],
                    "barrier_mode": barrier_mode,
                })
        elif event_type == "transcript.final":
            if text:
                await emit_translated_final(text)
        elif event_type == "session.flushed":
            await send_json({"type": "stage", "stage": "stt_provider_flushed", "message": "Streaming STT provider flushed."})
        elif event_type == "error":
            await send_json({"type": "error", "message": event.get("message") or "Streaming STT provider error.", "recoverable": True})

    async def provider_receive_loop(active_provider_ws) -> None:
        async for raw_message in active_provider_ws:
            await handle_provider_event(raw_message)

    async def ensure_provider_connected() -> None:
        nonlocal provider_ws, provider_receiver_task, provider_language
        provider_language_hint = None if barrier_mode else source_language
        provider_language_key = "auto" if barrier_mode else source_language
        if provider_ws is not None and provider_language == provider_language_key:
            return
        await close_provider()
        stt_bridge = pipeline.stt
        if not hasattr(stt_bridge, "is_streaming") or not stt_bridge.is_streaming:
            raise RuntimeError("STT provider is not configured for streaming mode.")
        client = stt_bridge.get_streaming_client()
        provider_url = client._stream_url(language=provider_language_hint)
        provider_ws = await websockets.connect(
            provider_url,
            max_size=8 * 1024 * 1024,
            close_timeout=client.connection_timeout,
            ping_timeout=client.connection_timeout,
            ping_interval=20,
        )
        provider_language = provider_language_key
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
                    previous_source_language = source_language
                    previous_barrier_mode = barrier_mode
                    source_language = _sanitize_language_code(
                        data.get("source_language"), source_language,
                    )
                    target_language = _sanitize_language_code(
                        data.get("target_language"), target_language,
                    )
                    if "barrier_mode" in data:
                        barrier_mode = _truthy(data.get("barrier_mode"))
                    speaker_mode = data.get("speaker_mode", speaker_mode)
                    session_id = _sanitize_session_id(data.get("session_id"), session_id)
                    device_id = data.get("device_id", device_id)
                    requested_speaker_label = data.get("speaker_name") or data.get("speaker_label")
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
                    if previous_source_language != source_language or previous_barrier_mode != barrier_mode:
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
                        "barrier_mode": barrier_mode,
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
                        "barrier_mode": barrier_mode,
                        "message": "Receiving PCM16 audio chunks via streaming STT provider.",
                    })
                    await send_json({"type": "config_ack", "source_language": source_language, "target_language": target_language, "barrier_mode": barrier_mode})

                elif msg_type == "translate" and data.get("text"):
                    text = data["text"].strip()
                    if text:
                        text_route = resolve_barrier_route(text, source_language, target_language, enabled=barrier_mode)
                        text_source_language = text_route["source_language"]
                        text_target_language = text_route["target_language"]
                        text_speaker = text_route["speaker"] if barrier_mode else speaker
                        text_speaker_label = text_route["speaker_label"] if barrier_mode else speaker_label
                        result = await run_pipeline_step(
                            "text translation",
                            pipeline.translate_text,
                            text,
                            text_source_language,
                            text_target_language,
                        )
                        # AILang enhancement for streaming STT text translation
                        enhanced_text = _apply_ailang_enhancements(
                            result.translated_text, text, text_source_language, text_target_language,
                            text_speaker,
                        )
                        if enhanced_text and enhanced_text != result.translated_text:
                            result.translated_text = enhanced_text
                        await send_json({
                            "type": "translation",
                            "speaker": text_speaker,
                            "speaker_label": text_speaker_label,
                            "source_language": text_source_language,
                            "target_language": text_target_language,
                            "detected_language": text_route["detected_language"],
                            "detected_language_confidence": text_route["detected_language_confidence"],
                            "route_confidence": text_route["route_confidence"],
                            "needs_confirmation": text_route["needs_confirmation"],
                            "listener_label": text_route["listener_label"],
                            "barrier_mode": barrier_mode,
                            **result.__dict__,
                        })

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
