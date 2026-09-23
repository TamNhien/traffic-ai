# Traffic AI V0.5.5 — best.pt Activation Reliability & UI Spacing

**Đồ án môn Trí tuệ nhân tạo:** Nghiên cứu và xây dựng hệ thống phát hiện, phân loại, theo dõi và đếm phương tiện giao thông qua camera.

> Thư mục làm việc mặc định:
>
> ```powershell
> D:\LienThongDH\DoAn\traffic-ai
> ```

## 1. Mục tiêu V0.5.5

> **Hotfix V0.5.5:** sửa lỗi Backend không khởi động sau khi toàn bộ test đã PASS do Alembic cố ghi revision ID `0017_ai_test_dependency_isolation_v053` dài 38 ký tự vào cột `alembic_version.version_num` mặc định chỉ `VARCHAR(32)`. V0.5.5 rút gọn revision V0.5.3 thành `0017_ai_test_dep_v053`, thêm bước self-heal trước migration để nới cột lên `VARCHAR(128)`, và thêm contract kiểm tra tất cả revision ID không vượt quá 32 ký tự.

> V0.5.3 vẫn giữ nguyên fix lazy import OpenCV/PyYAML cho unit test AI Service; V0.5.5 chỉ harden chuỗi migration/startup, không xóa dữ liệu camera, đếm xe, dataset hay training run.

V0.5.0 chuyển dự án từ giai đoạn chỉ tối ưu **pretrained COCO + runtime** sang giai đoạn **huấn luyện model riêng cho cảnh giao thông Việt Nam**. Đây là bước cần thiết để giảm các nhầm lẫn như:

- xe máy ↔ xe đạp;
- ô tô ↔ xe tải nhẹ;
- xe tải ↔ xe buýt;
- xe nhỏ ở xa;
- xe bị che khuất hoặc đi qua vùng nắng/bóng cây;
- cùng một loại xe nhưng hình dáng khác dữ liệu COCO.

Không có hệ thống camera + AI thực tế nào có thể cam kết **100% chính xác trong mọi tình huống**. V0.5.0 bổ sung quy trình đo lường để biết model đạt bao nhiêu thay vì suy đoán.

Pipeline phát hiện/đếm V0.4.1 vẫn được giữ nguyên:

```text
MP4 / RTSP
    ↓
YOLO26s
    ↓
ByteTrack + Track Continuity
    ↓
Realtime Gate Engine 4.0
    ↓
IN / OUT
    ↓
PostgreSQL 18
```

V0.5.0 bổ sung pipeline huấn luyện:

```text
Video thật từ camera
      ↓
Trích frame
      ↓
Auto-label bằng YOLO26
      ↓
Rà soát/sửa nhãn YOLO
      ↓
Train / Val / Test
      ↓
Fine-tune YOLO26s hoặc YOLO26m
      ↓
Precision / Recall / mAP50 / mAP50-95
      ↓
best.pt
      ↓
Kích hoạt model tùy biến
      ↓
Các phiên đếm mới dùng best.pt
```

## 2. Công nghệ chính

- PostgreSQL **18.6**.
- Python **3.14.7**.
- FastAPI **0.141.1**.
- SQLAlchemy **2.0.54**.
- Alembic **1.20.0**.
- PyTorch **2.14.0**.
- TorchVision **0.29.0**.
- OpenCV Headless **5.0.0.93**.
- Ultralytics **8.4.158**.
- YOLO26s: detector/runtime mặc định.
- YOLO26m: refiner và lựa chọn fine-tune chính xác hơn.
- ByteTrack: tracking.
- React **19.3.0** + Vite **8.3.0**.
- Node.js **26.9.0** + npm **12.1.0**.
- Nginx **1.31.6**.
- Docker Compose + NVIDIA GPU override.

## 3. Cổng và địa chỉ

| Thành phần | Địa chỉ |
|---|---|
| Dashboard | `https://traffic-ai.test:8443` |
| Swagger/API | `https://traffic-ai.test:8444/docs` |
| PostgreSQL host | `127.0.0.1:5445` |
| PostgreSQL Docker | `postgres:5432` |
| Database | `traffic_ai_db` |

## 4. Thư mục dữ liệu mới

V0.5.0 thêm:

```text
datasets/
training-runs/
```

Docker mount vào AI Service:

```text
./datasets      → /data/datasets
./training-runs → /data/training-runs
./models        → /data/models
```

Các thư mục runtime được `.gitignore` để không đẩy hàng GB ảnh/weights lên GitHub.

## 5. Database V0.5.5

Chuỗi migration hiện tại:

