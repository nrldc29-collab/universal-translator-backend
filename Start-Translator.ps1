param(
    [switch]$Restart,
    [switch]$NoTunnel,
    [switch]$SkipSetup
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Logs = Join-Path $Root "logs"
$BackendPort = 8000
$FrontendPort = 5173

New-Item -ItemType Directory -Force -Path $Logs | Out-Null

function Test-PortListening {
    param([int]$Port)
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Stop-PortOwner {
    param([int]$Port)
    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

function Get-CloudflaredPath {
    $command = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $knownPath = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
    if (Test-Path $knownPath) {
        return $knownPath
    }
    return $null
}

function Get-TunnelUrl {
    param([string[]]$Paths)
    foreach ($path in $Paths) {
        if (-not (Test-Path $path)) {
            continue
        }
        $match = Select-String -Path $path -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -AllMatches |
            Select-Object -ExpandProperty Matches |
            Select-Object -Last 1
        if ($match) {
            return $match.Value
        }
    }
    return $null
}

function Import-DotEnv {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        return
    }
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            return
        }
        $parts = $line -split "=", 2
        if ($parts.Count -ne 2) {
            return
        }
        $name = $parts[0].Trim().TrimStart([char]0xFEFF)
        $value = $parts[1].Trim().Trim('"').Trim("'")
        if ($name -and -not [string]::IsNullOrWhiteSpace($value)) {
            Set-Item -Path "Env:$name" -Value $value
        }
    }
}

