@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set ROOT=%~dp0

echo ==========================================
echo  Google Maps Scraper Suite - Build EXEs
echo ==========================================
echo.

echo [1/5] Installing dependencies...
pip install customtkinter playwright pyinstaller --quiet
if errorlevel 1 goto error

echo [2/5] Getting CustomTkinter path...
for /f "delims=" %%P in ('python -c "import customtkinter, os; print(os.path.dirname(customtkinter.__file__))"') do set CTK=%%P
if "!CTK!"=="" goto error
echo        !CTK!

echo [2b] Getting Playwright path...
for /f "delims=" %%P in ('python -c "import playwright, os; print(os.path.dirname(playwright.__file__))"') do set PWD=%%P
if "!PWD!"=="" goto error
echo        !PWD!

echo.
echo [3/5] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo.
echo [4/5] Building Scraper_Node.exe ...
pyinstaller ^
  --onefile ^
  --windowed ^
  --noconfirm ^
  --name "Scraper_Node" ^
  --add-data "!CTK!;customtkinter" ^
  --add-data "!PWD!;playwright" ^
  --paths "!ROOT!" ^
  --paths "!ROOT!scraper_node" ^
  --collect-all "playwright" ^
  --hidden-import "shared" ^
  --hidden-import "shared.config" ^
  --hidden-import "engine" ^
  --hidden-import "industries" ^
  --hidden-import "gmaps_scraper" ^
  --hidden-import "tkinter" ^
  --hidden-import "tkinter.ttk" ^
  "!ROOT!scraper_node\app.py"
if errorlevel 1 goto error

echo.
echo [5/5] Building Monitor_Dashboard.exe ...
for /f "delims=" %%P in ('python -c "import customtkinter, os; print(os.path.dirname(customtkinter.__file__))"') do set CTK=%%P
pyinstaller ^
  --onefile ^
  --windowed ^
  --noconfirm ^
  --name "Monitor_Dashboard" ^
  --add-data "!CTK!;customtkinter" ^
  --paths "!ROOT!" ^
  --paths "!ROOT!monitor" ^
  --hidden-import "shared" ^
  --hidden-import "shared.config" ^
  --hidden-import "data_manager" ^
  --hidden-import "tkinter" ^
  --hidden-import "tkinter.ttk" ^
  "!ROOT!monitor\app.py"
if errorlevel 1 goto error

echo.
echo ==========================================
echo  BUILD COMPLETE
echo ==========================================
echo.
dir /b dist\*.exe 2>nul
echo.
echo  Both EXEs are in: dist\
echo  On first run of Scraper_Node.exe:
echo    - Chromium is already on this machine
echo    - Click "Chromium Installed" shows green
echo    - Pick industries, set city, START QUEUE
echo ==========================================
pause
goto end

:error
echo.
echo BUILD FAILED - see errors above.
pause

:end
