param(
    [string]$LanIp = "",
    [int]$BackendPort = 8000,
    [int]$ExpoPort = 8082,
    [switch]$RestartExpo,
    [switch]$FreshPort,   # use TCP 8082 so Expo Go fetches a new bundle (bypasses stale 8081 cache)
    [switch]$UseTunnel,
    [switch]$AutoTunnel,  # fall back to tunnel when LAN is unreachable from this PC
    [switch]$VerifyBundle,  # optional; Metro /status is enough for Expo Go
    [int]$RestartAttempt = 0
)

$ErrorActionPreference = "Stop"
if ($RestartAttempt -ge 2) {
    throw "Start-MobilePhoneMode restart limit reached. Check logs/mobile-expo.err.log and firewall rules."
}
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Logs = Join-Path $Root "logs"
$MobileHttpsPort = 8443
$OpenSslPath = "C:\Program Files\Git\usr\bin\openssl.exe"
$MobileConnectPath = Join-Path $Logs "mobile-connect.json"

if ($RestartExpo -and -not $PSBoundParameters.ContainsKey("FreshPort")) {
    $FreshPort = $true
}
$MobileRoot = Join-Path $Root "translator-mobile"
$MobileBuildId = "2026-06-09-fix131"
$mobileBuildJs = Join-Path $MobileRoot "constants\mobileBuild.js"
if (Test-Path -LiteralPath $mobileBuildJs) {
    $buildJsText = Get-Content -LiteralPath $mobileBuildJs -Raw
    if ($buildJsText -match 'MOBILE_BUILD_ID\s*=\s*"([^"]+)"') {
        $MobileBuildId = $Matches[1]
    }
}
$EnvPath = Join-Path $MobileRoot ".env"
$ExpoOut = Join-Path $Logs "mobile-expo.out.log"
$ExpoErr = Join-Path $Logs "mobile-expo.err.log"
$ExpoPidPath = Join-Path $Logs "mobile-expo.pid"
$ExpoProxyOut = Join-Path $Logs "mobile-expo-proxy.out.log"
$ExpoProxyErr = Join-Path $Logs "mobile-expo-proxy.err.log"
$ExpoProxyPidPath = Join-Path $Logs "mobile-expo-proxy.pid"
$SummaryPath = Join-Path $Logs "mobile-phone-mode.txt"

New-Item -ItemType Directory -Force -Path $Logs | Out-Null

function Get-PreferredLanIp {
    $candidate = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -ne "127.0.0.1" -and
            $_.IPAddress -notmatch "^169\.254\." -and
            $_.InterfaceAlias -notmatch "vEthernet|Loopback|Docker|WSL"
        } |
        Sort-Object @{ Expression = { if ($_.InterfaceAlias -match "Wi-Fi|Wireless") { 0 } else { 1 } } }, InterfaceMetric |
        Select-Object -First 1
    if ($candidate) {
        return $candidate.IPAddress
    }
    $fallback = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -ne "127.0.0.1" -and $_.IPAddress -notmatch "^169\.254\." } |
        Select-Object -First 1
    if ($fallback) {
        return $fallback.IPAddress
    }
    throw "Could not detect a LAN IPv4 address."
}

function Get-OpenSslExe {
    if (Test-Path -LiteralPath $OpenSslPath) { return $OpenSslPath }
    $cmd = Get-Command openssl -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Ensure-MobileHttpsCert {
    param([string]$HostIp)
    $dir = Join-Path $Logs "mobile-https"
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $certPem = Join-Path $dir "cert.pem"
    $keyPem = Join-Path $dir "key.pem"
    $hostMarker = Join-Path $dir "host-ip.txt"
    $certValid = (Test-Path -LiteralPath $certPem) -and (Test-Path -LiteralPath $keyPem)
    $hostMatches = $false
    if ($certValid -and (Test-Path -LiteralPath $hostMarker)) {
        $storedHost = (Get-Content -LiteralPath $hostMarker -Raw -ErrorAction SilentlyContinue).Trim()
        $hostMatches = ($storedHost -eq $HostIp)
    }
    if ($certValid -and $hostMatches) {
        return @{ Cert = $certPem; Key = $keyPem }
    }
    if ($certValid -and -not $hostMatches) {
        Remove-Item -LiteralPath $certPem, $keyPem -Force -ErrorAction SilentlyContinue
    }
    $openssl = Get-OpenSslExe
    if (-not $openssl) {
        Write-Warning "OpenSSL not found - iPhone Safari microphone needs HTTPS on port $MobileHttpsPort."
        return $null
    }
    $subj = "/CN=$HostIp"
    $san = "subjectAltName=IP:127.0.0.1,IP:$HostIp,DNS:localhost"
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $openssl req -x509 -newkey rsa:2048 -keyout $keyPem -out $certPem -days 825 -nodes -subj $subj -addext $san 2>&1 | Out-Null
    } finally {
        $ErrorActionPreference = $prevEap
    }
    if ((Test-Path -LiteralPath $certPem) -and (Test-Path -LiteralPath $keyPem)) {
        Set-Content -LiteralPath $hostMarker -Value $HostIp -Encoding ascii -NoNewline
        return @{ Cert = $certPem; Key = $keyPem }
    }
    return $null
}

