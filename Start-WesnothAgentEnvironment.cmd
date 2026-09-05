@echo off
setlocal
set "DISTRO=Ubuntu-24.04"
set "PROJECT=/home/willj/projects/wesnoth-starwars"
set "SECURE_LAUNCHER=%LOCALAPPDATA%\WesnothAgentManager\Start-WesnothAgentShell.ps1"
set "CONTROL_BRIDGE=\\wsl.localhost\%DISTRO%\home\willj\projects\wesnoth-starwars\agent\dashboard\control-bridge.ps1"
set "LAN_PROXY=\\wsl.localhost\%DISTRO%\home\willj\projects\wesnoth-starwars\agent\dashboard\lan-view-proxy.ps1"
set "LAN_FIREWALL=\\wsl.localhost\%DISTRO%\home\willj\projects\wesnoth-starwars\agent\dashboard\configure-lan-firewall.ps1"
set "SESSION_WATCHER=\\wsl.localhost\%DISTRO%\home\willj\projects\wesnoth-starwars\agent\dashboard\launcher-session-watcher.ps1"

if not exist "%SECURE_LAUNCHER%" (
  echo Secure launcher not found: %SECURE_LAUNCHER%
  exit /b 1
)

for /f "usebackq delims=" %%I in (`powershell.exe -NoLogo -NoProfile -Command "$addresses=[Net.Dns]::GetHostAddresses([Net.Dns]::GetHostName()) ^| Where-Object { $s=$_.IPAddressToString; $_.AddressFamily -eq [Net.Sockets.AddressFamily]::InterNetwork -and ($s.StartsWith('10.') -or $s.StartsWith('192.168.') -or ($s.StartsWith('172.') -and [int]$s.Split('.')[1] -ge 16 -and [int]$s.Split('.')[1] -le 31)) }; ($addresses ^| Select-Object -First 1).IPAddressToString"`) do set "LAN_IP=%%I"
if not defined LAN_IP (
  echo No private LAN IPv4 address was found. Dashboard startup stopped safely.
  exit /b 1
)
for /f "usebackq delims=" %%I in (`powershell.exe -NoLogo -NoProfile -Command "[guid]::NewGuid().ToString('N')"`) do set "DASHBOARD_SESSION=%%I"
set "WESNOTH_DASHBOARD_LAN_URL=http://%LAN_IP%:8765"
set "WESNOTH_DASHBOARD_SESSION_ID=%DASHBOARD_SESSION%"
if defined WSLENV (
  set "WSLENV=%WSLENV%:WESNOTH_DASHBOARD_LAN_URL/u:WESNOTH_DASHBOARD_SESSION_ID/u"
) else (
  set "WSLENV=WESNOTH_DASHBOARD_LAN_URL/u:WESNOTH_DASHBOARD_SESSION_ID/u"
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$arguments=@('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File','%CONTROL_BRIDGE%','-Distro','%DISTRO%','-ProjectLinuxPath','%PROJECT%','-SessionId','%DASHBOARD_SESSION%'); Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -WindowStyle Hidden"
if errorlevel 1 exit /b %errorlevel%

wsl.exe -d "%DISTRO%" --cd "%PROJECT%" -e /bin/bash ./agent/dashboard/start-dashboard.sh
if errorlevel 1 exit /b %errorlevel%

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%LAN_FIREWALL%" -ListenAddress "%LAN_IP%" -ListenPort 8765
if errorlevel 1 (
  echo Private-LAN firewall access was not configured. The dashboard remains available on localhost.
)
start "" /b powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%LAN_PROXY%" -ListenAddress "%LAN_IP%" -ListenPort 8765 -UpstreamPort 8765 ^>nul 2^>^&1
start "" /b powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SESSION_WATCHER%" -SessionId "%DASHBOARD_SESSION%" ^>nul 2^>^&1

start "" "http://127.0.0.1:8765"
echo LAN dashboard: http://%LAN_IP%:8765
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SECURE_LAUNCHER%"
exit /b %errorlevel%
