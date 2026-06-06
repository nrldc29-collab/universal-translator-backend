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
    WHISPER_CPU_THREADS = "4"
    WHISPER_NUM_WORKERS = "1"
    PRELOAD_MODELS = "0"
    TRANSLATION_DEVICE = "cpu"
    GPU_COST_MODE = "low"
    STT_MAX_CONCURRENCY = "1"
    WHISPER_BEAM_SIZE = "1"
    VAD_RECENT_CHUNKS = "2"
    VAD_SILENT_CHECKS = "1"
    VAD_FORCE_FINAL_SECONDS = "0.35"
    SPEECH_MERGE_MS = "80"
    MIN_SPEECH_BYTES = "4000"
    NEAR_ZERO_LATENCY_MODE = "1"
    PARTIAL_STT_MIN_BYTES = "4000"
    PARTIAL_STT_INTERVAL_MS = "250"
    PIPELINE_STEP_TIMEOUT_SECONDS = "10"
    TTS_CHUNK_CHARS = "26"
    TRANSLATION_BACKEND = "marian"
    HYBRID_ENABLE_MARIAN_FALLBACK = "1"
    HYBRID_ENABLE_REMOTE = "0"
    PREFER_CLOUD_TTS = "0"
    STT_PROVIDER = "local"
    REQUESTS_PER_MINUTE = "120"
    QUOTA_REQUESTS_PER_HOUR = "500"
    MAX_ACTIVE_STREAMS_PER_USER = "5"
    ALLOWED_ORIGIN_REGEX = "https://.*\.up\.railway\.app"
    JWT_SECRET = $jwtSecret
    USERS = "$Username`:$Password"
    USER_TIERS = "$Username`:free"
}

if ($FrontendOrigin) {
    $variables.ALLOWED_ORIGINS = $FrontendOrigin
} else {
    $variables.ALLOWED_ORIGINS = 'https://${{RAILWAY_PUBLIC_DOMAIN}}'
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
Write-Output "Finish public access (required once):"
Write-Output "  1. Open https://railway.com/project/0d581567-e2fa-4405-a041-1b9aaeeafceb"
Write-Output "  2. Project Settings -> Tokens -> create a project token"
Write-Output "  3. Add Railway variable: RAILWAY_TOKEN=<project-token>"
Write-Output "  4. Redeploy - the service auto-generates https://....up.railway.app on startup"
Write-Output ""
Write-Output "Or manually: Service -> Settings -> Networking -> Generate Domain,"
Write-Output "then rerun: .\Get-Railway-Variables.ps1 -Username $Username -FrontendOrigin https://YOUR-SERVICE.up.railway.app"
Write-Output ""
Write-Output "Keep the password, JWT_SECRET, and RAILWAY_TOKEN private."
