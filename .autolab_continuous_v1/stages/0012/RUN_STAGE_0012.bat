@echo off
setlocal
cd /d "%~dp0"

echo.
echo === AUTOLAB CONTINUOUS V1 - STAGE 0012 ===
echo DISCOVERY ONLY - WEEKDAY SEASONALITY
echo VALIDATION LOCKED - NO LIVE
echo.

where py.exe >nul 2>&1
if errorlevel 1 goto try_python

py.exe -3 "%~dp0RESEARCH_STAGE0012.py"
set "RC=%ERRORLEVEL%"
exit /b %RC%

:try_python
where python.exe >nul 2>&1
if errorlevel 1 goto no_python

python.exe "%~dp0RESEARCH_STAGE0012.py"
set "RC=%ERRORLEVEL%"
exit /b %RC%

:no_python
echo ERREUR : Python introuvable.
exit /b 99
