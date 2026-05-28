@echo off
title Google Maps Scraper Node
cd /d "%~dp0"
python scraper_node\app.py
if errorlevel 1 (
    echo.
    echo Failed to start. Run setup.bat first.
    pause
)
