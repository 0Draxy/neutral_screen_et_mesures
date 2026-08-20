@echo off
title AutoLab Continuous V1 - Stage 0008 Upload Recovery
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0RECOVER_STAGE0007_UPLOAD_V3.ps1"
exit /b %ERRORLEVEL%
