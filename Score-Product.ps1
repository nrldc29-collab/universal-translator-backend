<#
.SYNOPSIS
    Print Anai product readiness scores (target: 10/10 all dimensions).

.USAGE
    .\Score-Product.ps1
    .\Score-Product.ps1 -BackendUrl "http://127.0.0.1:8000"
    .\Score-Product.ps1 -Full
#>
param(
    [string]$BackendUrl = "http://127.0.0.1:8000",
    [switch]$Full
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$liveArgs = @()
try {
    $health = Invoke-RestMethod -Uri "$BackendUrl/health" -TimeoutSec 6 -ErrorAction Stop
    if ($health.ready -eq $true) {
        $liveArgs = @("--live", $BackendUrl)
    }
} catch {
    # Static-only if backend down.
}

python scripts/product_readiness.py @liveArgs
$scoreExit = $LASTEXITCODE
if ($scoreExit -ne 0) { exit $scoreExit }

if ($Full) {
    powershell -NoProfile -File (Join-Path $Root "scripts\verify_all_product.ps1") -BackendUrl $BackendUrl
    exit $LASTEXITCODE
}
