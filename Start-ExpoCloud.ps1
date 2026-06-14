<#
.SYNOPSIS
    Start Expo Go against production Railway (open-and-go cloud). Syncs .env and clears Metro cache.

.USAGE
    .\Start-ExpoCloud.ps1
    .\Start-ExpoCloud.ps1 -CloudUrl "https://your-service.up.railway.app"
#>
param(
    [string]$CloudUrl = "https://universal-translator-backend-production.up.railway.app",
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$MobileRoot = Join-Path $Root "translator-mobile"
$EnvPath = Join-Path $MobileRoot ".env"
$CloudUrl = $CloudUrl.Trim().TrimEnd("/")

Write-Host "`n=== Anai Expo (production cloud) ===" -ForegroundColor Cyan
Write-Host "Cloud: $CloudUrl"

$demoUser = "demo"
$demoPass = ""
try {
    $railwayJson = railway variables --json 2>$null
    if ($LASTEXITCODE -eq 0 -and $railwayJson) {
        $vars = $railwayJson | ConvertFrom-Json
        if ($vars.USERS) {
            $parts = [string]$vars.USERS -split ":", 2
            if ($parts.Count -ge 1 -and $parts[0]) { $demoUser = $parts[0] }
            if ($parts.Count -ge 2 -and $parts[1]) { $demoPass = $parts[1] }
        }
    }
} catch {
    Write-Warning "Could not read Railway variables (run: railway login). Using existing .env password if present."
}

if (-not $demoPass -and (Test-Path -LiteralPath $EnvPath)) {
    Get-Content -LiteralPath $EnvPath | ForEach-Object {
        if ($_ -match '^EXPO_PUBLIC_CLOUD_DEMO_PASS=(.+)$') {
            $demoPass = $Matches[1].Trim()
        }
    }
}

if (-not $demoPass) {
    throw "No cloud demo password. Run 'railway login' then rerun, or set EXPO_PUBLIC_CLOUD_DEMO_PASS in translator-mobile/.env"
}

try {
    $health = Invoke-RestMethod -Uri "$CloudUrl/health" -TimeoutSec 20
    if ($health.ready -ne $true) {
        Write-Warning "Backend warming (ready=false). Expo will retry connect automatically."
    } else {
        Write-Host "Backend: ready" -ForegroundColor Green
    }
} catch {
    throw "Cannot reach $CloudUrl/health - check Railway deploy first."
}

$envContent = @(
    "EXPO_PUBLIC_API_URL=$CloudUrl"
    "EXPO_PUBLIC_CLOUD_API_URL=$CloudUrl"
    "EXPO_PUBLIC_CLOUD_DEMO_USER=$demoUser"
    "EXPO_PUBLIC_CLOUD_DEMO_PASS=$demoPass"
    "EXPO_PUBLIC_DEBUG_LOGS=0"
) -join "`n"
Set-Content -LiteralPath $EnvPath -Value ($envContent + "`n") -Encoding ascii -NoNewline
Write-Host "Wrote $EnvPath (EXPO_PUBLIC_DEBUG_LOGS=0 for quiet console)" -ForegroundColor Green
Write-Host "Login user: $demoUser"

Push-Location $MobileRoot
try {
    npm run preflight:expo
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    if ($ValidateOnly) {
        Write-Host "`nValidateOnly: .env synced and backend OK. Run without -ValidateOnly to start Expo.`n" -ForegroundColor Green
        return
    }
    Write-Host "`nStarting Expo with clean cache...`n" -ForegroundColor Cyan
    Write-Host "On your phone: force-close Expo Go, scan QR, wait for full bundle.`n"
    npm run start:clean
} finally {
    Pop-Location
}
