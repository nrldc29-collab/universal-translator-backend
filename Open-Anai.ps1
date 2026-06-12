<#
.SYNOPSIS
    One command: ensure Anai is running and open the interpreter in your browser.

.USAGE
    .\Open-Anai.ps1
    .\Open-Anai.ps1 -Restart
#>
param(
    [switch]$Restart
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendPort = 8000
$Base = "http://127.0.0.1:$BackendPort"
$HealthUrl = "$Base/health"

function Test-AnaiReady {
    try {
        $h = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 5
        return ($h.ready -eq $true)
    } catch {
        return $false
    }
}

function Get-LanIp {
    try {
        $addrs = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object {
                $_.IPAddress -notmatch '^(127\.|169\.254\.)' -and
                $_.PrefixOrigin -ne 'WellKnown'
            } |
            Sort-Object -Property InterfaceMetric
        if ($addrs) { return $addrs[0].IPAddress }
    } catch { }
    return ""
}

Set-Location $Root

if (-not (Test-AnaiReady) -or $Restart) {
    Write-Host "Starting Anai (QuickStart)..." -ForegroundColor Cyan
    & (Join-Path $Root "Start-Translator.ps1") -QuickStart -Restart
} else {
    Write-Host "Anai already running." -ForegroundColor Green
}

$deadline = (Get-Date).AddMinutes(3)
while (-not (Test-AnaiReady)) {
    if ((Get-Date) -gt $deadline) {
        Write-Error "Backend did not become ready within 3 minutes. Check logs\backend.err"
    }
    Start-Sleep -Seconds 2
}

Write-Host "`nOpening interpreter in your browser..." -ForegroundColor Cyan
Start-Process $Base

$lan = Get-LanIp
Write-Host "`nAnai is ready" -ForegroundColor Green
Write-Host "  PC:     $Base/"
if ($lan) {
    Write-Host "  iPhone: https://${lan}:8443/mobile/app  (Safari, same Wi-Fi, mic)"
    Write-Host "  Setup:  http://${lan}:$BackendPort/mobile"
}
Write-Host "`nTap Start, speak continuously, Pause to stop."
Write-Host "Score:  .\Score-Product.ps1`n"

python (Join-Path $Root "scripts\product_readiness.py") --live $Base
exit $LASTEXITCODE
