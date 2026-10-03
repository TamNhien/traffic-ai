# Traffic AI V0.5.52 — Observed Path, Clean Frame và Release tự động

Nâng cấp từ full source V0.5.51. Đơn vị đếm tiếp tục là **lượt cắt vạch**: cùng một phương tiện quay lại và cắt vạch lần nữa được tính thêm một lượt.

## Benchmark đầu vào

Hai screenshot V0.5.51, session 155 / benchmark 34, ghi nhận:

| Chỉ số | V0.5.51 |
|---|---:|
| Ground truth | 149 |
| AI đếm | 156 |
| Khớp | 136 |
| Lọt không đếm | 13 |
| Đếm dư | 20 |
| Recall | 91.3% |
| Precision | 87.2% |
| F1 | 89.2% |
| Class đúng | 98.5% |

Lọt gồm 5 anchor span, 3 gần vạch chưa span, 1 center-only và 4 cooldown. Hai lỗi loại được báo là bicycle → motorcycle ở 04:49.450 và car → truck ở 10:41.981. Worker đề xuất 243 event, backend loại trùng 87; tổng cuối là 156.

Đã đọc hai screenshot và giải nén 242 snapshot trong `camera_1(20261002-141243).rar`, từ frame 3 tới 23454. Clip hoàn chỉnh chưa tải được vào môi trường đóng gói. Các con số này là **đầu vào V0.5.51**; chưa có kết quả replay V0.5.52.

## Thay đổi V0.5.52

### Quỹ đạo thực và finite segment

Primary Gate, Verified Anchor Span, Heavy Center và Two-Wheel Center cùng sử dụng đoạn giao vạch giữa hai sample liền kề đã quan sát. Các sample trong dead band cũng được xét để tìm đoạn cắt thật. Không dùng đường nối hai điểm ổn định ở xa để suy ra crossing khi xe thực tế vòng quanh đầu vạch.

Crossing phải giao đoạn vạch hữu hạn. Các guard Road Zone, jump, cooldown, xác nhận hậu-vạch và lineage đang có tiếp tục áp dụng. Quan sát trùng hoặc cũ không tăng số lần xác nhận. Khi nối ID, history giữ một sample cho mỗi source frame và tính lại streak theo history thực.

### Center candidate và rollback

Worker lấy center candidate bằng `commit=False`, chỉ ghi passage sau khi Primary Gate chấp nhận. Candidate bị gate chính loại không làm mất lượt cắt vạch sau đó. Center rescuer giữ passage mới nhất, hỗ trợ chu kỳ IN → OUT → IN.

Nếu Human Guard loại hoặc pending hết hạn, Primary Gate, Anchor Span, Heavy Center và Two-Wheel Center được phục hồi về passage trước đó. Clock, hướng, rescue counter của center và telemetry liên quan được khôi phục cùng nhau; gọi rollback lặp không trừ thêm lượt hợp lệ.

### Model đọc frame sạch

Frame dùng cho detector, class refiner, Human/Rider Guard và Bicycle Context được tách khỏi frame dùng vẽ preview/snapshot. Chữ, bounding box và vạch overlay không lọt vào crop model, kể cả khi track trước đó đã được vẽ trong cùng frame.

### Bicycle Context theo đúng source frame

Evidence domain/general tại crossing được ghi trước quyết định cross-frame. Mỗi track/source frame chỉ chạy context scan một lần. Evidence đã tiêu thụ cho passage được xóa; lượt pre-scan muộn trong cùng frame không gieo lại evidence đã dùng.

Collection floor tôn trọng cấu hình XFRAME 0.08 thay vì chặn cứng ở 0.10. Điều kiện chấp nhận bicycle vẫn giữ đủ hai nguồn, hai frame, so sánh motorcycle aggregate và motor veto. Bản này không hạ ngưỡng chấp nhận toàn cục và chưa xác nhận sửa được hai lỗi loại trong benchmark nếu chưa replay.

### npm và quy trình phát hành

