# Kiểm tra Traffic AI V0.5.62

## Kết quả hiện tại

- **649 test functions offline đạt, 0 lỗi: 564 AI + 85 backend.** Giữ toàn bộ644 test-function identities của source .61, thêm40; current source có684 functions.
- **35 HTTP/ORM/app integration tests chưa chạy: 3 AI + 32 backend.** Có trong source; không đổi unavailable module thành pass. Không kế thừa số644 full pytest từ tài liệu .61 làm kết quả chạy lần này.
- **563 static source checks đạt**: version/payload/signature/source-clock/geometry/identity/class/cache/trace/release contracts; **131 Python files** parse/compile thành công.
- **76 migrations** unique revision, parent đầy đủ, không cycle; head `0076_identity_audit_v0562`, parent `0075_span_clock_class_v0561`. Upgrade chỉ cập nhật schema_version0.5.62, downgrade0.5.61.
- **38 local release checks đạt**: actual isolated Git/workflow artifact execution và các static/simulation/syntax checks có phân loại. Không push GitHub, không tạo Release thật, không chạy PowerShell publisher.
- **25 frontend checks đạt**: actual Babel AST App handlers/JSX conditions dưới Node VM, controlled fetch/state setters, JSX parser + malformed JSX rejection. Không phải React DOM/browser layout/Vite build.
- Full source **191 file: 188 UTF-8 text + 3 binary assets**; giữ toàn bộ190 đường dẫn của ZIP .61, chỉ thêm migration0076. **17 PowerShell scripts UTF-8 no-BOM/CRLF**; các text source/config còn lại LF.

40 Python functions mới gồm14 tracking,9 worker-context/class clock,12 trace geometry diagnosis,4 guard/event provenance và1 backend signed event schema. Targeted/differential checks dưới đây là bằng chứng riêng, không cộng vào649.

Harness chạy actual source test functions với phần pytest tối thiểu (`approx`, `raises`, temporary path, monkeypatch). Worker/backend helper được trích AST vì môi trường thiếu HTTP/ORM dependencies; tracking/classification/counting/Human Guard, Pydantic và NumPy dùng module thực. HTTP dispatcher dùng controlled fixture; model opinions không phải inference thật. Test signed event dùng actual `VehicleEventCreate` Pydantic schema. Không tuyên bố đã chạy full pytest hoặc dependency pins thật.

## Baseline và input

Baseline chính là ZIP V0.5.61 user gửi: **190 file /419,484 byte**, SHA256 `82e11cc03fea6121a07b24742e8449b1160d55aba3b1ddcdf4ca6124bd24b980`. CRC sạch, path an toàn/duy nhất; source giải nén khớp từng byte với ZIP. Không dùng loose checkout đã sửa làm oracle.

Screenshot V0.5.61: session167/benchmark44, GT149/AI149/khớp134/lọt15/dư15/Recall=Precision=F1=89.9%/class99.3%/1 lỗi/IN70OUT79. Worker196/backend dedup47/DB149 timed events/integrityOK. So với .60, class2 lỗi→1 nhưng F1 giữ nguyên. Đây là input, không phải kết quả .62.

RAR **81,436,675 byte**, SHA256 `45dc2936d2763d7c7b4effec1d944b53e7483a1e1d4fe4d9991c3422db512c92`, có196 members=195 JPG duy nhất và1 JSONL; tất cảJPG session167/1440×811, đã xem5 contact sheets và ảnh mục tiêu. Trace **195,773,106 byte /23,652 dòng**:23,650 observation +session/geometry headers. SHA256 `59307d1d0af68f706692978a07139cb6137ed158db66e43f96e24c7e3410348f`.

Geometry header thực: processed1440×811/source2960×1668, line[[.343,.479],[.7587,.385]], Road[[.5719,.02],[.351,.0438],[.2798,.8142],[.9543,.6617]]. Đây là cấu hình worker đã dùng; không lấy camera hiện tại hoặc fit infinite line để giả định finite gate lịch sử.

## Differential source V0.5.61

### Canonical collision

