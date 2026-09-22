# Traffic AI V0.2.9

**Đồ án môn Trí tuệ nhân tạo:** Nghiên cứu và xây dựng hệ thống phát hiện, phân loại, theo dõi và đếm phương tiện giao thông qua camera.

> Thư mục làm việc mặc định trên máy phát triển:
>
> ```powershell
> D:\LienThongDH\DoAn\traffic-ai
> ```

## 1. Trạng thái hiện tại

V0.2.9 sửa lỗi nâng cấp tại chỗ khi thư mục dự án cũ vẫn còn `scripts/release.ps1` hoặc `scripts/push-github.ps1`. Từ bản này, `scripts/test.ps1` tự nhận diện và xóa hai wrapper phát hành legacy trước khi chạy contract, nên người dùng có thể chép đè full source mới lên `D:\LienThongDH\DoAn\traffic-ai` mà không cần tự dọn file cũ. Lệnh phát hành duy nhất tiếp tục là `scripts/publish.ps1`. Các chức năng nguồn video, YOLO26n + ByteTrack, Smart Counting, PostgreSQL và stack công nghệ của V0.2.8 được giữ nguyên.

Trường hợp như `CAM-001` vẫn lưu `/data/videos/traffic_video.mp4` sau khi file đã đổi thành `demo.mp4` được xử lý theo hai lớp:

1. Dashboard hiển thị rõ nguồn cũ bị thiếu và cho chọn `demo.mp4` rồi bấm **Cập nhật camera** để lưu lại vào PostgreSQL.
2. Nếu thư mục `videos` chỉ có đúng một video hợp lệ, khi bấm **Chạy AI** Backend có thể tự sửa đường dẫn cũ sang video duy nhất đó, lưu lại database, probe frame đầu bằng OpenCV rồi mới tạo session và khởi động pipeline.

Các thành phần chính:

- PostgreSQL **18.6**, database `traffic_ai_db`, volume `traffic_ai_postgres_data`.
- Python **3.14.7** cho Backend/AI Service.
- FastAPI **0.141.1**, Uvicorn **0.53.0**, SQLAlchemy **2.0.54**, Alembic **1.20.0**, Psycopg **3.3.6**.
- YOLO26n qua Ultralytics **8.4.158**, PyTorch **2.14.0**, TorchVision **0.29.0**, OpenCV headless **5.0.0.93**.
- React **19.3.0**, Vite **8.3.0**, `@vitejs/plugin-react` **6.1.1**.
- Node.js **26.9.0 Current**, npm **12.0.2** cho build/test frontend.
- Nginx **1.31.6 mainline** cho frontend image và HTTPS Gateway.
- Docker Compose, HTTPS `traffic-ai.test`, GitHub Actions và phát hành tự động bằng `scripts/publish.ps1`.
- RTX 3060/CUDA vẫn là đường chạy ưu tiên; CPU fallback được giữ nguyên.

## 1.1. Phiên bản công nghệ V0.2.9

| Thành phần | Phiên bản |
|---|---:|
| Python | `3.14.7` |
| pip | `26.2.1` |
| FastAPI | `0.141.1` |
| Uvicorn | `0.53.0` |
| SQLAlchemy | `2.0.54` |
| Alembic | `1.20.0` |
| Psycopg | `3.3.6` |
| Pydantic | `2.13.5` |
| pydantic-settings | `2.15.0` |
| PostgreSQL | `18.6` |
| Ultralytics | `8.4.158` |
| PyTorch | `2.14.0` |
| TorchVision | `0.29.0` |
| OpenCV headless | `5.0.0.93` |
| React / React DOM | `19.3.0` |
| Vite | `8.3.0` |
| @vitejs/plugin-react | `6.1.1` |
| Node.js | `26.9.0` Current |
| npm | `12.0.2` |
| Nginx | `1.31.6` mainline |

Ghi chú: V0.2.9 tiếp tục ưu tiên **bản phát hành mới không phải beta/RC**. Vì vậy PostgreSQL 19 beta và SQLAlchemy 2.1 RC không được đưa vào stack chính.

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
PATCH /api/cameras/{camera_id}
GET  /api/sources/videos
GET  /api/cameras/{camera_id}/source-status
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

