# Traffic AI V0.5.12 — Road Guard 2.0 + Release Hygiene 🚗🛡️

> **V0.5.12:** dọn sạch warning LF/CRLF khi `publish.ps1`, thêm validation vùng lòng đường/vạch đếm fail-closed, và siết điều kiện Road Zone để cả điểm track trước/sau crossing đều phải nằm trong lòng đường. Vạch vàng không còn được phép lưu nếu đầu vạch nằm ra lề/vỉa hè hoặc polygon xanh bị bắt chéo.

## V0.5.12 nâng cấp gì

- **Release hygiene:** thêm `scripts/normalize-line-endings.ps1`, `.gitattributes` chốt `*.ps1 = CRLF`, source/config = `LF`; `publish.ps1` tự normalize trước `git add -A`, loại warning kiểu `LF will be replaced by CRLF` / `CRLF will be replaced by LF`.
- **Road Guard 2.0:** frontend hiển thị trạng thái `✓ ROAD GUARD hợp lệ` hoặc chặn lưu khi geometry sai.
- **Backend validation:** từ chối Road Zone quá nhỏ, polygon 4 điểm tự bắt chéo, vạch quá ngắn hoặc đầu vạch nằm ngoài vùng Lòng đường.
- **AI fail-closed:** lúc crossing, `previous anchor + crossing + probe trước/sau + current anchor` đều phải nằm trong Road Zone mới được tăng IN/OUT.
- **Biên an toàn mới:** `AI_ROAD_ZONE_PROBE_RATIO=0.018` (1,8% cạnh ngắn frame) để crossing sát lề khó lọt hơn.
- **Default gate an toàn:** camera còn dùng vạch factory cũ `0.10/0.50 → 0.90/0.50` được migration đổi sang `0.32/0.59 → 0.84/0.59`; vạch tùy chỉnh của người dùng không bị sửa.

## Cập nhật

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\test.ps1
.\scripts\start.ps1
.\scripts\verify-database.ps1
```

Mong muốn:

```text
0026_road_guard_v0512
schema_version = 0.5.12
```

Sau khi chạy ổn, phát hành vẫn chỉ một lệnh:

```powershell
.\scripts\publish.ps1
```

```text
→ test → normalize line endings → build → push GitHub → tag v0.5.12 → GitHub Actions → Release
```

---

# Traffic AI V0.5.11 — Road Zone Counting + Frame Browser 🚗🛣️

> **V0.5.11:** thêm vùng đa giác **Lòng đường** 4 điểm kéo trực tiếp trên ảnh. Một phương tiện chỉ tăng IN/OUT khi quỹ đạo cắt đúng đoạn vạch vàng **và** vùng nhỏ quanh điểm cắt nằm trong vùng xanh Lòng đường. Xe trên lề/vỉa hè có thể vẫn được nhận diện để quan sát nhưng không được đếm. Annotation Studio bỏ `<select size>` cũ và dùng Frame Browser dạng card cuộn dễ đọc.

## Cấu hình sau khi cập nhật

1. Bấm **Dừng AI**.
2. Mở **ROAD ZONE + COUNTING LINE**.
3. Kéo 4 chấm xanh để vùng **LÒNG ĐƯỜNG** chỉ phủ phần xe chạy, loại lề/vỉa hè ra ngoài.
4. Đặt vạch vàng trong vùng xanh và vuông góc hướng xe chạy.
5. Bấm **Lưu vạch + vùng lòng đường**.
6. Chạy AI. Telemetry `loại ngoài lòng đường` sẽ tăng khi quỹ đạo cắt vạch nhưng bị Road Zone loại.

```text
Xe trên lề ───────→   ngoài vùng xanh   → KHÔNG ĐẾM

        ┌──────────── LÒNG ĐƯỜNG ────────────┐
Xe     │                 ↓                    │
chạy   │          ====== VẠCH ======          │
đường  │                 ↓                    │
        └──────────────────────────────────────┘
                         → ĐẾM IN/OUT
