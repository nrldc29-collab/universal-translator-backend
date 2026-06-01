# Restart-Translator.ps1
# Kills backend + frontend, then relaunches with PARTIAL_TTS_MODE enabled.
# Double-click this or run: powershell -ExecutionPolicy Bypass -File Restart-Translator.ps1

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Output "Stopping existing backend (port 8000) and frontend (port 5173)..."

foreach ($Port in @(8000, 5173)) {
    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($l in $listeners) {
        Stop-Process -Id $l.OwningProcess -Force -ErrorAction SilentlyContinue
        Write-Output "  Killed process on port $Port (PID $($l.OwningProcess))"
    }
}

Start-Sleep -Seconds 2

Write-Output "Launching Anai Translator with real-time audio (PARTIAL_TTS_MODE=true)..."
& "$Root\Start-Translator.ps1"
