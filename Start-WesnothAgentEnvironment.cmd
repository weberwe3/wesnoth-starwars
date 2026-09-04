@echo off
setlocal
set "DISTRO=Ubuntu-24.04"
set "PROJECT=/home/willj/projects/wesnoth-starwars"
set "SECURE_LAUNCHER=%LOCALAPPDATA%\WesnothAgentManager\Start-WesnothAgentShell.ps1"

if not exist "%SECURE_LAUNCHER%" (
  echo Secure launcher not found: %SECURE_LAUNCHER%
  exit /b 1
)

wsl.exe -d "%DISTRO%" --cd "%PROJECT%" -e /bin/bash ./agent/dashboard/start-dashboard.sh
if errorlevel 1 exit /b %errorlevel%

start "" "http://127.0.0.1:8765"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SECURE_LAUNCHER%"
exit /b %errorlevel%

