@echo off
setlocal
cd /d "%~dp0"

echo.
echo === AUTOLAB CONTINUOUS V1 - STAGE 0011 ===
echo DISCOVERY ONLY - SERIAL DEPENDENCE / SIGN SEQUENCES
echo VALIDATION LOCKED - NO LIVE
echo HYPOTHESES = 30 (TECHNICAL COUNT FIX)
echo.

where py.exe >nul 2>&1
if not errorlevel 1 goto use_py

where python.exe >nul 2>&1
if not errorlevel 1 goto use_python

echo ERREUR : Python introuvable.
exit /b 99

:use_py
py.exe -3 "%~dp0RUN_STAGE0011_PATCH.py"
set "RC=%ERRORLEVEL%"
exit /b %RC%

:use_python
python.exe "%~dp0RUN_STAGE0011_PATCH.py"
set "RC=%ERRORLEVEL%"
exit /b %RC%
