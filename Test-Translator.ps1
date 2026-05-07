param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Username = "",
    [string]$Password = "",
    [int]$TimeoutSec = 30
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root "venv\Scripts\python.exe"
$Failures = @()
$BaseUrl = $BaseUrl.TrimEnd("/")
$AccessToken = ""

function Add-Pass {
    param([string]$Name, [string]$Detail = "")
    if ($Detail) {
        Write-Output "PASS $Name - $Detail"
    } else {
        Write-Output "PASS $Name"
    }
}

function Add-Fail {
    param([string]$Name, [string]$Detail)
    $script:Failures += "$Name - $Detail"
    Write-Output "FAIL $Name - $Detail"
}

function Invoke-SmokeCheck {
    param(
        [string]$Name,
        [scriptblock]$Check
    )
    try {
        $detail = & $Check
        Add-Pass -Name $Name -Detail $detail
    } catch {
        Add-Fail -Name $Name -Detail $_.Exception.Message
    }
}

function Get-WebSocketUrl {
    param([string]$Url)
    if ($Url.StartsWith("https://")) {
        $ws = "wss://$($Url.Substring(8))/ws/audio"
        if ($AccessToken) {
            return "$ws`?access_token=$AccessToken"
        }
        return $ws
    }
    if ($Url.StartsWith("http://")) {
        $ws = "ws://$($Url.Substring(7))/ws/audio"
        if ($AccessToken) {
            return "$ws`?access_token=$AccessToken"
        }
        return $ws
    }
    throw "Unsupported BaseUrl scheme: $Url"
}

function Get-FrontendScriptPaths {
    param([string]$Html)
    $matches = [regex]::Matches($Html, '<script[^>]+src="([^"]+)"')
    return @($matches | ForEach-Object { $_.Groups[1].Value })
}

function Get-AbsoluteAppUrl {
    param([string]$PathOrUrl)
    if ($PathOrUrl.StartsWith("http://") -or $PathOrUrl.StartsWith("https://")) {
        return $PathOrUrl
    }
    if ($PathOrUrl.StartsWith("/")) {
        return "$BaseUrl$PathOrUrl"
    }
    return "$BaseUrl/$PathOrUrl"
}

Write-Output ""
Write-Output "Universal Translator smoke test"
Write-Output "Target: $BaseUrl"
Write-Output ""

if ($Username -and $Password) {
    $loginBody = @{
        username = $Username
        password = $Password
    } | ConvertTo-Json
    $login = Invoke-RestMethod -Uri "$BaseUrl/auth/login" -Method Post -ContentType "application/json" -Body $loginBody -TimeoutSec $TimeoutSec
    $AccessToken = $login.access_token
}

Invoke-SmokeCheck "Backend health" {
    $health = Invoke-RestMethod -Uri "$BaseUrl/health" -TimeoutSec $TimeoutSec
    if ($health.status -ne "ok") {
        throw "Expected status ok, got $($health.status)"
    }
    "status ok"
}

Invoke-SmokeCheck "Diagnostics" {
    $diagnostics = Invoke-RestMethod -Uri "$BaseUrl/diagnostics" -TimeoutSec $TimeoutSec
    if (-not $diagnostics.ready) {
        throw "Backend is not ready"
    }
    if (-not $diagnostics.frontend.reachable) {
        throw "Frontend proxy is not reachable"
    }
    "ready, frontend $($diagnostics.frontend.status_code)"
}

Invoke-SmokeCheck "Frontend app shell" {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/" -TimeoutSec $TimeoutSec
    $scriptPaths = Get-FrontendScriptPaths -Html $response.Content
    if (-not $scriptPaths.Count) {
        throw "App shell does not reference a frontend script"
    }
    "index loaded, $($scriptPaths[0])"
}

Invoke-SmokeCheck "Frontend module" {
    $index = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/" -TimeoutSec $TimeoutSec
    $scriptPaths = Get-FrontendScriptPaths -Html $index.Content
    foreach ($scriptPath in $scriptPaths) {
        $scriptUrl = Get-AbsoluteAppUrl -PathOrUrl $scriptPath
        $response = Invoke-WebRequest -UseBasicParsing -Uri $scriptUrl -TimeoutSec $TimeoutSec
        if ($response.Content -match "Run Self Test|Self Test|Self-test|runSelfTest") {
            return "self-test UI present in $scriptPath"
        }
    }
    throw "Current frontend bundle is missing browser self-test UI"
}

Invoke-SmokeCheck "PWA assets" {
    $manifest = Invoke-RestMethod -Uri "$BaseUrl/manifest.json" -TimeoutSec $TimeoutSec
    if ($manifest.name -ne "Universal Translator") {
        throw "Manifest app name is not Universal Translator"
    }
    if ($manifest.display -ne "standalone") {
        throw "Manifest display is not standalone"
    }
    if ($manifest.background_color -ne "#0b1120" -or $manifest.theme_color -ne "#2563eb") {
        throw "Manifest colors are not the installable app colors"
    }
    if (-not ($manifest.icons | Where-Object { $_.src -eq "/icons/icon-512.png" -and $_.sizes -eq "512x512" })) {
        throw "Manifest is missing the 512px app icon"
    }
    $serviceWorker = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/sw.js" -TimeoutSec $TimeoutSec
    if ($serviceWorker.Content -notmatch "universal-translator-shell-v") {
        throw "Service worker is not using the Universal Translator cache"
    }
    if ($serviceWorker.Content -notmatch "cacheDiscoveredShellAssets" -or $serviceWorker.Content -notmatch "/offline.html") {
        throw "Service worker is missing offline shell caching"
    }
    "manifest and service worker ok"
}

Invoke-SmokeCheck "Text translation" {
    $body = @{
        text = "hello world"
        source_language = "en"
        target_language = "es"
        synthesize_audio = $false
    } | ConvertTo-Json
    $headers = @{}
    if ($AccessToken) {
        $headers.Authorization = "Bearer $AccessToken"
    }
    $result = Invoke-RestMethod -Uri "$BaseUrl/translate/text" -Method Post -ContentType "application/json" -Headers $headers -Body $body -TimeoutSec ([Math]::Max($TimeoutSec, 180))
    if (-not $result.translated_text) {
        throw "Translated text was empty"
    }
    $result.translated_text
}

Invoke-SmokeCheck "Audio WebSocket" {
    if (-not (Test-Path $Python)) {
        throw "Missing venv Python at $Python"
    }
    $wsUrl = Get-WebSocketUrl -Url $BaseUrl
    $wsScript = @'
import asyncio
import json
import sys
import websockets

async def main():
    url = sys.argv[1]
    async with websockets.connect(url, open_timeout=10) as ws:
        ready = json.loads(await ws.recv())
        if ready.get("type") != "ready":
            raise RuntimeError(f"Expected ready, got {ready}")
        await ws.send(json.dumps({"type": "ping"}))
        pong = json.loads(await ws.recv())
        if pong.get("type") != "pong":
            raise RuntimeError(f"Expected pong, got {pong}")
        print("pong")

asyncio.run(main())
'@
    $output = $wsScript | & $Python - $wsUrl
    if (($output -join "`n") -notmatch "pong") {
        throw "WebSocket did not return pong"
    }
    "pong"
}

Write-Output ""
if ($Failures.Count) {
    Write-Output "Smoke test failed:"
    foreach ($failure in $Failures) {
        Write-Output "  $failure"
    }
    exit 1
}

Write-Output "Smoke test passed."