**62 tracking functions đạt:48 cũ +14 mới.** Trên actual .61 source:48 cũ và3 control mới đạt;11 regression mới thất bại bằng AssertionError, không dùng TypeError do thiếu API làm bằng chứng.

Replay private-state checkpoint f7272 cùng recorded order/centers/bboxes tái hiện5 anchor .61 với sai số tối đa0.000855px. f7273 oldcanonicals[104160,104160], new[104160,-1]; upper object f7275 oldvelocityY−400.468413, new−0.04708. Fallback không ghi đè occupied/claimed canonical; monotonic negative allocation không tái sử dụng sau TTL và tránh token âm/raw/alias đã thấy. Next-frame order changes giữ mapping riêng; fresh identity không sao chép state cũ.

Giữ .59 bbox-conditioned opposite two-wheel stitch, same-raw reversal, four-wheel recovery, stitch distance/TTL và counters. Backend signed tracking_id có schema int không giới hạn dương và SQL Integer; actual Pydantic event schema regression giữ ID−1/source frame/time.

445 nhóm trùng canonical trên44 ID là telemetry breaches, không phải445 event sai. Object đến trước còn giữ canonical/history cũ; split không tái tạo history đã bị trộn. Synthetic canonical có thể âm, raw_track_id vẫn nguyên. Chưa có model/video/count replay.

### Class source clock

**116 classification +90 context functions đạt**; classification.py và116 test không đổi byte từ .61. Thêm9 context regression/control; actual .61 differential chứng minh6 semantic regressions và2 control không đổi.8 boundary controls của fresh-CAR .61 (future/stale/nonconsecutive/duplicate/heavy tie) vẫn đạt.

Lock source100/TTL30 cùng fresh CAR.90 ở129: .61 trảTRUCK và ghi overrideTRUCK/source129, tồn tại sau131; .62 cache underlying CAR/source129 và chỉ ưu tiên lock khi còn eligible. Losing refiner không làm mới clock primary label được giữ; expired/future clocks không ghi cache, correction cũ không đè correction mới.

Historical .57 semantic-protection test giữ assertion returnedTRUCK.90; cache assertion được sửa sang actual qualifiedBUS.63/source130. Assertion cũ mô tả chính lỗi copy lock, không phải yêu cầu phải giữ cache sai. Counters, confidence policy và crossing-only fresh-CAR .61 giữ semantics khi lock eligible.

Trace có2160 observation mismatch overrideTRUCKclock/live-lockclock trên254023/286434; không suy ra2160 lỗi class/count. CAR/BUS qualified trở lại sau lock hết hạn tới TTL gốc của correction; cần replay đánh giá tác động.

Xe đạp GT289.450 vẫn chưa được box tại7243;110070 đầu7273/t290.88 đã downstream. Refiner motorcycle104284 gần gate là target khác, domainNone/generalMC.694, contextbike0/generalMC.823. Không có matched GT identity export để khẳng định exactpair; không nới bicycle veto/threshold/tolerance.

### Finite geometry diagnosis

**49 trace functions đạt:37 cũ +12 mới.** Actual .61 differential có7 lỗi ngữ nghĩa được tái hiện/sửa,3 finite/endpoint/identical-duplicate controls giữ nguyên;80 randomized headerless cases khớp decoded JSON hoàn toàn, không đổi output shape legacy.

Track13014 f1354–1355 có anchors(1353.877,362.213)→(1138.465,208.928), infinite intersection(1254.631,291.591) ngoài visible rightendpoint(1092.528,312.235). Actual full JSONL diagnosis .61 `crossing_anchor_span_reject`; .62 `crossing_outside_segment_geometry`/extension_only_span.

Audit dùng valid processed geometry header và adjacent chronological observations. Finite anchor/center, extension-only và unverified được tách rõ. Alias cùng source frame nhưng khác point, unordered clock, thiếu/nonfinite/mismatched signed point hoặc gap>45 không tạo finite proof. One previous sample và flags mỗi track/window, không giữ full trajectory array.45 frame là bound audit, không đổi counter threshold.

