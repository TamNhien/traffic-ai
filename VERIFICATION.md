# Kiểm tra Traffic AI V0.5.63

## Kết quả hiện tại

- **687 test functions offline đạt, 0 lỗi: 599 AI + 88 backend.** Giữ toàn bộ684 test-function identities baseline .62; thêm38, hiện có722 definitions. 722 không phải số full pytest đã chạy.
- **35 HTTP/ORM/app integration tests chưa chạy: 3 AI + 32 backend.** Test còn nguyên trong source; không dùng unavailable dependency/module làm pass.
- **591 kiểm tra tĩnh đạt**: AST/signature/payload/source-clock/version/migration/PS source contracts; **132 Python files** parse/compile thành công.
- **77 migrations**, revision unique/parent đầy đủ/không cycle. Head `0077_delivery_prescan_v0563`, parent `0076_identity_audit_v0562`. Upgrade chỉ cập nhật schema_version0.5.63, downgrade0.5.62.
- **38 local release checks đạt**: actual isolated Git/workflow artifact execution và static/simulation/Bash syntax checks đã phân loại. Không push GitHub/tạo Release thật/chạy PowerShell publisher.
- **30 frontend checks đạt**: actual Babel AST handlers dưới Node VM; JSX parser/conditions, component evidence mới actual Babel transform rồi chạy với controlled JSX element factory. Không phải React DOM/browser/Vite build.
- Full source **192 files =189 UTF-8 text +3 binary assets**, giữ đủ191 paths .62, chỉ thêm migration0077. **17 PS scripts UTF-8 no-BOM/CRLF**, text source/config khác LF.

38 functions mới gồm11 worker-context/prescan,12 dispatcher,7 trace proposal/receipt,5 worker trace/lifecycle và3 backend metadata scope. Targeted/differential counts dưới đây là bằng chứng bổ sung, không cộng vào687.

Harness thực thi actual source test functions, với pytest tối thiểu (`approx`, `raises`, tmp_path, monkeypatch). Worker/backend helper trích AST vì thiếu HTTP/ORM; tracking/classification/counting/Human Guard, NumPy và Pydantic dùng module thực. Dispatcher dùng thread/queue/retry thật với HTTP Client kiểm soát. Model opinions là fixture/recorded evidence, không phải inference thật. Không claim full pytest/dependency pins.

## Baseline và input

Baseline đúng full source V0.5.62 đã giao: **191 files /426,488 byte**, SHA256 `0ffa19a281c6eee6699f134493ed7e88f2b13a9eb0e53fbec3e6afa406174c8a`. CRC/path an toàn/duy nhất; mọi source byte giải nén khớp ZIP. Không lấy loose checkout đã sửa làm oracle.

Ảnh V0.5.62 session168/benchmark45: GT149/AI149/khớp135/lọt14/dư14/Recall=Precision=F1=90.6%/class98.5%/2 sai loại/IN68OUT81. Worker195/backend gộp46/DB149 timed events/Human Guard30/IntegrityOK. GT sao chép benchmark44. So với .61, F1 89.9%→90.6%, class99.3%→98.5%. Hai lỗi: bicycle289.450 IN→MC vàCAR641.981 OUT→TRUCK. Đây là input chạy .62 trên máy người dùng, không phải kết quả .63.

RAR mới **81,062,189 byte**, SHA256 `e20d30497f9b2ed2e4a2057c6197b9574a81b796602b7a673d6d413f65028334`;195 members an toàn/duy nhất =194 JPG +1 JSONL. Đã xem194 ảnh qua5 contact sheets và ảnh mục tiêu, tất cảsession168/1440×811/f4–23454.

Trace **196,204,733 byte /23,652 dòng**, SHA256 `75763e361a7b8271b6ecd89b19ed5a3c4ccbf9d967a2b2a0a574da1546f1e4ad`:23,650 observation +2 metadata headers,271,208 gate observations,2037 class audits,195 proposals (194 committed_before_submit +1 submitted_after_guard).42 canonical âm,26,238 negative-ID observations,9 negative-ID proposals;0 duplicate canonical groups trong gate observations cùng frame. Không suy ra mọi identity vật lý đều đúng.

