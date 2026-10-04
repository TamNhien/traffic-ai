# Kiểm tra Traffic AI V0.5.57

## Kết quả đã thực hiện

- **459 test functions offline đạt, 0 lỗi**: 396 AI và 63 backend.
- AI gồm 142 counting, 95 classification, 57 worker context, 22 guard transaction, 25 tracking, 15 Human Guard, 15 benchmark-trace và các test thuần đã có. Backend 25 benchmarking và 38 helper/schema/geometry.
- **33 test HTTP/ORM integration chưa chạy**: 3 AI và 30 backend; giữ đầy đủ trong source.
- **46 regression/control Python mới** đều chạy offline: 8 counting,8 tracking,4 classification,11 worker context,4 Human Guard,4 guard transaction,7 trace-scope.
- **455 static source checks đạt**: PipelineState, event/start/finish payload, source clock/signatures, version/cache/Node/npm, migration lineage, heading lifetime, merged eligibility, consensus certificate, diagnostic provenance, frontend/release contract.
- **124 Python files** parse/compile thành công; 40 gate calls, 125 internal methods và 392 direct calls resolve được trong source khớp signature. Không bao phủ mọi dynamic/framework-generated call.
- **71 migrations** revision duy nhất,<=32 ký tự, parent đầy đủ, không cycle, head duy nhất `0071_anchor_lifecycle_v0557`, parent `0070_benchmark_evidence_v0556`.
- Contract V0.5.57 được khai báo/gọi trong test.ps1, source predicates đối chiếu bằng Python. Đã sửa predicate Human Guard để cho phép comment giữa hai lệnh. Chưa chạy PowerShell parser/runtime.
- **11 frontend timing assertions đạt** với handler thực trích AST; cùng 11 case đều thất bại trên source từ ZIP .56. Bao phủ late detail/reconcile/list, same-ID reload, A→B→A, wrong camera, delayed JSON, stale error và busy cleanup. Không phải browser/React runtime hoặc HTTP integration.
- JSX parse đạt bằng Babel bundle Playwright, Node thực 24.19.0; mẫu JSX sai bị từ chối. Chưa chạy Vite/React import resolution hoặc kiểm tra layout trong browser.
- Backend entrypoint đạt bash -n. 17 script PowerShell UTF-8 no-BOM/CRLF; source/config LF. Full source 184 file gồm 181 text UTF-8 và 3 binary assets; giữ toàn bộ 183 đường dẫn của ZIP .56, chỉ thêm migration 0071.

Harness chạy test functions source thực với phần pytest tối thiểu (`approx`, `raises`, temporary path, monkeypatch). Worker/route methods trích AST vì không có HTTP/ORM dependencies; classification/counting/Human Guard, Pydantic và NumPy dùng module thực. Model opinions trong regression là fixture, không chạy model inference. Các số offline không thay thế full pytest trong Docker.

## Đối chiếu source V0.5.56

- Gate/tracking:16case mới đều đạt .57;10case thất bại bằng AssertionError trên module thực .56. Bao phủ giảm tốc vẫn đi lên nhưng phát IN giả sau OUT, identity expiry, alias heading ownership, pending passage clock sau merge và NaN timestamp correction; positive control giữ crossing thật, startup và reversal đủ chuyển động.
- Class/refiner:15case mới đều đạt .57; trên .56 có5 AssertionError regression,4 trường hợp thiếu API/signature mới và6control đạt. Fused bicycle consensus .827744 đủ điều kiện trước đây tăng counter nhưng event vẫn motorcycle; certificate nay chỉ dùng đúng track/frame/tuple. Truck lock không được gia hạn bởi truy vấn history, primary truck refresh giữ clock hiện tại.
- Human Guard/transaction/snapshot:8case mới đều đạt .57;6case thất bại trên .56,2control đạt. Confirmed rejected+neutral không authorize crossing; trace2ordinary+1deferred=3, frame sau không tính lại; event giữ source519/20.72s và snapshot observation522. Session tên ảnh khác nhau; cv2.imwrite(False) trảNone. Snapshot regression dùng writer fixture, không kiểm chứng JPEG encoding thực.
- Trace scope:7case mới đều đạt .57, .56 thiếu field provenance nên các assertion đó thất bại. So sánh36case trên hai module cho thấy reason/counter/audit cũ giống nhau sau khi bỏ metadata mới; không đổi thứ tự reason hoặc scoring.
- Frontend:11case timing dùng actual handlers .57/.56 với controlled fetch/state. .57 chặn response stale; .56 bị overwrite hoặc cleanup sai. Đây là kiểm tra logic async source, không phải network/browser end-to-end.

