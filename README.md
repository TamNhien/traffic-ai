# Traffic AI V0.1.3

Do an Tri tue nhan tao: he thong phat hien, theo doi va dem phuong tien giao thong qua camera.

## Trang thai V0.1.3

V0.1 tap trung vao ha tang chay duoc truoc khi gan YOLO/ByteTrack:

- PostgreSQL 18, database `traffic_ai_db`
- Docker named volume `traffic_ai_postgres_data`
- FastAPI + SQLAlchemy 2 + Alembic
- React/Vite dashboard
- Nginx HTTPS gateway
- AI service scaffold de V0.2 gan YOLO + ByteTrack
- Schema co san cho camera, AI model, counting session, vehicle event, aggregate count va system settings

## Cong duoc co dinh

| Thanh phan | Dia chi |
|---|---|
| Dashboard HTTPS | `https://traffic-ai.test:8443` |
| API HTTPS | `https://traffic-ai.test:8444` |
| Swagger | `https://traffic-ai.test:8444/docs` |
| PostgreSQL tu Windows/pgAdmin | `127.0.0.1:5445` |
| PostgreSQL noi bo Docker | `postgres:5432` |
| Database | `traffic_ai_db` |
| User | `traffic_admin` |

Khong su dung port 3000, 5432 tren host, hoac 5434.

## Database tables V0.1

Sau khi Alembic chay, database se co:

- `users`
- `cameras`
- `ai_models`
- `counting_sessions`
- `vehicle_events`
- `vehicle_counts`
- `system_settings`
- `alembic_version`

## Chuan bi tren may hien tai

May da co container PostgreSQL tao thu cong va volume `traffic_ai_postgres_data`. Khong xoa volume nay.

### 1. Giai nen source

Vi du:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
```

### 2. Hosts

File:

```text
C:\Windows\System32\drivers\etc\hosts
```

Can co:

```text
127.0.0.1 traffic-ai.test
```

### 3. Tao certificate HTTPS

Docker Desktop phai dang chay:

```powershell
.\scripts\generate-dev-cert.ps1
```

Sau do mo PowerShell bang **Run as Administrator**:

```powershell
.\scripts\trust-dev-cert.ps1
```

Certificate server co SAN cho:

- `traffic-ai.test`
- `localhost`
- `127.0.0.1`

### 4. Chuyen container PostgreSQL thu cong sang Docker Compose

Container hien tai co ten `traffic-ai-postgres`. Script nay chi xoa container, KHONG xoa named volume:

```powershell
.\scripts\adopt-existing-postgres.ps1
```

Kiem tra volume van con:

```powershell
docker volume ls --filter "name=traffic_ai_postgres_data"
```

### 5. Khoi dong toan bo he thong

```powershell
.\scripts\start.ps1
```

Script se chay:

```powershell
docker compose up -d --build
```

Backend se tu dong chay:

```text
alembic upgrade head
```

nen schema V0.1 duoc tao trong `traffic_ai_db` ma khong can tao table bang tay.

## Kiem tra sau khi chay

```powershell
docker compose ps
```

hoac:

```powershell
.\scripts\status.ps1
```

Kiem tra database:

```powershell
.\scripts\verify-database.ps1
```

Mo:

```text
https://traffic-ai.test:8443
```

Swagger:

```text
https://traffic-ai.test:8444/docs
```

## pgAdmin Desktop

Server `Traffic AI PostgreSQL`:

```text
Host:                 127.0.0.1
Port:                 5445
Maintenance database: traffic_ai_db
Username:             traffic_admin
Password:             TrafficAI@2026
```

Sau khi V0.1.1 chay, vao:

```text
Databases
  -> traffic_ai_db
     -> Schemas
        -> public
           -> Tables
