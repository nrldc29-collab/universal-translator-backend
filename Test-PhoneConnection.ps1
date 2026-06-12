# Quick diagnostic for Expo Go "Could not connect to development server"
param(
    [string]$LanIp = "",
    [int]$BackendPort = 8000,
    [int]$ExpoPort = 8082
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$MobileConnectPath = Join-Path $Root "logs\mobile-connect.json"
if (Test-Path -LiteralPath $MobileConnectPath) {
    try {
        $mobileConnect = Get-Content -LiteralPath $MobileConnectPath -Raw | ConvertFrom-Json
        if ($mobileConnect.expo_port -and -not $PSBoundParameters.ContainsKey("ExpoPort")) {
            $ExpoPort = [int]$mobileConnect.expo_port
        }
        if ($mobileConnect.lan_ip -and -not $PSBoundParameters.ContainsKey("LanIp")) {
            $LanIp = [string]$mobileConnect.lan_ip
        }
    } catch {
        # Fall back to defaults.
    }
}

function Get-LanIpLocal {
    $candidate = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -ne "127.0.0.1" -and
            $_.IPAddress -notmatch "^169\.254\." -and
            $_.InterfaceAlias -notmatch "vEthernet|Loopback|Docker|WSL"
        } |
        Sort-Object @{ Expression = { if ($_.InterfaceAlias -match "Wi-Fi|Wireless") { 0 } else { 1 } } } |
        Select-Object -First 1
    if ($candidate) { return $candidate.IPAddress }
    return $null
}

if (-not $LanIp) { $LanIp = Get-LanIpLocal }
if (-not $LanIp) { throw "Could not detect LAN IP." }

Write-Host ""
Write-Host "=== Anai phone connection test ===" -ForegroundColor Cyan
Write-Host "LAN IP: $LanIp"
Write-Host ""

$checks = @()

$profile = Get-NetConnectionProfile -ErrorAction SilentlyContinue | Select-Object -First 1
$checks += [PSCustomObject]@{
    Check = "Wi-Fi network profile"
    Ok = ($profile.NetworkCategory -eq "Private")
    Detail = if ($profile) { "$($profile.Name) = $($profile.NetworkCategory)" } else { "unknown" }
}

$fwMetroName = "Anai Translator Expo Metro TCP $ExpoPort"
$fwMetro = netsh advfirewall firewall show rule name="$fwMetroName" 2>$null
$fwMetroOk = ($LASTEXITCODE -eq 0 -and $fwMetro -match "Enabled:\s+Yes")
if (-not $fwMetroOk) {
    $fwLegacy = netsh advfirewall firewall show rule name="Anai Translator Expo Metro" 2>$null
    $fwMetroOk = ($LASTEXITCODE -eq 0 -and $fwLegacy -match "Enabled:\s+Yes" -and $fwLegacy -match "LocalPort:\s+$ExpoPort")
}
$fwNode = netsh advfirewall firewall show rule name="Anai Translator Node.js (Metro)" 2>$null
$fwNodeOk = ($LASTEXITCODE -eq 0 -and $fwNode -match "Enabled:\s+Yes")
if (-not $fwMetroOk -and $fwNodeOk) {
    $fwMetroOk = $true
    $fwMetroName = "Anai Translator Node.js (Metro) program rule"
}
$checks += [PSCustomObject]@{
    Check = "Firewall TCP $ExpoPort"
    Ok = $fwMetroOk
    Detail = $fwMetroName
}

if ($ExpoPort -ne 8081) {
    $fw8081Name = "Anai Translator Expo Metro TCP 8081"
    $fw8081 = netsh advfirewall firewall show rule name="$fw8081Name" 2>$null
    $fw8081Ok = ($LASTEXITCODE -eq 0 -and $fw8081 -match "Enabled:\s+Yes")
    $checks += [PSCustomObject]@{
        Check = "Firewall TCP 8081 (stale Expo cache)"
        Ok = $fw8081Ok
        Detail = if ($fw8081Ok) { $fw8081Name } else { "missing - stale Expo Go may fail on 8081" }
    }
}

