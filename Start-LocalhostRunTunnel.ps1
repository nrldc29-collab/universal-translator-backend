param(
    [int]$Port = 8000,
    [int]$RestartDelaySeconds = 5
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Logs = Join-Path $Root "logs"
$TunnelOut = Join-Path $Logs "localhost-run-tunnel.out.log"
$TunnelErr = Join-Path $Logs "localhost-run-tunnel.err.log"
$SshOut = Join-Path $Logs "localhost-run-ssh.out.log"
$SshErr = Join-Path $Logs "localhost-run-ssh.err.log"
$CurrentPhoneUrlPath = Join-Path $Logs "current-phone-url.txt"

New-Item -ItemType Directory -Force -Path $Logs | Out-Null

function Get-SshPath {
    $command = Get-Command ssh.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $knownPath = "$env:SystemRoot\System32\OpenSSH\ssh.exe"
    if (Test-Path -LiteralPath $knownPath) {
        return $knownPath
    }
    throw "ssh.exe was not found. Install OpenSSH Client before starting localhost.run tunnel."
}

$ssh = Get-SshPath
Add-Content -LiteralPath $TunnelOut -Value "[$(Get-Date -Format o)] localhost.run tunnel target: https://*.lhr.life -> http://127.0.0.1:$Port"

function Get-PublishedUrl {
    param([string[]]$Paths)
    foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path)) {
            continue
        }
        $match = Select-String -Path $path -Pattern "https://[a-z0-9]+\.lhr\.life" -AllMatches -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty Matches |
            Select-Object -Last 1
        if ($match) {
            return $match.Value
        }
    }
    return $null
}

while ($true) {
    try {
        Add-Content -LiteralPath $TunnelOut -Value "[$(Get-Date -Format o)] starting localhost.run"
        Remove-Item -LiteralPath $SshOut, $SshErr -Force -ErrorAction SilentlyContinue
        $process = Start-Process -FilePath $ssh -ArgumentList @(
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ServerAliveInterval=60",
            "-R", "80:127.0.0.1:$Port",
            "nokey@localhost.run"
        ) -WindowStyle Hidden -RedirectStandardOutput $SshOut -RedirectStandardError $SshErr -PassThru

        $publishedUrl = $null
        $stableChecks = 0
        for ($attempt = 0; $attempt -lt 60; $attempt += 1) {
            Start-Sleep -Seconds 1
            $latestUrl = Get-PublishedUrl -Paths @($SshOut, $SshErr)
            if ($latestUrl -and $latestUrl -ne $publishedUrl) {
                $publishedUrl = $latestUrl
                $stableChecks = 0
                Set-Content -LiteralPath $CurrentPhoneUrlPath -Value $publishedUrl -Encoding ascii
                Add-Content -LiteralPath $TunnelOut -Value "[$(Get-Date -Format o)] published url: $publishedUrl"
            } elseif ($publishedUrl) {
                $stableChecks += 1
                if ($stableChecks -ge 8) {
                    break
                }
            }
            if ($process.HasExited) {
                break
            }
        }

        if (-not $publishedUrl) {
            Add-Content -LiteralPath $TunnelErr -Value "[$(Get-Date -Format o)] localhost.run did not publish a URL before ssh exited or timed out"
        }

        $process.WaitForExit()
        Add-Content -LiteralPath $TunnelOut -Value "[$(Get-Date -Format o)] localhost.run exited with code $($process.ExitCode); restarting in $RestartDelaySeconds seconds"
    } catch {
        Add-Content -LiteralPath $TunnelErr -Value "[$(Get-Date -Format o)] $($_.Exception.Message)"
    }
    Start-Sleep -Seconds $RestartDelaySeconds
}
