[CmdletBinding()]
param(
  [switch]$SkipDockerBuild
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root


function Assert-PowerShellSyntaxContract {
  Write-Host "`n[Traffic AI] PowerShell syntax contract" -ForegroundColor Cyan
  $scriptFiles = Get-ChildItem $PSScriptRoot -Filter "*.ps1" -File
  foreach ($scriptFile in $scriptFiles) {
    $tokens = $null
    $parseErrors = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
      $scriptFile.FullName,
      [ref]$tokens,
      [ref]$parseErrors
    ) | Out-Null
    if ($parseErrors.Count -gt 0) {
      $details = ($parseErrors | ForEach-Object { "line $($_.Extent.StartLineNumber): $($_.Message)" }) -join "; "
      throw "PowerShell syntax lỗi trong $($scriptFile.Name): $details"
    }
  }
  Write-Host "[OK] PowerShell syntax contract" -ForegroundColor Green
}


function Assert-LocalHttpsBootstrapContract {
  Write-Host "`n[Traffic AI] Local HTTPS bootstrap contract" -ForegroundColor Cyan
  $requiredScripts = @(
    (Join-Path $PSScriptRoot "generate-dev-cert.ps1"),
    (Join-Path $PSScriptRoot "ensure-local-https.ps1"),
    (Join-Path $PSScriptRoot "setup-local-machine.ps1")
  )
  foreach ($path in $requiredScripts) {
    if (-not (Test-Path $path)) { throw "Thiếu script HTTPS bootstrap: $path" }
  }
  $startText = Get-Content (Join-Path $PSScriptRoot "start.ps1") -Raw
  if ($startText -notmatch 'ensure-local-https\.ps1') {
    throw "start.ps1 chưa gọi ensure-local-https.ps1."
  }
  if ($startText -match 'HTTPS certificate not found') {
    throw "start.ps1 vẫn còn blocker certificate thủ công của phiên bản cũ."
  }
  Write-Host "[OK] Local HTTPS bootstrap contract" -ForegroundColor Green
}


function Assert-BackendHealthContract {
  Write-Host "`n[Traffic AI] Backend healthcheck dependency contract" -ForegroundColor Cyan
  $routesText = Get-Content (Join-Path $root "backend\app\api\routes.py") -Raw
  if ($routesText -notmatch '@router\.get\("/system/status"\)') {
    throw "Thiếu /api/system/status để tách kiểm tra AI khỏi Backend healthcheck."
  }
  $composeText = Get-Content (Join-Path $root "docker-compose.yml") -Raw
  if ($composeText -notmatch '/api/health') {
    throw "Docker Backend healthcheck không dùng /api/health."
  }
  $migration2 = Get-Content (Join-Path $root "backend\alembic\versions\0002_ai_pipeline.py") -Raw
  $migration3 = Get-Content (Join-Path $root "backend\alembic\versions\0003_yolo26_baseline.py") -Raw
  if ($migration2 -match 'ON CONFLICT ON CONSTRAINT' -or $migration3 -match 'ON CONFLICT ON CONSTRAINT') {
    throw "Migration vẫn phụ thuộc tên unique constraint cũ."
  }
  Write-Host "[OK] Backend healthcheck dependency contract" -ForegroundColor Green
}


function Assert-FrontendUtf8Contract {
  Write-Host "`n[Traffic AI] Frontend UTF-8/Vietnamese text contract" -ForegroundColor Cyan
  $frontendRoot = Join-Path $root "frontend"
  $sourceRoot = Join-Path $frontendRoot "src"

  # Chỉ kiểm tra source do con người chỉnh sửa. Không quét dist/node_modules vì
  # Vite/esbuild có thể serialize Unicode thành \uXXXX trong bundle sinh tự động.
  $files = @()
  if (Test-Path $sourceRoot) {
    $files += Get-ChildItem $sourceRoot -Recurse -File | Where-Object { $_.Extension -in @(".jsx", ".js", ".css", ".html", ".json") }
  }
  foreach ($name in @("index.html", "vite.config.js", "package.json")) {
    $path = Join-Path $frontendRoot $name
    if (Test-Path $path) { $files += Get-Item $path }
  }

  foreach ($file in $files) {
    $text = Get-Content $file.FullName -Raw -Encoding UTF8
    if ($text -match '\\u[0-9A-Fa-f]{4}') {
      throw "Frontend source còn Unicode escape dạng literal trong $($file.FullName). Hãy lưu trực tiếp tiếng Việt UTF-8 thay vì \uXXXX trong JSX/HTML source."
    }
  }

  $indexText = Get-Content (Join-Path $frontendRoot "index.html") -Raw -Encoding UTF8
  if ($indexText -notmatch '<meta charset="UTF-8"') {
    throw "frontend/index.html thiếu meta charset UTF-8."
  }
  Write-Host "[OK] Frontend UTF-8/Vietnamese text contract" -ForegroundColor Green
}


