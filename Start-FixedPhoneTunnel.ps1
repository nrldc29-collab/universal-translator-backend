param(
    [string]$Subdomain = $env:ANAI_LOCALTUNNEL_SUBDOMAIN,
    [int]$Port = 8000,
    [string]$LocalHost = "127.0.0.1",
    [int]$RestartDelaySeconds = 5
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Logs = Join-Path $Root "logs"
$TunnelOut = Join-Path $Logs "fixed-phone-tunnel.out.log"
$TunnelErr = Join-Path $Logs "fixed-phone-tunnel.err.log"

New-Item -ItemType Directory -Force -Path $Logs | Out-Null

function Get-NodePath {
    $command = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $knownPath = "C:\Program Files\nodejs\node.exe"
    if (Test-Path -LiteralPath $knownPath) {
        return $knownPath
    }
    throw "node.exe was not found. Install Node.js before starting the fixed phone tunnel."
}

function Get-LocalTunnelScript {
    $knownPath = Join-Path $env:APPDATA "npm\node_modules\localtunnel\bin\lt.js"
    if (Test-Path -LiteralPath $knownPath) {
        return $knownPath
    }
    $lt = Get-Command lt.cmd -ErrorAction SilentlyContinue
    if ($lt) {
        $npmRoot = Split-Path -Parent (Split-Path -Parent $lt.Source)
        $candidate = Join-Path $npmRoot "node_modules\localtunnel\bin\lt.js"
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    throw "localtunnel is not installed. Run: npm install -g localtunnel"
}

if (-not $Subdomain) {
    throw "Subdomain is required. Example: -Subdomain anai-translator-nrldc"
}

$Subdomain = $Subdomain.Trim()
$Subdomain = $Subdomain -replace "^https?://", ""
$Subdomain = $Subdomain -replace "\.loca\.lt/?$", ""
$Subdomain = $Subdomain -replace "/.*$", ""

$node = Get-NodePath
$ltScript = Get-LocalTunnelScript
$phoneUrl = "https://$Subdomain.loca.lt"

Add-Content -LiteralPath $TunnelOut -Value "[$(Get-Date -Format o)] fixed phone tunnel target: $phoneUrl -> http://$LocalHost`:$Port"

while ($true) {
    try {
        Add-Content -LiteralPath $TunnelOut -Value "[$(Get-Date -Format o)] starting localtunnel"
        & $node $ltScript --port $Port --subdomain $Subdomain --local-host $LocalHost 2>&1 |
            ForEach-Object {
                $line = "$_"
                if ($line -match "https://[a-z0-9-]+\.loca\.lt") {
                    $publishedUrl = $Matches[0]
                    "[$(Get-Date -Format o)] published phone tunnel: $publishedUrl"
                    if ($publishedUrl -ne $phoneUrl) {
                        Add-Content -LiteralPath $TunnelErr -Value "[$(Get-Date -Format o)] requested $phoneUrl but localtunnel published $publishedUrl"
                    }
                }
                "[$(Get-Date -Format o)] $line"
            } |
            Out-File -LiteralPath $TunnelOut -Append -Encoding utf8
        Add-Content -LiteralPath $TunnelOut -Value "[$(Get-Date -Format o)] localtunnel exited with code $LASTEXITCODE; restarting in $RestartDelaySeconds seconds"
    } catch {
        Add-Content -LiteralPath $TunnelErr -Value "[$(Get-Date -Format o)] $($_.Exception.Message)"
    }
    Start-Sleep -Seconds $RestartDelaySeconds
}
