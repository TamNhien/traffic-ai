param(
    [Parameter(Mandatory = $true)][string]$Export,
    [Parameter(Mandatory = $true)][string]$ReviewDirectory,
    [string]$OutputDirectory = '.\benchmark-review-frames-annotated',
    [int]$ExpectedSession = 0
)
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$exportFile = Get-Item -LiteralPath $Export -ErrorAction Stop
$reviewDir = Get-Item -LiteralPath $ReviewDirectory -ErrorAction Stop
if ($exportFile.PSIsContainer -or -not $reviewDir.PSIsContainer) { throw 'Export must be a ZIP file; ReviewDirectory must be a directory.' }
$manifestFile = Join-Path $reviewDir.FullName 'review-manifest.json'
if (-not (Test-Path -LiteralPath $manifestFile -PathType Leaf)) { throw "Review manifest missing: $manifestFile" }
$scriptFile = Join-Path $scriptDir 'annotate-benchmark-review-frames.py'
$reviewVerifier = Join-Path $scriptDir 'export-benchmark-review-frames.py'
$forensicsVerifier = Join-Path $scriptDir 'benchmark-forensics.py'
$gateVerifier = Join-Path $scriptDir 'benchmark-gate.py'
foreach ($required in @($scriptFile, $reviewVerifier, $forensicsVerifier, $gateVerifier)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Review overlay dependency missing: $required" }
}
$out = [System.IO.Path]::GetFullPath($OutputDirectory)
if ([System.IO.Path]::GetFullPath($reviewDir.FullName).TrimEnd('\') -eq $out.TrimEnd('\')) { throw 'Output must differ from ReviewDirectory' }
if ((Test-Path -LiteralPath $out) -and @(Get-ChildItem -LiteralPath $out -Force).Count -gt 0) {
    throw "Output is not empty: $out"
}
New-Item -ItemType Directory -Path $out -Force | Out-Null
$dockerArgs = @('compose','run','--rm','--no-deps',
    '-v',"$($scriptFile):/opt/track-review.py:ro",
    '-v',"$($reviewVerifier):/opt/export-benchmark-review-frames.py:ro",
    '-v',"$($forensicsVerifier):/opt/benchmark-forensics.py:ro",
    '-v',"$($gateVerifier):/opt/benchmark-gate.py:ro",
    '-v',"$($exportFile.FullName):/mnt/benchmark.zip:ro",
    '-v',"$($reviewDir.FullName):/mnt/review-original:ro",
    '-v',"${out}:/mnt/review-annotated",
    '--entrypoint','python','ai-service','/opt/track-review.py',
    '--export','/mnt/benchmark.zip','--review-dir','/mnt/review-original',
    '--output-dir','/mnt/review-annotated')
if ($ExpectedSession -gt 0) { $dockerArgs += @('--expected-session', [string]$ExpectedSession) }
& docker @dockerArgs
if ($LASTEXITCODE -ne 0) { throw "Trace overlay export failed: $LASTEXITCODE" }
