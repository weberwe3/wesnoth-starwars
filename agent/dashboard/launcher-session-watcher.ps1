param(
    [Parameter(Mandatory = $true)][string]$SessionId
)

$ErrorActionPreference = "Stop"
if ($SessionId -notmatch '^[A-Za-z0-9-]{8,80}$') {
    throw "Unsafe launcher watcher configuration."
}

$self = Get-CimInstance Win32_Process -Filter "ProcessId=$PID"
$LauncherPid = [int]$self.ParentProcessId
$launcher = Get-Process -Id $LauncherPid -ErrorAction Stop
if ($launcher.ProcessName -ne "cmd") {
    throw "The launcher watcher must be started directly by the associated CMD window."
}

$runtime = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\runtime"))
$marker = Join-Path $runtime "dashboard.shutdown.$SessionId"
while (Get-Process -Id $LauncherPid -ErrorAction SilentlyContinue) {
    if (Test-Path -LiteralPath $marker) {
        & taskkill.exe /PID $LauncherPid /T | Out-Null
        exit 0
    }
    Start-Sleep -Milliseconds 250
}
