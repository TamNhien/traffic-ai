# Traffic AI V0.5.21 — Ground-truth Error Analyzer + Crossing Engine 7.0 🎯🚗

V0.5.21 dùng trực tiếp Ground-truth Benchmark để xử lý hai vấn đề còn lại: **nút “Đối chiếu lại” không có phản hồi nhìn thấy được** và **Crossing Engine còn overcount / lọt xe**.

## Điểm mới chính

### 1. `Đối chiếu lại` giờ là một hành động thật

Frontend gọi endpoint riêng:

```text
POST /api/benchmarks/{id}/reconcile
```

Nút chuyển trạng thái:

```text
Đối chiếu lại
      ↓
Đang đối chiếu…
      ↓
Đã đối chiếu lại lúc HH:mm:ss
```

Nếu số liệu không đổi, giao diện nói rõ:

```text
Kết quả không đổi: khớp ..., lọt ..., dư ...
```

Không còn trường hợp bấm nút nhưng không biết hệ thống có chạy hay không.

### 2. Ground-truth Auto Error Analyzer cho `AI đếm dư`

Mỗi false-positive event được phân tích theo timecode, tracking ID và crossing method. Report có thể gắn các nhãn chẩn đoán:

```text
Event giả lúc khởi tạo clip
Cùng track đảo IN/OUT quá nhanh
Cùng track phát event lặp
Event dư nằm sát một GT đã khớp
Rescue qua gap nhưng GT không có
Nội suy qua vạch nhưng GT không có
Direct crossing nhưng GT không có
```

Đây là **chẩn đoán**, không thay Ground Truth. GT do người dùng đánh dấu vẫn là chuẩn để xác định xe có thật sự cắt vạch hay không.

### 3. Crossing Engine 7.0 giảm overcount

Runtime mặc định mới:

```env
AI_GATE_STARTUP_GRACE_FRAMES=12
AI_GATE_SIDE_CONFIRM_SAMPLES=2
AI_GATE_COOLDOWN_FRAMES=60
AI_ROAD_ANCHOR_MARGIN_RATIO=0.012
```

Luồng đếm mới:

```text
Track đi tới vạch
   ↓
không tính crossing trong 12 frame đầu clip
   ↓
trajectory thật sự đổi phía vạch
   ↓
phải có thêm observation xác nhận ở phía mới
   ↓
không được lặp crossing cùng canonical track trong cooldown
   ↓
Road Zone corridor vẫn strict
   ↓
COUNT
```

Mục tiêu là giảm các event kiểu:

```text
IN → OUT → IN
```

trong vài frame do jitter / ID instability.

### 4. Road Zone edge tolerance chỉ cứu sai số anchor nhỏ

Road Guard trước đây yêu cầu cả hai observed anchor phải nằm tuyệt đối trong polygon. V0.5.21 cho phép **chỉ observed anchor** lệch ra mép Road Zone một khoảng rất nhỏ (`0.012` cạnh ngắn frame), trong khi:

```text
crossing point
probe trước crossing
probe sau crossing
```

vẫn bắt buộc nằm **strict** trong Road Zone.

Do đó mục tiêu là cứu các GT bị `Road Zone reject` vì leading-edge anchor lệch vài pixel, nhưng không mở cửa cho xe chạy ngoài lề.

### 5. Backend chống rapid direction-flip lần hai

Ngay cả khi runtime gửi lại event do bất ổn, backend còn có lớp idempotency bổ sung cho cùng canonical `tracking_id` trong cửa sổ ngắn theo frame/timecode.

### 6. Không phải đánh lại 149 Ground Truth

Sau khi chạy V0.5.21 thành một Session mới với **cùng clip + cùng vạch**, Benchmark Studio hiện nút:

```text
Sao chép 149 GT sang Session #...
```

Backend chỉ cho sao chép khi nguồn video và vạch đếm khớp benchmark nguồn. Nhờ vậy bạn có thể dùng đúng 149 mốc GT đã đánh để so V0.5.20 ↔ V0.5.21, không phải xem lại 15 phút clip và bấm I/O lần nữa.

---

# Database V0.5.21

Migration:

