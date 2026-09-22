[CmdletBinding()]
param(
  [switch]$SkipDockerBuild
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root


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

function Invoke-Step([string]$Title, [scriptblock]$Action) {
  Write-Host "`n[Traffic AI] $Title" -ForegroundColor Cyan
  & $Action
  if ($LASTEXITCODE -ne 0) { throw "$Title failed with exit code $LASTEXITCODE" }
  Write-Host "[OK] $Title" -ForegroundColor Green
}

Assert-LocalHttpsBootstrapContract
Assert-BackendHealthContract
Assert-FrontendUtf8Contract

Invoke-Step "Backend syntax check" {
  docker run --rm -v "${root}:/src" -w /src/backend python:3.12-slim python -m compileall -q app tests alembic
}

Invoke-Step "AI service syntax check" {
  docker run --rm -v "${root}:/src" -w /src/ai-service python:3.12-slim python -m compileall -q app tests
}

Invoke-Step "Backend unit tests" {
  docker run --rm `
    -e DATABASE_URL_OVERRIDE=sqlite+pysqlite:///:memory: `
    -e AI_SERVICE_URL=http://127.0.0.1:8001 `
    -e PYTHONPATH=/src/backend `
    -e PIP_ROOT_USER_ACTION=ignore `
    -v "${root}:/src" -w /src/backend python:3.12-slim `
    sh -lc "pip install -q -r requirements-test.txt && python -m pytest -q"
}

Invoke-Step "AI service unit tests" {
  docker run --rm `
    -e PYTHONPATH=/src/ai-service `
    -e PIP_ROOT_USER_ACTION=ignore `
    -v "${root}:/src" -w /src/ai-service python:3.12-slim `
    sh -lc "pip install -q -r requirements-test.txt && python -m pytest -q"
}

Invoke-Step "Frontend build" {
  $frontendDist = Join-Path $root "frontend\dist"
  if (Test-Path $frontendDist) { Remove-Item $frontendDist -Recurse -Force }
  docker run --rm -v "${root}:/src" -w /src/frontend node:22-alpine `
    sh -lc "npm install && npm run build"
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
