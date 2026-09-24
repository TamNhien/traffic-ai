# Traffic AI V0.5.14 — Full-frame Detect + Strict Road Count 🚗🎯

V0.5.14 sửa lỗi thực tế quan sát trong clip: nhiều xe đi qua khung hình nhưng không có box/track và gần như không đếm. Nguyên nhân chính của V0.5.13 là detector mặc định bị crop theo **Road Zone**; nếu polygon xanh đặt hẹp hoặc lệch luồng xe thì YOLO không hề nhìn thấy các xe bên ngoài vùng đó.

## Kiến trúc mới

```text
TOÀN KHUNG HÌNH
   ↓
YOLO26 / best.pt       ← detect toàn frame
   ↓
ByteTrack              ← track xe từ sớm
   ↓
Road Guard + vạch vàng
   ↓
chỉ crossing nằm trong vùng xanh mới COUNT
```

Có thể thấy bounding box của xe trên lề để chẩn đoán detector, nhưng xe đó **không được cộng IN/OUT** nếu crossing không thỏa Road Zone.

### Runtime mặc định

```env
AI_DETECTION_ROI=full
AI_ROAD_ROI_MARGIN=0.02
```

`start.ps1` migrate đúng một lần cấu hình mặc định V0.5.13 `road -> full` bằng marker `AI_DETECTION_POLICY_V0514=1`. Sau lần migrate, người dùng vẫn có thể tự chọn lại `road` hoặc `gate` nếu cần tối ưu GPU.

## Telemetry mới

```text
DET  = số detection frame hiện tại
track = track đang hoạt động frame hiện tại
road = track có anchor nằm trong Road Zone
seen = tổng track từng quan sát trong phiên
DETECT FULL = detector đang quét toàn khung
```

Chẩn đoán nhanh:

- `DET=0` khi xe hiện rõ: detector/model/confidence có vấn đề.
- `DET>0`, `track>0`, `road=0`: Road Zone không phủ luồng xe; chỉnh polygon xanh.
- `road>0` nhưng `Tổng` không tăng khi cắt vạch: kiểm tra vị trí vạch/Road Guard.

## Vùng đếm

Vùng xanh vẫn chỉ là **vùng được phép đếm**, không còn là vùng giới hạn YOLO. Hãy kéo 4 điểm xanh bao toàn bộ phần lòng đường mà xe thực sự di chuyển, loại lề/vỉa hè. Vạch vàng đặt bên trong vùng xanh và cắt ngang hướng xe chạy.

## Database

```text
0027_fast_overlay_v0513
  ↓
0028_full_detect_v0514
```

Migration chỉ nâng `schema_version=0.5.14`, không xóa dataset, training run, best.pt hay lịch sử đếm.

## Cập nhật

Giữ `.env`, `gateway/certs`, `videos`, `models`, `snapshots`, `datasets`, `training-runs`; chép source mới đè vào `D:\LienThongDH\DoAn\traffic-ai`. Không dùng `docker compose down -v`.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\test.ps1
.\scripts\start.ps1
.\scripts\verify-database.ps1
```

Mong muốn:

```text
0028_full_detect_v0514
schema_version = 0.5.14
```

Sau khi chạy ổn, phát hành một lệnh:

```powershell
.\scripts\publish.ps1
```

```text
→ test → build → push GitHub → tag v0.5.14 → GitHub Actions → Release
```
