# Traffic AI V0.5.51 — Verified Span + Event Ordering Closure 9.7

Nâng cấp trực tiếp từ full source V0.5.50. Đơn vị đếm là **lượt cắt vạch**: cùng một phương tiện quay lại và cắt vạch lần nữa vẫn được tính thêm một lượt.

## Benchmark đầu vào

Hai screenshot V0.5.50 được gửi cùng source ghi nhận:

| Chỉ số | V0.5.50 |
|---|---:|
| Ground truth | 149 |
| AI đếm | 155 |
| Khớp | 136 |
| Lọt không đếm | 13 |
| Đếm dư | 19 |
| Recall | 91.3% |
| Precision | 87.7% |
| F1 | 89.5% |
| Class đúng | 98.5% |

Đã đọc 244 snapshot trong `camera_1(20261002-122800).rar`, từ frame 3 tới frame 23454. `clip1(10).mp4` chưa được tải thành công vào môi trường làm bản này; snapshot không đủ để xác nhận lại toàn bộ quỹ đạo/timecode. Các con số trên là **kết quả đầu vào V0.5.50**, chưa phải kết quả replay V0.5.51.

## Thay đổi V0.5.51

### 1. Continuous Approach Span

Anchor sample gần vạch có thể nông hoặc lệch do bounding box, khiến cặp sample mới nhất bị loại dù track đã có quỹ đạo tiếp cận hợp lệ. Nhánh mới chỉ dùng mẫu trước đó khi toàn bộ chuỗi đo được tiến liên tục theo phía đích, trong history gap hiện có. Tổng chiều dài quỹ đạo phải đạt các giới hạn jump và normal motion hiện có; mọi sample phải ở Road Zone; một đoạn giữa hai sample liền kề phải giao **finite counting segment** thật.

Nhánh này luôn chờ hậu-vạch xác nhận. Timecode lấy từ cặp sample thực sự giao vạch, không lấy từ một đường nối xa tùy ý. Sample lặp cùng frame không tăng số xác nhận; sample nhảy lớn hoặc ra khỏi Road Zone hủy pending. Track mất sau khi anchor quay lại phía đối diện không được finalize.

### 2. Đồng bộ passage khi nối track

Primary Gate và Anchor Span giữ hướng/clock của passage mới nhất khi hợp nhất ID. Không gộp IN/OUT thành một tập hướng đã đếm suốt đời. Metadata crossing được giữ cùng passage tương ứng, tránh lấy thời điểm của track cũ đè lên event mới.

### 3. Hoàn tác Human Guard đầy đủ

Khi crossing bị Human Guard loại hoặc pending hết hạn, cả Primary Gate và Anchor Span được hoàn tác. Giữ lại hướng, cooldown và metadata của passage hợp lệ trước đó; xóa geometry pending của event bị loại. Một lần rollback lặp lại không trừ thêm lượt đã được chấp nhận. Track đang có transaction Human Guard chờ xử lý không được mở thêm geometry event để đè metadata/rollback của event trước.

Metadata dùng khi track mất được cập nhật sau class refinement trong frame đó, để lost-finalize không lấy class cũ trước refinement.

### 4. Event shadow theo đúng Enum và source time

Nhánh chống trùng CAR/TRUCK/BUS trước đây so `str(VehicleType.truck)` với `truck`, khiến Enum từ Pydantic/ORM không chạy đúng nhánh. V0.5.51 chuẩn hóa `.value`, giữ nguyên ngưỡng 0.85 giây / 0.050 của nhánh đã có.

Candidate search xét hai phía của timestamp video vì rescue, lost-finalize và Human Guard có thể gửi crossing muộn với timecode trước đó. Không cắt bỏ ở 12 candidate; lọc theo vehicle family và vùng tọa độ hữu hạn trước khi xét các guard đang có. Giữ các ngưỡng riêng cho direct, interpolated, rescued và hướng di chuyển.

### 5. Giữ các guard và giao diện hiện có

Road Zone, finite segment, long-gap/lineage rescue, direct/secondary/reverse/semantic shadow, Human/Rider Guard, Geometry Late Confirm và Bicycle Context tiếp tục được giữ. Không có thay đổi ngưỡng toàn cục trong bản này.

Camera Preview / Vehicle Count và Ground Truth / Benchmark Report tiếp tục cân 50/50; các danh sách lỗi vẫn có vùng cuộn riêng. Trace bổ sung số candidate/rescue của Continuous Approach Span để kiểm tra trên replay tiếp theo.

## Version / database

- `VERSION`, Frontend, Backend và AI Service: `0.5.51`.
- Alembic head: `0065_span_shadow_v0551`.
- Parent: `0064_geometry_semantic_v0550`.
- `schema_version`: `0.5.51`.
- Migration chỉ cập nhật schema version, không xóa dữ liệu hay GT.

## Kiểm tra và chạy trên Windows

Giải nén full source, chép source vào thư mục dự án đang dùng; giữ cấu hình `.env`, video, model weights và dữ liệu hiện có.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Mở **https://traffic-ai.test:8443**, nhấn `Ctrl + F5`, chạy lại đúng clip với cùng vạch và Road Zone. Tạo benchmark cho session mới, sao chép GT 149 từ benchmark tương thích rồi bấm **Đối chiếu lại**.

`test.ps1` có contract V0.5.51 và bộ regression tests mới cho span, passage merge, Human Guard rollback, Enum từ ORM, event gửi trái thứ tự source time và xe thật chạy sát nhau.

## Kết quả kiểm tra trong môi trường đóng gói

Chi tiết và giới hạn kiểm thử được ghi trong `VERIFICATION.md`. Kiểm tra thuật toán offline không thay thế toàn bộ pytest/Docker hoặc replay YOLO thực. Không ghi giả GT/AI/lọt/dư của V0.5.51.

## Phát hành GitHub

Sau khi replay và bộ kiểm tra trên máy chạy đạt yêu cầu:

```powershell
.\scripts\publish.ps1
```

Luồng phát hành hiện có tiếp tục chạy test, commit/push, tag theo `VERSION` và đóng gói GitHub Release.
