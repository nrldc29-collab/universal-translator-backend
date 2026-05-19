$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
Write-Host "=== Deploy v9: meter responsiveness + copy button placement + es_MX-claude-high voice ===" -ForegroundColor Cyan
@(".git\index.lock") | ForEach-Object { if (Test-Path $_) { try { Remove-Item -Force $_ } catch {} } }
git status --short
git add backend/api.py tts/piper_tts.py Dockerfile frontend/src/main.jsx frontend/public/sw.js
try { git commit -m "tune: snappier mic meter, copy button bottom-right, upgrade Spanish to es_MX-claude-high (tune-v9)" } catch { Write-Host "nothing to commit" }
git push origin main
Write-Host "=== Done. Railway build will take ~10-12 min (new 63MB voice) ===" -ForegroundColor Green
[void][System.Console]::ReadLine()
