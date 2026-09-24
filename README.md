# Traffic AI V0.5.15 — Hybrid Recall + Track Rescue 🚗⚡

V0.5.15 sửa lỗi quan sát trực tiếp trong clip thực tế: xe chạy qua liên tục nhưng gần như không có box và không đếm. Telemetry trong clip cho thấy có thời điểm `DET 1 · track 0 · road 0 · seen 2`: detector đã tạo detection nhưng ByteTrack chưa cấp ID. V0.5.14 lại chỉ vẽ box khi `boxes.id` tồn tại, nên detection thật bị ẩn khỏi AI Overlay; không có track ID thì Strict Gate cũng không thể đếm.

## Thay đổi chính

- **Luôn vẽ detection thô**: detection chưa có track ID được vẽ box vàng `DET`, không còn tình trạng `DET > 0` nhưng màn hình như không nhận dạng.
- **Hybrid Recall mặc định khi kích hoạt custom `best.pt`**:
  - `yolo26s.pt` pretrained làm detector + ByteTrack full-frame để ưu tiên recall và continuity;
  - `best.pt` tùy biến vẫn là model đang kích hoạt và được dùng để refine class tại thời điểm crossing;
  - Road Zone vẫn chỉ quyết định xe nào được phép đếm.
- **Tăng kích thước inference mặc định** `640 → 960` để bắt xe nhỏ/xa tốt hơn trên camera giao thông.
- **Confidence mặc định** `0.12 → 0.06` cho camera đang dùng default cũ.
- **ByteTrack high-recall profile**:
  - `track_high_thresh: 0.05`
  - `track_low_thresh: 0.005`
  - `new_track_thresh: 0.05`
  - `track_buffer: 150`
  - `match_thresh: 0.78`
- Telemetry mới: `DET`, `chưa ID`, `track`, `road`, detector thực tế và trạng thái `HYBRID`/`DIRECT`.
- Cảnh báo được tách đúng nguyên nhân:
  - `DET > 0` nhưng `track = 0` → ByteTrack chưa cấp ID;
  - `track > 0` nhưng `road = 0` → Road Zone chưa phủ luồng xe.

## Kiến trúc inference mới

```text
Custom best.pt đang kích hoạt
        ↓
HYBRID RECALL
        ↓
yolo26s.pt pretrained @ imgsz 960
        ↓
Full-frame detection
        ↓
ByteTrack high-recall
        ↓
Track ổn định
        ↓
Road Zone + Strict Gate
        ↓
Cắt vạch hợp lệ?
   │             │
  Không          Có
   ↓              ↓
Không đếm   best.pt refine class
                  ↓
               IN / OUT
```

Xe trên lề vẫn có thể được nhận dạng/track nhưng **không được đếm** nếu crossing không nằm trong Road Zone hợp lệ.

## Database

Migration mới:

```text
0028_full_detect_v0514
        ↓
0029_hybrid_recall_v0515
```

Migration chỉ hạ default camera confidence và nâng `schema_version=0.5.15`; không xóa dataset, training run, model, best.pt hay lịch sử đếm.

## Cập nhật

Giải nén/chép đè source vào:

```powershell
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

Không dùng `docker compose down -v`.

Chạy:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\test.ps1
.\scripts\start.ps1
.\scripts\verify-database.ps1
```

Mong muốn:

```text
0029_hybrid_recall_v0515
schema_version = 0.5.15
```

Sau đó `Ctrl + F5`, bấm `Chạy AI` → `AI Overlay` và nhìn telemetry. Với custom model đang kích hoạt phải thấy dạng:

```text
HYBRID detect yolo26s.pt + refine best.pt
DET ... · chưa ID ... · track ... · road ...
```

## Phát hành

Sau khi chạy ổn vẫn chỉ một lệnh:

```powershell
.\scripts\publish.ps1
```

```text
→ test → build → push GitHub → tag v0.5.15 → GitHub Actions → Release
```

## V0.5.15-R1 — hotfix contract test ByteTrack

- Sửa false-fail ở `Strict Gate + fast crossing V0.5.8`: contract cũ bắt cứng `track_high_thresh: 0.10` và `new_track_thresh: 0.10` dù V0.5.15 đã chủ động hạ xuống `0.05` để tăng recall và nâng `track_buffer` lên `150`.
- Contract mới kiểm tra tương thích theo ngữ nghĩa: `track_high_thresh <= 0.10`, `new_track_thresh <= 0.10`, `track_buffer >= 120`, đồng thời vẫn giữ `AI_GATE_ENDPOINT_MARGIN=0.035`.
- Không đổi runtime, database, migration hay model. `VERSION` vẫn là `0.5.15`; đây chỉ là hotfix kiểm thử để `test.ps1` chấp nhận tuning V0.5.15 tốt hơn tuning lịch sử V0.5.8.
