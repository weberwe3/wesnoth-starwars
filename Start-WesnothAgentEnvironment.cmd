@echo off
setlocal
set "DISTRO=Ubuntu-24.04"
set "PROJECT=/home/willj/projects/wesnoth-starwars"
set "SECURE_LAUNCHER=%LOCALAPPDATA%\WesnothAgentManager\Start-WesnothAgentShell.ps1"
set "CONTROL_BRIDGE=\\wsl.localhost\%DISTRO%\home\willj\projects\wesnoth-starwars\agent\dashboard\control-bridge.ps1"

if not exist "%SECURE_LAUNCHER%" (
  echo Secure launcher not found: %SECURE_LAUNCHER%
  exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$arguments=@('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File','%CONTROL_BRIDGE%','-Distro','%DISTRO%','-ProjectLinuxPath','%PROJECT%'); Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -WindowStyle Hidden"
if errorlevel 1 exit /b %errorlevel%

wsl.exe -d "%DISTRO%" --cd "%PROJECT%" -e /bin/bash ./agent/dashboard/start-dashboard.sh
if errorlevel 1 exit /b %errorlevel%

start "" "http://127.0.0.1:8765"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SECURE_LAUNCHER%"
exit /b %errorlevel%
