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
    @{ Path = "frontend\Dockerfile"; Needle = "node:26.10.0-alpine" },
    @{ Path = "frontend\package.json"; Needle = '"node": ">=26.10.0"' },
    @{ Path = ".nvmrc"; Needle = "26.10.0" },
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


function Assert-CiNodePortabilityV0510Contract {
  Write-Host "`n[Traffic AI] CI + Node.js portability V0.5.10" -ForegroundColor Cyan
  $workflowFiles = @(
    (Join-Path $root ".github\workflows\release.yml")
    (Join-Path $root ".github\workflows\ci.yml")
    (Join-Path $root ".github\workflows\ci-release-reusable.yml")
  )
  foreach ($workflow in $workflowFiles) {
    $text = Get-Content $workflow -Raw -Encoding UTF8
    if ($text -match 'actions/checkout@v4' -or $text -match 'actions/setup-python@v5' -or $text -match 'actions/setup-node@v4') {
      throw "Workflow vẫn còn GitHub Action chạy Node.js 20: $workflow"
    }
    if ($text -notmatch 'actions/checkout@v7' -or $text -notmatch 'actions/setup-python@v7') {
      throw "Workflow chưa nâng checkout/setup-python lên major Node.js 24: $workflow"
    }
  }
  $releaseText = Get-Content (Join-Path $root ".github\workflows\release.yml") -Raw -Encoding UTF8
  $ciText = Get-Content (Join-Path $root ".github\workflows\ci.yml") -Raw -Encoding UTF8
  $reusableText = Get-Content (Join-Path $root ".github\workflows\ci-release-reusable.yml") -Raw -Encoding UTF8
  foreach ($text in @($releaseText, $ciText, $reusableText)) {
    if ($text -notmatch 'AI_DATASET_ROOT:.*runner\.temp' -or $text -notmatch 'AI_TRAINING_ROOT:.*runner\.temp' -or $text -notmatch 'AI_MODEL_ROOT:.*runner\.temp') {
      throw "GitHub Actions AI test chưa dùng runner.temp cho dữ liệu ghi được."
    }
  }
  foreach ($text in @($releaseText, $ciText, $reusableText)) {
    if ($text -match 'Set up Node\.js' -and ($text -notmatch 'actions/setup-node@v7' -or $text -notmatch "node-version: '26\.10\.0'")) {
      throw "Workflow frontend chưa dùng setup-node@v7 + Node.js 26.10.0."
    }
  }
  $training = Get-Content (Join-Path $root "ai-service\app\training.py") -Raw -Encoding UTF8
  if ($training -notmatch 'AI_MODEL_ROOT' -or $training -notmatch 'AI_DATASET_ROOT' -or $training -notmatch 'AI_TRAINING_ROOT') {
    throw "AI training roots chưa cấu hình qua environment cho CI/non-Docker."
  }
  Write-Host "[OK] CI + Node.js portability V0.5.10" -ForegroundColor Green
}

function Assert-CountingLineUiCleanupContract {
  Write-Host "`n[Traffic AI] Counting line UI cleanup contract" -ForegroundColor Cyan
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  if ($frontend -match 'Nguyên tắc:' -or $frontend -match 'Kéo đường vàng để di chuyển' -or $frontend -match 'kéo 2 đầu tròn') {
    throw "Counting line vẫn còn dòng nguyên tắc/hướng dẫn overlay đã yêu cầu loại bỏ."
  }
  Write-Host "[OK] Counting line UI cleanup contract" -ForegroundColor Green
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
  if ($version -ne "0.5.23") { throw "VERSION phải là 0.5.23, hiện tại: $version" }
  $migration = Join-Path $root "backend\alembic\versions\0037_integrity_v0523.py"
  if (-not (Test-Path $migration)) { throw "Thiếu migration 0037_integrity_v0523.py." }
  $migrationText = Get-Content $migration -Raw -Encoding UTF8
  if ($migrationText -notmatch 'revision = "0037_integrity_v0523"' -or $migrationText -notmatch 'down_revision = "0036_gt_reuse_v0522"' -or $migrationText -notmatch "value='0.5.23'") {
    throw "Migration 0037_integrity_v0523 không đúng contract V0.5.23."
  }
  Write-Host "[OK] Version/migration consistency contract" -ForegroundColor Green
}

function Assert-AlembicRevisionSafetyContract {
  Write-Host "`n[Traffic AI] Alembic revision-length safety V0.5.23" -ForegroundColor Cyan
  $versionsDir = Join-Path $root "backend\alembic\versions"
  $bad = @()
  Get-ChildItem $versionsDir -Filter "*.py" | ForEach-Object {
    $text = Get-Content $_.FullName -Raw -Encoding UTF8
    $match = [regex]::Match($text, '(?m)^revision(?:\s*:\s*str)?\s*=\s*"([^"]+)"')
    if ($match.Success) {
      $revisionId = $match.Groups[1].Value
      if ($revisionId.Length -gt 32) {
        $bad += "$($_.Name): $revisionId ($($revisionId.Length) ký tự)"
      }
    }
  }
  if ($bad.Count -gt 0) {
    throw ("Alembic revision ID vượt 32 ký tự:`n" + ($bad -join "`n"))
  }
  $entrypoint = Get-Content (Join-Path $root "backend\entrypoint.sh") -Raw -Encoding UTF8
  if ($entrypoint -notmatch 'ALTER COLUMN version_num TYPE VARCHAR\(128\)' -or $entrypoint -notmatch '0017_ai_test_dep_v053') {
    throw "Backend entrypoint thiếu self-heal cho alembic_version hoặc mapping revision V0.5.3."
  }
  $v17 = Get-Content (Join-Path $versionsDir "0017_ai_test_dependency_isolation_v053.py") -Raw -Encoding UTF8
  if ($v17 -notmatch 'revision = "0017_ai_test_dep_v053"') {
    throw "Migration V0.5.3 chưa dùng revision ID rút gọn an toàn."
  }
  Write-Host "[OK] Alembic revision-length safety V0.5.23" -ForegroundColor Green
}


function Assert-ReleaseLineEndingHygieneV0512Contract {
  Write-Host "`n[Traffic AI] Release line-ending hygiene V0.5.12" -ForegroundColor Cyan
  $attributes = Get-Content (Join-Path $root ".gitattributes") -Raw -Encoding UTF8
  $publish = Get-Content (Join-Path $PSScriptRoot "publish.ps1") -Raw -Encoding UTF8
  $normalizerPath = Join-Path $PSScriptRoot "normalize-line-endings.ps1"
  if (-not (Test-Path $normalizerPath)) { throw "Thiếu normalize-line-endings.ps1." }
  $normalizer = Get-Content $normalizerPath -Raw -Encoding UTF8
  if ($attributes -notmatch '\*\.ps1 text eol=crlf' -or $attributes -notmatch '\*\.json text eol=lf' -or $attributes -notmatch '\*\.py text eol=lf') {
    throw ".gitattributes chưa chốt CRLF cho PowerShell và LF cho source/config."
  }
  if ($publish -notmatch 'normalize-line-endings\.ps1' -or $publish -notmatch 'git add -A') {
    throw "publish.ps1 chưa normalize line endings trước khi git add."
  }
  if ($normalizer -notmatch 'UTF8Encoding' -or $normalizer -notmatch '"crlf"' -or $normalizer -notmatch '"lf"') {
    throw "Line-ending normalizer thiếu UTF-8 no-BOM hoặc hai mode LF/CRLF."
  }
  Write-Host "[OK] Release line-ending hygiene V0.5.12" -ForegroundColor Green
}

