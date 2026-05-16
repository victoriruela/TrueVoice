@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0debug_launcher.ps1"
endlocal
