[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Export,
  [string]$OutputDirectory = '.\benchmark-review'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Export -PathType Leaf)) { throw "Không tìm thấy benchmark ZIP: $Export" }
$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) { throw 'Cần cài Python 3.10 trở lên.' }
& $python.Source '-X' 'utf8' (Join-Path $PSScriptRoot 'review-benchmark-errors.py') `
  '--export' (Resolve-Path -LiteralPath $Export).Path `
  '--output-dir' $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw "Xuất danh sách review thất bại (exit $LASTEXITCODE)" }
