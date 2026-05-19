$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
Write-Host "=== Deploy v7: mic level meter + drop ONNX leftover ===" -ForegroundColor Cyan
@(".git\index.lock") | ForEach-Object { if (Test-Path $_) { try { Remove-Item -Force $_ } catch {} } }
git status --short
git add backend/api.py frontend/src/main.jsx
try { git commit -m "feat: live mic level meter while recording (mic-meter-v5)" } catch { Write-Host "nothing to commit" }
git push origin main
Write-Host "=== Done ===" -ForegroundColor Green
[void][System.Console]::ReadLine()
