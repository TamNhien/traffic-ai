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
# V0.5.111: validate the caller's local path before invoking Python.
# The benchmark downloaded in ChatGPT is not automatically copied to the project folder.
$benchmarkFile = Get-Item -LiteralPath $Export -ErrorAction SilentlyContinue
if ($null -eq $benchmarkFile -or $benchmarkFile.PSIsContainer) {
    $expectedPath = if ([System.IO.Path]::IsPathFullyQualified($Export)) { $Export } else { Join-Path (Get-Location).Path $Export }
    throw "Benchmark ZIP không tồn tại tại: $expectedPath. Hãy tải/chuyển file ZIP đã khôi phục vào đúng thư mục, hoặc dùng -Export với đường dẫn tuyệt đối. Kiểm tra bằng Test-Path -LiteralPath '<duong-dan-zip>'."
}
# Build arguments explicitly so optional switches do not change legacy usage.
$auditArgs = @((Join-Path $scriptDir 'audit-gate-coverage.py'), '--export', $benchmarkFile.FullName, '--output-dir', $OutputDirectory, '--window', $Window, '--near-radius', $NearRadius)
if ($ExpectedSession -gt 0) { $auditArgs += @('--expected-session', $ExpectedSession) }
if ($RequireProvenance) { $auditArgs += '--require-provenance' }
& $pythonCommand @auditArgs
if ($LASTEXITCODE -ne 0) { throw "Gate coverage audit failed: exit code $LASTEXITCODE" }
