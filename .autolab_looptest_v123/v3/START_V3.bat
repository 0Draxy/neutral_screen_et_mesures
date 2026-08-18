@echo off
cd /d "%~dp0"
echo ============================================================
echo  START_V3.BAT - PSEUDO ROUTINE V3
echo ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN_V3.ps1"
set "RC=%ERRORLEVEL%"
echo.
echo START_V3.BAT termine - code=%RC%
exit /b %RC%