function Assert-FrontendBrandingContract {
  Write-Host "`n[Traffic AI] Frontend logo/favicon contract" -ForegroundColor Cyan
  $frontendRoot = Join-Path $root "frontend"
  $favicon = Join-Path $frontendRoot "public\favicon.svg"
  $logo = Join-Path $frontendRoot "public\logo.svg"
  $manifest = Join-Path $frontendRoot "public\site.webmanifest"
  $faviconIco = Join-Path $frontendRoot "public\favicon.ico"
  $appleIcon = Join-Path $frontendRoot "public\apple-touch-icon.png"
  foreach ($path in @($favicon, $faviconIco, $appleIcon, $logo, $manifest)) {
    if (-not (Test-Path $path)) { throw "Thiếu tài nguyên nhận diện web: $path" }
  }
  $indexText = Get-Content (Join-Path $frontendRoot "index.html") -Raw -Encoding UTF8
  if ($indexText -notmatch 'rel="icon"' -or $indexText -notmatch '/favicon\.svg') {
    throw "frontend/index.html chưa khai báo favicon Traffic AI."
  }
  if ($indexText -notmatch 'rel="manifest"' -or $indexText -notmatch '/site\.webmanifest') {
    throw "frontend/index.html chưa khai báo web manifest."
  }
  $mainText = Get-Content (Join-Path $frontendRoot "src\main.jsx") -Raw -Encoding UTF8
  if ($mainText -notmatch '/logo\.svg') {
    throw "Sidebar chưa sử dụng logo.svg."
  }
  Write-Host "[OK] Frontend logo/favicon contract" -ForegroundColor Green
}

function Remove-LegacyReleaseScripts {
  Write-Host "`n[Traffic AI] Legacy release script cleanup" -ForegroundColor Cyan
  $removed = @()
  foreach ($legacy in @("release.ps1", "push-github.ps1")) {
    $legacyPath = Join-Path $PSScriptRoot $legacy
    if (Test-Path $legacyPath) {
      try {
        Remove-Item $legacyPath -Force -ErrorAction Stop
      } catch {
        throw "Không thể xóa script legacy '$legacyPath'. Hãy đóng file nếu đang mở và kiểm tra quyền ghi. Chi tiết: $($_.Exception.Message)"
      }
      $removed += $legacy
      Write-Host "[CLEAN] Đã xóa script cũ còn sót lại: $legacy" -ForegroundColor Yellow
    }
  }
  if ($removed.Count -eq 0) {
    Write-Host "[OK] Không còn script phát hành legacy." -ForegroundColor Green
  } else {
    Write-Host "[OK] Đã dọn script legacy. Từ nay chỉ dùng .\\scripts\\publish.ps1." -ForegroundColor Green
  }
}

function Assert-ReleaseFallbackContract {
  Write-Host "`n[Traffic AI] GitHub Release fallback contract" -ForegroundColor Cyan
  $publishText = Get-Content (Join-Path $PSScriptRoot "publish.ps1") -Raw -Encoding UTF8
  if ($publishText -notmatch 'New-DirectGitHubRelease -Tag \$tag') {
    throw "publish.ps1 thiếu fallback tạo GitHub Release trực tiếp."
  }
  if ($publishText -match 'GitHub Actions Release thất bại\. Xem chi tiết') {
    throw "publish.ps1 vẫn dừng cứng khi GitHub Actions Release thất bại."
  }
  if ($publishText -match '\[string\]\$Version') {
    throw "publish.ps1 không được nhận version thủ công; phải đọc từ file VERSION."
  }
  foreach ($legacy in @("release.ps1", "push-github.ps1")) {
    if (Test-Path (Join-Path $PSScriptRoot $legacy)) {
      throw "Không dọn được script legacy $legacy. Hãy kiểm tra quyền ghi trong thư mục scripts."
    }
  }
  $releaseText = Get-Content (Join-Path $root ".github\workflows\release.yml") -Raw -Encoding UTF8
  if ($releaseText -notmatch 'Create GitHub Release' -or $releaseText -notmatch 'Verify VERSION matches tag') {
    throw "release.yml thiếu verify/release contract."
  }
  $workflowFiles = Get-ChildItem (Join-Path $root ".github\workflows") -Filter "*.yml" -File
  foreach ($workflow in $workflowFiles) {
    $workflowText = Get-Content $workflow.FullName -Raw -Encoding UTF8
    if ($workflowText -match '(?m)^\s*DATABASE_URL_OVERRIDE:\s+sqlite\+pysqlite:///:memory:\s*$') {
      throw "Workflow YAML có DATABASE_URL_OVERRIDE kết thúc bằng dấu ':' nhưng chưa được quote: $($workflow.FullName)"
    }
  }
  Write-Host "[OK] GitHub Release fallback contract" -ForegroundColor Green
}


