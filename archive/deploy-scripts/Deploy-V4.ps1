$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "=== Force-redeploy v4 ===" -ForegroundColor Cyan

Write-Host "Removing locks/leftovers..." -ForegroundColor Yellow
@(".git\index.lock","backend\streaming.py.new","backend\api.py.new","speech\__init__.py.new","speech\whisper_stt.py.new","speech\silero_vad.py.new","frontend\src\main.jsx.new","frontend\public\sw.js.new") | ForEach-Object {
  if (Test-Path $_) {
    try { Remove-Item -Force $_ -ErrorAction Stop; Write-Host "   removed $_" } catch { Write-Host "   could not remove $_ : $($_.Exception.Message)" -ForegroundColor Red }
  }
}

Write-Host "git status:" -ForegroundColor Yellow
git status --short

Write-Host ""
Write-Host "Staging api.py..." -ForegroundColor Yellow
git add -A backend/api.py

Write-Host "Committing..." -ForegroundColor Yellow
try {
  git commit -m "force redeploy: bump RELEASE_ID to ios-audio-fix-v4"
} catch {
  Write-Host "Commit may have nothing to commit, continuing" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Pushing to origin/main..." -ForegroundColor Yellow
git push origin main

Write-Host ""
Write-Host "=== Done. Watch Railway dashboard for the new deploy. ===" -ForegroundColor Green
Write-Host "Press Enter to close..."
[void][System.Console]::ReadLine()
