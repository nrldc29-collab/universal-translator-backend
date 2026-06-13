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

from backend.api_health import runtime_state, voice_warmup_blocks_ready
from backend.conversation import ConversationBrain, ConversationBrainRegistry
from backend.memory import ConversationMemory
from backend.speakers import SpeakerMemory, detect_language_heuristic, resolve_barrier_route
from backend.refine import refine_translation

# AILang enhancement â€” optional, degrades gracefully if ailang is not installed
try:
    from ailang_integration.runtime.backend_hook import enhance_translation_v2 as _ailang_enhance_v2
    _AILANG_AVAILABLE = True
except ImportError:
    _AILANG_AVAILABLE = False
from backend.latency import LatencyEngine
from backend.stream_session import StreamSessionState
from backend.audio import process_wav_for_stt, compute_rms
from backend.cip_bridge import choose_translation, get_cip_confidence, get_cip_decision, resolve_translation_text, should_block_translation_for_cip
from backend.confidence import (
    ConfidenceEngine,
    assess_translation_confidence,
    estimate_stt_confidence,
    estimate_translation_confidence,
    detect_ambiguities,
    clarification_for,
    ambiguity_score,
)
from backend.config import (
    LANGUAGES,
    get_cip_confidence_threshold,
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
from backend.tts_pacing import build_tts_pacing, build_tts_pacing_advanced, emotion_config_from_style, resolve_tts_emotion_config
from backend.tts_cache import cached_tts_payload as _cached_tts_payload_impl, is_valid_tts_wav
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


def _default_barrier_mode(source_language: str, target_language: str) -> bool:
    pair = {_language_code(source_language), _language_code(target_language)}
    return pair == {"en", "ht"}


def _sanitize_environment(environment: str | None, default: str = "quiet") -> str:
    from backend.glossary import map_environment_for_stt

    return map_environment_for_stt(environment or default)


def _stt_conversation_prompt(
    source_language: str | None,
    partial_text: str | None,
    memory,
    *,
    max_turns: int = 3,
) -> str | None:
    from speech.whisper_stt import build_conversation_prompt

    recent_turns: list[str] = []
    if memory is not None:
        try:
            ctx = memory.get_context() or []
        except Exception:
            ctx = []
        for item in ctx[-max_turns:]:
            if isinstance(item, dict):
                text = item.get("source_text") or item.get("text") or item.get("translated_text") or ""
            else:
                text = str(item or "")
            text = str(text).strip()
            if text:
                recent_turns.append(text)
    return build_conversation_prompt(source_language, live_text=partial_text, recent_turns=recent_turns)


def _should_use_backend_live_tts(language: str | None) -> bool:
    return _language_code(language) in BACKEND_LIVE_TTS_LANGS


def _ailang_enhancement_provider_enabled() -> bool:
    explicit = os.getenv("AILANG_ENHANCEMENTS_ENABLED")
    if explicit is not None:
        return explicit.strip().lower() in {"1", "true", "yes", "on"}

    llm_agents = os.getenv("USE_LLM_AGENTS")
    if llm_agents is not None and llm_agents.strip().lower() not in {"1", "true", "yes", "on"}:
        return False

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
    return is_valid_tts_wav(path)


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
    from backend.streaming_helpers import sanitize_text_for_tts

    text = sanitize_text_for_tts(text)
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

    emotion_fingerprint = ""
    if emotion_config:
        import hashlib
        import json

        emotion_fingerprint = hashlib.sha256(
            json.dumps(effective_emotion, sort_keys=True, default=str).encode("utf-8"),
        ).hexdigest()[:16]

    payload = _cached_tts_payload_impl(
        text, language, "url", _render, emotion_fingerprint=emotion_fingerprint,
    )
    return payload["audio_output_path"]


_TTS_PREWARM_PHRASES = {
    "en": "Okay.",
    "es": "Hola.",
    "ht": "Bonjou.",
    "fr": "Bonjour.",
    "de": "Hallo.",
    "it": "Ciao.",
    "pt": "OlÃ¡.",
    "nl": "Hallo.",
    "ru": "ÐŸÑ€Ð¸Ð²ÐµÑ‚.",
    "zh": "ä½ å¥½ã€‚",
    "ja": "ã“ã‚“ã«ã¡ã¯ã€‚",
    "ko": "ì•ˆë…•í•˜ì„¸ìš”.",
    "ar": "Ù…Ø±Ø­Ø¨Ø§.",
    "hi": "à¤¨à¤®à¤¸à¥à¤¤à¥‡.",
}


async def _prewarm_language_tts(
    pipeline: AnaiTranslatorPipeline,
    language: str,
    *,
    phrase: str | None = None,
) -> None:
    """Prime Edge neural TTS so the first real translation sounds immediate."""
    normalized = _language_code(language)
    if not _should_use_backend_live_tts(normalized):
        return
    warm_phrase = (phrase or _TTS_PREWARM_PHRASES.get(normalized, "Okay.")).strip()
    try:
        await run_in_threadpool(
            lambda: _synthesize_live_tts_chunk(
                pipeline.tts,
                warm_phrase,
                f"models/tts/prewarm-{uuid4()}.wav",
                language=normalized,
            )
        )
        logger.info("neural_tts_prewarm_complete language=%s", normalized)
    except Exception as exc:
        logger.debug("neural_tts_prewarm_failed language=%s error=%s", normalized, exc)


async def _prewarm_conversation_languages(
    pipeline: AnaiTranslatorPipeline,
    source_language: str,
    target_language: str,
) -> None:
    """Warm neural voices for both sides of a two-language conversation."""
    from backend.ht_high_stakes_glossary import EMERGENCY_TTS_PREWARM

    await asyncio.gather(
        _prewarm_language_tts(pipeline, source_language),
        _prewarm_language_tts(pipeline, target_language),
    )
    extra_tasks = []
    for lang in {_language_code(source_language), _language_code(target_language)}:
        for phrase in EMERGENCY_TTS_PREWARM.get(lang, [])[:4]:
            extra_tasks.append(_prewarm_language_tts(pipeline, lang, phrase=phrase))
    if extra_tasks:
        await asyncio.gather(*extra_tasks, return_exceptions=True)


async def _prewarm_target_language_tts(pipeline: AnaiTranslatorPipeline, language: str) -> None:
    await _prewarm_language_tts(pipeline, language)


async def _reject_unusable_translation(
    websocket: WebSocket,
    translated_text: str,
    *,
    speaker: str,
    speaker_label: str,
    source_language: str,
    target_language: str,
    stage: str = "translation_unavailable",
) -> bool:
    """Return True when a translation artifact must not be shown or spoken."""
    if not is_internal_translation_artifact(translated_text):
        return False
    await websocket.send_json({
        "type": "clarify",
        "message": "I could not translate that reliably yet. Please try again.",
        "stage": stage,
        "speaker": speaker,
        "speaker_label": speaker_label,
        "source_language": source_language,
        "target_language": target_language,
    })
    return True


def _certification_payload_fields(assessed: dict) -> dict:
    step = assessed.get("human_certification_step") or "none"
    if step == "none" and assessed.get("needs_native_certification"):
        step = "required"
    elif step == "none" and assessed.get("native_speaker_listen_recommended"):
        step = "advisory"
    return {
        "native_speaker_listen_recommended": bool(assessed.get("native_speaker_listen_recommended")),
        "needs_native_certification": bool(assessed.get("needs_native_certification")),
        "certification_message": assessed.get("certification_message") or "",
        "human_certification_step": step,
    }


def _assessed_with_communication_context(
    source_text: str,
    translated_text: str,
    analysis: dict | None,
    *,
    stt_confidence: float | None = None,
    acoustic_confidence: float | None = None,
    glossary_trusted: bool = False,
    glossary_coverage: float = 1.0,
    domains: dict | None = None,
    source_language: str | None = None,
    context_match: float | None = None,
):
    lang_info = (analysis or {}).get("language") or {}
    return assess_translation_confidence(
        source_text,
        translated_text,
        stt_confidence=stt_confidence,
        context_match=context_match if context_match is not None else (analysis or {}).get("context_match"),
        domains=domains if domains is not None else (analysis or {}).get("domains"),
        glossary_coverage=glossary_coverage,
        source_language=source_language or (analysis or {}).get("source_language"),
        register=(analysis or {}).get("register"),
        tone=(analysis or {}).get("tone"),
        emotion=(analysis or {}).get("emotion"),
        intent=(analysis or {}).get("intent"),
        acoustic_confidence=acoustic_confidence,
        code_switching=bool(lang_info.get("code_switching")),
        glossary_trusted=glossary_trusted,
    )


def _streaming_analysis_for_text(
    text: str,
    *,
    memory_context=None,
    speaker_context=None,
    semantic_context=None,
    source_language: str | None = None,
) -> dict:
    from backend.communication_brain import analyze_communication

    return analyze_communication(
        text,
        context=memory_context,
        speaker_context=speaker_context,
        semantic_context=semantic_context,
        source_language=source_language,
    )


def _should_apply_audio_enhancer(metrics: dict | None, *, force: bool = False) -> bool:
    """Skip redundant enhancer only when RNNoise already lifted a strong clip."""
    if force:
        return True
    if not isinstance(metrics, dict) or not metrics:
        return True
    if not metrics.get("denoised"):
        return True
    rms_before = float(metrics.get("rms_before") or 0.0)
    rms_after = float(metrics.get("rms_after") or 0.0)
    if rms_after < 0.035:
        return True
    if rms_after >= 0.03 and rms_after >= rms_before * 0.9:
        return False
    return True


async def _maybe_enhance_stt_wav(
    audio_enhancer,
    processed_path: str | None,
    metrics: dict | None,
    *,
    force: bool = False,
) -> str | None:
    if not audio_enhancer or not processed_path or not _should_apply_audio_enhancer(metrics, force=force):
        return None
    try:
        enhanced_path, _ = await run_in_threadpool(audio_enhancer.enhance_wav_file, processed_path)
        return enhanced_path
    except Exception as exc:
        logger.debug("Audio enhancement skipped: %s", exc)
        return None


def _ailang_session_context(session_id: str, analysis: dict | None = None) -> dict:
    ctx: dict = {"session_id": session_id}
    if not isinstance(analysis, dict):
        return ctx
    instructions = list(analysis.get("instructions") or [])
    if instructions:
        ctx["instructions"] = instructions
    domains = analysis.get("domains") or {}
    high_stakes = list(domains.get("high_stakes") or [])
    if high_stakes:
        ctx["domain"] = str(high_stakes[0])
    return ctx


def _translation_kwargs_from_analysis(analysis: dict) -> dict:
    domains = (analysis.get("domains") or {}) if isinstance(analysis, dict) else {}
    high_stakes = list(domains.get("high_stakes") or [])
    strict_medical = "medical" in high_stakes
    hints = list(analysis.get("instructions") or [])
    style_guide = analysis.get("style_guide")
    if style_guide:
        hints.append(str(style_guide))
    tone = str(analysis.get("tone") or "").strip().lower()
    intent = str(analysis.get("intent") or "").strip().lower()
    if tone and tone not in {"neutral", "normal", "statement"}:
        hints.append(f"Match a {tone} tone in the translation.")
    emotion = str(analysis.get("emotion") or "").strip().lower()
    register = str(analysis.get("register") or "").strip().lower()
    if register == "informal":
        hints.append("Preserve informal register, slang, and conversational phrasing without adding meaning.")
    if emotion in {"frustrated", "angry", "excited"} or tone == "emphatic":
        hints.append("Preserve emotional intensity without adding or removing meaning.")
    if intent == "question":
        hints.append("Preserve natural question form in the target language.")
    elif intent == "emotional_statement":
        hints.append("Preserve emotional intensity without adding or removing meaning.")
    for entity in (analysis.get("entities") or [])[:5]:
        value = entity.get("value") if isinstance(entity, dict) else str(entity or "").strip()
        if value:
            hints.append(f"Preserve the name or term '{value}' exactly.")
    memory_block = analysis.get("memory") or {}
    recent_topics = list(memory_block.get("recent_topics") or [])[:4]
    if recent_topics:
        hints.append(f"Conversation topics: {', '.join(recent_topics)}. Keep references consistent.")
    return {
        "strict_medical": strict_medical,
        "hints": hints or None,
        "quality": bool(high_stakes),
    }


def _streaming_translate_with_glossary(
    pipeline: AnaiTranslatorPipeline,
    text: str,
    source_language: str,
    target_language: str,
    session_key: str,
    *,
    strict_medical: bool = False,
    hints: list | None = None,
    quality: bool = False,
    allow_partial: bool = False,
) -> str:
    from backend.glossary import (
        check_translation_safety,
        finalize_translation,
        get_session_glossary,
        prepare_for_translation,
        try_direct_glossary_translation,
    )
    from translation.lightweight_translator import LightweightTranslator

    glossary = get_session_glossary(session_key)
    direct = try_direct_glossary_translation(text, glossary, source_language, target_language)
    if direct:
        safety = check_translation_safety(
            text, direct, source_lang=source_language, target_lang=target_language, strict_medical=strict_medical,
        )
        if safety["safe"]:
            return direct

    lightweight = LightweightTranslator()
    if allow_partial:
        phrase_meta = lightweight.translate_with_meta(
            text, source_language, target_language, quality=quality,
        )
    else:
        phrase_meta = {
            "text": lightweight.translate(text, source_language, target_language, quality=quality),
            "phrase_hit": bool(lightweight._lookup_phrase(text, source_language, target_language)),
            "partial_hit": False,
        }
    if phrase_meta.get("phrase_hit") and phrase_meta.get("text") and not str(phrase_meta["text"]).startswith("["):
        candidate = str(phrase_meta["text"]).strip()
        safety = check_translation_safety(
            text, candidate, source_lang=source_language, target_lang=target_language, strict_medical=strict_medical,
        )
        if safety["safe"]:
            return candidate

    prepared, meta = prepare_for_translation(text, strict_medical=strict_medical)
    translate_kwargs: dict = {}
    if hints:
        translate_kwargs["hints"] = hints
    if quality or strict_medical:
        translate_kwargs["quality"] = True
    try:
        import inspect

        allowed = set(inspect.signature(pipeline.translator.translate).parameters)
        translate_kwargs = {key: value for key, value in translate_kwargs.items() if key in allowed}
    except (TypeError, ValueError):
        translate_kwargs = {}
    translated = pipeline.translator.translate(
        prepared, source_language, target_language, **translate_kwargs,
    )
    final, _ = finalize_translation(
        text,
        translated,
        session_id=session_key,
        source_lang=source_language,
        target_lang=target_language,
        strict_medical=strict_medical,
        metadata=meta,
    )
    safety = check_translation_safety(
        text, final, source_lang=source_language, target_lang=target_language, strict_medical=strict_medical,
    )
    if safety.get("critical"):
        raise ValueError("translation_safety:" + ",".join(safety.get("issues") or []))
    return final


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
    """Post-process an existing translation with AILang agents (no re-translation)."""
    if not _AILANG_AVAILABLE or not translated_text or not _ailang_enhancement_provider_enabled():
        return translated_text
    try:
        from ailang_integration.runtime.backend_hook import (
            run_back_translation_verify,
            run_confidence_fallback,
            run_dialect_adapter,
            run_glossary_inject,
        )
        from backend.glossary import get_session_glossary

        ctx = dict(session_context or {})
        session_key = ctx.get("session_id") or "default"
        glossary = ctx.get("glossary") or get_session_glossary(session_key)
        domain = (ctx.get("domain") or "general")
        dialect = ctx.get("target_dialect") or ""
        instructions = list(ctx.get("instructions") or [])
        working = translated_text

        gloss_result = run_glossary_inject(
            source_text, working, source_lang, target_lang, glossary, domain,
        )
        if gloss_result.get("glossary_applied"):
            working = gloss_result.get("final_translation") or working

        dialect_result = run_dialect_adapter(
            source_text, working, source_lang, target_lang, dialect,
        )
        if dialect_result.get("adaptation_applied"):
            working = dialect_result.get("final_translation") or working

        if tr_conf < 0.55:
            conf_result = run_confidence_fallback(
                source_text, working, tr_conf, source_lang, target_lang, domain, instructions,
            )
            if conf_result.get("escalated"):
                working = conf_result.get("final_translation") or working

        back_result = run_back_translation_verify(
            source_text, working, source_lang, target_lang, domain,
        )
        if back_result.get("improved"):
            working = back_result.get("final_translation") or working

        if is_internal_translation_artifact(working):
            return translated_text
        return working if working else translated_text
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
    session_restore_payload,
    should_translate_partial,
    stream_debug_log,
)


