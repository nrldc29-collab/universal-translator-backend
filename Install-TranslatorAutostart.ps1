param(
    [string]$TaskPrefix = "AnaiTranslator",
    [switch]$UseStableTunnel,
    [string]$TunnelName = $env:ANAI_TUNNEL_NAME,
    [string]$TunnelHostname = $env:ANAI_TUNNEL_HOSTNAME,
    [string]$TunnelToken = $env:ANAI_TUNNEL_TOKEN,
    [string]$TunnelTokenFile = $env:ANAI_TUNNEL_TOKEN_FILE,
    [switch]$RunElevated
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PowerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$StartScript = Join-Path $Root "Start-Translator.ps1"
$MonitorScript = Join-Path $Root "Monitor-Translator.ps1"
$StartupFolder = [Environment]::GetFolderPath("Startup")
$Logs = Join-Path $Root "logs"
$StableTunnelEnv = Join-Path $Logs "stable-tunnel.env"
$CurrentPhoneUrlPath = Join-Path $Logs "current-phone-url.txt"

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

function Normalize-PhoneUrl {
    param([string]$Value)
    $normalized = ($Value -replace "/+$", "").Trim()
    if (-not $normalized) {
        return ""
    }
    if ($normalized.StartsWith("http://") -or $normalized.StartsWith("https://")) {
        return $normalized
    }
    return "https://$normalized"
}

Import-KeyValueEnvFile -Path $StableTunnelEnv
if (-not $TunnelName) { $TunnelName = $env:ANAI_TUNNEL_NAME }
if (-not $TunnelHostname) { $TunnelHostname = $env:ANAI_TUNNEL_HOSTNAME }
if (-not $TunnelToken) { $TunnelToken = $env:ANAI_TUNNEL_TOKEN }
if (-not $TunnelTokenFile) { $TunnelTokenFile = $env:ANAI_TUNNEL_TOKEN_FILE }

if (-not (Test-Path -LiteralPath $StartScript)) {
    throw "Missing $StartScript"
}
if (-not (Test-Path -LiteralPath $MonitorScript)) {
    throw "Missing $MonitorScript"
}

$startArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$StartScript`"",
    "-Restart",
    "-SkipBuild"
)

if ($UseStableTunnel) {
    if (-not $TunnelHostname) {
        throw "UseStableTunnel requires TunnelHostname or ANAI_TUNNEL_HOSTNAME."
    }
    $startArgs += @("-TunnelHostname", "`"$TunnelHostname`"")
    if ($TunnelName) {
        $startArgs += @("-TunnelName", "`"$TunnelName`"")
    }
    if ($TunnelToken) {
        $startArgs += @("-TunnelToken", "`"$TunnelToken`"")
    }
    if ($TunnelTokenFile) {
        $startArgs += @("-TunnelTokenFile", "`"$TunnelTokenFile`"")
    }
}

$monitorBaseUrl = ""
if ($UseStableTunnel -and $TunnelHostname) {
    $monitorBaseUrl = Normalize-PhoneUrl -Value $TunnelHostname
} elseif ($env:ANAI_TUNNEL_PROVIDER -eq "localtunnel" -and $env:ANAI_LOCALTUNNEL_SUBDOMAIN) {
    $subdomain = $env:ANAI_LOCALTUNNEL_SUBDOMAIN.Trim()
    $subdomain = $subdomain -replace "^https?://", ""
    $subdomain = $subdomain -replace "\.loca\.lt/?$", ""
    $subdomain = $subdomain -replace "/.*$", ""
    if ($subdomain) {
        $monitorBaseUrl = "https://$subdomain.loca.lt"
    }
} elseif (Test-Path -LiteralPath $CurrentPhoneUrlPath) {
    $monitorBaseUrl = Normalize-PhoneUrl -Value (Get-Content -LiteralPath $CurrentPhoneUrlPath -Raw)
}

$monitorArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$MonitorScript`"",
    "-IntervalSeconds", "120",
    "-RestartOnFailure",
    "-HealthOnly"
)
if ($monitorBaseUrl) {
    $monitorArgs += @("-BaseUrl", "`"$monitorBaseUrl`"")
}

$runLevel = if ($RunElevated) { "Highest" } else { "Limited" }
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel $runLevel
$startTrigger = New-ScheduledTaskTrigger -AtLogOn
$monitorTrigger = New-ScheduledTaskTrigger -AtLogOn
$monitorTrigger.Delay = "PT2M"

$startAction = New-ScheduledTaskAction -Execute $PowerShell -Argument ($startArgs -join " ") -WorkingDirectory $Root
$monitorAction = New-ScheduledTaskAction -Execute $PowerShell -Argument ($monitorArgs -join " ") -WorkingDirectory $Root

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Days 365) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

$installedMode = "scheduled-task"
try {
    Register-ScheduledTask `
        -TaskName "$TaskPrefix-Start" `
        -Action $startAction `
        -Trigger $startTrigger `
        -Principal $principal `
        -Settings $settings `
        -Description "Start Anai Translator product stack at login." `
        -Force `
        -ErrorAction Stop | Out-Null

    Register-ScheduledTask `
        -TaskName "$TaskPrefix-Monitor" `
        -Action $monitorAction `
        -Trigger $monitorTrigger `
        -Principal $principal `
        -Settings $settings `
        -Description "Monitor Anai Translator translated-audio path and restart on failure." `
        -Force `
        -ErrorAction Stop | Out-Null

    Write-Output "Installed scheduled tasks:"
    Write-Output "  $TaskPrefix-Start"
    Write-Output "  $TaskPrefix-Monitor"
} catch {
    $installedMode = "startup-folder"
    New-Item -ItemType Directory -Force -Path $StartupFolder | Out-Null
    $startCmd = Join-Path $StartupFolder "$TaskPrefix-Start.cmd"
    $monitorCmd = Join-Path $StartupFolder "$TaskPrefix-Monitor.cmd"

    @"
@echo off
cd /d "$Root"
start "" /min "$PowerShell" $($startArgs -join " ")
"@ | Set-Content -LiteralPath $startCmd -Encoding ASCII

    @"
@echo off
timeout /t 120 /nobreak >nul
cd /d "$Root"
start "" /min "$PowerShell" $($monitorArgs -join " ")
"@ | Set-Content -LiteralPath $monitorCmd -Encoding ASCII

    Write-Output "Scheduled Tasks were blocked by Windows policy: $($_.Exception.Message)"
    Write-Output "Installed Startup folder launchers instead:"
    Write-Output "  $startCmd"
    Write-Output "  $monitorCmd"
}
Write-Output ""
if ($installedMode -eq "scheduled-task") {
    Write-Output "Run now:"
    Write-Output "  Start-ScheduledTask -TaskName '$TaskPrefix-Start'"
    Write-Output "  Start-ScheduledTask -TaskName '$TaskPrefix-Monitor'"
} else {
    Write-Output "Startup launchers will run at the next Windows login."
}
