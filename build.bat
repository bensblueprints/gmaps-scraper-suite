@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set ROOT=%~dp0

echo ==========================================
echo  Google Maps Scraper Suite - Build All EXEs
echo ==========================================
echo.

echo [1] Installing dependencies...
pip install customtkinter playwright pyinstaller --quiet
if errorlevel 1 goto error

echo [2] Getting paths...
for /f "delims=" %%P in ('python -c "import customtkinter, os; print(os.path.dirname(customtkinter.__file__))"') do set CTK=%%P
for /f "delims=" %%P in ('python -c "import playwright, os; print(os.path.dirname(playwright.__file__))"') do set PWL=%%P
if "!CTK!"=="" goto error
if "!PWL!"=="" goto error

echo       CTK: !CTK!
echo       PWL: !PWL!

echo.
echo [3] Cleaning previous builds...
if exist dist rmdir /s /q dist
mkdir dist

echo.
echo [4] Building LeadScraperPro.exe ...
pyinstaller --onefile --windowed --noconfirm ^
  --name "LeadScraperPro" ^
  --add-data "!CTK!;customtkinter" --add-data "!PWL!;playwright" ^
  --paths "!ROOT!" --paths "!ROOT!scraper_node" ^
  --collect-all "playwright" ^
  --hidden-import "shared" --hidden-import "shared.config" --hidden-import "shared.machine_id" ^
  --hidden-import "engine" --hidden-import "industries" --hidden-import "gmaps_scraper" ^
  --hidden-import "tkinter" --hidden-import "tkinter.ttk" ^
  "!ROOT!scraper_node\app.py"
if errorlevel 1 goto error

echo.
echo [5] Building Discovery1.exe ...
pyinstaller --onefile --windowed --noconfirm ^
  --name "Discovery1" ^
  --add-data "!CTK!;customtkinter" --add-data "!PWL!;playwright" ^
  --paths "!ROOT!" --paths "!ROOT!scraper_node" ^
  --collect-all "playwright" ^
  --hidden-import "shared" --hidden-import "shared.config" --hidden-import "shared.machine_id" ^
  --hidden-import "discovery1.industries" ^
  --hidden-import "engine" --hidden-import "tkinter" --hidden-import "tkinter.ttk" ^
  "!ROOT!discovery1\app.py"
if errorlevel 1 goto error

echo.
echo [6] Building ProspectHunter.exe ...
pyinstaller --onefile --windowed --noconfirm ^
  --name "ProspectHunter" ^
  --add-data "!CTK!;customtkinter" --add-data "!PWL!;playwright" ^
  --paths "!ROOT!" --paths "!ROOT!scraper_node" ^
  --collect-all "playwright" ^
  --hidden-import "shared" --hidden-import "shared.config" --hidden-import "shared.machine_id" ^
  --hidden-import "prospecthunter.industries" ^
  --hidden-import "engine" --hidden-import "tkinter" --hidden-import "tkinter.ttk" ^
  "!ROOT!prospecthunter\app.py"
if errorlevel 1 goto error

echo.
echo [7] Building AtomicScraper.exe ...
pyinstaller --onefile --windowed --noconfirm ^
  --name "AtomicScraper" ^
  --add-data "!CTK!;customtkinter" --add-data "!PWL!;playwright" ^
  --paths "!ROOT!" --paths "!ROOT!scraper_node" ^
  --collect-all "playwright" ^
  --hidden-import "shared" --hidden-import "shared.config" --hidden-import "shared.machine_id" ^
  --hidden-import "atomicscraper.industries" ^
  --hidden-import "engine" --hidden-import "tkinter" --hidden-import "tkinter.ttk" ^
  "!ROOT!atomicscraper\app.py"
if errorlevel 1 goto error

echo.
echo [8] Building LeadsBaby.exe ...
pyinstaller --onefile --windowed --noconfirm ^
  --name "LeadsBaby" ^
  --add-data "!CTK!;customtkinter" --add-data "!PWL!;playwright" ^
  --paths "!ROOT!" --paths "!ROOT!scraper_node" ^
  --collect-all "playwright" ^
  --hidden-import "shared" --hidden-import "shared.config" --hidden-import "shared.machine_id" ^
  --hidden-import "leadsbaby.industries" ^
  --hidden-import "engine" --hidden-import "tkinter" --hidden-import "tkinter.ttk" ^
  "!ROOT!leadsbaby\app.py"
if errorlevel 1 goto error

echo.
echo ==========================================
echo  BUILD COMPLETE
echo ==========================================
echo.
dir /b dist\*.exe 2>nul
echo.
echo  All EXEs are in: dist\
echo  Download links will be:
echo    dist\LeadScraperPro.exe     (lead-scraper-pro)
echo    dist\Discovery1.exe         (discoveryoneleads.com)
echo    dist\ProspectHunter.exe     (prospecthunter)
echo    dist\AtomicScraper.exe      (atomicscraper.com)
echo    dist\LeadsBaby.exe          (leads.baby)
echo ==========================================
pause
goto end

:error
echo.
echo BUILD FAILED - see errors above.
pause

:end
