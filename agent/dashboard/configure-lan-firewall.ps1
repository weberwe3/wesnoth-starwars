param(
    [Parameter(Mandatory = $true)][string]$ListenAddress,
    [int]$ListenPort = 8765,
    [switch]$Elevated
)

$ErrorActionPreference = "Stop"
$ruleName = "WesnothAgentDashboard-LAN"
if ($ListenAddress -notmatch '^(?:\d{1,3}\.){3}\d{1,3}$' -or $ListenPort -lt 1024 -or $ListenPort -gt 65535) {
    throw "Unsafe dashboard firewall configuration."
}

$rule = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
if ($rule) {
    $port = $rule | Get-NetFirewallPortFilter
    $address = $rule | Get-NetFirewallAddressFilter
    if ($rule.Enabled -eq "True" -and $rule.Profile -match "Private" -and
        $port.Protocol -eq "TCP" -and [int]$port.LocalPort -eq $ListenPort -and
        $address.LocalAddress -contains $ListenAddress -and
        $address.RemoteAddress -contains "LocalSubnet") {
        exit 0
    }
}

$principal = [Security.Principal.WindowsPrincipal]::new(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    if ($Elevated) { throw "Administrator approval was not granted." }
    $arguments = @(
        "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        ('"' + $PSCommandPath + '"'), "-ListenAddress", $ListenAddress,
        "-ListenPort", [string]$ListenPort, "-Elevated"
    )
    $process = Start-Process -FilePath "powershell.exe" -ArgumentList $arguments -Verb RunAs -Wait -PassThru
    exit $process.ExitCode
}

if ($rule) {
    Remove-NetFirewallRule -Name $ruleName
}
New-NetFirewallRule -Name $ruleName -DisplayName "Wesnoth Agent Dashboard (Private LAN)" `
    -Description "Allows paired dashboard access from this computer's private local subnet only." `
    -Enabled True -Direction Inbound -Action Allow -Profile Private -Protocol TCP `
    -LocalAddress $ListenAddress -LocalPort $ListenPort -RemoteAddress LocalSubnet | Out-Null
