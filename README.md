# Traffic AI V0.2.3

**Đồ án môn Trí tuệ nhân tạo:** Nghiên cứu và xây dựng hệ thống phát hiện, phân loại, theo dõi và đếm phương tiện giao thông qua camera.

> Thư mục làm việc mặc định trên máy phát triển:
>
> ```powershell
> D:\LienThongDH\DoAn\traffic-ai
> ```

## 1. Trạng thái hiện tại

V0.2.3 giữ YOLO26n làm model chính, đồng thời sửa blocker runtime khiến Backend bị đánh dấu `unhealthy` sau khi toàn bộ test/build đã PASS. Backend healthcheck nay chỉ phụ thuộc Backend + PostgreSQL; trạng thái AI được tách sang endpoint riêng để loại bỏ phụ thuộc vòng khi Docker khởi động:

- PostgreSQL 18, database `traffic_ai_db`.
- Docker named volume `traffic_ai_postgres_data` để giữ dữ liệu bền vững.
- FastAPI + SQLAlchemy 2 + Alembic.
- React/Vite Dashboard.
- Nginx HTTPS Gateway.
- AI Service chạy **YOLO26n + ByteTrack + counting line**, hỗ trợ MP4/RTSP và ghi sự kiện vào PostgreSQL.
- GitHub Actions CI.
- Tự động kiểm thử → đẩy GitHub → tạo tag → tạo GitHub Release chỉ bằng **một lệnh**.
- Hỗ trợ GPU NVIDIA RTX 3060 qua Docker Compose GPU override, tự rơi về CPU nếu khởi động GPU thất bại.
- `start.ps1` tự tạo certificate HTTPS nếu source mới chưa có certificate.
- `start.ps1` tự thêm `traffic-ai.test` vào Windows hosts và tin cậy Root CA; khi cần quyền hệ thống, Windows chỉ hiện UAC để người dùng xác nhận.

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

### 4.2. Hostname và certificate HTTPS — tự động từ V0.2.2

Không cần sửa file `hosts` hay chạy tạo certificate bằng tay trước khi khởi động.

Lần đầu chạy:

```powershell
.\scripts\start.ps1
```

script sẽ tự:

1. tạo local Root CA và certificate HTTPS nếu `gateway/certs` chưa có;
2. thêm `127.0.0.1 traffic-ai.test` vào Windows `hosts` nếu còn thiếu;
3. import `Traffic AI Local Root CA` vào Windows Trusted Root;
4. flush DNS;
5. tiếp tục khởi động Docker Compose.

Khi Windows cần sửa `hosts` hoặc Trusted Root, cửa sổ **UAC** sẽ hiện. Chọn **Yes** để hoàn tất. Các lần chạy sau không cần cấu hình lại nếu certificate/hosts còn nguyên.

Certificate server có SAN cho:

- `traffic-ai.test`
- `localhost`
- `127.0.0.1`

Các script thủ công vẫn được giữ để chẩn đoán khi cần:

```powershell
.\scripts\generate-dev-cert.ps1
.\scripts\trust-dev-cert.ps1
```

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
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
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
GET  /api/system/status
GET  /api/dashboard/summary
GET  /api/cameras
POST /api/cameras
GET  /api/events
POST /api/events
GET  /api/models
GET  /api/meta/vehicle-types
GET  /api/meta/directions
GET  /api/sessions
GET  /api/pipelines
POST /api/cameras/{camera_id}/start
POST /api/cameras/{camera_id}/stop
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

Từ V0.1.4 trở đi, chỉ dùng **một lệnh**. Script tự đọc phiên bản trong file `VERSION`:

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
Tạo tag theo file `VERSION` (ví dụ `v0.2.3`)
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

## 10. Model AI mặc định: YOLO26n

V0.2.1 chuyển model pretrained mặc định từ `yolo11n.pt` sang `yolo26n.pt`. YOLO26 là dòng model Ultralytics phát hành tháng 01/2026 và hỗ trợ detection, training, validation, inference và export.

- Model mặc định: `yolo26n.pt`
- Tracker: ByteTrack
- Framework: Ultralytics `8.4.158`
- Dataset pretrained: COCO
- GPU mục tiêu: NVIDIA RTX 3060
- CPU fallback: có
- Custom model: vẫn có thể thay bằng `best.pt`; script nâng cấp **không ghi đè** custom model.

Tài liệu tham khảo chính thức: `https://docs.ultralytics.com/models/yolo26`

