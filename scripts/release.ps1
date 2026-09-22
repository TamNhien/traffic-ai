[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [ValidatePattern('^\d+\.\d+\.\d+$')]
  [string]$Version,
  [string]$Owner = "TamNhien",
  [string]$Repository = "traffic-ai",
  [ValidateSet("public", "private")]
  [string]$Visibility = "private",
  [string]$Branch = "main",
  [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$tag = "v$Version"

function Assert-Command([string]$Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "$Name is not installed or not available in PATH."
  }
}

Assert-Command git
Assert-Command gh
Assert-Command docker

if (-not $SkipTests) {
  & "$PSScriptRoot\test.ps1"
  if ($LASTEXITCODE -ne 0) { throw "Tests failed. Release aborted." }
}

& "$PSScriptRoot\github-init.ps1" -Owner $Owner -Repository $Repository -Visibility $Visibility -Branch $Branch
if ($LASTEXITCODE -ne 0) { throw "GitHub initialization failed." }

$currentBranch = git branch --show-current
if ($currentBranch -ne $Branch) {
  throw "Current branch is '$currentBranch'. Expected '$Branch'."
}

Set-Content -Path (Join-Path $root "VERSION") -Value $Version -NoNewline

$packageJson = Join-Path $root "frontend\package.json"
$pkg = Get-Content $packageJson -Raw | ConvertFrom-Json
$pkg.version = $Version
$pkg | ConvertTo-Json -Depth 20 | Set-Content -Path $packageJson -Encoding utf8

# Never publish local secrets/certificate private keys.
$forbiddenTracked = @(".env")
foreach ($file in $forbiddenTracked) {
  git ls-files --error-unmatch $file 1>$null 2>$null
  if ($LASTEXITCODE -eq 0) {
    throw "Refusing to release because secret file '$file' is tracked by Git. Remove it from Git first."
  }
}

$privateKeys = git ls-files "gateway/certs/*.key"
if ($privateKeys) {
  throw "Refusing to release because certificate private key(s) are tracked by Git: $privateKeys"
}

git add -A
$pending = git status --porcelain
if ($pending) {
  git commit -m "chore(release): $tag"
  if ($LASTEXITCODE -ne 0) {
    throw "git commit failed. Configure Git identity if needed: git config --global user.name and user.email"
  }
}

# Make sure there is at least one commit (important on a new repository).
git rev-parse --verify HEAD 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
  throw "No Git commit exists. Nothing can be pushed."
}

git rev-parse $tag 1>$null 2>$null
if ($LASTEXITCODE -eq 0) {
  throw "Tag $tag already exists. Use a new version."
}

git tag -a $tag -m "Traffic AI $tag"
if ($LASTEXITCODE -ne 0) { throw "git tag failed" }

git push -u origin $Branch
if ($LASTEXITCODE -ne 0) { throw "Push branch failed" }

git push origin $tag
if ($LASTEXITCODE -ne 0) { throw "Push tag failed" }

Write-Host "`n[SUCCESS] Traffic AI $tag published." -ForegroundColor Green
Write-Host "Repository: https://github.com/$Owner/$Repository"
Write-Host "GitHub Actions will verify the tag and automatically create the Release."
Write-Host "Watch CI : gh run watch"
Write-Host "Releases : https://github.com/$Owner/$Repository/releases"
