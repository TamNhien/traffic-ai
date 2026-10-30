param(
    [Parameter(Mandatory = $true)][string]$Export,
    [string]$OutputDirectory = '.\benchmark-quality-audit',
    [string]$CameraImages = ''
)
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonCommand = if (Get-Command python -ErrorAction SilentlyContinue) { 'python' } elseif (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { throw 'Python 3 is required' }
$arguments = @((Join-Path $scriptDir 'audit-benchmark-quality.py'), '--export', $Export, '--output-dir', $OutputDirectory)
if ($CameraImages) { $arguments += @('--camera-images', $CameraImages) }
& $pythonCommand @arguments
if ($LASTEXITCODE -ne 0) { throw "Benchmark quality audit failed: exit code $LASTEXITCODE" }