$fwBackendName = "Anai Translator Backend TCP $BackendPort"
$fwBackend = netsh advfirewall firewall show rule name="$fwBackendName" 2>$null
$checks += [PSCustomObject]@{
    Check = "Firewall TCP $BackendPort"
    Ok = ($LASTEXITCODE -eq 0 -and $fwBackend -match "Enabled:\s+Yes")
    Detail = $fwBackendName
}

$fwHttpsName = "Anai Translator Backend HTTPS TCP 8443"
$fwHttps = netsh advfirewall firewall show rule name="$fwHttpsName" 2>$null
$checks += [PSCustomObject]@{
    Check = "Firewall TCP 8443 (Safari HTTPS)"
    Ok = ($LASTEXITCODE -eq 0 -and $fwHttps -match "Enabled:\s+Yes")
    Detail = $fwHttpsName
}

$fwNode = netsh advfirewall firewall show rule name="Anai Translator Node.js (Metro)" 2>$null
$checks += [PSCustomObject]@{
    Check = "Firewall Node.js (Metro)"
    Ok = ($LASTEXITCODE -eq 0 -and $fwNode -match "Enabled:\s+Yes")
    Detail = "Anai Translator Node.js (Metro) rule"
}

try {
    $status = Invoke-WebRequest "http://${LanIp}:$ExpoPort/status" -UseBasicParsing -TimeoutSec 15
    $checks += [PSCustomObject]@{ Check = "Metro /status (LAN)"; Ok = ($status.StatusCode -eq 200); Detail = "HTTP $($status.StatusCode) on port $ExpoPort" }
} catch {
    $checks += [PSCustomObject]@{ Check = "Metro /status (LAN)"; Ok = $false; Detail = $_.Exception.Message }
}

if ($ExpoPort -ne 8081) {
    try {
        $proxyStatus = Invoke-WebRequest "http://${LanIp}:8081/status" -UseBasicParsing -TimeoutSec 10
        $proxyBuild = (Invoke-WebRequest "http://${LanIp}:8081/.anai/build-id" -UseBasicParsing -TimeoutSec 10).Content.Trim()
        $checks += [PSCustomObject]@{
            Check = "Metro 8081 proxy (stale Expo cache)"
            Ok = ($proxyStatus.StatusCode -eq 200 -and $proxyBuild)
            Detail = if ($proxyBuild) { "forwards to $ExpoPort, build=$proxyBuild" } else { "HTTP $($proxyStatus.StatusCode) on 8081" }
        }
    } catch {
        $checks += [PSCustomObject]@{
            Check = "Metro 8081 proxy (stale Expo cache)"
            Ok = $false
            Detail = $_.Exception.Message
        }
    }
}

$expectedBuild = ""
$mobileBuildJs = Join-Path $Root "translator-mobile\constants\mobileBuild.js"
if (Test-Path -LiteralPath $mobileBuildJs) {
    $buildJsText = Get-Content -LiteralPath $mobileBuildJs -Raw
    if ($buildJsText -match 'MOBILE_BUILD_ID\s*=\s*"([^"]+)"') {
        $expectedBuild = $Matches[1]
    }
}
try {
    $buildId = (Invoke-WebRequest "http://${LanIp}:$ExpoPort/.anai/build-id" -UseBasicParsing -TimeoutSec 15).Content.Trim()
    $buildOk = [bool]$buildId
    if ($buildOk -and $expectedBuild -and $buildId -ne $expectedBuild) {
        $buildOk = $false
    }
    $checks += [PSCustomObject]@{
        Check = "Metro build ID"
        Ok = $buildOk
        Detail = if ($buildId) { $buildId } else { "missing" }
    }
} catch {
    $checks += [PSCustomObject]@{ Check = "Metro build ID"; Ok = $false; Detail = $_.Exception.Message }
}

