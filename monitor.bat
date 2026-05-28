@echo off
title Google Maps Monitor Dashboard
cd /d "%~dp0"
python monitor\app.py
if errorlevel 1 (
    echo.
    echo Failed to start. Run setup.bat first.
    pause
)
