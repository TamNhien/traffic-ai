# Kiểm tra Traffic AI V0.5.54

## Kết quả đã thực hiện

- **333 test functions offline đạt, 0 lỗi**: 280 AI và 53 backend.
- AI gồm 114 counting, 68 classification, 32 worker context, 13 guard transaction và các test thuần hiện có. 48 assertion worker chạy method thực trích AST; backend gồm 18 benchmarking và 35 helper/schema/geometry tests.
- **27 test HTTP/ORM bị loại tường minh**: 3 AI và 24 backend. Bảy integration regression V0.5.54 nằm trong nhóm chưa chạy; vẫn được giữ trong full source để chạy bằng test.ps1.
- **61 regression mới** trong V0.5.54: 54 đã chạy offline, 7 HTTP/ORM chưa chạy. Phân bố: counting 12, classification 12, worker context 10, guard 5, trace 3, backend 17, benchmarking 2.
- **284 static source checks đạt**: PipelineState 126 fields, event/start/finish payloads, backend/AI schemas, version/cache/Node/npm, migration lineage, gate và semantic admission/trace contracts.
- AST parse **121 file Python** đạt; compileall các thư mục app/tests của hai service và backend/alembic đạt trên Python 3.12.14. Backend entrypoint đạt bash -n.
- 40 gate calls, 114 internal calls và 364 direct calls resolve được trong source khớp signature. Không bao phủ mọi dynamic/framework-generated call; static audit không thay execution.
- 68 migration có revision duy nhất, <=32 ký tự, parent đầy đủ, không cycle và cùng một lineage/head `0068_gate_semantics_v0554`, parent `0067_candidate_evidence_v0553`.
- Contract V0.5.54 được khai báo/gọi trong test.ps1; toàn bộ source predicates V0.5.52/V0.5.53/V0.5.54 đối chiếu bằng Python đạt. Chưa chạy PowerShell parser/runtime.
- JSX parse đạt bằng Babel bundle có sẵn của Playwright 1.62.1, Node thực v24.19.0; mẫu JSX sai được từ chối. Không kiểm chứng React imports/Vite bundle, stylesheet hoặc layout bằng browser.
- 178 text files giải mã UTF-8 thành công, giữ 3 image assets. Full source có 181 file: giữ toàn bộ 180 đường dẫn của V0.5.53, thêm migration 0068. Không đóng gói cache, video, model weights hoặc snapshot đầu vào.

Harness offline chạy test functions của source thực với các thành phần pytest tối thiểu (`approx`, `raises`, temporary path, monkeypatch). Worker/route helpers được trích từ AST vì HTTP/ORM transport chưa cài; dùng geometry/classification/human_guard dependencies thực, Pydantic và NumPy thực. Model output trong regression được cung cấp bằng fixture. Đây không phải kết quả toàn bộ pytest hay inference video.

## Regression V0.5.54

Các regression mới kiểm tra Road Zone qua bracket/quỹ đạo quan sát, pending hết hạn không tái mở history cũ, external chronology và alias rearm/cooldown; hard center bound, confidence hợp lệ, callback trùng, temporal winning-frame/source evidence và passage consumption; finite-gate refine budget, context veto và Human Guard commit; semantic trace/proposal status/EOF expiry; session/camera ownership, late persisted counts, stale start/stop và class mismatch trace; closest spatial benchmark candidate.

Counting regression mới được chạy trên code thực từ ZIP V0.5.53: **11 trong 12 test tái hiện lỗi cũ**, test còn lại là positive chronology control đạt trên cả hai phiên bản. Không dùng timestamp GT để ép class, không thay các threshold chấp nhận/dedup toàn cục.

Fast/Bracket/Late/adaptive là diagnostic ở bước candidate validation; không diễn giải chúng như tổng event đã persisted. Context rescue được commit sau Human Guard; audit phân biệt proposal acceptance với accepted crossing.

## Release verifier

**30 kiểm tra đạt**: 13 thực thi Git/workflow artifact, 3 cú pháp Bash, 12 static YAML/publisher và 2 fixture Python mô phỏng.

Các bước Bash Verify VERSION và Build release artifacts lấy trực tiếp từ release.yml chạy trong Git repository cô lập. Đúng tag/version/HEAD đạt; sai tag/version/HEAD bị chặn. ZIP, TAR.GZ và README lấy byte từ tag, không lấy working tree đã thay đổi; các SHA256 đối chiếu với SHA256SUMS.

Bare repository local kiểm tra annotated tag/peeled commit, tag chưa tồn tại khác lỗi lookup, fetch giữ đúng tag object khi retry và checkout tag khi main đã tiến. Fixture Python mô phỏng chọn đúng tag/SHA/event và push URL; không phải execution PowerShell. Không push source, tạo tag remote hay tạo GitHub Release thật trong phiên đóng gói.

## Bằng chứng hình ảnh và giới hạn

Đã đọc hai screenshot V0.5.53, giải nén an toàn **233 JPG**, tổng **80.205.092 byte**, kích thước 1440 × 811, frame 3–23454. Contact sheets bao phủ 233 ảnh; đã xem crop đại diện 01:18 và 04:49. Snapshot 01:18 cho thấy người áo đỏ đội mũ trên xe máy; snapshot 04:49 cho thấy người dắt xe đạp có giỏ cạnh xe máy đứng yên. Overlay snapshot được vẽ trước context crossing, không chứng minh điểm/nhánh quyết định context. Hai class errors còn lại không hiển thị trong phần screenshot đã gửi.

Mốc đầu vào **V0.5.53: GT149 / AI154 / khớp136 / lọt13 / dư18 / F1 89.8% / class đúng 97.1% / 4 lỗi class**. Chưa có replay V0.5.54. Không tạo kết quả benchmark mới từ regression fixtures.

Chưa thực hiện toàn bộ pytest với pinned dependencies, PowerShell parser/runtime, Docker/frontend npm build/audit, HTTP/ORM integration, migration PostgreSQL, model inference hay replay clip đầy đủ. Môi trường không có pytest/FastAPI/SQLAlchemy/httpx2/OpenCV/Torch/Ultralytics/pwsh/Docker. Python thực là 3.12.14, NumPy 2.3.5, Pydantic 2.13.5; NumPy 2.4.6 của requirements-test chưa được cài/chạy ở đây. npm 12.2.0/Node 26.10.0 giữ pin Docker/CI; chưa build môi trường đó trong phiên.

## Đầy đủ lệnh trên máy dự án

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Kiểm tra
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push, tạo tag và GitHub Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl + F5, replay đúng clip/cùng vạch/Road Zone rồi tạo benchmark session mới từ GT 149 tương thích. Publish đọc VERSION để phát hành v0.5.54; README có hướng dẫn auth GitHub CLI và retry.
