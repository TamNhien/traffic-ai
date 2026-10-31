[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$Export,
  [Parameter(Mandatory = $true)][string]$Video,
  [string]$OutputDirectory = '.\benchmark-video-review',
  [ValidateRange(0.25, 4.0)][double]$HalfWindow = 2.0,
  [int]$ExpectedSession = 0
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$archive = Get-Item -LiteralPath $Export -ErrorAction Stop
$clip = Get-Item -LiteralPath $Video -ErrorAction Stop
if ($archive.PSIsContainer -or $clip.PSIsContainer) { throw 'Export and Video must be ordinary files.' }
if ($clip.Extension -ine '.mp4') { throw 'Expected original source MP4.' }
$destination = [IO.Path]::GetFullPath($OutputDirectory)
if ((Test-Path -LiteralPath $destination) -and @(Get-ChildItem -LiteralPath $destination -Force).Count -gt 0) {
  throw "Output directory must be new or empty: $destination"
}
New-Item -ItemType Directory -Path $destination -Force | Out-Null
$scriptDir = [IO.Path]::GetFullPath($PSScriptRoot)
$dockerArgs = @('run','--rm','--network','none','--pull','never','--read-only',
  '--tmpfs','/tmp:rw,size=64m','--pids-limit','128',
  '-e','PYTHONDONTWRITEBYTECODE=1',
  '-v',"${scriptDir}:/opt/review-tools:ro",
  '-v',"$($archive.FullName):/inputs/benchmark.zip:ro",
  '-v',"$($clip.FullName):/inputs/$($clip.Name):ro",
  '-v',"${destination}:/out",
  '--entrypoint','python','traffic-ai-ai-service:latest',
  '/opt/review-tools/export-benchmark-review-clips.py',
  '--export','/inputs/benchmark.zip',
  '--video',"/inputs/$($clip.Name)",
  '--output-dir','/out',
  '--half-window',$HalfWindow.ToString([Globalization.CultureInfo]::InvariantCulture))
if ($ExpectedSession -gt 0) { $dockerArgs += @('--expected-session', [string]$ExpectedSession) }
& docker @dockerArgs
if ($LASTEXITCODE -ne 0) { throw "Verified review clips export failed: $LASTEXITCODE" }
