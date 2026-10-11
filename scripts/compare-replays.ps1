param(
  [Parameter(Mandatory=$true)][string]$PreviousTrace,
  [Parameter(Mandatory=$true)][string]$CurrentTrace,
  [string]$OutputDirectory = '.\replay-diff-report',
  [switch]$Strict
)
$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path $PSScriptRoot 'replay-diff.py'
foreach ($trace in @($PreviousTrace, $CurrentTrace)) {
  if (-not (Test-Path -LiteralPath $trace -PathType Leaf)) {
    throw "Trace file not found: $trace"
  }
}
$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) { throw 'Python 3.10 or newer is required.' }
$args = @('-X','utf8',$scriptPath,'--previous',(Resolve-Path -LiteralPath $PreviousTrace).Path,
  '--current',(Resolve-Path -LiteralPath $CurrentTrace).Path,'--output-dir',$OutputDirectory)
if ($Strict) { $args += '--strict' }
& $python.Source @args
if ($LASTEXITCODE -ne 0) { throw "Replay audit failed (exit $LASTEXITCODE)" }
