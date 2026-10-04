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
$repoFullName = "$Owner/$Repository"
if ($Owner -notmatch '^[A-Za-z0-9][A-Za-z0-9-]*$' -or $Repository -notmatch '^[A-Za-z0-9_.-]+$') {
  throw "Owner hoặc Repository không hợp lệ."
}

function Assert-Command([string]$Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "$Name chưa được cài đặt hoặc không có trong PATH."
  }
}

function Invoke-Checked([scriptblock]$Action, [string]$Message) {
  & $Action
  if ($LASTEXITCODE -ne 0) { throw $Message }
}

# PowerShell 5.1 có thể biến stderr native thành lỗi terminating khi Stop.
# Probe cần đọc exit code (Release chưa tồn tại/run chưa xuất hiện) để fallback.
function Invoke-QuietProbe([string]$Command, [string[]]$Arguments) {
  $ErrorActionPreference = "Continue"
  $PSNativeCommandUseErrorActionPreference = $false
  $output = @(& $Command @Arguments 2>$null)
  return [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = $output }
}

function Assert-GitHubPushTarget {
  # github-init đổi origin URL nhưng Git vẫn ưu tiên pushurl cấu hình riêng.
  $urls = @(git remote get-url --push --all origin)
  if ($LASTEXITCODE -ne 0 -or $urls.Count -eq 0) { throw "Không đọc được origin push URL." }
  foreach ($url in $urls) {
    $matched = $url -match '^(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)(?<repo>[^/]+/[^/]+?)(?:\.git)?/?$'
    if (-not $matched -or $Matches.repo -ine $repoFullName) {
      throw "Origin push URL '$url' khác repository đích '$repoFullName'. Cập nhật/xóa remote.origin.pushurl trước khi publish."
    }
  }
}

function Assert-NoTrackedSecrets {
  $tracked = @(git ls-files)
  if ($LASTEXITCODE -ne 0) { throw "Không đọc được danh sách file Git theo dõi." }
  $secrets = @($tracked | Where-Object {
    ($_ -match '(^|/)\.env($|\.)' -and $_ -notmatch '(^|/)\.env\.example$') -or
    $_ -match '^gateway/certs/.*\.(key|pem|pfx|p12)$'
  })
  if ($secrets.Count -gt 0) {
    throw "Từ chối phát hành vì Git đang theo dõi file bí mật: $($secrets -join ', ')"
  }
}

