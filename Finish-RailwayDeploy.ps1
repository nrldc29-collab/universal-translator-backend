<#
.SYNOPSIS
    Finish Railway deployment after code is pushed to GitHub.

.DESCRIPTION
    Polls /health until the service is ready, then updates translator-mobile/.env
    and prints verification commands.

.PARAMETER ServiceUrl
    Your Railway HTTPS URL, e.g. https://my-service.up.railway.app

.PARAMETER MaxWaitMinutes
    How long to poll before giving up (default 15).
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$ServiceUrl,
    [int]$MaxWaitMinutes = 15
)

$ErrorActionPreference = "Stop"
$ServiceUrl = $ServiceUrl.TrimEnd("/")

Write-Host "Polling $ServiceUrl/health (max ${MaxWaitMinutes}m)..." -ForegroundColor Cyan
$deadline = (Get-Date).AddMinutes($MaxWaitMinutes)
$ready = $false

while ((Get-Date) -lt $deadline) {
    try {
        $health = Invoke-RestMethod -Uri "$ServiceUrl/health" -TimeoutSec 20
        Write-Host "  status=$($health.status) ready=$($health.ready) release=$($health.release)"
        if ($health.ready -eq $true) {
            $ready = $true
            break
        }
    } catch {
        Write-Host "  waiting... ($($_.Exception.Message))"
    }
    Start-Sleep -Seconds 20
}

if (-not $ready) {
    Write-Host "Service not ready yet. Check Railway deploy logs." -ForegroundColor Yellow
    exit 1
}

Write-Host "`nHealth OK. Running diagnostics..." -ForegroundColor Green
$diag = Invoke-RestMethod -Uri "$ServiceUrl/diagnostics" -TimeoutSec 30
Write-Host "  diagnostics status: $($diag.status)"
Write-Host "  translation: $($diag.translation.backend) / $($diag.translation.runtime)"

$mobileEnv = Join-Path $PSScriptRoot "translator-mobile\.env"
$lines = @(
    "EXPO_PUBLIC_API_URL=$ServiceUrl",
    "EXPO_PUBLIC_DEBUG_LOGS=0"
)
Set-Content -Path $mobileEnv -Value $lines -Encoding utf8
Write-Host "`nUpdated $mobileEnv" -ForegroundColor Green

Write-Host "`nDeployment complete." -ForegroundColor Green
Write-Host "  Web UI:  $ServiceUrl"
Write-Host "  Health:  $ServiceUrl/health"
Write-Host "  Mobile:  restart Expo with translator-mobile/.env pointing here"
