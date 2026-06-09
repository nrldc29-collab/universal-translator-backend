param(
    [ValidateSet("ios", "android", "all")]
    [string]$Platform = "ios",

    [ValidateSet("development", "preview", "production")]
    [string]$Profile = "preview",

    [switch]$Login,
    [switch]$SkipChecks
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$MobileRoot = Join-Path $Root "translator-mobile"
$EnvPath = Join-Path $MobileRoot ".env"

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Command
}

if (-not (Test-Path -LiteralPath $MobileRoot)) {
    throw "Mobile project not found at $MobileRoot"
}

Push-Location $MobileRoot
try {
    if (-not (Test-Path -LiteralPath $EnvPath)) {
        throw "Missing $EnvPath. Run Start-MobilePhoneMode.ps1 first so the phone API URL is saved."
    }

    $apiLine = Get-Content -LiteralPath $EnvPath |
        Where-Object { $_ -match "^EXPO_PUBLIC_API_URL=" } |
        Select-Object -First 1
    if (-not $apiLine) {
        throw "Missing EXPO_PUBLIC_API_URL in $EnvPath"
    }

    $env:EXPO_PUBLIC_API_URL = $apiLine -replace "^EXPO_PUBLIC_API_URL=", ""
    $env:EXPO_PUBLIC_DEBUG_LOGS = "0"
    $env:EAS_NO_VCS = "1"

    Write-Host "Mobile API URL: $env:EXPO_PUBLIC_API_URL"
    Write-Host "Build target:   $Platform / $Profile"
    Write-Host "EAS archive:    mobile project only"

    if ($Login) {
        Invoke-Step "Expo login" {
            npx.cmd eas-cli login
        }
    }

    $whoamiOutput = & npx.cmd eas-cli whoami --non-interactive 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "Expo/EAS is not logged in on this machine." -ForegroundColor Yellow
        Write-Host "Run this first:"
        Write-Host "  .\Build-MobilePreview.ps1 -Login"
        Write-Host ""
        Write-Host "Or set EXPO_TOKEN and rerun this build script."
        exit 1
    }

    Write-Host "Expo account:   $whoamiOutput"

    if (-not $SkipChecks) {
        Invoke-Step "Expo Doctor" {
            npx.cmd expo-doctor
        }

        Invoke-Step "TypeScript" {
            npx.cmd tsc --noEmit
        }

        Invoke-Step "Mobile lint" {
            npm.cmd exec eslint -- App.js index.js AppStyles.js hooks\useMobileTts.js services\audio-stream.js services\ws.js
        }
    }

    $buildArgs = @("eas-cli", "build", "--platform", $Platform, "--profile", $Profile)
    if ($Profile -ne "production") {
        $buildArgs += "--clear-cache"
    }

    Invoke-Step "EAS build" {
        npx.cmd @buildArgs
    }
} finally {
    Pop-Location
}
