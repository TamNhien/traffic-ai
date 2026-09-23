# Traffic AI V0.4.0 — Realtime Gate Engine 4.0

**Đồ án môn Trí tuệ nhân tạo:** Nghiên cứu và xây dựng hệ thống phát hiện, nhận diện, theo dõi và đếm phương tiện giao thông qua camera.

> Thư mục làm việc mặc định:
>
> ```powershell
> D:\LienThongDH\DoAn\traffic-ai
> ```

## 1. Mục tiêu của V0.4.0

V0.4.0 tập trung vào hai vấn đề thực tế của các bản V0.3.x:

- xe chạy nhanh hoặc mất Track ID ngắn hạn đi qua vạch nhưng không được đếm;
- video/clip có lúc khựng do encode MJPEG, ghi PostgreSQL hoặc load model tinh chỉnh ngay trong vòng lặp inference;
- YOLO pretrained còn nhầm `motorcycle ↔ bicycle`, `car ↔ truck ↔ bus` ở góc camera từ trên cao.

Pipeline mới:

```text
Video / RTSP / Camera
        ↓
Gate-focused ROI
        ↓
YOLO26s detector
        ↓
ByteTrack traffic profile
        ↓
Track Continuity Resolver
        ↓
Motion-leading anchor
        ↓
Trajectory Gate 4.0
        ↓
IN / OUT crossing
        ↓
YOLO26m crossing refiner (khi cần)
        ↓
VehicleClassPolicy
        ↓
Async PostgreSQL event writer
        ↓
PostgreSQL 18
```

### Không cam kết “100%”

Không hệ thống camera/AI thực tế nào có thể bảo đảm chính xác 100% trong mọi điều kiện: che khuất, bóng tối, mưa, ngược sáng, xe chồng lấn, camera rung và góc nhìn đều có thể gây lỗi. V0.4.0 giảm lỗi runtime và tạo nền tảng để đo sai số. Muốn tiến gần mức 98–99% trên **chính camera triển khai**, lộ trình V0.5.x phải dùng dataset giao thông Việt Nam được gán nhãn và fine-tune riêng; nếu yêu cầu gần tuyệt đối trong vận hành thật nên kết hợp thêm cảm biến vật lý.

## 2. Điểm mới V0.4.0

### 2.1. Detector chính chuyển YOLO26n → YOLO26s

- Model realtime mặc định: `yolo26s.pt`.
- `YOLO26n` vẫn giữ trong bảng `ai_models` để đối chứng.
- Model tinh chỉnh tại vạch: `yolo26m.pt`.
- Confidence mặc định camera mới: `0.18`.
- Chỉ các camera còn đúng default cũ `0.20` mới được migration tự hạ xuống `0.18`; giá trị người dùng đã tự chỉnh không bị ghi đè.

### 2.2. Gate-focused ROI

AI không còn dành toàn bộ độ phân giải model cho toàn khung hình. Một vùng quan tâm lớn bao quanh vạch đếm được cắt ra trước khi inference. Điều này:

- tăng kích thước tương đối của xe khi đi gần vạch;
- giảm nhiễu từ xe đỗ/vỉa hè ngoài vùng đếm;
- dùng tài nguyên GPU tập trung cho vùng thực sự quyết định kết quả đếm.

Cấu hình:

```env
AI_GATE_ROI=1
AI_GATE_ROI_MARGIN=0.22
AI_GATE_ROI_MIN_SPAN=0.52
```

### 2.3. Motion-leading anchor

Bản cũ dùng bottom-center cho mọi hướng xe. V0.4.0 chọn mép dẫn đầu theo vector chuyển động:

```text
xe ↓  → bottom-center
xe ↑  → top-center
xe →  → right-center
xe ←  → left-center
```

Do đó xe hai chiều cắt cùng một vạch được phát hiện nhất quán hơn.

### 2.4. Trajectory Gate 4.0

Counter giữ lịch sử trajectory tối đa nhiều frame thay vì chỉ dựa vào hai quan sát gần nhau. Nếu detector/tracker mất xe ngắn hạn:

```text
frame 100: xe ở phía A
frame 101..106: mất detection
frame 107: xe xuất hiện phía B
```

V0.4.0 kiểm tra toàn đoạn quỹ đạo A → B có cắt **đoạn vạch hữu hạn** hay không. Nếu có và chuyển động đủ vuông góc với vạch, xe vẫn được đếm.

Chỉ phương tiện thực sự đi từ một phía sang phía còn lại mới tăng bộ đếm.

