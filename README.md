# Traffic AI V0.5.13 — Instant Overlay + Road ROI Tracking 🚗⚡

> V0.5.13 tập trung vào đúng hai hiện tượng thực tế: chuyển sang **AI Overlay bị đen một lúc**, và xe chạy nhiều nhưng **box/track xuất hiện trễ, đếm chậm**. Bản này giữ Road Guard 2.0 để không đếm xe trên lề, nhưng cho detector/ByteTrack quan sát **toàn vùng lòng đường** sớm hơn thay vì chỉ chờ xe đi sát vạch.

## Vì sao AI Overlay trước đây có thể đen lúc mới chuyển

V0.5.12 chỉ phát MJPEG sau khi worker đã mở video, tải YOLO, warm-up CUDA và tải/warm-up thêm model refiner `yolo26m.pt`. Trong thời gian đó thẻ `<img>` của AI Overlay chưa nhận được frame nên vùng preview có thể đen.

V0.5.13 xử lý theo ba lớp:

1. Worker mở encoder sớm và gửi ngay một frame nguồn có dòng `AI warming up...` trước khi warm-up YOLO.
2. Frontend giữ video native ở phía dưới cho đến khi MJPEG thực sự có frame (`overlayReady`). Không còn đổi sang một `<img>` rỗng rồi chờ.
3. Model refiner được warm-up nền sau khi main detector đã chạy; refiner không còn chặn frame AI đầu tiên.

MJPEG cũng trả thêm:

```text
Cache-Control: no-store, no-cache
Pragma: no-cache
X-Accel-Buffering: no
```

để tránh browser/proxy gom frame trước khi hiển thị.

## Vì sao V0.5.12 có thể thấy ít box dù xe chạy nhiều

V0.5.12 mặc định dùng **Gate ROI** khá hẹp quanh vạch đếm. Điều này giảm tải và chặn phần lớn lề đường, nhưng có nhược điểm: YOLO/ByteTrack chỉ bắt đầu thấy xe khi xe đã vào dải gần vạch. Xe nhanh hoặc bị che có thể không đủ lịch sử track ở cả hai phía vạch.

V0.5.13 mặc định dùng:

```text
AI_DETECTION_ROI=road
AI_ROAD_ROI_MARGIN=0.02
```

Luồng mới:

```text
Video
  ↓
Vùng LÒNG ĐƯỜNG xanh
  ↓
Bounding ROI quanh toàn vùng đường
  ↓
YOLO26 / best.pt
  ↓
ByteTrack theo dõi xe từ sớm
  ↓
Road Guard + vạch vàng
  ↓
chỉ crossing trong lòng đường mới đếm
```

Xe trên lề vẫn không được cộng IN/OUT vì Road Guard 2.0 của V0.5.12 được giữ nguyên.

## Telemetry mới

Dòng trạng thái khi chạy AI giờ có thêm:

```text
CUDA/CPU
track N
ROI road
```

Ví dụ:

```text
INFERENCE · best.pt · AI 23% · FPS 31/30 · RT x1.03 · lag 0.0s · 19 ms · CUDA · track 48 · ROI road · Tổng 17 ...
```

Cách đọc nhanh:

- `CUDA`: đang dùng GPU. Nếu thấy `CPU`, inference sẽ chậm đáng kể.
- `RT x >= 1`: AI theo kịp tốc độ video.
- `RT x < 1` và `lag` tăng: AI đang xử lý chậm hơn video.
- `track` tăng mà `Tổng` không tăng: detector/tracker thấy xe nhưng xe chưa thỏa điều kiện crossing/Road Guard.
- `track` gần 0 dù xe rõ trong vùng xanh: vấn đề nằm ở model/confidence/ROI, không phải bộ đếm.

## Việc bạn đang sửa label để train lại

Các label bạn đang sửa **chưa làm model đang chạy thông minh hơn ngay lập tức**. Phiên AI hiện tại vẫn dùng model đang được kích hoạt trước đó.

Quy trình đúng sau khi sửa label:

```text
Sửa box/class trong Annotation Studio
        ↓
Lưu nhãn + đánh dấu đã rà soát
        ↓
4. Chia lại train / val / test
        ↓
5. Fine-tune mới từ YOLO26s pretrained
        ↓
training run COMPLETED
        ↓
6. Kích hoạt best.pt mới
        ↓
Dừng phiên AI cũ / Chạy AI lại
        ↓
Inference dùng best.pt mới
```

Nếu bạn đổi `bicycle → motorcycle`, thay đổi đó chỉ đi vào training run mới sau bước chia dataset lại. Không cần xóa `best.pt` cũ trước khi train.

## Tuning mặc định mới

```text
AI_DETECTION_ROI=road
AI_ROAD_ROI_MARGIN=0.02
AI_REFINE_BACKGROUND_WARMUP=1
```

Các tuning cũ vẫn giữ, gồm:

```text
AI_IMGSZ=640
AI_GATE_SEGMENT_MARGIN=0.0
AI_ROAD_ZONE_PROBE_RATIO=0.018
AI_STREAM_EVERY_N=2
AI_REFINE_MAX_PER_FRAME=1
AI_REFINE_MAX_LAG=0.35
```

## Database

Migration mới:

```text
0026_road_guard_v0512
        ↓
0027_fast_overlay_v0513
```

Migration V0.5.13 chỉ nâng:

```text
schema_version = 0.5.13
```

Không xóa camera, dataset, ảnh, training run, model, `best.pt`, event hoặc session.

## Cập nhật

Chép source đè vào:

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
0027_fast_overlay_v0513
schema_version = 0.5.13
```

Sau khi chạy ổn, phát hành vẫn một lệnh:

```powershell
.\scripts\publish.ps1
```

```text
→ test → build → push GitHub → tag v0.5.13 → GitHub Actions → Release
```