```text
0014_dataset_training_v50
        ↓
0015_ui_test_hardening_v051
        ↓
0016_contract_alignment_v052
        ↓
0017_ai_test_dep_v053
        ↓
0018_alembic_guard_v054
```

Migration `0014` tạo các bảng Dataset/Fine-tune; `0015` dọn UI/test harness; `0016` đồng bộ contract Smooth Playback; `0017` đánh dấu hotfix tách dependency unit-test/runtime; `0018` nới `alembic_version.version_num` lên `VARCHAR(128)` trên PostgreSQL và đánh dấu V0.5.5. Các migration hotfix không xóa dữ liệu nghiệp vụ.

`schema_version`:

```text
0.5.4
```

Hai bảng mới:

### `datasets`

Theo dõi:

- tên dataset;
- slug;
- camera/video nguồn;
- đường dẫn dataset;
- số frame;
- số ảnh có nhãn;
- số bounding box;
- số ảnh train/val/test;
- trạng thái dataset.

### `training_runs`

Theo dõi:

- dataset;
- base model;
- epochs;
- image size;
- batch size;
- device;
- epoch hiện tại;
- tiến độ;
- Precision;
- Recall;
- mAP50;
- mAP50-95;
- đường dẫn `best.pt`;
- lỗi training nếu có.

## 6. Dataset Studio trên Dashboard

Mở:

```text
https://traffic-ai.test:8443
```

Menu mới:

```text
Dữ liệu & huấn luyện
```

### Bước 1 — Trích frame

Chọn camera/video đang có, nhập:

```text
Tên dataset
Mỗi N frame
Tối đa số ảnh
```

Ví dụ video 25 FPS:

```text
Mỗi 10 frame
```

sẽ lấy khoảng 2,5 ảnh/giây video.

Bấm:

```text
1. Trích frame
```

Frame được lưu:

```text
datasets/<slug>/raw/images/
```

### Bước 2 — Auto-label

Bấm:

```text
2. Auto-label YOLO26
```

YOLO26 đang active sẽ tạo nhãn gợi ý cho 5 lớp:

```text
0 motorcycle
1 bicycle
2 car
3 bus
4 truck
```

Nhãn lưu tại:

```text
datasets/<slug>/raw/labels/
```

**Quan trọng:** Auto-label chỉ là pseudo-label. Nếu model đang nhầm xe máy thành xe đạp thì pseudo-label cũng có thể nhầm theo. Muốn fine-tune thực sự tốt phải rà soát nhãn.

Có thể mở bộ ảnh/nhãn bằng CVAT, Label Studio, Roboflow hoặc công cụ YOLO annotation khác. Khi sửa nhãn:

- chỉ gán `bicycle` khi phương tiện thực sự là xe đạp/pedal-cycle;
- xe máy/scooter/mô tô phải là `motorcycle`;
- xe tải và xe buýt phải rà soát kỹ ở góc camera hiện tại.

### Bước 3 — Chia train/val/test

Mặc định:

```text
Train = 70%
Val   = 20%
Test  = 10%
Seed  = 2026
```

Bấm:

```text
3. Chia train/val/test
```

Sinh:

```text
datasets/<slug>/images/train
datasets/<slug>/images/val
datasets/<slug>/images/test

datasets/<slug>/labels/train
datasets/<slug>/labels/val
datasets/<slug>/labels/test

datasets/<slug>/dataset.yaml
```

## 7. Fine-tune YOLO26 bằng RTX 3060

Trong Dashboard chọn:

```text
Base model: YOLO26s hoặc YOLO26m
Epochs
Image size
Batch
```

Cấu hình khởi đầu phù hợp RTX 3060:

```text
Base model = yolo26s.pt
Epochs     = 80
Image size = 640
Batch      = 8
Device     = auto
```

Bấm:

```text
4. Bắt đầu fine-tune RTX 3060
```

Training chạy nền trong AI Service. Dashboard theo dõi:

```text
Epoch
Progress
Precision
Recall
mAP50
mAP50-95
```

Kết quả runtime:

```text
training-runs/run-<id>/
```

Weights tốt nhất được tự copy thành:

```text
models/traffic-ai-v050-run-<id>-best.pt
```

## 8. Kích hoạt model tùy biến

Khi training hoàn tất, bấm:

```text
5. Kích hoạt best.pt
```

Backend sẽ:

1. tắt `is_active` của model cũ;
2. tạo bản ghi `AIModel` mới;
3. lưu Precision/Recall/mAP;
4. đặt `best.pt` mới thành model active.

Các phiên `Chạy AI` **sau đó** sẽ dùng model mới. Phiên đang chạy không bị đổi model giữa chừng.