```text
0034_benchmark_overlay_v0520
        ↓
0035_crossing_v0521
```

Schema:

```text
schema_version = 0.5.21
```

Migration này không xóa bảng/dữ liệu và không đụng:

```text
Dataset #4
Ground Truth Benchmark hiện có
Run #3
best.pt
vehicle_events cũ
counting_sessions cũ
```

---

# Cập nhật trên máy

Chép full source đè vào:

```text
D:\LienThongDH\DoAn\traffic-ai
```

Giữ nguyên:

```text
.env
gateway\certs\
videos\
models\
snapshots\
datasets\
training-runs\
```

Không dùng:

```powershell
docker compose down -v
```

Nếu Windows đánh dấu file PowerShell từ ZIP:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
```

Sau đó:

```powershell
.\scripts\test.ps1
```

Mong muốn có:

```text
[Traffic AI] Crossing Engine 7.0 + Benchmark Reconcile V0.5.21
[OK] Crossing Engine 7.0 + Benchmark Reconcile V0.5.21
```

Nếu PASS:

```powershell
.\scripts\start.ps1
```

Database:

```powershell
.\scripts\verify-database.ps1
```

mong muốn:

```text
0035_crossing_v0521
schema_version = 0.5.21
```

Sau đó `Ctrl + F5` trên trình duyệt.

---

# Kiểm thử V0.5.21

```text
Python compile                         PASS
Backend unit tests                    15/15 PASS
AI Service unit tests                 66/66 PASS
Crossing Engine 7.0 regression        PASS
Ground-truth false-positive analyzer  PASS
Benchmark reconcile endpoint          PASS
Ground Truth clone contract           PASS
Alembic single head                   PASS
head = 0035_crossing_v0521            PASS
Revision ID <= 32 chars               PASS
Sensitive/runtime artifact scan       PASS
```

Môi trường đóng gói hiện tại không có đúng Node 26.10/Docker Desktop của máy đích, nên vòng `Vite build + Docker full-suite` vẫn do `./scripts/test.ps1` trên máy Windows của bạn xác nhận. Backend tests ở môi trường đóng gói dùng SQLite và temporary `httpx2 -> httpx` compatibility shim; source thật không đổi dependency của dự án.


# Benchmark sau khi nâng

Benchmark cũ vẫn được giữ để xem kết quả V0.5.20. Để đo hiệu quả Crossing Engine 7.0, hãy chạy lại **đúng clip + đúng vạch + đúng Road Zone** thành một Session mới rồi tạo Benchmark mới. Ground Truth cũ có thể dùng làm mốc tham chiếu, nhưng event AI của session mới phải được đối chiếu với session mới.

Mục tiêu không phải làm tổng AI “gần 149” bằng cách ép số, mà là đồng thời:

```text
missed ↓
false positive ↓
Recall ↑
Precision ↑
F1 ↑
```

---

# Phát hành vẫn một lệnh

```powershell
.\scripts\publish.ps1
```

```text
→ test
→ build
→ push GitHub
→ tag v0.5.21
→ GitHub Actions
→ Release
```

---

# Lịch sử trước V0.5.21

# Traffic AI V0.5.20 — Benchmark Gate Overlay + IN/OUT 🎯🛣️

V0.5.20 sửa blocker của Ground-truth Benchmark: **video benchmark phải hiển thị đúng vạch đếm, Road Zone và hướng IN/OUT**, nếu không người dùng không thể biết lúc nào xe thực sự cắt vạch để đánh dấu GT.

Điểm mới:

- benchmark lưu snapshot `line_x1/y1/x2/y2` và 4 điểm Road Zone khi tạo;
- benchmark cũ V0.5.19 được backfill geometry từ camera hiện tại khi migrate;
- video benchmark vẽ trực tiếp **Road Zone xanh + vạch vàng + mũi tên IN/OUT**;
- hướng IN/OUT dùng đúng cùng quy ước `signed_side()` của Counting Engine, không phải mũi tên minh họa đoán tay;
- geometry đã snapshot không đổi nếu sau này bạn chỉnh camera;
- video không còn ép khung 16:9 để overlay lệch trên nguồn khác tỉ lệ.

```text
          IN
          ↓
   ┌───────────────┐
   │   ROAD ZONE   │
   │               │
   │ ===== VẠCH ===│
   │               │
   └───────────────┘
          ↑
         OUT