function Assert-TechnologyVersionsContract {
  Write-Host "`n[Traffic AI] Technology versions contract" -ForegroundColor Cyan
  $checks = @(
    @{ Path = "backend\requirements.txt"; Needle = "fastapi==0.141.1" },
    @{ Path = "backend\requirements.txt"; Needle = "uvicorn[standard]==0.53.0" },
    @{ Path = "backend\requirements.txt"; Needle = "SQLAlchemy==2.0.54" },
    @{ Path = "backend\requirements.txt"; Needle = "psycopg[binary]==3.3.6" },
    @{ Path = "backend\requirements.txt"; Needle = "alembic==1.20.0" },
    @{ Path = "backend\requirements.txt"; Needle = "pydantic==2.13.5" },
    @{ Path = "backend\requirements.txt"; Needle = "pydantic-settings==2.15.0" },
    @{ Path = "backend\requirements.txt"; Needle = "httpx2==2.13.0" },
    @{ Path = "ai-service\requirements.txt"; Needle = "opencv-python-headless==5.0.0.93" },
    @{ Path = "ai-service\requirements.txt"; Needle = "torch==2.14.0" },
    @{ Path = "ai-service\requirements.txt"; Needle = "torchvision==0.29.0" },
    @{ Path = "ai-service\requirements.txt"; Needle = "ultralytics==8.4.158" },
    @{ Path = "ai-service\requirements.txt"; Needle = "httpx2==2.13.0" },
    @{ Path = "frontend\package.json"; Needle = '"react": "19.3.0"' },
    @{ Path = "frontend\package.json"; Needle = '"react-dom": "19.3.0"' },
    @{ Path = "frontend\package.json"; Needle = '"vite": "8.3.0"' },
    @{ Path = "frontend\package.json"; Needle = '"@vitejs/plugin-react": "6.1.1"' },
    @{ Path = "docker-compose.yml"; Needle = "postgres:18.6" },
    @{ Path = "docker-compose.yml"; Needle = "nginx:1.31.6-alpine" },
    @{ Path = "backend\Dockerfile"; Needle = "python:3.14.7-slim" },
    @{ Path = "ai-service\Dockerfile"; Needle = "python:3.14.7-slim" },
    @{ Path = "frontend\Dockerfile"; Needle = "node:26.9.0-alpine" },
    @{ Path = "frontend\Dockerfile"; Needle = "nginx:1.31.6-alpine" },
    @{ Path = "frontend\Dockerfile"; Needle = "npm@12.1.0" }
  )
  foreach ($check in $checks) {
    $path = Join-Path $root $check.Path
    $text = Get-Content $path -Raw -Encoding UTF8
    if (-not $text.Contains($check.Needle)) {
      throw "Thiếu phiên bản công nghệ đã chốt '$($check.Needle)' trong $($check.Path)."
    }
  }
  Write-Host "[OK] Technology versions contract" -ForegroundColor Green
}

function Assert-SourceManagementContract {
  Write-Host "`n[Traffic AI] Camera/video source management contract" -ForegroundColor Cyan
  $routes = Get-Content (Join-Path $root "backend\app\api\routes.py") -Raw -Encoding UTF8
  $aiMain = Get-Content (Join-Path $root "ai-service\app\main.py") -Raw -Encoding UTF8
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  if ($routes -notmatch '/sources/videos' -or $routes -notmatch '/source-status' -or $routes -notmatch '/sources/validate' -or $routes -notmatch 'source_repaired') {
    throw "Backend thiếu source listing/status/preflight/auto-repair."
  }
  if ($aiMain -notmatch '/sources/validate' -or $aiMain -notmatch 'inspect_source') {
    throw "AI Service thiếu source validation trước khi chạy pipeline."
  }
  if ($frontend -notmatch 'Cập nhật camera' -or $frontend -notmatch 'videoSources' -or $frontend -notmatch 'Dùng nguồn gợi ý') {
    throw "Frontend thiếu workflow sửa nguồn camera/video cũ."
  }
  Write-Host "[OK] Camera/video source management contract" -ForegroundColor Green
}

