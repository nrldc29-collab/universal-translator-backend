$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
Write-Host "=== Deploy v10: Haitian Creole + recover V9 (mic meter / copy buttons / Spanish voice) ===" -ForegroundColor Cyan
@(".git\index.lock") | ForEach-Object { if (Test-Path $_) { try { Remove-Item -Force $_ } catch {} } }

# Pre-push integrity check — catches the silent-truncation issue where files
# end mid-statement before commit. If any of these fail, ABORT before touching git.
Write-Host "--- Integrity check ---" -ForegroundColor Yellow
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
        $reason = ""
        if (-not $hasMarker) { $reason += " missing marker '" + $c.MustContain + "'" }
        if (-not $endsOk) { $reason += " bad tail (must end '" + $c.TailMustEnd + "', got '" + $trimmed.Substring([Math]::Max(0,$trimmed.Length-40)) + "')" }
        Write-Host ("  FAIL " + $c.Path + $reason) -ForegroundColor Red
        $failed = $true
    }
}
if ($failed) {
    Write-Host "ABORT: one or more files failed integrity check. Do NOT commit corrupted files." -ForegroundColor Red
    Write-Host "Likely cause: OneDrive sync or antivirus is silently truncating saves. Try moving the project off OneDrive (e.g. C:\dev\universal-translator)." -ForegroundColor Yellow
    [void][System.Console]::ReadLine(); exit 1
}

git status --short
git add backend/api.py backend/config.py translation/marian_translator.py tts/piper_tts.py Dockerfile frontend/src/main.jsx frontend/public/sw.js
try { git commit -m "feat: add Haitian Creole target language with eSpeak NG TTS + recover V9 (haitian-creole-v10)" } catch { Write-Host "nothing to commit" }
git push origin main
Write-Host "=== Done. Railway build will take ~10-12 min ===" -ForegroundColor Green
[void][System.Console]::ReadLine()
