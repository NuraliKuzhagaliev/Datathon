param([string]$Python = '3.12', [string]$Uv = 'uv')
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$env:UV_PROJECT_ENVIRONMENT = Join-Path $repoRoot '.venv'
& $Uv sync --project (Join-Path $repoRoot 'services/backend') --python $Python --extra test --frozen
if ($LASTEXITCODE -ne 0) { throw 'Locked dependency setup failed.' }
Write-Host 'Python environment is ready. Provision model weights explicitly before offline use.'
