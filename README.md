# Traffic AI V0.1.4

**Đồ án môn Trí tuệ nhân tạo:** Nghiên cứu và xây dựng hệ thống phát hiện, phân loại, theo dõi và đếm phương tiện giao thông qua camera.

> Thư mục làm việc mặc định trên máy phát triển:
>
> ```powershell
> D:\LienThongDH\DoAn\traffic-ai
> ```

## 1. Trạng thái hiện tại

V0.1.x tập trung xây dựng nền tảng ổn định trước khi tích hợp pipeline AI thực tế ở V0.2:

- PostgreSQL 18, database `traffic_ai_db`.
- Docker named volume `traffic_ai_postgres_data` để giữ dữ liệu bền vững.
- FastAPI + SQLAlchemy 2 + Alembic.
- React/Vite Dashboard.
- Nginx HTTPS Gateway.
- AI Service scaffold, chuẩn bị cho YOLO + ByteTrack.
- GitHub Actions CI.
- Tự động kiểm thử → đẩy GitHub → tạo tag → tạo GitHub Release chỉ bằng **một lệnh**.

## 2. Cổng và địa chỉ cố định

| Thành phần | Địa chỉ |
|---|---|
| Dashboard HTTPS | `https://traffic-ai.test:8443` |
| Backend API HTTPS | `https://traffic-ai.test:8444` |
| Swagger | `https://traffic-ai.test:8444/docs` |
| PostgreSQL từ Windows/pgAdmin | `127.0.0.1:5445` |
| PostgreSQL nội bộ Docker | `postgres:5432` |
| Database | `traffic_ai_db` |
| PostgreSQL user | `traffic_admin` |

Dự án **không sử dụng** port `3000`, host port `5432` hoặc port `5434`.

## 3. Database hiện có

Sau khi Alembic chạy thành công, schema `public` có các bảng:

- `users`
- `cameras`
- `ai_models`
- `counting_sessions`
- `vehicle_events`
- `vehicle_counts`
- `system_settings`
- `alembic_version`

## 4. Chuẩn bị máy phát triển

### 4.1. Mở thư mục dự án

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
```

### 4.2. Cấu hình hosts

File:

```text
C:\Windows\System32\drivers\etc\hosts
```

Cần có:

```text
127.0.0.1 traffic-ai.test
```

### 4.3. Tạo và tin cậy certificate HTTPS

Docker Desktop phải đang chạy.

```powershell
.\scripts\generate-dev-cert.ps1
```

Sau đó mở PowerShell bằng **Run as Administrator**:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\trust-dev-cert.ps1
```

Certificate server có SAN cho:

- `traffic-ai.test`
- `localhost`
- `127.0.0.1`

### 4.4. PostgreSQL 18

Nếu máy đã có container `traffic-ai-postgres` được tạo thủ công và volume `traffic_ai_postgres_data`, chỉ chuyển quyền quản lý container sang Docker Compose:

```powershell
.\scripts\adopt-existing-postgres.ps1
```

Script **không xóa volume database**.

Kiểm tra volume:

```powershell
docker volume ls --filter "name=traffic_ai_postgres_data"
```

## 5. Chạy hệ thống

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\start.ps1
```

Hoặc trực tiếp:

```powershell
docker compose up -d --build
```

Backend tự chạy:

```text
alembic upgrade head
```

### Kiểm tra trạng thái

```powershell
.\scripts\status.ps1
```

Kiểm tra database:

```powershell
.\scripts\verify-database.ps1
```

Dashboard:

```text
https://traffic-ai.test:8443
```

Swagger:

```text
https://traffic-ai.test:8444/docs
```

## 6. pgAdmin Desktop

Kết nối server `Traffic AI PostgreSQL`:

```text
Host:                 127.0.0.1
Port:                 5445
Maintenance database: traffic_ai_db
Username:             traffic_admin
Password:             TrafficAI@2026
```

Trong pgAdmin:

```text
Databases
  └── traffic_ai_db
      └── Schemas
          └── public
              └── Tables
```

Nếu chưa thấy bảng mới, nhấn chuột phải vào **Tables → Refresh**.

## 7. API hiện có

```text
GET  /api/health
GET  /api/dashboard/summary
GET  /api/cameras
POST /api/cameras
GET  /api/events
POST /api/events
GET  /api/models
GET  /api/meta/vehicle-types
GET  /api/meta/directions
```

Ví dụ tạo camera từ Swagger:

```json
{
  "name": "Camera cổng chính",
  "code": "CAM-001",
  "source_type": "rtsp",
  "source_url": "rtsp://user:password@192.168.1.100:554/stream1",
  "location": "Cổng chính",
  "description": "Camera demo Traffic AI"
}
```

## 8. Kiểm thử tự động

Chạy toàn bộ kiểm thử tại máy phát triển:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\test.ps1
```

Các bước kiểm thử gồm:

1. Kiểm tra cú pháp Backend Python.
2. Kiểm tra cú pháp AI Service Python.
3. Backend unit tests.
4. AI Service unit tests.
5. Build Frontend.
6. Validate Docker Compose.
7. Build các Docker image ứng dụng.

Khi thành công sẽ có:

```text
[SUCCESS] All Traffic AI tests passed.
```

## 9. Một lệnh duy nhất để test + GitHub + Release

### Chuẩn bị một lần

Cài GitHub CLI và đăng nhập đúng tài khoản `TamNhien`:

```powershell
gh auth login
```

Kiểm tra:

```powershell
gh api user --jq .login
```

Kết quả phải là:

