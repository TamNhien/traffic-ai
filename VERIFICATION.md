# Kiểm tra Traffic AI V0.5.66

## Kết quả thực hiện

| Phạm vi | Kết quả |
|---|---|
| Test functions offline thực thi | **731 đạt, 0 lỗi**: 628 AI + 103 backend |
| HTTP/ORM/app integration chưa chạy | **35**: đúng 3 AI + 32 backend identities của .65 |
| Test definitions trong source | **766**: giữ đủ 758 cũ, thêm 8 |
| Kiểm tra tĩnh source/contracts | **645 đạt** |
| Python parse/compile | **135 files** |
| Alembic | **80 migrations**, head/parent hợp lệ, không cycle |
| Release cục bộ | **38 đạt**: 17 executed + 14 static + 4 simulation + 3 Bash syntax |
| Frontend | **57 đạt**: đủ 41 ca cũ + 16 ca mới, Babel/Node VM/controlled JSX |
| Frontend layout/evidence subset | **27 đạt**, thuộc 57 ca trên |
| Full source | **195 files**: 192 UTF-8 text + 3 binary assets |
| Code/config đóng băng sau test | **193 SHA256**, hai tài liệu review riêng |

731 là test functions thực sự chạy qua offline harness, không phải full pytest. 766 definitions gồm 35 integration chưa chạy. Giữ đủ 758 baseline test identities và đúng 35 integration exclusions; không xóa test hay bỏ thêm integration để đạt số pass.

Thêm 8 backend tests về GT0/AI0, GT0/AI149, không chạy assignment/diagnostics khi GT trống, generator/input preservation, có GT nhưng AI0, valid scored report, chuyển trạng thái sau thêm GT và export JSON null với đủ events. Năm test bodies cũ đổi: 4 health/version assertions lên .66 và 1 startup-artifact fixture thêm GT ở xa; assertion chẩn đoán startup vẫn giữ nguyên.

Actual NumPy 2.3.5/Pydantic 2.13.5 và algorithm modules dùng thư viện thực. Worker/pure backend helpers trích AST để tránh HTTP/ORM imports thiếu; pytest shim chỉ cung cấp approx/raises/tmp_path/monkeypatch. Dispatcher dùng queue/thread/retry thực với HTTP client được kiểm soát. Model opinions là fixture/recorded evidence, không phải inference thật.

## Baseline và input

Baseline đúng ZIP .65 đã giao: **447,906 byte / 194 files**, SHA256 `96f4d7681b8f924da24c42e162e2cb93497c92da0de839e515cd83aa27352b92`. Đã kiểm CRC/safe unique paths và giải nén byte-exact. Source .66 giữ đủ 194 paths, thêm duy nhất migration0080.

Hai ảnh .65 session171/benchmark48 cho thấy AI149, IN68/OUT81; AI146 xe máy +1 xe đạp +2 xe tải, không có CAR. Worker195/backend gộp46/DB149 timed events/Human Guard30/IntegrityOK. Truck lock→car0/truck semantic locks2/truck crossings2; class checks2168.

**Benchmark #48 đang GT0**, có nút sao chép149GT từ benchmark #47 nhưng chưa có GT trong target. Báo cáo cũ FP149/F10% chưa phải score hợp lệ về chất lượng AI. Không có GT/event assignment export hoặc full model replay để đo score .66. Không đổi GT để làm đẹp score.

RAR **81,081,480 byte**, SHA256 `fd48df69f5676d71b21126a68bddaaba997ecc3fee91e4ce469e123351e10927`; 195 safe unique regular members =194 JPEG +1 JSONL. Tất cả194JPEG1440×811 được decode; đã xem5 contact sheets và hai ảnh crossing.

Trace **196,487,992 byte**, SHA256 `069b706128174ef4ba0dfabae3d744467dbc579ecebad5ef5f59af557c3f2e2d`; 23,650 continuous observation frames,195proposals=195terminalreceipts khớp11source fields:149created+46deduplicated, allattempt1, mọi dedupID resolve tới created event. Footer drain_complete=true/pending0/dropped0. Không thấy canonical collision trong cùng frame.

| Lượt van đã sửa trong run .65 | Source / observed frame | Backend event | Kết quả |
|---|---:|---:|---|
| 254023 OUT641.9311s | 16049 /16050 | 10212 | TRUCK |
| −22 IN882.2898s | 22058 /22059 | 10254 | TRUCK |

Cả hai raw crossing audits ghi generic CAR winning frames2, domain0, qualified_truck_requires_domain_car, demotion_accepted=false. Đối chiếu195receipt với session170: tracking/direction/source frame/time/method/x/y/outcome/attempts/dedup reason giữ nguyên sau bỏ session/backend IDs vốn thay đổi giữa các run. Chỉ hai vehicle_type đổi CAR→TRUCK; confidence OUT giữ .995817, IN đổi .994647→.986346 theo truck lock. Đây là bằng chứng từ run người dùng, không phải inference .66 hoặc khẳng định hai canonical là cùng xe vật lý.

## Chính sách readiness và hồi quy

GT0 short-circuit trước global assignment/FP diagnostics. Report thêm report_readiness với status needs_ground_truth, scoring_available=false, reason no_ground_truth. GT/AI totals và raw counts theo class/direction vẫn có; score/count-error scalars, difference/correct_matches là null, assignment/diagnostic lists rỗng. Export roundtrip giữ JSON null, GT[], đủ0hoặc149AIevents và không mutate input.

