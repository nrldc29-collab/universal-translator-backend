$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
Write-Host "=== Deploy v8: history persistence + copy buttons + Spanish TTS voice ===" -ForegroundColor Cyan
@(".git\index.lock") | ForEach-Object { if (Test-Path $_) { try { Remove-Item -Force $_ } catch {} } }
git status --short
git add backend/api.py backend/pipeline.py backend/streaming.py tts/piper_tts.py Dockerfile frontend/src/main.jsx
try { git commit -m "feat: persist conversation, copy buttons, Spanish Piper voice (history-copy-v6)" } catch { Write-Host "nothing to commit" }
git push origin main
Write-Host "=== Done ===" -ForegroundColor Green
[void][System.Console]::ReadLine()
