@echo off
setlocal
cd /d "%~dp0"

:: Clear Mark-of-the-Web so the script is not blocked by SmartScreen / execution policy
powershell -NoProfile -Command "try { Unblock-File -Path '%~dp0launcher.ps1' -ErrorAction SilentlyContinue } catch {}" >nul 2>&1

echo Task Cultivation Timer - Launcher
echo.

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher.ps1"

echo.
echo Launcher finished. Exit code: %errorlevel%
echo Press any key to close this window...
pause >nul
