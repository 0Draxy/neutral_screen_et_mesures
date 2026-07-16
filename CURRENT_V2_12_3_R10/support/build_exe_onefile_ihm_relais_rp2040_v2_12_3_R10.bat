@echo off
setlocal EnableExtensions
chcp 65001 >nul

title BUILD EXE UNIQUE - NEUTRAL SCREEN V2.12.3 R10
cd /d "%~dp0"

set "APP_NAME=neutral_screen_v2_12_3_R10"
set "PY_FILE=main_ihm_relais_rp2040_v2_12_3.py"
set "UI_FILE=ihm_relais_rp2040_28vdc_precision_v2_12_3.ui"
set "LICENCE_FILE=licence_manager.py"
set "SCENARIOS_FILE=neutral_scenarios.json"

for %%F in ("%PY_FILE%" "%UI_FILE%" "%LICENCE_FILE%" "%SCENARIOS_FILE%" "requirements.txt") do (
    if not exist %%F (
        echo ERREUR : fichier obligatoire introuvable : %%~F
        pause
        exit /b 1
    )
)

set "PYTHON_CMD="
where py >nul 2>nul && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD where python >nul 2>nul && set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
    echo ERREUR : Python introuvable.
    pause
    exit /b 1
)

%PYTHON_CMD% -m pip install --upgrade pip setuptools wheel
%PYTHON_CMD% -m pip install -r requirements.txt
if errorlevel 1 goto :error

%PYTHON_CMD% -m py_compile "%PY_FILE%"
if errorlevel 1 goto :error

%PYTHON_CMD% "test_capture_premier_passage_v2_12_3.py"
if errorlevel 1 goto :error

set "QT_QPA_PLATFORM=offscreen"
%PYTHON_CMD% "test_securite_ea_plausibilite_v2_12_3.py"
if errorlevel 1 goto :error
set "QT_QPA_PLATFORM="

%PYTHON_CMD% "test_integration_chrono_tensions_v2_12_3_R4.py"
if errorlevel 1 goto :error

%PYTHON_CMD% "test_reglages_rampes_leds_v2_12_3_R10.py"
if errorlevel 1 goto :error

%PYTHON_CMD% "test_mesurer_tout_exports_v2_12_3_R10.py"
if errorlevel 1 goto :error

%PYTHON_CMD% "test_mesurer_tout_ea_auto_v2_12_3_R10.py"
if errorlevel 1 goto :error

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "%APP_NAME%.spec" del /q "%APP_NAME%.spec"

%PYTHON_CMD% -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "%APP_NAME%" ^
    --add-data "%UI_FILE%;." ^
    --add-data "%SCENARIOS_FILE%;." ^
    --hidden-import tkinter ^
    --hidden-import tkinter.simpledialog ^
    --hidden-import tkinter.messagebox ^
    --collect-submodules serial ^
    --collect-submodules openpyxl ^
    "%PY_FILE%"
if errorlevel 1 goto :error

mkdir "dist\DOCUMENTATION" 2>nul
mkdir "dist\FIRMWARE" 2>nul
mkdir "dist\AUDIT_R10" 2>nul
mkdir "dist\BASES_REFERENCE_VIDES" 2>nul

copy /Y "README_PACK_V2_12_3_R10_PROPRE.md" "dist\" >nul
copy /Y "LIRE_EN_PREMIER_R10.txt" "dist\" >nul
copy /Y "%SCENARIOS_FILE%" "dist\" >nul
copy /Y "SCHEMA_SQLITE_V2_12_3.sql" "dist\DOCUMENTATION\" >nul
copy /Y "rp2040_relais_28vdc_precision_v2_12_3_ADS1115_GP26_RGB.ino" "dist\FIRMWARE\" >nul
xcopy /E /I /Y "DOCUMENTATION" "dist\DOCUMENTATION" >nul
xcopy /E /I /Y "AUDIT_R10" "dist\AUDIT_R10" >nul
copy /Y "production_essais_REFERENCE_VIDE.sqlite3" "dist\BASES_REFERENCE_VIDES\" >nul
copy /Y "chronometrie_contacts_REFERENCE_VIDE.sqlite3" "dist\BASES_REFERENCE_VIDES\" >nul

echo.
echo EXE cree : %CD%\dist\%APP_NAME%.exe
echo IMPORTANT : les bases de reference vides sont dans dist\BASES_REFERENCE_VIDES.
echo Elles ne remplacent pas vos bases utilisateur.
explorer "%CD%\dist"
pause
exit /b 0

:error
echo.
echo ERREUR : construction interrompue.
pause
exit /b 1