function Assert-RoadGuardV0512Contract {
  Write-Host "`n[Traffic AI] Road Guard 2.0 V0.5.12" -ForegroundColor Cyan
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  $routes = Get-Content (Join-Path $root "backend\app\api\routes.py") -Raw -Encoding UTF8
  $geometry = Get-Content (Join-Path $root "backend\app\geometry.py") -Raw -Encoding UTF8
  $counting = Get-Content (Join-Path $root "ai-service\app\counting.py") -Raw -Encoding UTF8
  $envExample = Get-Content (Join-Path $root ".env.example") -Raw -Encoding UTF8
  if ($frontend -notmatch 'validateCountingGeometry' -or $frontend -notmatch 'ROAD GUARD hợp lệ' -or $frontend -notmatch '!countingGeometryState\.valid') {
    throw "Frontend thiếu Road Guard validation/fail-closed save."
  }
  if ($routes -notmatch 'validate_counting_geometry' -or $geometry -notmatch 'Hai đầu vạch đếm phải nằm trong vùng Lòng đường') {
    throw "Backend thiếu validation polygon/vạch Road Guard."
  }
  if ($counting -notmatch 'self\.road_zone\.contains\(previous\.point' -or $counting -notmatch 'AI_ROAD_ZONE_PROBE_RATIO') {
    throw "AI counter chưa yêu cầu anchor trước/sau nằm trong Road Zone hoặc thiếu probe ratio."
  }
  if ($envExample -notmatch 'AI_ROAD_ZONE_PROBE_RATIO=0\.018') {
    throw ".env.example thiếu Road Zone probe ratio V0.5.12."
  }
  Write-Host "[OK] Road Guard 2.0 V0.5.12" -ForegroundColor Green
}


function Assert-InstantOverlayRoadRoiV0513Contract {
  Write-Host "`n[Traffic AI] Instant Overlay + Road ROI V0.5.13" -ForegroundColor Cyan
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  $css = Get-Content (Join-Path $root "frontend\src\styles.css") -Raw -Encoding UTF8
  $worker = Get-Content (Join-Path $root "ai-service\app\worker.py") -Raw -Encoding UTF8
  $roi = Get-Content (Join-Path $root "ai-service\app\gate_roi.py") -Raw -Encoding UTF8
  $aiMain = Get-Content (Join-Path $root "ai-service\app\main.py") -Raw -Encoding UTF8
  $envExample = Get-Content (Join-Path $root ".env.example") -Raw -Encoding UTF8
  $startText = Get-Content (Join-Path $PSScriptRoot "start.ps1") -Raw -Encoding UTF8

  if ($frontend -notmatch 'overlayReady' -or $frontend -notmatch 'overlay-loading-badge' -or $frontend -notmatch 'native-preview') {
    throw "Frontend thiếu native-video fallback khi AI Overlay đang chờ frame đầu tiên."
  }
  if ($css -notmatch 'dual-preview-stage' -or $css -notmatch 'overlay-preview') {
    throw "CSS thiếu dual-layer preview cho chuyển AI Overlay không màn hình đen."
  }
  if ($worker -notmatch 'AI warming up' -or $worker -notmatch 'AI_DETECTION_ROI' -or $worker -notmatch 'road_zone_roi' -or $worker -notmatch 'AI_REFINE_BACKGROUND_WARMUP') {
    throw "AI worker thiếu prime JPEG, Road ROI tracking hoặc background refiner warmup V0.5.13."
  }
  if ($roi -notmatch 'def road_zone_roi') {
    throw "Thiếu road_zone_roi để detect/track xe xuyên suốt phần lòng đường."
  }
  if ($aiMain -notmatch 'X-Accel-Buffering' -or $aiMain -notmatch 'no-store, no-cache') {
    throw "MJPEG stream thiếu header chống proxy/browser buffering."
  }
  if ($envExample -notmatch 'AI_DETECTION_ROI=full' -or $envExample -notmatch 'AI_ROAD_ROI_MARGIN=0\.02' -or $envExample -notmatch 'AI_REFINE_BACKGROUND_WARMUP=1') {
    throw ".env.example thiếu tuning Instant Overlay/Road ROI V0.5.13."
  }
  if ($startText -notmatch 'AI_DETECTION_ROI.*full' -or $startText -notmatch 'AI_REFINE_BACKGROUND_WARMUP.*1') {
    throw "start.ps1 chưa tự bổ sung tuning V0.5.13 vào .env cũ."
  }
  Write-Host "[OK] Instant Overlay + Road ROI V0.5.13" -ForegroundColor Green
}



function Assert-FullFrameDetectStrictRoadCountV0514Contract {
  Write-Host "`n[Traffic AI] Full-frame Detect + Strict Road Count V0.5.14" -ForegroundColor Cyan
  $worker = Get-Content (Join-Path $root "ai-service\app\worker.py") -Raw -Encoding UTF8
  $runtime = Get-Content (Join-Path $root "ai-service\app\runtime.py") -Raw -Encoding UTF8
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  $envExample = Get-Content (Join-Path $root ".env.example") -Raw -Encoding UTF8
  $startText = Get-Content (Join-Path $PSScriptRoot "start.ps1") -Raw -Encoding UTF8
  if ($worker -notmatch 'AI_DETECTION_ROI.*, "full"' -or $worker -notmatch 'self\.detection_roi_mode == "gate"' -or $worker -notmatch 'detections_current_frame' -or $worker -notmatch 'road_tracks_current_frame') {
    throw "AI worker chưa tách full-frame detection khỏi Road Zone counting hoặc thiếu telemetry DET/ROAD."
  }
  if ($runtime -notmatch 'active_tracks' -or $runtime -notmatch 'road_tracks_current_frame' -or $runtime -notmatch 'detection_roi_mode: str = "full"') {
    throw "PipelineState thiếu telemetry realtime hoặc default full detection V0.5.14."
  }
  if ($frontend -notmatch 'DETECT.*TOUPPER' -and $frontend -notmatch 'DETECT.*toUpperCase') {
    throw "Frontend thiếu telemetry mode quét detector V0.5.14."
  }
  if ($frontend -notmatch 'detections_current_frame' -or $frontend -notmatch 'active_tracks' -or $frontend -notmatch 'road_tracks_current_frame') {
    throw "Frontend thiếu DET/track/road telemetry để chẩn đoán bỏ sót."
  }
  if ($envExample -notmatch 'AI_DETECTION_ROI=full' -or $startText -notmatch 'AI_DETECTION_POLICY_V0514' -or $startText -notmatch 'road -> full') {
    throw "Thiếu default/migration one-time từ Road ROI sang full-frame detect."
  }
  Write-Host "[OK] Full-frame Detect + Strict Road Count V0.5.14" -ForegroundColor Green
}

function Assert-HybridRecallTrackRescueV0515Contract {
  Write-Host "`n[Traffic AI] Hybrid Recall + Track Rescue V0.5.15" -ForegroundColor Cyan
  $worker = Get-Content (Join-Path $root "ai-service\app\worker.py") -Raw -Encoding UTF8
  $runtime = Get-Content (Join-Path $root "ai-service\app\runtime.py") -Raw -Encoding UTF8
  $tracker = Get-Content (Join-Path $root "ai-service\app\bytetrack_traffic.yaml") -Raw -Encoding UTF8
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  $envExample = Get-Content (Join-Path $root ".env.example") -Raw -Encoding UTF8
  $startText = Get-Content (Join-Path $PSScriptRoot "start.ps1") -Raw -Encoding UTF8
  $schema = Get-Content (Join-Path $root "backend\app\schemas\camera.py") -Raw -Encoding UTF8

  if ($worker -notmatch 'AI_HYBRID_RECALL' -or $worker -notmatch 'AI_RECALL_MODEL_NAME' -or $worker -notmatch '_looks_like_custom_model' -or $worker -notmatch 'self\.detector_model_name') {
    throw "AI worker thiếu hybrid recall: pretrained detector + activated best.pt refiner."
  }
  if ($worker -notmatch '_draw_raw_detection' -or $worker -notmatch 'untracked_detections') {
    throw "AI worker vẫn có thể giấu detection chưa được ByteTrack cấp ID."
  }
  if ($runtime -notmatch 'untracked_detections' -or $runtime -notmatch 'detector_model_name' -or $runtime -notmatch 'hybrid_mode') {
    throw "PipelineState thiếu telemetry hybrid/untracked V0.5.15."
  }
  if ($tracker -notmatch 'track_high_thresh: 0\.05' -or $tracker -notmatch 'new_track_thresh: 0\.05' -or $tracker -notmatch 'track_buffer: 150') {
    throw "ByteTrack chưa dùng high-recall traffic profile V0.5.15."
  }
  if ($envExample -notmatch 'AI_IMGSZ=960' -or $envExample -notmatch 'AI_HYBRID_RECALL=1' -or $envExample -notmatch 'AI_RECALL_MODEL_NAME=yolo26s\.pt') {
    throw ".env.example thiếu imgsz 960 / hybrid recall defaults."
  }
  if ($startText -notmatch 'AI_HYBRID_POLICY_V0515' -or $startText -notmatch 'AI_IMGSZ=960') {
    throw "start.ps1 chưa nâng .env cũ sang high-recall profile V0.5.15."
  }
  if ($frontend -notmatch 'YOLO thấy xe nhưng ByteTrack chưa cấp ID' -or $frontend -notmatch 'untracked_detections' -or $frontend -notmatch 'HYBRID detect') {
    throw "Frontend thiếu telemetry/cảnh báo DET nhưng chưa có track ID."
  }
  if ($schema -notmatch 'default=0\.06' -or $schema -notmatch 'ge=0\.02') {
    throw "Camera confidence chưa hạ baseline để cứu xe nhỏ/nhanh."
  }
  Write-Host "[OK] Hybrid Recall + Track Rescue V0.5.15" -ForegroundColor Green
}

