#!/usr/bin/env pwsh
# One-shot verification: speech, TTS, translation, and client tests.
param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Step($name, [scriptblock]$action) {
    Write-Host "`n=== $name ===" -ForegroundColor Cyan
    & $action
    if ($? -eq $false) { throw "$name failed" }
    Write-Host "OK: $name" -ForegroundColor Green
}

$failed = $false
try {
    Step "Health" {
        $r = Invoke-WebRequest -Uri "$BaseUrl/health" -UseBasicParsing -TimeoutSec 10
        if ($r.StatusCode -ne 200) { exit 1 }
        Write-Host $r.Content
    }
    Step "Speech pipeline (14 langs translate + TTS)" {
        python scripts/verify_speech_pipeline.py $BaseUrl
        if ($LASTEXITCODE -ne 0) { throw "speech pipeline failed" }
    }
    Step "Live API matrix (182 pairs)" {
        python scripts/live_api_lang_test.py --api-url $BaseUrl --phrases greeting --max-seconds 180
        if ($LASTEXITCODE -ne 0) { throw "live api failed" }
    }
    Step "Backend pytest (speech/TTS/glossary)" {
        python -m pytest tests/test_glossary_quality.py tests/test_live_voice_language_coverage.py tests/test_tts_cache.py tests/test_streaming_helpers.py tests/test_api_translate.py -q
        if ($LASTEXITCODE -ne 0) { throw "pytest failed" }
    }
    Step "Frontend unit tests" {
        Push-Location frontend
        npm test -- --run
        if ($LASTEXITCODE -ne 0) { Pop-Location; throw "frontend tests failed" }
        Pop-Location
    }
    Step "Mobile unit tests" {
        Push-Location translator-mobile
        npm test -- --passWithNoTests
        if ($LASTEXITCODE -ne 0) { Pop-Location; throw "mobile tests failed" }
        Pop-Location
    }
    Step "Console probe (35s, zero errors)" {
        Push-Location frontend
        $out = node scripts/console-probe.cjs "$BaseUrl/"
        Pop-Location
        Write-Host "Console errors: $out"
        if ($out -ne "[]") { exit 1 }
    }
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "ALL SPEECH VERIFICATION PASSED" -ForegroundColor Green
    Write-Host "========================================`n" -ForegroundColor Green
} catch {
    Write-Host "`nFAILED: $_" -ForegroundColor Red
    exit 1
}
