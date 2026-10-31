[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$Export,
  [Parameter(Mandatory = $true)][string]$CameraFolder,
  [string]$OutputDirectory = '.\benchmark-frame-evidence-audit',
  [ValidateRange(0.04, 2.0)][double]$MaxGapSeconds = 0.8,
  [switch]$NoCopyImages
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $Export -PathType Leaf)) { throw "Missing benchmark ZIP: $Export" }
if (-not (Test-Path -LiteralPath $CameraFolder -PathType Container)) { throw "Extract camera RAR to a folder first: $CameraFolder" }
$zip = (Resolve-Path -LiteralPath $Export).Path
$camera = (Resolve-Path -LiteralPath $CameraFolder).Path
$out = [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $OutputDirectory))
if ($out -eq $camera -or $out.StartsWith($camera.TrimEnd('\') + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Output cannot be within CameraFolder' }
if (Test-Path -LiteralPath $out) {
  if ((Get-ChildItem -LiteralPath $out -Force | Select-Object -First 1)) { throw "Output must be an empty or new folder: $out" }
} else { New-Item -ItemType Directory -Path $out -Force | Out-Null }
$arguments = @('python','-B','scripts/audit-benchmark-frame-evidence.py', '--export','/inputs/benchmark.zip','--camera-folder','/camera','--output-dir','/out','--max-gap-seconds',$MaxGapSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture))
if ($NoCopyImages) { $arguments += '--no-copy-images' }
& docker run --rm -e PYTHONPYCACHEPREFIX=/tmp/traffic-ai-test-pycache `
  -v "${root}:/src:ro" -v "${zip}:/inputs/benchmark.zip:ro" -v "${camera}:/camera:ro" -v "${out}:/out" `
  -w /src python:3.14.10-slim @arguments
if ($LASTEXITCODE -ne 0) { throw "Camera evidence audit failed: Docker exit $LASTEXITCODE" }
