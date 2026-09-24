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

function Show-GatewayDiagnostics {
  Write-Host "`n[Traffic AI] Gateway logs (last 120 lines)" -ForegroundColor Yellow
  docker compose -f docker-compose.yml logs --tail 120 gateway 2>$null
}

function Test-HttpsEndpoint([string]$Url, [int]$Attempts = 20) {
  for ($i = 1; $i -le $Attempts; $i++) {
    try {
      $code = (& curl.exe -k -sS -o NUL -w "%{http_code}" --max-time 4 $Url 2>$null | Select-Object -Last 1).Trim()
      if ($code -eq "200") { return $true }
    } catch {}
    Start-Sleep -Seconds 1
  }
  return $false
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
  if ($envText -match "(?m)^AI_MODEL_NAME=(yolo11n|yolo26n)\.pt[ \t]*\r?$") {
    $oldModel = ([regex]::Match($envText, "(?m)^AI_MODEL_NAME=([^\r\n]+)")).Groups[1].Value
    $envText = [regex]::Replace($envText, "(?m)^AI_MODEL_NAME=(yolo11n|yolo26n)\.pt[ \t]*\r?$", "AI_MODEL_NAME=yolo26s.pt")
    [System.IO.File]::WriteAllText($envPath, $envText, [System.Text.UTF8Encoding]::new($false))
    Write-Host "[Traffic AI] Đã nâng baseline model trong .env: $oldModel -> yolo26s.pt" -ForegroundColor Yellow
  }
}

# V0.5.8: giữ detector/classifier, nhưng nâng tuning cho Strict Gate + Fast Crossing.
function Set-EnvDefaultUpgrade([string]$Key, [string]$OldValue, [string]$NewValue) {
  $text = Get-Content $envPath -Raw
  $pattern = "(?m)^" + [regex]::Escape($Key) + "=" + [regex]::Escape($OldValue) + "[ \t]*\r?$"
  if ($text -match $pattern) {
    $text = [regex]::Replace($text, $pattern, "$Key=$NewValue")
    [System.IO.File]::WriteAllText($envPath, $text, [System.Text.UTF8Encoding]::new($false))
    Write-Host "[Traffic AI] Tuning ${Key}: $OldValue -> $NewValue" -ForegroundColor Yellow
  }
}
function Ensure-EnvSetting([string]$Key, [string]$Value) {
  $text = Get-Content $envPath -Raw
  if ($text -notmatch ("(?m)^" + [regex]::Escape($Key) + "=")) {
    Add-Content -Path $envPath -Value "$Key=$Value" -Encoding UTF8
    Write-Host "[Traffic AI] Đã thêm $Key=$Value vào .env" -ForegroundColor Yellow
  }
}
Set-EnvDefaultUpgrade "AI_IMGSZ" "832" "640"
Set-EnvDefaultUpgrade "AI_PROCESS_MAX_WIDTH" "1152" "1440"
Set-EnvDefaultUpgrade "AI_JPEG_QUALITY" "72" "70"
Set-EnvDefaultUpgrade "AI_CLASS_HISTORY" "24" "30"
Set-EnvDefaultUpgrade "AI_STITCH_MAX_GAP" "18" "30"
Set-EnvDefaultUpgrade "AI_STITCH_DISTANCE_RATIO" "0.085" "0.14"
Set-EnvDefaultUpgrade "AI_REFINE_MODEL_NAME" "yolo26s.pt" "yolo26m.pt"
Set-EnvDefaultUpgrade "AI_GATE_HISTORY_GAP" "30" "45"
Set-EnvDefaultUpgrade "AI_GATE_MIN_NORMAL_RATIO" "0.12" "0.10"
Set-EnvDefaultUpgrade "AI_GATE_ROI_MARGIN" "0.22" "0.16"
Set-EnvDefaultUpgrade "AI_BICYCLE_CERTAINTY" "0.76" "0.80"
Set-EnvDefaultUpgrade "AI_BICYCLE_MIN_HITS" "4" "5"
Ensure-EnvSetting "AI_STREAM_EVERY_N" "2"
Ensure-EnvSetting "AI_STREAM_MAX_WIDTH" "960"
Ensure-EnvSetting "AI_IOU" "0.55"
Ensure-EnvSetting "AI_GATE_HISTORY_GAP" "45"
Ensure-EnvSetting "AI_GATE_MIN_NORMAL_RATIO" "0.10"
Ensure-EnvSetting "AI_GATE_SEGMENT_MARGIN" "0.0"
Ensure-EnvSetting "AI_GATE_DEAD_BAND_RATIO" "0.006"
Ensure-EnvSetting "AI_GATE_REARM_DISTANCE_RATIO" "0.028"
Ensure-EnvSetting "AI_GATE_MIN_MOTION_RATIO" "0.004"
Ensure-EnvSetting "AI_GATE_ROI" "1"
Ensure-EnvSetting "AI_GATE_ROI_MARGIN" "0.16"
Ensure-EnvSetting "AI_GATE_ROI_MIN_SPAN" "0.52"
Ensure-EnvSetting "AI_GATE_ENDPOINT_MARGIN" "0.035"
Ensure-EnvSetting "AI_ROAD_ZONE_PROBE_RATIO" "0.018"
Ensure-EnvSetting "AI_REFINE_AT_CROSSING" "1"
Ensure-EnvSetting "AI_REFINE_MODEL_NAME" "yolo26m.pt"
Ensure-EnvSetting "AI_REFINE_IMGSZ" "640"
Ensure-EnvSetting "AI_REFINE_MAX_PER_FRAME" "1"
Ensure-EnvSetting "AI_REFINE_MAX_LAG" "0.35"
Ensure-EnvSetting "AI_BICYCLE_CERTAINTY" "0.80"
Ensure-EnvSetting "AI_BICYCLE_MIN_HITS" "5"
Ensure-EnvSetting "AI_BICYCLE_STRONG_CERTAINTY" "0.90"
Ensure-EnvSetting "AI_BICYCLE_STRONG_HITS" "8"
Ensure-EnvSetting "AI_WARMUP" "1"

