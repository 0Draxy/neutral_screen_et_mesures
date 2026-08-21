@echo off
setlocal
cd /d "%~dp0"

echo.
echo === AUTOLAB CONTINUOUS V1 - STAGE 0010 ===
echo DISCOVERY ONLY - LOCAL BAR STRUCTURE
echo VALIDATION LOCKED - NO LIVE
echo.

where py.exe >nul 2>&1
if %errorlevel%==0 (
  py.exe -3 "%~dp0RUN_STAGE0010_PATCH.py"
  exit /b %errorlevel%
)

where python.exe >nul 2>&1
if %errorlevel%==0 (
  python.exe "%~dp0RUN_STAGE0010_PATCH.py"
  exit /b %errorlevel%
)

echo ERREUR : Python introuvable.
exit /b 99
