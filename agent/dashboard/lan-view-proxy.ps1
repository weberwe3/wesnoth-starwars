param(
    [Parameter(Mandatory = $true)][string]$ListenAddress,
    [int]$ListenPort = 8765,
    [int]$UpstreamPort = 8765
)

$ErrorActionPreference = "Stop"
if ($ListenAddress -notmatch '^(?:\d{1,3}\.){3}\d{1,3}$' -or
    $ListenPort -lt 1024 -or $ListenPort -gt 65535 -or
    $UpstreamPort -lt 1024 -or $UpstreamPort -gt 65535) {
    throw "Unsafe LAN proxy configuration."
}

$runtime = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\runtime"))
$shutdownMarker = Join-Path $runtime "dashboard.shutdown"
$readyMarker = Join-Path $runtime "dashboard-lan-proxy.ready"
$mutex = [Threading.Mutex]::new($false, "Local\WesnothDashboardLanProxy-$ListenPort")
if (-not $mutex.WaitOne(5000)) { exit 0 }

function Send-ProxyError([Net.Sockets.NetworkStream]$Stream, [int]$Status, [string]$Message) {
    $body = [Text.Encoding]::UTF8.GetBytes($Message + "`n")
    $reason = if ($Status -eq 400) { "Bad Request" } elseif ($Status -eq 405) { "Method Not Allowed" } else { "Bad Gateway" }
    $head = [Text.Encoding]::ASCII.GetBytes(
        "HTTP/1.1 $Status $reason`r`nContent-Type: text/plain; charset=utf-8`r`nContent-Length: $($body.Length)`r`nConnection: close`r`n`r`n"
    )
    $Stream.Write($head, 0, $head.Length)
    $Stream.Write($body, 0, $body.Length)
}

function Read-RequestHead([Net.Sockets.NetworkStream]$Stream) {
    $bytes = [Collections.Generic.List[byte]]::new()
    while ($bytes.Count -lt 16384) {
        $value = $Stream.ReadByte()
        if ($value -lt 0) { break }
        $bytes.Add([byte]$value)
        $count = $bytes.Count
        if ($count -ge 4 -and $bytes[$count-4] -eq 13 -and $bytes[$count-3] -eq 10 -and $bytes[$count-2] -eq 13 -and $bytes[$count-1] -eq 10) {
            return [Text.Encoding]::ASCII.GetString($bytes.ToArray())
        }
    }
    throw "Request headers were incomplete or too large."
}

$listener = $null
try {
    New-Item -ItemType Directory -Path $runtime -Force | Out-Null
    Remove-Item -LiteralPath $shutdownMarker -Force -ErrorAction SilentlyContinue
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Parse($ListenAddress), $ListenPort)
    $listener.Start()
    [IO.File]::WriteAllText($readyMarker, "$ListenAddress`:$ListenPort`n", [Text.UTF8Encoding]::new($false))

    while (-not (Test-Path -LiteralPath $shutdownMarker)) {
        if (-not $listener.Pending()) {
            Start-Sleep -Milliseconds 150
            continue
        }
        $client = $listener.AcceptTcpClient()
        try {
            $client.ReceiveTimeout = 5000
            $client.SendTimeout = 5000
            $downstream = $client.GetStream()
            try {
                $headerText = Read-RequestHead $downstream
                $lines = $headerText -split "`r`n"
                if ($lines[0] -notmatch '^(GET|HEAD|POST) (/[^ ]*) HTTP/1\.[01]$') {
                    Send-ProxyError $downstream 405 "Only dashboard GET, HEAD, and POST requests are allowed."
                    continue
                }
                $method = $Matches[1]
                $target = $Matches[2]
                if ($method -eq "POST" -and $target -notmatch '^/api/control(?:\?|$)') {
                    Send-ProxyError $downstream 405 "POST is limited to the governed dashboard control endpoint."
                    continue
                }

                $forward = [Collections.Generic.List[string]]::new()
                $contentLength = 0
                foreach ($line in $lines[1..($lines.Count - 1)]) {
                    if (-not $line) { continue }
                    if ($line -notmatch '^([A-Za-z0-9-]+):\s*(.*)$') { throw "Malformed request header." }
                    $name = $Matches[1]
                    $value = $Matches[2]
                    if ($name -ieq "Content-Length") {
                        if (-not [int]::TryParse($value, [ref]$contentLength) -or $contentLength -lt 0 -or $contentLength -gt 4096) {
                            throw "Invalid request body length."
                        }
                    }
                    if ($name -in @("Accept", "Accept-Language", "Content-Type", "Content-Length", "If-Modified-Since", "If-None-Match", "Origin", "User-Agent", "X-Wesnoth-CSRF", "X-Wesnoth-LAN-Token")) {
                        $forward.Add("$name`: $value")
                    }
                }
                if ($method -ne "POST" -and $contentLength -ne 0) { throw "GET and HEAD requests cannot contain a body." }

                $body = [byte[]]::new($contentLength)
                $offset = 0
                while ($offset -lt $contentLength) {
                    $read = $downstream.Read($body, $offset, $contentLength - $offset)
                    if ($read -le 0) { throw "Incomplete request body." }
                    $offset += $read
                }

                $upstreamClient = [Net.Sockets.TcpClient]::new()
                try {
                    $upstreamClient.Connect("127.0.0.1", $UpstreamPort)
                    $upstream = $upstreamClient.GetStream()
                    $request = "$method $target HTTP/1.0`r`nHost: 127.0.0.1`:$UpstreamPort`r`nX-Wesnoth-LAN-View: 1`r`n$($forward -join "`r`n")`r`nConnection: close`r`n`r`n"
                    $requestBytes = [Text.Encoding]::ASCII.GetBytes($request)
                    $upstream.Write($requestBytes, 0, $requestBytes.Length)
                    if ($body.Length) { $upstream.Write($body, 0, $body.Length) }
                    $upstream.CopyTo($downstream)
                } finally {
                    if ($upstreamClient) { $upstreamClient.Dispose() }
                }
            } catch {
                try { Send-ProxyError $downstream 400 "The dashboard proxy rejected this request." } catch {}
            }
        } finally {
            $client.Dispose()
        }
    }
} finally {
    if ($listener) { $listener.Stop() }
    Remove-Item -LiteralPath $readyMarker -Force -ErrorAction SilentlyContinue
    try { $mutex.ReleaseMutex() } catch {}
    $mutex.Dispose()
}
