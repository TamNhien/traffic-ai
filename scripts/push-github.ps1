[CmdletBinding()]
param(
  [string]$Owner = "TamNhien",
  [string]$Repository = "traffic-ai",
  [ValidateSet("public", "private")]
  [string]$Visibility = "private",
  [string]$Branch = "main",
  [string]$Message = "chore: sync Traffic AI source",
  [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not $SkipTests) {
  & "$PSScriptRoot\test.ps1"
  if ($LASTEXITCODE -ne 0) { throw "Tests failed. Push aborted." }
}

& "$PSScriptRoot\github-init.ps1" -Owner $Owner -Repository $Repository -Visibility $Visibility -Branch $Branch
if ($LASTEXITCODE -ne 0) { throw "GitHub initialization failed." }

# Fail closed on obvious local secrets.
git ls-files --error-unmatch .env 1>$null 2>$null
if ($LASTEXITCODE -eq 0) { throw "Refusing to push because .env is tracked by Git." }
if (git ls-files "gateway/certs/*.key") { throw "Refusing to push because a certificate private key is tracked by Git." }

git add -A
$pending = git status --porcelain
if ($pending) {
  git commit -m $Message
  if ($LASTEXITCODE -ne 0) {
    throw "git commit failed. Configure Git identity if needed."
  }
} else {
  Write-Host "[OK] No local source changes to commit." -ForegroundColor Green
}

git push -u origin $Branch
if ($LASTEXITCODE -ne 0) { throw "Push failed." }

Write-Host "[SUCCESS] Source pushed to https://github.com/$Owner/$Repository" -ForegroundColor Green
