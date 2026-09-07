@echo off
setlocal EnableExtensions

rem Launch the campaign from an exact copy of the current local main add-on.
rem This prevents the Windows test userdata from retaining a stale map/config
rem while still allowing an owner to playtest locally generated original art.
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
rem Only add-on changes are relevant to this isolated playtest snapshot. The
rem launcher remains main-only, but may stage locally generated art and its
rem manifest/WML wiring before those owner changes are published.
set "LOCAL_ADDON_CHANGES="
for /f "delims=" %%I in ('wsl.exe -d %DISTRO% -- git -C %PROJECT_LINUX% status --porcelain --untracked-files=all -- addons/%ADDON_ID%') do set "LOCAL_ADDON_CHANGES=1"
for /f "delims=" %%I in ('wsl.exe -d %DISTRO% -- git -C %PROJECT_LINUX% rev-parse HEAD') do set "MAIN_SHA=%%I"
if not defined MAIN_SHA (
  echo Could not identify the current main revision.
  exit /b 5
)
for /f "delims=" %%I in ('wsl.exe -d %DISTRO% -- wslpath -w %PROJECT_LINUX%/addons/%ADDON_ID%') do set "ADDON_SOURCE=%%I"
if not exist "%ADDON_SOURCE%\_main.cfg" (
  echo The current main add-on source is unavailable.
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
  echo Could not refresh the test add-on from local main.
  exit /b 8
)
if not exist "%ADDON_TARGET%\_main.cfg" (
  echo The refreshed add-on is incomplete.
  exit /b 9
)

if defined LOCAL_ADDON_CHANGES (
  echo Launching Star Wars: Thrawn Trilogy from local main %MAIN_SHA% with uncommitted add-on changes.
) else (
  echo Launching Star Wars: Thrawn Trilogy from published main %MAIN_SHA%.
)
if /i "%WESNOTH_PLAY_VALIDATE_ONLY%"=="1" (
  echo Validation-only mode: the add-on was refreshed and the launch was not started.
  exit /b 0
)
start "Wesnoth Star Wars" /wait "%WESNOTH_EXE%" --userdata-dir "%USERDATA%" --campaign "%ADDON_ID%"
set "EXIT_CODE=%ERRORLEVEL%"
exit /b %EXIT_CODE%
