param(
    [switch]$Restart,
    [switch]$NoTunnel,
    [switch]$DevFrontend,
    [switch]$SkipBuild,
    [switch]$SkipProductTest,
    [string]$TunnelName = $env:ANAI_TUNNEL_NAME,
    [string]$TunnelHostname = $env:ANAI_TUNNEL_HOSTNAME,
    [string]$TunnelToken = $env:ANAI_TUNNEL_TOKEN,
    [string]$TunnelTokenFile = $env:ANAI_TUNNEL_TOKEN_FILE,
    [string]$TunnelProvider = $env:ANAI_TUNNEL_PROVIDER,
    [string]$LocalTunnelSubdomain = $env:ANAI_LOCALTUNNEL_SUBDOMAIN
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Logs = Join-Path $Root "logs"
$BackendPort = 8000
$FrontendPort = 5173
$MinFreeBytes = 512MB

New-Item -ItemType Directory -Force -Path $Logs | Out-Null

function Import-KeyValueEnvFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or $trimmed -notmatch "=") {
            continue
        }
        $name, $value = $trimmed.Split("=", 2)
        $name = $name.Trim()
        if (-not $name) {
            continue
        }
        [Environment]::SetEnvironmentVariable($name, $value.Trim(), "Process")
    }
}

Import-KeyValueEnvFile -Path (Join-Path $Logs "stable-tunnel.env")

if (-not $TunnelName) { $TunnelName = $env:ANAI_TUNNEL_NAME }
if (-not $TunnelHostname) { $TunnelHostname = $env:ANAI_TUNNEL_HOSTNAME }
if (-not $TunnelToken) { $TunnelToken = $env:ANAI_TUNNEL_TOKEN }
if (-not $TunnelTokenFile) { $TunnelTokenFile = $env:ANAI_TUNNEL_TOKEN_FILE }
if (-not $TunnelProvider) { $TunnelProvider = $env:ANAI_TUNNEL_PROVIDER }
if (-not $LocalTunnelSubdomain) { $LocalTunnelSubdomain = $env:ANAI_LOCALTUNNEL_SUBDOMAIN }

$TunnelProvider = if ($TunnelProvider) { $TunnelProvider.Trim().ToLowerInvariant() } else { "" }
if ($LocalTunnelSubdomain) {
    $LocalTunnelSubdomain = $LocalTunnelSubdomain.Trim()
    $LocalTunnelSubdomain = $LocalTunnelSubdomain -replace "^https?://", ""
    $LocalTunnelSubdomain = $LocalTunnelSubdomain -replace "\.loca\.lt/?$", ""
    $LocalTunnelSubdomain = $LocalTunnelSubdomain -replace "/.*$", ""
}
if (-not $TunnelProvider) {
    $TunnelProvider = if ($LocalTunnelSubdomain) { "localtunnel" } else { "cloudflare" }
}
if ($TunnelProvider -eq "localhost_run") {
    $TunnelProvider = "localhost-run"
}
if ($TunnelProvider -notin @("cloudflare", "localtunnel", "localhost-run")) {
    throw "Unsupported tunnel provider '$TunnelProvider'. Use cloudflare, localtunnel, or localhost-run."
}

if (($TunnelName -or $TunnelToken -or $TunnelTokenFile) -and -not $TunnelHostname) {
    throw "Stable tunnel mode requires TunnelHostname so the launcher can verify the stable phone URL."
}

