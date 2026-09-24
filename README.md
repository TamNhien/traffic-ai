# Traffic AI V0.5.18 — Crossing Engine 6.0 🚗⚡

V0.5.18 tiếp tục từ V0.5.17 và tập trung vào **độ chính xác của thời điểm cắt vạch + telemetry đếm**. Clip kiểm thử người dùng cung cấp ở V0.5.17 kết thúc với hệ thống báo **Tổng 11 · IN 5 · OUT 6**, nhưng có tới **9 lượt bị ghi là `cứu`**. Điều đó không có nghĩa 9 xe thật sự mất track dài: engine cũ coi mọi crossing có khoảng cách frame > 1 là rescue, kể cả trường hợp track đi qua dead-band quanh vạch rất bình thường.

> Con số 11/5/6 ở trên là **kết quả hệ thống trên clip**, không phải ground-truth đã kiểm đếm thủ công độc lập.

## Crossing Engine 6.0

V0.5.18 tách crossing thành ba mức:

```text
DIRECT
  hai observation liên tiếp nằm hai phía vạch

INTERPOLATED
  track liên tục / gần liên tục,
  có frame trong dead-band hoặc hụt tối đa vài frame

RESCUED
  có khoảng mất detection/tracking thật sự dài,
  history mới phải nối qua gap
```

Mặc định:

```env
AI_GATE_INTERPOLATION_GAP=3
```

Nghĩa là gap quan sát tối đa 3 frame vẫn được coi là nội suy ngắn; dài hơn mới được tính `rescued`.

### Local crossing segment

Engine cũ lấy một điểm ổn định ở phía cũ và điểm hiện tại rồi dựng một đoạn dài để tìm giao điểm. V0.5.18 trước tiên tìm **cặp observation cục bộ gần vạch nhất** để nội suy giao điểm. Chỉ khi track quá thưa mới fallback sang history dài.

Điều này giúp:

- đếm sát thời điểm xe vừa cắt vạch hơn;
- giảm telemetry `cứu` giả;
- giữ Strict Finite Gate;
- giữ Road Guard, không đếm xe ngoài lòng đường;
- giữ Hybrid Recall, Auto Road-Zone và Single-Object BUS/TRUCK Guard.

## Tổng xe hiển thị rõ hơn

Panel `VEHICLE COUNT` có thêm:

```text
Tổng lượt cắt vạch
IN
OUT

Trực tiếp
Nội suy
Cứu qua gap
```

`Tổng = IN + OUT` vẫn là số lượt xe cắt vạch của phiên hiện tại. Breakdown crossing chỉ giải thích **engine đã xác nhận lượt đó theo cách nào**, không cộng thêm xe.

Ví dụ mục tiêu telemetry sau nâng cấp:

```text
Tổng 11 · IN 5 · OUT 6
Trực tiếp 4 · Nội suy 6 · Cứu 1
```

thay vì mọi dead-band crossing bị dồn vào `cứu`.

## Không thay đổi dataset/model

V0.5.18 không xóa hoặc train lại:

```text
datasets/
training-runs/
models/
best.pt
```

Model Run #3 đang kích hoạt vẫn được giữ. Confidence hiện tại `0.05` cũng không bị thay đổi bởi migration này.

## Database

Migration mới:

```text
0031_single_vehicle_v0517
        ↓
0032_crossing_engine_v0518
```

Mong muốn:

```text
schema_version = 0.5.18
```

Migration chỉ nâng `schema_version`, không xóa dữ liệu.

## Cập nhật

Chép source đè vào:

```text
D:\LienThongDH\DoAn\traffic-ai
```

Giữ:

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
[Traffic AI] Crossing Engine 6.0 V0.5.18
[OK] Crossing Engine 6.0 V0.5.18
```

Chạy:

```powershell
.\scripts\start.ps1
```

Kiểm tra database:

```powershell
.\scripts\verify-database.ps1
```

Mong muốn:

```text
0032_crossing_engine_v0518
schema_version = 0.5.18
```

Sau đó `Ctrl + F5` trên trình duyệt.

## Kiểm thử clip hiện tại

Khi chạy lại đúng clip đã gửi, theo dõi:

```text
DET
track
road
Tổng / IN / OUT
trực tiếp
nội suy
cứu
loại ngoài lòng đường
```

Nếu `Tổng` vẫn sai so với kiểm đếm thủ công, bước tiếp theo là tạo **Ground-truth Counting Benchmark** cho chính clip này: đánh dấu thời điểm từng xe cắt vạch và so event-by-event thay vì chỉ nhìn tổng cuối clip.

## Phát hành

Sau khi chạy ổn vẫn chỉ một lệnh:

```powershell
.\scripts\publish.ps1
```

```text
→ test → build → push GitHub → tag v0.5.18 → GitHub Actions → Release
```

## Kiểm thử khi đóng gói

```text
Python compile                    ✅
AI Service unit tests             61/61 ✅
Backend unit tests                 7/7 ✅
Crossing direct                   ✅
Crossing dead-band interpolation  ✅
Small-gap interpolation           ✅
Long-gap rescue                   ✅
Strict Road Zone                  ✅
BUS/TRUCK guard                   ✅
Alembic revision safety           ✅
Sensitive/runtime artifact scan   ✅
```

Frontend `npm install` trong môi trường đóng gói bị timeout mạng nên không ghi Vite build PASS giả. `./scripts/test.ps1` trên máy Windows/Docker của dự án vẫn là vòng xác nhận cuối cho frontend + Docker images.
