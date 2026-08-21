@echo off
setlocal
cd /d "%~dp0"

echo.
echo === AUTOLAB CONTINUOUS V1 - STAGE 0011 ===
echo DISCOVERY ONLY - SERIAL DEPENDENCE / SIGN SEQUENCES
echo VALIDATION LOCKED - NO LIVE
echo.

where py.exe >nul 2>&1
if not errorlevel 1 goto USE_PY

where python.exe >nul 2>&1
if not errorlevel 1 goto USE_PYTHON

echo ERREUR : Python introuvable.
exit /b 99

:USE_PY
py.exe -3 "%~dp0RESEARCH_STAGE0011.py"
set "RC=%ERRORLEVEL%"
exit /b %RC%

:USE_PYTHON
python.exe "%~dp0RESEARCH_STAGE0011.py"
set "RC=%ERRORLEVEL%"
exit /b %RC%
