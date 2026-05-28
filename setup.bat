@echo off
title Google Maps Scraper Suite - Setup
echo ============================================
echo  Google Maps Scraper Suite - Setup
echo ============================================
echo.

echo [1/3] Installing Scraper Node dependencies...
pip install -r scraper_node\requirements.txt
if errorlevel 1 goto error

echo.
echo [2/3] Installing Monitor dependencies...
pip install -r monitor\requirements.txt
if errorlevel 1 goto error

echo.
echo [3/3] Creating output directories...
if not exist "output" mkdir output
if not exist "queries" mkdir queries
if not exist "bin" mkdir bin

echo.
echo ============================================
echo  Setup complete!
echo.
echo  NEXT STEP: Run the Scraper Node app and
echo  click "Download Binary" to get the scraper.
echo.
echo  Then run:
echo    scraper.bat   - to launch Scraper Node
echo    monitor.bat   - to launch Monitor
echo ============================================
pause
goto end

:error
echo.
echo ERROR: Setup failed. Make sure Python is installed.
echo Get Python from: https://python.org/downloads
pause

:end