Khi chạy lần đầu và file `yolo26n.pt` chưa có trong `models`, Ultralytics có thể cần Internet để tải checkpoint. Sau khi checkpoint đã có trong thư mục model/volume, các lần chạy sau có thể tái sử dụng file đó.

### Nâng cấp từ V0.2.0

- Alembic tự chạy migration `0003_yolo26_baseline`.
- Model `YOLO11n COCO` được giữ lại trong database để phục vụ lịch sử/thực nghiệm, nhưng chuyển sang `is_active=false`.
- Model `YOLO26n COCO` được seed và đặt `is_active=true`.
- Nếu `.env` vẫn có đúng `AI_MODEL_NAME=yolo11n.pt`, `scripts/start.ps1` tự đổi sang `yolo26n.pt`.
- Nếu `.env` đang dùng model riêng như `best.pt`, script giữ nguyên.

## 11. Chạy AI với video hoặc RTSP

### Video MP4 local

Chép video vào thư mục:

```text
D:\LienThongDH\DoAn\traffic-ai\videos
```

Ví dụ file `demo.mp4` sẽ được AI Service đọc bằng đường dẫn trong container:

```text
/data/videos/demo.mp4
```

Tạo camera với `source_type=video`, sau đó bấm **Chạy AI** trên Dashboard.

### Camera RTSP

Tạo camera với `source_type=rtsp` và `source_url` dạng:

```text
rtsp://user:password@192.168.1.100:554/stream1
```

### GPU RTX 3060

Mặc định `start.ps1` thử chạy GPU NVIDIA trước:

```powershell
.\scripts\start.ps1
```

Nếu Docker/NVIDIA runtime chưa sẵn sàng, script tự thử lại ở CPU. Muốn ép CPU ngay từ đầu:

```powershell
.\scripts\start.ps1 -Cpu
```

Kiểm tra GPU/CUDA:

```powershell
.\scripts\check-gpu.ps1
```

Hoặc gọi trực tiếp AI health:

```powershell
Invoke-RestMethod -SkipCertificateCheck https://traffic-ai.test:8443/ai/health
```

Live MJPEG của camera đang chạy:

```text
https://traffic-ai.test:8443/ai/streams/{camera_id}.mjpg
```

Snapshot khi xe cắt counting line được lưu trong thư mục `snapshots` và `snapshot_path` được ghi vào bảng `vehicle_events`.

## 11.1. Healthcheck và khởi động ổn định từ V0.2.3

Docker Backend healthcheck sử dụng:

```text
GET /api/health
```

Endpoint này chỉ xác nhận Backend và PostgreSQL sẵn sàng. Nó **không gọi AI Service**. Trạng thái AI/GPU được lấy riêng qua:

```text
GET /api/system/status
```

Thiết kế này tránh phụ thuộc vòng `Backend health -> AI Service -> chờ Backend healthy`. Nếu Backend vẫn không healthy, `start.ps1` tự in Backend logs và trạng thái container thay vì thử CPU fallback không liên quan.

## 12. Các lệnh thường dùng

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

## 13. Bảo mật local

File `.env` không được commit lên GitHub. Khóa riêng certificate trong `gateway/certs/*.key` cũng bị chặn khỏi Git.

Mật khẩu local hiện tại được giữ để tương thích database đã tạo:

```text
TrafficAI@2026
```

Khi triển khai ngoài máy phát triển, phải thay mật khẩu và quản lý secret bằng cơ chế phù hợp.

## 14. Lịch sử phát triển

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

### V0.2.0 — AI Pipeline thực tế

- Tích hợp YOLO detector và ByteTrack tracker.
- Nhận nguồn video MP4 hoặc RTSP.
- Gán Track ID và chống đếm trùng theo Track ID.
- Counting line theo tọa độ chuẩn hóa, đếm hướng IN/OUT.
- Ghi `vehicle_events`, cập nhật `counting_sessions` trong PostgreSQL.
- Lưu snapshot khi phương tiện cắt counting line.
- Live MJPEG stream qua HTTPS Gateway.
- Dashboard có chọn camera, Start/Stop AI, FPS, tổng đếm và lịch sử sự kiện.
- Bổ sung migration `0002_ai_pipeline` và seed model YOLO11n COCO.
- Docker Compose hỗ trợ GPU NVIDIA và CPU fallback.
- CI dùng bộ test nhẹ cho thuật toán counting, trong khi Docker build vẫn kiểm tra image AI đầy đủ.

### V0.2.1 — Chuyển model chính sang YOLO26n