Geometry dùng recorded processed-frame header, không lấy camera hiện tại/fit infinite line. Chưa có benchmark export events.json/ground-truth.json mới; không khẳng định exact physical GT attribution hoặc backend dedup reason chỉ từ proposal/timecode gần nhau.

## Class sampling

**217 targeted functions đạt =116 classification +101 context**, gồm11 mới. Actual .62 ZIP differential có210 positive controls +5 semantic AssertionError regressions; .63 đạt215 assertion chung. Hai test dùng helper mới loại khỏi differential, không lấy TypeError/missing API làm bằng chứng lỗi.

CAR canonical254023: .61 cóCAR.838867 ởf16049 vàCAR.858887 ởcrossingf16050, đủ .80/two-consecutive policy. .62 cóCAR.716797 từf16007 vàCAR.858887 crossing;f16049 không inference nên eligibleTRUCKlock thắng. .62 cache/source clock không phải nguyên nhân được chứng minh của sampling phase khác nhau.

`_truck_lock_prescan_candidate` nhận displayTRUCK/live nonfuture lock gần đoạn vạch bằng finite-segment distance có sẵn. Deferred refinement giữ pass periodic thường trước; extra sample dùng slot còn dư sau crossing và queue thường. Default budget2 giữ nguyên; due MC/bicycle giữ priority cũ, target đã crossing không prescan lại; no-opinion cùng frame không nhân đôi inference.

Threshold.80/hai frame liên tiếp/TTL/consensus/heavy-tie/source-veto giữ nguyên. classification.py/116 test và cache/resolve/observe/fresh-CAR methods .62 byte-identical. Probe4 cadence phases16004/16007/16008/16048 dùng actual methods vàopinions kiểm soát: .62 CAR chỉphase16004, .63 CAR cả4. Không phải video/model replay. GPU work có thể tăng cục bộ; busy budget vẫn có thể thiếu CAR proof.

Xe đạp GT289.450 vẫn có detection muộn/target khác. Không tạo model opinion giả, hạ bicycle veto hoặc sửa GT/window để đạt score. Không bảo đảm class/F1 cải thiện trước replay.

## Dispatcher terminal audit và worker lifecycle

**21 actual threaded dispatcher tests đạt =9 cũ +12 mới.** Actual .62 ZIP giữ9 test cũ đạt;7 cặp .62/.63 giữ số POST, payload, retry delays và mọi state counter. .63 thêm terminal record; đây là observability mới, không phải claim sửa thuật toán delivery.

Queue1024 có drain/dropped counter. Request đã xử lý đến finite retry outcome ghi một terminal receipt:11 source event fields gốc, kind=event_delivery/audit_only, stage backend_acknowledged/delivery_failed, outcome created/deduplicated/acknowledged_unknown/failed, attempts, optional positive non-bool integer backend ID và fixed whitelist dedup reason.

Header0/1 phân biệt tạo/gộp; thiếu header không tự suy ra created. Body absent/invalid/non-object hoặc ID bool/float/string không chặn delivery. Bỏ body/token/URL/snapshot/model path/error text. Audit ngoài retry exception boundary: audit exception/full queue không resend HTTP hoặc mất event tiếp theo; queue đầy tăng dropped. Client initialization failure vẫn pending/flush=False theo .62, không tạo terminal receipt cho request chưa xử lý.

5 worker tests mới xác nhận single writer, late receipt trước close, EOF footer complete/dropped/pending, failed flush giữ error, trace I/O failure không đổi delivery. Test tích hợp dùng **actual EventDispatcher thread→actual worker writer→actual diagnose_trace**, giữ ID−1/source69.4566/backend event12 và không coi receipt là frame counter. Review độc lập phát hiện discriminator thiếu ở handoff đầu; source cuối thêm kind/audit_only và integration regression đạt.

Worker drain dispatcher timeout=None trước trace close/camera publication/gzip; camera/session còn draining qua optional closure. EOF delivery_summary là toàn phiên, không giả observation/sourceclock. Existing .58/.59 AST fixtures cấp đủ context cho thứ tự mới; giữ identities/assertions về không publish failed trace, không finish/release trước drain.

## Diagnosis và API/UI scope

