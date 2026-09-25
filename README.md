# V0.5.23-R1 — Legacy test contract hotfix

Bản R1 không đổi AI runtime, database, model, dataset hay migration. Hotfix chỉ sửa `scripts/test.ps1` để các contract legacy kiểm tra **ý nghĩa tương thích** thay vì bắt cứng chuỗi giao diện của engine cũ.

- V0.5.18 không còn bắt buộc literal `Crossing Engine 6.0`; V0.5.23 đang dùng Crossing Engine 7.1 nhưng vẫn phải giữ `Tổng lượt cắt vạch`, `Trực tiếp`, `Nội suy` và `rescued_crossings`.
- V0.5.21 chấp nhận workflow tái sử dụng GT mới `Sao chép ... GT từ Benchmark ...`, thay cho wording cũ `... sang Session`.
- thêm contract `Legacy semantic contract compatibility V0.5.23-R1` để ngăn regression tương tự ở các bản sau.

Lỗi được sửa:

```text
[Traffic AI] Crossing Engine 6.0 V0.5.18
Frontend thiếu tổng xe hoặc breakdown crossing V0.5.18.
```

Đây là **false-fail của test legacy**; frontend V0.5.23 vẫn có đầy đủ breakdown crossing và đã nâng nhãn engine lên 7.1.

---

# Traffic AI V0.5.23 — Benchmark Integrity + Crossing Engine 7.1 + Human-vs-Motorcycle Guard 🚗🎯🧍

V0.5.23 tiếp tục trực tiếp từ benchmark thật của `clip1.mp4` và frame camera người dùng cung cấp.

Baseline V0.5.22 đã đo được:

```text
Ground Truth      149
AI event DB       158
Khớp              133
Lọt                16
Đếm dư             25
Recall            89.3%
Precision         84.2%
F1                86.6%
Class đúng        97.0%
```

Ngoài ra Session #120 từng hiển thị `162` ở worker nhưng Benchmark chỉ có `158` event DB. Frame camera thực tế còn cho thấy **một người đi bộ bị YOLO gán `motorcycle`**, nên nếu người đó cắt vạch thì có thể tạo false positive xe máy.

Bản này xử lý đồng thời ba lớp thay vì tiếp tục hạ confidence:

1. **Human-vs-Motorcycle Guard** — dùng PERSON evidence của YOLO26 pretrained để chặn người bị nhầm thành motorcycle/bicycle trước khi tăng IN/OUT.
2. **Benchmark Integrity** — tổng Session sau khi COMPLETED lấy từ `vehicle_events` thật trong DB; worker total, event bị backend dedup và event thiếu timecode được hiển thị tách biệt.
3. **Crossing Engine 7.1** — fast-confirm cho xe nhanh, adaptive cooldown cho lượt quay đầu thật, rescue validation chống ID-jump và crossing-signature dedup cực hẹp cho ID switch.

---

## 1. Human-vs-Motorcycle Guard

Ảnh camera cho thấy trường hợp điển hình:

```text
người đi bộ
   ↓
YOLO vehicle detector
   ↓
motorcycle #... 0.52   ❌
   ↓
ByteTrack
   ↓
đi qua vạch
   ↓
Xe máy +1              ❌
```

V0.5.23 thêm verifier person-aware độc lập:

```text
candidate motorcycle/bicycle
        ↓
box cao/hẹp giống người?
        ↓
YOLO26 pretrained kiểm tra crop:
PERSON + MOTORCYCLE + BICYCLE
        ↓
PERSON chiếm gần toàn candidate
và two-wheel evidence yếu
        ↓
PERSON-GUARD
        ↓
KHÔNG đưa vào Crossing Counter
KHÔNG tăng IN / OUT
KHÔNG tạo VehicleEvent
```

Guard cố ý **không** xóa motorcycle khi có người lái thật. Nếu crop vẫn có two-wheel evidence cạnh tranh, candidate được giữ.

Telemetry mới:

```text
Human Guard 3
HUMAN-X 3
```

Box bị loại trên AI Overlay hiển thị `PERSON-GUARD` để dễ kiểm tra bằng mắt.

Runtime:

```env
AI_HUMAN_GUARD=1
AI_HUMAN_GUARD_MODEL=yolo26s.pt
AI_HUMAN_GUARD_IMGSZ=512
AI_HUMAN_GUARD_CHECK_INTERVAL=12
AI_HUMAN_GUARD_CONF=0.08
```

