param(
    [string]$Distro = "Ubuntu-24.04",
    [string]$ProjectLinuxPath = "/home/willj/projects/wesnoth-starwars",
    [switch]$Once
)

$ErrorActionPreference = "Stop"

if ($Distro -notmatch '^[A-Za-z0-9._-]+$' -or
    $ProjectLinuxPath -notmatch '^/[A-Za-z0-9._/-]+$' -or
    $ProjectLinuxPath.Contains('..')) {
    throw "Unsafe control-bridge configuration."
}

$secureLauncher = Join-Path $env:LOCALAPPDATA "WesnothAgentManager\Start-WesnothAgentShell.ps1"
$mutex = [Threading.Mutex]::new($false, "Local\WesnothAgentControlBridge")

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
            $info.EnvironmentVariables["WSLENV"] = if ($existingWslEnv) {
                "$existingWslEnv`:BASH_ENV"
            } else {
                "BASH_ENV"
            }
            $process = [Diagnostics.Process]::Start($info)
            $process.StandardInput.Close()
            if (-not $process.WaitForExit(1200000)) {
                $process.Kill()
                throw "Secure ticket runner timed out."
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
    }
}
finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