## 9. Chạy và kiểm thử

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\test.ps1
```

Nếu PASS:

```powershell
.\scripts\start.ps1
```

Kiểm tra container:

```powershell
.\scripts\status.ps1
```

Kiểm tra database:

```powershell
.\scripts\verify-database.ps1
```

Revision mong muốn:

```text
0014_dataset_training_v50
```

## 10. Cấu hình training trong `.env`

V0.5.0 tự bổ sung khi thiếu:

```env
AI_DATASET_ROOT=/data/datasets
AI_TRAINING_ROOT=/data/training-runs
AI_TRAIN_BASE_MODEL=yolo26s.pt
AI_TRAIN_EPOCHS=80
AI_TRAIN_IMGSZ=640
AI_TRAIN_BATCH=8
AI_TRAIN_WORKERS=4
AI_TRAIN_PATIENCE=20
AI_TRAIN_CACHE=false
AI_DATASET_SEED=2026
```

Nếu gặp CUDA out-of-memory, giảm:

```text
Batch 8 → 4 → 2
```

Không cần hạ model ngay.

## 11. Lưu ý về độ chính xác

Mục tiêu của fine-tune là **đo và cải thiện có bằng chứng**, không phải tuyên bố 100%.

Ít nhất cần:

- video nhiều thời điểm trong ngày;
- nắng/râm/ban đêm nếu hệ thống sẽ chạy các điều kiện đó;
- xe gần và xa;
- che khuất;
- đủ mẫu xe máy, xe đạp, ô tô, xe buýt, xe tải;
- nhãn đúng và nhất quán.

Một dataset chỉ lấy từ một clip ngắn dễ bị overfit và có thể nhìn rất tốt trên clip đó nhưng kém ở video khác.

## 12. GitHub + Release

Chỉ dùng một lệnh:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\publish.ps1
```

Quy trình:

```text
Test local
→ PASS
→ Commit
→ Push main
→ Tag v0.5.5
→ GitHub Actions
→ ZIP / TAR.GZ / SHA256
→ GitHub Release
```

Repository:

```text
https://github.com/TamNhien/traffic-ai
```

## 13. Lộ trình tiếp theo

### V0.5.5 — Ground-truth Benchmark

- nhập số xe đúng theo từng loại và IN/OUT;
- benchmark cùng một clip với pretrained và `best.pt`;
- confusion matrix;
- Precision/Recall/F1;
- counting MAE/MAPE/accuracy;
- báo cáo so sánh tự động.

### V0.5.6 — Annotation Studio tích hợp

- vẽ/sửa bounding box trực tiếp trên Dashboard;
- hotkey đổi class;
- review pseudo-label;
- đánh dấu ảnh khó;
- kiểm tra class imbalance.

### V0.6.0 — Multi-camera / RTSP Production

- worker độc lập mỗi camera;
- reconnect RTSP;
- watchdog;
- queue backpressure;
- GPU scheduler;
- dashboard nhiều camera.

## 14. Lịch sử phát triển

Các phiên bản được sắp xếp **tăng dần**.

### V0.1.0 — Nền tảng ban đầu
PostgreSQL 18, FastAPI, React/Vite, Nginx HTTPS, Docker Compose.

### V0.1.1 — Ổn định Backend/PostgreSQL
Sửa Alembic, volume PostgreSQL và script chẩn đoán.

### V0.1.2 — CI/CD và test tự động
Thêm `test.ps1`, GitHub Actions và Release workflow.

### V0.1.3 — Tự động hóa GitHub
Tự tạo/push repository `TamNhien/traffic-ai`.

### V0.1.4 — Một lệnh phát hành
README tiếng Việt; `publish.ps1` gom test → push → release.

### V0.2.0 — AI Pipeline đầu tiên
YOLO + ByteTrack + counting line + PostgreSQL.

### V0.2.1 — YOLO26
Chuyển model chính từ YOLO11 sang YOLO26.

### V0.2.2 — HTTPS bootstrap tự động
Tự tạo certificate/hosts/trusted root.

### V0.2.3 — Runtime stability
Tách Backend health và AI health; gia cố migration/startup.

### V0.2.4 — UTF-8
Sửa tiếng Việt hiển thị literal `\\uXXXX`.

### V0.2.5 — CI/source hygiene
Sửa false-positive UTF-8 ở `dist`; Release fallback.

### V0.2.6 — Logo/favicon + Release
Thêm branding và harden GitHub Release.

### V0.2.7 — Counting reliability
Session reset, persistence, crossing reliability, pip/warning cleanup.

### V0.2.8 — Source management
Sửa camera giữ đường dẫn video cũ; probe source trước chạy AI.

### V0.2.9 — Release hygiene
Tự dọn script legacy khi copy source đè.

