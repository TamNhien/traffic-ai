# Kiểm tra Traffic AI V0.5.60

## Kết quả đã thực hiện

### V0.5.60 — lỗi được tái hiện và sửa

- Tái hiện đúng lỗi người dùng gửi: `test_v0554_stale_stop_preserves_newer_active_camera` trả 502 vì `SimpleNamespace(status_code=200)` không có `json()`.
- Sửa route stop theo hướng backward-compatible: chỉ parse JSON khi `response.json` tồn tại và callable; response HTTP thực vẫn đi qua validation object như V0.5.59.
- Thêm 2 regression V0.5.60: legacy status-only 200 phải stop bình thường; 200 có JSON không phải object vẫn phải bị từ chối.
- Không thay đổi AI counting/tracking/classification hoặc benchmark scoring.

- **637 pytest cases đạt, 0 lỗi trong môi trường đóng gói**: **521 AI + 116 backend**. Backend dùng SQLite memory và test-only shim `httpx2 -> httpx`; AI dùng cùng shim và các `AI_*_ROOT` tạm ghi được dưới `/mnt/data`. Đây là kiểm tra source logic, không thay thế Docker với dependency pin `httpx2==2.13.0`.
- Riêng lỗi người dùng gửi và 2 regression V0.5.60: **3/3 pass** (`stale_stop`, legacy 200 không có `json()`, JSON không phải object vẫn bị từ chối).
- **129 Python files** parse AST thành công; frontend `package.json` parse JSON thành công. Không đổi JSX/AI counting code ngoài version string.
- **74 migrations** có revision duy nhất, tối đa 32 ký tự, parent đầy đủ, không cycle; head duy nhất `0074_stop_ack_compat_v0560`, parent `0073_trace_identity_v0559`. Migration mới chỉ cập nhật schema_version lên 0.5.60; downgrade về 0.5.59.
- Giữ `Assert-TraceIdentityV0559Contract` và thêm `Assert-StopAckCompatibilityV0560Contract` trong `test.ps1`; contract mới kiểm tra fallback 200 không có `json()` và regression V0.5.60. Chưa chạy PowerShell parser/runtime trong môi trường đóng gói.
- JSX parse bằng Babel bundle Playwright đạt và mẫu JSX sai bị từ chối; frontend JSON/config hợp lệ. Chưa chạy Vite/React import resolution hoặc browser layout.
- Backend entrypoint giữ nguyên; **17 script PowerShell UTF-8 no-BOM/CRLF**, các text source/config còn lại LF. Full source **189 file: 186 text UTF-8 và 3 binary assets** sau khi thêm migration 0074; 17 script PowerShell giữ CRLF không BOM.

Harness chạy test functions source thực với phần pytest tối thiểu (`approx`, `raises`, temporary path, monkeypatch). Worker/backend helpers được trích AST vì môi trường không có HTTP/ORM dependencies; classification/counting/tracking/Human Guard, Pydantic và NumPy dùng module thực. Dispatcher HTTP dùng transport fixture điều khiển. Model opinions trong regression là fixture; không chạy model inference. Các số offline không thay thế full pytest trong Docker.

89 Python functions mới gồm 12 tracking, 23 class/context, 26 dispatcher/guard/runtime, 24 trace/export/transport/geometry-metadata và 4 backend stop-owner checks. Các phép đối chiếu source, frontend và release bên dưới là kiểm tra riêng, không cộng vào 602 Python functions.

## Đối chiếu source V0.5.58 thực tế

Baseline khôi phục từ full source ZIP đã giao: 185 file, 388,199 byte, SHA256 `e449bcdd9ad7b3bfe6e10e84ff2776ea44923f3ebf53b72639961c1a92fdb811`. CRC và từng byte source khôi phục khớp ZIP. Không dùng source lịch sử đã sửa để làm oracle.

### Identity xe hai bánh

**48/48 tracking functions đạt**: giữ 36 baseline và thêm 12. Trên source .58, 10 control đạt và 2 regression thất bại bằng AssertionError: rider hijack và duplicate-clock bbox evidence. Không dùng TypeError do thiếu keyword mới làm bằng chứng lỗi.

Ảnh và trace cùng xác nhận canonical328328 ghép một xe khác ở f18860. Repro actual center/bbox/velocity: .58 trả canonical328328/stitchedTrue, anchor453.1407; .59 trả raw331821/stitchedFalse và giữ heading rider trước. Fragment thật f18872 của xe sau vẫn stitch được. Giữ same-raw reversal, same-direction fragment, bbox uncertainty, no-bbox legacy callers, unestablished motion và four-wheel perspective behavior.

