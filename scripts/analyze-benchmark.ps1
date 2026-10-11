[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$ExportZip,
  [string]$OutputDirectory = '.\benchmark-forensics-report',
  [double]$WindowSeconds = 1.0
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $ExportZip -PathType Leaf)) {
  throw "Không tìm thấy ZIP 'Tải hồ sơ benchmark': $ExportZip"
}
$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) { throw 'Cần Python 3.10+ để phân tích hồ sơ benchmark offline.' }
& $python.Source '-X' 'utf8' (Join-Path $PSScriptRoot 'benchmark-forensics.py') `
  '--export' (Resolve-Path -LiteralPath $ExportZip).Path `
  '--output-dir' $OutputDirectory '--window' ([string]::Format([System.Globalization.CultureInfo]::InvariantCulture, '{0}', $WindowSeconds))
if ($LASTEXITCODE -ne 0) { throw "Benchmark forensic audit failed, exit $LASTEXITCODE" }