```

va Refresh de thay cac bang moi.

## API hien co

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

Vi du tao camera tu Swagger:

```json
{
  "name": "Camera cong chinh",
  "code": "CAM-001",
  "source_type": "rtsp",
  "source_url": "rtsp://user:password@192.168.1.100:554/stream1",
  "location": "Cong chinh",
  "description": "Camera demo Traffic AI"
}
```

## Lenh thuong dung

Khoi dong/build:

```powershell
.\scripts\start.ps1
```

Xem log:

```powershell
docker compose logs -f
```

Chi xem backend:

```powershell
docker compose logs -f backend
```

Dung he thong ma giu database:

```powershell
.\scripts\stop.ps1
```

**Khong dung** lenh sau neu khong chu dich xoa database:

```powershell
docker compose down -v
```

Volume database phai duoc giu:

```text
traffic_ai_postgres_data
```

## Bao mat local

`.env` hien dung mat khau local de tuong thich voi database da tao:

```text
TrafficAI@2026
```

Truoc khi dua source len Git hoac trien khai sang may khac, hay doi mat khau va khong commit file `.env`.

## Lo trinh tiep theo

### V0.2 - AI pipeline

- NVIDIA RTX 3060 / CUDA
- YOLO detector
- ByteTrack tracker
- MP4, webcam va RTSP input
- Bounding box + class + confidence + Track ID
- Counting line
- Dem IN/OUT, chong dem trung
- Ghi `vehicle_events` vao PostgreSQL
- Live preview tren dashboard

### V0.3 - Training

- Dataset giao thong Viet Nam
- Fine-tune model
- Precision, Recall, mAP50, mAP50-95
- FPS va counting error
- Quan ly phien train/model trong database

### V0.4 - Bao cao/thong ke

- Theo gio/ngay/camera/loai xe
- Bieu do dashboard
- Export CSV/Excel
- Snapshot su kien


## V0.1.1 - sua loi khoi dong

- Sua Alembic/ConfigParser khi password PostgreSQL co ky tu `@` (URL encoding tao `%40`).
- Danh dau `traffic_ai_postgres_data` la external volume de Compose dung dung volume da tao truoc do.
- Sua kiem tra `hosts` tren PowerShell; truoc day mang dong hosts lam script canh bao sai.
- Them `scripts\diagnose.ps1` de thu thap nhanh trang thai va log.

Thu muc mac dinh cua do an:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
```

## V0.1.2 - CI/CD and GitHub Release automation

This version adds a fail-closed release workflow:

- Local test suite: `scripts/test.ps1`
- GitHub Actions CI on push and pull request
- Python unit tests for Backend and AI Service
- Frontend production build verification
- Docker Compose validation and image builds
- One-time GitHub remote setup: `scripts/github-init.ps1`
- One-command release: `scripts/release.ps1 -Version X.Y.Z`
- Tag-driven GitHub Release with ZIP, TAR.GZ and SHA256SUMS assets

Recommended workflow from the project root (`D:\LienThongDH\DoAn\traffic-ai`):

```powershell
.\scripts\test.ps1
.\scripts\github-init.ps1 -RepositoryUrl "https://github.com/<OWNER>/<REPO>.git"
.\scripts\release.ps1 -Version 0.1.2
```

Before the first release, install/authenticate GitHub CLI:

```powershell
gh auth login
```

The release script runs the local test suite, updates `VERSION` and the frontend package version, commits changes, creates an annotated `vX.Y.Z` tag, pushes `main` plus the tag, then GitHub Actions verifies the tag and creates the GitHub Release automatically.

## GitHub automation (TamNhien)

Repository mac dinh cua project:

```text
https://github.com/TamNhien/traffic-ai
```

De tranh vo tinh cong khai source, script mac dinh tao repository **private**. Neu muon public, truyen `-Visibility public`.

### Dang nhap GitHub CLI mot lan

```powershell
gh auth login
```

Kiem tra tai khoan:

```powershell
gh api user --jq .login
```

Ket qua phai la:

```text
TamNhien
```

### Tu dong tao repo neu chua co va push source

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\push-github.ps1
```

Neu muon repository public ngay tu dau:

```powershell
.\scripts\push-github.ps1 -Visibility public
```

Script se tu:

1. Chay full test.
2. Xac minh `gh` dang dang nhap dung tai khoan `TamNhien`.
3. Tao `TamNhien/traffic-ai` neu repository chua ton tai.
4. Khoi tao Git neu can.
5. Cau hinh `origin`.
6. Chan `.env` va private key TLS neu bi track nham.
7. Commit source.
8. Push branch `main`.

### Tao version + tag + GitHub Release tu dong

Vi du:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\release.ps1 -Version 0.1.3
```

Neu repository chua ton tai, script release cung se tu tao repository truoc khi push.
Sau khi tag `v0.1.3` duoc push, GitHub Actions se:

- test Backend;
- test AI Service;
- build Frontend;
- validate/build Docker images;
- tao release archives;
- tao `SHA256SUMS.txt`;
- tao GitHub Release.

Theo doi workflow:

```powershell
gh run watch
```

## V0.1.3 - test fix + TamNhien GitHub bootstrap

- Sua `PYTHONPATH` cho backend/AI unit test de khong con `ModuleNotFoundError: No module named 'app'`.
- Dong bo GitHub Actions test cung mot cach import voi local test.
- Dong bo hostname development sang `traffic-ai.test` de tranh xung dot `.local`/mDNS.
- `github-init.ps1` tu xac minh tai khoan `TamNhien` va tao `TamNhien/traffic-ai` neu chua co.
- `push-github.ps1` chay test, commit va push source sau khi test xanh.
- `release.ps1` chay test, tu tao repo neu can, commit, tag, push va kich hoat GitHub Release workflow.
- Fail-closed neu `.env` hoac TLS private key bi track nham.