function Test-HttpsOk {
    param([string]$Url)
    $python = Join-Path $Root "venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $python) {
        try {
            $status = & $python -c "import ssl,urllib.request,sys; ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE; print(urllib.request.urlopen(sys.argv[1], context=ctx, timeout=8).status)" $Url 2>$null
            return [string]$status -match "200"
        } catch {
            # Fall through to PowerShell probe.
        }
    }
    try {
        [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 8
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Stop-MobileHttpsBackend {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -and $_.Name -match "python" -and
            $_.CommandLine -match "uvicorn" -and $_.CommandLine -match "backend\.api:app" -and
            $_.CommandLine -match "--port\s+`"?$MobileHttpsPort`"?"
        } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    for ($attempt = 0; $attempt -lt 20; $attempt += 1) {
        if (-not (Get-NetTCPConnection -LocalPort $MobileHttpsPort -State Listen -ErrorAction SilentlyContinue)) {
            break
        }
        Start-Sleep -Milliseconds 400
    }
}

function Ensure-MobileHttpsBackend {
    param([string]$HostIp)
    $hostMarker = Join-Path $Logs "mobile-https\host-ip.txt"
    $storedHost = ""
    if (Test-Path -LiteralPath $hostMarker) {
        $storedHost = (Get-Content -LiteralPath $hostMarker -Raw -ErrorAction SilentlyContinue).Trim()
    }
    $hostIpChanged = [bool]$storedHost -and ($storedHost -ne $HostIp)
    if ($hostIpChanged -and (Get-NetTCPConnection -LocalPort $MobileHttpsPort -State Listen -ErrorAction SilentlyContinue)) {
        Write-Output "LAN IP changed ($storedHost -> $HostIp) - restarting HTTPS backend on port $MobileHttpsPort."
        Stop-MobileHttpsBackend
    }
    $material = Ensure-MobileHttpsCert -HostIp $HostIp
    if (-not $material) { return $false }
    $fwScript = Join-Path $Root "Allow-AnaiTranslatorFirewall.ps1"
    if (Test-Path -LiteralPath $fwScript) {
        try {
            & $fwScript -BackendPort $BackendPort -ExpoPort $ExpoPort -HttpsPort $MobileHttpsPort
        } catch {
            Write-Warning "Could not ensure firewall rule for HTTPS port $MobileHttpsPort."
        }
    }
    if (Get-NetTCPConnection -LocalPort $MobileHttpsPort -State Listen -ErrorAction SilentlyContinue) {
        if (Test-Path -LiteralPath $fwScript) {
            try {
                & $fwScript -BackendPort $BackendPort -ExpoPort $ExpoPort -HttpsPort $MobileHttpsPort | Out-Null
            } catch {
                Write-Warning "Could not ensure firewall rule for HTTPS port $MobileHttpsPort."
            }
        }
        $lanOk = Test-HttpsOk "https://${HostIp}:$MobileHttpsPort/health"
        $localOk = Test-HttpsOk "https://127.0.0.1:$MobileHttpsPort/health"
        if ($localOk -and $lanOk) {
            return $true
        }
        Stop-MobileHttpsBackend
        Start-Sleep -Seconds 1
    }
    $python = Join-Path $Root "venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) { return $false }
    $httpsOut = Join-Path $Logs "backend-https.out.log"
    $httpsErr = Join-Path $Logs "backend-https.err.log"
    $HttpsPidPath = Join-Path $Logs "backend-https.pid"
    $httpsProcess = Start-Process -FilePath $python `
        -ArgumentList @(
            "-m", "uvicorn", "backend.api:app",
            "--host", "0.0.0.0",
            "--port", "$MobileHttpsPort",
            "--ssl-keyfile", $material.Key,
            "--ssl-certfile", $material.Cert
        ) `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $httpsOut `
        -RedirectStandardError $httpsErr `
        -PassThru
    if ($httpsProcess) {
        Set-Content -LiteralPath $HttpsPidPath -Value $httpsProcess.Id -Encoding ascii
    }
    for ($attempt = 0; $attempt -lt 30; $attempt += 1) {
        if ((Test-HttpsOk "https://127.0.0.1:$MobileHttpsPort/health") -and (Test-HttpsOk "https://${HostIp}:$MobileHttpsPort/health")) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Test-HttpOk {
    param([string]$Url)
    try {
        $response = Invoke-RestMethod -Uri $Url -TimeoutSec 8
        return ($null -ne $response) -and ($response.ready -ne $false)
    } catch {
        return $false
    }
}

function Start-MetroPortProxy {
    param(
        [int]$TargetPort,
        [int]$ProxyPort = 8081,
        [string]$HostIp
    )
    if ($TargetPort -eq $ProxyPort) { return $false }
    $proxyScript = Join-Path $MobileRoot "scripts\metro-port-proxy.js"
    if (-not (Test-Path -LiteralPath $proxyScript)) { return $false }
    Remove-Item -LiteralPath $ExpoProxyOut, $ExpoProxyErr -Force -ErrorAction SilentlyContinue
    $env:ANAI_METRO_PORT = "$TargetPort"
    $env:ANAI_METRO_PROXY_PORT = "$ProxyPort"
    $env:REACT_NATIVE_PACKAGER_HOSTNAME = $HostIp
    $proxyProcess = Start-Process -FilePath "node.exe" `
        -ArgumentList @($proxyScript) `
        -WorkingDirectory $MobileRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $ExpoProxyOut `
        -PassThru
    if ($proxyProcess) {
        Set-Content -LiteralPath $ExpoProxyPidPath -Value $proxyProcess.Id -Encoding ascii
    }
    for ($attempt = 0; $attempt -lt 20; $attempt += 1) {
        try {
            $status = Invoke-WebRequest -Uri "http://127.0.0.1:$ProxyPort/status" -TimeoutSec 3 -UseBasicParsing
            if ($status.StatusCode -eq 200) {
                Write-Output "Metro proxy: TCP $ProxyPort forwards to Metro on $TargetPort (stale Expo Go 8081 cache works)."
                return $true
            }
        } catch {
            # Proxy still starting.
        }
        Start-Sleep -Milliseconds 500
    }
    Write-Warning "Metro port proxy on $ProxyPort did not become ready."
    return $false
}

function Stop-ExpoProcesses {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -and $_.Name -in @("node.exe", "cmd.exe") -and
            (
                $_.CommandLine -match [regex]::Escape("translator-mobile") -or
                $_.CommandLine -match "metro-port-proxy" -or
                ($_.CommandLine -match "expo" -and $_.CommandLine -match "808[12]")
            )
        } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    foreach ($port in @($ExpoPort, 8081, 8082, 19000)) {
        for ($attempt = 0; $attempt -lt 20; $attempt += 1) {
            if (-not (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)) {
                break
            }
            Start-Sleep -Milliseconds 500
        }
    }
}

function Wait-MetroReady {
    param([int]$Attempts = 60)
    for ($attempt = 0; $attempt -lt $Attempts; $attempt += 1) {
        try {
            $status = Invoke-WebRequest -Uri "http://127.0.0.1:$ExpoPort/status" -TimeoutSec 5 -UseBasicParsing
            if ($status.StatusCode -eq 200) {
                return $true
            }
        } catch {
            # Metro still starting.
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Get-PortFirewallRuleName {
    param([string]$BaseName, [int]$Port)
    return "$BaseName TCP $Port"
}

function Test-FirewallRuleExists {
    param([string]$Name)
    $existing = Get-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue
    if ($existing) { return $true }
    $netsh = netsh advfirewall firewall show rule name="$Name" 2>$null
    return ($LASTEXITCODE -eq 0 -and $netsh -match "Rule Name")
}

function Ensure-FirewallRules {
    $rules = @()
    foreach ($port in @($ExpoPort, 8081, 8082) | Select-Object -Unique) {
        $rules += @{ Base = "Anai Translator Expo Metro"; Port = $port }
    }
    $rules += @(
        @{ Base = "Anai Translator Backend"; Port = $BackendPort },
        @{ Base = "Anai Translator Backend HTTPS"; Port = $MobileHttpsPort }
    )
    $missingPorts = @()
    foreach ($rule in $rules) {
        $ruleName = Get-PortFirewallRuleName -BaseName $rule.Base -Port $rule.Port
        if (Test-FirewallRuleExists -Name $ruleName) { continue }
        try {
            New-NetFirewallRule `
                -DisplayName $ruleName `
                -Direction Inbound `
                -Protocol TCP `
                -LocalPort $rule.Port `
                -Action Allow `
                -Profile Any `
                -Enabled True `
                -ErrorAction Stop | Out-Null
            Write-Output "Added firewall rule for TCP $($rule.Port)"
        } catch {
            try {
                netsh advfirewall firewall add rule name="$ruleName" dir=in action=allow protocol=TCP localport=$($rule.Port) profile=any enable=yes | Out-Null
                Write-Output "Added firewall rule (netsh) for TCP $($rule.Port)"
            } catch {
                $missingPorts += $rule.Port
                Write-Warning "Could not add firewall rule for TCP $($rule.Port). Run PowerShell as Administrator: .\Allow-AnaiTranslatorFirewall.ps1"
            }
        }
    }
    try {
        $nodePath = (Get-Command node -ErrorAction Stop).Source
        $nodeRule = "Anai Translator Node.js (Metro)"
        if (-not (Test-FirewallRuleExists -Name $nodeRule)) {
            New-NetFirewallRule `
                -DisplayName $nodeRule `
                -Direction Inbound `
                -Program $nodePath `
                -Action Allow `
                -Profile Any `
                -Enabled True `
                -ErrorAction Stop | Out-Null
            Write-Output "Added firewall rule for Node.js (Metro)"
        }
    } catch {
        Write-Warning "Could not add Node.js firewall rule. Run as Administrator: .\Allow-AnaiTranslatorFirewall.ps1"
    }
    return $missingPorts
}

function Get-ExpoTunnelUrlFromLogs {
    param([string[]]$Paths)
    foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path)) { continue }
        $match = Select-String -LiteralPath $path -Pattern "exp://[a-zA-Z0-9._-]+\.exp\.direct(?::\d+)?" -AllMatches |
            Select-Object -Last 1
        if ($match) {
            return $match.Matches[0].Value
        }
    }
    return $null
}

function Wait-ExpoTunnelUrl {
    param(
        [string[]]$Paths,
        [int]$Attempts = 45
    )
    for ($attempt = 0; $attempt -lt $Attempts; $attempt += 1) {
        $url = Get-ExpoTunnelUrlFromLogs -Paths $Paths
        if ($url) { return $url }
        Start-Sleep -Seconds 2
    }
    return $null
}

function Ensure-PrivateNetwork {
    try {
        $publicProfiles = Get-NetConnectionProfile -ErrorAction SilentlyContinue |
            Where-Object { $_.NetworkCategory -eq "Public" }
        foreach ($profile in $publicProfiles) {
            Set-NetConnectionProfile -InterfaceIndex $profile.InterfaceIndex -NetworkCategory Private
            Write-Output "Set '$($profile.Name)' ($($profile.InterfaceAlias)) to Private network (phones cannot reach Public networks reliably)."
        }
    } catch {
        Write-Warning "Wi-Fi is still on Public network. Run as Administrator: .\Allow-AnaiTranslatorFirewall.ps1"
        return $false
    }
    return $true
}

function Request-AdminFirewallFix {
    $firewallScript = Join-Path $Root "Allow-AnaiTranslatorFirewall.ps1"
    if (-not (Test-Path -LiteralPath $firewallScript)) { return }
    Write-Output "Requesting Administrator approval to open firewall ports and set Wi-Fi to Private..."
    try {
        Start-Process powershell -Verb RunAs -ArgumentList @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $firewallScript,
            "-BackendPort", $BackendPort, "-ExpoPort", $ExpoPort, "-HttpsPort", $MobileHttpsPort
        ) -Wait -ErrorAction Stop | Out-Null
    } catch {
        Write-Warning "Administrator approval was not granted."
    }
}

function Test-LanMetroReachable {
    param([string]$HostIp)
    try {
        $status = Invoke-WebRequest -Uri "http://${HostIp}:$ExpoPort/status" -TimeoutSec 8 -UseBasicParsing
        return $status.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Get-ExpoGoBundleUrl {
    param(
        [string]$Platform,
        [string]$HostIp
    )
    $query = "dev=true&hot=false&lazy=true&transform.engine=hermes&transform.bytecode=1&transform.routerRoot=app&unstable_transformProfile=hermes-stable"
    if ($Platform -eq "ios") {
        return "http://${HostIp}:$ExpoPort/index.bundle?platform=ios&$query"
    }
    return "http://${HostIp}:$ExpoPort/index.bundle?platform=android&$query"
}

function Test-ExpoBundleReady {
    param(
        [string]$BundleUrl,
        [string]$Label = "bundle"
    )
    $bundlePath = Join-Path $Logs "mobile-expo.bundle-test.js"
    try {
        Remove-Item -LiteralPath $bundlePath -Force -ErrorAction SilentlyContinue
        Invoke-WebRequest -Uri $BundleUrl -TimeoutSec 300 -OutFile $bundlePath -UseBasicParsing | Out-Null
        $bundleSize = if (Test-Path -LiteralPath $bundlePath) { (Get-Item -LiteralPath $bundlePath).Length } else { 0 }
        $bundleText = if ($bundleSize -gt 0) { Get-Content -LiteralPath $bundlePath -Raw -ErrorAction SilentlyContinue } else { "" }
        Remove-Item -LiteralPath $bundlePath -Force -ErrorAction SilentlyContinue
        return @{
            Ok = ($bundleSize -gt 2000000 -and $bundleText -match "registerRootComponent")
            Size = $bundleSize
            Label = $Label
        }
    } catch {
        return @{ Ok = $false; Size = 0; Label = $Label }
    }
}

function Wait-ExpoBundleReady {
    param(
        [string]$HostIp,
        [int]$Attempts = 8,
        [string[]]$Platforms = @("ios", "android")
    )
    # Avoid hammering Metro with rapid bundle probes (those return tiny 1-module stubs).
    Start-Sleep -Seconds 15
    foreach ($platform in $Platforms) {
        $bundleUrl = Get-ExpoGoBundleUrl -Platform $platform -HostIp $HostIp
        $ready = $false
        for ($attempt = 0; $attempt -lt $Attempts; $attempt += 1) {
            $result = Test-ExpoBundleReady -BundleUrl $bundleUrl -Label $platform
            if ($result.Ok) {
                $ready = $true
                Write-Output "Pre-warmed $platform bundle from $HostIp ($([math]::Round($result.Size / 1MB, 1)) MB)"
                break
            }
            Start-Sleep -Seconds 12
        }
        if (-not $ready) {
            return $false
        }
    }
    return $true
}

if (-not $LanIp) {
    $LanIp = Get-PreferredLanIp
}

if ($FreshPort) {
    $ExpoPort = 8082
    Write-Output "FreshPort: Metro on TCP $ExpoPort (open this NEW URL on your phone to bypass a stale 8081 cache)."
    $fwScript = Join-Path $Root "Allow-AnaiTranslatorFirewall.ps1"
    if (Test-Path -LiteralPath $fwScript) {
        try {
            & $fwScript -ExpoPort $ExpoPort -BackendPort $BackendPort -HttpsPort $MobileHttpsPort
        } catch {
            Write-Warning "Could not add firewall rule for port $ExpoPort. Run Allow-AnaiTranslatorFirewall.ps1 as Admin."
        }
    }
}

$publicWifi = @(Get-NetConnectionProfile -ErrorAction SilentlyContinue | Where-Object { $_.NetworkCategory -eq "Public" })
if ($publicWifi.Count -gt 0 -and -not $UseTunnel) {
    Write-Warning "Wi-Fi network is Public - phones often cannot reach Metro until it is Private."
    Request-AdminFirewallFix
    Ensure-PrivateNetwork | Out-Null
}

$missingFirewallPorts = @(Ensure-FirewallRules)
if ($missingFirewallPorts.Count -gt 0 -and -not $UseTunnel) {
    Request-AdminFirewallFix
    $missingFirewallPorts = @(Ensure-FirewallRules)
}

$CurrentPhoneUrlPath = Join-Path $Logs "current-phone-url.txt"
$tunnelBackendUrl = ""
if (Test-Path -LiteralPath $CurrentPhoneUrlPath) {
    $tunnelBackendUrl = (Get-Content -LiteralPath $CurrentPhoneUrlPath -Raw -ErrorAction SilentlyContinue).Trim()
    if ($tunnelBackendUrl -and -not (Test-HttpOk "$tunnelBackendUrl/health")) {
        Write-Warning "Tunnel URL is stale or unreachable - not publishing to phone: $tunnelBackendUrl"
        Remove-Item -LiteralPath $CurrentPhoneUrlPath -Force -ErrorAction SilentlyContinue
        $tunnelBackendUrl = ""
    }
}

$BackendUrl = "http://$LanIp`:$BackendPort"
$ExpoUrl = if ($UseTunnel) { "exp://127.0.0.1:$ExpoPort (use tunnel URL printed in $ExpoOut)" } else { "exp://$LanIp`:$ExpoPort" }
$PhoneSetupUrl = "$BackendUrl/mobile"
$WebAppUrl = "$BackendUrl/mobile/app"
$BackendHttpsUrl = "https://$LanIp`:$MobileHttpsPort"
$WebAppHttpsUrl = "$BackendHttpsUrl/mobile/app"
$httpsReady = Ensure-MobileHttpsBackend -HostIp $LanIp
if (-not $httpsReady) {
    $BackendHttpsUrl = ""
    $WebAppHttpsUrl = ""
}

function Write-MobileConnectJson {
    @{
        build_id    = $MobileBuildId
        expo_url    = if ($UseTunnel) { "" } else { $ExpoUrl }
        backend_url = $BackendUrl
        backend_https_url = $BackendHttpsUrl
        lan_ip      = $LanIp
        expo_port   = $ExpoPort
        https_port  = $MobileHttpsPort
        phone_setup_url = $PhoneSetupUrl
        web_app_url = $WebAppUrl
        web_app_https_url = $WebAppHttpsUrl
        tunnel_backend_url = $tunnelBackendUrl
    } | ConvertTo-Json | Set-Content -LiteralPath $MobileConnectPath -Encoding utf8
}

$envLines = @{}
if (Test-Path -LiteralPath $EnvPath) {
    Get-Content -LiteralPath $EnvPath | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line -match '^([^=]+)=(.*)$') {
            $envLines[$Matches[1].Trim()] = $Matches[2].Trim()
        }
    }
}
$effectiveBackendUrl = $BackendUrl
if ($UseTunnel -and $tunnelBackendUrl) {
    $effectiveBackendUrl = $tunnelBackendUrl
}
$envLines["EXPO_PUBLIC_API_URL"] = $effectiveBackendUrl
if ($tunnelBackendUrl) {
    $envLines["EXPO_PUBLIC_TUNNEL_API_URL"] = $tunnelBackendUrl
} else {
    $envLines.Remove("EXPO_PUBLIC_TUNNEL_API_URL")
}
if (-not $envLines.ContainsKey("EXPO_PUBLIC_DEBUG_LOGS")) {
    $envLines["EXPO_PUBLIC_DEBUG_LOGS"] = "1"
}
($envLines.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Key)=$($_.Value)" }) |
    Set-Content -LiteralPath $EnvPath -Encoding ascii

if (-not (Test-HttpOk "$BackendUrl/health")) {
    $translatorArgs = @{ SkipBuild = $true; NoTunnel = $true; SkipProductTest = $true; SkipMobile = $true }
    if ($RestartExpo) {
        $translatorArgs.Restart = $true
    }
    & (Join-Path $Root "Start-Translator.ps1") @translatorArgs
}
if (-not (Test-HttpOk "$BackendUrl/health")) {
    throw "Backend is not reachable at $BackendUrl/health. Check Wi-Fi and Windows firewall."
}
Write-MobileConnectJson
if ($RestartExpo -and -not (Test-HttpOk "$BackendUrl/mobile/info")) {
    Write-Warning "Backend /mobile/info not ready yet (may need a few seconds after restart)."
}

if ($RestartExpo) {
    Stop-ExpoProcesses
    if (Test-Path -LiteralPath $ExpoPidPath) {
        Remove-Item -LiteralPath $ExpoPidPath -Force -ErrorAction SilentlyContinue
    }
}

$expoStatusOk = $false
if (Test-Path -LiteralPath $ExpoPidPath) {
    $savedExpoPid = (Get-Content -LiteralPath $ExpoPidPath -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($savedExpoPid -and -not (Get-Process -Id $savedExpoPid -ErrorAction SilentlyContinue)) {
        Remove-Item -LiteralPath $ExpoPidPath -Force -ErrorAction SilentlyContinue
        if (Get-NetTCPConnection -LocalPort $ExpoPort -State Listen -ErrorAction SilentlyContinue) {
            Write-Output "Stale Expo parent PID $savedExpoPid - cleaning port $ExpoPort."
            Stop-ExpoProcesses
        }
    }
}
try {
    $status = Invoke-WebRequest -Uri "http://127.0.0.1:$ExpoPort/status" -TimeoutSec 5 -UseBasicParsing
    $expoStatusOk = $status.StatusCode -eq 200
} catch {
    $expoStatusOk = $false
}

if ($expoStatusOk) {
    try {
        $runningBuild = (Invoke-WebRequest -Uri "http://127.0.0.1:$ExpoPort/.anai/build-id" -TimeoutSec 5 -UseBasicParsing).Content.Trim()
        if ($runningBuild -and $runningBuild -ne $MobileBuildId) {
            Write-Output "Metro serves $runningBuild but expected $MobileBuildId - restarting Expo on port $ExpoPort."
            $RestartExpo = $true
            $expoStatusOk = $false
        }
    } catch {
        # Old Metro without build-id endpoint - leave running unless user asked for restart.
    }
}

if (-not $expoStatusOk -or $RestartExpo) {
    if ($RestartExpo -or $FreshPort) {
        Stop-ExpoProcesses
    }
    Remove-Item -LiteralPath $ExpoOut, $ExpoErr -Force -ErrorAction SilentlyContinue
    $env:EXPO_PUBLIC_API_URL = $effectiveBackendUrl
    if ($tunnelBackendUrl) {
        $env:EXPO_PUBLIC_TUNNEL_API_URL = $tunnelBackendUrl
    } else {
        Remove-Item Env:EXPO_PUBLIC_TUNNEL_API_URL -ErrorAction SilentlyContinue
    }
    $env:EXPO_PUBLIC_DEBUG_LOGS = "1"
    $env:EXPO_NO_TELEMETRY = "1"
    Remove-Item Env:CI -ErrorAction SilentlyContinue
    $env:REACT_NATIVE_PACKAGER_HOSTNAME = $LanIp
    $env:ANAI_MOBILE_BUILD_ID = $MobileBuildId
    $env:NODE_OPTIONS = "--max-old-space-size=8192"
    $env:METRO_MAX_WORKERS = "1"
    $MetroCacheRoot = Join-Path $env:LOCALAPPDATA "AnaiTranslatorMetroCache"
    New-Item -ItemType Directory -Force -Path $MetroCacheRoot | Out-Null
    $env:TEMP = $MetroCacheRoot
    $env:TMP = $MetroCacheRoot
    Remove-Item Env:EXPO_OFFLINE -ErrorAction SilentlyContinue

    $expoArgs = @("expo", "start", "--port", "$ExpoPort", "--max-workers", "1")
    if ($UseTunnel) {
        $expoArgs += @("--host", "tunnel")
    } else {
        $expoArgs += @("--host", "lan")
    }
    if ($RestartExpo) {
        $expoArgs += "--clear"
    }

    $expoEnvLines = @(
        "set NODE_OPTIONS=--max-old-space-size=8192",
        "set METRO_MAX_WORKERS=1",
        "set TEMP=$MetroCacheRoot",
        "set TMP=$MetroCacheRoot",
        "set REACT_NATIVE_PACKAGER_HOSTNAME=$LanIp",
        "set ANAI_MOBILE_BUILD_ID=$MobileBuildId",
        "set EXPO_PUBLIC_API_URL=$effectiveBackendUrl",
        "set EXPO_PUBLIC_DEBUG_LOGS=1"
    )
    if ($tunnelBackendUrl) {
        $expoEnvLines += "set EXPO_PUBLIC_TUNNEL_API_URL=$tunnelBackendUrl"
    }
    if ($env:NGROK_AUTHTOKEN) {
        $expoEnvLines += "set NGROK_AUTHTOKEN=$($env:NGROK_AUTHTOKEN)"
    }
    $expoCommand = ($expoEnvLines + "npx.cmd $($expoArgs -join ' ')") -join "&& "
    $process = Start-Process -FilePath "cmd.exe" `
        -ArgumentList @("/c", $expoCommand) `
        -WorkingDirectory $MobileRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $ExpoOut `
        -RedirectStandardError $ExpoErr `
        -PassThru
    Set-Content -LiteralPath $ExpoPidPath -Value $process.Id -Encoding ascii

    if (-not (Wait-MetroReady)) {
        $tail = Get-Content -LiteralPath $ExpoOut -Tail 30 -ErrorAction SilentlyContinue
        throw "Expo Metro did not become ready on port $ExpoPort. Recent log:`n$($tail -join "`n")"
    }
    if (-not $UseTunnel -and $ExpoPort -ne 8081) {
        Start-MetroPortProxy -TargetPort $ExpoPort -ProxyPort 8081 -HostIp $LanIp | Out-Null
    }
    if (-not $UseTunnel) {
        if (-not (Wait-ExpoBundleReady -HostIp $LanIp)) {
            $tail = Get-Content -LiteralPath $ExpoOut -Tail 20 -ErrorAction SilentlyContinue
            Write-Warning @"
Metro bundle is not fully pre-warmed yet. Wait 30-60 seconds before opening Expo Go on your phone.
If the phone shows a black screen or error code, close Expo Go completely and try again.
Recent log:
$($tail -join "`n")
"@
            if ($VerifyBundle) {
                throw "Expo bundle failed to compile for Expo Go."
            }
        }
    }
}

if (Select-String -LiteralPath $ExpoErr -Pattern "unable to sign manifest" -Quiet -ErrorAction SilentlyContinue) {
    throw "Expo manifest signing failed. Do not use --offline mode for Expo Go."
}
$tunnelFailed = $false
if ($UseTunnel) {
    $tunnelFailed = Select-String -LiteralPath $ExpoErr -Pattern "Ngrok|tunnel took too long|CommandError" -Quiet -ErrorAction SilentlyContinue
    if ($tunnelFailed -and -not (Wait-MetroReady -Attempts 3)) {
        Write-Warning "Tunnel mode failed (ngrok). Restarting in LAN mode..."
        if (-not $env:NGROK_AUTHTOKEN) {
            Write-Warning "Tip: set NGROK_AUTHTOKEN (free at ngrok.com) then rerun with -UseTunnel for router AP isolation."
        }
        & $MyInvocation.MyCommand.Path -LanIp $LanIp -BackendPort $BackendPort -ExpoPort $ExpoPort -RestartExpo -RestartAttempt ($RestartAttempt + 1)
        return
    }
}

$lanMetroOk = if ($UseTunnel) { $true } else { Test-LanMetroReachable -HostIp $LanIp }
$lanBundleOk = $false
if (-not $UseTunnel -and $lanMetroOk) {
    $iosBundle = Test-ExpoBundleReady -BundleUrl (Get-ExpoGoBundleUrl -Platform "ios" -HostIp $LanIp) -Label "ios-lan"
    $androidBundle = Test-ExpoBundleReady -BundleUrl (Get-ExpoGoBundleUrl -Platform "android" -HostIp $LanIp) -Label "android-lan"
    $lanBundleOk = $iosBundle.Ok -and $androidBundle.Ok
    if ($lanBundleOk) {
        Write-Output "Phone bundles reachable at LAN IP (iOS $([math]::Round($iosBundle.Size / 1MB, 1)) MB, Android $([math]::Round($androidBundle.Size / 1MB, 1)) MB)"
    }
}
$tunnelHint = ""
$tunnelUrl = ""
if ($UseTunnel) {
    $tunnelUrl = Wait-ExpoTunnelUrl -Paths @($ExpoOut, $ExpoErr)
    if ($tunnelUrl) {
        $ExpoUrl = $tunnelUrl
        Write-Output "Expo tunnel URL: $tunnelUrl"
        Write-MobileConnectJson
    }
    if (-not $tunnelUrl -and $tunnelFailed) {
        Write-Warning "ngrok tunnel did not publish a URL. LAN mode is still running at $ExpoUrl"
        Write-Warning "If phone cannot reach LAN: iPhone Settings > Expo Go > Local Network = ON, or use iPhone Personal Hotspot."
    }
}

$tunnelHint = ""
if (-not $lanMetroOk -and -not $UseTunnel) {
    $tunnelHint = @"

LAN WARNING: Metro is not reachable at http://${LanIp}:$ExpoPort from this PC.
Your phone will show 'Could not connect to development server' until this is fixed.
Fix (run PowerShell as Administrator once):
  .\Allow-AnaiTranslatorFirewall.ps1
Or bypass LAN entirely:
  .\Start-MobilePhoneMode.ps1 -RestartExpo -UseTunnel
"@
    if ($AutoTunnel) {
        if (-not $tunnelBackendUrl) {
            Write-Warning "No cloudflare backend tunnel in logs/current-phone-url.txt - API may fail on cellular/AP-isolated Wi-Fi."
            Write-Warning "Run: .\Start-Translator.ps1  (creates tunnel), then rerun mobile mode."
        } else {
            Write-Warning "LAN Metro unreachable - restarting with Expo tunnel + API tunnel $tunnelBackendUrl"
        }
        & $MyInvocation.MyCommand.Path -LanIp $LanIp -BackendPort $BackendPort -ExpoPort $ExpoPort -RestartExpo -UseTunnel -RestartAttempt ($RestartAttempt + 1)
        return
    }
} elseif (-not $lanBundleOk -and -not $UseTunnel) {
    Write-Warning "Metro is up but the full bundle is still warming. Wait 30-60s before opening Expo Go (PC terminal should show ~1280 modules)."
}

@"
Anai native phone mode
Mobile build: $MobileBuildId
Backend URL: $BackendUrl
Expo URL:    $ExpoUrl
LAN Metro:   $(if ($UseTunnel) { 'skipped (tunnel mode)' } elseif ($lanMetroOk -and $lanBundleOk) { 'reachable' } else { 'NOT reachable - use -UseTunnel' })
- If phone shows Offline and plain 'Network restored' without 'Build $MobileBuildId', Expo Go has STALE cached JS
- Fix stale cache: force-close Expo Go, open the Expo URL above, or rerun with -FreshPort -RestartExpo (uses port 8082)
- iPhone: Settings > Expo Go > Local Network must be ON (if OFF, you get 'Could not connect to development server')
- Phone must be on the SAME Wi-Fi as this PC (cellular alone cannot reach 192.168.x.x)
- Force-close Expo Go before retrying after a failed load

Phone setup page (open in iPhone Safari): $PhoneSetupUrl
Open Expo Go on the phone and enter:
$(if ($tunnelUrl) { $tunnelUrl } else { $ExpoUrl })

Requirements:
- Expo Go updated for SDK 54 (same major SDK as package.json)
- If LAN fails, rerun with: Start-MobilePhoneMode.ps1 -RestartExpo -UseTunnel
- Phone and PC on the same Wi-Fi for LAN mode
- Allow inbound Windows Firewall ports TCP $BackendPort and TCP $ExpoPort
  (run as Admin once: .\Allow-AnaiTranslatorFirewall.ps1)
$tunnelHint
"@ | Set-Content -LiteralPath $SummaryPath -Encoding ascii

Write-Output "Backend URL: $BackendUrl"
Write-Output "Phone setup: $PhoneSetupUrl  (open in iPhone Safari if Expo Go shows stale Offline UI)"
if ($tunnelUrl) {
    Write-Output "Expo URL:    $tunnelUrl (tunnel - use this on your phone)"
} else {
    Write-Output "Expo URL:    $ExpoUrl"
}
Write-Output "Summary:     $SummaryPath"

if ($missingFirewallPorts.Count -gt 0) {
    Write-Output ""
    Write-Output ">>> FIREWALL REQUIRED (phone will NOT connect without this) <<<"
    Write-Output "Open PowerShell as Administrator and run:"
    Write-Output "  .\Allow-AnaiTranslatorFirewall.ps1"
    Write-Output "Missing inbound TCP: $($missingFirewallPorts -join ', ')"
}

$qrScript = Join-Path $MobileRoot "node_modules\qrcode-terminal\bin\qrcode-terminal.js"
$qrUrl = if ($tunnelUrl) { $tunnelUrl } else { $ExpoUrl }
if (Test-Path -LiteralPath $qrScript) {
    & node $qrScript $qrUrl
}

if (-not $UseTunnel -and ($missingFirewallPorts.Count -gt 0 -or -not $lanMetroOk -or -not $lanBundleOk)) {
    Write-Output ""
    Write-Output ">>> PHONE WILL FAIL WITH 'Could not connect to development server' <<<"
    Write-Output "Run as Administrator: .\Allow-AnaiTranslatorFirewall.ps1"
    Write-Output "Or use tunnel: .\Start-MobilePhoneMode.ps1 -RestartExpo -UseTunnel"
}

Write-Output "Safari app:  $WebAppUrl  (HTTP - mic blocked on iPhone)"
if ($httpsReady) {
    Write-Output "Safari mic:  $WebAppHttpsUrl  (HTTPS - use this on iPhone for microphone)"
}
if ($tunnelBackendUrl) {
    Write-MobileConnectJson
}

Write-Output "Mobile build: $MobileBuildId (badge should show '$($MobileBuildId -replace '^.*-','')' when offline)"
if ($tunnelBackendUrl) {
    Write-Output "Tunnel API:  $tunnelBackendUrl (phones on isolated Wi-Fi can use this backend)"
}
if ($FreshPort) {
    Write-Output ">>> OPEN THIS NEW URL ON YOUR PHONE (bypasses stale 8081 cache): $ExpoUrl <<<"
    Write-Output ">>> STALE 8081 CACHE ALSO WORKS: exp://${LanIp}:8081 (auto-forwards to port $ExpoPort) <<<"
}
try {
    Set-Clipboard -Value $(if ($tunnelUrl) { $tunnelUrl } else { $ExpoUrl })
    Write-Output "Expo URL copied to Windows clipboard."
} catch {
    # Clipboard unavailable in some shells.
}
if ($lanMetroOk -and $lanBundleOk -and -not $UseTunnel) {
    Write-Output ""
    Write-Output "PC checks passed. If phone still fails:"
    Write-Output "  1. iPhone Settings > Expo Go > Local Network = ON"
    Write-Output "  2. Same Wi-Fi as PC (not guest network)"
    Write-Output "  3. Force-close Expo Go, reopen exp://$LanIp`:$ExpoPort"
    Write-Output "  4. Router AP isolation? Connect PC to iPhone Personal Hotspot instead"
}
