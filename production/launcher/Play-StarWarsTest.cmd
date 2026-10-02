@echo off
setlocal EnableExtensions
title Star Wars: Thrawn Trilogy - test build

rem Tester launcher. It plays the latest PUBLISHED add-on (origin/main), never
rem the development working tree, so it works while development is in progress
rem and never shows unreviewed content. The add-on is exported read-only with
rem git archive; the checkout, its branches and its files are not touched.
rem Saves and preferences persist in the isolated test userdata below.
rem Installed by Install-StarWarsTestShortcut.ps1 (same folder in the repo).

set "DISTRO=Ubuntu-24.04"
set "PROJECT_LINUX=/home/willj/projects/wesnoth-starwars"
set "ADDON_ID=Star_Wars_Thrawn_Trilogy"
set "EXPORT_LINUX=/tmp/wesnoth-starwars-test-export"
set "USERDATA=%LOCALAPPDATA%\WesnothStarWarsTest\userdata"
set "ADDON_TARGET=%USERDATA%\data\add-ons\%ADDON_ID%"

set "WESNOTH_EXE=%ProgramFiles(x86)%\Battle for Wesnoth\wesnoth.exe"
if not exist "%WESNOTH_EXE%" set "WESNOTH_EXE=%ProgramFiles%\Battle for Wesnoth\wesnoth.exe"
if not exist "%WESNOTH_EXE%" set "WESNOTH_EXE=%ProgramFiles(x86)%\Battle for Wesnoth 1.19.27\wesnoth.exe"
if not exist "%WESNOTH_EXE%" set "WESNOTH_EXE=%ProgramFiles%\Battle for Wesnoth 1.19.27\wesnoth.exe"
if not exist "%WESNOTH_EXE%" (
  echo Battle for Wesnoth 1.19 was not found in Program Files.
  goto :failed
)

echo Checking for the latest published build...
wsl.exe -d %DISTRO% -- git -C %PROJECT_LINUX% fetch --quiet origin main
if errorlevel 1 echo Could not reach GitHub; using the last published build already downloaded.

set "PUBLISHED_SHA="
for /f "delims=" %%I in ('wsl.exe -d %DISTRO% -- git -C %PROJECT_LINUX% rev-parse --verify origin/main') do set "PUBLISHED_SHA=%%I"
if not defined PUBLISHED_SHA (
  echo Could not identify the published build.
  goto :failed
)

rem Export exactly that revision's add-on into a scratch folder inside WSL.
wsl.exe -d %DISTRO% -- bash -c "rm -rf '%EXPORT_LINUX%' && mkdir -p '%EXPORT_LINUX%' && git -C '%PROJECT_LINUX%' archive '%PUBLISHED_SHA%' 'addons/%ADDON_ID%' | tar -x -C '%EXPORT_LINUX%'"
if errorlevel 1 (
  echo Could not export the published add-on.
  goto :failed
)
set "ADDON_SOURCE="
for /f "delims=" %%I in ('wsl.exe -d %DISTRO% -- wslpath -w %EXPORT_LINUX%/addons/%ADDON_ID%') do set "ADDON_SOURCE=%%I"
if not exist "%ADDON_SOURCE%\_main.cfg" (
  echo The exported add-on is incomplete.
  goto :failed
)

if not exist "%USERDATA%\data\add-ons" mkdir "%USERDATA%\data\add-ons"
rem /MIR is limited to this one add-on folder: stale files are removed, but
rem saves, preferences, logs and other add-ons are never touched.
robocopy "%ADDON_SOURCE%" "%ADDON_TARGET%" /MIR /COPY:DAT /DCOPY:T /R:2 /W:1 /XJ /NFL /NDL /NJH /NJS >nul
if errorlevel 8 (
  echo Could not install the add-on into the test userdata.
  goto :failed
)
if not exist "%ADDON_TARGET%\_main.cfg" (
  echo The installed add-on is incomplete.
  goto :failed
)

> "%USERDATA%\wesnoth-starwars-launch.txt" (
  echo add-on=%ADDON_ID%
  echo published_main=%PUBLISHED_SHA%
  echo launcher=tester
)
echo Starting Wesnoth with build %PUBLISHED_SHA:~0,10%.
echo Choose Campaigns on the title screen, then any of the three Thrawn Trilogy campaigns.
if /i "%WESNOTH_PLAY_VALIDATE_ONLY%"=="1" exit /b 0
start "Wesnoth Star Wars" "%WESNOTH_EXE%" --userdata-dir "%USERDATA%"
exit /b 0

:failed
echo.
echo The test build was not started. Press any key to close this window.
pause >nul
exit /b 1
