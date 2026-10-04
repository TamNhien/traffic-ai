# Kiểm tra Traffic AI V0.5.56

## Kết quả đã thực hiện

- **413 test functions offline đạt, 0 lỗi**: 350 AI và 63 backend.
- AI: 134 counting, 91 classification, 46 worker context, 18 guard, 17 tracking và các test thuần hiện có. 67 worker assertions chạy method/source section thực trích từ AST. Backend: 25 benchmarking và 38 helper/schema/geometry tests.
- **33 test HTTP/ORM chưa chạy trong môi trường tích hợp**: 3 AI và 30 backend. Ba kiểm tra endpoint/transport mới giữ trong full source; isolated review chạy helper transport trích AST với fixture, không phải HTTP/ORM thật.
- **35 regression/control mới**: 32 chạy offline, 3 thuộc nhóm integration trên. Counting8, classification10, guard5, tracking4, benchmarking4, backend helper1 và endpoint/transport3.
- **424 static source checks đạt**: PipelineState, payload/schema/version/cache/Node/npm, migration lineage, pending proof revalidation, competitive evidence, trace/export liên kết và release probe.
- **123 Python files** parse/compile thành công. 40 gate calls, 121 internal calls và 390 direct calls resolve được trong source khớp signature; không bao phủ mọi dynamic/framework-generated call.
- 70 migration có revision duy nhất, <=32 ký tự, parent đầy đủ, không cycle, chung lineage/head `0070_benchmark_evidence_v0556`, parent `0069_refine_admission_v0555`.
- Contract V0.5.56 được khai báo/gọi trong test.ps1; source predicates được đối chiếu bằng Python. Chưa chạy PowerShell parser/runtime.
- JSX parse đạt bằng Babel bundle có sẵn của Playwright, Node thực v24.19.0; mẫu JSX sai bị từ chối. Chưa kiểm chứng React imports/Vite bundle hoặc CSS/layout bằng browser.
- Backend entrypoint đạt bash -n. 17 script PowerShell đúng UTF-8 no-BOM/CRLF; source/config dùng LF. 180 text files giải mã UTF-8 đạt, giữ 3 image assets.
- Full source **183 file**, giữ toàn bộ 182 đường dẫn của ZIP V0.5.55 và thêm migration0070. Cache, model weights, video và snapshot đầu vào không nằm trong ZIP source.

Harness chạy test functions của source thực với các phần pytest tối thiểu (`approx`, `raises`, temporary path, monkeypatch). Worker/route helpers trích AST vì HTTP/ORM transport chưa cài; dependencies geometry/classification/human_guard, Pydantic và NumPy lấy từ source/môi trường thực. Model output trong regression là fixture. Các con số offline không thay thế toàn bộ pytest, HTTP integration hoặc model inference.

## Đối chiếu source V0.5.55

- Counting: cả8 regression mới thất bại trên module thực từ immutable ZIP .55; .56 đạt cả8. Bao phủ alias observation bên trong proof, Road Zone/finite/path/normal/approach, endpoint replacement, cập nhật crossing clock và finalize-lost limit.
- Classification: 6 trong10 kiểm tra mới phát hiện frame/source thua hoặc hòa vẫn được mượn làm bicycle consensus trên .55;4 control đạt. .56 đạt cả10, bộ classification tổng91.
- Guard:3 trong5 regression mới thất bại trên .55 — returning track tại/sau deadline hồi sinh pending và pending trace thiếu geometry;2 source-clock/expiry control đạt. .56 đạt cả5.
- Tracking:3 counterexample thất bại trên .55 — heading sát đường phân chia ngang/dọc nhảy cạnh, chuỗi đi đều đảo phía vạch, tốc độ sát cutoff nhảy chiều cao bbox. .56 đạt; positive control cắt vạch thật đạt trên cả hai phiên bản.
- Export:4 pure ZIP tests kiểm tra dựng lại scoring từ marks/events, giữ nguyên byte trace, trạng thái thiếu evidence, streamed cap và URL redaction. Metadata helper phân biệt benchmark snapshot với camera hiện tại. Read-only review chạy thêm transport fixture và fallback timeout/service-unavailable từ source thực trích AST; đây không phải thực thi HTTP endpoint.

Ngưỡng gate, Road Zone, consensus và dedup toàn cục giữ nguyên. Vị trí anchor hướng chéo thay đổi cần được replay; fixes không chứng minh van tại10:41 đã đổi thành car hay người dắt xe đạp tại04:49 được phát hiện.

## Release verifier

**38 kiểm tra đạt**:17 execution Git/workflow artifact cục bộ,16 static YAML/publisher/bootstrap,3 cú pháp Bash,2 fixture Python mô phỏng.

Bash Verify VERSION và Build release artifacts lấy trực tiếp từ release.yml chạy trong Git repository cô lập: đúng tag/version/HEAD đạt; sai tag/version/HEAD bị chặn. ZIP, TAR.GZ và README lấy byte từ tag, SHA256 khớp SHA256SUMS. Local bare Git kiểm tra annotated/peeled tag, absent khác unreachable, retry giữ tag object và checkout tag khi main đã tiến.

Probe local `show-ref` trên tag chưa tồn tại trả1; repository lỗi trả128. Source publish dùng quiet probe scoped rồi xử lý exit code; verifier thực thi native Git và kiểm tra source predicates, chưa chạy PowerShell. Chọn đúng tag/SHA/event và push URL được kiểm tra bằng fixture mô phỏng Python.

Không push source, tạo tag remote hay GitHub Release thật trong phiên đóng gói.

## Benchmark và giới hạn

Đầu vào screenshot **V0.5.55: GT149 / AI152 / khớp136 / lọt13 / dư16 / F1 90.4% / class đúng98.5% / 2 lỗi class**, session159/benchmark38. Đã xem222JPG; chuỗi scooter#19086 tại65.84–66.24s cung cấp dấu hiệu điểm bám nhảy cạnh và source hiện thực đúng cơ chế đó. Snapshot không có model scores/JSONL để xác định mọi nguyên nhân lọt/dư. **Chưa replay V0.5.56** và chưa khẳng định cải thiện số đo clip.

Chưa chạy toàn bộ pytest với pinned dependencies, HTTP/ORM integration, PostgreSQL concurrency/migration, PowerShell parser/runtime, Docker/npm build/audit, inference hay clip replay. Python thực3.12.14, NumPy2.3.5, Pydantic2.13.5; NumPy2.4.6 trong requirements-test chưa được chạy. npm12.2.0/Node26.10.0 pin trong Docker/CI; JSX parser dùng Node24.19.0 hiện có. npm12.2.0 được đối chiếu là latest trên npm CLI releases/npm Docs ngày04/10/2026.

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

Mở https://traffic-ai.test:8443, Ctrl+F5, replay cùng clip/vạch/Road Zone rồi tạo benchmark session mới từ GT149 tương thích. Bấm **Đối chiếu lại**, sau đó **Tải hồ sơ benchmark**. Publish đọc VERSION để phát hành v0.5.56; README có hướng dẫn đăng nhập GitHub CLI và retry.
