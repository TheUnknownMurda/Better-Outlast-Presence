@echo off
title Better Outlast Presence
cd /d "%~dp0"

python -c "import pypresence" 2>nul
if errorlevel 1 (
    echo pypresence is missing, installing it...
    python -m pip install -r requirements.txt || goto :fail
)

python main.py
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo Better Outlast Presence stopped with an error.
pause