function Test-PortListening {
    param([int]$Port)
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Stop-PortOwner {
    param([int]$Port)
    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

function Get-CloudflaredPath {
    $command = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $knownPath = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
    if (Test-Path $knownPath) {
        return $knownPath
    }
    return $null
}

# Local desktop use: skip phone tunnel when no tunnel tool is configured.
if (-not $NoTunnel -and $TunnelProvider -eq "cloudflare" -and -not $LocalTunnelSubdomain -and -not (Get-CloudflaredPath)) {
    Write-Host "No cloudflared found - running local-only (phone tunnel skipped)."
    $NoTunnel = $true
}

function Get-TunnelUrl {
    param([string[]]$Paths)
    foreach ($path in $Paths) {
        if (-not (Test-Path $path)) {
            continue
        }
        $match = Select-String -Path $path -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -AllMatches |
            Select-Object -ExpandProperty Matches |
            Select-Object -Last 1
        if ($match) {
            return $match.Value
        }
    }
    return $null
}

function Get-LocalTunnelUrl {
    param([string[]]$Paths)
    foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path)) {
            continue
        }
        $match = Select-String -Path $path -Pattern "your url is:\s*(https://[a-z0-9-]+\.loca\.lt)" -AllMatches |
            Select-Object -ExpandProperty Matches |
            Select-Object -Last 1
        if ($match -and $match.Groups.Count -gt 1) {
            return $match.Groups[1].Value
        }
    }
    return $null
}

function Wait-LocalTunnelPublishedUrl {
    param(
        [string[]]$Paths,
        [int]$Attempts = 30
    )
    for ($attempt = 0; $attempt -lt $Attempts; $attempt += 1) {
        $url = Get-LocalTunnelUrl -Paths $Paths
        if ($url) {
            return $url
        }
        Start-Sleep -Seconds 1
    }
    return $null
}

function Get-LocalhostRunUrl {
    param([string[]]$Paths)
    foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path)) {
            continue
        }
        $match = Select-String -Path $path -Pattern "https://[a-z0-9]+\.lhr\.life" -AllMatches |
            Select-Object -ExpandProperty Matches |
            Select-Object -Last 1
        if ($match) {
            return $match.Value
        }
    }
    return $null
}

function Wait-LocalhostRunPublishedUrl {
    param(
        [string[]]$Paths,
        [int]$Attempts = 35
    )
    for ($attempt = 0; $attempt -lt $Attempts; $attempt += 1) {
        $url = Get-LocalhostRunUrl -Paths $Paths
        if ($url) {
            return $url
        }
        Start-Sleep -Seconds 1
    }
    return $null
}

function Stop-LocalTunnelProcesses {
    param(
        [int]$Port,
        [string]$Subdomain
    )
    $escapedSubdomain = if ($Subdomain) { [regex]::Escape($Subdomain) } else { "" }
    $portPattern = "--port\s+$Port|--port=$Port"
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.ProcessId -ne $PID -and
            $_.CommandLine -and
            (
                $_.CommandLine -match "Start-FixedPhoneTunnel\.ps1" -or
                ($_.CommandLine -match "localtunnel|lt\.js" -and ($_.CommandLine -match $portPattern -or ($escapedSubdomain -and $_.CommandLine -match $escapedSubdomain)))
            )
        } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

function Stop-LocalhostRunProcesses {
    param([int]$Port)
    $portPattern = "80:localhost:$Port|80:127\.0\.0\.1:$Port|Start-LocalhostRunTunnel\.ps1"
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.ProcessId -ne $PID -and
            $_.CommandLine -and
            (
                $_.CommandLine -match "Start-LocalhostRunTunnel\.ps1" -or
                ($_.CommandLine -match "nokey@localhost\.run|localhost\.run" -and $_.CommandLine -match $portPattern)
            )
        } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

function Get-PhoneUrlFromTunnel {
    param(
        [string]$QuickTunnelUrl,
        [string]$Hostname
    )
    if ($Hostname) {
        if ($Hostname.StartsWith("http://") -or $Hostname.StartsWith("https://")) {
            return $Hostname.TrimEnd("/")
        }
        return "https://$Hostname"
    }
    return $QuickTunnelUrl
}

function Get-FreeBytes {
    $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
    return [int64]$disk.FreeSpace
}

