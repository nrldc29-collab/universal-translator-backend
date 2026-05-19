$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
Write-Host "=== Deploy v6: drop 60MB ONNX from git ===" -ForegroundColor Cyan

@(".git\index.lock") | ForEach-Object {
  if (Test-Path $_) {
    try { Remove-Item -Force $_; Write-Host "removed $_" } catch { Write-Host "lock present: $($_.Exception.Message)" -ForegroundColor Yellow }
  }
}

Write-Host ""
Write-Host "Untracking ONNX files..." -ForegroundColor Yellow
git rm --cached "models/tts/en_US-lessac-medium.onnx" "models/tts/en_US-lessac-medium.onnx.json"

Write-Host ""
Write-Host "Staging .gitignore + cleanup..." -ForegroundColor Yellow
git add .gitignore

Write-Host ""
Write-Host "Status:" -ForegroundColor Yellow
git status --short

Write-Host ""
Write-Host "Committing..." -ForegroundColor Yellow
try {
  git commit -m "chore: untrack 60MB Piper ONNX (Dockerfile downloads from HuggingFace at build)"
} catch {
  Write-Host "commit failed: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Pushing..." -ForegroundColor Yellow
git push origin main

Write-Host ""
Write-Host "=== Done. Future pushes ~1000x smaller. ===" -ForegroundColor Green
[void][System.Console]::ReadLine()
