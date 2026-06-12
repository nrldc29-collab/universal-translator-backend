param(
    [string]$LanIp = "",
    [int]$BackendPort = 8000,
    [int]$ExpoPort = 8082,
    [int]$MobileHttpsPort = 8443
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Logs = Join-Path $Root "logs"
$HttpsPidPath = Join-Path $Logs "backend-https.pid"
$OpenSslPath = "C:\Program Files\Git\usr\bin\openssl.exe"

function Stop-HttpsPortOwner {
    param([int]$Port)
    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        $processId = $listener.OwningProcess
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
        if (-not $proc -or $proc.CommandLine -notmatch "backend\.api:app") {
            continue
        }
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
}

New-Item -ItemType Directory -Force -Path $Logs | Out-Null

function Get-PreferredLanIpLocal {
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

if (-not $LanIp) {
    $LanIp = Get-PreferredLanIpLocal
}
if (-not $LanIp) {
    Write-Warning "Could not detect LAN IP for HTTPS mobile server."
    return $false
}

function Get-OpenSslExeLocal {
    if (Test-Path -LiteralPath $OpenSslPath) { return $OpenSslPath }
    $cmd = Get-Command openssl -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Ensure-MobileHttpsCertLocal {
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
    $openssl = Get-OpenSslExeLocal
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

function Test-HttpsOkLocal {
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

$material = Ensure-MobileHttpsCertLocal -HostIp $LanIp
if (-not $material) { return $false }

$fwScript = Join-Path $Root "Allow-AnaiTranslatorFirewall.ps1"
if (Test-Path -LiteralPath $fwScript) {
    try {
        & $fwScript -BackendPort $BackendPort -ExpoPort $ExpoPort -HttpsPort $MobileHttpsPort
    } catch {
        Write-Warning "Could not ensure firewall rule for HTTPS port $MobileHttpsPort."
    }
}

if (Test-Path -LiteralPath $HttpsPidPath) {
    $savedHttpsPid = (Get-Content -LiteralPath $HttpsPidPath -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($savedHttpsPid -and -not (Get-Process -Id $savedHttpsPid -ErrorAction SilentlyContinue)) {
        if (Get-NetTCPConnection -LocalPort $MobileHttpsPort -State Listen -ErrorAction SilentlyContinue) {
            Write-Output "Stale HTTPS backend PID $savedHttpsPid - cleaning port $MobileHttpsPort."
            Stop-HttpsPortOwner -Port $MobileHttpsPort
        }
    }
}

if (Get-NetTCPConnection -LocalPort $MobileHttpsPort -State Listen -ErrorAction SilentlyContinue) {
    $lanHttpsOk = Test-HttpsOkLocal "https://${LanIp}:$MobileHttpsPort/health"
    if ((Test-HttpsOkLocal "https://127.0.0.1:$MobileHttpsPort/health") -and $lanHttpsOk) {
        Write-Output "HTTPS mobile server already running on port $MobileHttpsPort"
        Write-Output "Safari mic:  https://$LanIp`:$MobileHttpsPort/mobile/app"
        return $true
    }
    if (-not $lanHttpsOk) {
        Stop-HttpsPortOwner -Port $MobileHttpsPort
        Start-Sleep -Seconds 1
    }
}

$python = Join-Path $Root "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    Write-Warning "Missing venv Python - cannot start HTTPS mobile server."
    return $false
}

$httpsOut = Join-Path $Logs "backend-https.out.log"
$httpsErr = Join-Path $Logs "backend-https.err.log"
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
    if (Test-HttpsOkLocal "https://127.0.0.1:$MobileHttpsPort/health") {
        $connectPath = Join-Path $Logs "mobile-connect.json"
        $webHttps = "https://$LanIp`:$MobileHttpsPort/mobile/app"
        $backendHttps = "https://$LanIp`:$MobileHttpsPort"
        if (Test-Path -LiteralPath $connectPath) {
            try {
                $info = Get-Content -LiteralPath $connectPath -Raw | ConvertFrom-Json
                $info | Add-Member -NotePropertyName backend_https_url -NotePropertyValue $backendHttps -Force
                $info | Add-Member -NotePropertyName web_app_https_url -NotePropertyValue $webHttps -Force
                $info | Add-Member -NotePropertyName https_port -NotePropertyValue $MobileHttpsPort -Force
                $info | ConvertTo-Json | Set-Content -LiteralPath $connectPath -Encoding utf8
            } catch {
                # mobile-connect.json may be absent or locked.
            }
        }
        Write-Output "HTTPS mobile server started on port $MobileHttpsPort"
        Write-Output "Safari mic:  $webHttps"
        return $true
    }
    Start-Sleep -Seconds 1
}

Write-Warning "HTTPS mobile server did not become ready on port $MobileHttpsPort."
return $false