async def _reject_audio_socket_if_warming(websocket: WebSocket) -> bool:
    if runtime_state.get("ready", True) and not voice_warmup_blocks_ready():
        return False
    await websocket.send_json({
        "type": "error",
        "message": "LIVE voice pipeline is warming up. Retry in a few seconds.",
        "warming": True,
    })
    await websocket.close(code=1013, reason="Pipeline warming")
    return True


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
        target_language = payload.get("target_language") or "ht"

        if not text.strip():
            await websocket.send_json({"type": "error", "message": "Text is required."})
            continue

        text_analysis = _streaming_analysis_for_text(text, source_language=source_language)
        result = pipeline.translate_text(
            text=text,
            source_language=source_language,
            target_language=target_language,
            synthesize_audio=False,
        )
        enhanced_text = _apply_ailang_enhancements(
            result.translated_text, text, source_language, target_language,
            "speaker",
            session_context=_ailang_session_context("text-ws", text_analysis),
        )
        if enhanced_text and enhanced_text != result.translated_text:
            result.translated_text = enhanced_text
        from backend.glossary import get_session_glossary, glossary_coverage_score

        text_ws_glossary_cov = glossary_coverage_score(
            text,
            result.translated_text,
            get_session_glossary(pipeline.session_id),
            source_language,
            target_language,
        )
        assessed = assess_translation_confidence(
            text,
            result.translated_text,
            stt_confidence=0.95,
            context_match=text_analysis.get("context_match") if isinstance(text_analysis, dict) else None,
            domains=text_analysis.get("domains") if isinstance(text_analysis, dict) else None,
            glossary_coverage=text_ws_glossary_cov,
        )
        await websocket.send_json({
            "type": "translation",
            **result.__dict__,
            "confidence": assessed.get("confidence"),
            "confidence_threshold": assessed.get("confidence_threshold"),
            "low_confidence": assessed.get("low_confidence"),
            "confidence_message": assessed.get("confidence_message") or "",
            "needs_confirmation": assessed.get("needs_confirmation"),
            "clarify": bool(assessed.get("needs_confirmation")),
            "clarify_message": (assessed.get("confidence_message") or "") if assessed.get("needs_confirmation") else "",
        })