function Assert-AutoRoadZoneV0516Contract {
  Write-Host "`n[Traffic AI] Auto Road-Zone Calibration V0.5.16" -ForegroundColor Cyan
  $flow = Get-Content (Join-Path $root "ai-service\app\flow_calibration.py") -Raw -Encoding UTF8
  $worker = Get-Content (Join-Path $root "ai-service\app\worker.py") -Raw -Encoding UTF8
  $runtime = Get-Content (Join-Path $root "ai-service\app\runtime.py") -Raw -Encoding UTF8
  $aiMain = Get-Content (Join-Path $root "ai-service\app\main.py") -Raw -Encoding UTF8
  $routes = Get-Content (Join-Path $root "backend\app\api\routes.py") -Raw -Encoding UTF8
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  $css = Get-Content (Join-Path $root "frontend\src\styles.css") -Raw -Encoding UTF8
  $envExample = Get-Content (Join-Path $root ".env.example") -Raw -Encoding UTF8
  $startText = Get-Content (Join-Path $PSScriptRoot "start.ps1") -Raw -Encoding UTF8
  if ($flow -notmatch 'class FlowCalibrator' -or $flow -notmatch 'dominant_direction' -or $flow -notmatch 'moving_track_count') {
    throw "Thiếu thuật toán học luồng xe / đề xuất Road Zone V0.5.16."
  }
  if ($worker -notmatch '_flow_calibrator\.add' -or $worker -notmatch 'calibration_proposal' -or $runtime -notmatch 'calibration_ready') {
    throw "AI runtime chưa thu thập quỹ đạo hoặc thiếu telemetry calibration."
  }
  if ($aiMain -notmatch "road-proposal" -or $routes -notmatch 'road-proposal') {
    throw "Thiếu endpoint AI/Backend cho Auto Road-Zone."
  }
  if ($frontend -notmatch 'AI đề xuất theo luồng xe' -or $frontend -notmatch 'Dừng AI \+ áp dụng đề xuất' -or $frontend -notmatch 'calibration_moving_tracks') {
    throw "Frontend thiếu workflow đề xuất/áp dụng Auto Road-Zone."
  }
  if ($css -notmatch '\.auto-road-toolbar' -or $css -notmatch '\.proposal-status') {
    throw "CSS thiếu Auto Road-Zone UI."
  }
  if ($envExample -notmatch 'AI_FLOW_CALIBRATION_HISTORY_FRAMES=1200' -or $startText -notmatch 'AI_FLOW_CALIBRATION_HISTORY_FRAMES') {
    throw "Thiếu cấu hình runtime Auto Road-Zone V0.5.16."
  }
  Write-Host "[OK] Auto Road-Zone Calibration V0.5.16" -ForegroundColor Green
}


function Assert-SingleVehicleGuardV0517Contract {
  Write-Host "`n[Traffic AI] Single-Object BUS/TRUCK Guard V0.5.17" -ForegroundColor Cyan
  $dedup = Get-Content (Join-Path $root "ai-service\app\dedup.py") -Raw -Encoding UTF8
  $worker = Get-Content (Join-Path $root "ai-service\app\worker.py") -Raw -Encoding UTF8
  $runtime = Get-Content (Join-Path $root "ai-service\app\runtime.py") -Raw -Encoding UTF8
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  $envExample = Get-Content (Join-Path $root ".env.example") -Raw -Encoding UTF8
  $startText = Get-Content (Join-Path $PSScriptRoot "start.ps1") -Raw -Encoding UTF8
  if ($dedup -notmatch 'single_heavy_vehicle_plan' -or $dedup -notmatch 'HEAVY_CONFLICTS' -or $dedup -notmatch 'box_iou') {
    throw "Thiếu BUS/TRUCK duplicate suppression implementation V0.5.17."
  }
  if ($worker -notmatch 'agnostic_nms=self\.agnostic_nms' -or $worker -notmatch 'single_heavy_vehicle_plan' -or $worker -notmatch 'alias_raw_id' -or $worker -notmatch 'AI_HEAVY_DUP_IOU') {
    throw "AI worker chưa chặn cross-class NMS / BUS-TRUCK overlap trước counting."
  }
  if ($runtime -notmatch 'suppressed_class_duplicates_current_frame' -or $frontend -notmatch 'gộp bus/truck') {
    throw "Thiếu telemetry Single-Object Guard V0.5.17."
  }
  if ($envExample -notmatch 'AI_AGNOSTIC_NMS=0' -or $envExample -notmatch 'AI_HEAVY_DUP_IOU=0\.68') {
    throw ".env.example thiếu Single-Object Guard defaults."
  }
  if ($startText -notmatch 'AI_AGNOSTIC_NMS' -or $startText -notmatch 'AI_HEAVY_DUP_IOU') {
    throw "start.ps1 chưa bổ sung tuning Single-Object Guard vào .env cũ."
  }
  Write-Host "[OK] Single-Object BUS/TRUCK Guard V0.5.17" -ForegroundColor Green
}


function Assert-CrossingEngineV0518Contract {
  Write-Host "`n[Traffic AI] Crossing Engine 6.0 V0.5.18" -ForegroundColor Cyan
  $counting = Get-Content (Join-Path $root "ai-service\app\counting.py") -Raw -Encoding UTF8
  $runtime = Get-Content (Join-Path $root "ai-service\app\runtime.py") -Raw -Encoding UTF8
  $worker = Get-Content (Join-Path $root "ai-service\app\worker.py") -Raw -Encoding UTF8
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  $envExample = Get-Content (Join-Path $root ".env.example") -Raw -Encoding UTF8
  if ($counting -notmatch 'direct_crossings' -or $counting -notmatch 'interpolated_crossings' -or $counting -notmatch 'crossing_mode_for' -or $counting -notmatch 'interpolation_gap_frames') {
    throw "Thiếu phân loại direct/interpolated/rescued của Crossing Engine 6.0."
  }
  if ($runtime -notmatch 'direct_crossings' -or $runtime -notmatch 'interpolated_crossings' -or $worker -notmatch 'DIRECT-X' -or $worker -notmatch 'INTERP') {
    throw "Thiếu telemetry Crossing Engine 6.0 ở runtime/overlay."
  }
  # Legacy V0.5.18 contract is semantic, not tied to the old UI label "Crossing Engine 6.0".
  # Newer engines (7.x) must preserve the same total/direct/interpolated/rescued breakdown.
  if ($frontend -notmatch 'Trực tiếp' -or $frontend -notmatch 'Nội suy' -or $frontend -notmatch 'Tổng lượt cắt vạch' -or $frontend -notmatch 'rescued_crossings') {
    throw "Frontend thiếu tổng xe hoặc breakdown crossing tương thích V0.5.18+."
  }
  if ($envExample -notmatch 'AI_GATE_INTERPOLATION_GAP=3') {
    throw ".env.example thiếu AI_GATE_INTERPOLATION_GAP=3."
  }
  Write-Host "[OK] Crossing Engine 6.0 V0.5.18" -ForegroundColor Green
}