```text
TamNhien
```

### Lệnh phát hành chính thức

Từ V0.1.4, chỉ dùng **một lệnh**. Script tự đọc phiên bản trong file `VERSION`:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai; .\scripts\publish.ps1
```

Nếu cần chỉ định phiên bản thủ công, vẫn có thể dùng `-Version X.Y.Z`.

Script sẽ tự động thực hiện theo đúng thứ tự:

```text
Kiểm thử local
    ↓
Tất cả PASS?
    ├── Không → Dừng, không push, không release
    └── Có
         ↓
Kiểm tra đăng nhập GitHub TamNhien
         ↓
Tạo TamNhien/traffic-ai nếu repository chưa tồn tại
         ↓
Cập nhật VERSION + frontend/package.json
         ↓
Kiểm tra .env và khóa riêng TLS không bị commit
         ↓
Commit source
         ↓
Tạo tag v0.1.4
         ↓
Push main
         ↓
Push tag
         ↓
GitHub Actions kiểm thử Release
         ↓
Tạo ZIP + TAR.GZ + SHA256SUMS.txt
         ↓
Tạo GitHub Release
         ↓
Script chờ workflow hoàn tất và xác nhận Release tồn tại
```

Nếu muốn tạo repository ở chế độ public trong lần đầu:

```powershell
.\scripts\publish.ps1 -Visibility public
```

Không nên dùng `-SkipTests` khi phát hành chính thức.

Repository mặc định:

```text
https://github.com/TamNhien/traffic-ai
```

Release:

```text
https://github.com/TamNhien/traffic-ai/releases
```

## 10. Các lệnh thường dùng

Khởi động/build:

```powershell
.\scripts\start.ps1
```

Xem toàn bộ log:

```powershell
docker compose logs -f
```

Chỉ xem Backend:

```powershell
docker compose logs -f backend
```

Chẩn đoán lỗi:

```powershell
.\scripts\diagnose.ps1
```

Dừng hệ thống nhưng giữ database:

```powershell
.\scripts\stop.ps1
```

**Không chạy** lệnh dưới đây nếu không chủ đích xóa dữ liệu:

```powershell
docker compose down -v
```

Volume cần giữ:

```text
traffic_ai_postgres_data
```

## 11. Bảo mật local

File `.env` không được commit lên GitHub. Khóa riêng certificate trong `gateway/certs/*.key` cũng bị chặn khỏi Git.

Mật khẩu local hiện tại được giữ để tương thích database đã tạo:

```text
TrafficAI@2026
```

Khi triển khai ngoài máy phát triển, phải thay mật khẩu và quản lý secret bằng cơ chế phù hợp.

## 12. Lịch sử phát triển

Các phiên bản được sắp xếp **tăng dần**:

### V0.1.0 — Nền tảng ban đầu

- Khởi tạo kiến trúc Traffic AI.
- PostgreSQL 18 + `traffic_ai_db`.
- FastAPI, SQLAlchemy 2, Alembic.
- React/Vite Dashboard.
- Nginx HTTPS.
- AI Service scaffold.
- Docker Compose.

### V0.1.1 — Ổn định Backend và PostgreSQL

- Sửa lỗi Alembic/SQLAlchemy khi mật khẩu PostgreSQL chứa ký tự đặc biệt.
- Sử dụng volume PostgreSQL hiện có dưới dạng external volume.
- Cải thiện kiểm tra hosts và script chẩn đoán.

### V0.1.2 — CI/CD và kiểm thử tự động

- Thêm `scripts/test.ps1`.
- Thêm Backend/AI unit test pipeline.
- Thêm GitHub Actions CI.
- Thêm workflow tạo GitHub Release tự động.
- Sửa `PYTHONPATH` cho test Backend và AI Service.

### V0.1.3 — Tự động hóa GitHub

- Mặc định GitHub owner là `TamNhien`.
- Tự tạo repository `TamNhien/traffic-ai` nếu chưa tồn tại.
- Tự commit/push/tag.
- Chặn commit `.env` và khóa riêng TLS.
- Chuẩn hóa full-source workflow sau mỗi lần sửa lỗi.

### V0.1.4 — Một lệnh phát hành hoàn chỉnh

- README chuyển hoàn toàn sang **tiếng Việt có dấu**.
- Gom quy trình test, GitHub và Release vào `scripts/publish.ps1`.
- Một lệnh chạy test → tạo repo nếu cần → commit → push → tag → GitHub Actions → Release.
- Script chờ GitHub Actions hoàn tất và kiểm tra Release đã được tạo.
- `release.ps1` và `push-github.ps1` được giữ làm wrapper tương thích, nhưng `publish.ps1` là lệnh chính thức.
- Lịch sử phiên bản trong README được sắp xếp tăng dần.

## 13. Lộ trình tiếp theo

### V0.2 — AI Pipeline

- NVIDIA RTX 3060 / CUDA.
- YOLO detector.
- ByteTrack tracker.
- Input MP4, webcam và RTSP.
- Track ID ổn định.
- Counting line.
- Đếm IN/OUT và chống đếm trùng.
- Ghi `vehicle_events` vào PostgreSQL.
- Live Dashboard cập nhật dữ liệu AI.

### Các giai đoạn sau

- Fine-tune dataset giao thông Việt Nam.
- So sánh model và lưu metric huấn luyện.
- Thống kê theo giờ/ngày/camera/loại xe.
- Xuất báo cáo Excel/CSV.
- Nhiều camera và tối ưu hiệu năng GPU.
