# Keep-NeuralVoiceAlive.ps1
# Restarts the neural voice backend if it stops (prevents robotic browser fallback).
# Run in background: powershell -ExecutionPolicy Bypass -File Keep-NeuralVoiceAlive.ps1

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StartScript = Join-Path $Root "Start-NeuralVoiceBackend.ps1"
$BackendPort = 8000
$IntervalSeconds = 30

function Test-NeuralBackend {
    try {
        $diag = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/diagnostics" -TimeoutSec 5
        return ($diag.tts_neural.neural_ready -eq $true)
    } catch {
        return $false
    }
}

Write-Host "Neural voice watchdog started (checks every ${IntervalSeconds}s). Press Ctrl+C to stop."

while ($true) {
    if (-not (Test-NeuralBackend)) {
        Write-Host "$(Get-Date -Format 'HH:mm:ss') Neural backend down - restarting..."
        if (Test-Path -LiteralPath $StartScript) {
            & $StartScript | Out-Host
        }
    }
    Start-Sleep -Seconds $IntervalSeconds
}