function Clear-GeneratedAudio {
    $targets = @(
        (Join-Path $Root "models\tts"),
        (Join-Path $Root "models\uploads")
    )
    foreach ($target in $targets) {
        $resolved = Resolve-Path -LiteralPath $target -ErrorAction SilentlyContinue
        if (-not $resolved) {
            continue
        }
        if (-not $resolved.Path.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean outside project root: $($resolved.Path)"
        }
        Get-ChildItem -LiteralPath $resolved.Path -File -Filter "*.wav" -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
        Get-ChildItem -LiteralPath $resolved.Path -File -Filter "*-partial*" -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
        Get-ChildItem -LiteralPath $resolved.Path -File -Filter "*-live-text*" -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-FrontendBuild {
    if ($SkipBuild) {
        return
    }
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) {
        throw "Missing npm.cmd. Install Node.js or run with -SkipBuild after building frontend/dist."
    }
    Push-Location (Join-Path $Root "frontend")
    try {
        & $npm.Source run build
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend build failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
}

function Wait-HttpReady {
    param(
        [string]$Url,
        [int]$Attempts = 30
    )
    for ($attempt = 0; $attempt -lt $Attempts; $attempt += 1) {
        try {
            $response = Invoke-RestMethod -Uri $Url -TimeoutSec 3
            if ($null -ne $response) {
                return $response
            }
        } catch {
            Start-Sleep -Milliseconds 750
        }
    }
    throw "Timed out waiting for $Url"
}

function Invoke-ProductWarmup {
    try {
        $warmTranslate = @{
            text = "Bonjou kijan ou ye"
            source_language = "ht"
            target_language = "ru"
            synthesize_audio = $false
        } | ConvertTo-Json
        Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/translate/text" -Method Post -ContentType "application/json" -Body $warmTranslate -TimeoutSec 90 | Out-Null

        $warmVoice = @{
            text = "Hello"
            language = "ru"
            response_format = "base64"
        } | ConvertTo-Json
        Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/tts" -Method Post -ContentType "application/json" -Body $warmVoice -TimeoutSec 60 | Out-Null
    } catch {
        "Warm-up skipped: $($_.Exception.Message)" | Out-File -FilePath (Join-Path $Logs "warmup.err.log") -Append
    }
}

function Wait-VoiceWarmupComplete {
    param([int]$Attempts = 180)
    for ($attempt = 0; $attempt -lt $Attempts; $attempt += 1) {
        try {
            $diagnostics = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/diagnostics" -TimeoutSec 5
            $voiceWarmup = $diagnostics.voice_warmup
            if ($voiceWarmup -and $voiceWarmup.status -eq "complete") {
                return $voiceWarmup
            }
        } catch {
            Start-Sleep -Seconds 1
            continue
        }
        Start-Sleep -Seconds 1
    }
    Write-Warning "Voice warmup did not complete before timeout; continuing with product smoke test."
    return $null
}

function Wait-TunnelReady {
    param(
        [string]$Url,
        [int]$Attempts = 24
    )
    $uri = [System.Uri]$Url
    for ($attempt = 0; $attempt -lt $Attempts; $attempt += 1) {
        try {
            Resolve-DnsName $uri.Host -ErrorAction Stop | Out-Null
            $healthUrl = "$($Url.TrimEnd('/'))/health"
            $response = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 8
            if ($response.ready -eq $true -or $response.status -eq "ok") {
                return $true
            }
        } catch {
            ipconfig /flushdns | Out-Null
            Start-Sleep -Seconds 3
        }
    }
    return $false
}

function Invoke-ProductSmokeTest {
    param([string]$Url)
    if ($SkipProductTest) {
        return "skipped"
    }
    $python = Join-Path $Root "venv\Scripts\python.exe"
    $script = Join-Path $Root "scripts\product_smoke_test.py"
    if (-not (Test-Path $python)) {
        throw "Missing venv Python at $python"
    }
    if (-not (Test-Path $script)) {
        throw "Missing product smoke test at $script"
    }
    $cases = @(
        @{ source = "ht"; target = "ru"; phrase = "Mesi anpil"; expected = $null },
        @{ source = "en"; target = "fr"; phrase = "Hello"; expected = "Bonjour.|Bonjour" }
    )
    $outputs = @()
    foreach ($case in $cases) {
        $testArgs = @(
            $script,
            "--base-url", $Url,
            "--timeout", "70",
            "--source", $case.source,
            "--target", $case.target,
            "--phrase", $case.phrase
        )
        if ($case.expected) {
            $testArgs += @("--expected", $case.expected)
        }
        if (-not $DevFrontend) {
            $testArgs += "--require-embedded"
        }
        $testArgs += "--no-doh"
        $lastOutput = ""
        for ($attempt = 0; $attempt -lt 5; $attempt += 1) {
            $lastOutput = & $python @testArgs
            if ($LASTEXITCODE -eq 0) {
                $outputs += $lastOutput
                break
            }
            Start-Sleep -Seconds 5
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Product smoke test failed for $($case.source)->$($case.target): $lastOutput"
        }
    }
    return "[" + ($outputs -join ",") + "]"
}

if ($Restart) {
    Stop-PortOwner -Port $BackendPort
    Stop-PortOwner -Port $FrontendPort
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    if ($LocalTunnelSubdomain -or $TunnelProvider -eq "localtunnel") {
        Stop-LocalTunnelProcesses -Port $BackendPort -Subdomain $LocalTunnelSubdomain
        Stop-LocalTunnelProcesses -Port $FrontendPort -Subdomain $LocalTunnelSubdomain
    }
    if ($TunnelProvider -eq "localhost-run") {
        Stop-LocalhostRunProcesses -Port $BackendPort
        Stop-LocalhostRunProcesses -Port $FrontendPort
    }
    Start-Sleep -Seconds 1
}

$backendOut = Join-Path $Logs "backend.out.log"
$backendErr = Join-Path $Logs "backend.err.log"
$frontendOut = Join-Path $Logs "frontend.out.log"
$frontendErr = Join-Path $Logs "frontend.err.log"
$tunnelOut = Join-Path $Logs "tunnel.out.log"
$tunnelErr = Join-Path $Logs "tunnel.err.log"
$fixedTunnelOut = Join-Path $Logs "fixed-phone-tunnel.out.log"
$fixedTunnelErr = Join-Path $Logs "fixed-phone-tunnel.err.log"
$localhostRunOut = Join-Path $Logs "localhost-run-tunnel.out.log"
$localhostRunErr = Join-Path $Logs "localhost-run-tunnel.err.log"
$currentPhoneUrlPath = Join-Path $Logs "current-phone-url.txt"
$productSmokePath = Join-Path $Logs "product-smoke-last.json"

Clear-GeneratedAudio
$freeBytes = Get-FreeBytes
if ($freeBytes -lt $MinFreeBytes) {
    Write-Warning ("C: drive has only {0:N0} MB free. TTS needs free space for live WAV chunks." -f ($freeBytes / 1MB))
}

if (-not $DevFrontend) {
    Invoke-FrontendBuild
}

if (Test-PortListening -Port $BackendPort) {
    try {
        $diagnostics = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/diagnostics" -TimeoutSec 3
        $currentMode = $diagnostics.frontend.mode
        if (-not $DevFrontend -and $currentMode -ne "embedded_dist") {
            Stop-PortOwner -Port $BackendPort
            Start-Sleep -Seconds 1
        } elseif ($DevFrontend -and $currentMode -eq "embedded_dist") {
            Stop-PortOwner -Port $BackendPort
            Start-Sleep -Seconds 1
        }
    } catch {
        Stop-PortOwner -Port $BackendPort
        Start-Sleep -Seconds 1
    }
}

function Ensure-NeuralTtsDeps {
    param([string]$PythonExe)
    $check = & $PythonExe -c "from tts.tts_readiness import is_neural_tts_ready; import sys; sys.exit(0 if is_neural_tts_ready() else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Neural TTS ready (edge-tts + ffmpeg)."
        return
    }
    Write-Host "Installing neural TTS dependency (edge-tts) for lifelike voice..."
    & $PythonExe -m pip install "edge-tts==7.2.8" -q
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Could not install edge-tts. Voice will sound robotic until you run: pip install edge-tts"
    }
}