1. Contract HTTPS, Backend health, UTF-8, logo/favicon và GitHub Release.
2. Contract khóa phiên bản công nghệ V0.2.9.
3. Contract quản lý nguồn video/camera, preflight và auto-repair đường dẫn cũ.
4. Kiểm tra cú pháp Backend và AI Service trên Python 3.14.7.
5. Backend unit tests và AI Service unit tests bằng pytest 9.1.1.
6. Cài npm 12.0.2, kiểm tra `npm audit --audit-level=high`, build React/Vite bằng Node 26.9.0.
7. Validate Docker Compose.
8. Build các Docker image ứng dụng.

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

Không truyền version bằng tham số. `publish.ps1` luôn đọc đúng phiên bản từ file `VERSION` của full source hiện tại để tránh phát hành nhầm tag cũ.

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
Tạo tag theo file `VERSION` (ví dụ `v0.2.9`)
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

### Sửa camera cũ sau khi đổi tên video

Nếu camera trong PostgreSQL vẫn lưu tên file cũ, ví dụ:

```text
/data/videos/traffic_video.mp4
```

nhưng file thật đã đổi thành:

```text
D:\LienThongDH\DoAn\traffic-ai\videos\demo.mp4
```

Dashboard V0.2.9 sẽ báo **Nguồn chưa sẵn sàng** và liệt kê video thật trong thư mục `videos`. Chọn `demo.mp4` rồi bấm **Cập nhật camera**. Database sẽ lưu lại:

```text
/data/videos/demo.mp4
```

Nếu chỉ có đúng một video hợp lệ, Backend còn có cơ chế auto-repair khi bấm **Chạy AI**: cập nhật `source_url` trong PostgreSQL, đọc thử frame đầu rồi mới tạo session. Vì vậy việc **Lưu cấu hình đếm** không còn dẫn tới một session lỗi chỉ vì camera đang trỏ vào file cũ.

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
- `publish.ps1` là lệnh phát hành chính thức; các wrapper legacy được loại khỏi full source ở V0.2.8 để tránh nhầm lệnh cũ.
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

### V0.2.4 — Chuẩn hóa tiếng Việt UTF-8 trên Dashboard

- Sửa lỗi giao diện hiển thị nguyên chuỗi dạng `\u00e1`, `\u1ed5`, `\u0111` thay vì chữ tiếng Việt có dấu.
- Chuyển toàn bộ text frontend sang ký tự Unicode UTF-8 thực trong `frontend/src/main.jsx`, bao gồm nội dung JSX, thuộc tính JSX và chuỗi JavaScript.
- Giữ `<meta charset="UTF-8">` trong `frontend/index.html` và bổ sung test contract kiểm tra charset.
- `test.ps1` fail-closed nếu frontend còn literal Unicode escape dạng `\uXXXX`, ngăn tái phát lỗi sau các lần sinh/cập nhật source.
- Backend, AI Service, Frontend và `VERSION` đồng bộ phiên bản `0.2.4`.
- Không có migration database mới; dữ liệu PostgreSQL hiện tại được giữ nguyên.

### V0.2.5 — Sửa false-positive UTF-8 và gia cố Release tự động

- Sửa `test.ps1`: contract UTF-8 chỉ quét source frontend (`frontend/src`, `index.html`, `vite.config.js`, `package.json`), không quét `frontend/dist` hoặc `node_modules`.
- Bundle do Vite/esbuild sinh có thể chứa `\uXXXX` hợp lệ; đây không phải lỗi hiển thị nếu source JSX đã là UTF-8 thực.
- Xóa `frontend/dist` cũ trước mỗi lần frontend build để tránh artifact stale gây nhiễu khi kiểm tra thủ công.
- Gia cố `publish.ps1`: tìm GitHub Actions Release theo commit SHA của tag thay vì chỉ dựa vào `headBranch`.
- Nếu workflow Release không xuất hiện sau thời gian chờ, script tự tạo ZIP, TAR.GZ, `SHA256SUMS.txt` và GitHub Release trực tiếp bằng `gh`, không dừng ở lỗi timeout.
- Thêm `.gitattributes` để chuẩn hóa line ending và giảm cảnh báo LF/CRLF trên Windows.
- Backend, AI Service, Frontend và `VERSION` đồng bộ phiên bản `0.2.5`.
- Không có migration database mới; schema vẫn ở `0004_runtime_stability`, dữ liệu PostgreSQL được giữ nguyên.

