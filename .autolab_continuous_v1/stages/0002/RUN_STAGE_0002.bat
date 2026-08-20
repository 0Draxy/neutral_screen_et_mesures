@echo off
title AutoLab Continuous V1 - Stage 0002 Technical Recovery
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0HOTFIX_AND_RUN_STAGE0002.ps1"
exit /b %ERRORLEVEL%
