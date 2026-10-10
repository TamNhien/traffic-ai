[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path '.env')) { throw 'Không tìm thấy .env. Không thay đổi PostgreSQL.' }
$envText = Get-Content '.env' -Raw -Encoding UTF8
$u = [regex]::Match($envText, '(?m)^POSTGRES_USER=([^\r\n]+)')
$d = [regex]::Match($envText, '(?m)^POSTGRES_DB=([^\r\n]+)')
$p = [regex]::Match($envText, '(?m)^POSTGRES_PASSWORD=([^\r\n]*)')
if (-not $u.Success -or -not $d.Success -or -not $p.Success) {
  throw 'Thiếu POSTGRES_USER / POSTGRES_DB / POSTGRES_PASSWORD trong .env.'
}
$dbUser = $u.Groups[1].Value.Trim()
$dbName = $d.Groups[1].Value.Trim()
# Only standard SQL identifiers; never interpolate arbitrary input into a psql meta-command.
if ($dbUser -notmatch '^[A-Za-z_][A-Za-z0-9_]*$' -or $dbName -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
  throw 'POSTGRES_USER / POSTGRES_DB không đúng định dạng nhận diện an toàn.'
}
if ([string]::IsNullOrWhiteSpace($p.Groups[1].Value) -or $p.Groups[1].Value -eq 'CHANGE_ME_GENERATED_ON_START') {
  throw 'POSTGRES_PASSWORD đang rỗng hoặc là mật khẩu mẫu. Hãy đặt secret mạnh trong .env trước.'
}

$names = @(& docker ps --filter 'name=^/traffic-ai-postgres$' --format '{{.Names}}' 2>$null)
if ($LASTEXITCODE -ne 0 -or $names -notcontains 'traffic-ai-postgres') {
  throw 'Container traffic-ai-postgres chưa chạy. Dùng docker compose up -d --no-deps postgres trước.'
}

Write-Host '[Traffic AI] Đồng bộ mật khẩu PostgreSQL an toàn, không xóa volume.' -ForegroundColor Cyan
Write-Host 'Mở .env tại máy cục bộ, sao chép POSTGRES_PASSWORD. KHÔNG gửi secret vào chat/log.' -ForegroundColor Yellow
Write-Host "PostgreSQL sẽ yêu cầu nhập lại mật khẩu mới 2 lần cho role $dbUser (ký tự sẽ được ẩn)." -ForegroundColor Yellow
Write-Host 'Lưu ý: đổi mật khẩu role này có thể ảnh hưởng các ứng dụng khác dùng cùng role.' -ForegroundColor Yellow

# psql's \password handles secret input safely (not a plaintext SQL command,
# command-line argument, PowerShell history entry, or shell variable).
& docker exec -it traffic-ai-postgres psql -X -v ON_ERROR_STOP=1 -U $dbUser -d $dbName -c "\password $dbUser"
if ($LASTEXITCODE -ne 0) {
  throw 'Không thực thi được psql \password. Không đổi pg_hba.conf, không tắt xác thực hoặc xóa volume.'
}

# Verify SCRAM over TCP using only container env (no credential in output).
$query = 'PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -X -q -t -A -c "SELECT 1" 2>/dev/null'
$result = & docker exec traffic-ai-postgres sh -c $query 2>$null
if ($LASTEXITCODE -ne 0 -or ($result -join "`n").Trim() -ne '1') {
  throw 'Mật khẩu PostgreSQL chưa trùng với môi trường của container. Kiểm tra .env, chạy docker compose up -d --no-deps --force-recreate postgres, rồi thử lại. Không hiện mật khẩu.'
}
Write-Host '[OK] PostgreSQL TCP/SCRAM authentication thành công. Dữ liệu và volume được giữ nguyên.' -ForegroundColor Green
Write-Host 'Tiếp theo: .\\scripts\\start.ps1' -ForegroundColor Cyan