### V0.2.6 — Logo/Favicon web và Release fallback khi GitHub Actions lỗi

- Thêm `frontend/public/logo.svg` và dùng logo thật tại sidebar thay cho ô chữ `AI` thuần CSS.
- Thêm `frontend/public/favicon.svg`, `favicon.ico`, `apple-touch-icon.png` và `site.webmanifest`; tab trình duyệt từ nay hiển thị logo Traffic AI thay cho biểu tượng mặc định.
- `frontend/index.html` khai báo favicon có version query để hạn chế cache favicon cũ sau khi nâng cấp.
- `test.ps1` bổ sung **Frontend logo/favicon contract**, fail nếu thiếu logo, favicon, manifest hoặc sidebar không dùng `logo.svg`.
- Sửa `release.yml`: workflow Release tự kiểm thử Backend, AI Service, build Frontend và validate Docker Compose trước khi đóng gói; bỏ Docker image build lặp lại ở bước Release vì CI/local test đã thực hiện phần này.
- Sửa lỗi workflow thực tế của V0.2.5: `DATABASE_URL_OVERRIDE: sqlite+pysqlite:///:memory:` là plain YAML scalar kết thúc bằng dấu `:` nên parser có thể coi workflow gọi lại là không hợp lệ; V0.2.6 quote giá trị thành `"sqlite+pysqlite:///:memory:"` trong toàn bộ workflow.
- Sửa `publish.ps1`: nếu GitHub Actions Release **có xuất hiện nhưng chạy failure**, script in log lỗi rồi tự fallback tạo Release bằng GitHub CLI thay vì dừng cứng.
- Nếu workflow thành công nhưng chưa tạo Release, script cũng fallback trực tiếp; mục tiêu là một lệnh `publish.ps1` vẫn khép kín quá trình phát hành.
- `test.ps1` bổ sung **GitHub Release fallback contract** để ngăn việc quay lại hành vi dừng cứng của V0.2.5.
- Backend, AI Service, Frontend và `VERSION` đồng bộ phiên bản `0.2.6`.
- Không có migration database mới; schema PostgreSQL vẫn ở `0004_runtime_stability`.

### V0.2.7 — Đếm ổn định, lưu PostgreSQL và chạy lại video

- Sửa thuật toán crossing: dùng **bottom-center** của bounding box làm điểm đại diện của xe và kiểm tra đoạn chuyển động giữa hai frame có thực sự cắt counting line.
- Giữ được crossing khi track đi qua đúng pixel của line hoặc nhảy qua line giữa hai frame.
- Thêm bộ đếm IN/OUT tích lũy và trạng thái `detected_tracks`, `delivered_events`, `pending_events`, `delivery_failures` cho mỗi pipeline.
- Sự kiện crossing được retry khi Backend/PostgreSQL tạm thời chưa nhận; pending event được flush lại trong lúc chạy và trước khi đóng session.
- Endpoint ghi event trở thành idempotent theo `session_id + tracking_id`, tránh đếm trùng khi retry mạng.
- Mỗi event ngoài `vehicle_events` còn cập nhật `vehicle_counts` theo bucket giờ để có dữ liệu thống kê thực sự.
- Callback kết thúc session được retry nhiều lần; Backend tự hòa giải session `running` bị stale nếu AI pipeline thực tế đã kết thúc, vì vậy cùng một MP4 có thể bấm **Chạy AI** lại.
- Dashboard cho phép chọn preset counting line **ngang/dọc**, chỉnh X1/Y1/X2/Y2 và confidence, lưu cấu hình cho camera đang chọn.
- Dashboard hiển thị trạng thái lần chạy gần nhất, số frame, tổng xe, sự kiện đã ghi và lịch sử các counting session.
- Nâng pip trong Docker, local test và GitHub Actions lên **26.2.1** (bản mới nhất trên PyPI tại thời điểm V0.2.7).
- Thêm `pytest.ini` để loại warning `anyio.abc.BlockingPortal` từ Starlette TestClient khỏi warning summary, giữ output test sạch.
- GitHub Actions chuyển sang `actions/checkout@v7`, `actions/setup-python@v7`, `actions/setup-node@v7`, Node 24 và `ubuntu-24.04` để tránh cảnh báo runtime Node 20/runner migration.
- `release.ps1` chỉ còn là alias đọc version từ file `VERSION`; lệnh phát hành chính thức duy nhất vẫn là `./scripts/publish.ps1`.
- Thêm migration `0005_counting_reliability`, cập nhật `schema_version` thành `0.2.7`; không xóa dữ liệu cũ.

