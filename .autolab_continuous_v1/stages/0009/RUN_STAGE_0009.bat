@echo off
title AutoLab Continuous V1 - Stage 0009 Upload Recovery v4
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0RECOVER_STAGE0007_UPLOAD_V4.ps1"
exit /b %ERRORLEVEL%
