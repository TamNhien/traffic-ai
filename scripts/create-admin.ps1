[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Write-Host "Traffic AI V0.5.68 - Tạo quản trị viên đầu tiên" -ForegroundColor Cyan
Write-Host "Mật khẩu sẽ được nhập ẩn, KHÔNG dùng mật khẩu mặc định." -ForegroundColor Yellow
docker compose -f docker-compose.yml exec backend python -m app.create_admin
if ($LASTEXITCODE -ne 0) { throw "Không tạo được Admin. Kiểm tra Docker/backend và quyền tài khoản." }
