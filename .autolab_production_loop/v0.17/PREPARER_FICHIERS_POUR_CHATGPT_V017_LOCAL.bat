@echo off
cd /d "%~dp0"
py.exe -3 "%~dp0autolab_v017_local.py" --bundle-only
pause
