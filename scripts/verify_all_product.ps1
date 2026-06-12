<#
.SYNOPSIS
    Full product verification - core pipeline, polish, ops, UX, consumer readiness.

.USAGE
    .\scripts\verify_all_product.ps1
    .\scripts\verify_all_product.ps1 -BackendUrl "http://127.0.0.1:8000"
#>
param(
    [string]$BackendUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "`n=== Anai full product verification ===" -ForegroundColor Cyan
Write-Host "Backend: $BackendUrl`n"

function Invoke-Step {
    param([string]$Name, [scriptblock]$Action)
    Write-Host "--- $Name ---" -ForegroundColor Yellow
    & $Action
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "$Name failed (exit $LASTEXITCODE)"
    }
    Write-Host "  OK`n" -ForegroundColor Green
}

$liveArgs = @()
try {
    $health = Invoke-RestMethod -Uri "$BackendUrl/health" -TimeoutSec 8
    if ($health.ready -eq $true) {
        $liveArgs = @("--live", $BackendUrl)
        Write-Host "Backend ready - running live checks.`n" -ForegroundColor Green
    } else {
        Write-Host "Backend not ready - static checks only.`n" -ForegroundColor DarkYellow
    }
} catch {
    Write-Host "Backend unreachable - static checks only.`n" -ForegroundColor DarkYellow
}

Invoke-Step "Product readiness scorecard" {
    python scripts/product_readiness.py @liveArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Invoke-Step "Continuous speech audit" {
    python scripts/audit_continuous_speech.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Invoke-Step "Brain / confidence / cert tests" {
    python -m pytest tests/test_communication_brain.py tests/test_confidence_latency.py -q --tb=line
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if ($liveArgs.Count -gt 0) {
    Invoke-Step 'Speech pipeline (14 languages)' {
        python scripts/verify_speech_pipeline.py $BackendUrl
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}

Invoke-Step "Mobile unit tests" {
    Push-Location (Join-Path $Root "translator-mobile")
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    npm test -- --passWithNoTests --no-coverage 2>&1 | Out-Null
    $testExit = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    Pop-Location
    if ($testExit -ne 0) {
        throw "Mobile unit tests failed (exit $testExit)"
    }
}

Write-Host "=== ALL PRODUCT VERIFICATION PASSED ===" -ForegroundColor Green