```

## Phát hành

Sau khi chạy ổn vẫn chỉ một lệnh:

```powershell
.\scripts\publish.ps1
```

```text
→ test → build → push GitHub → tag v0.5.11 → GitHub Actions → Release
```

---

# Traffic AI V0.5.10-R1 — Dataset Studio UI Visibility Hotfix 🚗🧰




> **V0.5.10-R1 hotfix:** sửa Dataset Studio khi nằm trong cột hẹp trên màn hình desktop: `Ngưỡng thay đổi`, checkbox `Loại frame gần trùng` và nút `1. Tạo dataset · Trích frame thông minh` không còn tràn ra ngoài panel. Layout giờ phản ứng theo **chiều rộng panel** bằng CSS container query, không dựa riêng vào chiều rộng toàn viewport. Runtime/database vẫn là **0.5.10 / 0024_ci_node_v0510**.

> **V0.5.10:** nâng Node.js frontend từ **26.9.0 → 26.10.0**, nâng GitHub Actions lên `actions/checkout@v7`, `actions/setup-python@v7`, `actions/setup-node@v7` để không còn action runtime Node.js 20, và sửa lỗi GitHub runner không có quyền ghi `/data` bằng `runner.temp`. Clean Retrain + Smart Review của V0.5.9 được giữ nguyên.

> **V0.5.9-R1 hotfix:** sửa `scripts/test.ps1` để contract Dataset & Fine-tune Studio kiểm tra handler thật `startTraining` / `activateTraining` thay vì phụ thuộc nguyên văn nút `Bắt đầu fine-tune RTX 3060`. Runtime, database schema và migration vẫn là **0.5.9 / 0023_clean_retrain_v059**.


## V0.5.10-R1 sửa giao diện tạo dataset

Ở V0.5.10, JSX đã có đủ `min_change_ratio`, `smart_dedupe` và `createDataset`, nhưng CSS dùng media query theo chiều rộng toàn cửa sổ. Khi Dashboard desktop rộng nhưng Dataset Studio chỉ nằm trong một cột hẹp, các control thứ 4–6 bị tràn sang bên phải nên người dùng chỉ thấy Tên dataset / Mỗi N frame / Tối đa ảnh.

R1 bố trí lại để ở panel hẹp luôn thấy đủ:

```text
Tên dataset
Mỗi N frame        | Tối đa ảnh
Ngưỡng thay đổi    | ☑ Loại frame gần trùng
[ 1. Tạo dataset · Trích frame thông minh ]
```

`Ngưỡng thay đổi = 0.008` nghĩa là frame ứng viên phải có ít nhất khoảng **0,8% điểm ảnh đại diện thay đổi đủ rõ** so với frame đã giữ gần nhất thì mới được giữ lại. Giá trị thấp giữ nhiều ảnh hơn; giá trị cao lọc mạnh hơn. Khuyến nghị bắt đầu ở `0.008`.

## V0.5.10 sửa lỗi publish trên GitHub Actions

Log V0.5.9 cho thấy local test/build đều PASS nhưng Release workflow dừng ở `Test AI service` vì `app/training.py` tạo `/data/datasets` khi import trên GitHub-hosted runner. V0.5.10 sửa theo hai lớp:

- `AI_DATASET_ROOT`, `AI_TRAINING_ROOT`, `AI_MODEL_ROOT`, `VIDEO_DIR` trên CI trỏ vào `${{ runner.temp }}`;
- `MODEL_ROOT` trong `training.py` cũng đọc `AI_MODEL_ROOT`, không còn hard-code tuyệt đối `/data/models`;
- GitHub Actions nâng lên `checkout/setup-python/setup-node @v7`;
- frontend Docker/local test nâng Node.js lên `26.10.0`;
- thêm `.nvmrc` và `engines.node >=26.10.0` để đồng bộ môi trường.

V0.5.9 tập trung vào một việc thực tế: **train lại sạch mà không bắt người dùng ngồi sửa thủ công 1.200 frame gần giống nhau**.

Bản này giữ nguyên toàn bộ Strict Gate/Fast Crossing của V0.5.8 và bổ sung workflow dataset mới:

```text
Video gốc
   ↓
Trích frame thông minh
   ↓
Bỏ frame gần trùng
   ↓
Auto-label YOLO26
   ↓
Smart Review
   ├─ ưu tiên motorcycle / bicycle
   ├─ confidence thấp
   ├─ ảnh đông xe
   └─ ảnh không detection
   ↓