### V0.3.0 — Smart Gate 2.0
Vạch tương tác, bidirectional counting, track smoothing.

### V0.3.1 — Smart Gate 3.0
Reset bộ đếm theo session, track continuity.

### V0.3.2 — Runtime hardening
PowerShell syntax contract và dependency cleanup.

### V0.3.3 — Gateway DNS runtime
Sửa 502 sau khi container được recreate bằng Docker DNS động.

### V0.4.0 — Realtime Gate Engine 4.0
YOLO26s, YOLO26m refiner, Gate ROI, trajectory crossing rescue, async persistence/stream.

### V0.4.1 — Smooth Playback
Tách native video playback khỏi AI Overlay/MJPEG; thêm progress, realtime factor và lag.

### V0.5.0 — Dataset & Fine-tune Studio
- Trích frame từ video thật.
- Auto-label YOLO26.
- Quản lý dataset trong PostgreSQL.
- Chia train/val/test.
- Fine-tune YOLO26s/YOLO26m bằng RTX 3060.
- Theo dõi Precision/Recall/mAP.
- Xuất và kích hoạt `best.pt`.

### V0.5.1 — UI Counting Line Cleanup & Test Harness Hotfix
- Bỏ hoàn toàn dòng “Nguyên tắc” khỏi khu vực Counting Line.
- Bỏ thanh hướng dẫn kéo vạch phủ trên hình preview.
- Sửa `scripts/test.ps1` bị lỗi parser `Unexpected token '}'` bằng cách khôi phục hàm `Assert-TechnologyVersionsContract`.
- Thêm contract chống hồi quy để hai dòng UI đã bỏ không xuất hiện lại.
- Thêm migration `0015_ui_test_hardening_v051`, cập nhật `schema_version = 0.5.1`.



### V0.5.2 — Smooth Telemetry Contract Alignment
- Sửa false-positive trong `scripts/test.ps1`: contract cũ bắt buộc literal `Smooth Gate 4.1` dù frontend dùng nhãn `Phát mượt` / `AI Overlay`.
- Contract mới kiểm tra capability thực: `realtime_factor`, `playback_lag_seconds`, `RT x`, `lag`, `Phát mượt`, `AI Overlay`.
- Thêm regression check để tránh quay lại test phụ thuộc text trình bày.
- Thêm migration `0016_contract_alignment_v052`, cập nhật `schema_version = 0.5.2`.

### V0.5.3 — AI Test Dependency Isolation
- Sửa pytest collection của AI Service bị `ModuleNotFoundError: No module named 'cv2'`.
- Chuyển `cv2` và `yaml` trong `app.training` sang lazy import tại đúng chức năng cần dùng.
- Giữ `requirements-test.txt` nhẹ; không bắt unit-test container tải OpenCV/Torch/Ultralytics.
- Thêm contract chống hồi quy để cấm import OpenCV/PyYAML ở module scope của `app.training`.
- Revision thực tế của migration V0.5.3 được rút gọn thành `0017_ai_test_dep_v053` để tương thích giới hạn 32 ký tự của Alembic mặc định.
- Cập nhật `schema_version = 0.5.3`.

### V0.5.5 — Alembic Revision Guard
- Sửa lỗi `StringDataRightTruncation: value too long for type character varying(32)` khi Backend chạy `alembic upgrade head`.
- Rút gọn revision ID V0.5.3 từ 38 ký tự xuống `0017_ai_test_dep_v053`.
- Thêm `0018_alembic_guard_v054`, cập nhật `schema_version = 0.5.4`.
- Backend tự nới `alembic_version.version_num` lên `VARCHAR(128)` trước khi chạy Alembic và tự map revision ID V0.5.3 cũ nếu môi trường nào đã từng lưu được ID dài.
- `test.ps1` kiểm tra toàn bộ revision ID không vượt 32 ký tự để ngăn lỗi startup tương tự quay lại.



### V0.5.5 — Kích hoạt best.pt ổn định + tách khung giao diện

- Sửa nút **Kích hoạt best.pt**: activation idempotent, bấm lại không tạo model trùng và không còn lỗi `Internal Server Error` do unique constraint.
- Frontend đọc lỗi API an toàn: nếu proxy/backend trả text thay vì JSON sẽ hiện đúng nội dung lỗi, không còn `Unexpected token ... is not valid JSON`.
- Training run đang được dùng hiển thị badge **✓ ĐANG DÙNG best.pt**.
- Tách khoảng cách giữa khối Dataset/Fine-tune và Lịch sử PostgreSQL/Phiên chạy để các panel không dính sát nhau.
- Thêm migration `0019_activation_ui_v055`, `schema_version = 0.5.5`.
