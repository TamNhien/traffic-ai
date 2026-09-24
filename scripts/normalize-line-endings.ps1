[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$skipParts = @(
  "\.git\", "\node_modules\", "\dist\", "\dist-release\", "\gateway\certs\",
  "\videos\", "\models\", "\snapshots\", "\datasets\", "\training-runs\",
  "\__pycache__\", "\.pytest_cache\"
)

$lfExtensions = @(".sh", ".yml", ".yaml", ".py", ".js", ".jsx", ".css", ".html", ".json", ".md", ".txt", ".ini", ".conf", ".mako", ".svg", ".webmanifest")
$lfNames = @("Dockerfile", ".gitattributes", ".gitignore", ".dockerignore", ".env.example", ".nvmrc", "VERSION")
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$changed = 0

function Test-SkippedPath([string]$Path) {
  $normalized = $Path.Replace('/', '\')
  foreach ($part in $skipParts) {
    if ($normalized.Contains($part)) { return $true }
  }
  return $false
}

function Set-NormalizedEol([string]$Path, [ValidateSet("lf", "crlf")][string]$Mode) {
  $text = [System.IO.File]::ReadAllText($Path)
  $normalized = $text.Replace("`r`n", "`n").Replace("`r", "`n")
  if ($Mode -eq "crlf") {
    $normalized = $normalized.Replace("`n", "`r`n")
  }
  if ($normalized -cne $text) {
    [System.IO.File]::WriteAllText($Path, $normalized, $utf8NoBom)
    return $true
  }
  return $false
}

Get-ChildItem $root -Recurse -File | ForEach-Object {
  $path = $_.FullName
  if (Test-SkippedPath $path) { return }

  $mode = $null
  if ($_.Extension -ieq ".ps1") {
    $mode = "crlf"
  } elseif ($lfExtensions -contains $_.Extension.ToLowerInvariant() -or $lfNames -contains $_.Name) {
    $mode = "lf"
  }

  if ($mode -and (Set-NormalizedEol -Path $path -Mode $mode)) {
    $script:changed += 1
  }
}

Write-Host "[OK] Line endings normalized: $changed file(s) changed. *.ps1=CRLF; source/config=LF." -ForegroundColor Green