Actual195.8MB trace với15 yêu cầu extension:2.726s/13,544KiB maxRSS;13 extension-only,1 unverified alias và1 còn finite+cooldown do một segment hợp lệ khác trong cửa sổ. Đây là requests kiểm tra, không phải15 hàng GT export; timings là local measurement.

Finite span chỉ xác nhận recorded geometry, không xác nhận Road/motion/class/HumanGuard qualification, physical GT identity, Gate acceptance hoặc backend persistence. Known tracking ID scope geometry; detection/rejection/event counter vẫn frame-global. Không có valid header giữ legacy chẩn đoán.

### Proposal/guard source provenance

4 functions mới xác nhận trace proposal khớp actual dispatch payload nhưng không báo đã persist, guard giữ original observation/sourceclock, failed admission không được ghi submitted và signed canonical/rounding/privacy không làm đổi event count.

`crossing_proposals` có11 event fields +stage/observed_frame_index; bỏ model_id/snapshot_path/URL/secrets. Frame proposal dùng `committed_before_submit`; dispatcher đã nhận guard-confirmed event dùng `submitted_after_guard`. Backend có thể dedup hoặc request hết retry; hai stage không bảo đảm DB event. `crossing_clock_audit` giữ geometric/trusted/selected/source clock và pending/rejected guard decision.

Existing .57 guard fixture được cập nhật bằng cách execute actual AST assignment `crossing_clock_audit` trước guard branch; giữ mọi assertion cũ về pedestrian rejection, rollback, count và không dispatch. Giữ .58 trace I/O failure không chặn event tests. Audit không chạy thêm model hoặc đổi payload gửi backend.

## Full-source/release scope

Current PS contract `Assert-IdentityProvenanceV0562Contract` được khai báo/gọi, source predicates đạt cùng các contract lịch sử đến .61. Rà soát riêng917 source predicates (916 individual matches +valid .46 alternative),653 internal imports và117 frontend pipeline field references không thấy contract lệch. Đây là inspection bổ sung, không cộng vào563 executed static checks.

189 code/config file hashes được đóng băng sau final batch (README/VERIFICATION loại khỏi code manifest). Counting.py, benchmark scoring/matching, taxonomy/model pins, Road Zone/gate/cooldown/dedup policy giữ byte hoặc cấu hình như baseline; behavioral changes chỉ nằm ở identity separation, class cache clock và audit interpretation.

Release verifier38 kiểm tra gồm actual local Git/workflow artifact execution và explicit static/simulated/Bash syntax checks. ZIP/TAR/README lấy byte từ immutable tag, checksum/tag/VERSION/HEAD mismatch bị chặn. Không chạy PowerShell runtime/publisher hoặc GitHub publication; `publish.ps1` tự đọc VERSION tạo tagv0.5.62 khi chạy trên máy dự án.

Môi trường thực: Python3.12.14/NumPy2.3.5/Pydantic2.13.5/Node24.19.0/npm11.9.0. pytest/FastAPI/SQLAlchemy/httpx/httpx2/cv2/Torch/pwsh/Docker chưa có; không có môi trường full pytest .61 trước đó để dùng lại. Package index probe không cung cấp pinned packages trong phiên này. Không dùng shim để tuyên bố dependency pin đã chạy.

Docker/CI giữ Node26.10.0/npm12.2.0; npm latest official được kiểm tra06/10/2026 vẫn12.2.0. Chưa chạy Docker/full pytest/HTTPORM/PostgreSQL concurrency hoặc migration thật/PowerShell/npm-Vite build/browser layout/model-video replay. **Chưa có F1/Recall/Precision của V0.5.62.**

## Đầy đủ lệnh Windows

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Kiểm tra
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.62 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Chạy cùng clip/vạch/Road Zone, tạo session benchmark mới, sao chépGT149 tương thích từ benchmark44, Đối chiếu lại→Tải hồ sơ benchmark. Gửi ZIP hồ sơ cùng screenshot; cần events.json/ground-truth.json và trace để đối chiếu producer proposal với event DB. Camera archive giữ kèm `session_<id>_benchmark-trace.jsonl` sau hoàn tất.
