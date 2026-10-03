# Kiểm tra Traffic AI V0.5.52

## Kết quả đã thực hiện

- **236 test functions offline đạt, 0 lỗi**: 202 AI và 34 backend.
- AI gồm 91 counting tests; 17 test chạy method worker thực trích từ AST, gồm 8 test Bicycle Context/frame và 6 Human Guard transaction tests. Các model response trong regression context được thay bằng fixture; không chạy inference thực.
- Backend gồm 13 benchmarking tests thuần và 21 helper/schema/geometry tests. Helper và Enum lấy từ source thực, schema dùng Pydantic thực; không kiểm thử HTTP endpoint/ORM qua harness này.
- 17 integration tests bị loại khỏi harness offline một cách tường minh; vẫn giữ nguyên trong full source để chạy với pytest trên môi trường dự án.
- Harness chỉ hỗ trợ phần pytest cần cho các tests đã chọn (`approx`, `raises`, temporary path và monkeypatch). Kết quả offline không phải kết quả chạy toàn bộ pytest.
- Python 3.12.14: compileall và AST parse 119 file Python thành công.
- **198 static checks đạt**: PipelineState 126 fields, worker payload/backend schema, pipeline start/finish contract, version/package/npm/Node, migration và các contract source V0.5.51/V0.5.52.
- 39 lời gọi constructor/method gate và 92 lời gọi method nội bộ được kiểm tra khớp signature.
- 66 migration có revision duy nhất, không vượt 32 ký tự, parent đầy đủ và một head `0066_observed_path_v0552`, parent `0065_span_shadow_v0551`.
- Contract V0.5.52 trong test.ps1 được gọi. Các regex literal của contract mới đã đối chiếu với source bằng Python; chưa chạy PowerShell.
- Bốn gate cùng dùng helper quỹ đạo thực; center proposal/commit/metadata khớp worker. Pending Human Guard giữ đủ rollback snapshot của anchor/heavy/two-wheel và membership rescue trước đó. Heavy track set và two-wheel UI counter được phục hồi khi loại event.
- Bảy vị trí gọi inference phụ dùng frame sạch; detector cũng đọc frame sạch, preview vẽ trên bản copy độc lập.
- Source text UTF-8: 176 file đọc được; giữ 3 image assets. Backend entrypoint đạt kiểm tra cú pháp Bash.
- Toàn bộ 177 file của full source V0.5.51 được giữ trong bản mới. Bổ sung test_worker_context.py và migration 0066; ZIP có 179 file, không chứa cache, model weights hay snapshot đầu vào.

## Kiểm tra quy trình Release

**30 kiểm tra đạt**, được tách rõ theo phạm vi: 13 kiểm tra thực thi, 3 kiểm tra cú pháp Bash, 12 kiểm tra static YAML/publisher và 2 fixture mô phỏng bằng Python.

Đã thực thi các bước Bash Verify VERSION và Build release artifacts lấy trực tiếp từ release.yml trong Git repository cô lập. Đúng tag/version/HEAD đạt; sai tag/version/HEAD bị chặn. ZIP, TAR.GZ và README chứa byte từ tag dù working tree có README khác. Ba SHA256 khớp SHA256SUMS.

Đã dùng bare repository local để kiểm tra annotated tag/peeled commit, phân biệt tag chưa tồn tại với lỗi lookup và fetch giữ đúng tag object khi retry. Fixture chọn workflow loại sai tag/SHA/event và giữ run phù hợp mới nhất; fixture push URL đối chiếu repository đích. Hai fixture này là mô phỏng, không thực thi PowerShell.

Đã parse ba workflow YAML, kiểm tra bash -n cho ba bước Bash của release.yml. Publish đọc VERSION, chuẩn hóa rồi test trước commit/push, chờ đúng tag/commit/push, tạo artifact từ tag và bổ sung Release assets tạo dở theo kiểm tra source. Không đẩy source, tạo tag remote hay tạo GitHub Release thật trong phiên đóng gói.

## Regression V0.5.52

Thêm 19 tests: 9 counting, 2 guard transaction và 8 worker context/frame. Nội dung kiểm tra endpoint detour, dead-band crossing thật, duplicate/stale frame, alias merge, center IN → OUT → IN, proposal bị gate chính loại, rollback passage/counter/telemetry, pixel independence, evidence crossing-frame được xét trước quyết định, scan trùng frame và evidence đã tiêu thụ.

Các regression V0.5.51 về continuous approach, finite segment/Road Zone, Enum, passage merge và source-time ordering được giữ. Các HTTP/SQLite ORM tests V0.5.51 chưa chạy trong harness offline.

## Giới hạn môi trường đóng gói

Chưa thực hiện toàn bộ pytest với pinned dependencies, PowerShell parser/runtime, Docker build, frontend npm build/audit, migration PostgreSQL hay replay YOLO trên clip hoàn chỉnh. Máy không có pwsh/Docker và thiếu các dependency integration; truy cập npm registry bằng shell trả E403.

npm 12.2.0 được xác minh từ trang phát hành chính thức và đã pin tại packageManager, Docker, test.ps1 và ba workflow. npm 12.2.0 chưa được cài/chạy trong môi trường đóng gói. Pixel regression dùng NumPy 2.3.5 có sẵn; requirements-test khai báo NumPy 2.4.6 cho Python 3.14 CI nhưng pinned environment đó chưa được cài/kiểm thử ở đây.

Hai screenshot V0.5.51 được đọc và RAR giải nén 242 snapshot. Clip chưa tải được; không xác nhận F1/lọt/dư hay hai lỗi class của V0.5.52 bằng snapshot. Mốc đầu vào: GT149 / AI156 / khớp136 / lọt13 / dư20.

## Chạy kiểm tra đầy đủ và phát hành trên máy dự án

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Chạy lại clip với cùng vạch/Road Zone, tạo benchmark từ GT 149 tương thích và bấm Đối chiếu lại. Lệnh publish mặc định chạy bộ kiểm tra đầy đủ trước khi commit/push/tag/Release:

```powershell
.\scripts\publish.ps1
```

Hướng dẫn đăng nhập GitHub CLI và retry phát hành có trong README.md.
