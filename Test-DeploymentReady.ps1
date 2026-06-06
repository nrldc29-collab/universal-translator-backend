param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [switch]$RunSmoke,
    [switch]$RequireClean
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Git = "C:\Program Files\Git\cmd\git.exe"
$Failures = @()
$Warnings = @()

Set-Location $Root

function Add-Pass {
    param([string]$Name, [string]$Detail = "")
    if ($Detail) {
        Write-Output "PASS $Name - $Detail"
    } else {
        Write-Output "PASS $Name"
    }
}

function Add-Warn {
    param([string]$Name, [string]$Detail)
    $script:Warnings += "$Name - $Detail"
    Write-Output "WARN $Name - $Detail"
}

function Add-Fail {
    param([string]$Name, [string]$Detail)
    $script:Failures += "$Name - $Detail"
    Write-Output "FAIL $Name - $Detail"
}

function Test-Check {
    param(
        [string]$Name,
        [scriptblock]$Check
    )
    try {
        $detail = & $Check
        Add-Pass -Name $Name -Detail $detail
    } catch {
        Add-Fail -Name $Name -Detail $_.Exception.Message
    }
}

function Test-WarningCheck {
    param(
        [string]$Name,
        [scriptblock]$Check
    )
    try {
        $detail = & $Check
        Add-Pass -Name $Name -Detail $detail
    } catch {
        Add-Warn -Name $Name -Detail $_.Exception.Message
    }
}

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $output = & $Git @Arguments 2>&1
    $code = $LASTEXITCODE
    return [pscustomobject]@{
        Code = $code
        Output = @($output)
    }
}

Write-Output ""
Write-Output "Anai Translator deployment preflight"
Write-Output "Root: $Root"
Write-Output ""

Test-Check "Git for Windows" {
    if (-not (Test-Path $Git)) {
        throw "Missing $Git"
    }
    (& $Git --version).Trim()
}

Test-Check "Git repository" {
    if (-not (Test-Path (Join-Path $Root ".git"))) {
        throw "This folder is not a Git repository"
    }
    $branch = (& $Git branch --show-current).Trim()
    if (-not $branch) {
        throw "Could not resolve current branch"
    }
    "branch $branch"
}

Test-WarningCheck "Git remote" {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $remote = & $Git remote get-url origin 2>$null
        $remoteCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($remoteCode -ne 0 -or -not $remote) {
        throw "No origin remote yet. Run .\Publish-To-GitHub.ps1 after creating an empty GitHub repo."
    }
    ($remote -join "").Trim()
}

Test-WarningCheck "Working tree" {
    $status = (& $Git status --short)
    if ($status) {
        if ($RequireClean) {
            throw "Uncommitted files exist. Commit them before pushing."
        }
        throw "Uncommitted files exist. This is OK while editing, but commit before pushing."
    }
    "clean"
}

Test-Check "Secret ignore rules" {
    $trackedEnv = @(& $Git ls-files ".env" ".env.*")
    if ($trackedEnv.Count) {
        throw "Tracked env files: $($trackedEnv -join ', ')"
    }
    $ignoredEnv = Invoke-Git check-ignore ".env" ".env.production"
    if ($ignoredEnv.Code -ne 0) {
        throw ".env files are not ignored"
    }
    ".env and .env.production ignored"
}

Test-Check "Tracked secret scan" {
    $secretPatterns = @(
        "hf_[A-Za-z0-9]{30,}",
        "github_pat_[A-Za-z0-9_]{80,}",
        "ghp_[A-Za-z0-9]{30,}",
        "sk-[A-Za-z0-9_-]{20,}",
        "AKIA[0-9A-Z]{16}",
        "-----BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY-----"
    )
    foreach ($pattern in $secretPatterns) {
        $result = Invoke-Git grep "-n" "-I" "-E" "-e" $pattern "--" "."
        if ($result.Code -eq 0) {
            throw "Potential secret matched '$pattern': $($result.Output[0])"
        }
        if ($result.Code -ne 1) {
            throw "git grep failed for '$pattern': $($result.Output -join '; ')"
        }
    }
    "no high-confidence secrets found"
}

Test-Check "Railway files" {
    $required = @("Dockerfile", "railway.json", "requirements-railway.txt", "RAILWAY-DEPLOY.md")
    $missing = $required | Where-Object { -not (Test-Path (Join-Path $Root $_)) }
    if ($missing) {
        throw "Missing: $($missing -join ', ')"
    }
    "required files present"
}

Test-Check "Production frontend bundle path" {
    $dockerfile = Get-Content -Path (Join-Path $Root "Dockerfile") -Raw
    if ($dockerfile -notmatch "frontend-build" -or $dockerfile -notmatch "SERVE_FRONTEND_DIST=1") {
        throw "Dockerfile does not build and serve the frontend bundle"
    }
    $api = Get-Content -Path (Join-Path $Root "backend\api.py") -Raw
    if ($api -notmatch "embedded_dist") {
        throw "Backend diagnostics do not expose embedded_dist mode"
    }
    "Docker builds frontend and FastAPI serves it"
}

Test-Check "Same-origin WebSocket support" {
    $utils = Get-Content -Path (Join-Path $Root "frontend\src\utils.js") -Raw
    $main = Get-Content -Path (Join-Path $Root "frontend\src\main.jsx") -Raw
    if ($utils -notmatch "\.up\.railway\.app") {
        throw "Frontend utils are missing Railway same-origin host detection"
    }
    if ($main -notmatch "wss:") {
        throw "Frontend main.jsx is missing wss:// WebSocket URL handling"
    }
    "Railway app URLs use wss:// same-origin audio"
}

Test-Check "Railway variables helper" {
    if (-not (Test-Path (Join-Path $Root "Get-Railway-Variables.ps1"))) {
        throw "Missing Get-Railway-Variables.ps1"
    }
    $output = powershell -NoProfile -ExecutionPolicy Bypass -File ".\Get-Railway-Variables.ps1" -Username demo -Password test-password
    if ($LASTEXITCODE -ne 0 -or -not ($output | Select-String -SimpleMatch "USERS=demo:test-password")) {
        throw "Railway variable helper did not emit expected variables"
    }
    "generator works"
}

if ($RunSmoke) {
    Test-Check "App smoke test" {
        if (-not (Test-Path (Join-Path $Root "Test-Translator.ps1"))) {
            throw "Missing Test-Translator.ps1"
        }
        $output = powershell -NoProfile -ExecutionPolicy Bypass -File ".\Test-Translator.ps1" -BaseUrl $BaseUrl
        if ($LASTEXITCODE -ne 0 -or -not ($output | Select-String -SimpleMatch "Local smoke check passed.")) {
            throw "Smoke test failed for $BaseUrl"
        }
        "passed for $BaseUrl"
    }
} else {
    Add-Warn -Name "App smoke test" -Detail "Skipped. Rerun with -RunSmoke to test $BaseUrl."
}

Write-Output ""
if ($Failures.Count) {
    Write-Output "Preflight failed:"
    foreach ($failure in $Failures) {
        Write-Output "  $failure"
    }
    exit 1
}

if ($Warnings.Count) {
    Write-Output "Preflight passed with warnings:"
    foreach ($warning in $Warnings) {
        Write-Output "  $warning"
    }
    exit 0
}

Write-Output "Preflight passed."
