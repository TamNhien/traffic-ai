[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Export,
  [string]$OutputDirectory = '.\raw-handoff-audit'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Export -PathType Leaf)) { throw "Khong tim thay benchmark ZIP: $Export" }
$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) { throw 'Can Python 3 de kiem tra benchmark.' }
& $python.Source '-X' 'utf8' (Join-Path $PSScriptRoot 'audit-raw-handoff.py') `
  '--export' (Resolve-Path -LiteralPath $Export).Path `
  '--output-dir' $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw "Raw handoff audit failed (exit $LASTEXITCODE)" }
