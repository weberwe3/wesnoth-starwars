@echo off
setlocal EnableExtensions

rem Launch the campaign from a clean, exact copy of the protected main add-on.
rem This prevents the Windows test userdata from retaining a stale map/config.
set "DISTRO=Ubuntu-24.04"
set "PROJECT_LINUX=/home/willj/projects/wesnoth-starwars"
set "ADDON_ID=Star_Wars_Thrawn_Trilogy"
set "USERDATA=%LOCALAPPDATA%\WesnothStarWarsTest\userdata"
set "ADDON_TARGET=%USERDATA%\data\add-ons\%ADDON_ID%"
set "WESNOTH_EXE=%ProgramFiles(x86)%\Battle for Wesnoth 1.19.27\wesnoth.exe"
if not exist "%WESNOTH_EXE%" set "WESNOTH_EXE=%ProgramFiles%\Battle for Wesnoth 1.19.27\wesnoth.exe"
if not exist "%WESNOTH_EXE%" set "WESNOTH_EXE=%ProgramFiles(x86)%\Battle for Wesnoth\wesnoth.exe"
if not exist "%WESNOTH_EXE%" set "WESNOTH_EXE=%ProgramFiles%\Battle for Wesnoth\wesnoth.exe"

if not exist "%WESNOTH_EXE%" (
  echo Battle for Wesnoth 1.19 executable was not found.
  exit /b 2
)

for /f "delims=" %%I in ('wsl.exe -d %DISTRO% -- git -C %PROJECT_LINUX% branch --show-current') do set "MAIN_BRANCH=%%I"
if /i not "%MAIN_BRANCH%"=="main" (
  echo Refusing to launch: the source checkout is not on protected main.
  exit /b 3
)
for /f "delims=" %%I in ('wsl.exe -d %DISTRO% -- git -C %PROJECT_LINUX% status --porcelain') do set "DIRTY=%%I"
if defined DIRTY (
  echo Refusing to launch: the source checkout has uncommitted changes.
  exit /b 4
)
for /f "delims=" %%I in ('wsl.exe -d %DISTRO% -- git -C %PROJECT_LINUX% rev-parse HEAD') do set "MAIN_SHA=%%I"
if not defined MAIN_SHA (
  echo Could not identify the protected main revision.
  exit /b 5
)
for /f "delims=" %%I in ('wsl.exe -d %DISTRO% -- wslpath -w %PROJECT_LINUX%/addons/%ADDON_ID%') do set "ADDON_SOURCE=%%I"
if not exist "%ADDON_SOURCE%\_main.cfg" (
  echo The protected main add-on source is unavailable.
  exit /b 6
)

if not exist "%USERDATA%\data\add-ons" mkdir "%USERDATA%\data\add-ons"
if not exist "%USERDATA%\data\add-ons" (
  echo Could not prepare the isolated Wesnoth test userdata.
  exit /b 7
)

rem /MIR is deliberately limited to this one add-on directory. It removes stale
rem map/config files, but never touches saves, preferences, logs, or other add-ons.
robocopy "%ADDON_SOURCE%" "%ADDON_TARGET%" /MIR /COPY:DAT /DCOPY:T /R:2 /W:1 /XJ /NFL /NDL /NJH /NJS >nul
if errorlevel 8 (
  echo Could not refresh the test add-on from protected main.
  exit /b 8
)
if not exist "%ADDON_TARGET%\_main.cfg" (
  echo The refreshed add-on is incomplete.
  exit /b 9
)

echo Launching Star Wars: Thrawn Trilogy from main %MAIN_SHA%.
if /i "%WESNOTH_PLAY_VALIDATE_ONLY%"=="1" (
  echo Validation-only mode: the add-on was refreshed and the launch was not started.
  exit /b 0
)
start "Wesnoth Star Wars" /wait "%WESNOTH_EXE%" --userdata-dir "%USERDATA%" --campaign "%ADDON_ID%"
set "EXIT_CODE=%ERRORLEVEL%"
exit /b %EXIT_CODE%