**56 trace functions đạt =49 retained +7 mới.** Actual .62 differential:5 semantic regressions/3 negative controls;160 decoded JSON legacy cases giống hệt (80 headerless +80 finite geometry, không newfields). Actual196.2MB trace old/new pair khoảng5.670s: counters/finite geometry fields giống hệt; no-ID reasons giữ nguyên.

20863 cóOUTproposal69.4566 ởobservation1739. Isolated Gate reconstruction từ anchors tái hiệngeometric1737.415736/source69.45662944; GT ảnh69.457 vẫnmiss/nearestDB70.52. Chứng minh upstream proposal, không chứng minh dispatch/persist/dedup hoặc đúng GT. Nearby12492IN58.89246877 và17578OUT70.52 tái hiện nhưng không ép gắn với GT59.446/69.457.

Known canonical có validated source-window receipt/proposal trả crossing_delivery_observed/crossing_proposal_observed và matched_track_delivery/proposal. Unknown canonical vẫn nearby_time_window; không dùng clock gần nhau làm proofGT. Bounded8 records/loại/window, original source clock routing kể cả guard/ack carrier muộn; validation bỏ sai session/clock/enum/private fields. Receipt/footer không vào geometry/counters. Proposal backend_persistence=unverified; receipt là phản hồi backend, không bảo đảm đúng physicalGT.

Footer dropped/drain/pending có session_global scope; không phải số của matched track. Duplicate requests nhận copy độc lập. Streaming giữ request byte boundary và legacy two-pass context refresh, không giữ full JSONL/trajectory trong RAM.

3 backend pure tests xác nhận negative canonical filtering/private-field omission/cap8/malformed records/unknownforeigntrack scope và không đổi scoring. API copy/sanitize newaudit; diagnosis không newfields giữ legacy attach semantics.

Frontend30 checks gồm25 kiểm tra cũ với guard phù hợp và5 mới: matched/nearby reasons, evidence clock/outcome, legacy malformed records, unknown-ack privacy. AnnotationEditor byte-exact. GroundTruthBenchmark mọi handler/state/scoring/render controls byte-exact với .62 sau chỉ bỏ2 evidence additions và div wrapper. New JSX actual Babel transform +controlled element factory; không claim browser DOM/layout.

## Full source, môi trường và release

PS contract mới `Assert-DeliveryPrescanV0563Contract` khai báo/gọi sau .62; historical contracts giữ nguyên. Inspection riêng935 source predicates (934 individual +valid paired .46 alternative),657 internal imports và117 frontend field pairs không lệch; không cộng vào591.

190 code/config hashes frozen sau final passing batch; README/VERIFICATION kiểm tra riêng. Counting.py/tracking.py, matching/scoring, backend dedup predicates, model/taxonomy/environment budget pins giữ nguyên.192paths giữ toàn baseline, chỉ thêm migration0077, không rewrite table/data.

38 release checks xác nhận immutable tagged ZIP/TAR/README/checksum và VERSION/tag/HEAD/fallback trong local isolated Git. Không PowerShell/GitHub Actions từ xa/publish thật; khi chạy publish.ps1, script đọc VERSION tạo tagv0.5.63.

Môi trường thực: Python3.12.14/NumPy2.3.5/Pydantic2.13.5/Node24.19/npm11.9. pytest/FastAPI/SQLAlchemy/httpx/httpx2/cv2/Torch/pwsh/Docker không có trong primary/systemPython. Fresh package-index probe HTTP403, không cài/giả dependency pin rồi báo full suite.

Docker/CI giữ Node26.10.0/npm12.2.0. [npm CLI latest](https://github.com/npm/cli/releases/latest) đối chiếu07/10/2026 vẫnv12.2.0. Chưa chạy Docker/full pytest/HTTPORM/PostgreSQL concurrency/migration thật/PowerShell/npm-Vite/browser layout/model-video replay. **Chưa có F1/Recall/Precision mới của V0.5.63.**

## Đầy đủ lệnh Windows

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Kiểm tra
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.63 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Chạy cùng clip/vạch/Road, tạo benchmark mới, sao chép149GT tương thích từ benchmark45, Đối chiếu lại→Tải hồ sơ benchmark. Gửi ZIP hồ sơ kèm screenshot; cần events.json/ground-truth.json và .63 receipts để xác định downstream cause. Camera archive giữ session_<id>_benchmark-trace.jsonl đã đóng cùng JPG.
