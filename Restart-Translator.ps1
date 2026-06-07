# Restart-Translator.ps1
# Kills backend + frontend, then relaunches with neural TTS enabled.
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

Write-Output "Launching Anai Translator with lifelike neural voice..."
$neuralScript = Join-Path $Root "Start-NeuralVoiceBackend.ps1"
$watchdogScript = Join-Path $Root "Keep-NeuralVoiceAlive.ps1"
if (Test-Path -LiteralPath $neuralScript) {
    & $neuralScript
    if (Test-Path -LiteralPath $watchdogScript) {
        $existing = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like "*Keep-NeuralVoiceAlive.ps1*" }
        if (-not $existing) {
            Start-Process -FilePath "powershell.exe" -ArgumentList @(
                "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$watchdogScript`""
            ) -WorkingDirectory $Root -WindowStyle Hidden | Out-Null
            Write-Output "Neural voice watchdog started (auto-restart if backend stops)."
        }
    }
} else {
    & "$Root\Start-Translator.ps1" -Restart -NoTunnel -SkipProductTest
}