function Assert-GroundTruthBenchmarkV0519Contract {
  Write-Host "`n[Traffic AI] Ground-truth Counting Benchmark V0.5.19" -ForegroundColor Cyan
  $models = Get-Content (Join-Path $root "backend\app\models\all_models.py") -Raw -Encoding UTF8
  $routes = Get-Content (Join-Path $root "backend\app\api\routes.py") -Raw -Encoding UTF8
  $benchmarking = Get-Content (Join-Path $root "backend\app\benchmarking.py") -Raw -Encoding UTF8
  $eventSchema = Get-Content (Join-Path $root "backend\app\schemas\event.py") -Raw -Encoding UTF8
  $worker = Get-Content (Join-Path $root "ai-service\app\worker.py") -Raw -Encoding UTF8
  $trace = Get-Content (Join-Path $root "ai-service\app\benchmark_trace.py") -Raw -Encoding UTF8
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  $css = Get-Content (Join-Path $root "frontend\src\styles.css") -Raw -Encoding UTF8
  if ($models -notmatch 'class CountingBenchmark' -or $models -notmatch 'class GroundTruthCrossing' -or $models -notmatch 'source_time_seconds') {
    throw "Backend models thiếu benchmark/ground-truth hoặc source timecode V0.5.19."
  }
  if ($routes -notmatch '/benchmarks/\{benchmark_id\}/report' -or $routes -notmatch '/benchmarks/\{benchmark_id\}/marks' -or $routes -notmatch 'legacy_ai_events_without_source_time') {
    throw "Backend API thiếu benchmark report/marks hoặc guard cho session legacy."
  }
  if ($benchmarking -notmatch 'match_crossings' -or $benchmarking -notmatch 'counting_recall' -or $benchmarking -notmatch 'false_positive_items') {
    throw "Benchmark engine thiếu matching Recall/Precision/false-positive."
  }
  if ($eventSchema -notmatch 'source_frame_index' -or $eventSchema -notmatch 'crossing_method' -or $worker -notmatch 'source_time_seconds' -or $worker -notmatch 'crossing_mode_for') {
    throw "AI event chưa ghi timecode/frame/crossing method để đối chiếu ground truth."
  }
  if ($worker -notmatch 'AI_BENCHMARK_TRACE' -or $trace -notmatch 'detector_miss' -or $trace -notmatch 'crossing_gate_miss') {
    throw "V0.5.19 thiếu frame trace hoặc phân loại nguyên nhân xe lọt."
  }
  if ($frontend -notmatch 'GROUND-TRUTH COUNTING BENCHMARK' -or $frontend -notmatch 'Lọt không đếm' -or $frontend -notmatch 'Counting Recall' -or $frontend -notmatch 'Đánh dấu GT') {
    throw "Frontend thiếu Ground-truth Counting Benchmark Studio V0.5.19."
  }
  if ($css -notmatch '\.benchmark-layout' -or $css -notmatch '\.benchmark-diff-list') {
    throw "CSS thiếu Benchmark Studio V0.5.19."
  }
  if ($css -notmatch '\.benchmark-panel,\.benchmark-report-panel\{min-width:0;overflow:hidden\}' -or $css -notmatch '\.benchmark-create-row>label:last-child\{grid-column:1/-1\}' -or $css -notmatch 'max-width:100%;box-sizing:border-box') {
    throw "Benchmark V0.5.19-R1 chưa chống tràn control sang Benchmark Report."
  }
  Write-Host "[OK] Ground-truth Counting Benchmark V0.5.19" -ForegroundColor Green
}

function Assert-BenchmarkGateOverlayV0520Contract {
  Write-Host "`n[Traffic AI] Benchmark gate overlay + IN/OUT V0.5.20" -ForegroundColor Cyan
  $models = Get-Content (Join-Path $root "backend\app\models\all_models.py") -Raw -Encoding UTF8
  $routes = Get-Content (Join-Path $root "backend\app\api\routes.py") -Raw -Encoding UTF8
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  $css = Get-Content (Join-Path $root "frontend\src\styles.css") -Raw -Encoding UTF8
  $migration = Get-Content (Join-Path $root "backend\alembic\versions\0034_benchmark_overlay_v0520.py") -Raw -Encoding UTF8
  if ($models -notmatch 'class CountingBenchmark' -or $models -notmatch 'line_x1' -or $models -notmatch 'road_x4') {
    throw "Benchmark V0.5.20 chưa lưu snapshot vạch/Road Zone."
  }
  if ($routes -notmatch '"geometry"' -or $routes -notmatch 'line_x1=camera\.line_x1' -or $routes -notmatch 'road_x4=camera\.road_x4') {
    throw "Backend benchmark chưa trả/lưu geometry snapshot V0.5.20."
  }
  if ($migration -notmatch 'UPDATE counting_benchmarks AS b' -or $migration -notmatch 'FROM cameras AS c') {
    throw "Migration V0.5.20 chưa backfill geometry cho benchmark V0.5.19 hiện có."
  }
  if ($frontend -notmatch 'function BenchmarkGateOverlay' -or $frontend -notmatch 'VẠCH ĐẾM' -or $frontend -notmatch '>IN<' -or $frontend -notmatch '>OUT<') {
    throw "Frontend benchmark chưa vẽ vạch và nhãn IN/OUT."
  }
  if ($frontend -notmatch 'signed_side\(\)' -or $frontend -notmatch 'negative -> positive') {
    throw "Overlay IN/OUT chưa bám cùng quy ước signed-side với Counting Engine."
  }
  if ($css -notmatch '\.benchmark-gate-overlay' -or $css -notmatch '\.benchmark-count-line' -or $css -notmatch '\.benchmark-road-zone') {
    throw "CSS thiếu lớp overlay vạch/Road Zone cho Benchmark V0.5.20."
  }
  Write-Host "[OK] Benchmark gate overlay + IN/OUT V0.5.20" -ForegroundColor Green
}


function Assert-CrossingEngineV0521Contract {
  Write-Host "`n[Traffic AI] Crossing Engine 7.0 + Benchmark Reconcile V0.5.21" -ForegroundColor Cyan
  $counting = Get-Content (Join-Path $root "ai-service\app\counting.py") -Raw -Encoding UTF8
  $worker = Get-Content (Join-Path $root "ai-service\app\worker.py") -Raw -Encoding UTF8
  $benchmarking = Get-Content (Join-Path $root "backend\app\benchmarking.py") -Raw -Encoding UTF8
  $routes = Get-Content (Join-Path $root "backend\app\api\routes.py") -Raw -Encoding UTF8
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  $envExample = Get-Content (Join-Path $root ".env.example") -Raw -Encoding UTF8
  $start = Get-Content (Join-Path $root "scripts\start.ps1") -Raw -Encoding UTF8
  if ($counting -notmatch 'startup_grace_frames' -or $counting -notmatch 'side_confirm_samples' -or $counting -notmatch 'crossing_cooldown_frames' -or $counting -notmatch 'contains_with_margin') {
    throw "Crossing Engine 7.0 thiếu startup guard / side confirm / cooldown / Road-edge tolerance."
  }
  if ($worker -notmatch 'AI_GATE_STARTUP_GRACE_FRAMES' -or $worker -notmatch 'AI_GATE_SIDE_CONFIRM_SAMPLES' -or $worker -notmatch 'AI_GATE_COOLDOWN_FRAMES' -or $worker -notmatch 'AI_ROAD_ANCHOR_MARGIN_RATIO') {
    throw "AI worker chưa nối tuning V0.5.21 vào Crossing Engine."
  }
  if ($envExample -notmatch 'AI_GATE_STARTUP_GRACE_FRAMES=12' -or $start -notmatch 'AI_GATE_COOLDOWN_FRAMES') {
    throw "Cấu hình runtime V0.5.21 chưa được persist qua .env/start.ps1."
  }
  if ($benchmarking -notmatch 'false_positive_reason_counts' -or $benchmarking -notmatch 'direction_flip_jitter' -or $benchmarking -notmatch 'startup_artifact') {
    throw "Ground-truth analyzer V0.5.21 chưa phân loại nguyên nhân đếm dư."
  }
  if ($routes -notmatch '/benchmarks/\{benchmark_id\}/reconcile' -or $routes -notmatch 'reconciled_at' -or $routes -notmatch 'clone_marks_from_benchmark_id') {
    throw "Backend thiếu endpoint Đối chiếu lại hoặc sao chép Ground Truth V0.5.21."
  }
  $hasGroundTruthReuseUi = ($frontend -match 'Sao chép .* GT sang Session') -or ($frontend -match 'Sao chép .* GT từ Benchmark')
  if ($frontend -notmatch 'Đang đối chiếu' -or $frontend -notmatch 'reconcileStatus' -or $frontend -notmatch 'Nguyên nhân đếm dư nghi ngờ' -or -not $hasGroundTruthReuseUi) {
    throw "Frontend chưa hiển thị trạng thái đối chiếu, analyzer đếm dư hoặc tái sử dụng GT V0.5.21+."
  }
  Write-Host "[OK] Crossing Engine 7.0 + Benchmark Reconcile V0.5.21" -ForegroundColor Green
}