74/1275 known stitch trong trace thỏa rejection predicate mới; không coi đó là 74 lỗi đã chứng minh hoặc dự đoán số event sau replay. Xe thật đảo chiều mạnh đồng thời đổi raw ID có thể bắt đầu canonical mới. Dao động bbox/heading trong cùng raw ID chưa được kết luận đã sửa.

### Class source clock và audit

**114 classification + 79 worker-context functions đạt**. Thêm 11 classification clock checks, 4 worker-clock checks và 8 observability checks. Differential source .58 thực tế chứng minh 4 semantic regressions và giữ 2 control: stale primary truck, merged primary clock, newest qualified refiner clock và expired refiner confidence.

Chuỗi truck thực cuối frame100 rồi car101–125 khiến .58 gia hạn lock tới121 bằng stable history; .59 giữ actual primary source100, hết TTL30 tại131. Merge/refiner lấy nguồn qualified mới nhất, không dùng thời điểm đọc cache để gia hạn. Confidence/taxonomy không bị đổi để ép kết quả GT.

6 đối chứng source .58 xác nhận class audit không đổi returned refinements, model calls, counters, class overrides, evidence history, rescue sets hoặc consensus/source-clock state. Audit chỉ ghi inference thật, có cap theo budget; cache/stale không tạo audit mới. Read-only snapshot không pop/gia hạn lock. Primary/stable evidence, target rect, domain/general opinions và semantic clocks có trong full raw/gzip trace; diagnosis API/reason ranking cũ giữ nguyên.

### Event drain, stop và finish callback

**60 dispatcher/guard/runtime functions đạt**; gồm 26 mới. Repro actual dispatcher .58: entered→finish→persisted, finish total0 nhưng DB1. .59: entered→persisted→finish, finish total1/DB1. Bao phủ in-flight pending, bounded timeout, late admission rejection, atomic submit/stop, accepted backlog, retry completion, fatal error preservation và producer terminal payload.

Registry get/list báo `draining` khi worker còn sống và chờ finish RPC, dù raw producer state đã terminal. Giữ raw terminal cho payload; callback cuối mới công khai completed/stopped/error và cho phép start mới. Differential .58 chứng minh public completed trong khi start vẫn bị từ chối; .59 public draining đồng nhất với trạng thái ownership thực.

4 backend owner-helper functions mới đạt. Actual stop route trích AST chứng minh .58 đánh DB stopped/camera inactive và commit khi AI vẫn draining; .59 giữ session running/camera active, chưa commit. Terminal response phải đúng camera/session; completed/stopped phải pending0. Sau terminal RPC, `db.refresh(session)` giữ kết quả finish callback đã ghi, cùng latest-owner guard.

Frontend 25 kiểm tra riêng xác nhận stop pending/error notices, disabled restart/geometry/apply trong draining và stop-and-apply không gửi PATCH sớm, vẫn giữ proposal. AnnotationEditor và GroundTruthBenchmark function source giữ nguyên byte từ .58. **Không tính lại 37 timing checks lịch sử** đã bị dọn khỏi scratch.

Accepted jobs kết thúc theo retry policy cũ: tối đa 5 attempts, timeout4s và backoff hiện có. Retry exhausted vẫn có thể không persist; flush không được mô tả như bảo đảm mọi request đã ghi DB.

### Trace gzip và diagnosis streaming

**24 regression functions mới đạt**: 9 AI gzip, 4 streaming, 2 worker geometry/compression, 3 backend bundle và 6 transport. Giữ raw API/camera JSONL, đóng writer trước gzip, atomic publication/certificate, source/artifact stat validation, truncation/hash/length/magic checks, old-service raw fallback và transport cap/deadline.

Trace phiên163 thực tế có **140,618,731 byte / 23,651 dòng**, SHA256 `5228d3ac12e560d3d91c7b9324ee0f6a4ece0bac4edfdcf1a78631faa2a1084d`: 23,650 observation frame và 1 metadata header. Raw134.1MiB vượt cap128MiB. Actual gzip product tạo **15,113,380 byte**, giải nén khớp từng byte/SHA nguồn; actual export ZIP **15,115,050 byte** chứa toàn bộ trace. Backend không inflate; byte equality được kiểm tra riêng bằng external chunked decode. Giữ cap128MiB cho representation truyền, total deadline20s; Content-Encoding khác identity bị từ chối trước body iteration.

Gzip được công bố khi trace writer đóng thành công; closed không có nghĩa video đã chạy hết. Camera raw JSONL và raw endpoint còn tương thích. Gzip lỗi là optional warning; manifest nói rõ thiếu/quá lớn/timeout/không hợp lệ, không cắt trace để báo thành công. Raw fallback của service cũ còn giới hạn raw128MiB.