`best.pt` Run #3 vẫn giữ vai trò refine class của phương tiện. Human Guard dùng model pretrained vì custom dataset hiện không có class `person`.

---

## 2. Benchmark Integrity: worker 162 nhưng DB 158 được giải thích rõ

Trước đây:

```text
AI worker total       162
backend dedup          -4
VehicleEvent DB       158

Session.total_vehicles = max(..., 162)
Benchmark AI count     = 158
```

nên Dashboard và Benchmark có hai tổng khác nhau.

V0.5.23 đổi semantics:

```text
worker_total_vehicles   = tổng candidate crossing ở worker

total_vehicles          = số VehicleEvent thật đã persist DB

dedup_suppressed_events = worker_total - persisted DB
```

Khi session kết thúc backend **COUNT trực tiếp `vehicle_events`** rồi chốt Session.

Benchmark Report có khối:

```text
✓ Benchmark Integrity OK
Worker đề xuất 162
DB lưu        158
Có timecode   158
Backend gộp     4
Human Guard     ...
```

Migration cũng sửa các session cũ có event DB để Session #120 không tiếp tục hiển thị `162` trong lịch sử khi DB chỉ có `158` event. Giá trị worker cũ được giữ ở `worker_total_vehicles`.

---

## 3. Crossing Engine 7.1

### Fast destination confirmation

V0.5.21 yêu cầu hai observation ở phía sau vạch. Benchmark cho thấy một số xe nhanh đã đi đủ xa sang phía mới nhưng vẫn bị ghi:

```text
Crossing chưa đủ xác nhận phía sau vạch
```

V0.5.23 cho phép xác nhận ngay khi điểm mới đã cách vạch đủ xa:

```env
AI_GATE_FAST_CONFIRM_DISTANCE_RATIO=0.018
```

Nó không nới crossing cho điểm chỉ rung sát dead-band.

### Adaptive cooldown

Cooldown cứng 60 frame giảm overcount nhưng cũng chặn một số lượt quay đầu thật.

V7.1 chỉ giữ cooldown nếu track **chưa thật sự rời xa vạch**. Track đã đi xa rồi quay lại có thể được release sớm:

```env
AI_GATE_ADAPTIVE_COOLDOWN=1
AI_GATE_COOLDOWN_RELEASE_RATIO=0.055
```

Telemetry:

```text
COOL-REL ...
```

### Rescue validation

Long-gap rescue là nguồn false positive rủi ro nhất. V7.1 từ chối rescue nếu:

- chuyển động quá song song với vạch;
- jump quá xa giống ID switch;
- hai điểm chỉ nằm rất sát hai phía dead-band.

```env
AI_GATE_RESCUE_MIN_NORMAL_RATIO=0.28
AI_GATE_RESCUE_MAX_JUMP_RATIO=0.26
AI_GATE_RESCUE_MIN_SIDE_RATIO=0.010
```

Telemetry:

```text
RESCUE-X ...
```

### Crossing signature dedup

Mỗi event mới lưu thêm vị trí giao vạch chuẩn hóa:

```text
crossing_x
crossing_y
```

Backend chỉ gộp hai event khác track khi chúng:

```text
cùng session
cùng hướng
cùng họ phương tiện
cách nhau <= ~0.22s
điểm cắt gần như cùng vị trí
```

Threshold được cố ý đặt hẹp để không gộp hai xe máy thật chạy gần nhau.

---

## 4. Database V0.5.23

Migration:

```text
0036_gt_reuse_v0522
        ↓
0037_integrity_v0523
```

Schema:

```text
schema_version = 0.5.23
```

`counting_sessions` thêm:

```text
worker_total_vehicles
dedup_suppressed_events
human_guard_rejections
```

`vehicle_events` thêm:

```text
crossing_x
crossing_y
```

Không xóa:

```text
Dataset #4
600 ảnh
Run #3
best.pt
Benchmark #1 / #2
149 Ground Truth
vehicle_events cũ
training-runs/
models/
```

---

## 5. Cách test đúng V0.5.23

Giữ nguyên vạch và Road Zone hiện tại để tái sử dụng đúng 149 GT.