GT>0 trả ready/scoring_available=true/reasonnull. Backend trường ready cùng metadata này; AI0 vẫn chấm được, matched0/missed=GT/FP0/RecallPrecisionF10%. Có mốc GT không phải chứng nhận annotation đã đầy đủ toàn clip. API chưa có trạng thái xác nhận riêng cho clip đã được kiểm chứng không có xe, nên GT0/AI0 cũng chưa chấm, không tự nhận100%.

**1,000 randomized valid-GT cases** của implementation review so với actual delivered .65 ZIP giữ toàn bộ legacy report fields; gồm127GT>0AI0 và1,000input-order checks. Independent review thêm **600 valid-GT cases**,5GT0 cases (AI0/1/2/7/149) và explicit GT>0AI0. Đây là supplemental assertions, không cộng vào731 test functions. Không dùng class/direction để thay đổi temporal matching hoặc nâng score.

Frontend giữ tổng AI/GT/Integrity/export khi GT trống, các score/Δ hiển thị — và không render stale diagnosis lists. Legacy API fallback dùng ground_truth_total; explicit metadata false/needs_ground_truth vẫn chặn score, không dùng legacy ready để bỏ AI0. Nút reconcile disabled khi detail.marks rỗng và handler cũng chặn POST; response needsGT không được tóm tắt là khớpnull/lọtnull/dưnull.

Sao chép vẫn là hành động explicit; source/target IDs và sốGT rõ ràng. Actual handler gửi source47→target48 và reload detail/report/list; không auto-clone. Selection guard tránh phản hồi clone/reconcile cũ thay đổi thông báo của benchmark mới. Existing request guards của list/detail/reconcile được giữ lại.

16 frontend cases mới cover emptyGT+AI149/0, stale diagnostics, scoredGT+AI0/metrics, legacy fallback, metadata precedence, clone available/incompatible, explicit clone POST/refresh/error/stale response, noGT reconcile/noPOST, needsGTresponse, valid/stale reconcile. Giữ đủ41 old check identities.

## Rà soát full source và contracts

Đối chiếu .65 ZIP, toàn bộ17 AI app policy files byteequal, gồm worker/classification/counting/tracking/Human Guard/dispatcher/runtime/trace. Giữ sửa van .65, admission/budgets/caches/semantic TTL/Gate/Road/cooldown/dedup/provenance/drain.

Benchmarking chỉ thêm _empty_ground_truth_report và early return/readiness trong match_crossings. Bỏ đúng các phần additive này thì AST trở về .65;12/13 old module functions byteequal, global matcher/missed matching audit/FP diagnostics/review pairing không đổi. Routes80/81functions byteequal, _build_benchmark_report chỉ thay ready bằng scoring_available. GT CRUD/clone/export không đổi.

Independent Babel parse39 top-level frontend statements: chỉ APP_VERSION và GroundTruthBenchmark đổi;37statements khác giữ đúng byte, gồm toàn bộ App/AnnotationEditor. GroundTruthBenchmark giữ state/effects và các handler khác; chỉ thêm3readiness declarations, đổi2handler clone/reconcile và render readiness. Original3diagnostic row maps giữ nguyên; originalcontrols/handlers giữ, chỉ reconcile thêm điều kiện GT và một nút clone bổ sung tại panel report. CSS byteequal .65, gồm dashboard50/50 và evidence stack. Controlled JSX không phải pixel geometry/browser rendering.

**969 source regex predicates**, **662 internal imported symbols**, **117 frontend runtime-field pairs** được rà soát, không còn findings. Assert-BenchmarkReadinessV0566Contract khai báo/gọi, historical functions/invocations vẫn có. VERSION/frontend/API health/start message0.5.66 đồng bộ;193code/config hashes final đóng băng và so lại khi đóng gói.

Head **0080_benchmark_ready_v0566**, parent **0079_van_semantics_v0565**; upgrade schema_version0.5.66/downgrade0.5.65, không đổi schema/GT/events. Revision dưới32ký tự.17PowerShell scripts UTF-8noBOM/CRLF, source/config text khácLF.

npm Docker/CI/packageManager12.2.0 đối chiếu [official npm CLI latest](https://github.com/npm/cli/releases/latest) ngày09/10/2026; Node pin26.10.0 giữ nguyên. Đây là source contracts, không phải host npm upgrade hoặc native PowerShell chạy thành công.

## Giới hạn và chạy lại trên Windows

Môi trường kiểm tra Python3.12.14/Node24.19.0/npm11.9.0; availability kế thừa .65, không probe/install dependency lặp lại. Thiếu pytest/FastAPI/SQLAlchemy/Alembic/httpx2/cv2/Torch/pwsh/Docker. Không chạy full dependency-pinned pytest, HTTP/ORM/database/migration thực, PowerShell native, Docker/npm audit/Vite build, browser/React DOM, GPU/model/video replay. Integration tests vẫn nguyên trong source để chạy scripts/test.ps1 trên máy đủ Docker.

38releasechecks gồm isolated local Git/workflow artifact execution và static/simulation/Bash syntax đã phân loại; không push GitHub/tạo Release thật. Không có Recall/F1/class accuracy .66 đo từ clip.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.66 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Với benchmark48, sao chép149GT từ benchmark47 nếu cùng clip/vạch; review GT loại van ở10:41.93OUT/14:42.29IN theo quy ước người dùng Xe tải, giữ timecode/hướng theo clip đã kiểm tra. Đối chiếu lại rồi Tải hồ sơ benchmark ZIP để lấy cả GT và AI assignments cho lần phân tích tiếp theo.
