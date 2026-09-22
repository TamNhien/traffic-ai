[CmdletBinding()]
param(
  [switch]$Cpu
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Get-ContainerHealth([string]$Name) {
  try {
    $value = docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $Name 2>$null
    if ($LASTEXITCODE -eq 0) { return ($value | Select-Object -First 1).Trim() }
  } catch {}
  return "missing"
}

function Show-StartupDiagnostics {
  Write-Host "`n[Traffic AI] Startup diagnostics" -ForegroundColor Yellow
  docker compose -f docker-compose.yml ps 2>$null
  Write-Host "`n[Traffic AI] Backend logs (last 200 lines)" -ForegroundColor Yellow
  docker compose -f docker-compose.yml logs --tail 200 backend 2>$null
  Write-Host "`n[Traffic AI] AI Service logs (last 120 lines)" -ForegroundColor Yellow
  docker compose -f docker-compose.yml logs --tail 120 ai-service 2>$null
}

if (-not (Test-Path ".\.env")) {
  Copy-Item ".\.env.example" ".\.env"
  Write-Warning ".env được tạo từ .env.example. Nếu đây là môi trường mới, hãy đổi POSTGRES_PASSWORD trước khi triển khai thật."
}

# Giữ tương thích với cấu hình cũ: chỉ nâng baseline pretrained YOLO11n.
# Custom model như best.pt không bao giờ bị ghi đè.
$envPath = Join-Path $ProjectRoot ".env"
if (Test-Path $envPath) {
  $envText = Get-Content $envPath -Raw
  if ($envText -match "(?m)^AI_MODEL_NAME=yolo11n\.pt[ \t]*\r?$") {
    $envText = [regex]::Replace($envText, "(?m)^AI_MODEL_NAME=yolo11n\.pt[ \t]*\r?$", "AI_MODEL_NAME=yolo26n.pt")
    [System.IO.File]::WriteAllText($envPath, $envText, [System.Text.UTF8Encoding]::new($false))
    Write-Host "[Traffic AI] Đã nâng baseline model trong .env: yolo11n.pt -> yolo26n.pt" -ForegroundColor Yellow
  }
}

# V0.2.8: bootstrap HTTPS/hosts tự động.
& (Join-Path $PSScriptRoot "ensure-local-https.ps1") -HostName "traffic-ai.test"

$volume = docker volume ls --filter "name=^traffic_ai_postgres_data$" --format "{{.Name}}"
if ($volume -ne "traffic_ai_postgres_data") {
  Write-Host "[Traffic AI] Đang tạo PostgreSQL volume..." -ForegroundColor Yellow
  docker volume create traffic_ai_postgres_data | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Không thể tạo traffic_ai_postgres_data." }
}

$composeArgs = @("compose", "-f", "docker-compose.yml")
if (-not $Cpu) {
  Write-Host "[Traffic AI] Thử khởi động chế độ NVIDIA GPU." -ForegroundColor Cyan
  $composeArgs += @("-f", "docker-compose.gpu.yml")
} else {
  Write-Host "[Traffic AI] Khởi động chế độ CPU." -ForegroundColor Yellow
}
$composeArgs += @("up", "-d", "--build")

& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
  $backendHealth = Get-ContainerHealth "traffic-ai-backend"

  # Backend lỗi không liên quan GPU. Không retry CPU vô ích; in log đúng blocker ngay.
  if ($backendHealth -in @("unhealthy", "exited", "restarting", "dead")) {
    Show-StartupDiagnostics
    throw "Backend không healthy ($backendHealth). Đã in log chẩn đoán phía trên; CPU fallback không thể sửa lỗi Backend."
  }

  if (-not $Cpu) {
    Write-Warning "Khởi động GPU thất bại trong khi Backend không báo lỗi. Đang thử lại AI Service bằng CPU..."
    docker compose -f docker-compose.yml up -d --build
    if ($LASTEXITCODE -ne 0) {
      Show-StartupDiagnostics
      throw "docker compose up thất bại ở chế độ CPU."
    }
  } else {
    Show-StartupDiagnostics
    throw "docker compose up thất bại."
  }
}

Write-Host ""
Write-Host "[OK] Traffic AI V0.2.9 đã khởi động." -ForegroundColor Green
Write-Host "Dashboard : https://traffic-ai.test:8443"
Write-Host "API Docs  : https://traffic-ai.test:8444/docs"
Write-Host "PostgreSQL: 127.0.0.1:5445 / traffic_ai_db"
Write-Host "AI stream : https://traffic-ai.test:8443/ai/streams/{camera_id}.mjpg"
