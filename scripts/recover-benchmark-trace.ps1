param(
    [Parameter(Mandatory = $true)][string]$Export,
    [Parameter(Mandatory = $true)][string]$Output,
    [string]$CameraRar,
    [string]$TraceJsonl
)
$ErrorActionPreference = 'Stop'
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { throw 'Python is required for benchmark trace recovery.' }
$argsList = @('-X', 'utf8', (Join-Path $PSScriptRoot 'recover-benchmark-trace.py'), '--export', $Export, '--output', $Output)
if ($CameraRar) { $argsList += @('--camera-rar', $CameraRar) }
if ($TraceJsonl) { $argsList += @('--trace-jsonl', $TraceJsonl) }
& $python.Source @argsList
if ($LASTEXITCODE -ne 0) { throw "Trace recovery failed with exit code $LASTEXITCODE" }
