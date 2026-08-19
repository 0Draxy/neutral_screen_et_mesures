@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_AND_RUN_V017.ps1"
exit /b %errorlevel%
