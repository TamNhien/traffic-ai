# Kiểm tra Traffic AI V0.5.58

## Kết quả đã thực hiện

- **513 test functions offline đạt, 0 lỗi**:442 AI và71 backend.
- Giữ toàn bộ459 test functions offline của .57, thêm54 regression/control Python:11 tracking,8 classification,10 worker context,9 guard/trace lifecycle,6 trace filesystem/header,8 backend numeric và2 AI numeric.
- **33 test HTTP/ORM integration chưa chạy**:3 AI và30 backend; giữ trong source.
- **37 frontend timing/effect/interaction checks đạt**:26 AnnotationEditor mới và11 benchmark-selection checks đã có.
- **508 static source checks đạt**: PipelineState, event/start/finish payload, source clock/signatures, finite numeric fields, version/cache/Node/npm, migration lineage, heading/consensus lifecycle, trace publication, annotation guards và release contract.
- **125 Python files** parse/compile thành công;40 gate calls,145 internal methods và395 direct calls resolve được trong source khớp signature. Không bao phủ mọi dynamic/framework-generated call.
- **72 migrations** revision duy nhất,<=32 ký tự, parent đầy đủ, không cycle, head duy nhất `0072_trace_lifecycle_v0558`, parent `0071_anchor_lifecycle_v0557`.
- Contract V0.5.58 và các contract lịch sử được khai báo/gọi trong test.ps1, source predicates đối chiếu bằng Python, kể cả7 geometry trace keys. Chưa chạy PowerShell parser/runtime.
- JSX parse đạt bằng Babel bundle Playwright; mẫu JSX sai bị từ chối. Chưa chạy Vite/React import resolution hoặc kiểm tra layout trong browser.
- Backend entrypoint đạt bash -n.17 script PowerShell UTF-8 no-BOM/CRLF; source/config LF. Full source185 file gồm182 text UTF-8 và3 binary assets; giữ toàn bộ184 đường dẫn của ZIP .57, chỉ thêm migration0072.

Harness chạy test functions source thực với phần pytest tối thiểu (`approx`, `raises`, temporary path, monkeypatch). Worker/route methods trích AST vì không có HTTP/ORM dependencies; classification/counting/tracking/Human Guard, Pydantic và NumPy dùng module thực. Model opinions trong regression là fixture, không chạy model inference. Các số offline không thay thế full pytest trong Docker.

## Đối chiếu source V0.5.57

- Tracking:36/36 tests đạt .58, giữ25 cũ và thêm11. Trên ZIP .57 thật:6 AssertionError regression và5 control đạt. Reversal chậm qua finite gate/Road Zone tái hiện hai chiều; giữ deceleration/coasting, chống alternating jitter, duplicate/stale frame, gap lớn, alias/expiry và ngoài finite gate/Road Zone.
- Class/refiner:103 classification +67 worker context đạt;18 mới. ZIP .57 thật có12 AssertionError regression,4 control đạt và2 kiểm tra thiếu API clock mới. Chronology differential chỉ bỏ keyword frame_index tại ranh giới gọi updater cũ, vẫn chạy updater/merge thực .57 để chứng minh history/hits/class sai, không coi TypeError keyword là bằng chứng lỗi class.
- Trace lifecycle/publication:15/15 mới đạt; .57 có14 lỗi và1 control đạt. AST run repro ghi trace OSError trước dispatch: .57 gửi0/1, .58 gửi1/1 và đóng writer lỗi. Kiểm tra open/write/close/EOF audit failure, source clock gốc, camera/session identity, đóng trước publication, hardlink/copy fallback, replace nguyên tử, cleanup partial và session header không tạo observation giả.
- Numeric:10/10 mới đạt; .57 có5 regression thất bại và5 control đạt. Pydantic thực từ chối nonfinite event/GT clock, finish FPS/duration, tolerance, diagnosis times/window; optional/finite/clamp compatibility giữ nguyên.
- Annotation Studio:26/26 mới đạt, ZIP .57 có24 AssertionError và2 control đạt. Dùng actual pre-JSX component body trích Babel AST, hook slots bền giữa render mô phỏng, fetch/body timing điều khiển và callback effect/cleanup thật được chọn. Bao phủ dataset/image/filter/updated_at, A→B→A, latest-request, stale save/index/bulk/error, hidden old boxes, edit blocking, interrupted draw, stale keyboard listener, một automatic loader đúng ảnh, giữ edit khi index tới muộn và chuyển ảnh sau save-index. Không phải React/browser/DOM hoặc HTTP integration.

