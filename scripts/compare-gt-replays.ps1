param(
  [Parameter(Mandatory=$true)][string]$ReferenceBenchmark,
  [Parameter(Mandatory=$true)][string]$CurrentTrace,
  [string]$OutputDirectory = '.\gt-replay-witness-report',
  [switch]$Strict
)
$ErrorActionPreference = 'Stop'
foreach ($path in @($ReferenceBenchmark, $CurrentTrace)) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing evidence file: $path" }
}
$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) { throw 'Python 3.10 or newer is required.' }
$args = @('-X', 'utf8', (Join-Path $PSScriptRoot 'gt-replay-witness.py'),
  '--reference-benchmark', (Resolve-Path -LiteralPath $ReferenceBenchmark).Path,
  '--current-trace', (Resolve-Path -LiteralPath $CurrentTrace).Path,
  '--output-dir', $OutputDirectory)
if ($Strict) { $args += '--strict' }
& $python.Source @args
if ($LASTEXITCODE -ne 0) { throw "GT replay witness failed (exit $LASTEXITCODE)" }
