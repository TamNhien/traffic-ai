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

function Test-ConfiguredPostgresPassword {
  # Probe over TCP+SCRAM. pg_isready and Unix socket checks alone cannot
  # establish that the password in .env matches the persistent database role.
  # The password remains inside the PostgreSQL container environment; never
  # echo it, pass it on docker's command line or emit it in diagnostics.
  $query = 'PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -X -q -t -A -c "SELECT 1" 2>/dev/null'
  $output = & docker exec traffic-ai-postgres sh -c $query 2>$null
  return ($LASTEXITCODE -eq 0 -and ($output -join "`n").Trim() -eq '1')
}

function Show-StartupDiagnostics {
  Write-Host "`n[Traffic AI] Startup diagnostics" -ForegroundColor Yellow
  docker compose -f docker-compose.yml ps -a 2>$null
  Write-Host "`n[Traffic AI] PostgreSQL logs (last 80 lines)" -ForegroundColor Yellow
  docker compose -f docker-compose.yml logs --tail 80 postgres 2>$null
  Write-Host "`n[Traffic AI] Backend healthcheck (last 5 checks)" -ForegroundColor Yellow
  docker inspect --format '{{if .State.Health}}{{range .State.Health.Log}}{{.ExitCode}} {{.Output}}{{end}}{{else}}{{.State.Status}}{{end}}' traffic-ai-backend 2>$null
  Write-Host "`n[Traffic AI] Backend logs (last 200 lines)" -ForegroundColor Yellow
  docker compose -f docker-compose.yml logs --tail 200 backend 2>$null
  Write-Host "`n[Traffic AI] AI Service logs (last 120 lines)" -ForegroundColor Yellow
  docker compose -f docker-compose.yml logs --tail 120 ai-service 2>$null
}

function Show-GatewayDiagnostics {
  Write-Host "`n[Traffic AI] Gateway logs (last 120 lines)" -ForegroundColor Yellow
  docker compose -f docker-compose.yml logs --tail 120 gateway 2>$null
}

