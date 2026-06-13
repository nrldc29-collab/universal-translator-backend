param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Username = "",
    [string]$Password = "",
    [int]$TimeoutSec = 30
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BaseUrl = $BaseUrl.TrimEnd("/")

$Python = "python"
$venvPython = Join-Path $Root "venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    $null = & $venvPython -c "import sacremoses" 2>&1
    $venvOk = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prevEap
    if ($venvOk) {
        $Python = $venvPython
    } else {
        Write-Output "Note: venv is missing smoke dependencies; using system python."
    }
}

$SmokeScript = Join-Path $Root "scripts\smoke_local.py"
if (-not (Test-Path $SmokeScript)) {
    Write-Error "Missing smoke script: $SmokeScript"
}

Write-Output ""
Write-Output "Anai Translator smoke test"
Write-Output "Target: $BaseUrl"
Write-Output ""

$args = @($SmokeScript, $BaseUrl)
if ($Username -and $Password) {
    Write-Output "Note: auth credentials are ignored; smoke_local.py uses the demo account."
}

& $Python @args
exit $LASTEXITCODE
