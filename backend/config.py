import os


def _to_int(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _to_float(name: str, default: float, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _to_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "ht": "Haitian Creole",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ru": "Russian",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "hi": "Hindi",
}


def get_whisper_device() -> str:
    return os.getenv("WHISPER_DEVICE", "cuda" if os.getenv("USE_GPU", "0") == "1" else "cpu")


def get_whisper_compute_type() -> str:
    if get_whisper_device() == "cuda":
        return os.getenv("WHISPER_COMPUTE_TYPE", "float16")
    return os.getenv("WHISPER_COMPUTE_TYPE", "int8")


def get_whisper_model_size() -> str:
    # Optimize for faster partial translations - use tiny model for speed
    if os.getenv("GPU_COST_MODE", "balanced").lower() == "low":
        return os.getenv("WHISPER_MODEL_SIZE", "tiny")
    # Use tiny model by default for fastest partial STT
    return os.getenv("WHISPER_MODEL_SIZE", "tiny")


def get_whisper_cpu_threads() -> int:
    return _to_int("WHISPER_CPU_THREADS", max(2, min((os.cpu_count() or 2), 4)), minimum=1)


def get_whisper_num_workers() -> int:
    return _to_int("WHISPER_NUM_WORKERS", 1, minimum=1)


def get_stt_max_concurrency() -> int:
    return _to_int("STT_MAX_CONCURRENCY", 2, minimum=1)


def get_whisper_beam_size() -> int:
    return _to_int("WHISPER_BEAM_SIZE", 1, minimum=1)


def get_translation_backend() -> str:
    return os.getenv("TRANSLATION_BACKEND", "hybrid").lower()


def get_translation_device() -> str:
    return os.getenv("TRANSLATION_DEVICE", "cuda" if os.getenv("USE_GPU", "0") == "1" else "cpu")


def get_cip_process_url() -> str:
    return os.getenv("CIP_PROCESS_URL", "").strip()


def get_cip_mode() -> str:
    mode = os.getenv("CIP_DEFAULT_MODE", os.getenv("CIP_MODE", "ut_first")).strip().lower()
    return mode if mode in {"off", "ut_first", "cip_first"} else "off"


def get_cip_timeout_seconds() -> float:
    return _to_float("CIP_TIMEOUT_SECONDS", 0.65, minimum=0.05)


def get_cip_retries() -> int:
    return _to_int("CIP_RETRIES", 0, minimum=0)


def get_cip_confidence_threshold() -> float:
    return _to_float("CIP_CONFIDENCE_THRESHOLD", 0.42, minimum=0.0, maximum=1.0)


def get_cip_ambiguity_threshold() -> float:
    return _to_float("CIP_AMBIGUITY_THRESHOLD", 0.68, minimum=0.0, maximum=1.0)


def get_preload_models() -> bool:
    return _to_bool("PRELOAD_MODELS", True)


def get_allowed_origins() -> list[str]:
    # Default: local dev + production URLs
    default_origins = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "https://your-frontend.example.com"
    )
    origins = os.getenv("ALLOWED_ORIGINS", default_origins)
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


def get_allowed_origin_regex() -> str:
    return os.getenv(
        "ALLOWED_ORIGIN_REGEX",
        r"https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(:\d+)?",
    )


def get_backend_host() -> str:
    return os.getenv("BACKEND_HOST", "127.0.0.1")


def get_backend_port() -> int:
    return _to_int("BACKEND_PORT", _to_int("PORT", 8000, minimum=1, maximum=65535), minimum=1, maximum=65535)


def get_frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "http://127.0.0.1:5173")


def get_frontend_dist_dir() -> str:
    return os.getenv("FRONTEND_DIST_DIR", "frontend/dist")


def get_serve_frontend_dist() -> bool:
    return os.getenv("SERVE_FRONTEND_DIST", "1" if is_production() else "0") == "1"


def is_production() -> bool:
    return os.getenv("ENVIRONMENT", "development").lower() == "production"


def get_api_keys() -> set[str]:
    keys = os.getenv("API_KEYS", "")
    return {key.strip() for key in keys.split(",") if key.strip()}


def get_quota_limit() -> int:
    return _to_int("QUOTA_REQUESTS_PER_HOUR", 120, minimum=1)


def get_jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "dev-only-change-me")


def get_session_minutes() -> int:
    return _to_int("SESSION_MINUTES", 480, minimum=1)


def get_users() -> dict[str, str]:
    raw_users = os.getenv("USERS", "demo:demo")
    users = {}
    for item in raw_users.split(","):
        if ":" in item:
            username, password = item.split(":", 1)
            users[username.strip()] = password.strip()
    return users


