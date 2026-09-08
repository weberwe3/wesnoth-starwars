@echo off
setlocal EnableExtensions

rem Launch the campaign from the exact published origin/main add-on revision.
rem The launcher never silently opens a stale userdata snapshot or unpublished
rem local game content. It synchronizes a clean local main, then mirrors only
rem that verified add-on into isolated Wesnoth test userdata.
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

rem Published-and-tested play must never be mixed with uncommitted content.
set "SOURCE_DIRTY="
for /f "delims=" %%I in ('wsl.exe -d %DISTRO% -- git -C %PROJECT_LINUX% status --porcelain --untracked-files=all') do set "SOURCE_DIRTY=1"
if defined SOURCE_DIRTY (
  echo Refusing to launch: local main has unpublished changes.
  echo Publish or discard those changes before using the published play launcher.
  exit /b 4
)

rem Refresh the remote publication reference, then advance only by a safe
rem fast-forward. A divergent checkout is preserved and reported instead of
rem being reset or overwritten by the launcher.
wsl.exe -d %DISTRO% -- git -C %PROJECT_LINUX% fetch --quiet origin main
if errorlevel 1 (
  echo Could not refresh the published origin/main reference.
  exit /b 5
)
for /f "delims=" %%I in ('wsl.exe -d %DISTRO% -- git -C %PROJECT_LINUX% rev-parse origin/main') do set "PUBLISHED_SHA=%%I"
if not defined PUBLISHED_SHA (
  echo Could not identify the published main revision.
  exit /b 6
)
for /f "delims=" %%I in ('wsl.exe -d %DISTRO% -- git -C %PROJECT_LINUX% rev-parse HEAD') do set "MAIN_SHA=%%I"
if not defined MAIN_SHA (
  echo Could not identify the current main revision.
  exit /b 7
)
if /i not "%MAIN_SHA%"=="%PUBLISHED_SHA%" (
  echo Synchronizing local main to published revision %PUBLISHED_SHA%...
  wsl.exe -d %DISTRO% -- git -C %PROJECT_LINUX% merge --ff-only origin/main
  if errorlevel 1 (
    echo Refusing to launch: local main cannot fast-forward to published main.
    exit /b 8
  )
  for /f "delims=" %%I in ('wsl.exe -d %DISTRO% -- git -C %PROJECT_LINUX% rev-parse HEAD') do set "MAIN_SHA=%%I"
)
if /i not "%MAIN_SHA%"=="%PUBLISHED_SHA%" (
  echo Refusing to launch: local main does not match published origin/main.
  exit /b 9
)
for /f "delims=" %%I in ('wsl.exe -d %DISTRO% -- wslpath -w %PROJECT_LINUX%/addons/%ADDON_ID%') do set "ADDON_SOURCE=%%I"
if not exist "%ADDON_SOURCE%\_main.cfg" (
  echo The current main add-on source is unavailable.
  exit /b 10
)

if not exist "%USERDATA%\data\add-ons" mkdir "%USERDATA%\data\add-ons"
if not exist "%USERDATA%\data\add-ons" (
  echo Could not prepare the isolated Wesnoth test userdata.
  exit /b 11
)

rem /MIR is deliberately limited to this one add-on directory. It removes stale
rem map/config files, but never touches saves, preferences, logs, or other add-ons.
robocopy "%ADDON_SOURCE%" "%ADDON_TARGET%" /MIR /COPY:DAT /DCOPY:T /R:2 /W:1 /XJ /NFL /NDL /NJH /NJS >nul
if errorlevel 8 (
  echo Could not refresh the test add-on from local main.
  exit /b 12
)
if not exist "%ADDON_TARGET%\_main.cfg" (
  echo The refreshed add-on is incomplete.
  exit /b 13
)

rem A concurrent publication must not race the mirror step. In that case the
rem next launch will refresh the newer revision rather than opening ambiguity.
for /f "delims=" %%I in ('wsl.exe -d %DISTRO% -- git -C %PROJECT_LINUX% rev-parse HEAD') do set "SOURCE_AFTER_COPY_SHA=%%I"
if /i not "%SOURCE_AFTER_COPY_SHA%"=="%MAIN_SHA%" (
  echo The published source changed while the add-on was being refreshed.
  echo Launch it again to mirror the new published revision.
  exit /b 14
)

set "LAUNCH_MANIFEST=%USERDATA%\wesnoth-starwars-launch.txt"
> "%LAUNCH_MANIFEST%" (
  echo add-on=%ADDON_ID%
  echo published_main=%MAIN_SHA%
  echo source=%PROJECT_LINUX%
)
echo Launching Star Wars: Thrawn Trilogy from published main %MAIN_SHA%.
if /i "%WESNOTH_PLAY_VALIDATE_ONLY%"=="1" (
  echo Validation-only mode: the add-on was refreshed and the launch was not started.
  exit /b 0
)
start "Wesnoth Star Wars" /wait "%WESNOTH_EXE%" --userdata-dir "%USERDATA%" --campaign "%ADDON_ID%"
set "EXIT_CODE=%ERRORLEVEL%"
exit /b %EXIT_CODE%
