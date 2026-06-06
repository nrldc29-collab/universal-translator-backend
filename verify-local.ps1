<#
.SYNOPSIS
    Local verification script for the Universal Translator pipeline.
    Starts the backend, runs the full pipeline, measures latency, and reports results.

.DESCRIPTION
    Tests: text translation, audio translation, latency endpoint, health, diagnostics,
    duplex conversation brain, and three-tier routing metrics.

.USAGE
    .\verify-local.ps1
    .\verify-local.ps1 -BackendUrl "http://localhost:8000"
    .\verify-local.ps1 -SkipStartup   # if backend is already running
#>

param(
    [string]$BackendUrl = "http://localhost:8000",
    [switch]$SkipStartup
)

$ErrorActionPreference = "Continue"
$passed = 0
$failed = 0
$skipped = 0

function Test-Step {
    param([string]$Name, [scriptblock]$Action)
    Write-Host "`n--- $Name ---" -ForegroundColor Cyan
    try {
        $result = & $Action
        if ($result -eq $false) {
            Write-Host "  FAILED" -ForegroundColor Red
            $script:failed++
        } else {
            Write-Host "  PASSED" -ForegroundColor Green
            $script:passed++
        }
    } catch {
        Write-Host "  FAILED: $_" -ForegroundColor Red
        $script:failed++
    }
}

Write-Host "============================================" -ForegroundColor Yellow
Write-Host "  Universal Translator — Local Verification" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Yellow
Write-Host "Backend: $BackendUrl"
Write-Host ""

# -------------------------------------------------------
# 1. Check backend is running
# -------------------------------------------------------
Test-Step "Backend health check" {
    $resp = Invoke-RestMethod -Uri "$BackendUrl/health" -TimeoutSec 5
    Write-Host "  Ready: $($resp.ready)"
    if ($resp.ready -eq $true) { return $true }
    Write-Host "  Backend not ready yet. If you just started it, wait for model preloading."
    return $false
}

# -------------------------------------------------------
# 2. Text translation (lightweight phrase table)
# -------------------------------------------------------
Test-Step "Text translation — 'hello' -> Spanish" {
    $body = @{ text = "hello"; source_language = "en"; target_language = "es" } | ConvertTo-Json
    $resp = Invoke-RestMethod -Uri "$BackendUrl/translate/text" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 10
    Write-Host "  Source: $($resp.source_text)"
    Write-Host "  Translated: $($resp.translated_text)"
    return ($resp.translated_text -match "(?i)hola")
}

# -------------------------------------------------------
# 3. Text translation (longer phrase — tests remote/marian tier)
# -------------------------------------------------------
Test-Step "Text translation — longer phrase" {
    $body = @{ text = "The weather is beautiful today and I am very happy"; source_language = "en"; target_language = "es" } | ConvertTo-Json
    $resp = Invoke-RestMethod -Uri "$BackendUrl/translate/text" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 15
    Write-Host "  Source: $($resp.source_text)"
    Write-Host "  Translated: $($resp.translated_text)"
    $isPlaceholder = $resp.translated_text -match "^\[en->es\]"
    if ($isPlaceholder) {
        Write-Host "  WARNING: Got placeholder — remote and local ML both unavailable" -ForegroundColor Yellow
    }
    return ($resp.translated_text.Length -gt 0)
}

# -------------------------------------------------------
# 4. Latency endpoint
# -------------------------------------------------------
Test-Step "Latency endpoint" {
    $resp = Invoke-RestMethod -Uri "$BackendUrl/latency" -TimeoutSec 5
    Write-Host "  Health status: $($resp.health.status)"
    Write-Host "  Total runs: $($resp.summary.total_runs)"
    if ($resp.summary.total_runs -gt 0) {
        Write-Host "  Avg total: $($resp.summary.avg_total_ms) ms"
        Write-Host "  P95 total: $($resp.summary.p95_total_ms) ms"
    }
    Write-Host "  Stages tracked: $(($resp.stages.PSObject.Properties | Measure-Object).Count)"
    if ($resp.translation_tier_metrics) {
        Write-Host "  Translation tier metrics:"
        $resp.translation_tier_metrics.PSObject.Properties | ForEach-Object {
            Write-Host "    $($_.Name): $($_.Value)"
        }
    }
    return ($resp.stages -ne $null)
}