function Assert-GroundTruthReuseV0522Contract {
  Write-Host "`n[Traffic AI] Ground Truth reuse V0.5.22" -ForegroundColor Cyan
  $routes = Get-Content (Join-Path $root "backend\app\api\routes.py") -Raw -Encoding UTF8
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  if ($routes -notmatch '/benchmarks/\{benchmark_id\}/clone-marks' -or $routes -notmatch '_clone_marks_into_existing_benchmark' -or $routes -notmatch 'BenchmarkCloneMarks') {
    throw "Backend V0.5.22 thiếu API sao chép GT vào benchmark đã tạo."
  }
  if ($frontend -notmatch 'compatibleCloneSource' -or $frontend -notmatch 'cloneGroundTruthIntoCurrent' -or $frontend -notmatch 'Sao chép .* GT từ Benchmark') {
    throw "Frontend V0.5.22 chưa hiện nút sao chép GT cho benchmark đích GT=0."
  }
  if ($frontend -notmatch 'onClick=\{\(\)=>createBenchmark\(\)\}' -or $frontend -match 'onClick=\{createBenchmark\}') {
    throw "Frontend V0.5.22 còn truyền React click-event nhầm thành clone source khi tạo benchmark."
  }
  Write-Host "[OK] Ground Truth reuse V0.5.22" -ForegroundColor Green
}


function Assert-BenchmarkIntegrityCrossingV0523Contract {
  Write-Host "`n[Traffic AI] Benchmark Integrity + Crossing Engine 7.1 + Human Guard V0.5.23" -ForegroundColor Cyan
  $worker = Get-Content (Join-Path $root "ai-service\app\worker.py") -Raw -Encoding UTF8
  $counting = Get-Content (Join-Path $root "ai-service\app\counting.py") -Raw -Encoding UTF8
  $human = Get-Content (Join-Path $root "ai-service\app\human_guard.py") -Raw -Encoding UTF8
  $routes = Get-Content (Join-Path $root "backend\app\api\routes.py") -Raw -Encoding UTF8
  $models = Get-Content (Join-Path $root "backend\app\models\all_models.py") -Raw -Encoding UTF8
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  $envExample = Get-Content (Join-Path $root ".env.example") -Raw -Encoding UTF8
  if ($human -notmatch 'human_dominates_two_wheel_candidate' -or $worker -notmatch 'AI_HUMAN_GUARD' -or $worker -notmatch 'PERSON-GUARD') {
    throw "V0.5.23 thiếu Human-vs-Motorcycle Guard cho người bị nhầm thành xe hai bánh."
  }
  if ($counting -notmatch 'fast_confirm_distance_ratio' -or $counting -notmatch 'adaptive_cooldown' -or $counting -notmatch 'rejected_rescue_validation') {
    throw "Crossing Engine 7.1 thiếu fast-confirm / adaptive cooldown / rescue validation."
  }
  if ($routes -notmatch 'worker_total_vehicles' -or $routes -notmatch 'persisted_count' -or $routes -notmatch 'X-TrafficAI-Deduplicated') {
    throw "Benchmark Integrity V0.5.23 chưa đồng bộ worker count với VehicleEvent DB."
  }
  if ($models -notmatch 'dedup_suppressed_events' -or $models -notmatch 'human_guard_rejections' -or $models -notmatch 'crossing_x') {
    throw "Database V0.5.23 thiếu telemetry integrity/crossing signature."
  }
  if ($frontend -notmatch 'Benchmark Integrity' -or $frontend -notmatch 'Human Guard' -or $frontend -notmatch 'Rescue bị loại') {
    throw "Frontend V0.5.23 thiếu Benchmark Integrity / Human Guard telemetry."
  }
  if ($envExample -notmatch 'AI_GATE_ADAPTIVE_COOLDOWN=1' -or $envExample -notmatch 'AI_HUMAN_GUARD=1') {
    throw "Runtime config V0.5.23 thiếu tuning Crossing Engine 7.1 / Human Guard."
  }
  Write-Host "[OK] Benchmark Integrity + Crossing Engine 7.1 + Human Guard V0.5.23" -ForegroundColor Green
}


function Assert-SmoothPlaybackContract {
  Write-Host "`n[Traffic AI] Smooth Playback 4.1 contract" -ForegroundColor Cyan
  $aiMain = Get-Content (Join-Path $root "ai-service\app\main.py") -Raw -Encoding UTF8
  $worker = Get-Content (Join-Path $root "ai-service\app\worker.py") -Raw -Encoding UTF8
  $runtime = Get-Content (Join-Path $root "ai-service\app\runtime.py") -Raw -Encoding UTF8
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  $css = Get-Content (Join-Path $root "frontend\src\styles.css") -Raw -Encoding UTF8
  if ($aiMain -notmatch "/media/video" -or $aiMain -notmatch "FileResponse") {
    throw "AI Service thiếu endpoint phát video native cho browser."
  }
  if ($frontend -notmatch "Phát mượt" -or $frontend -notmatch "<video" -or $frontend -notmatch "AI Overlay" -or $frontend -notmatch "processing_progress") {
    throw "Frontend chưa có Smooth Playback/native video + chế độ AI Overlay."
  }
  if ($worker -notmatch "AI_VIDEO_PACE" -or $worker -notmatch "playback_lag_seconds" -or $worker -notmatch "_latest_jpeg_sequence") {
    throw "AI worker thiếu source pacing/lag metric/new-JPEG sequence."
  }
  if ($runtime -notmatch "source_frame_count" -or $runtime -notmatch "processing_progress" -or $runtime -notmatch "wait_for_jpeg") {
    throw "PipelineState/registry thiếu progress hoặc new-frame wait."
  }
  if ($css -notmatch "counting-overlay" -or $css -notmatch "smooth-badge") {
    throw "Frontend thiếu overlay vạch trên native video."
  }
  Write-Host "[OK] Smooth Playback 4.1 contract" -ForegroundColor Green
}



