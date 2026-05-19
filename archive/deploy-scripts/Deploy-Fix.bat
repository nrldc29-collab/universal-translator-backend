@echo off
REM Deploy-Fix.bat — double-click to push the iOS audio fix to Railway.
cd /d "%~dp0"

echo === Universal Translator: iOS audio fix deploy ===
echo.

echo 1) Removing stale lock files and leftover .new buffers...
del /F /Q ".git\index.lock" 2>nul
del /F /Q "backend\streaming.py.new" 2>nul
del /F /Q "backend\api.py.new" 2>nul
del /F /Q "speech\__init__.py.new" 2>nul
del /F /Q "speech\whisper_stt.py.new" 2>nul
del /F /Q "speech\silero_vad.py.new" 2>nul
del /F /Q "frontend\src\main.jsx.new" 2>nul
del /F /Q "frontend\public\sw.js.new" 2>nul

echo.
echo 2) git status:
git status --short

echo.
echo 3) Staging all changes...
git add -A

echo.
echo 4) Committing...
git commit -m "fix iOS audio: HTTP record-and-upload, ffmpeg transcode fallback, SW cache bust (ios-audio-fix-v3)"

echo.
echo 5) Pushing to origin/main...
git push origin main

echo.
echo === Done. Railway will rebuild in ~2 minutes. ===
echo.
echo Then on your iPhone:
echo   1. iOS Settings -^> Safari -^> Clear History and Website Data (one time)
echo   2. Reopen the app URL
echo   3. Open Debug Panel - you should see "Build: ios-audio-fix-v3"
echo   4. Tap mic, speak, tap mic again
echo.
pause