Giữ ngưỡng gate, Road Zone, matching, consensus one-shot/aggregate và dedup toàn cục. Các sửa đổi không dùng timestamp GT để ép class hoặc tự tạo benchmark mới.

## Release verifier

**38 kiểm tra đạt**:17 execution Git/workflow artifact cục bộ,16 static YAML/publisher/bootstrap,3 Bash syntax,2 fixture Python mô phỏng.

Bash Verify VERSION/Build release artifacts lấy trực tiếp từ release.yml, chạy trong Git repository cô lập. Tag/version/HEAD đúng đạt; sai bị chặn. ZIP/TAR.GZ/README lấy byte từ tag, hash khớp SHA256SUMS. Local bare Git kiểm tra annotated/peeled tag, absent khác unreachable, immutable retry và tag checkout khi main đã tiến.

Native Git tag chưa tồn tại trả1, repository lỗi trả128; source publish quiet probe xử lý đúng. Chọn đúng workflow tag/SHA/event và URL dùng fixture Python. **Không push GitHub hoặc tạo Release thật** trong phiên đóng gói; chưa chạy PowerShell publisher.

## Benchmark và giới hạn

Input screenshot **V0.5.56:GT149 / AI152 / khớp135 / lọt14 / dư17 / F1 89.7% / class đúng98.5% /2lỗi class**, session160/benchmark39. F1 giảm từ90.4% của .55; tổng AI không đổi.

Đã xem429JPG/11contact sheet; RAR trộn222ảnh cũ .55 giống byte và207ảnh mới .56, không có JSONL/scores. Không dùng chuỗi anchor nhảy cũ làm chứng cứ lỗi .56. Xe đạp289.68s chưa được box cạnh scooter riêng, về292.36s mới có box MC; không xác định AI event ghép GT289.450. Van641.96s vẫn rawtruck; không ép nhãncar. Các chẩn đoán time-window chưa thể gắn nhân quả với xeGT cụ thể. **Chưa replay V0.5.57** hoặc xác nhận cải thiện số đo clip.

Heading đã xác lập được giữ khi chuyển động dưới1.5, nên reversal rất chậm có thể cập nhật anchor muộn. Cần replay cùng clip/geometry để đánh giá tradeoff. Counter trace là frame xử lý/xác nhận; event timecode vẫn là crossing source frame/time gốc.

Chưa chạy full pytest với pinned dependencies, HTTP/ORM, PostgreSQL concurrency/migration, PowerShell parser/runtime, Docker/npm build/audit, inference hoặc replay. Môi trường thực Python3.12.14, NumPy2.3.5, Pydantic2.13.5, Node24.19.0/npm11.9.0. Project giữ NumPy2.4.6 test pin, Node26.10.0/npm12.2.0 Docker/CI pin; không khẳng định đã thực thi bằng các version pin đó.

## Đầy đủ lệnh trên máy dự án

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Kiểm tra
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push, tạo tag v0.5.57 và GitHub Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Chạy cùng clip/vạch/Road Zone, tạo benchmark session mới và sao chép GT149 tương thích, rồi **Đối chiếu lại → Tải hồ sơ benchmark**. Gửi ZIP hồ sơ cùng screenshot; manifest ghi trace có sẵn/thiếu. ZIP ảnh riêng không thay thế event/trace provenance. README có GitHub CLI login, repository override và retry release.
