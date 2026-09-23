[CmdletBinding()]
param(
  [string]$Owner = "TamNhien",
  [string]$Repository = "traffic-ai",
  [ValidateSet("public", "private")]
  [string]$Visibility = "private",
  [string]$Branch = "main",
  [switch]$SkipTests,
  [switch]$NoWait
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$versionFile = Join-Path $root "VERSION"
if (-not (Test-Path $versionFile)) { throw "Không tìm thấy file VERSION." }
$Version = (Get-Content $versionFile -Raw -Encoding utf8).Trim()
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "VERSION hiện tại không hợp lệ: '$Version'" }
$tag = "v$Version"

function Assert-Command([string]$Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "$Name chưa được cài đặt hoặc không có trong PATH."
  }
}

function Invoke-Checked([scriptblock]$Action, [string]$Message) {
  & $Action
  if ($LASTEXITCODE -ne 0) { throw $Message }
}

function New-DirectGitHubRelease([string]$Tag) {
  Write-Host "[Traffic AI] Chuyển sang tạo Release trực tiếp bằng GitHub CLI..." -ForegroundColor Yellow
  $distRoot = Join-Path $root "dist-release"
  if (Test-Path $distRoot) { Remove-Item $distRoot -Recurse -Force }
  New-Item -ItemType Directory -Path $distRoot | Out-Null

  $zip = Join-Path $distRoot "traffic-ai-$Tag.zip"
  $tar = Join-Path $distRoot "traffic-ai-$Tag.tar.gz"
  $readme = Join-Path $distRoot "traffic-ai-$Tag-README.md"
  $sums = Join-Path $distRoot "SHA256SUMS.txt"
  $prefix = "traffic-ai-$Tag/"

  Invoke-Checked { git archive --format=zip --prefix=$prefix -o $zip $Tag } "Không tạo được ZIP release."
  Invoke-Checked { git archive --format=tar.gz --prefix=$prefix -o $tar $Tag } "Không tạo được TAR.GZ release."
  Copy-Item (Join-Path $root "README.md") $readme -Force

  $lines = @()
  foreach ($artifact in @($zip, $tar, $readme)) {
    $hash = (Get-FileHash -Algorithm SHA256 $artifact).Hash.ToLowerInvariant()
    $lines += "$hash  $(Split-Path $artifact -Leaf)"
  }
  Set-Content -Path $sums -Value $lines -Encoding ascii

  gh release view $Tag --repo "$Owner/$Repository" 1>$null 2>$null
  if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] GitHub Release $Tag đã tồn tại." -ForegroundColor Green
    return
  }

  gh release create $Tag $zip $tar $readme $sums --repo "$Owner/$Repository" --title "Traffic AI $Tag" --notes-file $readme --verify-tag
  if ($LASTEXITCODE -ne 0) { throw "Tạo GitHub Release trực tiếp thất bại." }
  Write-Host "[OK] Đã tạo GitHub Release trực tiếp: $Tag" -ForegroundColor Green
}

Write-Host "" 
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host " Traffic AI - Kiểm thử, đẩy GitHub và tạo Release tự động" -ForegroundColor Cyan
Write-Host " Phiên bản: $tag" -ForegroundColor Cyan
Write-Host " Repository: https://github.com/$Owner/$Repository" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor DarkCyan

Assert-Command git
Assert-Command gh
Assert-Command docker

if (-not $SkipTests) {
  Write-Host "`n[BƯỚC 1/6] Chạy toàn bộ kiểm thử..." -ForegroundColor Cyan
  & "$PSScriptRoot\test.ps1"
  if ($LASTEXITCODE -ne 0) {
    throw "Kiểm thử thất bại. Dừng quy trình; không đẩy GitHub và không tạo Release."
  }
} else {
  Write-Host "`n[BƯỚC 1/6] Bỏ qua kiểm thử theo yêu cầu -SkipTests." -ForegroundColor Yellow
}

Write-Host "`n[BƯỚC 2/6] Kiểm tra/tạo repository GitHub..." -ForegroundColor Cyan
& "$PSScriptRoot\github-init.ps1" -Owner $Owner -Repository $Repository -Visibility $Visibility -Branch $Branch
if ($LASTEXITCODE -ne 0) { throw "Khởi tạo GitHub repository thất bại." }

$currentBranch = (git branch --show-current).Trim()
if ($currentBranch -ne $Branch) {
  throw "Đang ở nhánh '$currentBranch', yêu cầu nhánh '$Branch'."
}

Write-Host "`n[BƯỚC 3/6] Cập nhật số phiên bản và kiểm tra dữ liệu nhạy cảm..." -ForegroundColor Cyan
Set-Content -Path (Join-Path $root "VERSION") -Value $Version -NoNewline -Encoding utf8