```text
V0.5.22 baseline
GT 149 · AI 158 · Match 133 · Miss 16 · FP 25
        ↓
V0.5.23
Chạy lại đúng clip1.mp4 đến COMPLETED
        ↓
Tạo Benchmark Session mới
        ↓
Sao chép 149 GT
        ↓
Đối chiếu lại
```

So sánh:

```text
AI
Khớp
Lọt
Dư
Recall
Precision
F1
Benchmark Integrity
Human Guard
```

Không cần đánh I/O lại 149 lần.

---

## 6. Cập nhật trên máy

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

Nếu Windows chặn `.ps1`:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
```

Kiểm thử:

```powershell
.\scripts\test.ps1
```

Mong muốn:

```text
[Traffic AI] Benchmark Integrity + Crossing Engine 7.1 + Human Guard V0.5.23
[OK] Benchmark Integrity + Crossing Engine 7.1 + Human Guard V0.5.23

[SUCCESS] All Traffic AI tests passed.
```

Khởi động:

```powershell
.\scripts\start.ps1
```

Database:

```powershell
.\scripts\verify-database.ps1
```

Mong muốn:

```text
0037_integrity_v0523
schema_version = 0.5.23
```

Trình duyệt:

```text
Ctrl + F5
```

---

## 7. Phát hành vẫn một lệnh

```powershell
.\scripts\publish.ps1
```

```text
→ test
→ build
→ push GitHub
→ tag v0.5.23
→ GitHub Actions
→ Release
```

---

## Kiểm thử trong môi trường đóng gói

```text
Python compile                         PASS
AI Service unit tests                 74/74 PASS
Backend unit tests                    17/17 PASS
Human Guard geometry policy           PASS
Pedestrian dominates motorcycle       PASS
Real rider two-wheel evidence          PASS
Fast-confirm crossing                 PASS
Adaptive cooldown release             PASS
Long-gap rescue validation             PASS
Crossing rollback for Human Guard      PASS
Benchmark Integrity source contract    PASS
Alembic head/revision safety           PASS
```

Frontend `npm install` trong môi trường đóng gói bị timeout mạng; vì vậy Vite + Docker full-suite không được ghi PASS giả và vẫn do `./scripts/test.ps1` trên máy Windows/Docker của bạn xác nhận.

---

# Traffic AI V0.5.22 — Ground Truth Reuse Fix ♻️🎯

V0.5.22 sửa lỗi UX của V0.5.21: sau khi tạo Benchmark mới cho Session mới, selector tự chuyển sang Benchmark đích `GT 0`, làm nút sao chép biến mất vì frontend chỉ nhìn Ground Truth của benchmark đang chọn.

Bản này thêm API sao chép GT **vào benchmark đã tạo** và tự tìm benchmark nguồn tương thích (cùng video + cùng vạch). Với tình huống hiện tại:

```text
Benchmark #1 · Session #119 · GT 149
Benchmark #2 · Session #120 · GT 0
          ↓
Sao chép 149 GT từ Benchmark #1 sang Benchmark #2
          ↓
Benchmark #2 · GT 149
          ↓
Đối chiếu lại với AI Session #120
```

Không cần xem lại 15:46 phút clip và không cần bấm I/O lại. Backend từ chối sao chép nếu video/vạch khác hoặc benchmark đích đã có GT, để tránh benchmark sai hoặc nhân đôi dữ liệu.


## Với dữ liệu hiện tại của bạn

Sau khi nâng V0.5.22, chọn:

```text
Benchmark #2 · Session #120 · GT 0
```

ngay dưới selector sẽ hiện:

```text
Sao chép 149 GT từ Benchmark #1 sang Benchmark #2
```

Bấm một lần, Benchmark #2 thành `GT 149`, sau đó bấm `Đối chiếu lại`. Không cần tạo Benchmark #3 và không cần đánh lại I/O.

V0.5.22 cũng sửa một lỗi React kín: nút `Tạo benchmark cho phiên này` trước đây truyền click-event vào tham số clone vì dùng `onClick={createBenchmark}`. Bản mới gọi tường minh `onClick={()=>createBenchmark()}` nên tạo benchmark thường không còn bị hiểu nhầm là yêu cầu clone.

## Database

```text
0035_crossing_v0521
        ↓
0036_gt_reuse_v0522
schema_version = 0.5.22
```

Không xóa dataset, model, session, benchmark hay 149 Ground Truth cũ.

---

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
