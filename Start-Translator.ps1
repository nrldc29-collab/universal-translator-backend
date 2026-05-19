param(
    [switch]$Restart,
    [switch]$NoTunnel
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

if ($Restart) {
    Stop-PortOwner -Port $BackendPort
    Stop-PortOwner -Port $FrontendPort
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

$backendOut = Join-Path $Logs "backend.out.log"
$backendErr = Join-Path $Logs "backend.err.log"
$frontendOut = Join-Path $Logs "frontend.out.log"
$frontendErr = Join-Path $Logs "frontend.err.log"
$tunnelOut = Join-Path $Logs "tunnel.out.log"
$tunnelErr = Join-Path $Logs "tunnel.err.log"

if (-not (Test-PortListening -Port $BackendPort)) {
    $python = Join-Path $Root "venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        throw "Missing venv Python at $python"
    }
    $env:FRONTEND_URL = "http://127.0.0.1:$FrontendPort"
    $env:ALLOWED_ORIGIN_REGEX = "https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(:\d+)?|https://.*\.trycloudflare\.com"
    Start-Process -FilePath $python -ArgumentList @("-m", "uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "$BackendPort") -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr | Out-Null
}

if (-not (Test-PortListening -Port $FrontendPort)) {
    $viteCmd = Join-Path $Root "frontend\node_modules\.bin\vite.cmd"
    if (-not (Test-Path $viteCmd)) {
        throw "Missing Vite command at $viteCmd. Run npm install in the frontend folder first."
    }
    Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "`"$viteCmd`" --host 0.0.0.0") -WorkingDirectory (Join-Path $Root "frontend") -WindowStyle Hidden -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr | Out-Null
}

Start-Sleep -Seconds 3

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
Write-Output "Local app:  http://127.0.0.1:$BackendPort/"
Write-Output "Health:     http://127.0.0.1:$BackendPort/health"
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
