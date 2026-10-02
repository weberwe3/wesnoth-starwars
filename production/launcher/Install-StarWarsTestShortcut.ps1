# Install the tester launcher and its desktop shortcut for the current user.
#
# Copies Play-StarWarsTest.cmd to %LOCALAPPDATA%\WesnothStarWarsTest and puts
# "Star Wars - Thrawn Trilogy (Test)" on the desktop, using the Wesnoth icon.
# Touches nothing else: no credentials, startup entries, or other shortcuts.
# Re-run it to update the installed launcher after it changes.
$ErrorActionPreference = "Stop"

$installDir = Join-Path $env:LOCALAPPDATA "WesnothStarWarsTest"
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
$launcher = Join-Path $installDir "Play-StarWarsTest.cmd"
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "Play-StarWarsTest.cmd") -Destination $launcher -Force

$wesnoth = @(
    (Join-Path ${env:ProgramFiles(x86)} "Battle for Wesnoth\wesnoth.exe"),
    (Join-Path $env:ProgramFiles "Battle for Wesnoth\wesnoth.exe")
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut(
    (Join-Path $desktop "Star Wars - Thrawn Trilogy (Test).lnk"))
$shortcut.TargetPath = $launcher
$shortcut.WorkingDirectory = $installDir
$shortcut.Description = "Play the latest published Star Wars: Thrawn Trilogy test build in Battle for Wesnoth"
$shortcut.WindowStyle = 1  # normal console: shows progress, and any failure message stays visible
if ($wesnoth) { $shortcut.IconLocation = "$wesnoth,0" }
$shortcut.Save()
Write-Output "Installed $launcher and the desktop shortcut."
