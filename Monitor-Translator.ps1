param(
    [string]$BaseUrl = "",
    [int]$IntervalSeconds = 60,
    [switch]$RestartOnFailure,
    [switch]$HealthOnly,
    [switch]$Once
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Logs = Join-Path $Root "logs"
$MonitorLog = Join-Path $Logs "product-monitor.jsonl"
$CurrentUrlPath = Join-Path $Logs "current-phone-url.txt"
$SmokeScript = Join-Path $Root "scripts\product_smoke_test.py"
$Python = Join-Path $Root "venv\Scripts\python.exe"

New-Item -ItemType Directory -Force -Path $Logs | Out-Null
$lastStatus = "unknown"

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

function Get-CurrentPhoneUrl {
    if ($BaseUrl) {
        return $BaseUrl.Trim()
    }
    if (Test-Path -LiteralPath $CurrentUrlPath) {
        $saved = (Get-Content -LiteralPath $CurrentUrlPath -Raw).Trim()
        if ($saved) {
            return $saved
        }
    }
    $paths = @(
        (Join-Path $Logs "tunnel.err.log"),
        (Join-Path $Logs "tunnel.out.log"),
        (Join-Path $Logs "fixed-phone-tunnel.out.log"),
        (Join-Path $Logs "localhost-run-tunnel.out.log"),
        (Join-Path $Logs "manual-localtunnel.out.log")
    )
    $match = Select-String -Path $paths -Pattern "https://[a-z0-9-]+\.(trycloudflare\.com|loca\.lt)|https://[a-z0-9]+\.lhr\.life" -AllMatches -ErrorAction SilentlyContinue |
        ForEach-Object { $_.Matches.Value } |
        Select-Object -Last 1
    return $match
}

function Write-MonitorEvent {
    param([hashtable]$Event)
    $Event.time = (Get-Date).ToString("o")
    ($Event | ConvertTo-Json -Compress -Depth 5) | Out-File -FilePath $MonitorLog -Append -Encoding utf8
}

function Test-NormalBrowserPath {
    param([string]$Url)
    try {
        $uri = [System.Uri]$Url
        Resolve-DnsName -Name $uri.Host -ErrorAction Stop | Out-Null
        $health = Invoke-RestMethod -Uri "$($Url.TrimEnd('/'))/health" -TimeoutSec 12
        if ($health.ready -eq $true -or $health.status -eq "ok") {
            return @{ ok = $true }
        }
        return @{ ok = $false; error = "Health endpoint returned not-ready: $($health | ConvertTo-Json -Compress -Depth 3)" }
    } catch {
        return @{ ok = $false; error = $_.Exception.Message }
    }
}

function Invoke-SmokeSuite {
    param([string]$Url)
    $cases = @(
        @{ source = "ht"; target = "ru"; phrase = "Mesi anpil"; expected = $null },
        @{ source = "en"; target = "fr"; phrase = "Hello"; expected = "Bonjour.|Bonjour" }
    )
    $outputs = @()
    foreach ($case in $cases) {
        $testArgs = @(
            $SmokeScript,
            "--base-url", $Url,
            "--require-embedded",
            "--timeout", "70",
            "--source", $case.source,
            "--target", $case.target,
            "--phrase", $case.phrase
        )
        if ($case.expected) {
            $testArgs += @("--expected", $case.expected)
        }
        $testArgs += "--no-doh"
        $output = & $Python @testArgs 2>&1
        if ($LASTEXITCODE -ne 0) {
            return @{
                ok = $false
                case = "$($case.source)->$($case.target)"
                output = ($output | Out-String).Trim()
            }
        }
        $outputs += ($output | Out-String).Trim()
    }
    return @{
        ok = $true
        output = "[" + ($outputs -join ",") + "]"
    }
}

while ($true) {
    $url = Get-CurrentPhoneUrl
    if (-not $url) {
        $lastStatus = "fail"
        Write-MonitorEvent @{ status = "fail"; error = "No phone URL found." }
        if ($RestartOnFailure) {
            & (Join-Path $Root "Start-Translator.ps1") -Restart -SkipBuild
        }
    } else {
        $pathCheck = Test-NormalBrowserPath -Url $url
        if (-not $pathCheck.ok) {
            $lastStatus = "fail"
            Write-MonitorEvent @{ status = "fail"; url = $url; case = "normal-dns-health"; error = $pathCheck.error }
            if ($RestartOnFailure) {
                & (Join-Path $Root "Start-Translator.ps1") -Restart -SkipBuild
                $BaseUrl = ""
            }
        } elseif ($HealthOnly) {
            $lastStatus = "pass"
            Write-MonitorEvent @{ status = "pass"; url = $url; result = "normal DNS and health OK" }
        } else {
            $smoke = Invoke-SmokeSuite -Url $url
            if ($smoke.ok) {
                $lastStatus = "pass"
                Write-MonitorEvent @{ status = "pass"; url = $url; result = $smoke.output }
            } else {
                $lastStatus = "fail"
                Write-MonitorEvent @{ status = "fail"; url = $url; case = $smoke.case; error = $smoke.output }
                if ($RestartOnFailure) {
                    & (Join-Path $Root "Start-Translator.ps1") -Restart -SkipBuild
                    $BaseUrl = ""
                }
            }
        }
    }

    if ($Once) {
        break
    }
    Start-Sleep -Seconds $IntervalSeconds
}

if ($Once -and $lastStatus -ne "pass") {
    exit 1
}
