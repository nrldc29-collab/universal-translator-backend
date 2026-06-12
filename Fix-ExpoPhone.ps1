param(
    [switch]$SkipFirewall
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Output "=== Anai Expo phone fix ==="
Write-Output ""

if (-not $SkipFirewall) {
    $fwScript = Join-Path $Root "Allow-AnaiTranslatorFirewall.ps1"
    if (Test-Path -LiteralPath $fwScript) {
        try {
            & $fwScript
        } catch {
            Write-Warning "Firewall script needs Administrator. Run: Start-Process powershell -Verb RunAs -ArgumentList '-File ""$fwScript""'"
        }
    }
}

$backendOk = $false
try {
    $health = Invoke-RestMethod "http://127.0.0.1:8000/health" -TimeoutSec 6
    $backendOk = ($health.status -eq "ok")
} catch {
    $backendOk = $false
}
if (-not $backendOk) {
    Write-Output "Backend not healthy on :8000 - restarting translator..."
    $startTranslator = Join-Path $Root "Start-Translator.ps1"
    if (Test-Path -LiteralPath $startTranslator) {
        & $startTranslator -Restart
    } else {
        Write-Warning "Start-Translator.ps1 not found; start backend manually."
    }
}

& (Join-Path $Root "Start-MobilePhoneMode.ps1") -RestartExpo -FreshPort
& (Join-Path $Root "Test-PhoneConnection.ps1")
