# Traffic AI V0.5.50 — Geometry + Semantic Shadow Closure 9.6

V0.5.50 tiếp tục trực tiếp từ replay V0.5.49 trên `clip1(9).mp4` và bộ snapshot `camera_1(20260930-115201).rar`.

Mốc đầu vào đã xác nhận trên dashboard V0.5.49:

- **Ground truth:** 149
- **AI đếm:** 155
- **Khớp:** 136
- **Lọt:** 13
- **Dư:** 19
- **Recall:** 91.3%
- **Precision:** 87.7%
- **F1:** 89.5%
- **Class đúng:** 98.5%

Benchmark #32 cho thấy hai nhóm cần xử lý tiếp: một số crossing thật bị chặn vì chưa đủ hậu-vạch/cooldown, trong khi **6 event dư nằm rất sát một GT đã khớp và cùng điểm cắt**. V0.5.50 xử lý đúng hai nhánh này mà không hạ toàn cục các ngưỡng Road Zone/Gate.

## Điểm chính V0.5.50

### 1. Geometry-Backed Late Confirm

Primary Gate trước đây loại ngay crossing ngắn nếu chỉ có một sample phía đích và không đạt `Fast-confirm`/`Bracket-confirm`. V0.5.50 trì hoãn quyết định loại cho tới khi đã kiểm tra đủ:

- giao với **finite counting segment**;
- Road Zone/corridor;
- chuyển động theo pháp tuyến;
- độ sâu hai phía;
- giới hạn jump;
- gap tối đa ngắn.

Chỉ khi toàn bộ geometry mạnh mới được `Late-confirm`; jitter xiên/line-parallel vẫn fail-closed. Runtime mặc định:

```text
AI_GATE_LATE_GEOMETRY_CONFIRM=1
AI_GATE_LATE_GEOMETRY_CONFIRM_MIN_NORMAL_RATIO=0.48
AI_GATE_LATE_GEOMETRY_CONFIRM_MAX_JUMP_RATIO=0.08
AI_GATE_LATE_GEOMETRY_CONFIRM_MIN_SIDE_RATIO=0.008
AI_GATE_LATE_GEOMETRY_CONFIRM_MAX_GAP=3
```

Telemetry mới: **Late-confirm**.

### 2. Semantic Family Shadow Closure

V0.5.49 đã chặn direct/secondary shadow khi **class giống hệt nhau**. Benchmark #32 vẫn còn các event dư rất sát GT vì cùng một phương tiện có thể đổi class khi ID switch, ví dụ:

- `motorcycle ↔ bicycle`;
- `car ↔ truck/bus`.

V0.5.50 thêm guard **same-family class-wobble** với bán kính cực nhỏ và cửa sổ method-aware. Exact-class dense traffic vẫn đi qua các guard cũ; direct/direct khác class chỉ bị gộp khi gần như trùng điểm và thời gian rất ngắn. Opposite-direction chỉ được gộp khi có secondary method, không gộp direct/direct ngược hướng.

Telemetry mới: **FP semantic-shadow**.

### 3. Direct → Secondary ultra-spatial tail

Nhánh exact-class `direct ↔ rescued/interpolated` được nới **chỉ phần bán kính ultra-spatial** từ V0.5.49, không mở generic signature và không mở direct/direct bình thường. Mục tiêu là đóng phần đuôi của nhóm `spatial_duplicate_near_gt` nhưng vẫn bảo vệ xe thật chạy sát nhau.

### 4. Giữ nguyên các precision/recall guard trước

V0.5.50 vẫn giữ:

- Immediate Span không bypass cooldown trực tiếp;
- Post-Confirm / track-lost finalize của Verified Anchor Span;
- Canonical-Lineage long-gap rescue guard;
- same-track repeat / direction flip / secondary shadow / reverse shadow;
- Human Guard, Rider Guard, Road Zone;
- passage-cycle state và adaptive cooldown;
- giao diện Camera Preview / Vehicle Count 50/50;
- Ground Truth / Benchmark Report 50/50 và `scrollbar-gutter` ổn định.

## Version / database

- `VERSION = 0.5.50`
- Frontend / Backend / AI Service = `0.5.50`
- Alembic head: `0064_geometry_semantic_v0550`
- `schema_version = 0.5.50`

## Kiểm tra

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
```

Khởi động:

```powershell
.\scripts\start.ps1
```

Mở:

```text
https://traffic-ai.test:8443
```

Sau đó `Ctrl + F5`, chạy lại đúng `clip1(9).mp4`, tạo benchmark từ GT 149 đã có và bấm **Đối chiếu lại**.

## Phát hành GitHub

Khi benchmark V0.5.50 đạt yêu cầu:

```powershell
.\scripts\publish.ps1
```

`publish.ps1` tiếp tục chạy test → commit/push → tag theo `VERSION` → GitHub Actions → GitHub Release → upload ZIP/README.

## Lưu ý benchmark

Các thay đổi trên được xây từ benchmark V0.5.49 **149 / 155 / khớp 136 / lọt 13 / dư 19** và các regression test tương ứng. Source không ghi giả kết quả replay V0.5.50; số **GT/AI/khớp/lọt/dư** cuối cùng phải được xác nhận bằng replay thực trên máy có YOLO/GPU/model weights.
