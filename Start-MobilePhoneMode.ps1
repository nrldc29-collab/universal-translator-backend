param(
    [string]$LanIp = "",
    [int]$BackendPort = 8000,
    [int]$ExpoPort = 8081,
    [switch]$RestartExpo
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

if (-not $LanIp) {
    $LanIp = Get-PreferredLanIp
}

$BackendUrl = "http://$LanIp`:$BackendPort"
$ExpoUrl = "exp://$LanIp`:$ExpoPort"

Set-Content -LiteralPath $EnvPath -Encoding ascii -Value @(
    "EXPO_PUBLIC_API_URL=$BackendUrl",
    "EXPO_PUBLIC_DEBUG_LOGS=1"
)

if (-not (Test-HttpOk "$BackendUrl/health")) {
    & (Join-Path $Root "Start-Translator.ps1") -SkipBuild -NoTunnel
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

if (-not $expoStatusOk) {
    Remove-Item -LiteralPath $ExpoOut, $ExpoErr -Force -ErrorAction SilentlyContinue
    $env:EXPO_PUBLIC_API_URL = $BackendUrl
    $env:EXPO_PUBLIC_DEBUG_LOGS = "1"
    $env:EXPO_NO_TELEMETRY = "1"
    $env:EXPO_OFFLINE = "1"
    $env:REACT_NATIVE_PACKAGER_HOSTNAME = $LanIp
    $process = Start-Process -FilePath "cmd.exe" `
        -ArgumentList @("/c", "npx.cmd expo start --offline --port $ExpoPort --clear") `
        -WorkingDirectory $MobileRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $ExpoOut `
        -RedirectStandardError $ExpoErr `
        -PassThru
    Set-Content -LiteralPath $ExpoPidPath -Value $process.Id -Encoding ascii
    Start-Sleep -Seconds 8
}

@"
Anai native phone mode
Backend URL: $BackendUrl
Expo URL:    $ExpoUrl

Open Expo Go on the phone and enter:
$ExpoUrl

If the phone cannot connect, keep the app running and allow these inbound Windows Firewall ports:
- TCP $BackendPort for backend
- TCP $ExpoPort for Expo Metro
"@ | Set-Content -LiteralPath $SummaryPath -Encoding ascii

Write-Output "Backend URL: $BackendUrl"
Write-Output "Expo URL:    $ExpoUrl"
Write-Output "Summary:     $SummaryPath"

$qrScript = Join-Path $MobileRoot "node_modules\qrcode-terminal\bin\qrcode-terminal.js"
if (Test-Path -LiteralPath $qrScript) {
    & node $qrScript $ExpoUrl
}
