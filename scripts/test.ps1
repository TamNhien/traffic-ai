[CmdletBinding()]
param(
  [switch]$SkipDockerBuild
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Invoke-Step([string]$Title, [scriptblock]$Action) {
  Write-Host "`n[Traffic AI] $Title" -ForegroundColor Cyan
  & $Action
  if ($LASTEXITCODE -ne 0) { throw "$Title failed with exit code $LASTEXITCODE" }
  Write-Host "[OK] $Title" -ForegroundColor Green
}

Invoke-Step "Backend syntax check" {
  docker run --rm -v "${root}:/src" -w /src/backend python:3.12-slim python -m compileall -q app tests
}

Invoke-Step "AI service syntax check" {
  docker run --rm -v "${root}:/src" -w /src/ai-service python:3.12-slim python -m compileall -q app tests
}

Invoke-Step "Backend unit tests" {
  docker run --rm `
    -e POSTGRES_DB=traffic_ai_db `
    -e POSTGRES_USER=traffic_admin `
    -e POSTGRES_PASSWORD=ci-only-password `
    -e POSTGRES_HOST=127.0.0.1 `
    -e POSTGRES_PORT=5432 `
    -e AI_SERVICE_URL=http://127.0.0.1:8001 `
    -e PYTHONPATH=/src/backend `
    -e PIP_ROOT_USER_ACTION=ignore `
    -v "${root}:/src" -w /src/backend python:3.12-slim `
    sh -lc "pip install -q -r requirements-dev.txt && python -m pytest -q"
}

Invoke-Step "AI service unit tests" {
  docker run --rm `
    -e PYTHONPATH=/src/ai-service `
    -e PIP_ROOT_USER_ACTION=ignore `
    -v "${root}:/src" -w /src/ai-service python:3.12-slim `
    sh -lc "pip install -q -r requirements-dev.txt && python -m pytest -q"
}

Invoke-Step "Frontend build" {
  docker run --rm -v "${root}:/src" -w /src/frontend node:22-alpine `
    sh -lc "npm install && npm run build"
}

if (-not $SkipDockerBuild) {
  Invoke-Step "Docker Compose validation" {
    docker compose config --quiet
  }
  Invoke-Step "Docker image build" {
    docker compose build backend ai-service frontend
  }
}

Write-Host "`n[SUCCESS] All Traffic AI tests passed." -ForegroundColor Green