Spot-check + sửa ảnh rủi ro
   ↓
Duyệt nhanh ảnh tin cậy
   ↓
Train / Val / Test
   ↓
Fresh fine-tune từ YOLO26s pretrained
   ↓
best.pt mới
   ↓
Kích hoạt → Chạy AI = INFERENCE
```

## 1. “Train lại từ đầu” trong Traffic AI nghĩa là gì?

Trong dự án này, cách nên dùng là **tạo một Training Run mới từ base model pretrained `yolo26s.pt`**, không tiếp tục từ `best.pt` cũ.

```text
YOLO26s pretrained
       ↓
Dataset mới sạch
       ↓
Fine-tune run mới
       ↓
best.pt mới
```

Đây là **fresh fine-tune**, không phải huấn luyện random weights từ số 0. Random-weight training thường cần dataset lớn hơn rất nhiều và không phù hợp với bộ dữ liệu vài trăm đến vài nghìn ảnh của một góc camera.

Trong giao diện **FINE-TUNE**, chọn:

```text
Base model: YOLO26s
```

Không chọn `best.pt` cũ làm base model nếu mục tiêu là làm lại sạch.

## 2. Dataset cũ và ảnh cũ có xóa được không?

Có. V0.5.9 thêm hai thao tác riêng để tránh xóa nhầm.

### A. Nhãn sai nhưng ảnh vẫn tốt

Bấm:

```text
Làm lại nhãn · giữ ảnh
```

Hệ thống giữ:

```text
datasets/<slug>/raw/images/
```

và xóa/reset:

```text
raw/labels/
annotation_review.json
raw/auto_label_meta.json
images/train|val|test
labels/train|val|test
dataset.yaml
```

Sau đó chạy lại **Auto-label YOLO26** rồi Smart Review.

### B. Muốn làm lại hoàn toàn sạch

Bấm:

```text
Xóa dataset + ảnh cũ
```

Hệ thống xóa đồng bộ cả database và file vật lý của dataset, đồng thời dọn thư mục `training-runs/run-<id>` liên quan. Nếu một training run của dataset vẫn đang `queued/running`, thao tác xóa bị chặn để tránh hỏng dữ liệu.

**Model đã export trong `models/` được giữ nguyên**, kể cả `best.pt` đang dùng. Vì vậy bạn có thể train dataset mới mà hệ thống inference hiện tại vẫn dùng model cũ cho tới khi bạn chủ động kích hoạt model mới.

> Không nên tự `Remove-Item datasets/...` bằng tay khi PostgreSQL vẫn còn record dataset, vì UI sẽ thấy record nhưng file đã mất. Dùng nút xóa trong Dataset Studio để DB và disk luôn đồng bộ.

## 3. Vì sao không cần sửa tay 1.200 ảnh?

V0.5.8 lấy frame theo chu kỳ cố định và có thể sinh nhiều ảnh gần giống nhau. Ví dụ video 30 FPS với `N=10` tạo khoảng 3 frame ứng viên mỗi giây; camera cố định sẽ có rất nhiều frame nền gần như giống nhau.

V0.5.9 đổi mặc định:

```text
Mỗi N frame       = 15
Tối đa ảnh        = 600
Loại frame gần trùng = BẬT
Ngưỡng thay đổi   = 0.008
```

Quy trình trích mới:

```text
frame ứng viên
    ↓
ảnh xám 160×90
    ↓
so với frame đã giữ gần nhất
    ↓
tỷ lệ pixel thay đổi đủ lớn?
    ├─ Không → bỏ frame gần trùng
    └─ Có    → lưu vào dataset
```

Ví dụ:

```text
1.100 frame ứng viên
      ↓
350 frame gần trùng bị bỏ
      ↓
