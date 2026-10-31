[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string[]]$Exports,
  [string]$OutputDirectory = '.\benchmark-trend-audit'
)
$ErrorActionPreference = 'Stop'
if ($Exports.Count -lt 3 -or $Exports.Count -gt 12) { throw 'Provide 3 to 12 benchmark ZIP files ordered by session.' }
$root = Split-Path -Parent $PSScriptRoot
$inputs = @()
for ($i = 0; $i -lt $Exports.Count; $i++) {
  if (-not (Test-Path -LiteralPath $Exports[$i] -PathType Leaf)) { throw "Missing benchmark ZIP: $($Exports[$i])" }
  $inputs += (Resolve-Path -LiteralPath $Exports[$i]).Path
}
$dest = [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $OutputDirectory))
if (-not (Test-Path -LiteralPath $dest)) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }
$volumes = @('-v',"${root}:/src:ro",'-v',"${dest}:/out")
$files = @()
for ($i = 0; $i -lt $inputs.Count; $i++) {
  $dst = "/inputs/$i.zip"
  $volumes += @('-v',"$($inputs[$i]):${dst}:ro")
  $files += $dst
}
& docker run --rm -e PYTHONPYCACHEPREFIX=/tmp/traffic-ai-test-pycache `
  @volumes -w /src python:3.14.10-slim `
  python -B scripts/audit-benchmark-trend.py --exports @files --output-dir /out
if ($LASTEXITCODE -ne 0) { throw "Trend audit failed (Docker exit $LASTEXITCODE)" }