function Assert-GatewayRuntimeContract {
  Write-Host "`n[Traffic AI] Gateway Docker-DNS/502 resilience contract" -ForegroundColor Cyan
  $nginxText = Get-Content (Join-Path $root "gateway\nginx.conf") -Raw -Encoding UTF8
  $startText = Get-Content (Join-Path $PSScriptRoot "start.ps1") -Raw -Encoding UTF8
  if ($nginxText -notmatch 'resolver 127\.0\.0\.11' -or $nginxText -notmatch 'server frontend:80 resolve' -or $nginxText -notmatch 'server backend:8000 resolve' -or $nginxText -notmatch 'server ai-service:8001 resolve') {
    throw "Gateway chưa dùng Docker DNS động cho frontend/backend/AI Service."
  }
  if ($nginxText -notmatch 'zone traffic_ai_frontend' -or $nginxText -notmatch 'zone traffic_ai_backend' -or $nginxText -notmatch 'zone traffic_ai_service') {
    throw "Nginx upstream động thiếu shared zone."
  }
  if ($startText -notmatch '--force-recreate.*gateway' -or $startText -notmatch 'Test-HttpsEndpoint') {
    throw "start.ps1 chưa recreate/verify Gateway sau khi Docker Compose thay container IP."
  }
  Write-Host "[OK] Gateway Docker-DNS/502 resilience contract" -ForegroundColor Green
}

function Assert-VersionConsistencyContract {
  Write-Host "`n[Traffic AI] Version/migration consistency contract" -ForegroundColor Cyan
  $version = (Get-Content (Join-Path $root "VERSION") -Raw -Encoding UTF8).Trim()
  if ($version -ne "0.3.3") { throw "VERSION phải là 0.3.3, hiện tại: $version" }
  $migration = Join-Path $root "backend\alembic\versions\0011_gateway_dns_runtime.py"
  if (-not (Test-Path $migration)) { throw "Thiếu migration 0011_gateway_dns_runtime.py." }
  $migrationText = Get-Content $migration -Raw -Encoding UTF8
  if ($migrationText -notmatch 'revision = "0011_gateway_dns_runtime"' -or $migrationText -notmatch "value='0.3.3'") {
    throw "Migration 0011_gateway_dns_runtime không đúng contract V0.3.3."
  }
  Write-Host "[OK] Version/migration consistency contract" -ForegroundColor Green
}

function Invoke-Step([string]$Title, [scriptblock]$Action) {
  Write-Host "`n[Traffic AI] $Title" -ForegroundColor Cyan
  & $Action
  if ($LASTEXITCODE -ne 0) { throw "$Title failed with exit code $LASTEXITCODE" }
  Write-Host "[OK] $Title" -ForegroundColor Green
}

Remove-LegacyReleaseScripts
Assert-PowerShellSyntaxContract
Assert-LocalHttpsBootstrapContract
Assert-BackendHealthContract
Assert-FrontendUtf8Contract
Assert-FrontendBrandingContract
Assert-ReleaseFallbackContract
Assert-TechnologyVersionsContract
Assert-SourceManagementContract
Assert-GatewayRuntimeContract
Assert-VersionConsistencyContract