600 frame đa dạng được giữ
```

Con số thực tế phụ thuộc video. Mục tiêu không phải “càng nhiều ảnh càng tốt”, mà là **ảnh đa dạng + nhãn đúng**.

### Gợi ý sampling

Với video khoảng 30 FPS:

```text
N = 15  → khoảng 2 frame ứng viên/giây trước lọc
N = 30  → khoảng 1 frame ứng viên/giây trước lọc
```

Với một góc camera cố định, nên bắt đầu khoảng:

```text
400–800 ảnh đa dạng
```

sau đó đánh giá benchmark. Chỉ tăng dataset khi còn lỗi thực tế chưa được đại diện đủ.

## 4. Smart Review — chỉ xem ảnh có nguy cơ sai trước

Sau khi bấm:

```text
2. Auto-label YOLO26
```

V0.5.9 lưu thêm metadata confidence và tính **review priority** cho từng ảnh.

Annotation Studio mặc định mở bộ lọc:

```text
🔥 Ưu tiên cần kiểm tra
```

Các ảnh được đưa lên đầu khi có một hoặc nhiều yếu tố:

```text
motorcycle / bicycle
bicycle prediction
confidence thấp
nhiều xe trong cùng frame
không phát hiện phương tiện nào
```

Đây là đúng nhóm bạn nên dành thời gian sửa tay, đặc biệt với lỗi hiện tại:

```text
Xe máy → Xe đạp ❌
```

Các bộ lọc có sẵn:

```text
🔥 Ưu tiên cần kiểm tra
Chưa duyệt
Ảnh khó
Tất cả ảnh
```

## 5. “Duyệt nhanh ảnh tin cậy” hoạt động thế nào?

Sau khi bạn xem thử một số ảnh và thấy auto-label ổn, có thể bấm:

```text
Duyệt nhanh ảnh tin cậy
```

V0.5.9 cố ý rất bảo thủ. Hệ thống **không tự duyệt**:

```text
ảnh có motorcycle
ảnh có bicycle
ảnh không detection
ảnh đông xe
ảnh confidence thấp
```

Chỉ các frame rõ, ít box, class không phải xe hai bánh và confidence cao mới đủ điều kiện.

Điều này giúp giảm khối lượng click thủ công mà vẫn để nhóm xe máy/xe đạp — lỗi quan trọng nhất của dự án — cho người dùng kiểm tra thật.

## 6. Quy trình train lại sạch — từng bước

### Bước 0 — quyết định giữ hay xóa dataset cũ

Nếu frame cũ vẫn đa dạng và đúng góc camera:

```text
Làm lại nhãn · giữ ảnh
```

Nếu muốn làm mới hoàn toàn:

```text
Xóa dataset + ảnh cũ
```

### Bước 1 — trích frame thông minh

Trong **Dataset Studio**:

```text
Tên dataset       : traffic-vietnam-clean-01
Mỗi N frame       : 15
Tối đa ảnh        : 600
Ngưỡng thay đổi   : 0.008
☑ Loại frame gần trùng
```

Bấm:

```text
1. Trích frame thông minh
```

Thông báo sẽ cho biết số frame được giữ và số frame gần trùng đã bỏ.

### Bước 2 — Auto-label

Bấm:

```text
2. Auto-label YOLO26
```

Auto-label chỉ là **pseudo-label**, chưa phải ground truth.

### Bước 3 — Smart Review

Xuống **Annotation Studio · Smart Review**.

Đầu tiên giữ bộ lọc:

```text
🔥 Ưu tiên cần kiểm tra
```

Ưu tiên sửa theo thứ tự:

```text
1. bicycle nhưng thực tế là motorcycle
2. motorcycle nhưng box sai/mất box
3. ảnh không detection nhưng có xe
4. ảnh nhiều xe bị thiếu box
5. bus/truck/car bị nhầm class
```

Hotkey khi đã chọn box:

```text
1 → Xe máy
2 → Xe đạp
3 → Ô tô
4 → Xe buýt
5 → Xe tải
Delete / Backspace → xóa box
```

Sau khi sửa ảnh, đánh dấu:

```text
☑ Đã rà soát
```

rồi bấm:

```text
Lưu nhãn
```

### Bước 3B — spot-check ảnh dễ

Chuyển bộ lọc sang:

```text
Chưa duyệt
```

Xem ngẫu nhiên một số frame auto-label được coi là ổn. Nếu chất lượng tốt, bấm:

```text
Duyệt nhanh ảnh tin cậy
```

Không nên bấm duyệt nhanh trước khi spot-check.

### Bước 4 — chia Train / Val / Test

Sau khi sửa annotation, bấm:

```text
4. Chia train/val/test
```

Mặc định:

```text
Train 70%
Val   20%
Test  10%
Seed  2026
```

V0.5.9 tạo lại:

```text
images/train
images/val
images/test
labels/train
labels/val
labels/test
dataset.yaml
```

### Bước 5 — Fine-tune mới

Khuyến nghị ban đầu cho RTX 3060:

```text
Base model : YOLO26s
Epochs     : 80
Image size : 640
Batch      : 8
Device     : auto/CUDA
```

Bấm:

```text
5. Bắt đầu fine-tune mới RTX 3060
```

Training run mới khởi tạo từ `yolo26s.pt`, **không học tiếp từ `best.pt` cũ**.

### Bước 6 — kích hoạt best.pt mới

Khi run hoàn tất:

```text
COMPLETED
```

kiểm tra:

```text
Precision
Recall
mAP50
mAP50-95
```

rồi bấm:

```text
6. Kích hoạt best.pt
```

Lúc này:

```text
Kích hoạt best.pt
       ↓
