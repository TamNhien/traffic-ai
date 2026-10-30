[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Prior,
  [Parameter(Mandatory=$true)][string]$Current,
  [string]$OutputDirectory = '.\benchmark-repeatability-audit'
)
$ErrorActionPreference = 'Stop'
foreach ($file in @($Prior, $Current)) {
  if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Benchmark ZIP not found: $file" }
}
$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) { throw 'Python 3 is required.' }
& $python.Source '-X' 'utf8' (Join-Path $PSScriptRoot 'audit-benchmark-repeatability.py') `
  '--prior' (Resolve-Path -LiteralPath $Prior).Path `
  '--current' (Resolve-Path -LiteralPath $Current).Path `
  '--output-dir' $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw "Benchmark repeatability audit failed (exit $LASTEXITCODE)" }