if (-not (Test-PortListening -Port $BackendPort)) {
    $python = Join-Path $Root "venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        throw "Missing venv Python at $python"
    }
    Ensure-NeuralTtsDeps -PythonExe $python
    $env:FRONTEND_URL = if ($DevFrontend) { "http://127.0.0.1:$FrontendPort" } else { "http://127.0.0.1:$BackendPort" }
    $env:SERVE_FRONTEND_DIST = if ($DevFrontend) { "0" } else { "1" }
    $env:FRONTEND_DIST_DIR = "frontend/dist"
    $extraOriginRegex = ""
    if ($TunnelHostname) {
        $stableHost = $TunnelHostname
        if ($stableHost.StartsWith("http://") -or $stableHost.StartsWith("https://")) {
            $stableHost = ([Uri]$stableHost).Host
        }
        $extraOriginRegex += "|https://$([regex]::Escape($stableHost))"
    }
    if ($LocalTunnelSubdomain) {
        $localTunnelHost = "$LocalTunnelSubdomain.loca.lt"
        $extraOriginRegex += "|https://$([regex]::Escape($localTunnelHost))"
    }
    if ($TunnelProvider -eq "localhost-run") {
        $extraOriginRegex += "|https://.*\.lhr\.life"
    }
    $env:ALLOWED_ORIGIN_REGEX = "https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(:\d+)?|https://.*\.trycloudflare\.com$extraOriginRegex"
    $env:NEAR_ZERO_LATENCY_MODE = "true"
    $env:PARTIAL_TTS_MIN_WORDS = "1"
    $env:PARTIAL_TTS_MIN_INTERVAL = "0.35"
    $env:PARTIAL_TRANSLATION_MIN_WORDS = "1"
    $env:PARTIAL_STT_MIN_BYTES = "1200"
    $env:PARTIAL_STT_INTERVAL_MS = "100"
    $env:CLIENT_VAD_MODE = "true"
    $env:CLIENT_VAD_THRESHOLD = "0.035"
    $env:VAD_RECENT_CHUNKS = "2"
    $env:VAD_SILENT_CHECKS = "2"
    $env:VAD_FORCE_FINAL_SECONDS = "0.65"
    $env:SPEECH_MERGE_MS = "180"
    $env:PRELOAD_MODELS = "false"
    $env:SKIP_TRANSLATION_WARMUP = "true"
    $env:OLLAMA_ENABLED = "false"
    if (-not $env:REQUESTS_PER_MINUTE) {
        $env:REQUESTS_PER_MINUTE = "240"
    }
    if (-not $env:QUOTA_REQUESTS_PER_HOUR) {
        $env:QUOTA_REQUESTS_PER_HOUR = "5000"
    }
    $env:PREFER_EDGE_TTS = "true"
    $env:TTS_EDGE_SSML_PAUSES = "0"
    $env:TTS_SOFTENING_ENABLED = "true"
    $env:TTS_VOICE_PROFILE = "neural"
    $env:TTS_NEURAL_MINIMAL_PROCESSING = "true"
    $env:TTS_CHUNK_CHARS = "48"
    $env:TTS_FIRST_CHUNK_CHARS = "28"
    $env:TTS_NATURAL_SPEED = "1.0"
    $env:TTS_NATURAL_PITCH_SHIFT = "0"
    $env:TTS_NATURAL_VOICE = "true"
    $env:PARTIAL_TTS_MODE = "1"
    $env:TTS_PROSODY_WARMTH = "false"
    if (-not $env:AILANG_ENHANCEMENTS_ENABLED) {
        $env:AILANG_ENHANCEMENTS_ENABLED = "false"
    }
    Start-Process -FilePath $python -ArgumentList @("-m", "uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "$BackendPort") -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr | Out-Null
}

