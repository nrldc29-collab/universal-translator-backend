@echo off
REM Build the step-by-step PDF guide.
REM Double-click this file. It installs reportlab if needed, then generates
REM step-by-step-guide.pdf in the same folder.
REM On success the window closes itself; on error it stays open so you can read it.

setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
    set PY=py -3
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set PY=python
    ) else (
        echo Python is not installed or not on PATH.
        echo Install Python 3.10+ from https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

echo Installing reportlab if needed...
%PY% -m pip install --quiet --disable-pip-version-check reportlab
if %errorlevel% neq 0 (
    echo Failed to install reportlab.
    pause
    exit /b 1
)

echo Building PDF...
%PY% "%~dp0build_guide_pdf.py"
if %errorlevel% neq 0 (
    echo PDF build failed.
    pause
    exit /b 1
)

echo Done.
exit /b 0
