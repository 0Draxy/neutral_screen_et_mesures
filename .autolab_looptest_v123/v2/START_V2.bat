@echo off
cd /d "%~dp0"
echo ============================================================
echo  START_V2.BAT - PSEUDO ROUTINE V2
echo ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN_V2.ps1"
set "RC=%ERRORLEVEL%"
echo.
echo START_V2.BAT termine - code=%RC%
exit /b %RC%
