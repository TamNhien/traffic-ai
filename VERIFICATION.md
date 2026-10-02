# Kiểm tra Traffic AI V0.5.51

## Kết quả thực hiện trong phiên đóng gói

- Python 3.12.14: compileall và AST parse toàn bộ 117 file Python thành công.
- **217 assertion tests offline đạt; 0 lỗi**.
- AI: 183 test, gồm 82 counting tests. 7 test sử dụng các method worker thực được trích từ AST để tránh import HTTP transport không có trong môi trường này.
- Backend: 34 test, gồm 13 test benchmarking thuần và 21 test helper/schema/geometry. Dedup helpers và Enum được lấy từ source thực; schema sử dụng Pydantic thực. Đây không phải kiểm thử endpoint/ORM.
- 17 test phụ thuộc integration được loại khỏi harness offline một cách tường minh. Các test vẫn có nguyên trong full source để chạy bằng pytest trên môi trường đầy đủ dependencies.
- Rà soát static source: 130 điều kiện đạt; các slot PipelineState, payload worker/start/finish và schema tương ứng khớp nhau. 35 lời gọi constructor/method của các gate đúng signature.
- 65 migration liên kết đầy đủ, revision ID duy nhất và không vượt 32 ký tự; một head `0065_span_shadow_v0551`, parent `0064_geometry_semantic_v0550`.
- Metadata version ứng dụng, package và favicon cache là 0.5.51; contract V0.5.51 được gọi từ test.ps1.
- Các regex trong contract mới được đối chiếu với source bằng Python. Bash syntax entrypoint đạt. Source text giải mã UTF-8 thành công.
- Đã rà soát toàn bộ source và kiểm tra lại các lỗi tương tự ở passage merge, metadata, Enum, rollback và source-time ordering.

## Regression mới đã thêm

Các tests kiểm tra continuous approach, finite segment/Road Zone, reversal/jump, xác nhận trên frame khác nhau, track-loss sau jitter, clocks khi nối ID, rollback passage trước đó và rollback sau alias merge. Worker tests kiểm tra hoàn tác cả Primary Gate lẫn Anchor Span khi guard loại hoặc hết hạn.

Backend có regression tests SQLite thực cho Enum roundtrip, source-time ngược thứ tự gửi, reverse shadow, hơn 12 candidates, xe sát nhau và lượt crossing tiếp theo. Môi trường hiện tại thiếu SQLAlchemy/FastAPI/httpx2 nên các endpoint tests này chưa được chạy.

## Chưa thực hiện trong môi trường này

- Toàn bộ pytest bằng dependencies chính thức của dự án.
- PowerShell parser/runtime, Docker build, frontend npm build/audit.
- Chạy migration trên PostgreSQL thực.
- Replay YOLO/model weights trên clip hoàn chỉnh.

`clip1(10).mp4` không tải được vào phiên. Hai screenshot V0.5.50 và 244 snapshot RAR đã được đọc; không suy ra kết quả replay V0.5.51 từ snapshot.

## Kiểm tra đầy đủ trên máy chạy dự án

```powershell
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Sau đó chạy lại clip với cùng vạch/Road Zone, tạo benchmark cho session mới từ GT 149 hiện có và bấm Đối chiếu lại. Mốc đầu vào V0.5.50: GT149 / AI155 / khớp136 / lọt13 / dư19. Chưa xác nhận mốc đầu ra V0.5.51.
