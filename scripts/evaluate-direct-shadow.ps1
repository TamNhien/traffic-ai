[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$ExportZip,
  [string]$OutputDirectory = '.\shadow-counterfactual-report'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $ExportZip -PathType Leaf)) {
  throw "Khong tim thay ZIP benchmark: $ExportZip"
}
$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) { throw 'Can Python 3.10+ de phan tich offline.' }
& $python.Source '-X' 'utf8' (Join-Path $PSScriptRoot 'evaluate-direct-shadow.py') `
  '--export' (Resolve-Path -LiteralPath $ExportZip).Path `
  '--output-dir' $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw "Shadow counterfactual failed, exit $LASTEXITCODE" }
