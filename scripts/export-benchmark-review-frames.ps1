param(
    [Parameter(Mandatory = $true)][string]$Export,
    [Parameter(Mandatory = $true)][string]$Video,
    [string]$OutputDirectory = '.\benchmark-review-frames',
    [int]$ExpectedSession = 0
)
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$exportFile = Get-Item -LiteralPath $Export -ErrorAction Stop
$videoFile = Get-Item -LiteralPath $Video -ErrorAction Stop
if ($exportFile.PSIsContainer -or $videoFile.PSIsContainer) { throw 'Export and Video must be files.' }
$out = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $out -Force | Out-Null
$tool = Join-Path $scriptDir 'export-benchmark-review-frames.py'
# AI service image has cv2 + benchmark verification dependencies; the user
# does not need a separate OpenCV or ffmpeg installation on Windows.
$mounts = @(
    '-v', "${tool}:/opt/review-tool.py:ro",
    '-v', "$($exportFile.FullName):/mnt/benchmark.zip:ro",
    '-v', "$($videoFile.FullName):/mnt/input.mp4:ro",
    '-v', "${out}:/mnt/review-output"
)
# Both verifier files are required: review-tool.py loads benchmark-forensics.py,
# which loads benchmark-gate.py relative to its own __file__ in /opt.
# Explicitly mount the complete verifier chain; it is not in the AI image.
$verifier = Join-Path $scriptDir 'benchmark-forensics.py'
$gateVerifier = Join-Path $scriptDir 'benchmark-gate.py'
foreach ($required in @($tool, $verifier, $gateVerifier)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Review export dependency is missing: $required"
    }
}
$mounts += @(
    '-v', "${verifier}:/opt/benchmark-forensics.py:ro",
    '-v', "${gateVerifier}:/opt/benchmark-gate.py:ro"
)
$argList = @('compose','run','--rm','--no-deps') + $mounts + @('--entrypoint','python','ai-service',
    '/opt/review-tool.py','--export','/mnt/benchmark.zip','--video','/mnt/input.mp4',
    '--output-dir','/mnt/review-output')
if ($ExpectedSession -gt 0) { $argList += @('--expected-session', [string]$ExpectedSession) }
& docker @argList
if ($LASTEXITCODE -ne 0) { throw "Review frame extraction failed: $LASTEXITCODE" }
