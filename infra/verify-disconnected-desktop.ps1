param(
    [Parameter(Mandatory=$true)][string]$Node,
    [string]$Executable,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$nodePath = (Resolve-Path -LiteralPath $Node).Path
$probe = Join-Path $repoRoot 'tools\verify_packaged_desktop.cjs'
$packaged = if ($Executable) { (Resolve-Path -LiteralPath $Executable).Path } else { Join-Path $repoRoot 'apps\desktop\dist\offline\win-unpacked\CashProof.exe' }
foreach ($required in @($probe, $packaged, (Join-Path $repoRoot 'private-data\live-browser-integration\input.json'))) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw 'A prepared local test prerequisite is missing.' }
}

function Get-DisconnectionState {
    $physical = @(Get-NetAdapter -Physical -ErrorAction Stop | Where-Object { $_.Status -eq 'Up' }).Count
    $connected = @(Get-NetIPInterface -ErrorAction Stop | Where-Object { $_.ConnectionState -eq 'Connected' } | Select-Object -ExpandProperty InterfaceIndex -Unique)
    $defaults = @(Get-NetRoute -ErrorAction Stop | Where-Object { $_.DestinationPrefix -in @('0.0.0.0/0', '::/0') -and $_.InterfaceIndex -in $connected }).Count
    [pscustomobject]@{ physical_up = $physical; connected_default_routes = $defaults; disconnected = ($physical -eq 0 -and $defaults -eq 0) }
}

$before = Get-DisconnectionState
if ($CheckOnly) {
    [ordered]@{ prerequisites_present=$true; disconnected=$before.disconnected; physical_up=$before.physical_up; connected_default_routes=$before.connected_default_routes; settings_changed=$false } | ConvertTo-Json -Compress
    return
}
if (-not $before.disconnected) { throw 'Disconnect Wi-Fi/Ethernet/VPN first. No network settings were changed and no inference was started.' }
# No private data is sent. This native TCP probe must fail before the test starts.
$socket = [Net.Sockets.Socket]::new([Net.Sockets.AddressFamily]::InterNetwork, [Net.Sockets.SocketType]::Stream, [Net.Sockets.ProtocolType]::Tcp)
$probeBlocked = $true
try {
    $pending = $socket.BeginConnect('1.1.1.1', 443, $null, $null)
    if ($pending.AsyncWaitHandle.WaitOne(3000)) {
        try { $socket.EndConnect($pending); $probeBlocked = -not $socket.Connected } catch { $probeBlocked = $true }
    }
} finally { $socket.Dispose() }
if (-not $probeBlocked) { throw 'An external connection succeeded; no offline test was started.' }

$runId = [guid]::NewGuid().ToString('N')
$output = Join-Path $repoRoot ('private-data\disconnected-desktop\' + $runId)
New-Item -ItemType Directory -Path $output | Out-Null
$started = [DateTime]::UtcNow
$info = [Diagnostics.ProcessStartInfo]::new()
$info.FileName = $nodePath
$info.Arguments = '"' + $probe + '" --executable "' + $packaged + '" --output "' + (Join-Path $output 'runtime') + '"'
$info.WorkingDirectory = $repoRoot
$info.UseShellExecute = $false
$info.CreateNoWindow = $true
$info.RedirectStandardOutput = $true
$info.RedirectStandardError = $true
$process = [Diagnostics.Process]::Start($info)
$stdout = $process.StandardOutput.ReadToEndAsync()
$stderr = $process.StandardError.ReadToEndAsync()
$continuous = $true
$samples = 0
while (-not $process.WaitForExit(2000)) {
    $state = Get-DisconnectionState
    $samples++
    if (-not $state.disconnected) { $continuous = $false }
}
$stdoutText = $stdout.GetAwaiter().GetResult()
$stdoutText | Set-Content -LiteralPath (Join-Path $output 'technical-stdout.log') -Encoding utf8
$stderr.GetAwaiter().GetResult() | Set-Content -LiteralPath (Join-Path $output 'private-stderr.log') -Encoding utf8
$after = Get-DisconnectionState
$continuous = $continuous -and $after.disconnected
$pass = $false
if ($process.ExitCode -eq 0) {
    $summary = ($stdoutText -split '[\r\n]+' | Where-Object { $_.Trim().Length -gt 0 } | Select-Object -Last 1) | ConvertFrom-Json
    $pass = $continuous -and $summary.packaged -and $summary.new_real_analysis_completed -and $summary.export_downloaded -and $summary.reload_restored -and $summary.backend_stopped_after_app_close -and $summary.health.mode -eq 'offline'
    $summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $output 'runtime-summary.json') -Encoding utf8
}
$proof = [ordered]@{
    run_id = $runId
    checked_at_utc = [DateTime]::UtcNow.ToString('o')
    started_at_utc = $started.ToString('o')
    method = 'User-disconnected physical links and connected default routes checked before, during and after the run, with a blocked native external TCP probe'
    network_settings_changed_by_script = $false
    external_probe_blocked = $probeBlocked
    disconnected_before = $before.disconnected
    disconnected_after = $after.disconnected
    all_network_samples_disconnected = $continuous
    network_state_samples = $samples
    new_packaged_runtime_passed_disconnected = [bool]$pass
    full_I17_passed = $false
    remaining = 'Real positive/multi-event semantic, source-time and review checks remain separate. This receipt does not qualify recognition accuracy or every I17 criterion.'
}
$proof | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $output 'disconnected-proof.json') -Encoding utf8
$proof | ConvertTo-Json -Depth 5
if (-not $pass) { throw 'Disconnected runtime qualification did not pass. Inspect the local technical receipt; no offline PASS is claimed.' }
