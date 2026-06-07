# Start-NeuralVoiceBackend.ps1
# Starts only the backend with lifelike Edge neural TTS (no phone tunnel).
# Run: powershell -ExecutionPolicy Bypass -File Start-NeuralVoiceBackend.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Logs = Join-Path $Root "logs"
$BackendPort = 8000
$Python = Join-Path $Root "venv\Scripts\python.exe"

New-Item -ItemType Directory -Force -Path $Logs | Out-Null

if (-not (Test-Path $Python)) {
    throw "Missing venv at $Python. Run: python -m venv venv; .\venv\Scripts\pip install -r requirements.txt"
}

function Stop-Port([int]$Port) {
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}

Write-Host "Installing neural TTS if needed..."
try { & $Python -m pip install "edge-tts==7.2.8" -q } catch {}

Stop-Port -Port $BackendPort
Start-Sleep -Seconds 1

$env:PRELOAD_MODELS = "false"
$env:SKIP_TRANSLATION_WARMUP = "true"
$env:OLLAMA_ENABLED = "false"
$env:PREFER_EDGE_TTS = "true"
$env:TTS_EDGE_SSML_PAUSES = "true"
$env:TTS_SOFTENING_ENABLED = "true"
$env:TTS_VOICE_PROFILE = "neural"
$env:TTS_NEURAL_MINIMAL_PROCESSING = "true"
$env:TTS_NATURAL_VOICE = "true"
$env:TTS_NATURAL_SPEED = "1.0"
$env:TTS_NATURAL_PITCH_SHIFT = "0"
$env:PARTIAL_TTS_MODE = "0"
$env:TTS_PROSODY_WARMTH = "false"
$env:SERVE_FRONTEND_DIST = "1"
$env:FRONTEND_DIST_DIR = "frontend/dist"
$env:ALLOW_ESPEAK_FALLBACK = "0"

$backendOut = Join-Path $Logs "backend.out.log"
$backendErr = Join-Path $Logs "backend.err.log"

Write-Host "Starting neural voice backend on port $BackendPort..."
Start-Process -FilePath $Python `
    -ArgumentList @("-m", "uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "$BackendPort") `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $backendOut `
    -RedirectStandardError $backendErr | Out-Null

for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $diag = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/diagnostics" -TimeoutSec 3
        if ($diag.tts_neural.neural_ready) {
            Write-Host ""
            Write-Host "READY - Lifelike neural voice is active."
            Write-Host "Open:     http://127.0.0.1:$BackendPort/"
            Write-Host "Neural:   $($diag.tts_neural.recommended_engine)"
            Write-Host "Logs:     $backendErr"
            exit 0
        }
        if ($diag.ready) {
            Write-Host "Backend up but neural TTS not ready: $($diag.tts_neural.issues -join '; ')"
            exit 1
        }
    } catch {}
}

Write-Host "Backend did not become ready in time. Check: $backendErr"
exit 1
