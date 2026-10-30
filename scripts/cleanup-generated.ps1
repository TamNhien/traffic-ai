# V0.5.126 - only allow known report output directories; safe dry-run by default.
param(
    [switch]$Apply,
    [switch]$IncludeReleaseArtifacts,
    [switch]$IncludeLegacyDocs
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
# No raw camera media, data, model weights, DB backup, Git metadata or source trees.
$names = @(
    'crossing-cycle-audit',
    'endpoint-precision-audit',
    'endpoint-precision-audit-v108',
    'gate-coverage-audit',
    'raw-id-audit-report',
    'replay-diff-report',
    'benchmark-quality-audit',
    'benchmark-repeatability-audit',
    'benchmark-forensics-report',
    'passage-evidence-audit'
)
if ($IncludeReleaseArtifacts) { $names += 'dist-release' }
foreach ($name in $names) {
    $path = Join-Path $root $name
    $item = Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    if (-not $item) { continue }
    if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        Write-Warning "Skipped non-directory or junction: $path"
        continue
    }
    # Resolve and confirm the report folder is an immediate child of the project root.
    if ((Split-Path -Parent $item.FullName).TrimEnd('\') -ine $root.TrimEnd('\')) {
        throw "Unsafe report path: $($item.FullName)"
    }
    if ($Apply) {
        # Do not traverse symlinks inside a report directory; refuse deletion instead.
        $links = Get-ChildItem -LiteralPath $path -Recurse -Force -Attributes ReparsePoint -ErrorAction Stop | Select-Object -First 1
        if ($links) {
            Write-Warning "Skipped directory with junction/symlink: $path"
            continue
        }
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction Stop
        Write-Host "[REMOVED] $path"
    } else {
        Write-Host "[DRY RUN] Would remove: $path"
    }
}

# Legacy root documents were merged into README.md in V0.5.126.
if ($IncludeLegacyDocs) {
    foreach ($name in @('VERIFICATION.md', 'DEPENDENCIES_V05122.md')) {
        $path = Join-Path $root $name
        $item = Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        if (-not $item) { continue }
        if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            Write-Warning "Skipped non-file or link: $path"
            continue
        }
        if ($Apply) {
            Remove-Item -LiteralPath $path -Force -ErrorAction Stop
            Write-Host "[REMOVED] $path"
        } else {
            Write-Host "[DRY RUN] Would remove merged legacy document: $path"
        }
    }
}
if (-not $Apply) { Write-Host 'Preview only. Add -Apply to delete listed items.' }