### 2.5. Không để persistence làm đứng clip

Ghi `vehicle_events` sang Backend/PostgreSQL chạy trên `EventDispatcher` riêng. Vòng lặp YOLO không chờ HTTP retry.

```text
Inference thread ──> queue ──> EventDispatcher ──> Backend ──> PostgreSQL
```

### 2.6. Encode MJPEG bất đồng bộ

OpenCV resize/JPEG encode chuyển sang `LatestFrameEncoder` riêng. Nếu browser chậm, hệ thống bỏ **frame hiển thị cũ** nhưng không bỏ frame inference của video local.

Video local dùng:

```text
frame_policy = all-frames
```

Nghĩa là mọi frame vẫn đi qua detector/tracker/counter; chỉ luồng xem trước có thể bỏ frame để giao diện không kéo chậm AI.

### 2.7. Preload model tinh chỉnh

`yolo26m.pt` được load/warm-up trước khi video bắt đầu. Không còn tình trạng xe đầu tiên cắt vạch mới bắt đầu load model lớn làm clip đứng vài giây.

### 2.8. Xe đạp được phân loại bảo thủ

Với camera giao thông, false-positive `bicycle` rất dễ xảy ra. V0.4.0 chỉ chấp nhận **Xe đạp** khi có đồng thời:

- nhiều frame liên tiếp ủng hộ `bicycle`;
- độ chắc chắn temporal đủ cao;
- model refine tại crossing cũng nhận `bicycle` đủ confidence.

Nếu hai bánh còn mơ hồ, hệ thống mặc định về **Xe máy** thay vì ghi nhầm Xe đạp.

> Đây là rule giảm false bicycle, không phải nhận biết trực tiếp động tác “đạp chân”. Để xác định xe đạp/xe máy thật sự ở mọi góc camera cần fine-tune dataset riêng trong V0.5.x.

### 2.9. Bus / truck / car

Khi track có nhãn chưa ổn định, YOLO26m kiểm tra lại crop của chiếc xe tại thời điểm crossing. Kết quả được kết hợp với temporal history trước khi ghi PostgreSQL.

## 3. Cấu hình AI mặc định

```env
AI_MODEL_NAME=yolo26s.pt
AI_IMGSZ=640
AI_PROCESS_MAX_WIDTH=1440
AI_IOU=0.55
AI_CLASS_HISTORY=30

AI_STITCH_MAX_GAP=30
AI_STITCH_DISTANCE_RATIO=0.14
AI_GATE_HISTORY_GAP=30
AI_GATE_MIN_NORMAL_RATIO=0.12

AI_GATE_ROI=1
AI_GATE_ROI_MARGIN=0.22
AI_GATE_ROI_MIN_SPAN=0.52

AI_REFINE_AT_CROSSING=1
AI_REFINE_MODEL_NAME=yolo26m.pt
AI_REFINE_IMGSZ=640
AI_BICYCLE_CERTAINTY=0.76
AI_BICYCLE_MIN_HITS=4
AI_WARMUP=1

AI_STREAM_EVERY_N=2
AI_STREAM_MAX_WIDTH=960
AI_JPEG_QUALITY=70
```

ByteTrack:

```yaml
track_high_thresh: 0.16
track_low_thresh: 0.03
new_track_thresh: 0.18
track_buffer: 120
match_thresh: 0.90
fuse_score: true
```

## 4. Cổng dịch vụ

| Thành phần | Địa chỉ |
|---|---|
| Dashboard | `https://traffic-ai.test:8443` |
| API / Swagger | `https://traffic-ai.test:8444/docs` |
| PostgreSQL host | `127.0.0.1:5445` |
| Database | `traffic_ai_db` |

## 5. Database

Migration mới:

```text
0012_realtime_gate_v4
```

Sau migration:

```text
schema_version = 0.4.0
YOLO26s COCO = active
YOLO26n COCO = giữ lại để so sánh
```

Không xóa lịch sử camera, session, event hay `traffic_ai_postgres_data`.

## 6. Cập nhật từ V0.3.x

Chép full source V0.4.0 đè vào:

```text
D:\LienThongDH\DoAn\traffic-ai
```

Giữ lại dữ liệu local:

```text
.env
gateway\certs\
videos\
models\
snapshots\
```

Không chạy:

```powershell
docker compose down -v
```

`start.ps1` sẽ tự nâng các default cũ nếu chúng vẫn còn nguyên giá trị mặc định, ví dụ:

```text
yolo26n.pt  → yolo26s.pt
832         → 640 (AI_IMGSZ)
1152        → 1440 (PROCESS_MAX_WIDTH)
24          → 30  (CLASS_HISTORY)
18          → 30  (STITCH_MAX_GAP)
0.085       → 0.14 (STITCH_DISTANCE_RATIO)
yolo26s.pt  → yolo26m.pt (refiner)
```

Custom model như `best.pt` không bị đổi.

## 7. Kiểm thử và chạy

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\test.ps1
```

Nếu PASS:

```powershell
.\scripts\start.ps1
```

Kiểm tra trạng thái:

```powershell
.\scripts\status.ps1
```

Kiểm tra database:

```powershell
.\scripts\verify-database.ps1
```

## 8. Cách đọc hiệu năng trên Dashboard

Khi chạy AI, Dashboard hiện dạng:

```text
FPS 22.8/25 · RT x0.91 · 31 ms · Tổng 12 · IN 8 · OUT 4 · cứu 3
```

Ý nghĩa:

- `22.8/25`: FPS xử lý / FPS nguồn;
- `RT x0.91`: tốc độ xử lý bằng 91% realtime;
- `31 ms`: thời gian inference gần nhất;
- `cứu 3`: 3 crossing được Trajectory Gate cứu qua khoảng mất detection/track ngắn.

Với video local, dù `RT < 1`, engine vẫn xử lý **mọi frame**. Clip có thể phát trên browser chậm hơn realtime nhưng không được phép bỏ frame inference.

## 9. Vạch đếm

Vạch phải **vuông góc với hướng xe chạy** và nằm trên phần đường xe thực sự đi qua.

```text
Hướng xe ↑/↓  → vạch gần ngang ──────────
Hướng xe ←/→  → vạch gần dọc  │
```

Khi AI đang chạy, frontend và backend đều khóa thay đổi vạch. Dừng AI trước khi chỉnh.

## 10. Publish GitHub + Release

Lệnh duy nhất:

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
→ Tag v0.4.0
→ GitHub Actions
→ ZIP / TAR.GZ / SHA256
→ GitHub Release
```

Repository mặc định:

```text
https://github.com/TamNhien/traffic-ai
```

## 11. Lộ trình tiếp theo

### V0.5.0 — Dataset giao thông Việt Nam + Fine-tune

Đây là bước bắt buộc nếu mục tiêu là tăng độ chính xác phân loại, đặc biệt:

- xe máy ↔ xe đạp;
- ô tô ↔ xe tải nhẹ;
- xe tải ↔ xe buýt;
- xe ở xa / nhỏ;
- xe bị che khuất.

Dự kiến:

```text
Thu thập frame từ camera thật
→ gán nhãn
→ chia train/val/test
→ fine-tune YOLO26s/m
→ Precision / Recall / mAP
→ benchmark counting error
→ model best.pt
→ lưu metadata training vào PostgreSQL
```

### V0.5.1 — Ground-truth benchmark

- nhập số xe đúng theo từng loại và IN/OUT;
- chạy clip tự động;
- sinh báo cáo sai số đếm;
- confusion matrix;
- counting accuracy, precision, recall;
- so sánh `YOLO26 pretrained` và `best.pt`.

### V0.6.0 — Multi-camera / RTSP production

- worker riêng theo camera;
- watchdog/reconnect RTSP;
- queue backpressure;
- GPU scheduler;
- dashboard nhiều camera.

## 12. Lịch sử phát triển

Các phiên bản được sắp xếp tăng dần:

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
Sửa tiếng Việt hiển thị literal `\uXXXX`.

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
Reset bộ đếm theo session, track continuity, async stream giảm tải ban đầu.

### V0.3.2 — Runtime hardening
PowerShell syntax contract, dependency warning cleanup.

### V0.3.3 — Gateway DNS runtime
Sửa 502 sau khi container được recreate bằng Docker DNS động.

### V0.4.0 — Realtime Gate Engine 4.0
- YOLO26s detector + YOLO26m crossing refiner.
- Gate-focused ROI.
- Motion-leading anchor.
- Trajectory-history crossing rescue.
- Async PostgreSQL event writer.
- Async MJPEG encoder.
- Preload/warm-up refiner trước playback.
- Bicycle policy bảo thủ để giảm xe máy bị đếm thành xe đạp.
- Metrics `source FPS / processing FPS / realtime factor / rescued crossings`.