```

Khi benchmark, chỉ bấm `I` hoặc `O` lúc **tâm/quỹ đạo xe thật sự cắt đúng vạch vàng đang hiển thị trên video**.

---

## Nền tảng từ V0.5.19

V0.5.19 tiếp tục từ V0.5.18 và tập trung vào vấn đề còn lại: **AI vẫn lọt một số xe không đếm được nhưng nhìn tổng cuối clip không biết xe nào bị lọt và bị lọt ở tầng nào**.

Bản này không tiếp tục chỉnh confidence/tracker một cách đoán mò. Nó thêm một quy trình benchmark có ground truth theo **timecode của chính video** để đo chính xác:

- xe thật sự cắt vạch bao nhiêu;
- AI đếm bao nhiêu;
- xe nào khớp;
- xe nào **lọt không đếm**;
- event nào **đếm dư**;
- Counting Precision / Recall / F1;
- sai class và sai hướng;
- nguyên nhân xe lọt nằm ở detector, ByteTrack, Road Zone hay Crossing Gate.

---

## Kiến trúc benchmark mới

```text
Video gốc
   ↓
Chạy AI V0.5.19
   ↓
Mỗi event lưu:
- source_frame_index
- source_time_seconds
- crossing_method
   ↓
Frame trace của toàn phiên:
DET / track / road / crossing / reject
   ↓
GROUND-TRUTH BENCHMARK
   ↓
Người dùng xem lại chính clip
và đánh dấu từng xe thật cắt vạch
   ↓
GT timecode ↔ AI event timecode
   ↓
Matched / Missed / False positive
   ↓
Precision / Recall / F1
   ↓
Phân loại nguyên nhân xe lọt
```

---

## Vì sao phiên cũ 191 xe chưa dùng để tìm chính xác xe lọt?

Phiên trong V0.5.18 có thể đã lưu 191 `vehicle_events`, nhưng các event cũ chưa có:

```text
source_time_seconds
source_frame_index
crossing_method
```

V0.5.19 **không tự ước lượng timecode từ đồng hồ hệ thống**, vì warm-up CUDA/video pacing có thể làm lệch thời gian và biến benchmark thành số liệu giả.

Vì vậy sau khi nâng V0.5.19, hãy **chạy lại clip một lần**. Phiên mới sẽ có timecode chuẩn để đối chiếu.

---

# Ground-truth Counting Benchmark Studio

Sidebar có thêm:

```text
Benchmark
```

Panel mới:

```text
GROUND-TRUTH COUNTING BENCHMARK
Đánh dấu xe thật cắt vạch trên chính clip
```

Quy trình:

```text
1. Chạy clip bằng AI đến hết
2. Chọn session vừa hoàn tất
3. Tạo benchmark
4. Xem lại video ở 0.5×
5. Mỗi xe thật sự cắt vạch:
   I = IN
   O = OUT
6. Đối chiếu report
```

### Phím nhanh

```text
I   → đánh dấu IN
O   → đánh dấu OUT
[   → lùi 1 frame
]   → tiến 1 frame
```

Class được chọn bằng combobox:

```text
Xe máy
Xe đạp
Ô tô
Xe buýt
Xe tải
Khác
```

Mặc định video benchmark phát ở **0.5×**, phù hợp clip có khoảng 190–200 xe mà không cần click nút cho từng frame.

---

# Báo cáo benchmark

Report hiển thị:

```text
Ground truth
AI đếm
Khớp
Lọt không đếm
Đếm dư
Sai số tổng

Counting Recall
Counting Precision
F1
Class accuracy
```

Ví dụ:

```text
GT            200
AI            191
Matched       188
Missed         12
False positive  3