async def websocket_audio_translation(
    websocket: WebSocket,
    pipeline: AnaiTranslatorPipeline,
    vad: SileroVoiceActivityDetector,
    conversation_brain: ConversationBrain | ConversationBrainRegistry,
    memory: ConversationMemory | None = None,
    speaker_memory: SpeakerMemory | None = None,
    identity: str = "anonymous",
    global_latency_engine: LatencyEngine | None = None,
):
    await websocket.accept()
    if await _reject_audio_socket_if_warming(websocket):
        return
    observability.increment("websocket_connects_total")
    logger.info("websocket_audio_connected partial_tts_mode=%s", get_partial_tts_mode())
    await websocket.send_json({"type": "ready", "message": "Audio streaming connected."})
    memory = memory or ConversationMemory()
    speaker_memory = speaker_memory or SpeakerMemory()

    # Initialize advanced optimization modules if available
    adaptive_vad = AdaptiveVAD() if _ADAPTIVE_VAD_AVAILABLE else None
    smart_buffer = SmartBuffer(max_size_mb=get_stream_buffer_max_mb()) if _SMART_BUFFER_AVAILABLE else None
    audio_enhancer = AudioEnhancer() if _AUDIO_ENHANCER_AVAILABLE else None

    source_language = "en"
    target_language = "ht"
    asyncio.create_task(_prewarm_conversation_languages(pipeline, source_language, target_language))
    speaker = "speaker"
    speaker_label = "Person 1"
    speaker_index = 1
    speaker_mode = "manual"
    speaker_detection = "manual"
    barrier_mode = _default_barrier_mode(source_language, target_language)
    device_id = None
    session_id = "default"

    def resolve_brain(active_session_id: str | None = None) -> ConversationBrain:
        if isinstance(conversation_brain, ConversationBrainRegistry):
            return conversation_brain.get(active_session_id or session_id)
        return conversation_brain

    audio_chunks = bytearray()
    recent_chunks = []
    speech_started = False
    finalizing = False
    silent_checks = 0
    vad_error_count = 0
    max_buffer_bytes = get_stream_buffer_max_mb() * 1024 * 1024
    last_chunk_meta = {}
    last_segment_audio_level = 0.0
    client_mime_type = "audio/webm"
    audio_suffix = ".webm"
    last_speech_at = 0.0
    last_partial_at = 0.0
    last_partial_degraded_at = 0.0
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
    pipeline_worker = None
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
        nonlocal audio_chunks, recent_chunks, speech_started, silent_checks, last_speech_at, vad_error_count, partial_text, partial_buffer, partial_tts_text, last_live_tts_source_text, last_live_tts_utterance_id, last_partial_at, last_sent_translation, last_active_speaker, turn_announced_for_segment, segment_generation, phrase_accumulation_buffer, phrase_accumulation_start, partial_task, last_segment_audio_level
        if partial_task is not None and not partial_task.done():
            partial_task.cancel()
        partial_task = None
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
        last_segment_audio_level = 0.0
        if smart_buffer is not None:
            smart_buffer.clear()

    async def announce_active_speaker(reason: str, audio_level: float | None = None) -> bool:
        nonlocal turn_announced_for_segment, active_speaker_notice_at, partial_tts_active
        if turn_announced_for_segment:
            return True
        decision = resolve_brain().request_turn(speaker)
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
        if decision.behavior == "interruption":
            resolve_brain().cancel_playback()
            partial_tts_active = False
        return decision.allowed

    async def enqueue_finalize(reason: str) -> None:
        nonlocal audio_chunks, recent_chunks, speech_started, silent_checks, last_speech_at, vad_error_count
        if pipeline_queue.full():
            for _ in range(8):
                await asyncio.sleep(0.12)
                if not pipeline_queue.full():
                    break
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
            "segment_audio_level": last_segment_audio_level,
            "metering_available": last_chunk_meta.get("metering_available"),
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
        partial_min_bytes = get_partial_stt_min_bytes()
        if latency_engine.total() > 0 and latency_engine.total() < 1.0:
            partial_min_bytes = max(600, partial_min_bytes - 400)
        if len(audio_chunks) < partial_min_bytes:
            return
        partial_interval_ms = get_partial_stt_interval_ms()
        total_latency = latency_engine.total()
        if total_latency > 0 and total_latency < 1.2:
            partial_interval_ms = max(25, partial_interval_ms - 35)
        elif total_latency > 2.0:
            partial_interval_ms = min(300, partial_interval_ms + 60)
        if (time() - last_partial_at) * 1000 < partial_interval_ms:
            return
        if partial_task is not None and not partial_task.done():
            partial_task.cancel()
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
        nonlocal partial_text, partial_buffer, partial_tts_text, last_sent_translation, last_active_speaker, tts_active, partial_tts_active, last_partial_degraded_at
        upload_dir = Path("models/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        partial_audio_path = upload_dir / f"{uuid4()}-partial{partial_suffix}"
        partial_audio_path.write_bytes(partial_audio)
        transcoded_partial_path = None
        processed_partial_path = None
        enhanced_partial_path = None
        partial_acoustic_conf = None
        next_partial_text = ""
        partial_proc_metrics = {}
        stt_input_path = str(partial_audio_path)
        try:
            if partial_suffix.lower() in {".webm", ".m4a", ".mp4", ".ogg", ".aac", ".mp3"}:
                transcoded_partial_path = await run_in_threadpool(transcode_to_wav, str(partial_audio_path))
                if transcoded_partial_path:
                    stt_input_path = transcoded_partial_path
            # Denoise/normalize partial audio if possible
            processed_partial_path, partial_proc_metrics = process_wav_for_stt(stt_input_path)
            stt_input_path = processed_partial_path or stt_input_path
            if str(stt_input_path).lower().endswith(".wav"):
                from backend.audio import trim_wav_tail

                trimmed_partial_path, trimmed = trim_wav_tail(stt_input_path, 4.0)
                if trimmed:
                    stt_input_path = trimmed_partial_path

            partial_force_enhance = False
            try:
                partial_rms = (partial_proc_metrics or {}).get("rms_after")
                partial_force_enhance = partial_rms is not None and float(partial_rms) < 0.02
            except (TypeError, ValueError):
                partial_force_enhance = False
            enhanced_partial_path = await _maybe_enhance_stt_wav(
                audio_enhancer,
                processed_partial_path,
                partial_proc_metrics,
                force=partial_force_enhance or environment in {"restaurant", "street", "crowded", "noisy"},
            )
            if enhanced_partial_path:
                stt_input_path = enhanced_partial_path
            partial_acoustic_conf = None
            try:
                stt_language_hint = None if partial_barrier_mode else partial_source_language
                from speech.whisper_stt import build_conversation_prompt

                partial_prompt = _stt_conversation_prompt(
                    partial_source_language,
                    partial_buffer or partial_text,
                    memory,
                ) or build_conversation_prompt(
                    partial_source_language,
                    live_text=partial_buffer or partial_text,
                )
                if hasattr(pipeline.stt, "transcribe_result"):
                    partial_stt_result = await stt_circuit_breaker.call(
                        run_pipeline_step,
                        "partial STT",
                        lambda: pipeline.stt.transcribe_result(
                            stt_input_path,
                            stt_language_hint,
                            condition_on_previous_text=bool(partial_buffer or partial_text),
                            initial_prompt=partial_prompt,
                            environment=environment,
                        ),
                    )
                    next_partial_text = partial_stt_result.text
                    partial_acoustic_conf = partial_stt_result.confidence
                else:
                    next_partial_text = await run_pipeline_step(
                        "partial STT", pipeline.stt.transcribe, stt_input_path, stt_language_hint,
                    )
            except PipelineStepTimeout as exc:
                if partial_generation == segment_generation:
                    await websocket.send_json({"type": "stage", "stage": "partial_timeout", "message": str(exc)})
                return
            except (RuntimeError, ValueError, OSError) as exc:
                if partial_generation == segment_generation and "Circuit breaker" in str(exc):
                    await websocket.send_json({
                        "type": "error",
                        "message": "Speech recognition paused briefly — keep speaking",
                        "recoverable": True,
                    })
                return
            try:
                rms_after = (partial_proc_metrics or {}).get("rms_after")
                from backend.streaming_helpers import _partial_length_units as _partial_weak_units

                if rms_after is not None and float(rms_after) < 0.02 and _partial_weak_units(next_partial_text) < 2:
                    await websocket.send_json({
                        "type": "stage",
                        "stage": "weak_audio",
                        "message": "Move closer to the microphone or reduce noise.",
                    })
            except (TypeError, ValueError):
                pass
        finally:
            partial_audio_path.unlink(missing_ok=True)
            if transcoded_partial_path:
                Path(transcoded_partial_path).unlink(missing_ok=True)
            if processed_partial_path and processed_partial_path != str(partial_audio_path):
                Path(processed_partial_path).unlink(missing_ok=True)
            if enhanced_partial_path and enhanced_partial_path != processed_partial_path:
                Path(enhanced_partial_path).unlink(missing_ok=True)
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
        from backend.streaming_helpers import _partial_length_units

        if bool(re.search(r"[.!?;:,。！？]\s*$", partial_buffer.strip())) or _partial_length_units(partial_buffer) >= min_words:
            partial_memory = memory.get_context()
            partial_speaker_ctx = speaker_memory.get_context(effective_speaker)
            partial_semantic = resolve_brain(session_id).semantic_snapshot()
            partial_analysis = _streaming_analysis_for_text(
                partial_buffer,
                memory_context=partial_memory,
                speaker_context=partial_speaker_ctx,
                semantic_context=partial_semantic,
                source_language=effective_source_language,
            )
            partial_tx_kwargs = _translation_kwargs_from_analysis(partial_analysis)
            partial_tone = partial_semantic.get("conversation_mood") or partial_analysis.get("tone")
            improved_partial = await run_in_threadpool(
                pipeline.context_layer.improve,
                partial_buffer,
                effective_source_language,
                effective_target_language,
                partial_tone,
            )
            try:
                partial_translation_raw = await translation_circuit_breaker.call(
                    run_pipeline_step,
                    "partial translation",
                    _streaming_translate_with_glossary,
                    pipeline,
                    improved_partial,
                    effective_source_language,
                    effective_target_language,
                    session_id,
                    allow_partial=True,
                    **partial_tx_kwargs,
                )
            except PipelineStepTimeout as exc:
                if partial_generation == segment_generation:
                    await websocket.send_json({"type": "stage", "stage": "partial_timeout", "message": str(exc)})
                return
            except (RuntimeError, ValueError, OSError) as exc:
                if partial_generation == segment_generation and "Circuit breaker" in str(exc):
                    await websocket.send_json({
                        "type": "error",
                        "message": "Translation paused briefly — keep speaking",
                        "recoverable": True,
                    })
                elif partial_generation == segment_generation and str(exc).startswith("translation_safety:"):
                    await websocket.send_json({
                        "type": "clarify",
                        "message": "Important detail may have changed — please confirm before acting.",
                        "stage": "translation_safety",
                        "needs_confirmation": True,
                        "human_certification_step": "required",
                    })
                return
            if partial_generation != segment_generation:
                return
            # Lock or auto-detect language for this speaker once
            if not speaker_memory.get_language(effective_speaker):
                auto_lang = detect_language_heuristic(partial_text)
                speaker_memory.register(effective_speaker, language=effective_source_language or auto_lang)
            refined_partial = refine_translation(partial_buffer, partial_translation_raw, memory.get_context(), speaker_memory.get_context(effective_speaker))
            # AILang enhancement for partials (lightweight â€” context memory, glossary, dialect)
            stt_conf = estimate_stt_confidence(partial_text, partial_acoustic_conf)
            try:
                rms_after = (partial_proc_metrics or {}).get("rms_after")
                if rms_after is not None and float(rms_after) < 0.02:
                    stt_conf = min(stt_conf, 0.38)
            except (TypeError, ValueError):
                pass
            tr_conf = estimate_translation_confidence(partial_buffer, refined_partial)
            refined_partial = await run_in_threadpool(
                _apply_ailang_enhancements,
                refined_partial, partial_buffer, effective_source_language, effective_target_language,
                effective_speaker, memory=memory, speaker_memory=speaker_memory, tr_conf=tr_conf,
                session_context=_ailang_session_context(session_id, partial_analysis),
            )
            tr_conf = estimate_translation_confidence(partial_buffer, refined_partial)
            # Confidence and ambiguity checks for partials
            from backend.glossary import get_session_glossary, glossary_blocks_clarification, glossary_coverage_score

            partial_ambiguity = ambiguity_score(partial_buffer, effective_source_language)
            partial_glossary = get_session_glossary(session_id)
            glossary_cov = glossary_coverage_score(
                partial_buffer, refined_partial, partial_glossary,
                effective_source_language, effective_target_language,
            )
            if glossary_cov < 1.0:
                tr_conf = max(0.0, tr_conf - (1.0 - glossary_cov) * 0.1)
            glossary_trusted = glossary_blocks_clarification(
                partial_buffer, refined_partial, partial_glossary,
                effective_source_language, effective_target_language,
            )
            partial_assessed = _assessed_with_communication_context(
                partial_buffer,
                refined_partial,
                partial_analysis,
                stt_confidence=stt_conf,
                acoustic_confidence=partial_acoustic_conf,
                glossary_trusted=glossary_trusted,
                glossary_coverage=glossary_cov,
                source_language=effective_source_language,
            )
            conf_score = partial_assessed.get("confidence", confidence_engine.evaluate(stt_conf, tr_conf, partial_ambiguity))
            clarify_threshold = partial_assessed.get("confidence_threshold") or get_cip_confidence_threshold()
            partial_low_confidence = (
                (
                    partial_assessed.get("low_confidence")
                    or conf_score < clarify_threshold
                    or partial_assessed.get("needs_native_certification")
                )
                and not glossary_trusted
            )
            if partial_low_confidence:
                from backend.communication_brain import clarification_message

                partial_clarify_msg = (
                    partial_assessed.get("confidence_message")
                    or clarification_message(
                        partial_buffer,
                        {**partial_analysis, "ambiguity": {"words": detect_ambiguities(partial_buffer)}},
                        "low_confidence",
                    )
                )
                await websocket.send_json({
                    "type": "clarify",
                    "message": partial_clarify_msg,
                    "stage": "partial_low_confidence",
                    "speaker": effective_speaker,
                    "speaker_label": effective_speaker_label,
                    "confidence": conf_score,
                    "confidence_threshold": partial_assessed.get("confidence_threshold"),
                    "low_confidence": True,
                })
            # Adaptive partial update suppression if under heavy load
            allow_partial_updates = latency_engine.total() <= 2.5
            if is_internal_translation_artifact(refined_partial):
                return
            if partial_low_confidence:
                return
            if not allow_partial_updates:
                if time() - last_partial_degraded_at > 5.0:
                    last_partial_degraded_at = time()
                    await websocket.send_json({
                        "type": "stage",
                        "stage": "partial_degraded",
                        "message": "Catching up — live preview paused briefly",
                    })
                return
            if refined_partial and refined_partial != last_sent_translation:
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
                    "confidence": conf_score,
                    "low_confidence": bool(partial_assessed.get("low_confidence")),
                    "confidence_message": partial_assessed.get("confidence_message") or "",
                    "confidence_threshold": partial_assessed.get("confidence_threshold"),
                    **_certification_payload_fields(partial_assessed),
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
            partial_tts_threshold = partial_assessed.get("confidence_threshold") or clarify_threshold
            if (
                get_partial_tts_mode()
                and is_speakable_live_delta(tts_text_to_speak)
                and conf_score >= partial_tts_threshold
                and not partial_assessed.get("needs_native_certification")
                and (partial_assessed.get("human_certification_step") or "none") != "required"
            ):
                if recently_spoken_audio_tts(tts_text_to_speak):
                    return
                partial_semantic = resolve_brain(session_id).semantic_snapshot()
                partial_intent = partial_semantic.get("last_intent") or "statement"
                partial_urgency = "high" if partial_semantic.get("conversation_mood") == "urgent" else None
                partial_pacing = build_tts_pacing_advanced(
                    tts_text_to_speak,
                    partial_intent,
                    partial_urgency,
                    {**partial_semantic, "target_language": effective_target_language},
                )
                partial_emotion_config = emotion_config_from_style(partial_pacing.get("style"))
                try:
                    partial_tts_path = await run_pipeline_step(
                        "partial TTS",
                        lambda: _synthesize_live_tts_chunk(
                            pipeline.tts,
                            tts_text_to_speak,
                            f"models/tts/{uuid4()}-partial.wav",
                            language=effective_target_language,
                            emotion_config=partial_emotion_config,
                        ),
                    )
                except Exception as exc:
                    logger.debug("partial_tts_failed error=%s", exc)
                    partial_tts_path = None
                if partial_tts_path:
                    try:
                        if partial_generation == segment_generation:
                            partial_brain = resolve_brain(session_id)
                            if (
                                partial_brain.active_speaker
                                and partial_brain.active_speaker != effective_speaker
                            ):
                                return
                            partial_playback = partial_brain.begin_playback(effective_speaker)
                            partial_tts_text = refined_partial
                            partial_tts_active = True
                            partial_tts_audio = Path(partial_tts_path).read_bytes()
                            await websocket.send_json({
                                "type": "turn",
                                "speaker": effective_speaker,
                                "speaker_label": effective_speaker_label,
                                "allowed": partial_playback.allowed,
                                "reason": partial_playback.reason,
                                "behavior": partial_playback.behavior,
                                "active_speaker": partial_playback.active_speaker,
                                "playback_owner": partial_playback.playback_owner,
                                "partial": True,
                            })
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
                            resolve_brain(session_id).cancel_playback(effective_speaker)
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
            "stt_confidence": payload.get("stt_confidence", payload.get("confidence")),
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
        live_utterance_id = payload.get("utterance_id")
        live_final_sent = False

        async def emit_live_text_final_turn(*, translated_text: str = "", skip_tts_end: bool = False) -> None:
            nonlocal live_final_sent
            if not payload.get("final") or live_final_sent:
                return
            live_final_sent = True
            if not skip_tts_end:
                await websocket.send_json({
                    "type": "tts_end",
                    "speaker": live_speaker,
                    "speaker_label": live_speaker_label,
                    "partial": False,
                    "source_language": live_source_language,
                    "target_language": live_target_language,
                    "barrier_mode": live_barrier_mode,
                    "source": "browser_live_text",
                })
            await websocket.send_json({
                "type": "final",
                "speaker": live_speaker,
                "speaker_label": live_speaker_label,
                "source_text": text_value,
                "translated_text": translated_text,
                "source_language": live_source_language,
                "target_language": live_target_language,
                "source": "browser_live_text",
                "utterance_id": live_utterance_id,
            })

        live_memory = memory.get_context()
        live_speaker_ctx = speaker_memory.get_context(live_speaker)
        live_semantic = resolve_brain(session_id).semantic_snapshot()
        live_analysis = _streaming_analysis_for_text(
            text_value,
            memory_context=live_memory,
            speaker_context=live_speaker_ctx,
            semantic_context=live_semantic,
            source_language=live_source_language,
        )
        live_tx_kwargs = _translation_kwargs_from_analysis(live_analysis)
        try:
            raw_translation = await translation_circuit_breaker.call(
                run_pipeline_step,
                "live text translation",
                _streaming_translate_with_glossary,
                pipeline,
                text_value,
                live_source_language,
                live_target_language,
                session_id,
                **live_tx_kwargs,
            )
        except PipelineStepTimeout as exc:
            if payload_revision == live_text_revision:
                await websocket.send_json({"type": "stage", "stage": "live_text_timeout", "message": str(exc)})
            await emit_live_text_final_turn()
            return
        except Exception as exc:
            logger.warning("live_text_translation_failed error=%s", exc)
            await emit_live_text_final_turn()
            return

        if not speaker_memory.get_language(live_speaker):
            speaker_memory.register(live_speaker, language=live_source_language or detect_language_heuristic(text_value))
        refined = refine_translation(text_value, raw_translation, memory.get_context(), speaker_memory.get_context(live_speaker))
        if not refined or is_internal_translation_artifact(refined):
            await emit_live_text_final_turn()
            return
        refined = _apply_ailang_enhancements(
            refined, text_value, live_source_language, live_target_language,
            live_speaker, memory=memory, speaker_memory=speaker_memory,
            session_context=_ailang_session_context(session_id, live_analysis),
        )

        normalized_live_utterance_id = str(live_utterance_id) if live_utterance_id is not None else None
        previous_live_source = folded_live_text(last_live_tts_source_text)
        current_live_source = folded_live_text(text_value)
        utterance_changed = normalized_live_utterance_id is not None and last_live_tts_utterance_id is not None and normalized_live_utterance_id != last_live_tts_utterance_id
        source_changed = bool(previous_live_source and current_live_source and not current_live_source.startswith(previous_live_source))
        new_live_utterance = utterance_changed or source_changed

        from backend.glossary import get_session_glossary, glossary_blocks_clarification, glossary_coverage_score

        live_glossary = get_session_glossary(session_id)
        live_glossary_cov = glossary_coverage_score(
            text_value, refined, live_glossary, live_source_language, live_target_language,
        )

        reported_stt_conf = payload.get("stt_confidence")
        try:
            reported_stt_conf = max(0.0, min(1.0, float(reported_stt_conf))) if reported_stt_conf is not None else None
        except (TypeError, ValueError):
            reported_stt_conf = None
        live_stt_conf = estimate_stt_confidence(text_value, reported_stt_conf)
        live_tr_conf = estimate_translation_confidence(text_value, refined)
        live_glossary_trusted = glossary_blocks_clarification(
            text_value, refined, live_glossary, live_source_language, live_target_language,
        )
        live_assessed = _assessed_with_communication_context(
            text_value,
            refined,
            live_analysis,
            stt_confidence=reported_stt_conf,
            glossary_trusted=live_glossary_trusted,
            glossary_coverage=live_glossary_cov,
            source_language=live_source_language,
        )
        live_conf_score = live_assessed.get("confidence", confidence_engine.evaluate(live_stt_conf, live_tr_conf))
        live_low_confidence = (
            bool(live_assessed.get("low_confidence") or live_assessed.get("needs_native_certification"))
            and not live_glossary_trusted
        )
        if live_low_confidence:
            from backend.communication_brain import clarification_message

            await websocket.send_json({
                "type": "clarify",
                "message": live_assessed.get("confidence_message") or clarification_message(
                    text_value,
                    {**live_analysis, "ambiguity": {"words": detect_ambiguities(text_value, live_source_language)}},
                    "low_confidence",
                ),
                "stage": "partial_low_confidence",
            })

        if live_low_confidence:
            await emit_live_text_final_turn()
            return

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
                "confidence": live_conf_score,
                "low_confidence": live_low_confidence,
                "confidence_message": live_assessed.get("confidence_message") or "",
                **_certification_payload_fields(live_assessed),
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
                "confidence": live_conf_score,
                "low_confidence": live_low_confidence,
                "confidence_threshold": live_assessed.get("confidence_threshold"),
            })

        if new_live_utterance:
            live_tts_delta = refined
            phrase_accumulation_buffer = ""
            phrase_accumulation_start = 0.0
            last_partial_tts_at = 0.0
        else:
            live_tts_delta = live_translation_delta(partial_tts_text, refined)

        partial_tts_enabled = get_partial_tts_mode()
        if not partial_tts_enabled and not payload.get("final"):
            return
        if not _should_use_backend_live_tts(live_target_language):
            logger.info(
                "live_tts_browser_fallback target=%s text=%r",
                live_target_language,
                refined[:60],
            )
            await emit_live_text_final_turn(translated_text=refined)
            return

        if partial_tts_enabled:
            if not is_speakable_live_delta(live_tts_delta):
                await emit_live_text_final_turn(translated_text=refined)
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
                await emit_live_text_final_turn(translated_text=refined)
                return
            if too_short and not force:
                await emit_live_text_final_turn(translated_text=refined)
                return

            words = phrase_accumulation_buffer.split()
            live_tts_to_speak = " ".join(words[:PARTIAL_TTS_MAX_WORDS])
        else:
            live_tts_to_speak = refined
            if not is_speakable_live_delta(live_tts_to_speak):
                await emit_live_text_final_turn(translated_text=refined)
                return
        fire_words = len(live_tts_to_speak.split())
        logger.info("live_tts_firing words=%d text=%r", fire_words, live_tts_to_speak[:60])
        phrase_accumulation_buffer = ""
        phrase_accumulation_start = 0.0

        live_tts_threshold = live_assessed.get("confidence_threshold") or get_cip_confidence_threshold()
        if live_conf_score < live_tts_threshold:
            await emit_live_text_final_turn(translated_text=refined)
            return

        live_intent = live_semantic.get("last_intent") or "statement"
        live_urgency = "high" if live_semantic.get("conversation_mood") == "urgent" else None
        live_pacing = build_tts_pacing_advanced(
            live_tts_to_speak,
            live_intent,
            live_urgency,
            {**live_semantic, "target_language": live_target_language},
        )
        live_emotion_config = emotion_config_from_style(live_pacing.get("style"))

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
                        emotion_config=live_emotion_config,
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
            await emit_live_text_final_turn(translated_text=refined)
            return

        try:
            partial_tts_text = refined
            last_live_tts_source_text = text_value
            last_live_tts_utterance_id = normalized_live_utterance_id
            last_partial_tts_at = time()
            partial_tts_active = True
            audio_bytes = Path(live_tts_path).read_bytes()
            if len(audio_bytes) < 100:
                await emit_live_text_final_turn(translated_text=refined)
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
                "partial": not bool(payload.get("final")),
                "source_language": live_source_language,
                "target_language": live_target_language,
                "barrier_mode": live_barrier_mode,
                "source": "browser_live_text",
            })
            await emit_live_text_final_turn(translated_text=refined, skip_tts_end=True)
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
            segment_partial_translation = segment.get("partial_translation", "") or ""
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

            segment_brain = resolve_brain(segment_session_id)
            decision = segment_brain.request_turn(speaker)
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
                await websocket.send_json({
                    "type": "stage",
                    "stage": "turn_held",
                    "message": decision.reason or "Waiting for other speaker",
                    "speaker": speaker,
                    "speaker_label": speaker_label,
                    "behavior": decision.behavior,
                })
                if decision.behavior == "hold":
                    for _ in range(40):
                        await asyncio.sleep(0.05)
                        if not segment_brain.playback_owner:
                            decision = segment_brain.request_turn(speaker)
                            if decision.allowed:
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
                                break
                if not decision.allowed:
                    await websocket.send_json({
                        "type": "error",
                        "message": decision.reason or "Waiting for other speaker — try again",
                        "recoverable": True,
                    })
                    held_retries = int(segment.get("_held_retry") or 0)
                    if held_retries < 2 and not pipeline_queue.full():
                        segment["_held_retry"] = held_retries + 1
                        finalizing = False
                        await pipeline_queue.put(segment)
                    return
            if decision.behavior == "interruption":
                segment_brain.cancel_playback()

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
            final_force_enhance = False
            try:
                final_rms = (proc_metrics or {}).get("rms_after")
                final_force_enhance = final_rms is not None and float(final_rms) < 0.02
            except (TypeError, ValueError):
                final_force_enhance = False
            enhanced_final_path = await _maybe_enhance_stt_wav(
                audio_enhancer,
                processed_path,
                proc_metrics,
                force=final_force_enhance or environment in {"restaurant", "street", "crowded", "noisy"},
            )
            if enhanced_final_path:
                stt_call_input = enhanced_final_path
            acoustic_confidence = None
            try:
                from speech.whisper_stt import build_conversation_prompt

                stt_language_hint = None if segment_barrier_mode else active_source_language
                final_stt_prompt = _stt_conversation_prompt(
                    active_source_language,
                    segment_partial_text,
                    memory,
                ) or build_conversation_prompt(
                    active_source_language,
                    live_text=segment_partial_text,
                )
                if hasattr(pipeline.stt, "transcribe_result"):
                    stt_result = await stt_circuit_breaker.call(
                        run_pipeline_step,
                        "STT",
                        lambda: pipeline.stt.transcribe_result(
                            stt_call_input,
                            stt_language_hint,
                            condition_on_previous_text=True,
                            initial_prompt=final_stt_prompt,
                            environment=environment,
                        ),
                    )
                    source_text = stt_result.text
                    acoustic_confidence = stt_result.confidence
                else:
                    source_text = await run_pipeline_step("STT", pipeline.stt.transcribe, stt_call_input, stt_language_hint)
            except (RuntimeError, ValueError, OSError) as stt_exc:
                message = str(stt_exc)
                if "Circuit breaker" in message:
                    message = "Speech recognition paused briefly — keep speaking"
                elif "Invalid data found" in message or "1094995529" in message:
                    message = "Could not decode that audio clip. Try speaking again - hold the button a moment longer."
                await websocket.send_json({"type": "error", "message": message, "recoverable": True})
                observability.record_event("stt_failed", identity=identity, speaker=speaker, error=str(stt_exc), mime_type=segment_mime_type)
                return
            finally:
                if transcoded_path:
                    Path(transcoded_path).unlink(missing_ok=True)
                if processed_path and processed_path != str(stt_input_path):
                    Path(processed_path).unlink(missing_ok=True)
                if enhanced_final_path and enhanced_final_path != processed_path:
                    Path(enhanced_final_path).unlink(missing_ok=True)
            stt_ms = round((time() - stt_started_at) * 1000)
            if not source_text.strip() and segment_partial_text.strip():
                source_text = segment_partial_text
            stream_debug_log("STT:", stt_ms, "ms", source_text)
            await websocket.send_json({"type": "latency", "metric": "stt", "ms": stt_ms})
            observability.record_event("mobile_stream_checkpoint", identity=identity, speaker=speaker, checkpoint="stt_done", source_text=source_text)
            # Weak audio guidance (distance-aware)
            try:
                rms_after = (proc_metrics or {}).get("rms_after")
                from backend.streaming_helpers import _partial_length_units as _weak_audio_units

                if (rms_after is not None) and rms_after < 0.02 and _weak_audio_units(source_text) < 2:
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
            semantic_context = segment_brain.analyze_semantics(speaker, source_text)
            await websocket.send_json({"type": "semantic_context", "speaker": speaker, "speaker_label": speaker_label, **semantic_context})
            await websocket.send_json({"type": "stage", "stage": "translation", "message": "Transcription ready. Translating..."})

            translation_started_at = time()
            memory_context = memory.get_context()
            speaker_context = speaker_memory.get_context(speaker)
            pre_analysis = _streaming_analysis_for_text(
                source_text,
                memory_context=memory_context,
                speaker_context=speaker_context,
                semantic_context=semantic_context,
                source_language=active_source_language,
            )
            tx_kwargs = _translation_kwargs_from_analysis(pre_analysis)
            conversation_tone = semantic_context.get("conversation_mood") or pre_analysis.get("tone")
            ref_source_text = source_text
            partial_folded = folded_live_text(segment_partial_text)
            source_folded = folded_live_text(source_text)
            partial_matches = (
                bool(segment_partial_translation.strip())
                and partial_folded
                and (
                    source_folded == partial_folded
                    or source_folded.startswith(partial_folded)
                    or partial_folded.startswith(source_folded)
                )
            )
            from backend.streaming_helpers import _partial_length_units as _segment_length_units

            reuse_partial_translation = (
                partial_matches
                and _segment_length_units(source_text) >= 2
                and estimate_stt_confidence(source_text, acoustic_confidence) >= 0.45
            )
            if reuse_partial_translation:
                improved_text = ref_source_text
                translated_text = refine_translation(
                    source_text, segment_partial_translation, memory_context, speaker_context,
                )
            else:
                improved_text = await run_pipeline_step(
                    "context improvement",
                    pipeline.context_layer.improve,
                    ref_source_text,
                    active_source_language,
                    active_target_language,
                    conversation_tone,
                )
                try:
                    raw_translated_text = await translation_circuit_breaker.call(
                        run_pipeline_step,
                        "translation",
                        _streaming_translate_with_glossary,
                        pipeline,
                        improved_text,
                        active_source_language,
                        active_target_language,
                        segment_session_id,
                        **tx_kwargs,
                    )
                except (RuntimeError, ValueError, OSError) as exc:
                    message = (
                        "Translation paused briefly — keep speaking"
                        if "Circuit breaker" in str(exc)
                        else str(exc)
                    )
                    await websocket.send_json({"type": "error", "message": message, "recoverable": True})
                    return
                translated_text = refine_translation(source_text, raw_translated_text, memory_context, speaker_context)
            if await _reject_unusable_translation(
                websocket,
                translated_text,
                speaker=speaker,
                speaker_label=speaker_label,
                source_language=active_source_language,
                target_language=active_target_language,
            ):
                return
            segment_audio_level = float(segment.get("segment_audio_level") or 0.0)
            if acoustic_confidence is not None:
                stt_conf = estimate_stt_confidence(source_text, acoustic_confidence)
            elif segment_audio_level > 0:
                energy_conf = min(0.88, max(0.32, 0.32 + segment_audio_level * 1.6))
                stt_conf = estimate_stt_confidence(source_text, acoustic_confidence=energy_conf)
            else:
                stt_conf = estimate_stt_confidence(source_text)
            try:
                if segment.get("metering_available") is False:
                    stt_conf = min(stt_conf, 0.44)
                rms_after = (proc_metrics or {}).get("rms_after")
                if rms_after is not None and float(rms_after) < 0.02:
                    stt_conf = min(stt_conf, 0.38)
                elif segment_audio_level > 0 and segment_audio_level < 0.04:
                    stt_conf = min(stt_conf, 0.42)
            except (TypeError, ValueError):
                pass
            tr_conf = estimate_translation_confidence(source_text, translated_text)
            translated_text = await run_in_threadpool(
                _apply_ailang_enhancements,
                translated_text, source_text, active_source_language, active_target_language,
                speaker, memory, speaker_memory, tr_conf,
                session_context=_ailang_session_context(segment_session_id, pre_analysis),
            )
            tr_conf = estimate_translation_confidence(source_text, translated_text)
            # CIP override and decision
            cip = None
            try:
                cip_context = {"session_id": segment_session_id}
                if isinstance(memory_context, list):
                    cip_context["history"] = memory_context
                elif isinstance(memory_context, dict):
                    cip_context.update(memory_context)
                cip = await call_cip_brain(
                    source_text,
                    active_target_language,
                    segment_session_id,
                    fallback_translation=translated_text,
                    source_language=active_source_language,
                    stt_confidence=stt_conf,
                    translation_confidence=tr_conf,
                    context=cip_context,
                    speaker_context=speaker_context,
                    semantic_context=semantic_context,
                )
            except (RuntimeError, ValueError, ConnectionError):
                cip = None
            cip_decision = get_cip_decision(cip)
            cip_clarify = should_block_translation_for_cip(
                cip,
                translated_text,
                tr_conf,
                source_text=source_text,
                source_language=active_source_language,
                target_language=active_target_language,
                session_id=segment_session_id,
            )
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
            translated_text = resolve_translation_text(cip_clarify, cip, translated_text) if cip_clarify else choose_translation(cip, translated_text)
            # Confidence and ambiguity checks for final
            tr_conf = estimate_translation_confidence(source_text, translated_text)
            cip_conf = get_cip_confidence(cip)
            final_ambiguity = ambiguity_score(source_text)
            from backend.glossary import (
                get_session_glossary,
                glossary_blocks_clarification,
                glossary_coverage_score,
            )

            final_glossary = get_session_glossary(segment_session_id)
            final_glossary_cov = glossary_coverage_score(
                source_text,
                translated_text,
                final_glossary,
                active_source_language,
                active_target_language,
            )
            glossary_trusted = glossary_blocks_clarification(
                source_text,
                translated_text,
                final_glossary,
                active_source_language,
                active_target_language,
            )
            cip_domains = {}
            if isinstance(cip, dict) and isinstance(cip.get("analysis"), dict):
                cip_domains = cip["analysis"].get("domains") or {}
            assessed = _assessed_with_communication_context(
                source_text,
                translated_text,
                pre_analysis,
                stt_confidence=stt_conf,
                acoustic_confidence=acoustic_confidence,
                glossary_trusted=glossary_trusted,
                glossary_coverage=final_glossary_cov,
                domains=cip_domains if cip_domains else None,
                source_language=active_source_language,
            )
            conf_score = cip_conf if cip_conf is not None else assessed.get("confidence", confidence_engine.evaluate(stt_conf, tr_conf, final_ambiguity, pre_analysis.get("context_match") or 0.6))
            low_confidence_threshold = assessed.get("confidence_threshold") or get_cip_confidence_threshold()
            low_confidence_warn = (
                (
                    assessed.get("low_confidence")
                    or conf_score < low_confidence_threshold
                    or assessed.get("needs_native_certification")
                )
                and not cip_clarify
                and not glossary_trusted
            )
            from backend.glossary import check_translation_safety

            safety_check = check_translation_safety(
                source_text,
                translated_text,
                source_lang=active_source_language,
                target_lang=active_target_language,
                strict_medical=bool(tx_kwargs.get("strict_medical")),
            )
            tts_safety_block = bool(safety_check.get("block_tts"))
            final_clarify_message = assessed.get("confidence_message") or clarification_for(
                source_text, detect_ambiguities(source_text),
            )
            if cip_clarify and isinstance(cip_decision, dict) and cip_decision.get("message"):
                final_clarify_message = cip_decision.get("message")
            if low_confidence_warn:
                await websocket.send_json({
                    "type": "clarify",
                    "message": final_clarify_message,
                    "stage": "final_low_confidence",
                    "speaker": speaker,
                    "speaker_label": speaker_label,
                    "source_language": active_source_language,
                    "target_language": active_target_language,
                    "detected_language": barrier_route["detected_language"],
                    "route_confidence": barrier_route["route_confidence"],
                    "barrier_mode": segment_barrier_mode,
                    **_certification_payload_fields(assessed),
                })
            translation_ms = round((time() - translation_started_at) * 1000)
            intent = semantic_context.get("last_intent") or semantic_context.get("intent") or "statement"
            urgency = "high" if semantic_context.get("conversation_mood") == "urgent" else None
            # Lifelike voice: one full neural pass per sentence (not choppy partial clips).
            tts_playback_text = translated_text
            if get_partial_tts_mode():
                live_spoken_text = normalize_live_text(segment_partial_tts_text)
                if live_spoken_text:
                    live_tail = live_translation_delta(live_spoken_text, translated_text)
                    if is_speakable_live_delta(live_tail):
                        tts_playback_text = live_tail
                    elif folded_live_text(translated_text).startswith(folded_live_text(live_spoken_text)):
                        tts_playback_text = ""
            tts_semantic = {
                **(semantic_context or {}),
                "target_language": active_target_language,
            }
            tts_pacing = build_tts_pacing_advanced(
                tts_playback_text or translated_text,
                intent,
                urgency,
                tts_semantic,
            ) if semantic_context else build_tts_pacing(tts_playback_text or translated_text, intent, urgency)
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
                    "confidence": conf_score,
                    "low_confidence": bool(low_confidence_warn or assessed.get("low_confidence")),
                    "confidence_threshold": assessed.get("confidence_threshold"),
                    **_certification_payload_fields(assessed),
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
                or tts_safety_block
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
            playback_decision = segment_brain.begin_playback(speaker)
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
                    tts_chunks.extend(chunk_text_for_tts(tts_segment, natural=True))
                if get_partial_tts_mode():
                    tts_chunks = [chunk for chunk in tts_chunks if not recently_spoken_audio_tts(chunk)]
                elif get_natural_tts_mode():
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
            tts_total_ms = 0
            tts_active = True
            for index, chunk in enumerate(tts_chunks if not skip_tts else [], start=1):
                if segment_brain.active_speaker and segment_brain.active_speaker != speaker:
                    break
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
                    tts_total_ms = tts_ms
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
                "clarify": bool(cip_clarify),
                "clarify_message": final_clarify_message if cip_clarify else (assessed.get("confidence_message") if low_confidence_warn else ""),
                "low_confidence": bool(low_confidence_warn or assessed.get("low_confidence")),
                "confidence": conf_score,
                "confidence_threshold": assessed.get("confidence_threshold"),
                "confidence_message": assessed.get("confidence_message") or "",
                "needs_confirmation": bool(assessed.get("needs_confirmation")) or barrier_route["needs_confirmation"],
                **_certification_payload_fields(assessed),
                "session": shared_session,
                "source_language": active_source_language,
                "target_language": active_target_language,
                "detected_language": barrier_route["detected_language"],
                "detected_language_confidence": barrier_route["detected_language_confidence"],
                "route_confidence": barrier_route["route_confidence"],
                "listener_label": barrier_route["listener_label"],
                "barrier_mode": segment_barrier_mode,
                **result.__dict__,
            })
            observability.observe_latency("streaming_segment", time() - segment_started_at)
            observability.record_event("streaming_segment", identity=identity, speaker=speaker, latency_seconds=time() - segment_started_at)
            total_ms = round((time() - segment_started_at) * 1000)
            await websocket.send_json({"type": "latency", "metric": "backend_response", "ms": total_ms})
            # Update latency engine for adaptive decisions next turns
            latency_engine.update(stt=stt_ms / 1000.0, translate=translation_ms / 1000.0, tts=tts_total_ms / 1000.0)
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
            complete_decision = segment_brain.end_turn(speaker)
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
            resolve_brain().cancel(speaker)
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
                resolve_brain().cancel(segment.get("speaker", speaker))
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
                try:
                    payload = json.loads(message["text"])
                except (json.JSONDecodeError, TypeError):
                    continue
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
                    if payload.get("environment") or payload.get("audio_environment"):
                        environment = _sanitize_environment(
                            payload.get("environment") or payload.get("audio_environment"),
                            environment,
                        )
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
                        asyncio.create_task(
                            _prewarm_conversation_languages(pipeline, source_language, target_language)
                        )
                    await websocket.send_json({
                        "type": "config_ack",
                        "source_language": source_language,
                        "target_language": target_language,
                        "speaker_mode": speaker_mode,
                        "speaker": speaker,
                        "speaker_label": speaker_label,
                        "session_id": session_id,
                        "barrier_mode": barrier_mode,
                        "environment": environment,
                    })
                    continue

                if message_type == "glossary_correction":
                    from backend.glossary import promote_glossary_correction

                    result = promote_glossary_correction(
                        session_id,
                        source=str(payload.get("source_text") or payload.get("source") or ""),
                        target=str(payload.get("corrected_text") or payload.get("target") or ""),
                        source_lang=_sanitize_language_code(payload.get("source_language"), source_language),
                        target_lang=_sanitize_language_code(payload.get("target_language"), target_language),
                        context=str(payload.get("context") or "general"),
                    )
                    await websocket.send_json({
                        "type": "glossary_correction_ack",
                        "ok": bool(result.get("ok")),
                        "updated": bool(result.get("updated")),
                        "entry": result.get("entry"),
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
                        "metering_available": payload.get("metering_available"),
                        "received_at": time(),
                    }
                    if payload.get("heartbeat") and adaptive_vad is not None:
                        try:
                            level = float(payload.get("audio_level") or 0.0)
                        except (TypeError, ValueError):
                            level = 0.0
                        adaptive_vad.adapt_threshold(level, bool(extract_client_voice_active(payload)))
                        vad.set_energy_threshold(adaptive_vad.current_threshold)
                        from backend.glossary import map_environment_for_stt
                        environment = map_environment_for_stt(adaptive_vad.environment.value)
                    continue

                if message_type == "start":
                    previous_session_id = session_id
                    previous_speaker = speaker
                    previous_device_id = device_id
                    speaker_mode = payload.get("speaker_mode") or "manual"
                    if "barrier_mode" in payload:
                        barrier_mode = _truthy(payload.get("barrier_mode"))
                    else:
                        barrier_mode = _default_barrier_mode(
                            payload.get("source_language") or source_language,
                            payload.get("target_language") or target_language,
                        )
                    session_id = payload.get("session_id") or "default"
                    source_language = payload.get("source_language") or "en"
                    target_language = payload.get("target_language") or "ht"
                    if payload.get("environment") or payload.get("audio_environment"):
                        environment = _sanitize_environment(
                            payload.get("environment") or payload.get("audio_environment"),
                            environment,
                        )
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
                        "active_speaker": resolve_brain().active_speaker,
                        "playback_owner": resolve_brain().playback_owner,
                    })
                    reset_segment_state()
                    await websocket.send_json({
                        "type": "session_restored",
                        "session": session_restore_payload(session_state),
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
                    resolve_brain().cancel(speaker)
                    reset_segment_state()
                    await websocket.send_json({"type": "cancelled"})

            if "bytes" in message:
                chunk = message["bytes"]
                stream_debug_log("AUDIO RECEIVED:", len(chunk))
                if last_chunk_meta.get("sent_at_ms"):
                    mic_to_backend_ms = round(time() * 1000 - float(last_chunk_meta["sent_at_ms"]))
                    latency_engine.record_stage("mic_to_backend", mic_to_backend_ms)
                    await websocket.send_json({"type": "latency", "metric": "mic_to_backend", "ms": mic_to_backend_ms})
                    observability.record_event("mobile_latency", identity=identity, metric="mic_to_backend", ms=mic_to_backend_ms, chunk_bytes=len(chunk))
                audio_chunks.extend(chunk)
                audio_suffix = audio_suffix_for_bytes(audio_chunks, client_mime_type)
                observability.record_event("mobile_stream_checkpoint", identity=identity, speaker=speaker, checkpoint="audio_chunk", chunk_bytes=len(chunk), total_audio_bytes=len(audio_chunks))
                effective_buffer_limit = max_buffer_bytes
                if smart_buffer is not None:
                    smart_buffer.add_chunk(chunk, priority=Priority.NORMAL)
                    smart_buffer.update_network_quality(
                        max(0.2, min(1.0, 1.0 - latency_engine.total() / 4.0)),
                    )
                    effective_buffer_limit = min(max_buffer_bytes, smart_buffer.current_max_size)
                if len(audio_chunks) > effective_buffer_limit:
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
                    vad_threshold = get_client_vad_threshold()
                    if adaptive_vad is not None:
                        adaptive_vad.adapt_threshold(audio_level, bool(last_chunk_meta.get("client_voice_active")))
                        vad_threshold = adaptive_vad.current_threshold
                        environment = adaptive_vad.environment.value
                    voice_active = bool(last_chunk_meta.get("client_voice_active")) or audio_level >= vad_threshold
                    if audio_level > 0:
                        last_segment_audio_level = max(last_segment_audio_level, audio_level)
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
                    server_vad_threshold = adaptive_vad.current_threshold if adaptive_vad is not None else None
                    vad_result = await run_in_threadpool(
                        vad.detect_bytes,
                        b"".join(recent_chunks),
                        audio_suffix,
                        energy_threshold=server_vad_threshold,
                    )
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

                if adaptive_vad is not None:
                    try:
                        avg_energy = float(vad_result.get("avg_energy") or 0.0)
                    except (TypeError, ValueError):
                        avg_energy = 0.0
                    if avg_energy > 0:
                        adaptive_vad.adapt_threshold(avg_energy, bool(vad_result.get("speech_detected")))
                        environment = adaptive_vad.environment.value
                        last_segment_audio_level = max(last_segment_audio_level, avg_energy)
                if vad_result["speech_detected"]:
                    stream_debug_log("VAD:", True)
                    observability.increment("vad_speech_total")
                    speech_started = True
                    last_speech_at = time()
                    silent_checks = 0
                    await announce_active_speaker("server_vad", vad_result.get("avg_energy"))
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
        if pipeline_worker is not None:
            pipeline_worker.cancel()
            with suppress(asyncio.CancelledError):
                await pipeline_worker



async def websocket_streaming_stt_translation(
    websocket: WebSocket,
    pipeline: AnaiTranslatorPipeline,
    conversation_brain: ConversationBrain | ConversationBrainRegistry,
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
    if await _reject_audio_socket_if_warming(websocket):
        return
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
    barrier_mode = _default_barrier_mode(source_language, target_language)
    session_id = "default"
    device_id = None
    provider_ws = None
    provider_receiver_task = None
    provider_language = None
    provider_last_partial_text = ""
    provider_last_partial_translation = ""
    provider_partial_tts_text = ""
    provider_last_partial_tts_at = 0.0
    provider_recent_tts_texts: list[str] = []
    send_lock = asyncio.Lock()

    def provider_remember_tts(text: str) -> None:
        spoken = normalize_live_text(text)
        if spoken:
            provider_recent_tts_texts.append(spoken)
            del provider_recent_tts_texts[:-6]

    def provider_recently_spoken(text: str) -> bool:
        spoken = normalize_live_text(text)
        if not spoken:
            return True
        return any(live_translation_redundant(previous, spoken) for previous in provider_recent_tts_texts)

    def resolve_brain(active_session_id: str | None = None) -> ConversationBrain:
        if isinstance(conversation_brain, ConversationBrainRegistry):
            return conversation_brain.get(active_session_id or session_id)
        return conversation_brain

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
        nonlocal provider_partial_tts_text, provider_last_partial_tts_at
        nonlocal provider_last_partial_text, provider_last_partial_translation
        provider_partial_tts_text = ""
        provider_last_partial_tts_at = 0.0
        provider_last_partial_text = ""
        provider_last_partial_translation = ""
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
        semantic_context = resolve_brain().analyze_semantics(effective_speaker, source_text)
        await send_json({"type": "semantic_context", "speaker": effective_speaker, "speaker_label": effective_speaker_label, **semantic_context})
        await send_json({"type": "stage", "stage": "translation", "message": "Transcription ready. Translating..."})

        translation_started_at = time()
        memory_context = memory.get_context()
        speaker_context = speaker_memory.get_context(effective_speaker)
        pre_analysis = _streaming_analysis_for_text(
            source_text,
            memory_context=memory_context,
            speaker_context=speaker_context,
            semantic_context=semantic_context,
            source_language=effective_source_language,
        )
        tx_kwargs = _translation_kwargs_from_analysis(pre_analysis)
        conversation_tone = semantic_context.get("conversation_mood") or pre_analysis.get("tone")
        improved_text = await run_pipeline_step(
            "context improvement",
            pipeline.context_layer.improve,
            source_text,
            effective_source_language,
            effective_target_language,
            conversation_tone,
        )
        try:
            raw_translated_text = await translation_circuit_breaker.call(
                run_pipeline_step,
                "translation",
                _streaming_translate_with_glossary,
                pipeline,
                improved_text,
                effective_source_language,
                effective_target_language,
                session_id,
                **tx_kwargs,
            )
        except (RuntimeError, ValueError, OSError) as exc:
            message = (
                "Translation paused briefly — keep speaking"
                if "Circuit breaker" in str(exc)
                else str(exc)
            )
            await send_json({"type": "error", "message": message, "recoverable": True})
            return
        translated_text = refine_translation(source_text, raw_translated_text, memory_context, speaker_context)
        if await _reject_unusable_translation(
            websocket,
            translated_text,
            speaker=effective_speaker,
            speaker_label=effective_speaker_label,
            source_language=effective_source_language,
            target_language=effective_target_language,
        ):
            return
        stt_conf = estimate_stt_confidence(source_text)
        tr_conf = estimate_translation_confidence(source_text, translated_text)
        translated_text = await run_in_threadpool(
            _apply_ailang_enhancements,
            translated_text, source_text, effective_source_language, effective_target_language,
            effective_speaker, memory, speaker_memory, tr_conf,
            session_context=_ailang_session_context(session_id, pre_analysis),
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
        cip_clarify = should_block_translation_for_cip(
            cip,
            translated_text,
            tr_conf,
            source_text=source_text,
            source_language=effective_source_language,
            target_language=effective_target_language,
            session_id=session_id,
        )
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
        translated_text = resolve_translation_text(cip_clarify, cip, translated_text) if cip_clarify else choose_translation(cip, translated_text)
        tr_conf = estimate_translation_confidence(source_text, translated_text)
        cip_conf = get_cip_confidence(cip)
        from backend.glossary import (
            get_session_glossary,
            glossary_blocks_clarification,
            glossary_coverage_score,
        )

        provider_glossary = get_session_glossary(session_id)
        provider_glossary_cov = glossary_coverage_score(
            source_text,
            translated_text,
            provider_glossary,
            effective_source_language,
            effective_target_language,
        )
        provider_glossary_trusted = glossary_blocks_clarification(
            source_text,
            translated_text,
            provider_glossary,
            effective_source_language,
            effective_target_language,
        )
        cip_domains = {}
        if isinstance(cip, dict) and isinstance(cip.get("analysis"), dict):
            cip_domains = cip["analysis"].get("domains") or {}
        assessed = _assessed_with_communication_context(
            source_text,
            translated_text,
            pre_analysis,
            stt_confidence=stt_conf,
            glossary_trusted=provider_glossary_trusted,
            glossary_coverage=provider_glossary_cov,
            domains=cip_domains if cip_domains else None,
            source_language=effective_source_language,
        )
        conf_score = cip_conf if cip_conf is not None else assessed.get("confidence", ConfidenceEngine().evaluate(stt_conf, tr_conf, ambiguity_score(source_text), pre_analysis.get("context_match") or 0.6))
        low_confidence_threshold = assessed.get("confidence_threshold") or get_cip_confidence_threshold()
        low_confidence_warn = (
            (
                assessed.get("low_confidence")
                or conf_score < low_confidence_threshold
                or assessed.get("needs_native_certification")
            )
            and not cip_clarify
            and not provider_glossary_trusted
        )
        from backend.glossary import check_translation_safety

        provider_tx_kwargs = _translation_kwargs_from_analysis(pre_analysis)
        safety_check = check_translation_safety(
            source_text,
            translated_text,
            source_lang=effective_source_language,
            target_lang=effective_target_language,
            strict_medical=bool(provider_tx_kwargs.get("strict_medical")),
        )
        tts_safety_block = bool(safety_check.get("block_tts"))
        final_clarify_message = assessed.get("confidence_message") or clarification_for(
            source_text, detect_ambiguities(source_text),
        )
        if cip_clarify and isinstance(cip_decision, dict) and cip_decision.get("message"):
            final_clarify_message = cip_decision.get("message")
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
        provider_audio_path = None
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
        elif low_confidence_warn:
            await send_json({
                "type": "clarify",
                "message": final_clarify_message,
                "stage": "final_low_confidence",
                "speaker": effective_speaker,
                "speaker_label": effective_speaker_label,
                "source_language": effective_source_language,
                "target_language": effective_target_language,
                "detected_language": barrier_route["detected_language"],
                "route_confidence": barrier_route["route_confidence"],
                "barrier_mode": barrier_mode,
                **_certification_payload_fields(assessed),
            })
        if not cip_clarify:
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
                "confidence": conf_score,
                "low_confidence": bool(low_confidence_warn or assessed.get("low_confidence")),
                "confidence_threshold": assessed.get("confidence_threshold"),
                **_certification_payload_fields(assessed),
            })
            provider_intent = semantic_context.get("last_intent") or "statement"
            provider_urgency = "high" if semantic_context.get("conversation_mood") == "urgent" else None
            provider_tts_text = translated_text
            if get_partial_tts_mode():
                live_spoken_text = normalize_live_text(provider_last_partial_translation)
                if live_spoken_text:
                    live_tail = live_translation_delta(live_spoken_text, translated_text)
                    if is_speakable_live_delta(live_tail):
                        provider_tts_text = live_tail
                    elif folded_live_text(translated_text).startswith(folded_live_text(live_spoken_text)):
                        provider_tts_text = ""
            provider_pacing = build_tts_pacing_advanced(
                provider_tts_text or translated_text, provider_intent, provider_urgency, semantic_context,
            )
            provider_emotion = emotion_config_from_style(provider_pacing.get("style"))
            provider_skip_tts = (
                not _should_use_backend_live_tts(effective_target_language)
                or not is_speakable_live_delta(provider_tts_text or translated_text)
                or tts_safety_block
                or not (provider_tts_text or translated_text).strip()
            )
            provider_brain = resolve_brain(session_id)
            if not provider_skip_tts:
                playback_decision = provider_brain.begin_playback(effective_speaker)
                await send_json({
                    "type": "turn",
                    "speaker": effective_speaker,
                    "speaker_label": effective_speaker_label,
                    "allowed": playback_decision.allowed,
                    "reason": playback_decision.reason,
                    "behavior": playback_decision.behavior,
                    "active_speaker": playback_decision.active_speaker,
                    "playback_owner": playback_decision.playback_owner,
                })
            if not provider_skip_tts:
                provider_chunks: list[str] = []
                for tts_segment in provider_pacing["segments"]:
                    provider_chunks.extend(chunk_text_for_tts(tts_segment, natural=True))
                provider_chunks = [
                    chunk for chunk in provider_chunks
                    if is_speakable_live_delta(chunk) and not provider_recently_spoken(chunk)
                ]
                if provider_chunks:
                    await send_json({
                        "type": "tts_start",
                        "speaker": effective_speaker,
                        "speaker_label": effective_speaker_label,
                        "chunks": len(provider_chunks),
                        "source_language": effective_source_language,
                        "target_language": effective_target_language,
                        "barrier_mode": barrier_mode,
                    })
                    for index, chunk in enumerate(provider_chunks, start=1):
                        if provider_brain.active_speaker and provider_brain.active_speaker != effective_speaker:
                            break
                        try:
                            chunk_path = await tts_circuit_breaker.call(
                                run_pipeline_step,
                                "provider TTS",
                                lambda c=chunk, idx=index: _synthesize_live_tts_chunk(
                                    pipeline.tts,
                                    c,
                                    f"models/tts/{uuid4()}-provider-{idx}.wav",
                                    language=effective_target_language,
                                    emotion_config=provider_emotion,
                                ),
                            )
                            chunk_audio = Path(chunk_path).read_bytes()
                            if len(chunk_audio) < 100:
                                continue
                            if provider_audio_path is None:
                                provider_audio_path = chunk_path
                            await send_json({
                                "type": "tts_audio_chunk",
                                "speaker": effective_speaker,
                                "speaker_label": effective_speaker_label,
                                "index": index,
                                "total": len(provider_chunks),
                                "text": chunk,
                                "audio_base64": base64.b64encode(chunk_audio).decode("ascii"),
                                "mime_type": "audio/wav",
                                "source_language": effective_source_language,
                                "target_language": effective_target_language,
                                "barrier_mode": barrier_mode,
                            })
                            provider_remember_tts(chunk)
                        except Exception as exc:
                            logger.debug("provider_tts_chunk_failed error=%s", exc)
                            break
                    await send_json({
                        "type": "tts_end",
                        "speaker": effective_speaker,
                        "speaker_label": effective_speaker_label,
                        "source_language": effective_source_language,
                        "target_language": effective_target_language,
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
            audio_output_path=provider_audio_path,
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
            "clarify": bool(cip_clarify),
            "clarify_message": final_clarify_message if cip_clarify else (assessed.get("confidence_message") if low_confidence_warn else ""),
            "low_confidence": bool(low_confidence_warn or assessed.get("low_confidence")),
            "confidence": conf_score,
            "confidence_threshold": assessed.get("confidence_threshold"),
            "confidence_message": assessed.get("confidence_message") or "",
            "needs_confirmation": bool(assessed.get("needs_confirmation")) or barrier_route["needs_confirmation"],
            **_certification_payload_fields(assessed),
            "session": shared_session,
            "source_language": effective_source_language,
            "target_language": effective_target_language,
            "detected_language": barrier_route["detected_language"],
            "detected_language_confidence": barrier_route["detected_language_confidence"],
            "route_confidence": barrier_route["route_confidence"],
            "listener_label": barrier_route["listener_label"],
            "barrier_mode": barrier_mode,
            **result.__dict__,
        })
        complete_decision = resolve_brain().end_turn(effective_speaker)
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

    async def emit_provider_partial(text: str) -> None:
        nonlocal provider_last_partial_text, provider_last_partial_translation, provider_partial_tts_text, provider_last_partial_tts_at
        text = normalize_live_text(text)
        if not text or len(text.split()) < 2 or text == provider_last_partial_text:
            return
        provider_last_partial_text = text
        partial_route = resolve_barrier_route(text, source_language, target_language, enabled=barrier_mode)
        effective_source = partial_route["source_language"]
        effective_target = partial_route["target_language"]
        effective_speaker = partial_route["speaker"] if barrier_mode else speaker
        effective_label = partial_route["speaker_label"] if barrier_mode else speaker_label
        partial_memory = memory.get_context()
        partial_speaker_ctx = speaker_memory.get_context(effective_speaker)
        partial_semantic = resolve_brain(session_id).semantic_snapshot()
        partial_analysis = _streaming_analysis_for_text(
            text,
            memory_context=partial_memory,
            speaker_context=partial_speaker_ctx,
            semantic_context=partial_semantic,
            source_language=effective_source,
        )
        partial_tx_kwargs = _translation_kwargs_from_analysis(partial_analysis)
        partial_tone = partial_semantic.get("conversation_mood") or partial_analysis.get("tone")
        try:
            improved = await run_in_threadpool(
                pipeline.context_layer.improve,
                text,
                effective_source,
                effective_target,
                partial_tone,
            )
            raw_partial = await translation_circuit_breaker.call(
                run_pipeline_step,
                "provider partial translation",
                _streaming_translate_with_glossary,
                pipeline,
                improved,
                effective_source,
                effective_target,
                session_id,
                **partial_tx_kwargs,
            )
        except (RuntimeError, ValueError, OSError):
            return
        refined = refine_translation(text, raw_partial, partial_memory, partial_speaker_ctx)
        if not refined or is_internal_translation_artifact(refined) or refined == provider_last_partial_translation:
            return
        provider_last_partial_translation = refined
        from backend.glossary import get_session_glossary, glossary_blocks_clarification, glossary_coverage_score

        provider_glossary = get_session_glossary(session_id)
        provider_glossary_cov = glossary_coverage_score(
            text, refined, provider_glossary, effective_source, effective_target,
        )
        stt_conf = estimate_stt_confidence(text)
        tr_conf = estimate_translation_confidence(text, refined)
        provider_partial_glossary_trusted = glossary_blocks_clarification(
            text, refined, provider_glossary, effective_source, effective_target,
        )
        partial_assessed = _assessed_with_communication_context(
            text,
            refined,
            partial_analysis,
            stt_confidence=stt_conf,
            glossary_trusted=provider_partial_glossary_trusted,
            glossary_coverage=provider_glossary_cov,
            source_language=effective_source,
        )
        partial_low_confidence = bool(
            partial_assessed.get("low_confidence") or partial_assessed.get("needs_native_certification")
        ) and not provider_partial_glossary_trusted
        if partial_low_confidence:
            from backend.communication_brain import clarification_message

            await send_json({
                "type": "clarify",
                "message": partial_assessed.get("confidence_message") or clarification_message(
                    text,
                    {**partial_analysis, "ambiguity": {"words": detect_ambiguities(text)}},
                    "low_confidence",
                ),
                "stage": "partial_low_confidence",
                "speaker": effective_speaker,
                "speaker_label": effective_label,
                "confidence": partial_assessed.get("confidence"),
                "confidence_threshold": partial_assessed.get("confidence_threshold"),
                "low_confidence": True,
            })
            return
        await send_json({
            "type": "partial_translation",
            "speaker": effective_speaker,
            "speaker_label": effective_label,
            "text": refined,
            "source_text": text,
            "source_language": effective_source,
            "target_language": effective_target,
            "detected_language": partial_route.get("detected_language"),
            "route_confidence": partial_route.get("route_confidence"),
            "barrier_mode": barrier_mode,
            "source": "stt_provider",
            "confidence": partial_assessed.get("confidence", tr_conf),
            "low_confidence": bool(partial_assessed.get("low_confidence")),
            "confidence_message": partial_assessed.get("confidence_message") or "",
            "confidence_threshold": partial_assessed.get("confidence_threshold"),
            **_certification_payload_fields(partial_assessed),
        })
        if not get_partial_tts_mode() or not _should_use_backend_live_tts(effective_target):
            return
        tts_delta = live_translation_delta(provider_partial_tts_text, refined)
        tts_text_to_speak = (
            tts_delta
            if is_speakable_live_delta(tts_delta)
            else (refined if refined != provider_partial_tts_text else "")
        )
        if not is_speakable_live_delta(tts_text_to_speak) or provider_recently_spoken(tts_text_to_speak):
            return
        provider_partial_threshold = partial_assessed.get("confidence_threshold") or get_cip_confidence_threshold()
        if float(partial_assessed.get("confidence", tr_conf) or 0.0) < provider_partial_threshold:
            return
        now = time()
        if provider_last_partial_tts_at and (now - provider_last_partial_tts_at) < 0.45:
            return
        partial_intent = partial_semantic.get("last_intent") or "statement"
        partial_urgency = "high" if partial_semantic.get("conversation_mood") == "urgent" else None
        partial_pacing = build_tts_pacing_advanced(
            tts_text_to_speak, partial_intent, partial_urgency, partial_semantic,
        )
        partial_emotion = emotion_config_from_style(partial_pacing.get("style"))
        provider_brain = resolve_brain(session_id)
        if provider_brain.active_speaker and provider_brain.active_speaker != effective_speaker:
            return
        try:
            partial_tts_path = await tts_circuit_breaker.call(
                run_pipeline_step,
                "provider partial TTS",
                lambda: _synthesize_live_tts_chunk(
                    pipeline.tts,
                    tts_text_to_speak,
                    f"models/tts/{uuid4()}-provider-partial.wav",
                    language=effective_target,
                    emotion_config=partial_emotion,
                ),
            )
            partial_tts_audio = Path(partial_tts_path).read_bytes()
            if len(partial_tts_audio) < 100:
                return
            playback = provider_brain.begin_playback(effective_speaker)
            provider_partial_tts_text = refined
            provider_last_partial_tts_at = now
            await send_json({
                "type": "turn",
                "speaker": effective_speaker,
                "speaker_label": effective_label,
                "allowed": playback.allowed,
                "reason": playback.reason,
                "behavior": playback.behavior,
                "active_speaker": playback.active_speaker,
                "playback_owner": playback.playback_owner,
                "partial": True,
            })
            await send_json({
                "type": "tts_start",
                "speaker": effective_speaker,
                "speaker_label": effective_label,
                "chunks": 1,
                "partial": True,
                "source_language": effective_source,
                "target_language": effective_target,
                "barrier_mode": barrier_mode,
            })
            await send_json({
                "type": "tts_audio_chunk",
                "speaker": effective_speaker,
                "speaker_label": effective_label,
                "index": 1,
                "total": 1,
                "text": tts_text_to_speak,
                "live_translation_text": refined,
                "source_text": text,
                "source_language": effective_source,
                "target_language": effective_target,
                "audio_base64": base64.b64encode(partial_tts_audio).decode("ascii"),
                "mime_type": "audio/wav",
                "partial": True,
                "barrier_mode": barrier_mode,
            })
            provider_remember_tts(tts_text_to_speak)
            await send_json({
                "type": "tts_end",
                "speaker": effective_speaker,
                "speaker_label": effective_label,
                "partial": True,
                "source_language": effective_source,
                "target_language": effective_target,
                "barrier_mode": barrier_mode,
            })
        except Exception as exc:
            logger.debug("provider_partial_tts_failed error=%s", exc)

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
                await emit_provider_partial(text)
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
                    if session_registry.active_stream_count(identity) > get_max_active_streams_per_user():
                        session_registry.disconnect(session_id, speaker, identity, device_id)
                        await send_json({"type": "error", "message": "Too many active streams for this user."})
                        continue
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
                        "active_speaker": resolve_brain().active_speaker,
                        "playback_owner": resolve_brain().playback_owner,
                    })
                    await send_json({
                        "type": "session_restored",
                        "session": session_restore_payload(session_state),
                        "message": "Speaker stream bound to session.",
                    })
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
                    resolve_brain().cancel(speaker)
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