Write-Host "`n[Traffic AI] Smart Gate 3.0 / session reset + track continuity contract" -ForegroundColor Cyan
$countingText = Get-Content (Join-Path $root "ai-service\app\counting.py") -Raw -Encoding UTF8
$classText = Get-Content (Join-Path $root "ai-service\app\classification.py") -Raw -Encoding UTF8
$frontendText = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
$trackerText = Get-Content (Join-Path $root "ai-service\app\bytetrack_traffic.yaml") -Raw -Encoding UTF8
$smartRoutesText = Get-Content (Join-Path $root "backend\app\api\routes.py") -Raw -Encoding UTF8
if ($countingText -notmatch 'dead_band_ratio' -or $countingText -notmatch 'counted_directions' -or $countingText -notmatch 'total_crossings') {
  throw "Smart Gate 2.0 thiếu dead-band hoặc đếm hai chiều."
}
if ($classText -notmatch 'TrackLabelSmoother' -or $frontendText -notmatch 'CountingLineEditor' -or $frontendText -notmatch 'Dừng AI để chỉnh vạch') {
  throw "Thiếu ổn định nhãn theo Track ID hoặc trình chỉnh vạch trực tiếp/khóa khi AI chạy."
}
if ($trackerText -notmatch 'track_buffer: 100' -or $smartRoutesText -notmatch 'preview.jpg') {
  throw "Thiếu ByteTrack traffic profile V3 hoặc endpoint preview để đặt vạch."
}
$trackingText = Get-Content (Join-Path $root "ai-service\app\tracking.py") -Raw -Encoding UTF8
if ($trackingText -notmatch 'TrackContinuityResolver' -or $frontendText -notmatch 'sessionCounts' -or $frontendText -notmatch 'Bộ đếm phiên mới đã reset về 0') {
  throw "Thiếu track stitching hoặc bộ đếm frontend theo từng phiên."
}
Write-Host "[OK] Smart Gate 3.0 / session reset + track continuity contract" -ForegroundColor Green

Write-Host "`n[Traffic AI] AI counting/persistence contract" -ForegroundColor Cyan
$workerText = Get-Content (Join-Path $root "ai-service\app\worker.py") -Raw -Encoding UTF8
$routesText = Get-Content (Join-Path $root "backend\app\api\routes.py") -Raw -Encoding UTF8
if ($workerText -notmatch 'y2\)' -or $workerText -notmatch '_pending_events' -or $workerText -notmatch '_notify_finished') {
  throw "AI worker thiếu bottom-center counting/retry persistence contract."
}
if ($routesText -notmatch 'Reconcile stale DB state' -or $routesText -notmatch 'VehicleCount') {
  throw "Backend thiếu stale-session reconciliation hoặc hourly vehicle_counts persistence."
}
Write-Host "[OK] AI counting/persistence contract" -ForegroundColor Green

Invoke-Step "Backend syntax check" {
  docker run --rm -v "${root}:/src" -w /src/backend python:3.14.7-slim python -m compileall -q app tests alembic
}

Invoke-Step "AI service syntax check" {
  docker run --rm -v "${root}:/src" -w /src/ai-service python:3.14.7-slim python -m compileall -q app tests
}

Invoke-Step "Backend unit tests" {
  docker run --rm `
    -e DATABASE_URL_OVERRIDE=sqlite+pysqlite:///:memory: `
    -e AI_SERVICE_URL=http://127.0.0.1:8001 `
    -e PYTHONPATH=/src/backend `
    -e PIP_ROOT_USER_ACTION=ignore `
    -e PIP_DISABLE_PIP_VERSION_CHECK=1 `
    -v "${root}:/src" -w /src/backend python:3.14.7-slim `
    sh -lc "python -m pip install -q --upgrade pip==26.2.1 && python -m pip install -q -r requirements-test.txt && python -m pytest -q"
}

Invoke-Step "AI service unit tests" {
  docker run --rm `
    -e PYTHONPATH=/src/ai-service `
    -e PIP_ROOT_USER_ACTION=ignore `
    -e PIP_DISABLE_PIP_VERSION_CHECK=1 `
    -v "${root}:/src" -w /src/ai-service python:3.14.7-slim `
    sh -lc "python -m pip install -q --upgrade pip==26.2.1 && python -m pip install -q -r requirements-test.txt && python -m pytest -q"
}

Invoke-Step "Frontend build" {
  $frontendDist = Join-Path $root "frontend\dist"
  $frontendLock = Join-Path $root "frontend\package-lock.json"
  if (Test-Path $frontendDist) { Remove-Item $frontendDist -Recurse -Force }
  if (Test-Path $frontendLock) { Remove-Item $frontendLock -Force }
  docker run --rm -v "${root}:/src" -w /src/frontend node:26.9.0-alpine `
    sh -lc "npm install -g npm@12.1.0 && npm install && npm audit --audit-level=high && npm run build"
}

if (-not $SkipDockerBuild) {
  Invoke-Step "Docker Compose validation" {
    docker compose -f docker-compose.yml -f docker-compose.gpu.yml config --quiet
  }
  Invoke-Step "Docker image build" {
    docker compose build backend ai-service frontend
  }
}

Write-Host "`n[SUCCESS] All Traffic AI tests passed." -ForegroundColor Green
