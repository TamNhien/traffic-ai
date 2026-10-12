[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$ExportZip,
  [string]$OutputDirectory = '.\raw-id-audit-report'
)
$ErrorActionPreference = 'Stop'
$scriptFile = Join-Path $PSScriptRoot 'raw-id-audit.py'
& python $scriptFile --export-zip $ExportZip --output-directory $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw 'Raw ID audit failed; see error above.' }
