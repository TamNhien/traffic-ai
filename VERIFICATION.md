# Kiểm tra Traffic AI V0.5.64

## Kết quả thực hiện

| Phạm vi | Kết quả |
|---|---|
| Test functions offline thực thi | **707 đạt, 0 lỗi**: 612 AI +95 backend |
| HTTP/ORM/app integration chưa chạy | **35**: 3 AI +32 backend; đúng 35 identities của .63 |
| Test definitions trong source | **742**: giữ đủ722 cũ, thêm20 |
| Kiểm tra tĩnh source/contracts | **612 đạt** |
| Python parse/compile | **133 files** |
| Alembic | **78 migrations**, head/parent duy nhất hợp lệ, không cycle |
| Release cục bộ | **38 đạt**: 17 executed +14 static +4 simulation +3 Bash syntax |
| Frontend | **40 đạt**: Babel/Node VM và controlled JSX, không phải browser/Vite build |
| Full source | **193 files**: 190 UTF-8 text +3 binary assets |
| Code/config đóng băng sau test | **191 SHA256**, hai tài liệu review riêng |

707 là số test functions thực sự chạy qua offline harness, không phải số full pytest. 742 bao gồm35 integration chưa chạy. Giữ nguyên toàn bộ722 test-function identities của baseline .63. Hai mươi test mới gồm13 worker-context/admission và7 benchmark assignment audit.

Harness dùng NumPy2.3.5 và Pydantic2.13.5 thực; actual modules counting/classification/tracking/Human Guard và test functions thực. Worker/pure backend helpers trích AST để tránh HTTP/ORM dependencies thiếu; pytest shim chỉ cung cấp approx/raises/tmp_path/monkeypatch. Dispatcher dùng queue/thread/retry thực với HTTP client được kiểm soát. Opinions là fixtures, không phải model inference thật.

Frontend dùng Babel parser/transform đã cài, actual source slices trong Node VM và controlled JSX element factory. AnnotationEditor và benchmark state/handlers/scoring controls giữ nguyên sau khi bỏ đúng wrappers/components bổ sung. 10 ca UI mới kiểm tra cây JSX, scope/cap/invalid evidence và CSS grid; không cộng riêng vào40. Không có Chromium để kiểm tra pixel layout.

## Baseline và input đã xác minh

Baseline là full source .63 đã giao: **440,606 byte /192 files**, SHA256 `7a3b78a98f96e2d56d1f9e63ab6bae425fff820444c35f81e1cb20253abf3d0c`. ZIP CRC/path an toàn/duy nhất và byte extraction đã kiểm tra. Giữ đủ192 paths, thêm duy nhất `backend/alembic/versions/0078_replay_audit_v0564.py`.

Ảnh .63 session169 / benchmark46: GT149/AI149/khớp135/lọt14/dư14/Recall=Precision=F1=90.6%/class98.5%/2 lỗi/IN68OUT81. Worker195/backend gộp46/DB149 timed events/Human Guard30/IntegrityOK. Hai lỗi bicycle289.450 IN→MC và CAR641.981 OUT→TRUCK. Đây là **input .63 trên máy người dùng**, chưa có replay hoặc F1 .64.

RAR81,071,069byte, SHA256 `1ba987864f2b8f5b5b243e52f91046d8d6fe3d87dbc9feeceb5d451abca53d2b`;195 safe unique regular members =194 JPG +1 JSONL. Tất cả JPEG decode thành công, session169/1440×811; đã xem đủ194 ảnh qua5 contact sheets và2 screenshots.

Trace196,235,528byte, SHA256 `35c7faa5a0c15771b548be0d4368f47c270a41caa2ac028627fb0a6645ad27ba`:23,848 dòng =23,650 observation frame1–23,650 +2 metadata headers +195 terminal receipts +1 delivery summary. Có271,208 gate tracks,2110 class audits,195 proposals. Proposal và receipt khớp đủ11 source fields gốc.

Terminal receipts **149 created +46 deduplicated**, tất cả attempt1. Created IDs9818–9966 đầy đủ;46 dedup references đều resolve tới created event. Footer drain_complete=true/pending0/dropped0. Các receipt mục tiêu:

| Backend ID | Canonical | Hướng / source time |
|---|---:|---|
| 9826 | 12492 | IN58.8925 |
| 9828 | 20863 | OUT69.4566 |
| 9829 | 17578 | OUT70.52 |
| 9914 | 254023 | TRUCK OUT641.9311 |