- Chuyển model mặc định từ `YOLO11n` sang **`YOLO26n`** (`yolo26n.pt`).
- Pin Ultralytics `8.4.158` để bảo đảm runtime có hỗ trợ YOLO26 và tăng tính tái lập của đồ án.
- Thêm migration `0003_yolo26_baseline`: giữ YOLO11n cho lịch sử so sánh nhưng kích hoạt YOLO26n.
- Backend, AI Service, Frontend và `VERSION` đồng bộ phiên bản `0.2.1`.
- Health API mặc định báo `yolo26n.pt`; bổ sung unit test khóa contract này.
- `start.ps1` tự nâng `.env` từ `yolo11n.pt` sang `yolo26n.pt` nhưng không ghi đè custom model.
- README giữ lịch sử phiên bản theo thứ tự tăng dần.

### V0.2.2 — Tự động bootstrap HTTPS/hosts khi khởi động

- Sửa blocker của V0.2.1: full source/release không chứa khóa TLS local nên `start.ps1` trước đây dừng với lỗi `HTTPS certificate not found`.
- `start.ps1` gọi `ensure-local-https.ps1` để tự tạo certificate còn thiếu trước khi chạy Docker Compose.
- Tự cấu hình `traffic-ai.test` trong Windows hosts và import đúng Root CA; chỉ yêu cầu xác nhận UAC khi hệ thống thực sự cần quyền Administrator.
- Thêm `setup-local-machine.ps1` để tách các thao tác cần quyền hệ thống khỏi phần khởi động bình thường.
- `generate-dev-cert.ps1` không giữ private key của Root CA sau khi ký server certificate.
- `.gitignore` bỏ qua toàn bộ certificate sinh local trong `gateway/certs`, chỉ giữ `.gitkeep`, tránh đưa certificate/khóa máy phát triển lên GitHub Release.
- `test.ps1` bổ sung contract test để ngăn việc quay lại blocker certificate thủ công.
- Backend, AI Service, Frontend và `VERSION` đồng bộ phiên bản `0.2.2`; không có migration database mới.

### V0.2.3 — Ổn định Backend runtime và migration local

- Sửa kiến trúc healthcheck: `GET /api/health` chỉ kiểm tra Backend + PostgreSQL, không gọi AI Service trong lúc AI Service còn đang chờ Backend healthy.
- Thêm `GET /api/system/status` cho Dashboard để lấy trạng thái mở rộng của AI/GPU mà không ảnh hưởng Docker healthcheck.
- Frontend tách trạng thái hệ thống khỏi Backend liveness; card GPU đọc dữ liệu từ `/api/system/status`.
- Migration `0002` và `0003` được làm idempotent hơn, không còn phụ thuộc tên unique constraint local; hỗ trợ database phát triển từng có schema drift.
- Thêm migration `0004_runtime_stability` để repair an toàn các cột pipeline còn thiếu, bảo đảm YOLO26 baseline tồn tại và ghi `schema_version=0.2.3` mà không ghi đè custom model đang active.
- Backend entrypoint chờ PostgreSQL rõ ràng, chạy Alembic với log revision/head nếu migration lỗi rồi mới khởi động Uvicorn.
- `start.ps1` không còn nhầm lỗi Backend thành lỗi GPU: nếu Backend unhealthy, script in trực tiếp log chẩn đoán và dừng; chỉ CPU fallback khi Backend không phải blocker.
- `diagnose.ps1` hiển thị health từng container, Backend logs, AI logs, Backend health, system status và AI health.
- `test.ps1` bổ sung contract chống tái xuất hiện phụ thuộc vòng Backend ↔ AI.
- Backend, AI Service, Frontend và `VERSION` đồng bộ phiên bản `0.2.3`.

## 15. Lộ trình tiếp theo

### V0.3 — Huấn luyện và đánh giá model riêng

- Thu thập và gán nhãn dữ liệu giao thông Việt Nam.
- Fine-tune model từ dataset riêng.
- Lưu Precision, Recall, mAP50, mAP50-95 và thông tin training vào `ai_models`.
- So sánh pretrained và fine-tuned model trên cùng tập test.
- Thống kê counting error và FPS.

### Các giai đoạn sau

- Fine-tune dataset giao thông Việt Nam.
- So sánh model và lưu metric huấn luyện.
- Thống kê theo giờ/ngày/camera/loại xe.
- Xuất báo cáo Excel/CSV.
- Nhiều camera và tối ưu hiệu năng GPU.
