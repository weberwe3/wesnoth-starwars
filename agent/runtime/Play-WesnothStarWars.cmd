@echo off
setlocal EnableExtensions
rem Local game launcher: native Git replaces WSL process transport.
rem This preserves protected-main, clean-source and isolated-mirror checks.
set "PROJECT_WINDOWS=\\wsl.localhost\Ubuntu-24.04\home\willj\projects\wesnoth-starwars"
set "PROJECT_LINUX=/home/willj/projects/wesnoth-starwars"
rem An operator running tests in a worktree may inherit Git selectors.
rem Pin this local process to the actual published source checkout.
set "GIT_DIR=%PROJECT_WINDOWS%\.git"
set "GIT_WORK_TREE=%PROJECT_WINDOWS%"
set "GIT_COMMON_DIR="
set "GIT_INDEX_FILE="
set "GIT_OBJECT_DIRECTORY="
set "GIT_ALTERNATE_OBJECT_DIRECTORIES="
set "GIT_NAMESPACE="
set "GIT_EXE=C:\Users\willj\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe"
set "GIT_TERMINAL_PROMPT=0"
set "GCM_INTERACTIVE=Never"
set "ADDON_ID=Star_Wars_Thrawn_Trilogy"
set "USERDATA=%LOCALAPPDATA%\WesnothStarWarsTest\userdata"
set "ADDON_TARGET=%USERDATA%\data\add-ons\%ADDON_ID%"
set "ADDON_SOURCE=%PROJECT_WINDOWS%\addons\%ADDON_ID%"
set "CHECKS_DIR=%LOCALAPPDATA%\WesnothStarWarsTest\launcher-checks"
set "CHECK_FILE=%CHECKS_DIR%\sync-%RANDOM%-%RANDOM%.txt"
set "WESNOTH_EXE=%ProgramFiles(x86)%\Battle for Wesnoth 1.19.27\wesnoth.exe"
if not exist "%WESNOTH_EXE%" set "WESNOTH_EXE=%ProgramFiles%\Battle for Wesnoth 1.19.27\wesnoth.exe"
if not exist "%WESNOTH_EXE%" set "WESNOTH_EXE=%ProgramFiles(x86)%\Battle for Wesnoth\wesnoth.exe"
if not exist "%WESNOTH_EXE%" set "WESNOTH_EXE=%ProgramFiles%\Battle for Wesnoth\wesnoth.exe"
if not exist "%WESNOTH_EXE%" exit /b 2
if not exist "%GIT_EXE%" exit /b 3
if /i not "%USERDATA%"=="C:\Users\willj\AppData\Local\WesnothStarWarsTest\userdata" (
  echo Refusing to mirror outside the explicit local player userdata.
  exit /b 4
)
if not exist "%CHECKS_DIR%" mkdir "%CHECKS_DIR%"
if not exist "%CHECKS_DIR%" exit /b 4
if exist "%CHECK_FILE%" exit /b 4
"%GIT_EXE%" -c "safe.directory=%PROJECT_WINDOWS%" -c core.autocrlf=false -c core.filemode=false -C "%PROJECT_WINDOWS%" branch --show-current > "%CHECK_FILE%"
if errorlevel 1 exit /b 5
set "MAIN_BRANCH="
set /p MAIN_BRANCH=<"%CHECK_FILE%"
if /i not "%MAIN_BRANCH%"=="main" (
  echo Refusing to launch: the source checkout is not on protected main.
  exit /b 6
)
"%GIT_EXE%" -c "safe.directory=%PROJECT_WINDOWS%" -c core.autocrlf=false -c core.filemode=false -C "%PROJECT_WINDOWS%" status --porcelain --untracked-files=all > "%CHECK_FILE%"
if errorlevel 1 exit /b 7
for %%Z in ("%CHECK_FILE%") do if %%~zZ GTR 0 exit /b 7
if errorlevel 1 (
  echo Refusing to launch: local main has unpublished changes.
  exit /b 7
)
"%GIT_EXE%" -c "safe.directory=%PROJECT_WINDOWS%" -c core.autocrlf=false -c core.filemode=false -C "%PROJECT_WINDOWS%" fetch --quiet origin main
if errorlevel 1 exit /b 8
"%GIT_EXE%" -c "safe.directory=%PROJECT_WINDOWS%" -c core.autocrlf=false -c core.filemode=false -C "%PROJECT_WINDOWS%" rev-parse origin/main > "%CHECK_FILE%"
if errorlevel 1 exit /b 8
set "PUBLISHED_SHA="
set /p PUBLISHED_SHA=<"%CHECK_FILE%"
if not defined PUBLISHED_SHA exit /b 8
"%GIT_EXE%" -c "safe.directory=%PROJECT_WINDOWS%" -c core.autocrlf=false -c core.filemode=false -C "%PROJECT_WINDOWS%" merge --ff-only origin/main
if errorlevel 1 (
  echo Refusing to launch: local main cannot fast-forward to published main.
  exit /b 9
)
"%GIT_EXE%" -c "safe.directory=%PROJECT_WINDOWS%" -c core.autocrlf=false -c core.filemode=false -C "%PROJECT_WINDOWS%" rev-parse HEAD > "%CHECK_FILE%"
if errorlevel 1 exit /b 9
set "MAIN_SHA="
set /p MAIN_SHA=<"%CHECK_FILE%"
if /i not "%MAIN_SHA%"=="%PUBLISHED_SHA%" exit /b 9
if not exist "%ADDON_SOURCE%\_main.cfg" exit /b 10
rem Canonical boundary and ancestor reparse checks occur before /MIR.
rem This is a read-only inline check; no execution policy is changed.
powershell.exe -NoLogo -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop';$s=[IO.Path]::GetFullPath($env:ADDON_SOURCE);$t=[IO.Path]::GetFullPath($env:ADDON_TARGET);$u=[IO.Path]::GetFullPath($env:USERDATA);if($s -ine ($env:PROJECT_WINDOWS+'\addons\'+$env:ADDON_ID) -or [IO.Path]::GetDirectoryName($t) -ine ($u+'\data\add-ons') -or [IO.Path]::GetFileName($t) -cne $env:ADDON_ID){exit 1};foreach($p in @($s,$t)){while($p){if(Test-Path -LiteralPath $p){if(((Get-Item -LiteralPath $p -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){exit 1}};$next=[IO.Path]::GetDirectoryName($p);if($next -eq $p){break};$p=$next}};exit 0"
if errorlevel 1 (
  echo Refusing an unsafe source or destination for the addon mirror.
  exit /b 11
)
if not exist "%USERDATA%\data\add-ons" mkdir "%USERDATA%\data\add-ons"
if not exist "%USERDATA%\data\add-ons" exit /b 11
robocopy "%ADDON_SOURCE%" "%ADDON_TARGET%" /MIR /COPY:DAT /DCOPY:T /R:2 /W:1 /XJ /NFL /NDL /NJH /NJS >nul
if errorlevel 8 exit /b 12
if not exist "%ADDON_TARGET%\_main.cfg" exit /b 13
"%GIT_EXE%" -c "safe.directory=%PROJECT_WINDOWS%" -c core.autocrlf=false -c core.filemode=false -C "%PROJECT_WINDOWS%" rev-parse HEAD > "%CHECK_FILE%"
if errorlevel 1 exit /b 14
set "AFTER_SHA="
set /p AFTER_SHA=<"%CHECK_FILE%"
if /i not "%AFTER_SHA%"=="%MAIN_SHA%" exit /b 14
"%GIT_EXE%" -c "safe.directory=%PROJECT_WINDOWS%" -c core.autocrlf=false -c core.filemode=false -C "%PROJECT_WINDOWS%" rev-parse origin/main > "%CHECK_FILE%"
if errorlevel 1 exit /b 14
set "AFTER_SHA="
set /p AFTER_SHA=<"%CHECK_FILE%"
if /i not "%AFTER_SHA%"=="%MAIN_SHA%" exit /b 14
"%GIT_EXE%" -c "safe.directory=%PROJECT_WINDOWS%" -c core.autocrlf=false -c core.filemode=false -C "%PROJECT_WINDOWS%" status --porcelain --untracked-files=all > "%CHECK_FILE%"
if errorlevel 1 exit /b 14
for %%Z in ("%CHECK_FILE%") do if %%~zZ GTR 0 exit /b 14
if errorlevel 1 exit /b 14
> "%USERDATA%\wesnoth-starwars-launch.txt" (
  echo add-on=%ADDON_ID%
  echo published_main=%MAIN_SHA%
  echo source=%PROJECT_LINUX%
)
echo Refreshed Star Wars: Thrawn Trilogy from published main %MAIN_SHA%.
if /i "%WESNOTH_PLAY_VALIDATE_ONLY%"=="1" (
  echo Validation-only mode: the published add-on was refreshed and the launch was not started.
  exit /b 0
)
start "Wesnoth Star Wars" /wait "%WESNOTH_EXE%" --userdata-dir "%USERDATA%" --campaign "%ADDON_ID%"
exit /b %ERRORLEVEL%