function Assert-DatasetTrainingContract {
  Write-Host "`n[Traffic AI] Dataset & Fine-tune Studio V0.5.0 contract" -ForegroundColor Cyan
  $models = Get-Content (Join-Path $root "backend\app\models\all_models.py") -Raw -Encoding UTF8
  $routes = Get-Content (Join-Path $root "backend\app\api\routes.py") -Raw -Encoding UTF8
  $training = Get-Content (Join-Path $root "ai-service\app\training.py") -Raw -Encoding UTF8
  $aiMain = Get-Content (Join-Path $root "ai-service\app\main.py") -Raw -Encoding UTF8
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  $compose = Get-Content (Join-Path $root "docker-compose.yml") -Raw -Encoding UTF8
  if ($models -notmatch 'class DatasetRecord' -or $models -notmatch 'class TrainingRun') { throw "Backend thiếu bảng datasets/training_runs." }
  if ($routes -notmatch '/datasets' -or $routes -notmatch '/training/runs' -or $routes -notmatch '/activate') { throw "Backend thiếu API dataset/training/model activation." }
  if ($training -notmatch 'extract_frames' -or $training -notmatch 'auto_label' -or $training -notmatch 'prepare_dataset' -or $training -notmatch 'TrainingRegistry') { throw "AI Service thiếu pipeline dataset/fine-tune." }
  if ($aiMain -notmatch '/datasets/extract' -or $aiMain -notmatch '/training/start') { throw "AI Service thiếu endpoint training." }
  $hasDatasetStudio = $frontend -match 'Dataset giao thông Việt Nam'
  $hasTrainingHandler = $frontend -match 'const\s+startTraining\s*=\s*async' -and $frontend -match 'onClick=\{startTraining\}'
  $hasActivationHandler = $frontend -match 'const\s+activateTraining\s*=\s*async' -and $frontend -match 'activateTraining\(run\)'
  $hasActivationUi = $frontend -match 'Kích hoạt best\.pt'
  if (-not $hasDatasetStudio -or -not $hasTrainingHandler -or -not $hasActivationHandler -or -not $hasActivationUi) { throw "Frontend thiếu Dataset & Fine-tune Studio." }
  if ($compose -notmatch './datasets:/data/datasets' -or $compose -notmatch './training-runs:/data/training-runs') { throw "Docker Compose thiếu volume dataset/training." }
  Write-Host "[OK] Dataset & Fine-tune Studio V0.5.0 contract" -ForegroundColor Green
}

function Assert-AiTestDependencyIsolationContract {
  Write-Host "`n[Traffic AI] AI test dependency isolation V0.5.3" -ForegroundColor Cyan
  $trainingText = Get-Content (Join-Path $root "ai-service\app\training.py") -Raw -Encoding UTF8
  $testReq = Get-Content (Join-Path $root "ai-service\requirements-test.txt") -Raw -Encoding UTF8
  if ($trainingText -match '(?m)^import cv2\s*$' -or $trainingText -match '(?m)^import yaml\s*$') {
    throw "app.training còn import OpenCV/PyYAML ở module scope; unit-test container tối giản sẽ lỗi khi collection."
  }
  if ($trainingText -notmatch '(?m)^\s+import cv2\s*$' -or $trainingText -notmatch '(?m)^\s+import yaml\s*$') {
    throw "app.training thiếu lazy import OpenCV/PyYAML tại chức năng cần dùng."
  }
  if ($testReq -match 'opencv-python-headless' -or $testReq -match '(?m)^PyYAML==') {
    throw "requirements-test.txt không nên kéo dependency CV/training nặng chỉ để collection unit test."
  }
  Write-Host "[OK] AI test dependency isolation V0.5.3" -ForegroundColor Green
}


function Assert-ActivationUiContract {
  Write-Host "`n[Traffic AI] best.pt activation + panel separation V0.5.5" -ForegroundColor Cyan
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  $css = Get-Content (Join-Path $root "frontend\src\styles.css") -Raw -Encoding UTF8
  $routes = Get-Content (Join-Path $root "backend\app\api\routes.py") -Raw -Encoding UTF8
  if ($frontend -notmatch 'readApiBody' -or $frontend -notmatch 'is_active_model' -or $frontend -notmatch 'ĐANG DÙNG best.pt') {
    throw "Frontend thiếu parser API an toàn hoặc trạng thái model đang kích hoạt."
  }
  if ($routes -notmatch 'Idempotent activation' -or $routes -notmatch 'AIModel.model_path == run.best_model_path' -or $routes -notmatch 'already_active') {
    throw "Backend thiếu kích hoạt best.pt idempotent."
  }
  if ($css -notmatch 'margin:20px 0 24px' -or $css -notmatch 'active-model-badge') {
    throw "UI chưa tách khoảng cách các khung hoặc thiếu badge model active."
  }
  Write-Host "[OK] best.pt activation + panel separation V0.5.5" -ForegroundColor Green
}

function Assert-AnnotationStudioContract {
  Write-Host "`n[Traffic AI] Annotation Studio V0.5.7 contract" -ForegroundColor Cyan
  $annotation = Get-Content (Join-Path $root "ai-service\app\annotation.py") -Raw -Encoding UTF8
  $aiMain = Get-Content (Join-Path $root "ai-service\app\main.py") -Raw -Encoding UTF8
  $routes = Get-Content (Join-Path $root "backend\app\api\routes.py") -Raw -Encoding UTF8
  $models = Get-Content (Join-Path $root "backend\app\models\all_models.py") -Raw -Encoding UTF8
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  $css = Get-Content (Join-Path $root "frontend\src\styles.css") -Raw -Encoding UTF8
  if ($annotation -notmatch 'parse_yolo_label' -or $annotation -notmatch 'save_annotation' -or $annotation -notmatch 'difficult') { throw "AI Service thiếu annotation core." }
  if ($aiMain -notmatch '/datasets/\{slug\}/annotations' -or $aiMain -notmatch 'dataset_annotation_save') { throw "AI Service thiếu Annotation API." }
  if ($routes -notmatch '/datasets/\{dataset_id\}/annotations' -or $routes -notmatch 'save_dataset_annotation') { throw "Backend thiếu proxy Annotation Studio." }
  if ($models -notmatch 'reviewed_images' -or $models -notmatch 'difficult_images') { throw "Dataset model thiếu trạng thái review/ảnh khó." }
  $hasAnnotationHotkeyHandler = $frontend.Contains('/^[1-5]$/.test(event.key)')
  $hasAnnotationHotkeyHelp = $frontend -match '1 Xe máy' -and $frontend -match '2 Xe đạp' -and $frontend -match '3 Ô tô' -and $frontend -match '4 Xe buýt' -and $frontend -match '5 Xe tải'
  if ($frontend -notmatch 'ANNOTATION STUDIO' -or $frontend -notmatch 'Lưu nhãn' -or $frontend -notmatch 'Kéo chuột trên ảnh' -or -not $hasAnnotationHotkeyHandler -or -not $hasAnnotationHotkeyHelp) { throw "Frontend thiếu editor gán nhãn tích hợp hoặc hotkey class 1-5." }
  if ($css -notmatch 'annotation-workspace' -or $css -notmatch 'annotation-box') { throw "Frontend thiếu CSS Annotation Studio." }
  Write-Host "[OK] Annotation Studio V0.5.7 contract" -ForegroundColor Green
}


function Assert-AnnotationUxClarityContract {
  Write-Host "`n[Traffic AI] Annotation UX clarity V0.5.7" -ForegroundColor Cyan
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  $css = Get-Content (Join-Path $root "frontend\src\styles.css") -Raw -Encoding UTF8
  if ($frontend -notmatch 'Box \{index\+1\} ·' -or $frontend -notmatch 'Đang chọn: ' -or $frontend -notmatch 'Class cho box mới' -or $frontend -notmatch 'Đổi class box đã chọn') {
    throw "Annotation Studio chưa phân biệt rõ số thứ tự box và class."
  }
  if ($frontend -match '\{id\+1\}\. \{name\}</option>' -or $frontend -match '\{index\+1\}\. \{annotationClasses') {
    throw "Annotation Studio vẫn hiển thị số gây nhầm giữa box index và class."
  }
  if ($frontend -notmatch 'setNewClassId\(box\.class_id\)' -or $frontend -notmatch 'Box 1 · Xe đạp') {
    throw "Click box chưa đồng bộ class hoặc thiếu giải thích Box N · Class."
  }
  if ($css -notmatch 'annotation-selection' -or $css -notmatch 'has-selection') {
    throw "Thiếu trạng thái trực quan cho box đang chọn."
  }
  Write-Host "[OK] Annotation UX clarity V0.5.7" -ForegroundColor Green
}

