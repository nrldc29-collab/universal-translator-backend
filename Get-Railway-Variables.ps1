param(
    [string]$Username = "demo",
    [string]$Password = "",
    [string]$FrontendOrigin = ""
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
    GPU_COST_MODE = "low"
    STT_MAX_CONCURRENCY = "1"
    WHISPER_BEAM_SIZE = "1"
    VAD_FORCE_FINAL_SECONDS = "0.75"
    SPEECH_MERGE_MS = "140"
    MIN_SPEECH_BYTES = "9000"
    NEAR_ZERO_LATENCY_MODE = "1"
    PARTIAL_STT_MIN_BYTES = "8000"
    PARTIAL_STT_INTERVAL_MS = "500"
    TTS_CHUNK_CHARS = "36"
    REQUESTS_PER_MINUTE = "20"
    MAX_ACTIVE_STREAMS_PER_USER = "2"
    JWT_SECRET = $jwtSecret
    USERS = "$Username`:$Password"
    USER_TIERS = "$Username`:free"
}

if ($FrontendOrigin) {
    $variables.ALLOWED_ORIGINS = $FrontendOrigin
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
Write-Output "Keep the password and JWT_SECRET private."
