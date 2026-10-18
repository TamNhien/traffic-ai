param(
    [Parameter(Mandatory = $true)][string]$Export,
    [string]$OutputDirectory = '.\temporal-neighbor-audit',
    [double]$Horizon = 2.0
)
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonCommand = if (Get-Command python -ErrorAction SilentlyContinue) { 'python' } elseif (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { throw 'Python 3 is required' }
& $pythonCommand (Join-Path $scriptDir 'audit-temporal-neighbors.py') --export $Export --output-dir $OutputDirectory --horizon $Horizon
if ($LASTEXITCODE -ne 0) { throw "Temporal neighbor audit failed: exit code $LASTEXITCODE" }