GT69.457 đang lọt nhưng source69.4566 được tạo event9828, nên receipt này không chứng minh nguyên nhân dedup. Review candidate70.52 là event chưa ghép. Chưa có events.json/ground-truth.json để chứng minh event9828 đang ghép với GT nào, GT trùng hoặc physical identity. Matching audit mới sẽ cung cấp assignments của **report mới hiện tại**, không tái tạo benchmark46 bằng dữ liệu thiếu.

## Hồi quy và đối chiếu source .63

13 test worker mới thực thi actual crossing branch trích từ run(): kiểm tra lag0/.36/2.0; model/flag/label/budget/cache/future observation; shared per-frame slots; live/non-deterministic/all-frame conditions; CAR .80/two-frame/TRUCK veto; periodic/prescan gate giữ nguyên; source clock event khác frame quan sát và attempted sample không có opinion.

12 differential cases chạy actual worker code từ **ZIP .63** với cùng controlled opinions/budget. Chỉ all-frame deterministic video crossing được bỏ lag gate; cases còn lại giữ admission/policy. Các số này là bằng chứng bổ sung, không cộng vào707. Không khẳng định lag gây lỗi session169 vì trace .63 không ghi admission/lag. Counter model-target attempt không được diễn giải là inference thành công; target_sample_attempted và target_opinion_available tách riêng.

7 test matching mới kiểm tra event đã ghép cho GT khác, raw-clock tolerance boundary, tie order/cap4, signed deltas, hướng/class độc lập với assignment, không mutate inputs và legacy metrics. **400 differential cases /428 audited missed items** so với actual benchmarking.py trong ZIP .63: bỏ trường matching_audit mới thì mọi report field cũ giữ nguyên.

Independent comparison giữ nguyên từng byte3 policy modules counting.py/classification.py/async_tasks.py và23 core methods, gồm backend delivery/dedup, temporal matcher, unmatched review và worker class policy/deferred refinement. match_crossings chỉ thêm optional audit attachment đã xác minh; không đổi objective/tolerance hoặc scores. Tracking source cũng giữ nguyên. Không nới Gate/cooldown/dedup/class confidence để ép khớp GT.

## Source contracts và phiên bản

VERSION/frontend/API health/start message0.5.64 đồng bộ. Head `0078_replay_audit_v0564`, parent `0077_delivery_prescan_v0563`; upgrade schema_version0.5.64, downgrade0.5.63, không đổi schema/GT/events. Revision dưới32 ký tự.

New contract `Assert-ReplayAuditV0564Contract` được khai báo và gọi; các historical functions giữ lại. Rà soát độc lập949 source regex predicates,659 internal imported symbols và117 frontend runtime-field pairs, không còn findings. Hai guard legacy .41/.42 còn yêu cầu minmax460px đã đổi sang đúng media rule ≥1500px/two equal columns, giữ max-width:none; tránh test.ps1 bác bỏ layout50/50 đã sửa.

17 PowerShell scripts UTF-8 no-BOM/CRLF; source/config text khác LF. Đây là kiểm tra source/encoding/contracts; không giả lập thành PowerShell runtime pass.

npm Docker/CI/packageManager12.2.0 đối chiếu official npm CLI latest ngày08/10/2026; Node pin26.10.0 giữ nguyên. Runtime kiểm tra thực là Python3.12.14/Node24.19.0/npm11.9.0. Không tuyên bố đã cài npm12.2.0 toàn cục trên máy người dùng hoặc môi trường đóng gói.

## Giới hạn kiểm tra

Môi trường thiếu pytest/FastAPI/SQLAlchemy/Alembic/httpx2/cv2/Torch/pwsh/Docker. Không chạy full dependency-pinned pytest, HTTP/ORM/database/migration thực, PowerShell native, Docker build/npm audit/Vite build, React DOM/browser, GPU/model/video replay. Test integration vẫn nguyên trong source để scripts/test.ps1 chạy trên máy đủ Docker.

Release checks dùng isolated local Git và artifact workflow execution; không push GitHub hay tạo Release thật. publish.ps1 vẫn test→commit→push→tag→Actions/CLI fallback; source/tag/release target protection giữ nguyên.

## Chạy trên Windows

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.64 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Replay cùng clip/vạch/Road Zone, sao chép149 GT từ benchmark46 tương thích, Đối chiếu lại và Tải hồ sơ benchmark. Giữ cùng tolerance0.75s khi so sánh. Cần full ZIP hồ sơ cùng screenshots để đánh giá F1 .64 và xác định GT/event assignments.