function Wait-ContainerHealthy([string]$Name, [int]$TimeoutSeconds = 180) {
  $timer = [System.Diagnostics.Stopwatch]::StartNew()
  $previousStatus = ''
  while ($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
    $state = Get-ContainerHealth $Name
    if ($state -eq 'healthy') {
      Write-Host "[OK] $Name healthy after $([int]$timer.Elapsed.TotalSeconds)s." -ForegroundColor Green
      return $true
    }
    if ($state -in @('unhealthy', 'exited', 'dead')) {
      Write-Warning "$Name has failed health/state check: $state."
      return $false
    }
    if ($state -ne $previousStatus -or [int]$timer.Elapsed.TotalSeconds % 15 -eq 0) {
      Write-Host "[Traffic AI] Waiting for $Name ($state, $([int]$timer.Elapsed.TotalSeconds)s/${TimeoutSeconds}s)..." -ForegroundColor DarkYellow
      $previousStatus = $state
    }
    Start-Sleep -Seconds 3
  }
  Write-Warning "Timed out after $TimeoutSeconds seconds waiting for $Name (last state: $(Get-ContainerHealth $Name))."
  return $false
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

# V0.5.68: generate strong DB secret ONLY for fresh template installs.
# Existing working PostgreSQL credentials are never modified automatically.
$firstDbSecret = [regex]::Match((Get-Content $envPath -Raw), '(?m)^POSTGRES_PASSWORD=([^\r\n]*)')
if ($firstDbSecret.Success -and $firstDbSecret.Groups[1].Value -eq 'CHANGE_ME_GENERATED_ON_START') {
  # V0.5.70: an existing named volume may contain an old password.
  # Never replace the template value with a new random value on an existing DB.
  $existingDbVolume = docker volume ls --filter 'name=^traffic_ai_postgres_data$' --format '{{.Name}}'
  if ($LASTEXITCODE -ne 0) { throw 'Không kiểm tra được PostgreSQL volume, đã dừng để bảo vệ dữ liệu.' }
  if ($existingDbVolume -eq 'traffic_ai_postgres_data') {
    throw 'Đã có PostgreSQL volume cũ nhưng .env vẫn là mật khẩu mẫu. Khôi phục POSTGRES_PASSWORD đúng trong .env (hoặc đặt mật khẩu mới an toàn trước khi chạy repair-postgres-auth.ps1). Không tự đổi DB secret.'
  }
  $newDbSecret = [Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).TrimEnd('=') -replace '\+', '-' -replace '/', '_'
  $dbEnv = Get-Content $envPath -Raw
  $dbEnv = [regex]::Replace($dbEnv, '(?m)^POSTGRES_PASSWORD=[^\r\n]*', "POSTGRES_PASSWORD=$newDbSecret")
  [System.IO.File]::WriteAllText($envPath, $dbEnv, [System.Text.UTF8Encoding]::new($false))
  Write-Host "[Traffic AI] Môi trường mới: đã tạo mật khẩu PostgreSQL ngẫu nhiên." -ForegroundColor Green
}

# V0.5.68: upgrade the published example AI token to a unique machine secret.
$oldAiToken = [regex]::Match((Get-Content $envPath -Raw), '(?m)^AI_SHARED_TOKEN=([^\r\n]*)')
if (-not $oldAiToken.Success -or $oldAiToken.Groups[1].Value -in @('TrafficAI-Local-2026', 'CHANGE_ME_GENERATED_ON_START')) {
  $newToken = [Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).TrimEnd('=') -replace '\+', '-' -replace '/', '_'
  $allEnv = Get-Content $envPath -Raw
  if ($oldAiToken.Success) {
    $allEnv = [regex]::Replace($allEnv, '(?m)^AI_SHARED_TOKEN=[^\r\n]*', "AI_SHARED_TOKEN=$newToken")
  } else {
    $allEnv = $allEnv.TrimEnd("`r", "`n") + "`r`nAI_SHARED_TOKEN=$newToken`r`n"
  }
  [System.IO.File]::WriteAllText($envPath, $allEnv, [System.Text.UTF8Encoding]::new($false))
  Write-Host "[Traffic AI] Đã tạo bí mật nội bộ AI ngẫu nhiên; không ghi giá trị vào log." -ForegroundColor Green
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
# V0.5.47 keeps the V0.5.46 passage re-arm default; custom values remain untouched.
Set-EnvDefaultUpgrade "AI_GATE_PASSAGE_REARM_MIN_FRAMES" "10" "16"
# V0.5.47: evidence-gated Balanced Recall Recovery; only add missing keys.
Ensure-EnvSetting "AI_GATE_ANCHOR_SPAN_SAME_DIRECTION_MIN_FRAMES" "16"
Ensure-EnvSetting "AI_GATE_ANCHOR_SPAN_LOST_MIN_NORMAL_RATIO" "0.55"
Ensure-EnvSetting "AI_GATE_ANCHOR_SPAN_LOST_MIN_SIDE_RATIO" "0.014"
Set-EnvDefaultUpgrade "AI_GATE_MIN_NORMAL_RATIO" "0.12" "0.10"
Set-EnvDefaultUpgrade "AI_GATE_ROI_MARGIN" "0.22" "0.16"
Set-EnvDefaultUpgrade "AI_BICYCLE_CERTAINTY" "0.76" "0.80"
Set-EnvDefaultUpgrade "AI_BICYCLE_MIN_HITS" "4" "5"
Set-EnvDefaultUpgrade "AI_HUMAN_GUARD_CHECK_INTERVAL" "12" "8"
Set-EnvDefaultUpgrade "AI_REFINE_MAX_PER_FRAME" "1" "2"
Set-EnvDefaultUpgrade "AI_BICYCLE_CONSENSUS_CONF" "0.60" "0.78"
Set-EnvDefaultUpgrade "AI_BICYCLE_CONSENSUS_MIN_HITS" "3" "4"
Set-EnvDefaultUpgrade "AI_BICYCLE_CONSENSUS_MARGIN" "0.08" "0.16"
Set-EnvDefaultUpgrade "AI_BICYCLE_CONSENSUS_MIN_STRONG" "0.34" "0.45"
Set-EnvDefaultUpgrade "AI_BICYCLE_REFINE_OVERRIDE_CONF" "0.58" "0.90"

# V0.5.14: detector quét toàn khung; Road Zone chỉ còn nhiệm vụ quyết định ĐẾM.
# Chỉ migrate đúng một lần để người dùng vẫn có thể chủ động chuyển lại road/gate sau đó.
$envTextV514 = Get-Content $envPath -Raw
if ($envTextV514 -notmatch '(?m)^AI_DETECTION_POLICY_V0514=1[ \t]*\r?$') {
  if ($envTextV514 -match '(?m)^AI_DETECTION_ROI=road[ \t]*\r?$') {
    $envTextV514 = [regex]::Replace($envTextV514, '(?m)^AI_DETECTION_ROI=road[ \t]*\r?$', 'AI_DETECTION_ROI=full')
    Write-Host '[Traffic AI] V0.5.14: AI_DETECTION_ROI road -> full (detect toàn khung, Road Zone chỉ lọc đếm).' -ForegroundColor Yellow
  }
  $envTextV514 = $envTextV514.TrimEnd("`r", "`n") + "`r`nAI_DETECTION_POLICY_V0514=1`r`n"
  [System.IO.File]::WriteAllText($envPath, $envTextV514, [System.Text.UTF8Encoding]::new($false))
}
# V0.5.15: high-recall hybrid tracking for custom best.pt.
# Existing default 640 is upgraded once to 960; custom values other than 640 are preserved.
$envTextV515 = Get-Content $envPath -Raw
if ($envTextV515 -notmatch '(?m)^AI_HYBRID_POLICY_V0515=1[ \t]*\r?$') {
  if ($envTextV515 -match '(?m)^AI_IMGSZ=640[ \t]*\r?$') {
    $envTextV515 = [regex]::Replace($envTextV515, '(?m)^AI_IMGSZ=640[ \t]*\r?$', 'AI_IMGSZ=960')
    Write-Host '[Traffic AI] V0.5.15: AI_IMGSZ 640 -> 960 để bắt xe nhỏ/xa rõ hơn.' -ForegroundColor Yellow
  }
  $envTextV515 = $envTextV515.TrimEnd("`r", "`n") + "`r`nAI_HYBRID_POLICY_V0515=1`r`n"
  [System.IO.File]::WriteAllText($envPath, $envTextV515, [System.Text.UTF8Encoding]::new($false))
}
Ensure-EnvSetting "AI_HYBRID_RECALL" "1"
Ensure-EnvSetting "AI_AGNOSTIC_NMS" "0"
Ensure-EnvSetting "AI_HEAVY_DUP_IOU" "0.68"
Ensure-EnvSetting "AI_RECALL_MODEL_NAME" "yolo26s.pt"
Ensure-EnvSetting "AI_FLOW_CALIBRATION_HISTORY_FRAMES" "1200"
Ensure-EnvSetting "AI_FLOW_CALIBRATION_POINTS_PER_TRACK" "180"
Ensure-EnvSetting "AI_IMGSZ" "960"
Ensure-EnvSetting "AI_STREAM_EVERY_N" "2"
Ensure-EnvSetting "AI_STREAM_MAX_WIDTH" "960"
Ensure-EnvSetting "AI_IOU" "0.55"
Ensure-EnvSetting "AI_GATE_HISTORY_GAP" "45"
Ensure-EnvSetting "AI_GATE_INTERPOLATION_GAP" "3"
Ensure-EnvSetting "AI_GATE_MIN_NORMAL_RATIO" "0.10"
Ensure-EnvSetting "AI_GATE_SEGMENT_MARGIN" "0.0"
Ensure-EnvSetting "AI_GATE_DEAD_BAND_RATIO" "0.006"
Ensure-EnvSetting "AI_GATE_REARM_DISTANCE_RATIO" "0.028"
Ensure-EnvSetting "AI_GATE_MIN_MOTION_RATIO" "0.004"
Ensure-EnvSetting "AI_GATE_ROI" "1"
Ensure-EnvSetting "AI_DETECTION_ROI" "full"
Ensure-EnvSetting "AI_ROAD_ROI_MARGIN" "0.02"
Ensure-EnvSetting "AI_GATE_ROI_MARGIN" "0.16"
Ensure-EnvSetting "AI_GATE_ROI_MIN_SPAN" "0.52"
Ensure-EnvSetting "AI_GATE_ENDPOINT_MARGIN" "0.035"
Ensure-EnvSetting "AI_GATE_STARTUP_GRACE_FRAMES" "12"
Ensure-EnvSetting "AI_VIDEO_STARTUP_GRACE_FRAMES" "0"
Ensure-EnvSetting "AI_VIDEO_ORIGIN_RESCUE_FRAMES" "20"
Ensure-EnvSetting "AI_VIDEO_ORIGIN_DISTANCE_RATIO" "0.065"
Ensure-EnvSetting "AI_VIDEO_ORIGIN_MIN_NORMAL_RATIO" "0.30"
Ensure-EnvSetting "AI_HEAVY_ANCHOR_INSET_RATIO" "0.16"
Ensure-EnvSetting "AI_STITCH_HEAVY_MAX_GAP" "90"
Ensure-EnvSetting "AI_STITCH_HEAVY_DISTANCE_RATIO" "0.18"
Ensure-EnvSetting "AI_HEAVY_CENTER_RESCUE" "1"
Ensure-EnvSetting "AI_HEAVY_CENTER_HISTORY_GAP" "90"
Ensure-EnvSetting "AI_HEAVY_CENTER_MIN_NORMAL_RATIO" "0.20"
Ensure-EnvSetting "AI_HEAVY_CENTER_ROAD_MARGIN_RATIO" "0.020"
Ensure-EnvSetting "AI_TWO_WHEEL_CENTER_RESCUE" "1"
Ensure-EnvSetting "AI_TWO_WHEEL_CENTER_HISTORY_GAP" "12"
Ensure-EnvSetting "AI_TWO_WHEEL_CENTER_MIN_NORMAL_RATIO" "0.42"
Ensure-EnvSetting "AI_TWO_WHEEL_CENTER_MAX_JUMP_RATIO" "0.10"
Ensure-EnvSetting "AI_TWO_WHEEL_CENTER_MIN_SIDE_RATIO" "0.006"
Ensure-EnvSetting "AI_TWO_WHEEL_CENTER_ROAD_MARGIN_RATIO" "0.008"
Ensure-EnvSetting "AI_TWO_WHEEL_CENTER_SEGMENT_EDGE_RATIO" "0.04"
Ensure-EnvSetting "AI_TWO_WHEEL_CENTER_MIN_TRACK_HITS" "3"
Ensure-EnvSetting "AI_TRUCK_SEMANTIC_LOCK_FRAMES" "450"
Ensure-EnvSetting "AI_TRUCK_SEMANTIC_LOCK_MIN_HITS" "2"
Ensure-EnvSetting "AI_TRUCK_SEMANTIC_LOCK_CONF" "0.62"
Ensure-EnvSetting "AI_TRUCK_SEMANTIC_PRIMARY_HITS" "3"
Ensure-EnvSetting "AI_TRUCK_SEMANTIC_PRIMARY_CERTAINTY" "0.80"
Ensure-EnvSetting "AI_GATE_SIDE_CONFIRM_SAMPLES" "2"
Ensure-EnvSetting "AI_GATE_COOLDOWN_FRAMES" "60"
Ensure-EnvSetting "AI_ROAD_ZONE_PROBE_RATIO" "0.018"
Ensure-EnvSetting "AI_ROAD_ANCHOR_MARGIN_RATIO" "0.012"
Ensure-EnvSetting "AI_GATE_FAST_CONFIRM_DISTANCE_RATIO" "0.018"
Ensure-EnvSetting "AI_GATE_BRACKET_CONFIRM" "1"
Ensure-EnvSetting "AI_GATE_BRACKET_CONFIRM_MIN_NORMAL_RATIO" "0.55"
Ensure-EnvSetting "AI_GATE_BRACKET_CONFIRM_MAX_GAP" "2"
Ensure-EnvSetting "AI_GATE_LATE_GEOMETRY_CONFIRM" "1"
Ensure-EnvSetting "AI_GATE_LATE_GEOMETRY_CONFIRM_MIN_NORMAL_RATIO" "0.48"
Ensure-EnvSetting "AI_GATE_LATE_GEOMETRY_CONFIRM_MAX_JUMP_RATIO" "0.08"
Ensure-EnvSetting "AI_GATE_LATE_GEOMETRY_CONFIRM_MIN_SIDE_RATIO" "0.008"
Ensure-EnvSetting "AI_GATE_LATE_GEOMETRY_CONFIRM_MAX_GAP" "3"
Ensure-EnvSetting "AI_GATE_ADAPTIVE_COOLDOWN" "1"
Ensure-EnvSetting "AI_GATE_COOLDOWN_RELEASE_RATIO" "0.055"
Ensure-EnvSetting "AI_GATE_RESCUE_MIN_NORMAL_RATIO" "0.28"
Ensure-EnvSetting "AI_GATE_RESCUE_MAX_JUMP_RATIO" "0.26"
Ensure-EnvSetting "AI_GATE_RESCUE_MIN_SIDE_RATIO" "0.010"
Ensure-EnvSetting "AI_HUMAN_GUARD" "1"
Ensure-EnvSetting "AI_HUMAN_GUARD_MODEL" "yolo26s.pt"
Ensure-EnvSetting "AI_HUMAN_GUARD_IMGSZ" "512"
Ensure-EnvSetting "AI_HUMAN_GUARD_CHECK_INTERVAL" "8"
Ensure-EnvSetting "AI_HUMAN_GUARD_CONF" "0.08"
Ensure-EnvSetting "AI_HUMAN_GUARD_REQUIRED_STRIKES" "2"
Ensure-EnvSetting "AI_HUMAN_GUARD_PENDING_MAX_FRAMES" "12"
Ensure-EnvSetting "AI_REFINE_AT_CROSSING" "1"
Ensure-EnvSetting "AI_REFINE_MODEL_NAME" "yolo26m.pt"
Ensure-EnvSetting "AI_DUAL_CLASS_REFINE" "1"
Ensure-EnvSetting "AI_GENERAL_REFINE_MODEL_NAME" "yolo26m.pt"
Ensure-EnvSetting "AI_REFINE_CONSENSUS_MIN_HITS" "2"
Ensure-EnvSetting "AI_REFINE_CONSENSUS_HISTORY_FRAMES" "120"
Ensure-EnvSetting "AI_BICYCLE_CONSENSUS_CONF" "0.78"
Ensure-EnvSetting "AI_BICYCLE_CONSENSUS_MIN_HITS" "4"
Ensure-EnvSetting "AI_BICYCLE_CONSENSUS_MARGIN" "0.16"
Ensure-EnvSetting "AI_BICYCLE_CONSENSUS_MIN_STRONG" "0.45"
Ensure-EnvSetting "AI_BICYCLE_CONSENSUS_MIN_SOURCES" "2"
Ensure-EnvSetting "AI_BICYCLE_CONSENSUS_SINGLE_SOURCE_STRONG" "0.88"
Ensure-EnvSetting "AI_TRUCK_CONSENSUS_CONF" "0.52"
Ensure-EnvSetting "AI_REFINE_IMGSZ" "640"
Ensure-EnvSetting "AI_REFINE_MAX_PER_FRAME" "2"
Ensure-EnvSetting "AI_REFINE_MAX_LAG" "0.35"
Ensure-EnvSetting "AI_REFINE_BACKGROUND_WARMUP" "1"
Ensure-EnvSetting "AI_CLASS_REFINE_INTERVAL" "10"
Ensure-EnvSetting "AI_CLASS_REFINE_HEAVY_INTERVAL" "45"
Ensure-EnvSetting "AI_CLASS_REFINE_GATE_DISTANCE_RATIO" "0.11"
Ensure-EnvSetting "AI_CLASS_OVERRIDE_TTL_FRAMES" "180"
Ensure-EnvSetting "AI_BICYCLE_OVERRIDE_TTL_FRAMES" "60"
Ensure-EnvSetting "AI_HEAVY_OVERRIDE_TTL_FRAMES" "240"
Ensure-EnvSetting "AI_REFINE_TARGET_MIN_IOU" "0.08"
Ensure-EnvSetting "AI_REFINE_TARGET_MIN_COVERAGE" "0.16"
Ensure-EnvSetting "AI_BICYCLE_REFINE_OVERRIDE_CONF" "0.90"
Ensure-EnvSetting "AI_TRUCK_REFINE_OVERRIDE_CONF" "0.48"
Ensure-EnvSetting "AI_HEAVY_REFINE_OVERRIDE_CONF" "0.54"
Ensure-EnvSetting "AI_BICYCLE_CERTAINTY" "0.80"
Ensure-EnvSetting "AI_BICYCLE_MIN_HITS" "5"
Ensure-EnvSetting "AI_BICYCLE_STRONG_CERTAINTY" "0.90"
Ensure-EnvSetting "AI_BICYCLE_STRONG_HITS" "8"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_RESCUE" "1"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_PAD_X" "1.10"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_PAD_Y" "0.85"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_DUAL_CONF" "0.72"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_SINGLE_CONF" "0.90"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_MIN_SOURCE_CONF" "0.18"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_MIN_STRONG" "0.34"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_MAX_PER_FRAME" "1"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_TEMPORAL_MIN_HITS" "2"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_TEMPORAL_CONF" "0.50"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_TEMPORAL_STRONG" "0.26"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_TEMPORAL_COMBINED" "0.72"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_WEAK_MOTOR_MAX_CONF" "0.62"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_WEAK_MOTOR_DUAL_CONF" "0.58"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_WEAK_MOTOR_MIN_STRONG" "0.24"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_COMPETITIVE_MAX_MOTOR_CONF" "0.55"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_COMPETITIVE_MIN_SOURCE_CONF" "0.12"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_COMPETITIVE_SOURCE_MARGIN" "0.06"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_COMPETITIVE_DUAL_CONF" "0.34"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_COMPETITIVE_FUSED_MARGIN" "0.08"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_COMPETITIVE_SINGLE_CONF" "0.55"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_NEAR_MARGIN_MAX_MOTOR_CONF" "0.50"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_NEAR_MARGIN_MIN_SOURCE_CONF" "0.10"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_NEAR_MARGIN_SOURCE_WIN" "0.02"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_NEAR_MARGIN_MOTOR_VETO" "0.08"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_NEAR_MARGIN_DUAL_CONF" "0.28"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_NEAR_MARGIN_FUSED_MARGIN" "0.02"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_XFRAME" "1"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_XFRAME_HISTORY" "18"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_XFRAME_GATE_DISTANCE_RATIO" "0.070"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_XFRAME_INTERVAL" "4"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_XFRAME_MAX_PER_FRAME" "1"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_XFRAME_MAX_MOTOR_CONF" "0.52"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_XFRAME_MIN_SOURCE_CONF" "0.08"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_XFRAME_MIN_FRAMES" "2"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_XFRAME_MIN_SOURCES" "2"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_XFRAME_SOURCE_WIN" "0.015"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_XFRAME_MOTOR_VETO" "0.10"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_XFRAME_MIN_STRONG" "0.14"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_XFRAME_DUAL_CONF" "0.30"
Ensure-EnvSetting "AI_BICYCLE_CONTEXT_XFRAME_FUSED_MARGIN" "0.015"
Ensure-EnvSetting "AI_GATE_ANCHOR_SPAN_RECOVERY" "1"
Ensure-EnvSetting "AI_GATE_ANCHOR_SPAN_HISTORY_GAP" "12"
Ensure-EnvSetting "AI_GATE_ANCHOR_SPAN_MIN_NORMAL_RATIO" "0.40"
Ensure-EnvSetting "AI_GATE_ANCHOR_SPAN_IMMEDIATE_NORMAL_RATIO" "0.68"
Ensure-EnvSetting "AI_GATE_ANCHOR_SPAN_MAX_JUMP_RATIO" "0.12"
Ensure-EnvSetting "AI_GATE_ANCHOR_SPAN_MIN_SIDE_RATIO" "0.006"
Ensure-EnvSetting "AI_GATE_ANCHOR_SPAN_IMMEDIATE_SIDE_RATIO" "0.012"
Ensure-EnvSetting "AI_GATE_ANCHOR_SPAN_ROAD_MARGIN_RATIO" "0.010"
Ensure-EnvSetting "AI_GATE_POST_CONFIRM_SAMPLES" "2"
Ensure-EnvSetting "AI_GATE_POST_CONFIRM_MAX_GAP" "6"
Ensure-EnvSetting "AI_WARMUP" "1"

# V0.2.8: bootstrap HTTPS/hosts tự động.

Ensure-EnvSetting "AI_VIDEO_PACE" "1"
Ensure-EnvSetting "AI_VIDEO_DETERMINISTIC" "1"
Ensure-EnvSetting "AI_VIDEO_DETERMINISTIC_SEED" "20260926"
Ensure-EnvSetting "AI_VIDEO_AUX_READY_TIMEOUT" "90"
Ensure-EnvSetting "AI_CROSS_TIME_MAX_INTERP_SECONDS" "0.24"
Ensure-EnvSetting "AI_CROSS_TIME_MAX_RESCUE_SECONDS" "0.72"
Ensure-EnvSetting "AI_NATIVE_VIDEO_PREVIEW" "1"
Ensure-EnvSetting "AI_BENCHMARK_TRACE" "1"
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

# V0.5.69: staged startup avoids indefinite Compose service_healthy waits.
# Start database and backend separately and time-box healthchecks before
# launching their dependents. No volume or data is ever removed here.
$baseComposeArgs = @("compose", "-f", "docker-compose.yml")
$gpuComposeArgs = @("compose", "-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml")

Write-Host "[Traffic AI] Stage 1/4: PostgreSQL..." -ForegroundColor Cyan
& docker @baseComposeArgs up -d --no-deps postgres
if ($LASTEXITCODE -ne 0 -or -not (Wait-ContainerHealthy "traffic-ai-postgres" 120)) {
  Show-StartupDiagnostics
  throw "PostgreSQL startup failed or timed out. Database volume was NOT removed."
}

# V0.5.70: the POSTGRES_PASSWORD environment variable does not change the
# password inside an already-initialized PostgreSQL volume.
if (-not (Test-ConfiguredPostgresPassword)) {
  Write-Warning 'PostgreSQL đã healthy nhưng từ chối POSTGRES_PASSWORD trong .env.'
  Write-Host '[Traffic AI] Chạy .\scripts\repair-postgres-auth.ps1 để đồng bộ mật khẩu một cách tương tác.' -ForegroundColor Yellow
  throw 'PostgreSQL authentication failed (SQLSTATE 28P01). No data/volumes were modified.'
}
Write-Host '[OK] PostgreSQL TCP/SCRAM credential check passed.' -ForegroundColor Green

Write-Host "[Traffic AI] Stage 2/4: Backend and database migrations..." -ForegroundColor Cyan
& docker @baseComposeArgs up -d --build --no-deps backend
if ($LASTEXITCODE -ne 0) {
  Show-StartupDiagnostics
  throw "Backend container could not start."
}
if (-not (Wait-ContainerHealthy "traffic-ai-backend" 180)) {
  Show-StartupDiagnostics
  throw "Backend did not become healthy within 180s. Check the PostgreSQL and Backend logs printed above (Alembic/DB import/healthcheck)."
}

Write-Host "[Traffic AI] Stage 3/4: AI Service..." -ForegroundColor Cyan
$aiReady = $false
if (-not $Cpu) {
  Write-Host "[Traffic AI] Trying NVIDIA GPU mode." -ForegroundColor Cyan
  & docker @gpuComposeArgs up -d --build --no-deps ai-service
  if ($LASTEXITCODE -eq 0) {
    $aiReady = Wait-ContainerHealthy "traffic-ai-service" 240
  }
}
if (-not $aiReady) {
  if (-not $Cpu) { Write-Warning "AI Service GPU unavailable; retrying CPU mode." }
  & docker @baseComposeArgs up -d --build --no-deps ai-service
  if ($LASTEXITCODE -ne 0 -or -not (Wait-ContainerHealthy "traffic-ai-service" 240)) {
    Show-StartupDiagnostics
    throw "AI Service did not become healthy in CPU mode."
  }
}

Write-Host "[Traffic AI] Stage 4/4: Frontend and HTTPS gateway..." -ForegroundColor Cyan
& docker @baseComposeArgs up -d --build --no-deps frontend
if ($LASTEXITCODE -ne 0) {
  Show-StartupDiagnostics
  throw "Frontend failed to start."
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
Write-Host "[OK] Traffic AI V0.5.71 đã khởi động." -ForegroundColor Green
Write-Host "Dashboard : https://traffic-ai.test:8443"
Write-Host "API Docs  : https://traffic-ai.test:8444/docs"
$envNow = Get-Content $envPath -Raw -Encoding UTF8
$pgPortMatch = [regex]::Match($envNow, '(?m)^POSTGRES_HOST_PORT=(.+)$')
$pgDbMatch = [regex]::Match($envNow, '(?m)^POSTGRES_DB=(.+)$')
$pgPort = if ($pgPortMatch.Success) { $pgPortMatch.Groups[1].Value.Trim() } else { '5445' }
$pgDb = if ($pgDbMatch.Success) { $pgDbMatch.Groups[1].Value.Trim() } else { 'traffic_ai_db' }
Write-Host "PostgreSQL: 127.0.0.1:$pgPort / $pgDb"
Write-Host "AI stream : https://traffic-ai.test:8443/ai/streams/{camera_id}.mjpg"