Recall      94.0%
Precision   98.4%
```

Điểm quan trọng là **sai số tổng -9 không che mất thực tế có 12 xe lọt và 3 xe đếm dư**.

---

# Click đúng xe bị lọt

Danh sách:

```text
Lọt không đếm
00:14.320 · IN · Xe máy
00:27.080 · OUT · Xe máy
...
```

Click timecode sẽ đưa video benchmark thẳng tới đúng thời điểm đó để kiểm tra bằng mắt.

Danh sách `AI đếm dư` hoạt động tương tự.

---

# V0.5.19 tự phân loại nguyên nhân xe lọt

Trong lúc chạy video, AI Service ghi một JSONL trace nhẹ theo từng frame vào:

```text
snapshots/benchmark-traces/session_<id>.jsonl
```

Nó chỉ lưu telemetry số, không lưu thêm video:

```text
frame
source time
DET
track
road track
crossing event
total count
road rejects
segment rejects
```

Khi một Ground Truth không tìm thấy AI event gần timecode, hệ thống xem telemetry xung quanh thời điểm đó và phân loại:

### `Detector không thấy xe`

```text
DET = 0
```

→ vấn đề model/confidence/imgsz/dataset.

### `YOLO thấy nhưng ByteTrack mất ID`

```text
DET > 0
track = 0
```

→ vấn đề tracking.

### `Track bị Road Zone loại`

```text
track > 0
road = 0
```

hoặc road reject tăng.

→ vùng lòng đường quá hẹp/sai vị trí.

### `Track trong đường nhưng Crossing Gate không phát event`

```text
DET > 0
track > 0
road > 0
nhưng không crossing
```

→ tập trung sửa Strict Gate/Crossing Engine thay vì detector.

Report còn tổng hợp **nguyên nhân lọt nổi bật**, để bản nâng cấp kế tiếp sửa đúng tầng gây lỗi nhiều nhất.

---

# Timecode chính xác của AI event

`vehicle_events` có thêm:

```text
source_frame_index
source_time_seconds
crossing_method
```

Ví dụ:

```text
source_frame_index = 7312
source_time_seconds = 292.4400
crossing_method = interpolated
```

Ground truth và AI được ghép one-to-one bằng timecode, mặc định:

```text
±0.75 giây
```

Bạn có thể chỉnh từ UI. Sai class hoặc sai hướng được đánh giá **riêng** với counting match, tránh biến một xe đã đếm nhưng sai class thành “1 missed + 1 false positive”.

---

# Database V0.5.19

Migration:

```text
0032_crossing_engine_v0518
        ↓
0033_ground_truth_v0519
```

Schema:

```text
schema_version = 0.5.19
```

Thêm hai bảng:

```text
counting_benchmarks
ground_truth_crossings
```

`counting_sessions` thêm:

```text
source_url
source_fps
source_duration_seconds
```

`vehicle_events` thêm:

```text
source_frame_index
source_time_seconds
crossing_method
```

Không xóa:

```text
Dataset #4
annotations
Run #3
best.pt
models/
training-runs/
vehicle_events cũ
counting_sessions cũ
```

---

# Lưu ý với session V0.5.18 trở về trước

Nếu chọn session cũ, UI sẽ báo:

```text
⚠ Phiên cũ thiếu timecode
191 event được tạo trước V0.5.19 nên không thể ghép chính xác.
Hãy chạy lại clip một lần trên V0.5.19 rồi benchmark session mới.
```

Đây là fail-closed có chủ ý; hệ thống không tạo benchmark “chính xác giả”.

---

# Cập nhật trên máy

Chép full source V0.5.20 đè vào:

```text
D:\LienThongDH\DoAn\traffic-ai
```

Giữ nguyên:

```text
.env
gateway\certs\
videos\
models\
snapshots\
datasets\
training-runs\
```

Không dùng:

```powershell
docker compose down -v
```

Nếu Windows đánh dấu `.ps1` từ ZIP là file Internet:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
```

Sau đó:

```powershell
.\scripts\test.ps1
```

Mong muốn có:

```text
[Traffic AI] Ground-truth Counting Benchmark V0.5.19
[OK] Ground-truth Counting Benchmark V0.5.19

[Traffic AI] Benchmark gate overlay + IN/OUT V0.5.20
[OK] Benchmark gate overlay + IN/OUT V0.5.20
```

