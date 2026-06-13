param(
    [string]$Username = "admin",
    [string]$Password = "",
    [string]$RailwayOrigin = ""
)

$ErrorActionPreference = "Stop"

function New-Secret {
    param([int]$Bytes = 32)
    $buffer = [byte[]]::new($Bytes)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($buffer)
    } finally {
        $rng.Dispose()
    }
    return [Convert]::ToBase64String($buffer).TrimEnd("=") -replace "\+", "-" -replace "/", "_"
}

if (-not $Password) {
    $Password = New-Secret -Bytes 18
}

$jwtSecret = New-Secret -Bytes 48
$variables = [ordered]@{
    ENVIRONMENT = "production"
    BACKEND_HOST = "0.0.0.0"
    SERVE_FRONTEND_DIST = "1"
    FRONTEND_DIST_DIR = "frontend/dist"
    USE_GPU = "0"
    WHISPER_DEVICE = "cpu"
    WHISPER_COMPUTE_TYPE = "int8"
    WHISPER_MODEL_SIZE = "tiny"
    WHISPER_CPU_THREADS = "4"
    WHISPER_NUM_WORKERS = "1"
    PRELOAD_MODELS = "1"
    TRANSLATION_BACKEND = "hybrid"
    TRANSLATION_DEVICE = "cpu"
    HYBRID_ENABLE_MARIAN_FALLBACK = "0"
    OLLAMA_ENABLED = "0"
    AILANG_ENABLED = "1"
    GPU_COST_MODE = "low"
    STT_MAX_CONCURRENCY = "2"
    WHISPER_BEAM_SIZE = "1"
    VAD_RECENT_CHUNKS = "2"
    VAD_SILENT_CHECKS = "1"
    VAD_FORCE_FINAL_SECONDS = "0.25"
    SPEECH_MERGE_MS = "40"
    MIN_SPEECH_BYTES = "4000"
    NEAR_ZERO_LATENCY_MODE = "1"
    PARTIAL_STT_MIN_BYTES = "1200"
    PARTIAL_STT_INTERVAL_MS = "100"
    PARTIAL_TTS_MODE = "1"
    PIPELINE_STEP_TIMEOUT_SECONDS = "10"
    PREDICTIVE_CACHE_SIZE = "1000"
    PREDICTIVE_CACHE_TTL = "3600"
    TTS_CHUNK_CHARS = "14"
    TTS_FIRST_CHUNK_CHARS = "10"
    PREFER_CLOUD_TTS = "1"
    DATA_DIR = "/app/data"
    REQUESTS_PER_MINUTE = "120"
    QUOTA_REQUESTS_PER_HOUR = "500"
    MAX_ACTIVE_STREAMS_PER_USER = "5"
    JWT_SECRET = $jwtSecret
    USERS = "$Username`:$Password"
    USER_TIERS = "$Username`:standard"
    ADMIN_IDENTITIES = $Username
}

if ($RailwayOrigin) {
    $variables.ALLOWED_ORIGINS = $RailwayOrigin
    if ($RailwayOrigin -match "https?://([^/]+)") {
        $host = $Matches[1]
        $escaped = [regex]::Escape($host)
        $variables.ALLOWED_ORIGIN_REGEX = "https?://$escaped"
    }
}

Write-Output ""
Write-Output "Paste these into Railway service variables:"
Write-Output ""
foreach ($item in $variables.GetEnumerator()) {
    Write-Output "$($item.Key)=$($item.Value)"
}
Write-Output ""
Write-Output "Login for the app:"
Write-Output "  username: $Username"
Write-Output "  password: $Password"
Write-Output ""
Write-Output "Also mount a Railway volume at /app/data for persistent storage."
Write-Output "Keep the password and JWT_SECRET private."