try {
    $manifestResponse = Invoke-WebRequest "http://${LanIp}:$ExpoPort" -Headers @{ "expo-platform" = "ios"; "accept" = "application/expo+json,application/json" } -UseBasicParsing -TimeoutSec 10
    $manifestText = $manifestResponse.Content
    if ($manifestText -is [byte[]]) {
        $manifestText = [System.Text.Encoding]::UTF8.GetString($manifestText)
    }
    $hostUri = ""
    if ($manifestText -match '"debuggerHost"\s*:\s*"([^"]+)"') {
        $hostUri = $Matches[1]
    } elseif ($manifestText -match '"hostUri"\s*:\s*"([^"]+)"') {
        $hostUri = $Matches[1]
    }
    $manifestOk = ($hostUri -match [regex]::Escape($LanIp)) -and ($hostUri -notmatch "127\.0\.0\.1|localhost")
    $manifestPortOk = $true
    $manifestPortDetail = ""
    if ($hostUri -match ":(\d+)$") {
        $manifestPort = [int]$Matches[1]
        $manifestPortOk = ($manifestPort -eq $ExpoPort)
        if (-not $manifestPortOk) {
            $manifestPortDetail = "port $manifestPort (expected $ExpoPort - stale 8081 cache?)"
        }
    }
    $checks += [PSCustomObject]@{
        Check = "Expo manifest hostUri"
        Ok = ($manifestOk -and $manifestPortOk)
        Detail = if ($hostUri) {
            if ($manifestPortDetail) { "$hostUri · $manifestPortDetail" } else { $hostUri }
        } else { "missing hostUri" }
    }
} catch {
    $checks += [PSCustomObject]@{ Check = "Expo manifest hostUri"; Ok = $false; Detail = $_.Exception.Message }
}

$localhostHealthOk = $false
$healthOk = $false
try {
    $localhostHealth = Invoke-RestMethod "http://127.0.0.1:$BackendPort/health" -TimeoutSec 6
    $localhostHealthOk = ($localhostHealth.status -eq "ok") -and ($localhostHealth.ready -ne $false)
} catch {
    $localhostHealthOk = $false
}
try {
    $health = Invoke-RestMethod "http://${LanIp}:$BackendPort/health" -TimeoutSec 8
    $healthOk = ($health.status -eq "ok") -and ($health.ready -ne $false)
    $checks += [PSCustomObject]@{
        Check = "Backend /health (LAN)"
        Ok = $healthOk
        Detail = if ($health.ready -eq $false) { "warming (ready=false)" } else { $health.status }
    }
} catch {
    $healthOk = $false
    $checks += [PSCustomObject]@{ Check = "Backend /health (LAN)"; Ok = $false; Detail = $_.Exception.Message }
}
$bindOk = $healthOk -or (-not $localhostHealthOk)
$bindDetail = "LAN reachable"
if ($localhostHealthOk -and -not $healthOk) {
    $bindOk = $false
    $bindDetail = "127.0.0.1 only - restart with Start-Translator.ps1 (needs 0.0.0.0 bind)"
}
$checks += [PSCustomObject]@{
    Check = "Backend LAN bind (not localhost-only)"
    Ok = $bindOk
    Detail = $bindDetail
}

$tunnelUrl = ""
try {
    $mobileInfo = Invoke-RestMethod "http://${LanIp}:$BackendPort/mobile/info" -TimeoutSec 8
    $infoBuild = [string]$mobileInfo.build_id
    $infoOk = ($mobileInfo.server_ok -eq $true)
    if ($infoOk -and $expectedBuild -and $infoBuild -and $infoBuild -ne $expectedBuild) {
        $infoOk = $false
    }
    $tunnelNote = if ($mobileInfo.tunnel_backend_url) { "tunnel OK" } else { "no tunnel" }
    $checks += [PSCustomObject]@{
        Check = "Backend /mobile/info"
        Ok = $infoOk
        Detail = "build=$infoBuild ready=$($mobileInfo.ready) $tunnelNote"
    }
    $tunnelUrl = [string]$mobileInfo.tunnel_backend_url
} catch {
    $checks += [PSCustomObject]@{ Check = "Backend /mobile/info"; Ok = $false; Detail = $_.Exception.Message }
}

