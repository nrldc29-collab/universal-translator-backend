$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host ""
Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host " Migrate universal-translator off OneDrive (one-time, safe)"     -ForegroundColor Cyan
Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Plan:"
Write-Host "  1. Run integrity check on current working tree."
Write-Host "  2. Commit + push V10 to GitHub (only if integrity passes)."
Write-Host "  3. Clone fresh at the new non-OneDrive path."
Write-Host "  4. Print final manual steps (re-select folder in Cowork)."
Write-Host ""

# ---------- Step 0: configuration ----------
$RepoUrl  = "https://github.com/nrldc29-collab/universal-translator-backend.git"
$NewPath  = "C:\dev\universal-translator"
$Branch   = "main"

Write-Host "Old path: $PSScriptRoot" -ForegroundColor DarkGray
Write-Host "New path: $NewPath" -ForegroundColor DarkGray
Write-Host ""
$confirm = Read-Host "Continue? Type YES to proceed (anything else aborts)"
if ($confirm -ne "YES") { Write-Host "Aborted." -ForegroundColor Yellow; exit 0 }

# ---------- Step 1: integrity check ----------
Write-Host ""
Write-Host "--- Step 1: integrity check ---" -ForegroundColor Yellow
$checks = @(
    @{ Path = "backend/api.py";                    MustContain = 'RELEASE_ID = "2026-05-10-haitian-creole-v10"';  TailMustEnd = ')' }
    @{ Path = "backend/config.py";                 MustContain = '"ht": "Haitian Creole"';                         TailMustEnd = ')' }
    @{ Path = "translation/marian_translator.py";  MustContain = '"ht": "hat_Latn"';                                TailMustEnd = 'translated' }
    @{ Path = "tts/piper_tts.py";                  MustContain = 'ESPEAK_LANGUAGES = {"ht"}';                       TailMustEnd = ')' }
    @{ Path = "Dockerfile";                        MustContain = "espeak-ng";                                       TailMustEnd = ']' }
    @{ Path = "frontend/src/main.jsx";             MustContain = "TARGET_LANGUAGE_OPTIONS";                          TailMustEnd = ';' }
    @{ Path = "frontend/public/sw.js";             MustContain = "v10-haitian-creole";                               TailMustEnd = ';' }
)
$failed = $false
foreach ($c in $checks) {
    $content = Get-Content $c.Path -Raw -ErrorAction SilentlyContinue
    if (-not $content) { Write-Host ("  FAIL " + $c.Path + " (missing)") -ForegroundColor Red; $failed = $true; continue }
    $hasMarker = $content.Contains($c.MustContain)
    $trimmed = $content.TrimEnd()
    $endsOk = $trimmed.EndsWith($c.TailMustEnd)
    if ($hasMarker -and $endsOk) {
        Write-Host ("  OK   " + $c.Path) -ForegroundColor Green
    } else {
        Write-Host ("  FAIL " + $c.Path + " (marker=$hasMarker tail=$endsOk)") -ForegroundColor Red
        $failed = $true
    }
}
if ($failed) {
    Write-Host ""
    Write-Host "ABORT: working tree is corrupted. Don't migrate from a bad source." -ForegroundColor Red
    Write-Host "Re-run Claude to repair the files first, THEN re-run this script." -ForegroundColor Yellow
    [void][System.Console]::ReadLine(); exit 1
}

# ---------- Step 2: commit + push V10 ----------
Write-Host ""
Write-Host "--- Step 2: commit + push V10 ---" -ForegroundColor Yellow
@(".git\index.lock") | ForEach-Object { if (Test-Path $_) { try { Remove-Item -Force $_ } catch {} } }
git add backend/api.py backend/config.py translation/marian_translator.py tts/piper_tts.py Dockerfile frontend/src/main.jsx frontend/public/sw.js
$commitMsg = "feat: Haitian Creole + recover V9 (haitian-creole-v10)"
try { git commit -m $commitMsg } catch { Write-Host "  (nothing new to commit)" -ForegroundColor DarkGray }
git push origin $Branch
if ($LASTEXITCODE -ne 0) {
    Write-Host "ABORT: git push failed. Don't migrate before V10 is on GitHub." -ForegroundColor Red
    [void][System.Console]::ReadLine(); exit 1
}
Write-Host "  pushed to $RepoUrl" -ForegroundColor Green

# ---------- Step 3: clone fresh ----------
Write-Host ""
Write-Host "--- Step 3: clone fresh at $NewPath ---" -ForegroundColor Yellow
$parent = Split-Path -Parent $NewPath
if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
if (Test-Path $NewPath) {
    Write-Host "  $NewPath already exists." -ForegroundColor Red
    $r = Read-Host "  Type DELETE to remove it and re-clone, anything else to abort"
    if ($r -ne "DELETE") { [void][System.Console]::ReadLine(); exit 1 }
    Remove-Item -Recurse -Force $NewPath
}
git clone $RepoUrl $NewPath
if ($LASTEXITCODE -ne 0) {
    Write-Host "ABORT: clone failed." -ForegroundColor Red
    [void][System.Console]::ReadLine(); exit 1
}
Write-Host "  cloned" -ForegroundColor Green

# ---------- Step 4: copy untracked but useful files ----------
Write-Host ""
Write-Host "--- Step 4: copy local-only files (.env, models cache) ---" -ForegroundColor Yellow
$copyIfExists = @(".env", ".env.production")
foreach ($f in $copyIfExists) {
    if (Test-Path (Join-Path $PSScriptRoot $f)) {
        Copy-Item (Join-Path $PSScriptRoot $f) (Join-Path $NewPath $f) -Force
        Write-Host "  copied $f"
    }
}

# ---------- Step 5: final instructions ----------
Write-Host ""
Write-Host "===============================================================" -ForegroundColor Green
Write-Host " Migration complete." -ForegroundColor Green
Write-Host "===============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps (manual):"
Write-Host ""
Write-Host "  1. In the Cowork app, re-select the folder so it points to:"
Write-Host "     $NewPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "  2. Verify the new location works by running from there:"
Write-Host "     cd $NewPath" -ForegroundColor Cyan
Write-Host "     .\Deploy-V10-HaitianCreole.ps1" -ForegroundColor Cyan
Write-Host "     (or just check 'git log --oneline -3' shows the haitian-creole-v10 commit)"
Write-Host ""
Write-Host "  3. Once you confirm everything works at the new path, you can"
Write-Host "     safely delete the OLD OneDrive copy at:"
Write-Host "     $PSScriptRoot" -ForegroundColor DarkGray
Write-Host "     (do NOT delete it yet — keep it as a backup until you're sure)"
Write-Host ""
[void][System.Console]::ReadLine()
