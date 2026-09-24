# Traffic AI V0.5.16 — Auto Road-Zone Calibration 🚗🛣️✨

V0.5.16 tiếp tục từ V0.5.15-R1 và giải quyết điểm nghẽn còn lại khi detector/ByteTrack đã thấy nhiều xe nhưng `road = 0` hoặc số `loại ngoài lòng đường` tăng cao: **Road Zone đặt thủ công không phủ đúng luồng xe thực tế**.

Bản này giữ nguyên Hybrid Recall (`YOLO26s pretrained` detect/track toàn khung + `best.pt` đang kích hoạt refine class tại crossing), Strict Gate, Road Guard 2.0, Dataset/Annotation Studio và model Run #3. Không xóa dataset, training run hay model.

## Auto Road-Zone mới

Trong lúc AI chạy, worker thu thập anchor của các track **đang thật sự chuyển động**. Track đứng/đỗ bị loại bằng điều kiện displacement tối thiểu. Khi đủ dữ liệu, Dashboard hiện:

```text
calib 6T/143P
```

- `T` = số track chuyển động dùng để học vùng đường.
- `P` = số điểm quỹ đạo.

Khi đạt tối thiểu 4 moving tracks và 40 điểm, nút sau được bật:

```text
✨ AI đề xuất theo luồng xe
```

AI sẽ:

1. Gom quỹ đạo chuyển động gần đây.
2. Ước lượng trục chuyển động chính của luồng xe, gộp được cả hai chiều IN/OUT.
3. Lấy envelope robust theo quantile để bỏ outlier/xe đỗ.
4. Tạo polygon 4 điểm bám hành lang xe thực sự chạy.
5. Đặt vạch đếm **vuông góc với hướng chuyển động chính**.
6. Hiện preview vùng xanh/vạch vàng trước khi lưu.

Sau khi xem đề xuất, bấm:

```text
✓ Dừng AI + áp dụng đề xuất
```

Hệ thống sẽ dừng phiên AI hiện tại, lưu Road Zone/vạch vào camera rồi bạn bấm `Chạy AI` để kiểm thử phiên mới. Nếu video đã chạy xong nhưng proposal đã được cache, nút vẫn có thể lấy và áp dụng đề xuất.

## Thuật toán fail-safe

Auto Road-Zone không tự lưu ngay khi vừa học xong. Proposal chỉ là bản xem trước. Backend vẫn dùng `validate_counting_geometry()` để chặn:

- polygon tự bắt chéo;
- vùng đường quá nhỏ;
- vạch quá ngắn;
- đầu vạch nằm ngoài Road Zone.

Nếu dữ liệu chưa đủ, API trả rõ số track/điểm hiện có thay vì đoán geometry.

## Runtime telemetry mới

Ví dụ:

```text
DET 12 · chưa ID 1 · track 11 · road 4 · seen 36 · calib 8T/226P · Tổng 19
```

Mục tiêu sau khi áp dụng Auto Road-Zone là `road` phản ánh đúng số track đang chạy trong lòng đường, trong khi xe đứng/đỗ hoặc xe ngoài lề vẫn có thể được detect nhưng không được cộng IN/OUT.

## Cấu hình mới

`.env.example`:

```env
AI_FLOW_CALIBRATION_HISTORY_FRAMES=1200
AI_FLOW_CALIBRATION_POINTS_PER_TRACK=180
```

`start.ps1` tự bổ sung hai biến này nếu `.env` cũ chưa có.

## Database

Migration mới:

```text
0029_hybrid_recall_v0515
        ↓
0030_auto_road_v0516
```

Migration chỉ nâng:

```text
schema_version = 0.5.16
```

Không thêm cột mới vì proposal được học runtime rồi lưu vào các cột `road_x1..road_y4` và `line_x1..line_y2` vốn đã có.

## Cập nhật trên máy

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

Test:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\test.ps1
```

Mong muốn có:

```text
[Traffic AI] Auto Road-Zone Calibration V0.5.16
[OK] Auto Road-Zone Calibration V0.5.16
```

Sau đó:

```powershell
.\scripts\start.ps1
```

Database:

```powershell
.\scripts\verify-database.ps1
```

Mong muốn:

```text
0030_auto_road_v0516
schema_version = 0.5.16
```

## Cách dùng Auto Road-Zone

```text
1. Chạy AI
        ↓
2. Để xe chạy qua khoảng 10–30 giây
        ↓
3. Chờ calib đạt ít nhất 4T/40P
        ↓
4. Bấm “✨ AI đề xuất theo luồng xe”
        ↓
5. Xem vùng xanh + vạch vàng đề xuất
        ↓
6. Bấm “✓ Dừng AI + áp dụng đề xuất”
        ↓
7. Chạy AI lại
        ↓
8. Kiểm tra DET / track / road / Tổng / IN / OUT
```

Nếu luồng xe thay đổi theo giờ/camera, có thể chạy đề xuất lại để cập nhật geometry.

## Phát hành

Sau khi chạy ổn vẫn chỉ một lệnh:

```powershell
.\scripts\publish.ps1
```

```text
→ test → build → push GitHub → tag v0.5.16 → GitHub Actions → Release
```