function New-DirectGitHubRelease([string]$Tag) {
  Write-Host "[Traffic AI] Chuyển sang tạo Release trực tiếp bằng GitHub CLI..." -ForegroundColor Yellow
  # Chỉ thay các artifact của release này; giữ các bản phát hành khác.
  $distRoot = Join-Path (Join-Path $root "dist-release") $Tag
  New-Item -ItemType Directory -Path $distRoot -Force | Out-Null

  $zip = Join-Path $distRoot "traffic-ai-$Tag.zip"
  $tar = Join-Path $distRoot "traffic-ai-$Tag.tar.gz"
  $readme = Join-Path $distRoot "traffic-ai-$Tag-README.md"
  $sums = Join-Path $distRoot "SHA256SUMS.txt"
  $prefix = "traffic-ai-$Tag/"

  Invoke-Checked { git archive --format=zip --prefix=$prefix -o $zip "refs/tags/$Tag" } "Không tạo được ZIP release."
  Invoke-Checked { git archive --format=tar.gz --prefix=$prefix -o $tar "refs/tags/$Tag" } "Không tạo được TAR.GZ release."
  # Lấy đúng byte README từ tag đã kiểm thử, kể cả khi working tree đổi sau push.
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $archive = [System.IO.Compression.ZipFile]::OpenRead($zip)
  try {
    $entry = $archive.GetEntry("$($prefix)README.md")
    if (-not $entry) { throw "Tag $Tag thiếu README.md." }
    [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $readme, $true)
  } finally {
    $archive.Dispose()
  }

  $lines = @()
  foreach ($artifact in @($zip, $tar, $readme)) {
    $hash = (Get-FileHash -Algorithm SHA256 $artifact).Hash.ToLowerInvariant()
    $lines += "$hash  $(Split-Path $artifact -Leaf)"
  }
  Set-Content -Path $sums -Value $lines -Encoding ascii

  $probe = Invoke-QuietProbe -Command gh -Arguments @("release", "view", $Tag, "--repo", $repoFullName)
  if ($probe.ExitCode -ne 0) {
    $createResult = Invoke-QuietProbe -Command gh -Arguments @("release", "create", $Tag, $zip, $tar, $readme, $sums, "--repo", $repoFullName, "--title", "Traffic AI $Tag", "--notes-file", $readme, "--verify-tag")
    if ($createResult.ExitCode -eq 0) {
      Write-Host "[OK] Đã tạo GitHub Release trực tiếp: $Tag" -ForegroundColor Green
      return
    }
    # Workflow có thể vừa tạo Release trong lúc CLI chờ; kiểm tra trước khi retry.
    $probe = Invoke-QuietProbe -Command gh -Arguments @("release", "view", $Tag, "--repo", $repoFullName)
    if ($probe.ExitCode -ne 0) { throw "Tạo GitHub Release trực tiếp thất bại. Kiểm tra GitHub CLI, mạng và quyền ghi repository." }
  }
  # Retry phải bổ sung đủ tài sản cho Release đã tồn tại/được tạo dở.
  Invoke-Checked { gh release upload $Tag $zip $tar $readme $sums --repo $repoFullName --clobber } "Upload tài sản GitHub Release thất bại."
  Invoke-Checked { gh release edit $Tag --repo $repoFullName --draft=false } "Không hoàn tất được GitHub Release đang ở trạng thái draft."
  Write-Host "[OK] GitHub Release $Tag có đủ ZIP, TAR.GZ, README và SHA256SUMS." -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host " Traffic AI - Kiểm thử, đẩy GitHub và tạo Release tự động" -ForegroundColor Cyan
Write-Host " Phiên bản: $tag" -ForegroundColor Cyan
Write-Host " Repository: https://github.com/$repoFullName" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor DarkCyan

Assert-Command git
Assert-Command gh
if (-not $SkipTests) { Assert-Command docker }
Invoke-Checked { git check-ref-format --branch $Branch 1>$null } "Tên nhánh '$Branch' không hợp lệ."

# github-init.ps1 đặt tên nhánh; không để nó đổi tên một nhánh đang có ngoài ý muốn.
if (Test-Path (Join-Path $root ".git")) {
  $currentBranch = (git branch --show-current).Trim()
  if ($LASTEXITCODE -ne 0 -or $currentBranch -ne $Branch) {
    throw "Đang ở nhánh '$currentBranch', yêu cầu nhánh '$Branch'. Hãy checkout đúng nhánh trước khi publish."
  }
}
$packageJson = Join-Path $root "frontend/package.json"
$pkg = Get-Content $packageJson -Raw -Encoding utf8 | ConvertFrom-Json
if ($pkg.version -ne $Version) {
  throw "frontend/package.json version=$($pkg.version) khác VERSION=$Version. Đồng bộ trước khi kiểm thử/publish."
}
# Kiểm thử đúng source chuẩn hóa; không sửa VERSION/package.json sau khi test.
$global:LASTEXITCODE = 0
& "$PSScriptRoot/normalize-line-endings.ps1"
if ($LASTEXITCODE -ne 0) { throw "Chuẩn hóa line endings thất bại." }

if (-not $SkipTests) {
  Write-Host "`n[BƯỚC 1/6] Chạy toàn bộ kiểm thử..." -ForegroundColor Cyan
  $global:LASTEXITCODE = 0
  & "$PSScriptRoot/test.ps1"
  if ($LASTEXITCODE -ne 0) {
    throw "Kiểm thử thất bại. Dừng quy trình; không đẩy GitHub và không tạo Release."
  }
} else {
  Write-Host "`n[BƯỚC 1/6] Bỏ qua kiểm thử theo yêu cầu -SkipTests." -ForegroundColor Yellow
}

Write-Host "`n[BƯỚC 2/6] Kiểm tra/tạo repository GitHub..." -ForegroundColor Cyan
$global:LASTEXITCODE = 0
& "$PSScriptRoot/github-init.ps1" -Owner $Owner -Repository $Repository -Visibility $Visibility -Branch $Branch
if ($LASTEXITCODE -ne 0) { throw "Khởi tạo GitHub repository thất bại." }
Assert-GitHubPushTarget

Write-Host "`n[BƯỚC 3/6] Kiểm tra dữ liệu nhạy cảm và tag hiện có..." -ForegroundColor Cyan
Assert-NoTrackedSecrets
# Không có --exit-code: tag chưa tồn tại là thành công với kết quả rỗng;
# lỗi mạng/auth phải dừng, không được nhầm với tag mới.
$remoteTagLines = @(git ls-remote --tags origin "refs/tags/$tag" "refs/tags/$tag^{}")
if ($LASTEXITCODE -ne 0) { throw "Không kiểm tra được tag trên GitHub. Kiểm tra mạng và quyền truy cập rồi chạy lại." }
$remoteTagSha = $null
$directRemoteSha = $null
foreach ($line in $remoteTagLines) {
  $parts = $line -split '\s+', 2
  if ($parts.Count -ne 2) { continue }
  if ($parts[1] -eq "refs/tags/$tag^{}") { $remoteTagSha = $parts[0] }
  elseif ($parts[1] -eq "refs/tags/$tag") { $directRemoteSha = $parts[0] }
}
if (-not $remoteTagSha) { $remoteTagSha = $directRemoteSha }

$tagProbe = Invoke-QuietProbe -Command git -Arguments @("show-ref", "--verify", "--quiet", "refs/tags/$tag")
$tagStatus = $tagProbe.ExitCode
if ($tagStatus -notin @(0, 1)) { throw "Không kiểm tra được tag local $tag." }
$localTagExists = ($tagStatus -eq 0)

Write-Host "`n[BƯỚC 4/6] Commit source và tạo/kiểm tra tag $tag..." -ForegroundColor Cyan
Invoke-Checked { git add -A } "git add thất bại."
Assert-NoTrackedSecrets
$pending = @(git status --porcelain)
if ($LASTEXITCODE -ne 0) { throw "Không đọc được Git status." }
if (($localTagExists -or $remoteTagSha) -and $pending.Count -gt 0) {
  throw "Tag $tag đã tồn tại nhưng source còn thay đổi. Tăng VERSION cho thay đổi mới; không di chuyển tag đã phát hành."
}
if ($pending.Count -gt 0) {
  Invoke-Checked { git commit -m "chore(release): $tag" } "git commit thất bại. Hãy cấu hình git user.name và user.email nếu cần."
} else {
  Write-Host "[OK] Không có thay đổi source mới cần commit." -ForegroundColor Green
}
$headSha = (git rev-parse --verify HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw "Repository chưa có commit để phát hành." }
if ($localTagExists) {
  $localTagSha = (git rev-parse "refs/tags/$tag^{commit}").Trim()
  if ($LASTEXITCODE -ne 0 -or $localTagSha -ne $headSha) {
    throw "Tag local $tag không trỏ tới HEAD hiện tại. Tăng VERSION; không di chuyển tag đã tồn tại."
  }
  if ($directRemoteSha) {
    $localTagObject = (git rev-parse "refs/tags/$tag").Trim()
    if ($LASTEXITCODE -ne 0 -or $localTagObject -ne $directRemoteSha) {
      throw "Tag object local $tag khác tag trên GitHub. Lấy lại tag gốc từ GitHub trước khi tiếp tục; không ghi đè tag remote."
    }
  }
}
if ($remoteTagSha -and $remoteTagSha -ne $headSha) {
  throw "Tag $tag trên GitHub không trỏ tới HEAD hiện tại. Tăng VERSION; không ghi đè tag."
}
if (-not $localTagExists) {
  if ($remoteTagSha) {
    # Giữ đúng tag object trên remote, tránh tạo lại annotated tag có timestamp mới.
    Invoke-Checked { git fetch origin "refs/tags/$tag`:refs/tags/$tag" } "Không lấy được tag $tag đã tồn tại để tiếp tục phát hành."
  } else {
    Invoke-Checked { git tag -a $tag -m "Traffic AI $tag" } "Tạo tag $tag thất bại."
  }
}

Write-Host "`n[BƯỚC 5/6] Đẩy source và tag lên GitHub..." -ForegroundColor Cyan
Invoke-Checked { git push -u origin $Branch } "Đẩy nhánh $Branch lên GitHub thất bại. Chạy lại publish sau khi xử lý lỗi; tag local được giữ để tiếp tục."
Invoke-Checked { git push origin "refs/tags/$tag" } "Đẩy tag $tag lên GitHub thất bại. Chạy lại publish để tiếp tục."

Write-Host "`n[BƯỚC 6/6] GitHub Actions tạo Release..." -ForegroundColor Cyan
if ($NoWait) {
  Write-Host "[OK] Đã đẩy source và tag; Release đang chờ GitHub Actions (-NoWait)." -ForegroundColor Yellow
  Write-Host "Theo dõi: gh run list --repo $repoFullName --workflow release.yml" -ForegroundColor Yellow
  Write-Host "Kiểm tra Release: gh release view $tag --repo $repoFullName" -ForegroundColor Yellow
  return
}

$runId = $null
for ($i = 1; $i -le 45; $i++) {
  Start-Sleep -Seconds 2
  $probe = Invoke-QuietProbe -Command gh -Arguments @("run", "list", "--repo", $repoFullName, "--workflow", "release.yml", "--commit", $headSha, "--event", "push", "--limit", "100", "--json", "databaseId,headBranch,headSha,event,status,conclusion,createdAt")
  $json = $probe.Output -join "`n"
  if ($probe.ExitCode -eq 0 -and $json) {
    $runs = $json | ConvertFrom-Json
    # Một commit có thể có nhiều tag/run. Chỉ chờ đúng tag và đúng commit push.
    $match = $runs | Where-Object {
      $_.headSha -eq $headSha -and $_.headBranch -eq $tag -and $_.event -eq "push"
    } | Sort-Object createdAt -Descending | Select-Object -First 1
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
  # Hiển thị progress; giữ stderr thất bại để nhánh fallback chạy trên PS 5.1.
  $watchExit = & {
    $ErrorActionPreference = "Continue"
    $PSNativeCommandUseErrorActionPreference = $false
    gh run watch $runId --repo $repoFullName --exit-status | Out-Host
    $LASTEXITCODE
  }
  if ($watchExit -ne 0) {
    Write-Host "[WARNING] GitHub Actions Release thất bại. Đang lấy chẩn đoán rồi fallback sang GitHub CLI..." -ForegroundColor Yellow
    $probe = Invoke-QuietProbe -Command gh -Arguments @("run", "view", "$runId", "--repo", $repoFullName, "--log-failed")
    $probe.Output | Out-Host
    if ($probe.ExitCode -ne 0) {
      Write-Host "[INFO] Workflow không có step log. Xem run summary:" -ForegroundColor DarkYellow
      $probe = Invoke-QuietProbe -Command gh -Arguments @("run", "view", "$runId", "--repo", $repoFullName)
      $probe.Output | Out-Host
    }
    New-DirectGitHubRelease -Tag $tag
  } else {
    $probe = Invoke-QuietProbe -Command gh -Arguments @("release", "view", $tag, "--repo", $repoFullName, "--json", "assets,isDraft")
    $releaseJson = $probe.Output -join "`n"
    $releaseStatus = $probe.ExitCode
    $isDraft = $false
    $assetNames = @()
    if ($releaseStatus -eq 0 -and $releaseJson) {
      $release = $releaseJson | ConvertFrom-Json
      $isDraft = [bool]$release.isDraft
      $assetNames = @($release.assets | ForEach-Object { $_.name })
    }
    $requiredAssets = @("traffic-ai-$tag.zip", "traffic-ai-$tag.tar.gz", "traffic-ai-$tag-README.md", "SHA256SUMS.txt")
    $missingAssets = @($requiredAssets | Where-Object { $_ -notin $assetNames })
    if ($releaseStatus -ne 0 -or $missingAssets.Count -gt 0 -or $isDraft) {
      Write-Host "[WARNING] Workflow đã hoàn tất nhưng Release/tài sản chưa đủ. Fallback sang GitHub CLI..." -ForegroundColor Yellow
      New-DirectGitHubRelease -Tag $tag
    }
  }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkGreen
Write-Host " [THÀNH CÔNG] Traffic AI $tag đã được phát hành." -ForegroundColor Green
Write-Host " Source : https://github.com/$repoFullName" -ForegroundColor Green
Write-Host " Release: https://github.com/$repoFullName/releases/tag/$tag" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor DarkGreen