Actual diagnosis với **149 mốc yêu cầu kiểm tra**, không phải toàn bộ 149 GT đã export, khớp chính xác output source .58: .58 mất6.943s/618,740KiB peakRSS, .59 mất2.104s/13,292KiB. 5000 distinct windows:3.821s/63,104KiB; 5000 duplicate windows:1.225s/26,880KiB. Gzip:2.101s/11,808KiB. Đây là phép đo subprocess tại môi trường kiểm tra, không phải deployment SLA.

80 randomized differential cases, tổng9600 rows/3200 requested items, khớp source .58 toàn bộ output. Bao phủ unordered rows, duplicate windows, track filters, first label, inclusive boundaries, audit-only data và last8 context identities với late outcomes ngoài cửa sổ. Streaming hai lượt cập nhật đúng selected context identities; không đổi scoring/reason priority.

Geometry header mới ghi sau frame thật đầu tiên: canonical line/Road, processed/source dimensions, không tạo observation giả. Trace .58 thiếu finite endpoints/Road đầy đủ; infinite-line fit chỉ phục vụ phân tích, không coi là cấu hình gate thực để replay.

## Release verifier

**38 kiểm tra đạt**: 17 execution Git/workflow artifact cục bộ, 14 static YAML/publisher/bootstrap, 3 Bash syntax và 4 fixture Python simulations.

Bash Verify VERSION/Build release artifacts lấy trực tiếp từ `release.yml`, chạy trong Git repository cô lập. Tag/version/HEAD đúng đạt; sai bị chặn. ZIP/TAR.GZ/README lấy byte từ tag, hash khớp SHA256SUMS. Local bare Git kiểm tra annotated/peeled tag, tag absent khác lỗi repository, immutable retry và tag checkout khi main đã tiến.

Native Git tag chưa tồn tại trả1, repository lỗi trả128; source publish quiet probe xử lý đúng. Workflow selection theo tag/SHA/event và expected native probe fallback được kiểm tra bằng fixture. **Không push GitHub hoặc tạo Release thật** trong phiên đóng gói; chưa chạy PowerShell publisher. Lệnh `publish.ps1` trên máy dự án tự đọc VERSION để tạo tag `v0.5.60`.

## Benchmark đầu vào và giới hạn

Screenshot **V0.5.58: GT149 / AI149 / khớp132 / lọt17 / dư17 / F1 88.6% / class đúng98.5% / 2 lỗi class**, session163/benchmark42; IN72/OUT77, không đổi so với .57. Worker đề xuất198/backend dedup49/DB149 timed events/integrityOK. Đây là số input, không phải kết quả .59.

RAR có 198 members: 197 JPG duy nhất và 1 JSONL, tất cả JPG session163. Đã xem 5 contact sheets và ảnh mục tiêu. Chứng minh rider identity hijack ở f18860 vì hai xe khác nhau cùng xuất hiện. Bike GT289.450 chưa có đúng track tại gate; context target105044 ở f7243 là motorcycle khác, không giảm veto cho crop đó. Canonical110070 xuất hiện f7273/t290.88 đã downstream; van254023 thiếu ordinary refiner opinion trong trace .58. Không gán quan hệ nhân quả cho từng hàng lọt/dư/class chỉ từ cửa sổ thời gian.

**Chưa replay V0.5.60 hoặc xác nhận F1/Recall/Precision mới.** Giữ GT timestamps/class, matching window.75s, finite gate/Road Zone, cooldown, confidence, consensus policy, retry/dedup thresholds; counting.py giữ nguyên byte từ .58. Cần replay cùng clip/geometry và benchmark export chứa GT/event/trace để đánh giá thay đổi.

Chưa chạy full pytest với pinned dependencies, HTTP/ORM services, PostgreSQL concurrency/migration, PowerShell parser/runtime, Docker/npm build/audit, inference hoặc browser/model replay. Môi trường thực Python3.12.14, NumPy2.3.5, Pydantic2.13.5, Node24.19.0/npm11.9.0. Project giữ NumPy2.4.6 test pin, Node26.10.0/npm12.2.0 Docker/CI pin; không khẳng định đã thực thi bằng các version pin đó. npm12.2.0 được đối chiếu official latest ngày05/10/2026; không cài npm global trong môi trường đóng gói.

## Đầy đủ lệnh trên máy dự án

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Kiểm tra
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push, tạo tag v0.5.60 và GitHub Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Chạy cùng clip/vạch/Road Zone, tạo benchmark session mới và sao chép GT149 tương thích, rồi **Đối chiếu lại → Tải hồ sơ benchmark**. Gửi ZIP hồ sơ cùng screenshot; manifest ghi tình trạng trace. Khi nén thư mục ảnh camera, giữ `session_<id>_benchmark-trace.jsonl` sau khi hoàn tất. README có GitHub CLI login, repository override và retry release.
