import os


LANGUAGES = {
    "en": "English",
    "es": "Spanish",
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
    if os.getenv("GPU_COST_MODE", "balanced").lower() == "low":
        return os.getenv("WHISPER_MODEL_SIZE", "tiny")
    return os.getenv("WHISPER_MODEL_SIZE", "base")


def get_stt_max_concurrency() -> int:
    return int(os.getenv("STT_MAX_CONCURRENCY", "1"))


def get_whisper_beam_size() -> int:
    return int(os.getenv("WHISPER_BEAM_SIZE", "1"))


def get_translation_backend() -> str:
    return os.getenv("TRANSLATION_BACKEND", "marian").lower()


def get_allowed_origins() -> list[str]:
    # Default: local dev + production URLs
    default_origins = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "https://frontend-one-henna-99jlsna6ki.vercel.app,"
        "https://frontend-qftj8v2jh-nrldc29-9295s-projects.vercel.app"
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
    return int(os.getenv("BACKEND_PORT") or os.getenv("PORT", "8000"))


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
    return int(os.getenv("QUOTA_REQUESTS_PER_HOUR", "120"))


def get_jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "dev-only-change-me")


def get_session_minutes() -> int:
    return int(os.getenv("SESSION_MINUTES", "480"))


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
    return int(os.getenv("REQUESTS_PER_MINUTE", "20"))


def get_max_audio_mb() -> int:
    return int(os.getenv("MAX_AUDIO_MB", "25"))


def get_max_audio_seconds() -> int:
    return int(os.getenv("MAX_AUDIO_SECONDS", "300"))


def get_free_daily_audio_minutes() -> int:
    return int(os.getenv("FREE_DAILY_AUDIO_MINUTES", "10"))


def get_tts_chunk_chars() -> int:
    return int(os.getenv("TTS_CHUNK_CHARS", "36"))


def get_vad_recent_chunks() -> int:
    return int(os.getenv("VAD_RECENT_CHUNKS", "3"))


def get_vad_silent_checks() -> int:
    return int(os.getenv("VAD_SILENT_CHECKS", "1"))


def get_vad_force_final_seconds() -> float:
    return float(os.getenv("VAD_FORCE_FINAL_SECONDS", "0.75"))


def get_near_zero_latency_mode() -> bool:
    return os.getenv("NEAR_ZERO_LATENCY_MODE", "1") == "1"


def get_stream_hot_path_logging() -> bool:
    return os.getenv("STREAM_HOT_PATH_LOGGING", "0") == "1"


def get_partial_stt_min_bytes() -> int:
    return int(os.getenv("PARTIAL_STT_MIN_BYTES", "8000"))


def get_partial_stt_interval_ms() -> int:
    return int(os.getenv("PARTIAL_STT_INTERVAL_MS", "500"))


def get_min_speech_bytes() -> int:
    return int(os.getenv("MIN_SPEECH_BYTES", "9000"))


def get_speech_merge_ms() -> int:
    return int(os.getenv("SPEECH_MERGE_MS", "140"))


def get_stream_buffer_max_mb() -> int:
    return int(os.getenv("STREAM_BUFFER_MAX_MB", "12"))


def get_semantic_history_limit() -> int:
    return int(os.getenv("SEMANTIC_HISTORY_LIMIT", "12"))


def get_topic_limit() -> int:
    return int(os.getenv("TOPIC_LIMIT", "25"))


def get_session_ttl_seconds() -> int:
    return int(os.getenv("SESSION_TTL_SECONDS", "1800"))


def get_session_history_limit() -> int:
    return int(os.getenv("SESSION_HISTORY_LIMIT", "20"))


def get_stt_queue_max_depth() -> int:
    return int(os.getenv("STT_QUEUE_MAX_DEPTH", "8"))


def get_max_active_streams_per_user() -> int:
    return int(os.getenv("MAX_ACTIVE_STREAMS_PER_USER", "2"))


def get_pipeline_step_timeout_seconds() -> float:
    return float(os.getenv("PIPELINE_STEP_TIMEOUT_SECONDS", "10"))
