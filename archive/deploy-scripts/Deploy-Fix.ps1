# Deploy-Fix.ps1
# Run this from PowerShell to push the iOS audio fix to Railway.
# Right-click the file > "Run with PowerShell", or open PowerShell here and run:  .\Deploy-Fix.ps1

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "=== Universal Translator: iOS audio fix deploy ===" -ForegroundColor Cyan

Write-Host ""
Write-Host "1) Removing stale lock files and leftover .new buffers..." -ForegroundColor Yellow
$leftovers = @(
    ".git\index.lock",
    "backend\streaming.py.new",
    "backend\api.py.new",
    "speech\__init__.py.new",
    "speech\whisper_stt.py.new",
    "speech\silero_vad.py.new",
    "frontend\src\main.jsx.new",
    "frontend\public\sw.js.new"
)
foreach ($file in $leftovers) {
    if (Test-Path $file) {
        try {
            Remove-Item -Force $file -ErrorAction Stop
            Write-Host "   removed $file" -ForegroundColor DarkGray
        } catch {
            Write-Host "   could not remove $file ($($_.Exception.Message))" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "2) git status (sanity check):" -ForegroundColor Yellow
git status --short

Write-Host ""
Write-Host "3) Staging all changes..." -ForegroundColor Yellow
git add -A

Write-Host ""
Write-Host "4) Committing..." -ForegroundColor Yellow
$msg = "fix iOS audio: HTTP record-and-upload, ffmpeg transcode fallback, SW cache bust (ios-audio-fix-v3)"
try {
    git commit -m $msg
} catch {
    Write-Host "   commit failed (maybe nothing to commit): $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "5) Pushing to origin/main..." -ForegroundColor Yellow
git push origin main

Write-Host ""
Write-Host "=== Done. Railway should rebuild in ~2 minutes. ===" -ForegroundColor Green
Write-Host ""
Write-Host "Then on your iPhone:" -ForegroundColor Cyan
Write-Host "  1. iOS Settings -> Safari -> Clear History and Website Data (one time, to evict the old service worker)"
Write-Host "  2. Reopen the app URL"
Write-Host "  3. Open the Debug Panel - you should see 'Build: ios-audio-fix-v3'"
Write-Host "  4. Tap mic, speak, tap mic again to stop"
Write-Host ""
Write-Host "Press Enter to close..."
[void][System.Console]::ReadLine()