# V0.2.8: bootstrap HTTPS/hosts tự động.

Ensure-EnvSetting "AI_VIDEO_PACE" "1"
Ensure-EnvSetting "AI_NATIVE_VIDEO_PREVIEW" "1"
Ensure-EnvSetting "AI_MJPEG_WAIT_TIMEOUT" "2.0"

# V0.5.2 Dataset & Fine-tune Studio
Ensure-EnvSetting "AI_DATASET_ROOT" "/data/datasets"
Ensure-EnvSetting "AI_TRAINING_ROOT" "/data/training-runs"
Ensure-EnvSetting "AI_TRAIN_BASE_MODEL" "yolo26s.pt"
Ensure-EnvSetting "AI_TRAIN_EPOCHS" "80"
Ensure-EnvSetting "AI_TRAIN_IMGSZ" "640"
Ensure-EnvSetting "AI_TRAIN_BATCH" "8"
Ensure-EnvSetting "AI_TRAIN_WORKERS" "4"
Ensure-EnvSetting "AI_TRAIN_PATIENCE" "20"
Ensure-EnvSetting "AI_TRAIN_CACHE" "false"
Ensure-EnvSetting "AI_DATASET_SEED" "2026"

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

# Gateway có thể đã sống từ phiên bản trước trong khi frontend/backend vừa bị recreate.
# Force-recreate để nạp nginx.conf mới; Gateway tiếp tục dùng Docker DNS động.
Write-Host "[Traffic AI] Đồng bộ Gateway với IP container hiện tại..." -ForegroundColor Cyan
docker compose -f docker-compose.yml up -d --no-deps --force-recreate gateway
if ($LASTEXITCODE -ne 0) {
  Show-GatewayDiagnostics
  throw "Không thể recreate traffic-ai-gateway."
}

$dashboardOk = Test-HttpsEndpoint "https://traffic-ai.test:8443/" 25
$apiOk = Test-HttpsEndpoint "https://traffic-ai.test:8444/api/health" 25
if (-not $dashboardOk -or -not $apiOk) {
  Show-GatewayDiagnostics
  Show-StartupDiagnostics
  throw "Gateway chưa proxy được Dashboard/API sau khi startup (Dashboard=$dashboardOk, API=$apiOk)."
}

Write-Host ""
Write-Host "[OK] Traffic AI V0.5.12 đã khởi động." -ForegroundColor Green
Write-Host "Dashboard : https://traffic-ai.test:8443"
Write-Host "API Docs  : https://traffic-ai.test:8444/docs"
Write-Host "PostgreSQL: 127.0.0.1:5445 / traffic_ai_db"
Write-Host "AI stream : https://traffic-ai.test:8443/ai/streams/{camera_id}.mjpg"
