param(
    [string]$LanIp = "",
    [int]$BackendPort = 8000,
    [int]$ExpoPort = 8081,
    [switch]$RestartExpo,
    [switch]$UseTunnel,
    [switch]$VerifyBundle  # optional; Metro /status is enough for Expo Go
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Logs = Join-Path $Root "logs"
$MobileRoot = Join-Path $Root "translator-mobile"
$EnvPath = Join-Path $MobileRoot ".env"
$ExpoOut = Join-Path $Logs "mobile-expo.out.log"
$ExpoErr = Join-Path $Logs "mobile-expo.err.log"
$ExpoPidPath = Join-Path $Logs "mobile-expo.pid"
$SummaryPath = Join-Path $Logs "mobile-phone-mode.txt"

New-Item -ItemType Directory -Force -Path $Logs | Out-Null

function Get-PreferredLanIp {
    $candidate = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -ne "127.0.0.1" -and
            $_.IPAddress -notmatch "^169\.254\." -and
            $_.IPAddress -notmatch "^172\.(1[6-9]|2\d|3[0-1])\." -and
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

function Test-HttpOk {
    param([string]$Url)
    try {
        $response = Invoke-RestMethod -Uri $Url -TimeoutSec 8
        return $null -ne $response
    } catch {
        return $false
    }
}

function Stop-ExpoProcesses {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -and $_.Name -in @("node.exe", "cmd.exe") -and
            (
                $_.CommandLine -match [regex]::Escape("translator-mobile") -or
                ($_.CommandLine -match "expo" -and $_.CommandLine -match "$ExpoPort")
            )
        } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    for ($attempt = 0; $attempt -lt 20; $attempt += 1) {
        if (-not (Get-NetTCPConnection -LocalPort $ExpoPort -State Listen -ErrorAction SilentlyContinue)) {
            return
        }
        Start-Sleep -Milliseconds 500
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

function Ensure-FirewallRules {
    $rules = @(
        @{ Name = "Anai Translator Expo Metro"; Port = $ExpoPort },
        @{ Name = "Anai Translator Backend"; Port = $BackendPort }
    )
    $missingPorts = @()
    foreach ($rule in $rules) {
        $existing = Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue
        if ($existing) { continue }
        try {
            New-NetFirewallRule `
                -DisplayName $rule.Name `
                -Direction Inbound `
                -Protocol TCP `
                -LocalPort $rule.Port `
                -Action Allow `
                -Profile Any `
                -ErrorAction Stop | Out-Null
            Write-Output "Added firewall rule for TCP $($rule.Port)"
        } catch {
            $missingPorts += $rule.Port
            Write-Warning "Could not add firewall rule for TCP $($rule.Port). Run PowerShell as Administrator or allow the port manually."
        }
    }
    return $missingPorts
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

function Wait-ExpoBundleReady {
    param(
        [int]$Attempts = 8,
        [string[]]$Platforms = @("ios", "android")
    )
    $bundlePath = Join-Path $Logs "mobile-expo.bundle-test.js"
    # Avoid hammering Metro with rapid bundle probes (those return tiny 1-module stubs).
    Start-Sleep -Seconds 15
    foreach ($platform in $Platforms) {
        $bundleUrl = "http://127.0.0.1:$ExpoPort/index.bundle?platform=$platform&dev=true&minify=false&lazy=false"
        $ready = $false
        for ($attempt = 0; $attempt -lt $Attempts; $attempt += 1) {
            try {
                Remove-Item -LiteralPath $bundlePath -Force -ErrorAction SilentlyContinue
                Invoke-WebRequest -Uri $bundleUrl -TimeoutSec 300 -OutFile $bundlePath -UseBasicParsing | Out-Null
                $bundleSize = if (Test-Path -LiteralPath $bundlePath) { (Get-Item -LiteralPath $bundlePath).Length } else { 0 }
                $bundleText = if ($bundleSize -gt 0) { Get-Content -LiteralPath $bundlePath -Raw -ErrorAction SilentlyContinue } else { "" }
                if (
                    $bundleSize -gt 2000000 -and
                    $bundleText -match "registerRootComponent"
                ) {
                    $ready = $true
                    Write-Output "Pre-warmed $platform bundle ($([math]::Round($bundleSize / 1MB, 1)) MB)"
                    break
                }
            } catch {
                # Bundle still compiling.
            }
            Start-Sleep -Seconds 12
        }
        Remove-Item -LiteralPath $bundlePath -Force -ErrorAction SilentlyContinue
        if (-not $ready) {
            return $false
        }
    }
    return $true
}

if (-not $LanIp) {
    $LanIp = Get-PreferredLanIp
}

$missingFirewallPorts = @(Ensure-FirewallRules)

$BackendUrl = "http://$LanIp`:$BackendPort"
$ExpoUrl = if ($UseTunnel) { "exp://127.0.0.1:$ExpoPort (use tunnel URL printed in $ExpoOut)" } else { "exp://$LanIp`:$ExpoPort" }

Set-Content -LiteralPath $EnvPath -Encoding ascii -Value @(
    "EXPO_PUBLIC_API_URL=$BackendUrl",
    "EXPO_PUBLIC_DEBUG_LOGS=1"
)

if (-not (Test-HttpOk "$BackendUrl/health")) {
    & (Join-Path $Root "Start-Translator.ps1") -SkipBuild -NoTunnel -SkipProductTest
}
if (-not (Test-HttpOk "$BackendUrl/health")) {
    throw "Backend is not reachable at $BackendUrl/health. Check Wi-Fi and Windows firewall."
}

if ($RestartExpo) {
    Stop-ExpoProcesses
}

$expoStatusOk = $false
try {
    $status = Invoke-WebRequest -Uri "http://127.0.0.1:$ExpoPort/status" -TimeoutSec 5 -UseBasicParsing
    $expoStatusOk = $status.StatusCode -eq 200
} catch {
    $expoStatusOk = $false
}

if (-not $expoStatusOk -or $RestartExpo) {
    if ($RestartExpo) {
        Stop-ExpoProcesses
    }
    Remove-Item -LiteralPath $ExpoOut, $ExpoErr -Force -ErrorAction SilentlyContinue
    $env:EXPO_PUBLIC_API_URL = $BackendUrl
    $env:EXPO_PUBLIC_DEBUG_LOGS = "1"
    $env:EXPO_NO_TELEMETRY = "1"
    Remove-Item Env:CI -ErrorAction SilentlyContinue
    $env:REACT_NATIVE_PACKAGER_HOSTNAME = $LanIp
    $env:NODE_OPTIONS = "--max-old-space-size=8192"
    $env:METRO_MAX_WORKERS = "1"
    $MetroCacheRoot = Join-Path $env:LOCALAPPDATA "AnaiTranslatorMetroCache"
    New-Item -ItemType Directory -Force -Path $MetroCacheRoot | Out-Null
    $env:TEMP = $MetroCacheRoot
    $env:TMP = $MetroCacheRoot
    Remove-Item Env:EXPO_OFFLINE -ErrorAction SilentlyContinue

    $expoArgs = @("expo", "start", "--port", "$ExpoPort", "--max-workers", "1")
    if ($UseTunnel) {
        $expoArgs += "--tunnel"
    } else {
        $expoArgs += "--lan"
    }
    if ($RestartExpo) {
        $expoArgs += "--clear"
    }

    $expoCommand = @(
        "set NODE_OPTIONS=--max-old-space-size=8192",
        "set METRO_MAX_WORKERS=1",
        "set TEMP=$MetroCacheRoot",
        "set TMP=$MetroCacheRoot",
        "set REACT_NATIVE_PACKAGER_HOSTNAME=$LanIp",
        "set EXPO_PUBLIC_API_URL=$BackendUrl",
        "set EXPO_PUBLIC_DEBUG_LOGS=1",
        "npx.cmd $($expoArgs -join ' ')"
    ) -join "&& "
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
    if (-not (Wait-ExpoBundleReady)) {
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

if (Select-String -LiteralPath $ExpoErr -Pattern "unable to sign manifest" -Quiet -ErrorAction SilentlyContinue) {
    throw "Expo manifest signing failed. Do not use --offline mode for Expo Go."
}

$lanMetroOk = if ($UseTunnel) { $true } else { Test-LanMetroReachable -HostIp $LanIp }
$tunnelHint = ""
if (-not $lanMetroOk) {
    $tunnelHint = @"

LAN WARNING: Metro is not reachable at http://${LanIp}:$ExpoPort from this PC.
Your phone may show 'There was a problem running the requested app'.
Retry with tunnel mode:
  .\Start-MobilePhoneMode.ps1 -RestartExpo -UseTunnel
"@
}

@"
Anai native phone mode
Backend URL: $BackendUrl
Expo URL:    $ExpoUrl
LAN Metro:   $(if ($UseTunnel) { 'skipped (tunnel mode)' } elseif ($lanMetroOk) { 'reachable' } else { 'NOT reachable - use -UseTunnel' })

Open Expo Go on the phone and enter:
$ExpoUrl

Requirements:
- Expo Go updated for SDK 54 (same major SDK as package.json)
- If LAN fails, rerun with: Start-MobilePhoneMode.ps1 -RestartExpo -UseTunnel
- Phone and PC on the same Wi-Fi for LAN mode
- Allow inbound Windows Firewall ports TCP $BackendPort and TCP $ExpoPort
  (run as Admin once: .\Allow-AnaiTranslatorFirewall.ps1)
$tunnelHint
"@ | Set-Content -LiteralPath $SummaryPath -Encoding ascii

Write-Output "Backend URL: $BackendUrl"
Write-Output "Expo URL:    $ExpoUrl"
Write-Output "Summary:     $SummaryPath"

if ($missingFirewallPorts.Count -gt 0) {
    Write-Output ""
    Write-Output ">>> FIREWALL REQUIRED (phone will NOT connect without this) <<<"
    Write-Output "Open PowerShell as Administrator and run:"
    Write-Output "  .\Allow-AnaiTranslatorFirewall.ps1"
    Write-Output "Missing inbound TCP: $($missingFirewallPorts -join ', ')"
}

$qrScript = Join-Path $MobileRoot "node_modules\qrcode-terminal\bin\qrcode-terminal.js"
if (Test-Path -LiteralPath $qrScript) {
    & node $qrScript $ExpoUrl
}