function Wait-BackendReady {
    param(
        [int]$Port,
        [int]$Attempts = 120
    )
    for ($attempt = 1; $attempt -le $Attempts; $attempt += 1) {
        try {
            $response = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 5
            if ($response.ready -eq $true) {
                return $true
            }
        } catch {
            # backend still starting
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

if ($Restart) {
    Stop-PortOwner -Port $BackendPort
    Stop-PortOwner -Port $FrontendPort
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

Import-DotEnv -Path (Join-Path $Root ".env")

$env:FRONTEND_URL = "http://127.0.0.1:$FrontendPort"
$env:ALLOWED_ORIGIN_REGEX = "https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(:\d+)?|https://.*\.trycloudflare\.com"
$env:PARTIAL_TTS_MODE = "true"
if (-not $env:TRANSLATION_BACKEND) { $env:TRANSLATION_BACKEND = "marian" }
if (-not $env:WHISPER_MODEL_SIZE) { $env:WHISPER_MODEL_SIZE = "small" }
if (-not $env:PRELOAD_MODELS) { $env:PRELOAD_MODELS = "1" }
if (-not $env:HYBRID_ENABLE_REMOTE) { $env:HYBRID_ENABLE_REMOTE = "0" }
if (-not $env:PREFER_CLOUD_TTS) { $env:PREFER_CLOUD_TTS = "0" }
if (-not $env:MAX_ACTIVE_STREAMS_PER_USER) { $env:MAX_ACTIVE_STREAMS_PER_USER = "4" }
if (-not $env:REQUESTS_PER_MINUTE) { $env:REQUESTS_PER_MINUTE = "120" }
if (-not $env:STT_PROVIDER) { $env:STT_PROVIDER = "local" }

$backendOut = Join-Path $Logs "backend.out.log"
$backendErr = Join-Path $Logs "backend.err.log"
$frontendOut = Join-Path $Logs "frontend.out.log"
$frontendErr = Join-Path $Logs "frontend.err.log"
$tunnelOut = Join-Path $Logs "tunnel.out.log"
$tunnelErr = Join-Path $Logs "tunnel.err.log"

$python = Join-Path $Root "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Missing venv Python at $python. Create venv and run: pip install -r requirements.txt"
}

function Test-EspeakInstalled {
    if (Get-Command espeak-ng -ErrorAction SilentlyContinue) { return $true }
    if (Get-Command espeak -ErrorAction SilentlyContinue) { return $true }
    return $false
}

if (-not $SkipSetup) {
    if (-not (Test-EspeakInstalled)) {
        Write-Output "Warning: espeak-ng/espeak not found. Install for Haitian Creole TTS:"
        Write-Output "  choco install espeak-ng"
    }
    Write-Output "Running local model setup (first run downloads models)..."
    & $python (Join-Path $Root "scripts\setup_models.py")
    if ($LASTEXITCODE -ne 0) {
        throw "Model setup failed. Fix errors above, then retry Start-Translator.ps1"
    }
}

if (Test-PortListening -Port $BackendPort) {
    $backendHealthy = $false
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/health" -TimeoutSec 5
        $backendHealthy = ($health.ready -eq $true)
    } catch {
        $backendHealthy = $false
    }
    if (-not $backendHealthy) {
        Write-Output "Replacing stale backend listener on port $BackendPort..."
        Stop-PortOwner -Port $BackendPort
        Start-Sleep -Seconds 1
    }
}

if (-not (Test-PortListening -Port $BackendPort)) {
    Start-Process -FilePath $python -ArgumentList @("-m", "uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "$BackendPort") -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr | Out-Null
}

if (-not (Test-PortListening -Port $FrontendPort)) {
    $viteCmd = Join-Path $Root "frontend\node_modules\.bin\vite.cmd"
    if (-not (Test-Path $viteCmd)) {
        throw "Missing Vite command at $viteCmd. Run npm install in the frontend folder first."
    }
    Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "`"$viteCmd`" --host 0.0.0.0") -WorkingDirectory (Join-Path $Root "frontend") -WindowStyle Hidden -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr | Out-Null
}

Write-Output "Waiting for backend models to finish loading..."
$ready = Wait-BackendReady -Port $BackendPort
if (-not $ready) {
    Write-Output "Warning: backend health did not report ready=true yet. Check $backendErr"
}

Start-Sleep -Seconds 1

$tunnelUrl = $null
if (-not $NoTunnel) {
    $cloudflared = Get-CloudflaredPath
    if ($cloudflared) {
        Remove-Item -LiteralPath $tunnelOut, $tunnelErr -Force -ErrorAction SilentlyContinue
        Start-Process -FilePath $cloudflared -ArgumentList @("tunnel", "--url", "http://127.0.0.1:$BackendPort") -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $tunnelOut -RedirectStandardError $tunnelErr | Out-Null
        for ($attempt = 0; $attempt -lt 24; $attempt += 1) {
            Start-Sleep -Milliseconds 500
            $tunnelUrl = Get-TunnelUrl -Paths @($tunnelErr, $tunnelOut)
            if ($tunnelUrl) {
                break
            }
        }
    }
}

Write-Output ""
Write-Output "Anai Translator is starting."
Write-Output "Local app:  http://127.0.0.1:$FrontendPort/"
Write-Output "Backend:    http://127.0.0.1:$BackendPort/"
Write-Output "Health:     http://127.0.0.1:$BackendPort/health"
if ($ready) {
    Write-Output "Status:     LIVE (models ready — mic and text translate enabled)"
} else {
    Write-Output "Status:     WARMING (wait for LIVE in the app header before using mic)"
}
if ($tunnelUrl) {
    Write-Output "Phone app:  $tunnelUrl"
} elseif (-not $NoTunnel) {
    Write-Output "Phone app:  cloudflared URL not ready yet; check $tunnelErr"
}
Write-Output ""
Write-Output "Logs:"
Write-Output "  Backend:  $backendErr"
Write-Output "  Frontend: $frontendErr"
Write-Output "  Tunnel:   $tunnelErr"
Write-Output ""
Write-Output "When LIVE, verify with: .\Test-Translator.ps1"
Write-Output "Bundled dist check: npm run build in frontend, then .\Test-Translator.ps1 -BaseUrl http://127.0.0.1:8001"
