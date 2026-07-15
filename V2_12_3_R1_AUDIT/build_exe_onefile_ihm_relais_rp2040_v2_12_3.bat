@echo off
setlocal EnableExtensions
chcp 65001 >nul

title BUILD EXE UNIQUE - NEUTRAL SCREEN V2.12.3
cd /d "%~dp0"

set "APP_NAME=neutral_screen_v2_12_3"
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

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "%APP_NAME%.spec" del /q "%APP_NAME%.spec"

set "EXTRA_DATA=--add-data %UI_FILE%;. --add-data %SCENARIOS_FILE%;."

%PYTHON_CMD% -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "%APP_NAME%" ^
    %EXTRA_DATA% ^
    --hidden-import tkinter ^
    --hidden-import tkinter.simpledialog ^
    --hidden-import tkinter.messagebox ^
    --collect-submodules serial ^
    "%PY_FILE%"
if errorlevel 1 goto :error

for %%F in (
    "README_PACK_V2_12_3.md"
    "CHANGELOG_V2_12_3.md"
    "FICHIERS_MODIFIES_V2_12_3.md"
    "PROMPT_VERIFICATION_CLAUDE_V2_12_3.txt"
    "CAHIER_DES_CHARGES_AUDIT_IA_NEUTRAL_SCREEN_V2_12_3.md"
    "CORRECTION_SECURITE_EA_PLAUSIBILITE_V2_12_3.md"
    "CORRECTION_RAMPES_EA_V2_12_3.md"
    "CORRECTION_CAPTURE_PREMIER_PASSAGE_V2_12_3.md"
    "CABLAGE_FILS_A_FILS_V2_12_3.md"
    "DOCUMENTATION_IA_PROJET_RELAIS_RP2040_V2_12_3_ETALONNAGE_TENSION.md"
    "PROCEDURE_ETALONNAGE_TENSION_V2_12_3.md"
    "SOFTWARE_TESTS_V2_12_3.txt"
    "FINAL_TEST_OUTPUT_V2_12_3.txt"
    "VALIDATION_V2_12_3.txt"
    "MANIFEST_SHA256_V2_12_3.txt"
    "SCHEMA_SQLITE_V2_12_3.sql"
    "test_capture_premier_passage_v2_12_3.py"
    "test_securite_ea_plausibilite_v2_12_3.py"
    "rp2040_relais_28vdc_precision_v2_12_3_ADS1115_GP26_RGB.ino"
    "requirements.txt"
    "schema_cablage_initial.jpg"
    "RP2040-Zero_03.jpg"
) do if exist %%F copy /Y %%F "dist\" >nul

if exist "production_essais.sqlite3" copy /Y "production_essais.sqlite3" "dist\" >nul
if exist "chronometrie_contacts.sqlite3" copy /Y "chronometrie_contacts.sqlite3" "dist\" >nul
if exist "%SCENARIOS_FILE%" copy /Y "%SCENARIOS_FILE%" "dist\" >nul

echo.
echo EXE cree : %CD%\dist\%APP_NAME%.exe
explorer "%CD%\dist"
pause
exit /b 0

:error
echo.
echo ERREUR : construction interrompue.
pause
exit /b 1
