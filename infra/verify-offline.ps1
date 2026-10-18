param(
    [Parameter(Mandatory=$true)][string]$Bundle,
    [Parameter(Mandatory=$true)][string]$Video,
    [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference = 'Stop'
$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Administrator PowerShell is required for temporary Windows Firewall rules. No rules were changed.'
}
if (@(Get-NetFirewallProfile | Where-Object { -not $_.Enabled }).Count -gt 0) {
    throw 'Enable Windows Firewall profiles before qualification. No rules were changed.'
}
$bundleRoot = (Resolve-Path -LiteralPath $Bundle).Path
$videoPath = (Resolve-Path -LiteralPath $Video).Path
$outputPath = [IO.Path]::GetFullPath($Output)
$repoRoot = Split-Path -Parent $PSScriptRoot
$ruleNames = [Collections.Generic.List[string]]::new()
$runId = [guid]::NewGuid().ToString('N')
try {
    foreach ($relative in @('python\python.exe', 'python\pythonw.exe', 'bin\ffmpeg.exe', 'bin\ffprobe.exe')) {
        $program = (Resolve-Path -LiteralPath (Join-Path $bundleRoot $relative)).Path
        $name = 'CashProof-offline-' + $runId + '-' + $ruleNames.Count
        New-NetFirewallRule -Name $name -DisplayName $name -Direction Outbound -Action Block -Program $program -Profile Any | Out-Null
        $ruleNames.Add($name)
    }
    $python = Join-Path $bundleRoot 'python\python.exe'
    # No footage or private information is used in the external connectivity probe.
    & $python -s -c "import socket,sys; s=socket.socket(); s.settimeout(3); result=s.connect_ex(('1.1.1.1',443)); s.close(); sys.exit(0 if result else 1)"
    if ($LASTEXITCODE -ne 0) { throw 'External connection unexpectedly succeeded; offline qualification failed.' }
    & $python -s (Join-Path $repoRoot 'tools\verify_runtime.py') --bundle $bundleRoot --video $videoPath --output $outputPath --deny-external-network
    if ($LASTEXITCODE -ne 0) { throw 'Portable runtime verification failed.' }
    $summaryPath = Join-Path $outputPath 'technical-summary.json'
    $summary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
    if ($summary.done -ne $summary.submitted -or $summary.failed -ne 0) {
        throw 'Analysis did not complete successfully; no offline pass is recorded.'
    }
    $proof = [ordered]@{
        run_id = $runId
        checked_at_utc = [DateTime]::UtcNow.ToString('o')
        method = 'Temporary outbound block rules on bundled Python, pythonw, FFmpeg and ffprobe; loopback API remains usable'
        programs_blocked = $ruleNames.Count
        external_probe_blocked = $true
        completed = $summary.done
        scope = 'Specified runtime executable paths on this Windows host; not an audit of every OS service'
    }
    $proof | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $outputPath 'windows-firewall-proof.json') -Encoding UTF8
} finally {
    foreach ($name in $ruleNames) {
        Remove-NetFirewallRule -Name $name -ErrorAction Continue
    }
}