- Đồng bộ **npm 12.2.0** tại `packageManager`, frontend Dockerfile, lệnh kiểm tra và cả ba workflow GitHub Actions. Đây là bản stable mới nhất được kiểm tra ngày 03/10/2026: [npm releases](https://github.com/npm/cli/releases/tag/v12.2.0).
- Node.js tiếp tục dùng 26.10.0 trong Docker/CI và `.node-version`.
- Khai báo NumPy 2.4.6 trong test dependencies cho regression kiểm tra pixel; test CI vẫn tách khỏi stack inference.
- Publish kiểm thử source sau chuẩn hóa line endings, đối chiếu VERSION/package version, rồi commit/push/tag. Không sửa metadata phiên bản sau khi đã test.
- Chạy lại publish được khi source sạch và tag trỏ đúng HEAD. Không di chuyển hoặc ghi đè tag đã phát hành; thay đổi source mới phải tăng VERSION.
- Chờ đúng Release workflow theo tag, SHA và sự kiện push. Nếu workflow không xuất hiện hoặc không hoàn tất, GitHub CLI tạo/bổ sung Release trực tiếp từ tag đã kiểm thử.
- ZIP, TAR.GZ, README và SHA256 lấy đúng byte của tag. Fallback bổ sung đủ asset cho Release tạo dở và hoàn tất draft.
- Manual dispatch nhận tag bắt buộc, checkout đúng tag và xác minh version/commit trước khi test, đóng gói.

## Version / database

| Thành phần | Phiên bản |
|---|---|
| VERSION, Frontend, Backend, AI Service | 0.5.52 |
| Alembic head | `0066_observed_path_v0552` |
| Parent | `0065_span_shadow_v0551` |
| schema_version | 0.5.52 |

Migration chỉ cập nhật schema version, không xóa dữ liệu hay GT. Dashboard Camera Preview / Vehicle Count và Ground Truth / Benchmark Report tiếp tục dùng bố cục 50/50 với vùng cuộn riêng cho danh sách lỗi.

## Kiểm tra và chạy trên Windows

Giải nén full source vào thư mục dự án; giữ `.env`, video, model weights và dữ liệu đang dùng. Cần Docker Desktop chạy trước khi gọi bộ kiểm tra.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Mở **https://traffic-ai.test:8443**, nhấn `Ctrl + F5`, chạy lại đúng clip với cùng vạch và Road Zone. Tạo benchmark cho session mới, sao chép GT 149 từ benchmark tương thích rồi bấm **Đối chiếu lại**.

Để cập nhật npm trên Windows khi dùng frontend ngoài Docker, dùng Node.js 26.10.0 trở lên rồi chạy:

```powershell
npm install -g npm@latest
npm --version
```

Docker/CI cài bản pin 12.2.0 của bản source này để giữ môi trường phát hành nhất quán.

## Tự đẩy GitHub và tạo Release

Cần Git, GitHub CLI và Docker Desktop. Nếu chưa đăng nhập GitHub CLI, chạy một lần:

```powershell
gh auth login
gh auth setup-git
```

Nếu chưa cấu hình tác giả commit, đặt `git config --global user.name` và `git config --global user.email` bằng thông tin của bạn. Repository mặc định là `TamNhien/traffic-ai`, nhánh `main`; checkout đúng nhánh trước khi publish.

Lệnh phát hành:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\publish.ps1
```

Script tự đọc `VERSION`, chạy test, khởi tạo/kiểm tra repository, commit/push source, đẩy tag **v0.5.52** và tạo GitHub Release kèm ZIP, TAR.GZ, README, SHA256SUMS. Nếu bị gián đoạn, xử lý lỗi mạng/quyền truy cập rồi chạy lại cùng lệnh với source không đổi. Nếu tag đã phát hành nhưng source có thay đổi, cần tăng version trước lượt phát hành tiếp theo.

Đổi repository đích nếu cần:

```powershell
.\scripts\publish.ps1 -Owner TEN_GITHUB -Repository TEN_REPO
```

Script kiểm tra cả origin push URL để tránh đẩy sang repository khác. `-NoWait` chỉ đẩy source/tag rồi trả về; Release vẫn đang chờ Actions.

Để chủ động chạy lại workflow cho tag đã có trên GitHub:

```powershell
gh workflow run release.yml --repo TamNhien/traffic-ai -f tag=v0.5.52
```

Chi tiết kiểm tra đã thực hiện và các giới hạn của môi trường đóng gói nằm trong `VERIFICATION.md`.