function Assert-StrictGateV058Contract {
  Write-Host "`n[Traffic AI] Strict Gate + fast crossing V0.5.8" -ForegroundColor Cyan
  $counting = Get-Content (Join-Path $root "ai-service\app\counting.py") -Raw -Encoding UTF8
  $worker = Get-Content (Join-Path $root "ai-service\app\worker.py") -Raw -Encoding UTF8
  $roi = Get-Content (Join-Path $root "ai-service\app\gate_roi.py") -Raw -Encoding UTF8
  $classify = Get-Content (Join-Path $root "ai-service\app\classification.py") -Raw -Encoding UTF8
  $tracker = Get-Content (Join-Path $root "ai-service\app\bytetrack_traffic.yaml") -Raw -Encoding UTF8
  $envText = Get-Content (Join-Path $root ".env.example") -Raw -Encoding UTF8
  $startText = Get-Content (Join-Path $root "scripts\start.ps1") -Raw -Encoding UTF8
  if ($counting -notmatch 'segment_crossing_point' -or $counting -notmatch 'rejected_outside_segment' -or $counting -notmatch 'segment_margin: float = 0.0') {
    throw "V0.5.8 thiếu finite-line strict crossing contract."
  }
  if ($worker -notmatch 'AI_GATE_SEGMENT_MARGIN' -or $worker -notmatch 'AI_REFINE_MAX_PER_FRAME' -or $worker -notmatch 'pending_crossing_events') {
    throw "V0.5.8 thiếu strict gate/runtime anti-lag contract."
  }
  if ($roi -notmatch 'endpoint_margin_ratio' -or $classify -notmatch 'display_label' -or $classify -notmatch 'strong_bicycle_certainty') {
    throw "V0.5.8 thiếu compact ROI hoặc policy xe máy/xe đạp."
  }
  # V0.5.8 established the minimum fast-vehicle tracker sensitivity.
  # Later releases are allowed to make ByteTrack MORE permissive (for example
  # V0.5.15 uses 0.05/0.05 and buffer 150), so do not pin this historical
  # contract to the old literal 0.10 values. Verify semantic compatibility.
  $trackHighMatch = [regex]::Match($tracker, '(?m)^track_high_thresh:\s*([0-9.]+)\s*$')
  $newTrackMatch = [regex]::Match($tracker, '(?m)^new_track_thresh:\s*([0-9.]+)\s*$')
  $trackBufferMatch = [regex]::Match($tracker, '(?m)^track_buffer:\s*([0-9]+)\s*$')
  if (-not $trackHighMatch.Success -or -not $newTrackMatch.Success -or -not $trackBufferMatch.Success) {
    throw "V0.5.8 thiếu tham số ByteTrack bắt buộc cho xe nhanh."
  }
  $invariant = [System.Globalization.CultureInfo]::InvariantCulture
  $trackHigh = [double]::Parse($trackHighMatch.Groups[1].Value, $invariant)
  $newTrack = [double]::Parse($newTrackMatch.Groups[1].Value, $invariant)
  $trackBuffer = [int]::Parse($trackBufferMatch.Groups[1].Value, $invariant)
  if ($trackHigh -gt 0.10 -or $newTrack -gt 0.10 -or $trackBuffer -lt 120 -or $envText -notmatch 'AI_GATE_ENDPOINT_MARGIN=0.035') {
    throw "V0.5.8 thiếu tracker/ROI tuning tương thích cho xe nhanh."
  }
  if ($startText -notmatch 'Set-EnvDefaultUpgrade "AI_GATE_ROI_MARGIN" "0.22" "0.16"' -or $startText -notmatch 'Ensure-EnvSetting "AI_GATE_SEGMENT_MARGIN" "0.0"' -or $startText -notmatch 'Ensure-EnvSetting "AI_REFINE_MAX_PER_FRAME" "1"') {
    throw "V0.5.8 thiếu nâng cấp .env runtime từ tuning cũ sang Strict Gate."
  }
  Write-Host "[OK] Strict Gate + fast crossing V0.5.8" -ForegroundColor Green
}


function Assert-CleanRetrainV059Contract {
  Write-Host "`n[Traffic AI] Clean Retrain + Smart Review V0.5.9" -ForegroundColor Cyan
  $training = Get-Content (Join-Path $root "ai-service\app\training.py") -Raw -Encoding UTF8
  $annotation = Get-Content (Join-Path $root "ai-service\app\annotation.py") -Raw -Encoding UTF8
  $aiMain = Get-Content (Join-Path $root "ai-service\app\main.py") -Raw -Encoding UTF8
  $routes = Get-Content (Join-Path $root "backend\app\api\routes.py") -Raw -Encoding UTF8
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  if ($training -notmatch '_candidate_changed_enough' -or $training -notmatch 'smart_dedupe' -or $training -notmatch 'skipped_similar') {
    throw "V0.5.9 thiếu smart frame extraction / near-duplicate filtering."
  }
  if ($training -notmatch '_review_priority' -or $annotation -notmatch 'review_mode' -or $annotation -notmatch 'accept_safe_annotations') {
    throw "V0.5.9 thiếu Smart Review / review priority / bulk safe accept."
  }
  if ($training -notmatch 'purge_dataset' -or $training -notmatch 'reset_dataset_labels' -or $aiMain -notmatch '/datasets/purge' -or $aiMain -notmatch '/reset-labels') {
    throw "V0.5.9 thiếu reset/xóa dataset vật lý."
  }
  if ($routes -notmatch '@router\.delete\("/datasets/\{dataset_id\}"\)' -or $routes -notmatch '/annotations/accept-safe' -or $routes -notmatch '/reset-labels') {
    throw "Backend V0.5.9 thiếu API xóa/reset dataset hoặc Smart Review proxy."
  }
  if ($frontend -notmatch 'Trích frame thông minh' -or $frontend -notmatch 'Xóa dataset \+ ảnh cũ' -or $frontend -notmatch 'Duyệt nhanh ảnh tin cậy' -or $frontend -notmatch 'Ưu tiên cần kiểm tra') {
    throw "Frontend V0.5.9 thiếu Clean Retrain / Smart Review UX."
  }
  if ($frontend -notmatch 'không tiếp tục học từ best\.pt cũ' -or $frontend -notmatch 'every_n_frames:15' -or $frontend -notmatch 'max_images:600') {
    throw "Frontend V0.5.9 chưa giải thích fresh training run hoặc default sampling mới."
  }
  Write-Host "[OK] Clean Retrain + Smart Review V0.5.9" -ForegroundColor Green
}



function Assert-DatasetControlsVisibilityV0510R1Contract {
  Write-Host "`n[Traffic AI] Dataset controls visibility V0.5.10-R1" -ForegroundColor Cyan
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  $styles = Get-Content (Join-Path $root "frontend\src\styles.css") -Raw -Encoding UTF8
  if ($frontend -notmatch 'Ngưỡng thay đổi' -or $frontend -notmatch 'Loại frame gần trùng' -or $frontend -notmatch 'dataset-create-button' -or $frontend -notmatch 'Tạo dataset · Trích frame thông minh') {
    throw "Frontend thiếu control tạo dataset / lọc frame thông minh."
  }
  if ($frontend -notmatch 'datasetForm\.min_change_ratio' -or $frontend -notmatch 'datasetForm\.smart_dedupe' -or $frontend -notmatch 'onClick=\{createDataset\}') {
    throw "Frontend Dataset Studio chưa nối control vào createDataset."
  }
  if ($styles -notmatch 'container-type:inline-size' -or $styles -notmatch '\.dataset-form \.dataset-create-button\{grid-column:1/-1' -or $styles -notmatch '@container') {
    throw "CSS Dataset Studio chưa chống tràn control theo chiều rộng panel."
  }
  Write-Host "[OK] Dataset controls visibility V0.5.10-R1" -ForegroundColor Green
}

