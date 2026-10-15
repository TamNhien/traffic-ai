param(
    [Parameter(Mandatory=$true)][string]$Export,
    [string]$OutputDirectory = '.\crossing-cycle-audit',
    [ValidateRange(0.01,30)][double]$MaxGapSeconds = 12
)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$script=Join-Path $PSScriptRoot 'audit-crossing-cycles.py'
$source=Resolve-Path -LiteralPath $Export -ErrorAction Stop
$target=[System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputDirectory))
if (Get-Command python -ErrorAction SilentlyContinue) {
  & python $script --export $source.Path --output-dir $target --max-gap-seconds $MaxGapSeconds
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  & py -3 $script --export $source.Path --output-dir $target --max-gap-seconds $MaxGapSeconds
} else {
  throw 'Cần Python 3 để phân tích trace benchmark. Không sửa GT hoặc sự kiện AI.'
}
if ($LASTEXITCODE -ne 0) { throw "Crossing-cycle audit failed: $LASTEXITCODE" }
