<#
.SYNOPSIS
    Build production mobile app with hosted Anai Cloud URL (consumer open-and-go).

.USAGE
    .\Build-ConsumerApp.ps1 -CloudUrl "https://your-service.up.railway.app"
    .\Build-ConsumerApp.ps1 -CloudUrl "https://your-service.up.railway.app" -Platform ios
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$CloudUrl,
    [string]$DemoUser = "demo",
    [string]$DemoPass = "",
    [ValidateSet("all", "ios", "android")]
    [string]$Platform = "all"
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Mobile = Join-Path $Root "translator-mobile"
$EnvPath = Join-Path $Mobile ".env"

$CloudUrl = $CloudUrl.Trim().TrimEnd("/")
if ($CloudUrl -notmatch '^https?://') {
    throw "CloudUrl must start with http:// or https://"
}

if (-not $DemoPass -and (Test-Path -LiteralPath $EnvPath)) {
    Get-Content -LiteralPath $EnvPath | ForEach-Object {
        if ($_ -match '^EXPO_PUBLIC_CLOUD_DEMO_PASS=(.+)$') {
            $DemoPass = $Matches[1].Trim()
        }
        if ($_ -match '^EXPO_PUBLIC_CLOUD_DEMO_USER=(.+)$') {
            $DemoUser = $Matches[1].Trim()
        }
    }
}
if (-not $DemoPass) {
    throw "DemoPass required (or set EXPO_PUBLIC_CLOUD_DEMO_PASS in translator-mobile/.env). Also run: eas secret:create --scope project --name EXPO_PUBLIC_CLOUD_DEMO_PASS"
}

Write-Host "`n=== Anai consumer app build ===" -ForegroundColor Cyan
Write-Host "Cloud: $CloudUrl"
Write-Host "Platform: $Platform`n"

$env:EXPO_PUBLIC_CLOUD_API_URL = $CloudUrl
$env:EXPO_PUBLIC_CLOUD_DEMO_USER = $DemoUser
$env:EXPO_PUBLIC_CLOUD_DEMO_PASS = $DemoPass
$env:EXPO_PUBLIC_DEBUG_LOGS = "0"

Push-Location $Mobile
try {
    if (-not (Get-Command eas -ErrorAction SilentlyContinue)) {
        throw "EAS CLI not found. Run: npm install -g eas-cli && eas login"
    }
    eas build --profile production --platform $Platform --non-interactive
} finally {
    Pop-Location
}