function Assert-LegacySemanticCompatibilityV0523R1 {
  Write-Host "`n[Traffic AI] Legacy semantic contract compatibility V0.5.23-R1" -ForegroundColor Cyan
  $frontend = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
  if ($frontend -notmatch 'Tổng lượt cắt vạch' -or $frontend -notmatch 'direct_crossings' -or $frontend -notmatch 'interpolated_crossings' -or $frontend -notmatch 'rescued_crossings') {
    throw "V0.5.23-R1 thiếu crossing breakdown tương thích các engine cũ."
  }
  if ($frontend -notmatch 'Sao chép .* GT từ Benchmark' -or $frontend -notmatch 'cloneGroundTruthIntoCurrent') {
    throw "V0.5.23-R1 thiếu Ground Truth reuse UI tương thích V0.5.21+."
  }
  Write-Host "[OK] Legacy semantic contract compatibility V0.5.23-R1" -ForegroundColor Green
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
Assert-CiNodePortabilityV0510Contract
Assert-CountingLineUiCleanupContract
Assert-SourceManagementContract
Assert-GatewayRuntimeContract
Assert-VersionConsistencyContract
Assert-AlembicRevisionSafetyContract
Assert-SmoothPlaybackContract
Assert-DatasetTrainingContract
Assert-AiTestDependencyIsolationContract
Assert-ActivationUiContract
Assert-AnnotationStudioContract
Assert-AnnotationUxClarityContract
Assert-StrictGateV058Contract
Assert-CleanRetrainV059Contract
Assert-DatasetControlsVisibilityV0510R1Contract
Assert-ReleaseLineEndingHygieneV0512Contract
Assert-RoadGuardV0512Contract
Assert-InstantOverlayRoadRoiV0513Contract
Assert-FullFrameDetectStrictRoadCountV0514Contract
Assert-HybridRecallTrackRescueV0515Contract
Assert-AutoRoadZoneV0516Contract
Assert-SingleVehicleGuardV0517Contract
Assert-CrossingEngineV0518Contract
Assert-GroundTruthBenchmarkV0519Contract
Assert-BenchmarkGateOverlayV0520Contract
Assert-CrossingEngineV0521Contract
Assert-GroundTruthReuseV0522Contract
Assert-BenchmarkIntegrityCrossingV0523Contract
Assert-LegacySemanticCompatibilityV0523R1

Write-Host "`n[Traffic AI] Road Zone + Frame Browser V0.5.11" -ForegroundColor Cyan
$frontendV511 = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
$cssV511 = Get-Content (Join-Path $root "frontend\src\styles.css") -Raw -Encoding UTF8
$countingV511 = Get-Content (Join-Path $root "ai-service\app\counting.py") -Raw -Encoding UTF8
$cameraSchemaV511 = Get-Content (Join-Path $root "backend\app\schemas\camera.py") -Raw -Encoding UTF8
if ($frontendV511 -notmatch 'LÒNG ĐƯỜNG' -or $frontendV511 -notmatch 'road-zone-handle' -or $frontendV511 -notmatch 'annotation-frame-list') { throw "Frontend thiếu Road Zone editor hoặc Frame Browser V0.5.11." }
if ($cssV511 -notmatch '\.annotation-frame-item' -or $cssV511 -notmatch '\.road-zone-editor') { throw "CSS thiếu Frame Browser/Road Zone V0.5.11." }
if ($countingV511 -notmatch 'class RoadZone' -or $countingV511 -notmatch 'rejected_outside_road') { throw "AI counting thiếu Road Zone rejection." }
if ($cameraSchemaV511 -notmatch 'road_x1' -or $cameraSchemaV511 -notmatch 'road_y4') { throw "Backend camera schema thiếu Road Zone." }
Write-Host "[OK] Road Zone + Frame Browser V0.5.11" -ForegroundColor Green

Write-Host "`n[Traffic AI] Realtime Gate 4.0 / accuracy + non-blocking runtime contract" -ForegroundColor Cyan
$countingText = Get-Content (Join-Path $root "ai-service\app\counting.py") -Raw -Encoding UTF8
$classText = Get-Content (Join-Path $root "ai-service\app\classification.py") -Raw -Encoding UTF8
$trackingText = Get-Content (Join-Path $root "ai-service\app\tracking.py") -Raw -Encoding UTF8
$workerText = Get-Content (Join-Path $root "ai-service\app\worker.py") -Raw -Encoding UTF8
$asyncText = Get-Content (Join-Path $root "ai-service\app\async_tasks.py") -Raw -Encoding UTF8
$roiText = Get-Content (Join-Path $root "ai-service\app\gate_roi.py") -Raw -Encoding UTF8
$frontendText = Get-Content (Join-Path $root "frontend\src\main.jsx") -Raw -Encoding UTF8
$trackerText = Get-Content (Join-Path $root "ai-service\app\bytetrack_traffic.yaml") -Raw -Encoding UTF8
$smartRoutesText = Get-Content (Join-Path $root "backend\app\api\routes.py") -Raw -Encoding UTF8
if ($countingText -notmatch 'history_gap_frames' -or $countingText -notmatch 'rescued_crossings' -or $countingText -notmatch 'min_perpendicular_ratio') {
  throw "Realtime Gate 4.0 thiếu trajectory-history rescue hoặc kiểm tra chuyển động vuông góc."
}
if ($trackingText -notmatch 'motion_leading_anchor' -or $trackingText -notmatch 'velocity_for') {
  throw "Thiếu motion-leading anchor hoặc velocity-based track continuity."
}
if ($classText -notmatch 'VehicleClassPolicy' -or $classText -notmatch 'bicycle_certainty') {
  throw "Thiếu policy phân loại xe đạp/xe máy bảo thủ."
}
if ($workerText -notmatch 'gate_roi_for_line' -or $workerText -notmatch 'EventDispatcher' -or $workerText -notmatch 'LatestFrameEncoder') {
  throw "AI worker thiếu Gate ROI hoặc pipeline I/O bất đồng bộ."
}
if ($asyncText -notmatch 'queue.Queue' -or $roiText -notmatch 'GateROI') {
  throw "Thiếu bounded async queue hoặc Gate ROI implementation."
}
if ($trackerText -notmatch 'track_buffer: 150' -or $smartRoutesText -notmatch 'preview.jpg') {
  throw "Thiếu ByteTrack high-recall profile hoặc endpoint preview để đặt vạch."
}
if ($frontendText -notmatch 'realtime_factor' -or $frontendText -notmatch 'playback_lag_seconds' -or $frontendText -notmatch 'Phát mượt' -or $frontendText -notmatch 'AI Overlay') {
  throw "Frontend thiếu telemetry realtime hoặc chuyển đổi Phát mượt / AI Overlay của Smooth Playback."
}
$envExampleText = Get-Content (Join-Path $root ".env.example") -Raw -Encoding UTF8
if ($envExampleText -notmatch 'AI_MODEL_NAME=yolo26s\.pt' -or $envExampleText -notmatch 'AI_REFINE_MODEL_NAME=yolo26m\.pt' -or $envExampleText -notmatch 'AI_GATE_ROI=1') {
  throw "Cấu hình mặc định V0.4.0 chưa bật YOLO26s + YOLO26m refiner + Gate ROI."
}
Write-Host "[OK] Realtime Gate 4.0 / accuracy + non-blocking runtime contract" -ForegroundColor Green

Write-Host "`n[Traffic AI] Smooth telemetry contract alignment V0.5.3" -ForegroundColor Cyan
if ($frontendText -match 'Smooth Gate 4\.1') {
  Write-Host "[INFO] Frontend có nhãn Smooth Gate 4.1; contract không còn phụ thuộc text hiển thị." -ForegroundColor DarkGray
}
if ($frontendText -notmatch 'RT x' -or $frontendText -notmatch 'lag .*s') {
  throw "Frontend thiếu nhãn RT x / lag cho telemetry runtime."
}
Write-Host "[OK] Smooth telemetry contract alignment V0.5.3" -ForegroundColor Green

Write-Host "`n[Traffic AI] AI counting/persistence contract" -ForegroundColor Cyan
$routesText = Get-Content (Join-Path $root "backend\app\api\routes.py") -Raw -Encoding UTF8
if ($workerText -notmatch '_notify_finished' -or $workerText -notmatch '_event_dispatcher.submit' -or $workerText -notmatch 'motion_leading_anchor') {
  throw "AI worker thiếu async persistence, leading-edge counting hoặc session finish contract."
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
    -e AI_DATASET_ROOT=/tmp/traffic-ai-tests/datasets `
    -e AI_TRAINING_ROOT=/tmp/traffic-ai-tests/training-runs `
    -e AI_MODEL_ROOT=/tmp/traffic-ai-tests/models `
    -e VIDEO_DIR=/tmp/traffic-ai-tests/videos `
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
  docker run --rm -v "${root}:/src" -w /src/frontend node:26.10.0-alpine `
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
