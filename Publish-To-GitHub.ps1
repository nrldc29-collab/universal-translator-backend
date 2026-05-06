param(
    [string]$RepoUrl = "",
    [string]$RemoteName = "origin",
    [string]$Branch = "main",
    [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Git = "C:\Program Files\Git\cmd\git.exe"

if (-not (Test-Path $Git)) {
    throw "Git for Windows was not found at $Git"
}

Set-Location $Root

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & $Git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path (Join-Path $Root ".git"))) {
    throw "This folder is not a Git repository: $Root"
}

$currentBranch = (& $Git branch --show-current).Trim()
if ($currentBranch -and $currentBranch -ne $Branch) {
    Write-Output "Current branch is '$currentBranch'. Renaming it to '$Branch'."
    Invoke-Git branch -M $Branch
}

$status = (& $Git status --short)
if ($status -and -not $AllowDirty) {
    Write-Output "There are uncommitted files:"
    $status | ForEach-Object { Write-Output "  $_" }
    throw "Commit or discard local changes first, or rerun with -AllowDirty if you really want to push as-is."
}

if (-not $RepoUrl) {
    Write-Output ""
    Write-Output "Create an empty GitHub repo first:"
    Write-Output "  https://github.com/new"
    Write-Output ""
    Write-Output "Good name: universal-translator"
    Write-Output "Do not add a README, .gitignore, or license on GitHub because this repo already has files."
    Write-Output ""
    $RepoUrl = Read-Host "Paste the GitHub repo URL, for example https://github.com/YOURNAME/universal-translator.git"
}

if (-not $RepoUrl) {
    throw "A GitHub repo URL is required."
}

$existingRemote = (& $Git remote)
if ($existingRemote -contains $RemoteName) {
    Write-Output "Updating remote '$RemoteName' to $RepoUrl"
    Invoke-Git remote set-url $RemoteName $RepoUrl
} else {
    Write-Output "Adding remote '$RemoteName' as $RepoUrl"
    Invoke-Git remote add $RemoteName $RepoUrl
}

Write-Output "Pushing $Branch to $RemoteName..."
Invoke-Git push -u $RemoteName $Branch

Write-Output ""
Write-Output "GitHub publish complete."
Write-Output "Next: open Railway, choose Deploy from GitHub, and select this repository."