if (Test-Path -LiteralPath $MobileConnectPath) {
    try {
        $connectJson = Get-Content -LiteralPath $MobileConnectPath -Raw | ConvertFrom-Json
        if (-not $tunnelUrl) {
            $tunnelUrl = [string]$connectJson.tunnel_backend_url
        }
        $fileBuild = [string]$connectJson.build_id
        $fileOk = [bool]$fileBuild
        if ($fileOk -and $expectedBuild -and $fileBuild -ne $expectedBuild) {
            $fileOk = $false
        }
        $checks += [PSCustomObject]@{
            Check = "mobile-connect.json build_id"
            Ok = $fileOk
            Detail = if ($fileBuild) { $fileBuild } else { "missing" }
        }
    } catch {
        $checks += [PSCustomObject]@{
            Check = "mobile-connect.json build_id"
            Ok = $false
            Detail = $_.Exception.Message
        }
    }
}
if ($tunnelUrl) {
    try {
        $tunnelHeaders = @{}
        try {
            $tunnelHost = ([Uri]$tunnelUrl).Host
            if ($tunnelHost -match '\.loca\.lt$') {
                $tunnelHeaders["Bypass-Tunnel-Reminder"] = "true"
            }
            if ($tunnelHost -match 'ngrok-free\.app|ngrok\.io|ngrok\.app') {
                $tunnelHeaders["ngrok-skip-browser-warning"] = "true"
            }
        } catch {
            # Ignore malformed tunnel URL.
        }
        $tunnelHealth = Invoke-RestMethod $tunnelUrl/health -TimeoutSec 20 -Headers $tunnelHeaders
        $tunnelOk = ($tunnelHealth.status -eq "ok") -and ($tunnelHealth.ready -ne $false)
        $checks += [PSCustomObject]@{
            Check = "Backend tunnel /health"
            Ok = $tunnelOk
            Detail = if ($tunnelOk) { $tunnelUrl } else { "not ok" }
        }
    } catch {
        $checks += [PSCustomObject]@{
            Check = "Backend tunnel /health"
            Ok = $false
            Detail = $_.Exception.Message
        }
    }
}

$envPath = Join-Path $Root "translator-mobile\.env"
if (Test-Path -LiteralPath $envPath) {
    $envApiUrl = ""
    Get-Content -LiteralPath $envPath | ForEach-Object {
        $line = $_.Trim()
        if ($line -match '^EXPO_PUBLIC_API_URL=(.*)$') {
            $envApiUrl = $Matches[1].Trim()
        }
    }
    $expectedLanBackend = "http://${LanIp}:$BackendPort"
    $envOk = ($envApiUrl -eq $expectedLanBackend) -or ($tunnelUrl -and $envApiUrl -eq $tunnelUrl)
    $checks += [PSCustomObject]@{
        Check = "Mobile .env EXPO_PUBLIC_API_URL"
        Ok = [bool]$envOk
        Detail = if ($envApiUrl) { $envApiUrl } else { "missing" }
    }
    if ($tunnelUrl) {
        $envTunnelUrl = ""
        Get-Content -LiteralPath $envPath | ForEach-Object {
            $line = $_.Trim()
            if ($line -match '^EXPO_PUBLIC_TUNNEL_API_URL=(.*)$') {
                $envTunnelUrl = $Matches[1].Trim()
            }
        }
        $checks += [PSCustomObject]@{
            Check = "Mobile .env EXPO_PUBLIC_TUNNEL_API_URL"
            Ok = ($envTunnelUrl -eq $tunnelUrl)
            Detail = if ($envTunnelUrl) { $envTunnelUrl } else { "missing" }
        }
    }
}

