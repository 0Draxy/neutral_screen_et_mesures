@echo off
cd /d "%~dp0"
py.exe -3 "%~dp0autolab_v015_local.py" --bundle-only
pause
