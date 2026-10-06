# Kiểm tra Traffic AI V0.5.61

## Kết quả đã thực hiện

### V0.5.61 — span clock + fresh class closure

- **644 pytest cases đạt, 0 lỗi trong môi trường đóng gói: 528 AI + 116 backend.** Backend dùng SQLite memory và test-only shim `httpx2 -> httpx`; AI dùng cùng shim và các `AI_*_ROOT` tạm dưới `/mnt/data`. Đây là kiểm tra source logic, không thay thế Docker với dependency pin thật.
- **7 regression V0.5.61 mới đạt**: 2 class evidence, 3 anchor/timecode, 2 worker crossing-class. Chúng kiểm tra two-frame CAR win, same-frame heavy veto, trusted direct timestamp, hint expiry/no event reopen và crossing-only class override.
- **130 Python files parse AST thành công**. Frontend `package.json` parse JSON; source version đồng bộ `0.5.61`.
- **75 migrations** có revision duy nhất, parent đầy đủ, không cycle; head `0075_span_clock_class_v0561`, parent `0074_stop_ack_compat_v0560`. Migration 0075 chỉ cập nhật `schema_version` lên0.5.61; downgrade về0.5.60.
- Giữ `Assert-StopAckCompatibilityV0560Contract` và thêm `Assert-SpanClockClassV0561Contract` trong `test.ps1`. Contract mới kiểm tra `_SpanClockHint`, `reconciliation_crossing_frame_for`, `trusted_span_frame`, `recent_four_wheel_wins`, `_fresh_car_crossing_override`, telemetry và regression files.
- **17 PowerShell scripts** được chuẩn hóa UTF-8 no-BOM/CRLF ở bước đóng gói. Không có PowerShell runtime trong môi trường hiện tại, nên `test.ps1` phải được chạy lại trên máy Windows dự án.
- Full source **190 file: 187 text + 3 binary assets** sau migration0075; không thêm model weight/video/dataset vào ZIP.

### Phạm vi thay đổi có chủ ý

`Anchor Span Clock Reconciliation` chỉ cung cấp timestamp cho event mà primary Gate đã tự chấp nhận. Hint cùng track/direction phải xuất phát từ finite span đã qua geometry/Road Zone, không phải same-direction candidate/approach span, không có opposite observation, và nằm trong cửa sổ bounded. Hết hạn thì bỏ; hint không gọi `register_external_crossing()` và không tăng count.

`Fresh CAR Crossing Override` chỉ chạy tại crossing, cần refined CAR >=0.80 trên ít nhất2 distinct frame rất mới, mỗi frame CAR phải thắng BUS/TRUCK cùng frame và frame mới nhất phải là crossing frame. Nó không xóa TRUCK semantic lock toàn cục và không thay threshold bicycle/truck thông thường.

### Benchmark đầu vào thực tế V0.5.60

Screenshot session166 / benchmark43: **GT149 / AI149 / khớp134 / lọt15 / dư15 / Recall89.9% / Precision89.9% / F1 89.9% / class đúng98.5% / 2 sai loại / IN70 / OUT79**. Worker đề xuất196, backend gộp47, DB149 event.

RAR phiên166 chứa195 JPG và `session_166_benchmark-trace.jsonl` raw194,016,680byte. Trace tại track254023 quanh frame16049/16050 cho thấy GENERAL refiner CAR ~0.839/~0.859 nhưng event vẫn bị TRUCK lock giữ; đây là evidence trực tiếp cho fresh-CAR rule. GT bicycle04:49.450 chưa có bằng chứng đủ để hạ bicycle veto nên policy bicycle giữ nguyên.

**Chưa replay V0.5.61** và chưa xác nhận F1/Recall/Precision mới. Không đổi GT, tolerance0.75s, benchmark global matching, finite gate/Road Zone, dedup policy hoặc model taxonomy. Cần replay cùng clip/vạch/Road Zone rồi tải hồ sơ benchmark mới để đo hiệu quả thật.

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

Native Git tag chưa tồn tại trả1, repository lỗi trả128; source publish quiet probe xử lý đúng. Workflow selection theo tag/SHA/event và expected native probe fallback được kiểm tra bằng fixture. **Không push GitHub hoặc tạo Release thật** trong phiên đóng gói; chưa chạy PowerShell publisher. Lệnh `publish.ps1` trên máy dự án tự đọc VERSION để tạo tag `v0.5.61`.

## Benchmark đầu vào và giới hạn

Baseline dùng cho V0.5.61 là **V0.5.60 session166 / benchmark43: GT149 / AI149 / khớp134 / lọt15 / dư15 / F1 89.9% / class đúng98.5% / 2 lỗi class / IN70 / OUT79**. Đây là input trước nâng cấp, không phải kết quả V0.5.61.

Không chạy model/video replay trong môi trường đóng gói, nên không khẳng định số benchmark đã cải thiện. Chưa chạy PostgreSQL concurrency/migration thực, PowerShell runtime, Docker build, npm/Vite build hoặc browser layout. Full AI/backend pytest source đã chạy với shim/test roots như mô tả đầu file.

## Đầy đủ lệnh trên máy dự án

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Kiểm tra
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push, tạo tag v0.5.61 và GitHub Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Chạy cùng clip/vạch/Road Zone, tạo benchmark session mới và sao chép GT149 tương thích, rồi **Đối chiếu lại → Tải hồ sơ benchmark**. Gửi ZIP hồ sơ cùng screenshot; manifest ghi tình trạng trace. Khi nén thư mục ảnh camera, giữ `session_<id>_benchmark-trace.jsonl` sau khi hoàn tất. README có GitHub CLI login, repository override và retry release.
