[CmdletBinding()]
param(
  [string]$Owner = "TamNhien",
  [string]$Repository = "traffic-ai",
  [ValidateSet("public", "private")]
  [string]$Visibility = "private",
  [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Assert-Command([string]$Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "$Name is not installed or not available in PATH."
  }
}

Assert-Command git
Assert-Command gh

gh auth status
if ($LASTEXITCODE -ne 0) {
  throw "GitHub CLI is not authenticated. Run: gh auth login"
}

$login = (gh api user --jq .login).Trim()
if ($LASTEXITCODE -ne 0 -or -not $login) {
  throw "Unable to read the authenticated GitHub account."
}
if ($login -ine $Owner) {
  throw "GitHub CLI is authenticated as '$login', but this project is configured for '$Owner'. Run 'gh auth switch' or 'gh auth login' with the correct account."
}

if (-not (Test-Path .git)) {
  git init
  if ($LASTEXITCODE -ne 0) { throw "git init failed" }
}

git branch -M $Branch
if ($LASTEXITCODE -ne 0) { throw "Unable to set branch $Branch" }

$repoFullName = "$Owner/$Repository"
$repoUrl = "https://github.com/$repoFullName.git"

gh repo view $repoFullName --json nameWithOwner 1>$null 2>$null
$repoExists = ($LASTEXITCODE -eq 0)

if (-not $repoExists) {
  Write-Host "[Traffic AI] Creating GitHub repository $repoFullName ..." -ForegroundColor Cyan
  if ($Visibility -eq "private") {
    gh repo create $repoFullName --private --description "AI traffic vehicle detection, tracking and counting system" --disable-wiki
  } else {
    gh repo create $repoFullName --public --description "AI traffic vehicle detection, tracking and counting system" --disable-wiki
  }
  if ($LASTEXITCODE -ne 0) { throw "Unable to create GitHub repository $repoFullName" }
} else {
  Write-Host "[OK] GitHub repository already exists: $repoFullName" -ForegroundColor Green
}

$origin = git remote get-url origin 2>$null
if ($LASTEXITCODE -eq 0 -and $origin) {
  if ($origin -ne $repoUrl) {
    git remote set-url origin $repoUrl
    if ($LASTEXITCODE -ne 0) { throw "Unable to update origin" }
  }
} else {
  git remote add origin $repoUrl
  if ($LASTEXITCODE -ne 0) { throw "Unable to configure origin" }
}

Write-Host "[OK] GitHub target is ready." -ForegroundColor Green
Write-Host "Account : $login"
Write-Host "Repo    : https://github.com/$repoFullName"
Write-Host "Branch  : $Branch"
