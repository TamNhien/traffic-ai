param(
  [Parameter(Mandatory=$true)][string]$ExportZip,
  [int]$MaxMissed = 0,
  [int]$MaxExtra = 0,
  [int]$MaxWrongClass = -1,
  [string]$Baseline = '',
  [string]$WriteBaseline = ''
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$gate = Join-Path $PSScriptRoot 'benchmark-gate.py'
if (-not (Test-Path -LiteralPath $ExportZip)) { throw "Benchmark ZIP not found: $ExportZip" }
$arguments = @('-X', 'utf8', $gate, '--export', (Resolve-Path -LiteralPath $ExportZip).Path,
  '--max-missed', "$MaxMissed", '--max-extra', "$MaxExtra")
if ($MaxWrongClass -ge 0) { $arguments += @('--max-class-mismatches', "$MaxWrongClass") }
if ($Baseline) { $arguments += @('--baseline', $Baseline) }
if ($WriteBaseline) { $arguments += @('--write-baseline', $WriteBaseline) }
$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) { throw 'Python 3 is required for the optional offline benchmark gate.' }
& $python.Source @arguments
if ($LASTEXITCODE -ne 0) { throw "Benchmark gate failed (exit $LASTEXITCODE)" }
