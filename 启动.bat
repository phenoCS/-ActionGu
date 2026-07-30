@echo off
setlocal
cd /d "%~dp0"
title XiuXian Timer Launcher

REM Clear Mark-of-the-Web on all files (GitHub ZIP / browser download may flag them)
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem '%~dp0' -Recurse -File | Unblock-File -ErrorAction SilentlyContinue" >nul 2>&1

REM Check for administrator rights
net session >nul 2>&1
if %errorlevel%==0 goto :admin

echo =============================================
echo   XiuXian Timer - Requesting admin rights
echo =============================================
echo.
echo This launcher installs Python on first run.
echo It needs administrator rights (same as v11 FlashTap installer).
echo A UAC prompt will appear - click Yes.
echo.

REM Self-elevate: relaunch this bat as administrator via UAC
powershell -NoLogo -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
exit /b

:admin
echo =============================================
echo   XiuXian Timer - Launcher (admin OK)
echo =============================================
echo.

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher.ps1"
set RC=%errorlevel%

echo.
if %RC% neq 0 (
    echo Launcher finished with errors (code: %RC%)
    echo See the error messages shown above (log: %%TEMP%%\xiuxian-timer-launcher.log)
) else (
    echo Launcher finished successfully.
)
echo.
echo Press any key to close...
pause >nul
exit /b %RC%