Nếu PASS:

```powershell
.\scripts\start.ps1
```

Database:

```powershell
.\scripts\verify-database.ps1
```

mong muốn:

```text
0034_benchmark_overlay_v0520
schema_version = 0.5.20
```

Trình duyệt:

```text
Ctrl + F5
```

---

# Quy trình benchmark cho clip hiện tại

Sau khi nâng source:

```text
1. Chạy AI
2. Để clip chạy hết
3. Không đổi vạch/Road Zone giữa phiên
4. Vào Benchmark
5. Chọn session vừa hoàn tất
6. Tạo benchmark
7. Phát lại ở 0.5×
8. Nhấn I/O mỗi lần xe thật cắt vạch
9. Đối chiếu
```

Khi report có `Lọt không đếm`, click từng timecode. Hệ thống sẽ đồng thời cho biết tầng nghi ngờ:

```text
Detector
Tracker
Road Zone
Crossing Gate
```

Đây sẽ là dữ liệu đầu vào để fix tiếp, thay vì tiếp tục hạ confidence hoặc thay tracker khi chưa biết nguyên nhân thật.

---

# Kiểm thử đã thực hiện

```text
Python compile                         PASS
AI Service tests                      62/62 PASS
Backend tests                         11/11 PASS
Benchmark matching                    PASS
Benchmark API create/mark/report       PASS
Missed / false-positive matching      PASS
Class mismatch separated from count   PASS
Tolerance boundary                    PASS
Benchmark trace diagnosis             PASS
Detector miss diagnosis               PASS
Tracker miss diagnosis                PASS
Road Zone reject diagnosis            PASS
Crossing Gate miss diagnosis          PASS
SQLite ORM create_all                 PASS
New benchmark tables                  PASS
Event source-time columns             PASS
JSX parse/transpile                   PASS
Alembic single head                   PASS
head = 0033_ground_truth_v0519        PASS
Alembic revision <= 32 chars          PASS
```

Môi trường đóng gói hiện tại không có Docker Desktop/PowerShell và `npm install` bị timeout mạng, nên frontend Vite + Docker full-suite vẫn do `./scripts/test.ps1` trên máy của bạn xác nhận. Backend/AI tests ở môi trường đóng gói dùng temporary `httpx2 -> httpx` compatibility shim; source thật vẫn giữ dependency của dự án.

---

# Phát hành vẫn một lệnh

Sau khi chạy ổn:

```powershell
.\scripts\publish.ps1
```

```text
→ test
→ build
→ push GitHub
→ tag v0.5.20
→ GitHub Actions
→ Release
```


## V0.5.19-R1 — Benchmark responsive UI hotfix

- Sửa hàng `Phiên AI / Tạo benchmark / Benchmark` bị tràn sang panel `Benchmark Report` khi card bên trái hẹp hoặc trình duyệt đang zoom.
- `Benchmark` selector tự xuống một hàng riêng trên desktop hẹp; ở viewport nhỏ toàn bộ control xếp dọc.
- `select` dùng `min-width: 0`, `max-width: 100%` và `box-sizing: border-box` để không vượt chiều rộng card.
- Hai panel benchmark dùng `overflow: hidden` như lớp bảo vệ cuối, nhưng control vẫn được bố trí lại thay vì chỉ cắt phần tràn.
- Không đổi database, migration, AI, dataset, `best.pt` hay logic benchmark. Runtime vẫn là `0.5.19`.


## V0.5.20 — Benchmark Gate Overlay

- Lưu snapshot vạch đếm + Road Zone vào `counting_benchmarks`.
- Migration `0034_benchmark_overlay_v0520` backfill benchmark đã tạo trước đó bằng geometry camera hiện tại.
- Video Benchmark vẽ vạch vàng, vùng xanh và mũi tên `IN` / `OUT`.
- `IN` là hướng từ phía signed-side âm sang signed-side dương của vạch; `OUT` là chiều ngược lại, đúng cùng logic với `ai-service/app/counting.py`.
- Dùng `I` / `O` để đánh GT sau khi nhìn xe cắt đúng vạch hiển thị.