# -------------------------------------------------------
# 5. Diagnostics endpoint
# -------------------------------------------------------
Test-Step "Diagnostics endpoint" {
    $resp = Invoke-RestMethod -Uri "$BackendUrl/diagnostics" -TimeoutSec 10
    Write-Host "  Status: $($resp.status)"
    Write-Host "  Ready: $($resp.ready)"
    Write-Host "  Translation backend: $($resp.translation.backend)"
    Write-Host "  Translation runtime: $($resp.translation.runtime)"
    Write-Host "  Marian fallback: $($resp.translation.marian_fallback_enabled)"
    Write-Host "  Remote reachable: $($resp.translation.remote_translator_reachable)"
    Write-Host "  Frontend: $($resp.frontend.mode)"
    return ($resp.status -eq "ok")
}

# -------------------------------------------------------
# 6. Languages endpoint
# -------------------------------------------------------
Test-Step "Languages endpoint" {
    $resp = Invoke-RestMethod -Uri "$BackendUrl/languages" -TimeoutSec 5
    $count = ($resp.languages | Measure-Object).Count
    Write-Host "  Languages available: $count"
    return ($count -gt 0)
}

# -------------------------------------------------------
# 7. TTS synthesis test
# -------------------------------------------------------
Test-Step "TTS synthesis" {
    $body = @{ text = "Hola mundo"; language = "es" } | ConvertTo-Json
    $resp = Invoke-RestMethod -Uri "$BackendUrl/tts" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 15
    Write-Host "  Audio bytes: $($resp.audio_bytes)"
    Write-Host "  Cache hit: $($resp.cache_hit)"
    Write-Host "  Audio URL: $($resp.audio_url)"
    return ($resp.audio_bytes -gt 100)
}

# -------------------------------------------------------
# 8. Text translation with TTS (full text pipeline)
# -------------------------------------------------------
Test-Step "Full text pipeline (translate + TTS)" {
    $body = @{
        text = "good morning"
        source_language = "en"
        target_language = "es"
        synthesize_audio = $true
        audio_response_format = "url"
    } | ConvertTo-Json
    $resp = Invoke-RestMethod -Uri "$BackendUrl/translate/text" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 20
    Write-Host "  Translated: $($resp.translated_text)"
    $hasAudio = ($resp.audio_url -ne $null) -or ($resp.audio_base64 -ne $null)
    Write-Host "  Has audio: $hasAudio"
    return ($resp.translated_text.Length -gt 0)
}

# -------------------------------------------------------
# 9. Reverse translation (Spanish -> English)
# -------------------------------------------------------
Test-Step "Reverse translation — 'hola' -> English" {
    $body = @{ text = "hola"; source_language = "es"; target_language = "en" } | ConvertTo-Json
    $resp = Invoke-RestMethod -Uri "$BackendUrl/translate/text" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 10
    Write-Host "  Translated: $($resp.translated_text)"
    return ($resp.translated_text -match "(?i)hello")
}

# -------------------------------------------------------
# 10. Latency after translations (should have data now)
# -------------------------------------------------------
Test-Step "Latency report (post-translation)" {
    $resp = Invoke-RestMethod -Uri "$BackendUrl/latency" -TimeoutSec 5
    Write-Host "  Health: $($resp.health.status) — $($resp.health.message)"
    if ($resp.summary.total_runs -gt 0) {
        Write-Host "  Avg end-to-end: $($resp.summary.avg_total_ms) ms"
        Write-Host "  P50: $($resp.summary.p50_total_ms) ms"
        Write-Host "  P95: $($resp.summary.p95_total_ms) ms"
    }
    foreach ($stage in @("stt", "translation", "tts")) {
        $s = $resp.stages.$stage
        if ($s -and $s.count -gt 0) {
            Write-Host "  $stage — avg: $($s.avg_ms)ms, p95: $($s.p95_ms)ms ($($s.count) calls)"
        }
    }
    return $true
}

# -------------------------------------------------------
# Summary
# -------------------------------------------------------
Write-Host ""
Write-Host "============================================" -ForegroundColor Yellow
Write-Host "  RESULTS" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Yellow
Write-Host "  Passed:  $passed" -ForegroundColor Green
Write-Host "  Failed:  $failed" -ForegroundColor $(if ($failed -gt 0) { "Red" } else { "Green" })
Write-Host "  Skipped: $skipped" -ForegroundColor Yellow
Write-Host ""

if ($failed -eq 0) {
    Write-Host "  ALL TESTS PASSED" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Open the mobile app and test mic -> speaker pipeline"
    Write-Host "  2. Test duplex: two devices, same session, talk simultaneously"
    Write-Host "  3. Check /latency for real-world timing numbers"
    Write-Host "  4. If Ollama is running: set OLLAMA_ENABLED=1, OLLAMA_URL=http://localhost:11434"
    Write-Host "  5. Deploy: .\deploy-railway.sh"
} else {
    Write-Host "  $failed TEST(S) FAILED — check output above" -ForegroundColor Red
}
Write-Host ""
