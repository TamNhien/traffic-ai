[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Prior,
  [Parameter(Mandatory=$true)][string]$Current,
  [string]$OutputDirectory = '.\benchmark-comparison'
)
$ErrorActionPreference = 'Stop'
foreach ($path in @($Prior, $Current)) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Không tìm thấy file benchmark: $path" }
}
$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) { throw 'Cần cài Python 3.10 trở lên.' }
& $python.Source '-X' 'utf8' (Join-Path $PSScriptRoot 'compare-benchmark-exports.py') `
    '--prior' (Resolve-Path -LiteralPath $Prior).Path `
    '--current' (Resolve-Path -LiteralPath $Current).Path `
    '--output-dir' $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw "So sánh benchmark thất bại (exit $LASTEXITCODE)" }
