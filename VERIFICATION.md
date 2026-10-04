# Kiểm tra Traffic AI V0.5.55

## Kết quả đã thực hiện

- **381 test functions offline đạt, 0 lỗi**: 323 AI và 58 backend.
- AI: 126 counting, 81 classification, 46 worker context, 13 guard và các test thuần hiện có. 62 worker assertions chạy method/source section thực trích từ AST. Backend: 21 benchmarking và 37 helper/schema/geometry tests.
- **30 test HTTP/ORM chưa chạy**: 3 AI và 27 backend, gồm 3 ORM regression mới V0.5.55. Giữ toàn bộ trong full source để chạy trên môi trường dự án.
- **51 regression mới**: 48 chạy offline, 3 ORM chưa chạy. Counting 12, classification 13, worker context 14, trace 4, backend helper/ORM 5, benchmarking 3.
- **364 static source checks đạt**: PipelineState 126 fields, event/start/finish payload, schema/version/cache/Node/npm, migration lineage, semantic admission, trace provenance, query lock/refresh source predicates và release bootstrap.
- **122 Python files** parse/compileall thành công. 40 gate calls, 120 internal calls và 375 direct calls resolve được trong source khớp signature; không bao phủ mọi dynamic/framework-generated call.
- 69 migration có revision duy nhất, <=32 ký tự, parent đầy đủ, không cycle, chung lineage/head `0069_refine_admission_v0555`, parent `0068_gate_semantics_v0554`.
- Contract V0.5.55 được khai báo/gọi trong test.ps1; source predicates được đối chiếu bằng Python. Chưa chạy PowerShell parser/runtime.
- JSX parse đạt bằng Babel bundle có sẵn của Playwright, Node thực v24.19.0; mẫu JSX sai bị từ chối. Chưa kiểm chứng React imports/Vite bundle, CSS/layout bằng browser.
- Backend entrypoint đạt bash -n. 17 script PowerShell đúng UTF-8 no-BOM/CRLF; source/config dùng LF. 179 text files giải mã UTF-8 đạt, giữ 3 image assets.
- Full source **182 file**, giữ toàn bộ 181 đường dẫn của ZIP V0.5.54 và thêm migration 0069. Cache, model weights, video và snapshot đầu vào không nằm trong ZIP source.

Harness chạy test functions của source thực với các phần pytest tối thiểu (`approx`, `raises`, temporary path, monkeypatch). Worker/route helpers trích AST vì HTTP/ORM transport chưa cài; dependencies geometry/classification/human_guard, Pydantic và NumPy lấy từ source/môi trường thực. Model output trong regression là fixture. Các con số offline không thay thế toàn bộ pytest, HTTP integration hoặc model inference.

## Đối chiếu source V0.5.54

- Counting: 12 test mới chạy trên immutable ZIP .54; 10 phát hiện lỗi, 2 control hợp lệ đạt cả hai phiên bản. .55 đạt cả 12.
- Classification: 12 kiểm tra dùng API có sẵn trên .54; 8 thất bại (target bound/competing four-wheel evidence), 4 control đạt; .55 đạt cả 12. Tổng bộ classification .55 là 81.
- Worker: 14 regression/control mới; .54 thất bại 9, đạt 5 control; .55 đạt cả 14. Budget starvation test chạy các section class-work thật từ run(), kiểm tra periodic-first làm crossing sau mất slot. No-opinion/cache tests kiểm tra source clock và expiry thực.
- Backend: 3 regression timestamp/permutation đều thất bại trên .54; 2 kiểm tra provenance cũng phát hiện thiếu scope. .55 giữ nguyên temporal matching objective và dedup windows.
- Trace: dùng module thật từ ZIP .54 tái hiện evidence track cần xem bị last-eight của track khác đẩy mất và pending không cập nhật khi kết quả guard đến ngoài cửa sổ. .55 chọn track trước bound, cập nhật cùng identity và giữ diagnostic counters trong cửa sổ gốc.

Regression không dùng timestamp GT để ép class hay tự tạo benchmark video mới. Ngưỡng phân loại, gate và dedup toàn cục được giữ. Van GT car/model truck vẫn cần replay và kiểm tra taxonomy; source fixes không chứng minh riêng event đó đã đổi thành car.

## Release verifier

**34 kiểm tra đạt**: 14 execution Git/workflow artifact cục bộ, 3 cú pháp Bash, 15 static YAML/publisher/bootstrap, 2 fixture Python mô phỏng.

Bash Verify VERSION và Build release artifacts lấy trực tiếp từ release.yml chạy trong Git repository cô lập: đúng tag/version/HEAD đạt; sai tag/version/HEAD bị chặn. ZIP, TAR.GZ và README lấy byte từ tag, các SHA256 khớp SHA256SUMS. Local bare Git kiểm tra annotated/peeled tag, absent khác unreachable, retry giữ tag object và checkout tag khi main đã tiến.

Bổ sung kiểm tra quiet probes của github-init và thực thi Git local thiếu origin → add origin. Đây là kiểm tra native Git cùng source predicates, chưa thực thi PowerShell bootstrap. Fixture chọn đúng tag/SHA/event và push URL là mô phỏng Python.

Không push source, tạo tag remote hay GitHub Release thật trong phiên đóng gói.

## Benchmark và giới hạn

Mốc đầu vào screenshot **V0.5.54: GT149 / AI152 / khớp136 / lọt13 / dư16 / F1 90.4% / class đúng98.5% / 2 lỗi class**. Các snapshot đã xem ở lượt trước cho thấy vấn đề cần rà soát tại xe đạp, van và chuỗi proposal đảo hướng gần đầu vạch; snapshot không cung cấp model context scores hoặc quỹ đạo video đầy đủ. Bản nâng cấp này dùng source regression và benchmark đầu vào đó; **chưa replay V0.5.55**.

Chưa chạy toàn bộ pytest với pinned dependencies, HTTP/ORM integration, PostgreSQL concurrency/migration, PowerShell parser/runtime, Docker/npm build/audit, model inference hay clip replay. Python thực 3.12.14, NumPy 2.3.5, Pydantic 2.13.5; NumPy 2.4.6 trong requirements-test chưa được chạy. npm 12.2.0/Node26.10.0 được pin trong Docker/CI; JSX parser dùng Node24.19.0 hiện có. FOR UPDATE/identity-map refresh mới đã có static/query regression trong source; cần kiểm chứng concurrency PostgreSQL trên máy dự án.

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

Mở https://traffic-ai.test:8443, Ctrl + F5, replay cùng clip/vạch/Road Zone rồi tạo benchmark session mới từ GT149 tương thích. Publish đọc VERSION để phát hành v0.5.55; README có hướng dẫn đăng nhập GitHub CLI và retry.