Chạy AI
       ↓
INFERENCE
```

Chạy video không làm model train thêm.

## 7. Điều gì nên rà soát thủ công nhiều nhất cho lỗi xe máy → xe đạp?

Không cần chia thời gian đều cho mọi class. Với camera của dự án, ưu tiên:

```text
motorcycle ở xa
motorcycle bị motion blur
xe tay ga nhìn từ trên xuống
xe máy bị che một phần
motorcycle đi cạnh bicycle thật
bicycle thật để model học ranh giới hai class
```

Đặc biệt phải có **bicycle thật** trong dataset. Nếu dataset chỉ có hàng nghìn xe máy và rất ít xe đạp, model khó học ranh giới class dù annotation xe máy đã đúng.

## 8. Database V0.5.10

Migration mới:

```text
0022_strict_gate_v058
        ↓
0023_clean_retrain_v059
        ↓
0024_ci_node_v0510
```

`schema_version`:

```text
0.5.10
```

Migration này không xóa dataset/model cũ. Việc xóa chỉ xảy ra khi người dùng chủ động bấm **Xóa dataset + ảnh cũ**.

## 9. GitHub Actions / phát hành

V0.5.10 nâng GitHub Actions lên major hiện hành chạy trên runtime Node.js 24:

```text
actions/checkout@v7
actions/setup-python@v7
actions/setup-node@v7
```

Node.js dùng để **build frontend** là `26.10.0`. Đây là hai lớp khác nhau: runtime nội bộ của GitHub Action là Node 24, còn project frontend được `setup-node` cài Node 26.10.0.

AI unit test trên GitHub runner dùng thư mục ghi được:

```text
${{ runner.temp }}/traffic-ai/datasets
${{ runner.temp }}/traffic-ai/training-runs
${{ runner.temp }}/traffic-ai/models
${{ runner.temp }}/traffic-ai/videos
```

nên không còn cố tạo `/data/datasets` trực tiếp trên host runner.

Release artifact gồm:

```text
traffic-ai-v0.5.10.zip
traffic-ai-v0.5.10.tar.gz
traffic-ai-v0.5.10-README.md
SHA256SUMS.txt
```

Fallback GitHub CLI vẫn được giữ nếu GitHub Actions Release thất bại.

## 10. Cập nhật trên máy

Chép source mới đè vào:

```text
D:\LienThongDH\DoAn\traffic-ai
```

Giữ dữ liệu runtime:

```text
.env
gateway\certs\
videos\
models\
snapshots\
datasets\
training-runs\
```

Không chạy:

```powershell
docker compose down -v
```

Kiểm thử:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\test.ps1
```

Khởi động:

```powershell
.\scripts\start.ps1
```

Kiểm tra DB:

```powershell
.\scripts\verify-database.ps1
```

Mong muốn:

```text
0024_ci_node_v0510
schema_version = 0.5.10
```

## 11. Phát hành — vẫn chỉ một lệnh

Sau khi chạy ổn:

```powershell
.\scripts\publish.ps1
```

```text
test
→ build
→ commit
→ push GitHub
→ tag v0.5.10
→ GitHub Actions
→ GitHub Release
→ ZIP + TAR.GZ + README + SHA256SUMS
```

