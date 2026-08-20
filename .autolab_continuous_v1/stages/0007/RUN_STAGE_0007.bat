@echo off
title AutoLab Continuous V1 - Stage 0007 Discovery Tournament
py.exe -3 "%~dp0RESEARCH_STAGE0007.py"
set RC=%ERRORLEVEL%
if "%RC%"=="0" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0CLEANUP_AFTER_STAGE0007.ps1" -CurrentFolder "AUTOLAB_STAGE_0007_DISCOVERY_RESEARCH"
)
exit /b %RC%
