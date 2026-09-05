param(
    [string]$Distro = "Ubuntu-24.04",
    [string]$ProjectLinuxPath = "/home/willj/projects/wesnoth-starwars",
    [string]$SessionId,
    [switch]$Once
)

$ErrorActionPreference = "Stop"

if ($Distro -notmatch '^[A-Za-z0-9._-]+$' -or
    $ProjectLinuxPath -notmatch '^/[A-Za-z0-9._/-]+$' -or
    $ProjectLinuxPath.Contains('..') -or
    (-not $Once -and $SessionId -notmatch '^[A-Za-z0-9-]{8,80}$')) {
    throw "Unsafe control-bridge configuration."
}

$secureLauncher = Join-Path $env:LOCALAPPDATA "WesnothAgentManager\Start-WesnothAgentShell.ps1"
$mutex = [Threading.Mutex]::new($false, "Local\WesnothAgentControlBridge")
$runtime = Join-Path (Split-Path -Parent $PSScriptRoot) "runtime"
$shutdownMarker = Join-Path $runtime "dashboard.shutdown.$SessionId"
$codexRoot = Join-Path $env:LOCALAPPDATA "OpenAI\Codex\bin"
$codexWindows = Get-ChildItem -LiteralPath $codexRoot -Directory -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    ForEach-Object { Join-Path $_.FullName "codex.exe" } |
    Where-Object {
        (Test-Path -LiteralPath $_ -PathType Leaf) -and
        -not ((Get-Item -LiteralPath $_).Attributes -band [IO.FileAttributes]::ReparsePoint)
    } |
    Select-Object -First 1
$codexLinux = $null
if ($codexWindows) {
    $translated = & wsl.exe -d $Distro -e wslpath -u $codexWindows
    if ($LASTEXITCODE -eq 0) {
        $candidate = [string]($translated | Select-Object -Last 1)
        $candidate = $candidate.Trim()
        if ($candidate -match '^/mnt/[a-z]/Users/[A-Za-z0-9._ -]+/AppData/Local/OpenAI/Codex/bin/[A-Za-z0-9._-]+/codex\.exe$') {
            $codexLinux = $candidate
        }
    }
}

function Invoke-Mailbox([string[]]$MailboxArguments) {
    $output = & wsl.exe -d $Distro --cd $ProjectLinuxPath -e python3 `
        agent/dashboard/bridge_mailbox.py @MailboxArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Bridge mailbox command failed."
    }
    return ($output | Select-Object -Last 1)
}

function Write-Health([string]$State, [string]$Message) {
    Invoke-Mailbox @("heartbeat", $State, $Message) | Out-Null
}

if (-not $mutex.WaitOne(0)) {
    exit 0
}

try {
    while ($true) {
        if (Test-Path -LiteralPath $shutdownMarker) {
            break
        }
        Write-Health "online" "Secure bridge ready"
        if ($Once) {
            break
        }
        $runId = Invoke-Mailbox @("claim")
        if (-not $runId) {
            Start-Sleep -Seconds 1
            continue
        }
        try {
            if ($runId -notmatch '^[a-f0-9]{12}$') {
                throw "Invalid secure-run request."
            }
            $bootstrapLinux = Invoke-Mailbox @("prepare", $runId)
            if (-not $bootstrapLinux.StartsWith("$ProjectLinuxPath/agent/runtime/secure-bootstrap-")) {
                throw "Invalid secure bootstrap path."
            }

            Write-Health "executing" "Deterministic ticket gates running"
            $info = [Diagnostics.ProcessStartInfo]::new()
            $info.FileName = "powershell.exe"
            $info.Arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "' +
                $secureLauncher.Replace('"', '""') + '"'
            $info.UseShellExecute = $false
            $info.CreateNoWindow = $true
            $info.RedirectStandardInput = $true
            $windowsModules = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\Modules"
            $info.EnvironmentVariables["PSModulePath"] =
                "$windowsModules;$($env:PSModulePath)"
            $info.EnvironmentVariables["BASH_ENV"] = $bootstrapLinux
            $existingWslEnv = $info.EnvironmentVariables["WSLENV"]
            $forwardWslEnv = @()
            if ($existingWslEnv) {
                $forwardWslEnv += $existingWslEnv -split ":"
            }
            $forwardWslEnv += "BASH_ENV"
            if ($codexLinux) {
                $info.EnvironmentVariables["WESNOTH_CODEX_EXE"] = $codexLinux
                $forwardWslEnv += "WESNOTH_CODEX_EXE"
            }
            $info.EnvironmentVariables["WSLENV"] = (
                $forwardWslEnv | Where-Object { $_ } | Select-Object -Unique
            ) -join ":"
            $process = [Diagnostics.Process]::Start($info)
            $process.StandardInput.Close()
            $deadline = [DateTime]::UtcNow.AddMinutes(20)
            $cancelMarker = Join-Path $runtime "secure-run-cancel.$runId"
            $shutdownRequested = $false
            while (-not $process.HasExited) {
                if ((Test-Path -LiteralPath $cancelMarker) -or
                    (Test-Path -LiteralPath $shutdownMarker)) {
                    $shutdownRequested = Test-Path -LiteralPath $shutdownMarker
                    & taskkill.exe /PID $process.Id /T /F *> $null
                    $process.WaitForExit(5000) | Out-Null
                    throw "Secure ticket runner was cancelled."
                }
                if ([DateTime]::UtcNow -ge $deadline) {
                    & taskkill.exe /PID $process.Id /T /F *> $null
                    $process.WaitForExit(5000) | Out-Null
                    throw "Secure ticket runner timed out."
                }
                Write-Health "executing" "Deterministic ticket gates running"
                Start-Sleep -Milliseconds 1000
            }
            if ((Invoke-Mailbox @("result", $runId)) -ne "ready") {
                throw "Secure ticket runner returned no structured result."
            }
        }
        catch {
            if ($runId -match '^[a-f0-9]{12}$') {
                Invoke-Mailbox @("failure", $runId) | Out-Null
            }
            Write-Health "error" "Secure bridge stopped the request"
        }
        finally {
            Invoke-Mailbox @("cleanup", $runId) | Out-Null
        }
        if ($shutdownRequested -or (Test-Path -LiteralPath $shutdownMarker)) {
            break
        }
    }
}
finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
