param(
    [string]$TunnelName = "anai-translator",
    [Parameter(Mandatory = $true)]
    [string]$Hostname,
    [string]$TunnelToken = $env:ANAI_TUNNEL_TOKEN,
    [string]$TunnelTokenFile = $env:ANAI_TUNNEL_TOKEN_FILE,
    [switch]$OverwriteDns
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Get-CloudflaredPath {
    $command = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $knownPath = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
    if (Test-Path $knownPath) {
        return $knownPath
    }
    throw "cloudflared is not installed or not on PATH."
}

$cloudflared = Get-CloudflaredPath
$logsDir = Join-Path $Root "logs"
$envPath = Join-Path $logsDir "stable-tunnel.env"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

function Normalize-Hostname {
    param([string]$Value)
    $normalized = ($Value -replace "/+$", "").Trim()
    if ($normalized.StartsWith("http://") -or $normalized.StartsWith("https://")) {
        return ([Uri]$normalized).Host
    }
    return $normalized
}

$Hostname = Normalize-Hostname -Value $Hostname
if (-not $Hostname) {
    throw "Hostname is required."
}

if ($TunnelToken -or $TunnelTokenFile) {
    if ($TunnelToken) {
        $TunnelTokenFile = Join-Path $logsDir "stable-tunnel-token.txt"
        Set-Content -LiteralPath $TunnelTokenFile -Value $TunnelToken.Trim() -NoNewline -Encoding ascii
        $TunnelToken = ""
    } elseif (-not [System.IO.Path]::IsPathRooted($TunnelTokenFile)) {
        $TunnelTokenFile = Join-Path $Root $TunnelTokenFile
    }
    if (-not (Test-Path -LiteralPath $TunnelTokenFile)) {
        throw "Tunnel token file was not found: $TunnelTokenFile"
    }

@"
ANAI_TUNNEL_HOSTNAME=$Hostname
ANAI_TUNNEL_TOKEN_FILE=$TunnelTokenFile
"@ | Set-Content -LiteralPath $envPath -Encoding ascii

    Write-Output ""
    Write-Output "Stable tunnel token is configured."
    Write-Output "Hostname:    https://$Hostname"
    Write-Output "Token file:  $TunnelTokenFile"
    Write-Output "Saved:       $envPath"
    Write-Output ""
    Write-Output "Start with:"
    Write-Output ".\Start-Translator.ps1 -Restart"
    return
}

$cloudflaredDir = Join-Path $env:USERPROFILE ".cloudflared"
$originCert = Join-Path $cloudflaredDir "cert.pem"

if (-not (Test-Path $originCert)) {
    Write-Output "Cloudflare login is required once to create a stable named tunnel."
    Write-Output "A browser login will open. After it completes, rerun this command if setup does not continue."
    & $cloudflared tunnel login
}

if (-not (Test-Path $originCert)) {
    throw "Cloudflare origin certificate was not found at $originCert."
}

$existing = & $cloudflared tunnel list 2>&1 | Out-String
if ($existing -notmatch [regex]::Escape($TunnelName)) {
    & $cloudflared tunnel create $TunnelName
}

if ($OverwriteDns) {
    & $cloudflared tunnel route dns --overwrite-dns $TunnelName $Hostname
} else {
    & $cloudflared tunnel route dns $TunnelName $Hostname
}

@"
ANAI_TUNNEL_NAME=$TunnelName
ANAI_TUNNEL_HOSTNAME=$Hostname
"@ | Set-Content -LiteralPath $envPath -Encoding ascii

Write-Output ""
Write-Output "Stable tunnel is configured."
Write-Output "Tunnel name: $TunnelName"
Write-Output "Hostname:    https://$Hostname"
Write-Output "Saved:       $envPath"
Write-Output ""
Write-Output "Start with:"
Write-Output ".\Start-Translator.ps1 -Restart"