Nếu GitHub Actions Release lỗi, `publish.ps1` tự fallback sang `gh release create`; người dùng không cần chạy thêm chuỗi lệnh Git/gh thủ công.

---

# Lịch sử V0.5.8-R1

# Traffic AI V0.5.8-R1 — Strict Gate + Fast Crossing (Test Contract Hotfix)

**Đồ án môn Trí tuệ nhân tạo:** Nghiên cứu và xây dựng hệ thống phát hiện, phân loại, theo dõi và đếm phương tiện giao thông qua camera.

> **R1 là hotfix cho `scripts/test.ps1`, không đổi runtime/schema.** Phiên bản ứng dụng, Docker image contract và Alembic vẫn là `0.5.8` / `0022_strict_gate_v058`. Hotfix thay assertion Annotation Studio từ việc phụ thuộc literal trình bày `1–5` sang kiểm tra trực tiếp hotkey handler `/^[1-5]$/.test(event.key)` và đủ hướng dẫn `1 Xe máy` ... `5 Xe tải`.

> Thư mục làm việc mặc định:
>
> ```powershell
> D:\LienThongDH\DoAn\traffic-ai
> ```

## 1. Mục tiêu V0.5.8

V0.5.8 tập trung trực tiếp vào độ tin cậy khi **đếm xe qua vạch**:

- **không đếm xe trên lề / ngoài hai đầu vạch**: crossing chỉ hợp lệ khi quỹ đạo cắt đúng đoạn vạch hữu hạn đang nhìn thấy; mặc định `AI_GATE_SEGMENT_MARGIN=0.0`;
- **bắt xe chạy nhanh tốt hơn**: lịch sử crossing tăng lên 45 frame, ByteTrack hạ ngưỡng tạo track và ROI chỉ tập trung quanh vùng vạch;
- **nhiều xe qua vạch cùng lúc**: mỗi track được xét độc lập, một frame có thể ghi nhiều crossing; snapshot chỉ ghi một lần cho cả crossing frame để giảm I/O;
- **giảm nhầm xe máy thành xe đạp**: nhãn `bicycle` cần bằng chứng thời gian mạnh, còn trường hợp mơ hồ được giữ là `motorcycle`; refiner được giới hạn để không làm tụt realtime.
- **khôi phục blocker Backend trong source V0.5.7**: bổ sung lại `backend/app/models/all_models.py` và `backend/app/models/__init__.py` theo đúng schema Alembic hiện có; source mới không còn lỗi import model khi Backend khởi động.

> **Kích hoạt `best.pt` không phải train.** Fine-tune đã kết thúc trước đó và tạo ra `best.pt`. Khi kích hoạt, model này chỉ được chọn làm model **inference** cho các phiên `Chạy AI` tiếp theo. Chạy AI sẽ phát hiện/theo dõi/đếm bằng `best.pt`, không tự huấn luyện tiếp và không tự thay đổi trọng số. Muốn train tiếp phải tạo/chỉnh dataset rồi bấm fine-tune một training run mới.

Luồng inference V0.5.8:

```text
Video / Camera
      ↓
Compact Gate ROI
      ↓
YOLO26 / best.pt
      ↓
ByteTrack nhạy hơn với xe nhanh
      ↓
Track continuity + trajectory history
      ↓
STRICT FINITE LINE CROSSING
      ↓
Chỉ khi quỹ đạo cắt đúng đoạn vạch
      ↓
Policy phân loại xe máy / xe đạp
      ↓
IN / OUT + PostgreSQL
```

Annotation Studio của V0.5.6–V0.5.7 vẫn được giữ nguyên để sửa ground truth và fine-tune lại `best.pt` khi cần.

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
- Node.js **26.10.0** + npm **12.1.0**.
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

## 5. Database V0.5.8

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
        ↓
0019_activation_ui_v055
        ↓
0020_annotation_studio_v056
        ↓
0021_annotation_ux_v057
        ↓
