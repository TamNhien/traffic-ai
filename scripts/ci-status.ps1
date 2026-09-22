$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
  throw "GitHub CLI (gh) is required."
}

gh auth status
if ($LASTEXITCODE -ne 0) { throw "Run: gh auth login" }

gh run list --limit 10