$httpsPort = 8443
if (Test-Path -LiteralPath $MobileConnectPath) {
    try {
        $connectJson = Get-Content -LiteralPath $MobileConnectPath -Raw | ConvertFrom-Json
        if ($connectJson.https_port) { $httpsPort = [int]$connectJson.https_port }
    } catch {
        # Keep default HTTPS port.
    }
}
$httpsOk = $false
$httpsDetail = "port $httpsPort"
$python = Join-Path $Root "venv\Scripts\python.exe"
$httpsUrl = "https://${LanIp}:$httpsPort/health"
if (Test-Path -LiteralPath $python) {
    try {
        $status = & $python -c "import ssl,urllib.request,sys; ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE; print(urllib.request.urlopen(sys.argv[1], context=ctx, timeout=12).status)" $httpsUrl 2>$null
        $httpsOk = [string]$status -match "200"
        $httpsDetail = if ($httpsOk) { "port $httpsPort" } else { "HTTP $status" }
    } catch {
        $httpsDetail = $_.Exception.Message
    }
} else {
    try {
        [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
        $httpsHealth = Invoke-RestMethod $httpsUrl -TimeoutSec 12
        $httpsOk = ($httpsHealth.status -eq "ok")
    } catch {
        $httpsDetail = $_.Exception.Message
    }
}
$checks += [PSCustomObject]@{
    Check = "Backend HTTPS /health (LAN)"
    Ok = $httpsOk
    Detail = $httpsDetail
}

$wsScript = @"
const WebSocket = require('ws');
const url = 'ws://${LanIp}:$BackendPort/ws/audio';
const ws = new WebSocket(url);
let done = false;
const finish = (ok, detail) => {
  if (done) return;
  done = true;
  console.log(JSON.stringify({ ok, detail }));
  try { ws.close(); } catch {}
  process.exit(ok ? 0 : 1);
};
ws.on('open', () => {});
ws.on('message', (data) => {
  const msg = JSON.parse(String(data));
  if (msg.type === 'ready') finish(true, msg.message || 'ready');
});
ws.on('error', (err) => finish(false, err.message));
setTimeout(() => finish(false, 'timeout'), 8000);
"@
$mobileRoot = Join-Path $PSScriptRoot "translator-mobile"
$wsLogs = Join-Path $mobileRoot "logs"
New-Item -ItemType Directory -Force -Path $wsLogs | Out-Null
$wsScriptPath = Join-Path $wsLogs "ws-probe-temp.js"
Set-Content -LiteralPath $wsScriptPath -Encoding ascii -Value $wsScript
try {
    $wsProbe = & node $wsScriptPath 2>&1
    if (-not $wsProbe) { throw "node ws probe produced no output" }
    $wsLine = @($wsProbe | Where-Object { $_ -match '^\{.*\}$' } | Select-Object -Last 1)
    if (-not $wsLine) { throw ($wsProbe -join " ") }
    $wsJson = ($wsLine | ConvertFrom-Json)
$checks += [PSCustomObject]@{
    Check = "Backend WebSocket /ws/audio"
    Ok = [bool]$wsJson.ok
    Detail = [string]$wsJson.detail
}
} catch {
    $checks += [PSCustomObject]@{ Check = "Backend WebSocket /ws/audio"; Ok = $false; Detail = $_.Exception.Message }
} finally {
    Remove-Item -LiteralPath $wsScriptPath -Force -ErrorAction SilentlyContinue
}

if ($httpsOk) {
    $wssScript = @"
const WebSocket = require('ws');
const url = 'wss://${LanIp}:$httpsPort/ws/audio';
const ws = new WebSocket(url, { rejectUnauthorized: false });
let done = false;
const finish = (ok, detail) => {
  if (done) return;
  done = true;
  console.log(JSON.stringify({ ok, detail }));
  try { ws.close(); } catch {}
  process.exit(ok ? 0 : 1);
};
ws.on('open', () => {});
ws.on('message', (data) => {
  const msg = JSON.parse(String(data));
  if (msg.type === 'ready') finish(true, msg.message || 'ready');
});
ws.on('error', (err) => finish(false, err.message));
setTimeout(() => finish(false, 'timeout'), 12000);
"@
    $wssScriptPath = Join-Path $wsLogs "wss-probe-temp.js"
    Set-Content -LiteralPath $wssScriptPath -Encoding ascii -Value $wssScript
    try {
        $wssProbe = & node $wssScriptPath 2>&1
        if (-not $wssProbe) { throw "node wss probe produced no output" }
        $wssLine = @($wssProbe | Where-Object { $_ -match '^\{.*\}$' } | Select-Object -Last 1)
        if (-not $wssLine) { throw ($wssProbe -join " ") }
        $wssJson = ($wssLine | ConvertFrom-Json)
        $checks += [PSCustomObject]@{
            Check = "Backend WSS /ws/audio (Safari HTTPS)"
            Ok = [bool]$wssJson.ok
            Detail = [string]$wssJson.detail
        }
    } catch {
        $checks += [PSCustomObject]@{
            Check = "Backend WSS /ws/audio (Safari HTTPS)"
            Ok = $false
            Detail = $_.Exception.Message
        }
    } finally {
        Remove-Item -LiteralPath $wssScriptPath -Force -ErrorAction SilentlyContinue
    }
}

$iosUrl = "http://${LanIp}:$ExpoPort/index.bundle?platform=ios&dev=true&hot=false&lazy=true&transform.engine=hermes&transform.bytecode=1&transform.routerRoot=app&unstable_transformProfile=hermes-stable"
try {
    $bundle = Invoke-WebRequest $iosUrl -UseBasicParsing -TimeoutSec 120
    $sizeMb = [math]::Round($bundle.RawContentLength / 1MB, 1)
    $hasRegister = ($bundle.Content -match "registerRootComponent")
    $checks += [PSCustomObject]@{
        Check = "iOS bundle (Expo Go URL)"
        Ok = ($bundle.RawContentLength -gt 2000000 -and $hasRegister)
        Detail = if ($hasRegister) { "$sizeMb MB" } else { "$sizeMb MB (stub, missing registerRootComponent)" }
    }
} catch {
    $checks += [PSCustomObject]@{ Check = "iOS bundle (Expo Go URL)"; Ok = $false; Detail = $_.Exception.Message }
}

try {
    $bundleReady = (Invoke-WebRequest "http://${LanIp}:$ExpoPort/.anai/bundle-ready" -UseBasicParsing -TimeoutSec 15).Content.Trim()
    $checks += [PSCustomObject]@{
        Check = "Metro bundle ready"
        Ok = ($bundleReady -eq "1" -or $bundleReady -match "^1:\d+")
        Detail = if ($bundleReady -match "^1:(\d+)(?::(\d+))?$") {
            $blocked = if ($Matches[2]) { ", blocked $($Matches[2]) stubs" } else { "" }
            "full bundle served ($($Matches[1]) bytes$blocked)"
        } elseif ($bundleReady -eq "1") { "full bundle served" } else { "not ready ($bundleReady)" }
    }
} catch {
    $checks += [PSCustomObject]@{ Check = "Metro bundle ready"; Ok = $false; Detail = $_.Exception.Message }
}

if ($ExpoPort -ne 8081) {
    $proxyIosUrl = "http://${LanIp}:8081/index.bundle?platform=ios&dev=true&hot=false&lazy=true&transform.engine=hermes&transform.bytecode=1&transform.routerRoot=app&unstable_transformProfile=hermes-stable"
    try {
        $proxyBundle = Invoke-WebRequest $proxyIosUrl -UseBasicParsing -TimeoutSec 120
        $proxySizeMb = [math]::Round($proxyBundle.RawContentLength / 1MB, 1)
        $proxyHasRegister = ($proxyBundle.Content -match "registerRootComponent")
        $checks += [PSCustomObject]@{
            Check = "iOS bundle via 8081 proxy"
            Ok = ($proxyBundle.RawContentLength -gt 2000000 -and $proxyHasRegister)
            Detail = if ($proxyHasRegister) { "$proxySizeMb MB via stale-cache port" } else { "$proxySizeMb MB (stub)" }
        }
    } catch {
        $checks += [PSCustomObject]@{ Check = "iOS bundle via 8081 proxy"; Ok = $false; Detail = $_.Exception.Message }
    }
}

$androidUrl = "http://${LanIp}:$ExpoPort/index.bundle?platform=android&dev=true&hot=false&lazy=true"
try {
    $androidBundle = Invoke-WebRequest $androidUrl -UseBasicParsing -TimeoutSec 120
    $androidSizeMb = [math]::Round($androidBundle.RawContentLength / 1MB, 1)
    $checks += [PSCustomObject]@{
        Check = "Android bundle (Expo Go URL)"
        Ok = ($androidBundle.RawContentLength -gt 2000000)
        Detail = "$androidSizeMb MB"
    }
} catch {
    $checks += [PSCustomObject]@{ Check = "Android bundle (Expo Go URL)"; Ok = $false; Detail = $_.Exception.Message }
}

$checks | ForEach-Object {
    $color = if ($_.Ok) { "Green" } else { "Red" }
    $mark = if ($_.Ok) { "PASS" } else { "FAIL" }
    Write-Host ("[{0}] {1} - {2}" -f $mark, $_.Check, $_.Detail) -ForegroundColor $color
}

$metroBuildCheck = $checks | Where-Object { $_.Check -eq "Metro build ID" } | Select-Object -First 1
if ($expectedBuild -and $metroBuildCheck.Detail -and $metroBuildCheck.Detail -ne $expectedBuild) {
    Write-Host ""
    Write-Host "WARN: Metro serves '$($metroBuildCheck.Detail)' but repo expects '$expectedBuild'." -ForegroundColor Yellow
    Write-Host "      Restart Expo: .\Start-MobilePhoneMode.ps1 -RestartExpo -FreshPort" -ForegroundColor Yellow
}

$lanHealthOk = [bool](@($checks | Where-Object { $_.Check -eq "Backend /health (LAN)" -and $_.Ok }))
$tunnelCheck = @($checks | Where-Object { $_.Check -eq "Backend tunnel /health" } | Select-Object -First 1)
$failed = @($checks | Where-Object {
    (-not $_.Ok) -and (-not ($lanHealthOk -and $_.Check -eq "Backend tunnel /health")) -and (-not ($lanHealthOk -and $_.Check -eq "Backend WSS /ws/audio (Safari HTTPS)"))
})
if ($tunnelCheck -and -not $tunnelCheck.Ok -and $lanHealthOk) {
    Write-Host ""
    Write-Host "NOTE: Tunnel fallback unreachable (LAN mode is fine): $($tunnelCheck.Detail)" -ForegroundColor Yellow
}
Write-Host ""
if ($failed.Count -eq 0) {
    Write-Host "All checks passed. On phone use: exp://${LanIp}:$ExpoPort" -ForegroundColor Green
    Write-Host "Safari (no Expo cache): http://${LanIp}:$BackendPort/mobile/app" -ForegroundColor Green
    Write-Host "If phone still shows 'Could not connect to development server':" -ForegroundColor Yellow
    Write-Host "  1. iPhone Settings > Expo Go > Local Network = ON (most common phone-side fix)" -ForegroundColor Yellow
    Write-Host "  2. Force-close Expo Go, reopen the URL, wait up to 60s" -ForegroundColor Yellow
    Write-Host "  3. Same Wi-Fi as PC (not guest network); disable VPN on phone/PC" -ForegroundColor Yellow
    Write-Host "  4. Router AP isolation? Connect PC to iPhone Personal Hotspot, rerun this script" -ForegroundColor Yellow
    Write-Host "  5. Tunnel fallback: .\Start-MobilePhoneMode.ps1 -RestartExpo -UseTunnel (needs NGROK_AUTHTOKEN)" -ForegroundColor Yellow
} else {
    Write-Host "$($failed.Count) check(s) failed." -ForegroundColor Red
    Write-Host "Fix: run as Administrator: .\Allow-AnaiTranslatorFirewall.ps1" -ForegroundColor Yellow
    Write-Host "Then: .\Start-MobilePhoneMode.ps1 -RestartExpo" -ForegroundColor Yellow
    Write-Host "Or tunnel: .\Start-MobilePhoneMode.ps1 -RestartExpo -UseTunnel" -ForegroundColor Yellow
}
Write-Host "iPhone: Settings > Expo Go > Local Network = ON (required for LAN)" -ForegroundColor Cyan
exit $(if ($failed.Count -eq 0) { 0 } else { 1 })