0022_strict_gate_v058
```

Migration `0014` tạo các bảng Dataset/Fine-tune; `0015` dọn UI/test harness; `0016` đồng bộ contract Smooth Playback; `0017` tách dependency unit-test/runtime; `0018` nới `alembic_version.version_num`; `0019` ổn định kích hoạt `best.pt`; `0020` thêm trạng thái review cho Annotation Studio; `0021` đồng bộ `schema_version` cho UX Annotation V0.5.7; `0022` bật Strict Gate V0.5.8, hạ confidence mặc định từ `0.18` xuống `0.12` và không xóa dữ liệu nghiệp vụ.

`schema_version`:

```text
0.5.8
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
→ Tag v0.5.8
→ GitHub Actions
→ ZIP / TAR.GZ / SHA256
→ GitHub Release
```

Repository:

```text
https://github.com/TamNhien/traffic-ai
```

## 13. Lộ trình tiếp theo

### V0.5.13 — Ground-truth Benchmark

- benchmark cùng một clip với pretrained và `best.pt`;
- nhập/đối chiếu ground-truth theo từng loại và IN/OUT;
- confusion matrix;
- Precision/Recall/F1;
- counting MAE/MAPE/accuracy;
- báo cáo so sánh tự động.

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

### V0.5.4 — Alembic Revision Guard
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

### V0.5.6 — Annotation Studio tích hợp

- Vẽ bounding box trực tiếp trên Dashboard.
- Sửa class bằng dropdown hoặc hotkey `1..5`; xóa box bằng `Delete`.
- Đánh dấu ảnh đã rà soát và ảnh khó trong `annotation_review.json`.
- Hiển thị class balance và hệ số mất cân bằng.
- Thêm API đọc/ghi annotation an toàn qua Backend → AI Service.
- PostgreSQL lưu `reviewed_images` và `difficult_images` cho từng dataset.
- Dataset bị sửa nhãn quay lại trạng thái `labeled`; phải chia lại train/val/test trước khi fine-tune.
- Thêm migration `0020_annotation_studio_v056`, `schema_version = 0.5.6`.

### V0.5.7 — Annotation Studio UX rõ ràng

- Nhãn trên ảnh đổi từ dạng dễ nhầm `1. Xe đạp` thành `Box 1 · Xe đạp`.
- Dropdown class chỉ hiển thị tên phương tiện, không dùng số thứ tự gây nhầm với số box.
- Khi nhấp bounding box, dropdown tự đồng bộ đúng class hiện tại của box.
- Hiển thị trạng thái rõ ràng `Đang chọn: Box N · Class` hoặc `Chưa chọn box`.
- Phân biệt `Đổi class box đã chọn` và `Class cho box mới`.
- Click vùng trống của ảnh bỏ chọn box và chuyển về chế độ tạo box mới.
- Thêm regression contract `Annotation UX clarity V0.5.7`.
- Thêm migration `0021_annotation_ux_v057`, `schema_version = 0.5.7`.



### V0.5.8 — Strict Gate + Fast Crossing

- Chỉ đếm khi quỹ đạo track cắt đúng **đoạn vạch hữu hạn**; mặc định không nới ra ngoài hai đầu vạch.
- Compact Gate ROI giảm vùng inference thừa quanh lề đường, tăng khả năng theo kịp video.
- ByteTrack: `track_high_thresh=0.10`, `new_track_thresh=0.10`, `track_low_thresh=0.015`, `match_thresh=0.84`.
- Confidence mặc định cho camera mới và camera còn giá trị chuẩn cũ giảm từ `0.18` xuống `0.12`.
- Crossing history tăng mặc định lên 45 frame để cứu xe nhanh / mất detect ngắn.
- Một frame có thể đếm nhiều track độc lập; snapshot ghi một lần cho cả crossing frame.
- Refiner giới hạn `1` lần/frame và bỏ qua khi video lag trên `0.35s`.
- Nhãn xe đạp hiển thị/lưu chỉ khi có bằng chứng đủ mạnh; trường hợp mơ hồ hai bánh ưu tiên `motorcycle`.
- `start.ps1` tự nâng các tuning cũ trong `.env` sang V0.5.8 nhưng vẫn giữ các thiết lập tùy chỉnh khác của người dùng.
- Khôi phục đầy đủ `backend/app/models/all_models.py` bị thiếu trong gói V0.5.7 gốc, đồng bộ ORM với chuỗi migration hiện có.
- Thêm migration `0022_strict_gate_v058`, `schema_version = 0.5.8`.