$packageJson = Join-Path $root "frontend\package.json"
$pkg = Get-Content $packageJson -Raw -Encoding utf8 | ConvertFrom-Json
$pkg.version = $Version
$pkg | ConvertTo-Json -Depth 20 | Set-Content -Path $packageJson -Encoding utf8

# Không bao giờ phát hành .env hoặc khóa riêng TLS.
git ls-files --error-unmatch .env 1>$null 2>$null
if ($LASTEXITCODE -eq 0) {
  throw "Từ chối phát hành vì file .env đang được Git theo dõi. Hãy bỏ .env khỏi Git trước."
}

$privateKeys = @(git ls-files "gateway/certs/*.key")
if ($privateKeys.Count -gt 0) {
  throw "Từ chối phát hành vì khóa riêng TLS đang được Git theo dõi: $($privateKeys -join ', ')"
}

# Bảo đảm tag chưa tồn tại ở local hoặc remote.
git rev-parse $tag 1>$null 2>$null
if ($LASTEXITCODE -eq 0) {
  throw "Tag $tag đã tồn tại ở local. Hãy dùng phiên bản mới."
}

git ls-remote --exit-code --tags origin "refs/tags/$tag" 1>$null 2>$null
if ($LASTEXITCODE -eq 0) {
  throw "Tag $tag đã tồn tại trên GitHub. Hãy dùng phiên bản mới."
}

Write-Host "`n[BƯỚC 4/6] Commit source và tạo tag $tag..." -ForegroundColor Cyan
Invoke-Checked { git add -A } "git add thất bại."
$pending = git status --porcelain
if ($pending) {
  Invoke-Checked { git commit -m "chore(release): $tag" } "git commit thất bại. Hãy cấu hình git user.name và user.email nếu cần."
} else {
  Write-Host "[OK] Không có thay đổi source mới cần commit." -ForegroundColor Green
}

Invoke-Checked { git rev-parse --verify HEAD 1>$null } "Repository chưa có commit để phát hành."
Invoke-Checked { git tag -a $tag -m "Traffic AI $tag" } "Tạo tag $tag thất bại."

Write-Host "`n[BƯỚC 5/6] Đẩy source và tag lên GitHub..." -ForegroundColor Cyan
Invoke-Checked { git push -u origin $Branch } "Đẩy nhánh $Branch lên GitHub thất bại."
Invoke-Checked { git push origin $tag } "Đẩy tag $tag lên GitHub thất bại."

Write-Host "`n[BƯỚC 6/6] GitHub Actions tạo Release..." -ForegroundColor Cyan
if ($NoWait) {
  Write-Host "[OK] Đã đẩy tag. Không chờ GitHub Actions vì có -NoWait." -ForegroundColor Yellow
  Write-Host "Theo dõi: gh run list --workflow release.yml" -ForegroundColor Yellow
} else {
  $runId = $null
  $tagSha = (git rev-list -n 1 $tag).Trim()
  for ($i = 1; $i -le 45; $i++) {
    Start-Sleep -Seconds 2
    $json = gh run list --repo "$Owner/$Repository" --workflow release.yml --limit 30 --json databaseId,headBranch,headSha,status,conclusion 2>$null
    if ($LASTEXITCODE -eq 0 -and $json) {
      $runs = $json | ConvertFrom-Json
      $match = $runs | Where-Object { $_.headSha -eq $tagSha -or $_.headBranch -eq $tag } | Select-Object -First 1
      if ($match) {
        $runId = $match.databaseId
        break
      }
    }
    Write-Host "  Đang chờ workflow Release xuất hiện... ($i/45)"
  }

  if (-not $runId) {
    New-DirectGitHubRelease -Tag $tag
  } else {
    Write-Host "[Traffic AI] Theo dõi GitHub Actions run #$runId..." -ForegroundColor Cyan
    gh run watch $runId --repo "$Owner/$Repository" --exit-status
    if ($LASTEXITCODE -ne 0) {
      Write-Host "[WARNING] GitHub Actions Release thất bại. Đang lấy log lỗi rồi fallback sang GitHub CLI..." -ForegroundColor Yellow
      gh run view $runId --repo "$Owner/$Repository" --log-failed
      New-DirectGitHubRelease -Tag $tag
    } else {
      gh release view $tag --repo "$Owner/$Repository" 1>$null 2>$null
      if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARNING] Workflow đã hoàn tất nhưng chưa tạo Release. Fallback sang GitHub CLI..." -ForegroundColor Yellow
        New-DirectGitHubRelease -Tag $tag
      }
    }
  }
}

Write-Host "" 
Write-Host "============================================================" -ForegroundColor DarkGreen
Write-Host " [THÀNH CÔNG] Traffic AI $tag đã được phát hành." -ForegroundColor Green
Write-Host " Source : https://github.com/$Owner/$Repository" -ForegroundColor Green
Write-Host " Release: https://github.com/$Owner/$Repository/releases/tag/$tag" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor DarkGreen
