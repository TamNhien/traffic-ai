param(
  [Parameter(Mandatory=$true)][string]$Export,
  [string]$OutputDirectory = '.\endpoint-precision-audit'
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
python (Join-Path $PSScriptRoot 'audit-endpoint-precision.py') --export $Export --output-directory $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw "Endpoint precision audit failed with exit code $LASTEXITCODE" }