Giữ ngưỡng gate, Road Zone, matching, consensus one-shot/aggregate, TTL và dedup toàn cục. Không dùng timestamp/class GT để ép kết quả hoặc tự tạo benchmark mới.

## Release verifier

**38 kiểm tra đạt**:17 execution Git/workflow artifact cục bộ,16 static YAML/publisher/bootstrap,3 Bash syntax,2 fixture Python mô phỏng.

Bash Verify VERSION/Build release artifacts lấy trực tiếp từ release.yml, chạy trong Git repository cô lập. Tag/version/HEAD đúng đạt; sai bị chặn. ZIP/TAR.GZ/README lấy byte từ tag, hash khớp SHA256SUMS. Local bare Git kiểm tra annotated/peeled tag, absent khác unreachable, immutable retry và tag checkout khi main đã tiến.

Native Git tag chưa tồn tại trả1, repository lỗi trả128; source publish quiet probe xử lý đúng. Chọn đúng workflow tag/SHA/event và URL dùng fixture Python. **Không push GitHub hoặc tạo Release thật** trong phiên đóng gói; chưa chạy PowerShell publisher.

## Benchmark và giới hạn

Input screenshot **V0.5.57:GT149 / AI149 / khớp132 / lọt17 / dư17 / F1 88.6% / class đúng98.5% /2lỗi class**, session161/benchmark40. So .56 khớp135, IN75→72; OUT77 giữ nguyên.

Đã xem197 JPG duy nhất/5contact sheet, tất cả session161; không có JSONL/scores hoặc ảnh cũ trộn. Anchor rider#328328 vẫn dao động tại754.36–754.96s, tọa độ giống ảnh .56 cùng frame, bbox/raw ID biến động. Xe đạp289.68s chưa được box cạnh scooter riêng, về292.36s có box MC; chưa xác định AI event ghép GT289.450. Van641.96s vẫn rawtruck. Chẩn đoán time-window chưa thể gắn nhân quả với xe GT cụ thể. **Chưa replay V0.5.58** hoặc xác nhận cải thiện số đo clip.

Hai observation reverse và1.5px actual travel cho phép cập nhật heading khi đảo chiều chậm, nhưng anchor sẽ đổi cạnh dẫn sau xác nhận. Rapid bbox deformation/strong heading changes còn cần trace/replay; không khẳng định đã sửa chuỗi ảnh#328328 hoặc3IN bị mất. Trace bổ sung geometry/identity để kiểm tra lần sau. Event source clock gốc giữ nguyên; frame trace là observation/confirmation.

Chưa chạy full pytest với pinned dependencies, HTTP/ORM, PostgreSQL concurrency/migration, PowerShell parser/runtime, Docker/npm build/audit, inference hoặc replay. Môi trường thực Python3.12.14, NumPy2.3.5, Pydantic2.13.5, Node24.19.0/npm11.9.0. Project giữ NumPy2.4.6 test pin, Node26.10.0/npm12.2.0 Docker/CI pin; không khẳng định đã thực thi bằng version pin đó.

## Đầy đủ lệnh trên máy dự án

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Kiểm tra
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push, tạo tag v0.5.58 và GitHub Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Chạy cùng clip/vạch/Road Zone, tạo benchmark session mới và sao chép GT149 tương thích, rồi **Đối chiếu lại → Tải hồ sơ benchmark**. Gửi ZIP hồ sơ cùng screenshot; manifest ghi trace có sẵn/thiếu. Khi nén thư mục ảnh camera, giữ kèm `session_<id>_benchmark-trace.jsonl` sau khi hoàn tất; UI báo nếu trace lỗi. README có GitHub CLI login, repository override và retry release.
