<#
.SYNOPSIS
    One path to consumer open-and-go: verify cloud backend, smoke test, print app build command.

.USAGE
    .\Deploy-ConsumerCloud.ps1 -CloudUrl "https://your-service.up.railway.app"
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$CloudUrl
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$CloudUrl = $CloudUrl.Trim().TrimEnd("/")

Write-Host "`n=== Anai consumer cloud deploy check ===" -ForegroundColor Cyan
Write-Host "Cloud: $CloudUrl`n"

try {
    $health = Invoke-RestMethod -Uri "$CloudUrl/health" -TimeoutSec 20
    if ($health.ready -ne $true) {
        Write-Warning "Backend not ready yet. Wait for models, then re-run."
        Write-Host ($health | ConvertTo-Json -Depth 4)
        exit 1
    }
    Write-Host "Health: ready" -ForegroundColor Green
    if ($health.consumer_open_and_go) {
        Write-Host "Consumer open-and-go: enabled" -ForegroundColor Green
    }
} catch {
    throw "Cannot reach $CloudUrl/health - deploy Railway first (see RAILWAY-DEPLOY.md)"
}

$mobileEnv = Join-Path $Root "translator-mobile\.env"
$demoUser = "demo"
$demoPass = ""
if (Test-Path -LiteralPath $mobileEnv) {
    Get-Content -LiteralPath $mobileEnv | ForEach-Object {
        if ($_ -match '^EXPO_PUBLIC_CLOUD_DEMO_USER=(.+)$') { $demoUser = $Matches[1].Trim() }
        if ($_ -match '^EXPO_PUBLIC_CLOUD_DEMO_PASS=(.+)$') { $demoPass = $Matches[1].Trim() }
    }
}
if ($demoUser -and $demoPass) {
    $env:USERS = "${demoUser}:${demoPass}"
}
$env:SMOKE_REMOTE = "1"

python (Join-Path $Root "scripts\smoke_local.py") $CloudUrl
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python (Join-Path $Root "scripts\product_readiness.py") --live $CloudUrl
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n=== Cloud verified - build consumer app ===" -ForegroundColor Green
Write-Host "  .\Build-ConsumerApp.ps1 -CloudUrl `"$CloudUrl`""
Write-Host "`nWeb/PWA (same URL, no app): open $CloudUrl in mobile browser and Add to Home Screen."
Write-Host "Privacy: $CloudUrl/privacy.html`n"
