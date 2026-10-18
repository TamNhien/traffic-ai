param(
    [Parameter(Mandatory = $true)][string]$Export,
    [string]$OutputDirectory = '.\gate-coverage-audit',
    [double]$Window = 1.0,
    [double]$NearRadius = 0.035,
    [int]$ExpectedSession = 0,
    [switch]$RequireProvenance
)
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonCommand = if (Get-Command python -ErrorAction SilentlyContinue) { 'python' } elseif (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { throw 'Python 3 is required' }
# Build arguments explicitly so optional switches do not change legacy usage.
$auditArgs = @((Join-Path $scriptDir 'audit-gate-coverage.py'), '--export', $Export, '--output-dir', $OutputDirectory, '--window', $Window, '--near-radius', $NearRadius)
if ($ExpectedSession -gt 0) { $auditArgs += @('--expected-session', $ExpectedSession) }
if ($RequireProvenance) { $auditArgs += '--require-provenance' }
& $pythonCommand @auditArgs
if ($LASTEXITCODE -ne 0) { throw "Gate coverage audit failed: exit code $LASTEXITCODE" }