if ($DevFrontend -and -not (Test-PortListening -Port $FrontendPort)) {
    $viteCmd = Join-Path $Root "frontend\node_modules\.bin\vite.cmd"
    if (-not (Test-Path $viteCmd)) {
        throw "Missing Vite command at $viteCmd. Run npm install in the frontend folder first."
    }
    Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "`"$viteCmd`" --host 0.0.0.0") -WorkingDirectory (Join-Path $Root "frontend") -WindowStyle Hidden -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr | Out-Null
}

Start-Sleep -Seconds 3

$health = Wait-HttpReady -Url "http://127.0.0.1:$BackendPort/health" -Attempts 40
if (-not $SkipProductTest) {
    Invoke-ProductWarmup
    Wait-VoiceWarmupComplete | Out-Null
} else {
    Wait-VoiceWarmupComplete -Attempts 25 | Out-Null
}

$tunnelUrl = $null
if (-not $NoTunnel) {
    Remove-Item -LiteralPath $tunnelOut, $tunnelErr, $fixedTunnelOut, $fixedTunnelErr, $localhostRunOut, $localhostRunErr -Force -ErrorAction SilentlyContinue
    $tunnelPort = if ($DevFrontend) { $FrontendPort } else { $BackendPort }
    if ($TunnelProvider -eq "localhost-run") {
        $localhostRunScript = Join-Path $Root "Start-LocalhostRunTunnel.ps1"
        if (-not (Test-Path -LiteralPath $localhostRunScript)) {
            throw "Missing localhost.run tunnel runner at $localhostRunScript."
        }
        Stop-LocalhostRunProcesses -Port $tunnelPort
        $powerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
        Start-Process -FilePath $powerShell -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", "`"$localhostRunScript`"",
            "-Port", "$tunnelPort"
        ) -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $tunnelOut -RedirectStandardError $tunnelErr | Out-Null
        $tunnelUrl = Wait-LocalhostRunPublishedUrl -Paths @($localhostRunOut, $tunnelOut) -Attempts 45
        if (-not $tunnelUrl) {
            throw "localhost.run did not publish a phone URL."
        }
        Start-Sleep -Seconds 10
        $latestLocalhostRunUrl = Get-LocalhostRunUrl -Paths @($localhostRunOut, $tunnelOut)
        if ($latestLocalhostRunUrl) {
            $tunnelUrl = $latestLocalhostRunUrl
        }
    } elseif ($TunnelProvider -eq "localtunnel") {
        if (-not $LocalTunnelSubdomain) {
            throw "localtunnel provider requires ANAI_LOCALTUNNEL_SUBDOMAIN."
        }
        $fixedTunnelScript = Join-Path $Root "Start-FixedPhoneTunnel.ps1"
        if (-not (Test-Path -LiteralPath $fixedTunnelScript)) {
            throw "Missing fixed phone tunnel runner at $fixedTunnelScript."
        }
        $powerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
        $desiredLocalTunnelUrl = "https://$LocalTunnelSubdomain.loca.lt"
        for ($attempt = 0; $attempt -lt 4; $attempt += 1) {
            Stop-LocalTunnelProcesses -Port $tunnelPort -Subdomain $LocalTunnelSubdomain
            Remove-Item -LiteralPath $fixedTunnelOut, $fixedTunnelErr -Force -ErrorAction SilentlyContinue
            Start-Process -FilePath $powerShell -ArgumentList @(
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", "`"$fixedTunnelScript`"",
                "-Subdomain", "`"$LocalTunnelSubdomain`"",
                "-Port", "$tunnelPort"
            ) -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $tunnelOut -RedirectStandardError $tunnelErr | Out-Null
            $publishedLocalTunnelUrl = Wait-LocalTunnelPublishedUrl -Paths @($fixedTunnelOut, $tunnelOut) -Attempts 35
            if (-not $publishedLocalTunnelUrl) {
                Stop-LocalTunnelProcesses -Port $tunnelPort -Subdomain $LocalTunnelSubdomain
                Start-Sleep -Seconds 5
                continue
            }
            $tunnelUrl = $publishedLocalTunnelUrl
            if ($publishedLocalTunnelUrl -eq $desiredLocalTunnelUrl) {
                break
            }
            Write-Output "Phone tunnel requested $desiredLocalTunnelUrl but localtunnel returned $publishedLocalTunnelUrl; retrying fixed subdomain."
            Stop-LocalTunnelProcesses -Port $tunnelPort -Subdomain $LocalTunnelSubdomain
            Start-Sleep -Seconds 8
        }
        if (-not $tunnelUrl) {
            throw "localtunnel did not publish a phone URL."
        }
        if ($tunnelUrl -ne $desiredLocalTunnelUrl) {
            throw "localtunnel could not claim the fixed phone URL $desiredLocalTunnelUrl; last published URL was $tunnelUrl."
        }
    } else {
        $cloudflared = Get-CloudflaredPath
        if ($cloudflared) {
            if ($TunnelToken -or $TunnelTokenFile) {
                $tunnelArgs = @("tunnel", "run", "--url", "http://127.0.0.1:$tunnelPort")
                if ($TunnelToken) {
                    $tunnelArgs += @("--token", $TunnelToken)
                }
                if ($TunnelTokenFile) {
                    $tunnelArgs += @("--token-file", $TunnelTokenFile)
                }
                Start-Process -FilePath $cloudflared -ArgumentList $tunnelArgs -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $tunnelOut -RedirectStandardError $tunnelErr | Out-Null
                $tunnelUrl = Get-PhoneUrlFromTunnel -QuickTunnelUrl "" -Hostname $TunnelHostname
            } elseif ($TunnelName) {
                $tunnelArgs = @("tunnel", "run", "--url", "http://127.0.0.1:$tunnelPort")
                $tunnelArgs += $TunnelName
                Start-Process -FilePath $cloudflared -ArgumentList $tunnelArgs -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $tunnelOut -RedirectStandardError $tunnelErr | Out-Null
                $tunnelUrl = Get-PhoneUrlFromTunnel -QuickTunnelUrl "" -Hostname $TunnelHostname
            } else {
                Start-Process -FilePath $cloudflared -ArgumentList @("tunnel", "--url", "http://127.0.0.1:$tunnelPort") -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $tunnelOut -RedirectStandardError $tunnelErr | Out-Null
                for ($attempt = 0; $attempt -lt 24; $attempt += 1) {
                    Start-Sleep -Milliseconds 500
                    $tunnelUrl = Get-TunnelUrl -Paths @($tunnelErr, $tunnelOut)
                    if ($tunnelUrl) {
                        break
                    }
                }
            }
        } else {
            throw "cloudflared was not found; cannot create a phone tunnel."
        }
    }
}

Write-Output ""
Write-Output "Anai Translator is starting."
Write-Output "Mode:       $(if ($DevFrontend) { 'dev frontend proxy' } else { 'embedded production frontend' })"
Write-Output "Local app:  http://127.0.0.1:$(if ($DevFrontend) { $FrontendPort } else { $BackendPort })/"
Write-Output "Health:     http://127.0.0.1:$BackendPort/health"
Write-Output "Ready:      $($health.ready)"
if ($tunnelUrl) {
    Write-Output "Phone app candidate:  $tunnelUrl"
    if (Wait-TunnelReady -Url $tunnelUrl -Attempts 30) {
        Write-Output "Phone test: tunnel DNS and health resolved"
    } else {
        Write-Output "Phone test: failed normal DNS/health check"
        throw "Tunnel URL did not become reachable through normal DNS: $tunnelUrl"
    }
    try {
        $productResult = Invoke-ProductSmokeTest -Url $tunnelUrl
        Set-Content -LiteralPath $productSmokePath -Value $productResult
        Set-Content -LiteralPath $currentPhoneUrlPath -Value $tunnelUrl -Encoding ascii
        Write-Output "Phone app:  $tunnelUrl"
        Write-Output "Audio test: $productResult"
    } catch {
        Write-Output "Audio test: failed"
        throw
    }
} elseif (-not $NoTunnel) {
    Write-Output "Phone app:  cloudflared URL not ready yet; check $tunnelErr"
    throw "cloudflared did not publish a tunnel URL."
}
Write-Output ""
Write-Output "Logs:"
Write-Output "  Backend:  $backendErr"
Write-Output "  Frontend: $frontendErr"
Write-Output "  Tunnel:   $tunnelErr"
