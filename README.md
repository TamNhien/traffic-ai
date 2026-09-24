# Traffic AI V0.5.17 — Single-Object BUS/TRUCK Guard 🚛🚌

V0.5.17 tiếp tục từ V0.5.16 và sửa lỗi một **xe tải có thể bị nhận/đếm đồng thời thành Xe buýt + Xe tải** khi detector tạo hai bounding box BUS/TRUCK chồng lên cùng một phương tiện.

## Nguyên nhân

YOLO/COCO có thể giữ hai detection khác class cho cùng một vật thể vì NMS mặc định là class-aware. Nếu cả BUS và TRUCK cùng đi vào ByteTrack, chúng có thể thành hai raw track ID và cùng cắt vạch, khiến một xe thật tạo hai lượt đếm.

## Single-Object Guard V0.5.17

Pipeline mới:

```text
Full-frame YOLO26 detector
        ↓
ByteTrack
        ↓
BUS/TRUCK overlap guard
        ↓
IoU >= 0.68 ?
  ├─ Không → giữ riêng
  └─ Có    → giữ box mạnh hơn
              + alias raw ID còn lại vào cùng canonical track
        ↓
Temporal class smoothing
        ↓
best.pt refine tại crossing
        ↓
Road Guard + Strict Gate
        ↓
MỘT phương tiện = MỘT crossing event
```

Guard chỉ xử lý cặp **BUS ↔ TRUCK** chồng box mạnh; không gộp tùy tiện xe máy/ô tô trong giao thông đông.

## Cấu hình mới

```env
AI_AGNOSTIC_NMS=0
AI_HEAVY_DUP_IOU=0.68
```

`AI_AGNOSTIC_NMS=0` giữ NMS class-aware mặc định để tránh làm mất các phương tiện thật đang chồng nhau trong cảnh đông. Lớp BUS/TRUCK guard riêng xử lý đúng xung đột cần sửa.

`AI_HEAVY_DUP_IOU=0.68` nghĩa là BUS/TRUCK phải chồng nhau ít nhất khoảng 68% mới bị xem là cùng một xe.

## Telemetry

Dòng runtime có thêm:

```text
gộp bus/truck N
```

Ví dụ:

```text
DET 8 · track 7 · road 4 · gộp bus/truck 1 · Tổng 22
```

`gộp bus/truck 1` nghĩa là frame đó hệ thống đã loại 1 detection BUS/TRUCK trùng cùng một xe trước bộ đếm.

## Thông số hiện tại của camera

Với cấu hình người dùng đang thử:

```text
X1 = 0.32
Y1 = 0.81
X2 = 0.84
Y2 = 0.55
Confidence = 0.05
```

V0.5.17 **không yêu cầu đổi Confidence** chỉ để sửa lỗi BUS/TRUCK đếm đôi. Có thể giữ `0.05` để cứu xe nhỏ/xa. Không nên hạ thấp thêm trước khi kiểm thử Single-Object Guard vì sẽ tăng detection yếu/false positive.

Vạch vẫn nên gần vuông góc luồng xe thật và nằm hoàn toàn trong Road Zone.

## Database

Migration:

```text
0030_auto_road_v0516
        ↓
0031_single_vehicle_v0517
```

Mong muốn:

```text
schema_version = 0.5.17
```

Migration chỉ nâng schema version, không xóa dataset, Run #3, `best.pt`, camera, vehicle events hoặc counting sessions.

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

Không dùng:

```powershell
docker compose down -v
```

Test:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\test.ps1
```

Contract mới:

```text
[Traffic AI] Single-Object BUS/TRUCK Guard V0.5.17
[OK] Single-Object BUS/TRUCK Guard V0.5.17
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
0031_single_vehicle_v0517
schema_version = 0.5.17
```

Sau khi mở web, `Ctrl+F5`, chạy lại chính clip có xe tải và quan sát:

```text
DET · track · road · gộp bus/truck · Tổng
```

Một xe tải đi qua chỉ được tạo **một** crossing event. Class cuối được chọn bằng temporal evidence + `best.pt` refiner.

## Phát hành

Sau khi chạy ổn vẫn chỉ một lệnh:

```powershell
.\scripts\publish.ps1
```

```text
→ test → build → push GitHub → tag v0.5.17 → GitHub Actions → Release
```