def get_user_tiers() -> dict[str, str]:
    raw_tiers = os.getenv("USER_TIERS", "demo:free")
    tiers = {}
    for item in raw_tiers.split(","):
        if ":" in item:
            username, tier = item.split(":", 1)
            tiers[username.strip()] = tier.strip()
    return tiers


def get_requests_per_minute() -> int:
    return _to_int("REQUESTS_PER_MINUTE", 20, minimum=1)


def get_max_audio_mb() -> int:
    return _to_int("MAX_AUDIO_MB", 25, minimum=1)


def get_max_audio_seconds() -> int:
    return _to_int("MAX_AUDIO_SECONDS", 300, minimum=1)


def get_free_daily_audio_minutes() -> int:
    return _to_int("FREE_DAILY_AUDIO_MINUTES", 10, minimum=0)


def get_tts_chunk_chars() -> int:
    return _to_int("TTS_CHUNK_CHARS", 14, minimum=6)


def get_tts_first_chunk_chars() -> int:
    return _to_int("TTS_FIRST_CHUNK_CHARS", 10, minimum=4)


def get_client_vad_mode() -> bool:
    return _to_bool("CLIENT_VAD_MODE", True)


def get_client_vad_threshold() -> float:
    return _to_float("CLIENT_VAD_THRESHOLD", 0.055, minimum=0.0)


def get_partial_translation_min_words() -> int:
    return _to_int("PARTIAL_TRANSLATION_MIN_WORDS", 1, minimum=1)


def get_partial_tts_mode() -> bool:
    return _to_bool("PARTIAL_TTS_MODE", True)


def get_vad_recent_chunks() -> int:
    return _to_int("VAD_RECENT_CHUNKS", 2, minimum=1)


def get_vad_silent_checks() -> int:
    return _to_int("VAD_SILENT_CHECKS", 1, minimum=1)


def get_vad_force_final_seconds() -> float:
    return _to_float("VAD_FORCE_FINAL_SECONDS", 0.25, minimum=0.05)


def get_near_zero_latency_mode() -> bool:
    # Enable near-zero latency mode by default for streaming partial translation
    return _to_bool("NEAR_ZERO_LATENCY_MODE", True)


def get_stream_hot_path_logging() -> bool:
    return _to_bool("STREAM_HOT_PATH_LOGGING", False)


def get_partial_stt_min_bytes() -> int:
    return _to_int("PARTIAL_STT_MIN_BYTES", 1200, minimum=1)


def get_partial_stt_interval_ms() -> int:
    return _to_int("PARTIAL_STT_INTERVAL_MS", 100, minimum=25)


def get_min_speech_bytes() -> int:
    return _to_int("MIN_SPEECH_BYTES", 4000, minimum=1)


def get_speech_merge_ms() -> int:
    return _to_int("SPEECH_MERGE_MS", 40, minimum=0)


def get_stream_buffer_max_mb() -> int:
    return _to_int("STREAM_BUFFER_MAX_MB", 12, minimum=1)


def get_semantic_history_limit() -> int:
    return _to_int("SEMANTIC_HISTORY_LIMIT", 12, minimum=1)


def get_topic_limit() -> int:
    return _to_int("TOPIC_LIMIT", 25, minimum=1)


def get_session_ttl_seconds() -> int:
    return _to_int("SESSION_TTL_SECONDS", 1800, minimum=60)


def get_session_history_limit() -> int:
    return _to_int("SESSION_HISTORY_LIMIT", 20, minimum=1)


def get_stt_queue_max_depth() -> int:
    return _to_int("STT_QUEUE_MAX_DEPTH", 8, minimum=1)


def get_max_active_streams_per_user() -> int:
    return _to_int("MAX_ACTIVE_STREAMS_PER_USER", 2, minimum=1)



def get_pipeline_step_timeout_seconds() -> float:
    return _to_float("PIPELINE_STEP_TIMEOUT_SECONDS", 10.0, minimum=1.0)


# ---------------------------------------------------------------------------
# STT Provider (streaming STT service)
# ---------------------------------------------------------------------------


def get_stt_provider() -> str:
    """Return ``'local'`` (direct faster-whisper) or ``'streaming'`` (STT provider service)."""
    mode = os.getenv("STT_PROVIDER", "local").strip().lower()
    return mode if mode in {"local", "streaming"} else "local"


def get_stt_provider_url() -> str:
    return os.getenv("STT_PROVIDER_URL", "http://127.0.0.1:8002").rstrip("/")


def get_stt_provider_ws_url() -> str:
    return os.getenv("STT_PROVIDER_WS_URL", "ws://127.0.0.1:8002/stt/stream").rstrip("/")


def get_stt_provider_api_key() -> str:
    return os.getenv("STT_PROVIDER_API_KEY", "").strip()