> Nếu PowerShell hiển thị mờ lệnh cũ như `./scripts/release.ps1 -Version 0.1.3` sau dấu nhắc, đó là **PSReadLine history prediction**, không phải lệnh do Traffic AI tự chạy. Nhấn `Esc` để bỏ gợi ý hoặc tiếp tục dùng `./scripts/publish.ps1`.

### V0.2.8 — Quản lý nguồn video và nâng toàn bộ stack

- Sửa nguyên nhân CAM-001 vẫn giữ tên video cũ trong PostgreSQL: Dashboard chuyển từ create-only sang **create/update camera** và luôn nạp `source_url` thật của camera đang chọn.
- AI Service thêm `GET /sources/videos` và `POST /sources/validate`; nguồn video local được kiểm tra tồn tại, định dạng và có thể probe frame đầu bằng OpenCV trước khi pipeline chạy.
- Backend thêm `GET /api/sources/videos`, `GET /api/cameras/{id}/source-status` và preflight nguồn trước khi tạo `counting_sessions`.
- Khi đường dẫn video cũ không tồn tại nhưng thư mục `videos` chỉ có đúng một video hợp lệ, Backend tự sửa `source_url`, lưu PostgreSQL rồi mới chạy AI.
- Dashboard có trạng thái nguồn, danh sách video thật, nút **Dùng nguồn gợi ý**, **Cập nhật camera** và khóa nút Chạy AI khi nguồn không thể sửa an toàn.
- Thêm migration `0006_source_management`, cập nhật `schema_version=0.2.8`.
- Nâng Python 3.14.7; FastAPI 0.141.1; Uvicorn 0.53.0; SQLAlchemy 2.0.54; Alembic 1.20.0; Psycopg 3.3.6; Pydantic 2.13.5; pydantic-settings 2.15.0.
- Nâng PyTorch 2.14.0, TorchVision 0.29.0, OpenCV 5.0.0.93; giữ Ultralytics 8.4.158/YOLO26n là bản Ultralytics mới nhất đã xác minh tại thời điểm phát hành.
- Nâng React/React DOM 19.3.0, Vite 8.3.0, `@vitejs/plugin-react` 6.1.1, Node.js 26.9.0 Current, npm 12.0.2.
- Pin PostgreSQL image 18.6 và Nginx 1.31.6 mainline.
- CI/local test thêm contract khóa phiên bản công nghệ và source-management để tránh tái phát lỗi source stale.
- Full source chỉ dùng `scripts/publish.ps1` cho quy trình test → GitHub → Release.


### V0.2.9 — Tự dọn script phát hành legacy khi nâng cấp tại chỗ

- Sửa blocker `Còn script phát hành legacy release.ps1` khi chép source mới đè lên thư mục dự án cũ.
- `scripts/test.ps1` tự xóa `release.ps1` và `push-github.ps1` còn sót lại trước khi kiểm tra contract phát hành.
- Nếu không thể xóa vì quyền file, test dừng với thông báo rõ ràng thay vì gây nhầm lẫn về phiên bản.
- Chỉ giữ `scripts/publish.ps1` là lệnh test → GitHub → tag → Release chính thức.
- Thêm migration `0007_release_hygiene`, cập nhật `schema_version=0.2.9`.
- Giữ nguyên stack công nghệ và pipeline AI của V0.2.8.

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
