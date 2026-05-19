$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
Write-Host "=== Deploy v5: stale-frontend detection ===" -ForegroundColor Cyan
@(".git\index.lock") | ForEach-Object { if (Test-Path $_) { try { Remove-Item -Force $_ } catch {} } }
git status --short
git add -A frontend/src/main.jsx
try { git commit -m "feat: auto-detect stale frontend vs backend release mismatch with reload banner" } catch { Write-Host "nothing to commit" }
git push origin main
Write-Host "=== Done ===" -ForegroundColor Green
[void][System.Console]::ReadLine()
