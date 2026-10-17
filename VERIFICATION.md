# V0.5.94 — Kiểm chứng ổn định điểm neo và Human Guard audit

Bản này tiếp tục đúng ZIP full source .93 có SHA256 `a682bac12333683a5c8dec2f563c27c3989e73b0abee19c52a7ae4945d6b0f36`, 300 file. Đã thực thi **934 kiểm thử sản phẩm, 0 lỗi**, bằng harness offline/hàm thực tế và Node; không gọi đây là một lần chạy pytest/Docker/PowerShell đầy đủ.

## Kiểm tra source và hồi quy

| Nhóm thực thi | Đạt |
|---|---:|
| AI offline: module và worker helpers thực tế | 684 |
| Backend offline: pure functions/helpers thực tế | 129 |
| Scripts stdlib unittest | 79 |
| Benchmark-gate standalone | 5 |
| Backup-worker standalone | 4 |
| Node built-in tests | 33 |
| Tổng | 934 |

Giữ nguyên danh tính và thân AST của **943 Python test cũ**, cùng cả 5 file Node test cũ (30 tests) byte-exact. Thêm 7 tracking test, 14 HumanGuard test và 3 Node test. Tổng Python test definitions là 964; 63 test HTTP/ORM chưa thực thi vẫn đúng danh sách cũ (3 AI, 60 backend), không thêm trường hợp bỏ qua. Không dùng kết quả pytest lịch sử ở phần dưới làm kết quả môi trường này.

305 source file, 205 Python parse/compile hợp lệ; 29 PowerShell UTF-8 không BOM/CRLF, text còn lại LF. 786 internal-import symbols, 1081 literal PowerShell source predicates, 79 thân hàm Assert lịch sử giữ nguyên, 121 cặp trường UI/runtime được đối chiếu. Babel parse 18 JS/JSX và xác minh 45 import/export symbols. 303 code/config/data-fixture hashes đã đóng băng; README và tài liệu này được review riêng trước khi audit ZIP.

38 kiểm tra release: 17 thực thi Git/artifact cục bộ, 14 static, 4 mô phỏng lựa chọn và 3 Bash syntax; không push GitHub hay tạo Release thật. Thêm 4 kiểm tra render component HumanGuard bằng Babel/VM: trace cũ, identity đã ghép, tuổi cache/hình học chưa biết, scope lân cận/truncation và thiếu ý kiến model. Các kiểm tra bổ sung này không cộng vào 934.

## Bằng chứng input #67 / session 194

ZIP mới: CRC, đường dẫn và toàn bộ payload SHA/byte lengths hợp lệ; gzip đọc hết EOF, dữ liệu giải nén giống tuyệt đối trace trong RAR. Trace 197.761.000 byte, SHA256 `c20b45db45090dd34a42988747971154334e38f8246a9ce07a77c96e4faa6e8a`; 23.650 frame liên tục, 271.208 Gate-track observations. RAR 191 member an toàn: 190 ảnh và đúng một trace session 194.

191 proposal = 191 terminal receipt, đối chiếu đủ các source fields. 151 created khớp 151 DB events; 40 deduplicated, drain hoàn tất, pending/dropped bằng 0. Không có bằng chứng event bị mất ở bước gửi backend.

Matcher thực tế tái tạo đúng mọi base/matched/missed/false-positive field của cả hai báo cáo:

| Chỉ số | #66 / 193 | #67 / 194 |
|---|---:|---:|
| GT / AI | 149 / 150 | 149 / 151 |
| Khớp / Lọt / Dư | 138 / 11 / 12 | 140 / 9 / 11 |
| Recall | 92,6174% | 93,9597% |
| Precision | 92,0000% | 92,7152% |
| F1 | 92,3077% | 93,3333% |
| Đúng class / đúng hướng | 136 / 136 | 137 / 138 |
| Đúng cả time/class/direction | 134 | 135 |

149 GT semantic và thứ tự giống nhau, có hai cặp trùng semantic vẫn giữ đủ multiplicity; không tự xóa vì có thể hai xe cùng frame. Config byte-exact. Khớp thêm GT 534.086505 s (AI motorcycle 533.9503 s, GT bicycle) và 640.140782 s (AI 639.7107 s); hết FP 638.12 s, không có miss/FP signature mới. Class mismatch từ 2 lên 3 vì xe đạp vừa được khớp còn sai loại; không phải một xe trước đúng bị đổi sai. Chưa chứng minh weights/model availability và toàn bộ môi trường inference giống nhau nên không suy ra quan hệ nhân quả đầy đủ từ config/path.

Đính chính ghi chú .93: ảnh mới frame 15954/15968 cho thấy track 255061 là bbox thân trên người đi xe máy. Sau khi tách identity, OUT 638.6037 s khớp GT OUT 639.119033 s; canonical 251681 IN 639.7107 s khớp GT IN 640.140782 s. Không lặp lại suy diễn đây là người đi bộ. Nội dung .93 bên dưới được giữ nguyên như lịch sử, không phải nhận định cập nhật.

## Thay đổi heading và phạm vi tái lập

Chỉ thêm inertia cho hướng điểm neo hai bánh: bán kính là nửa đường chéo lớn hơn của hai box, sàn 1.5 px. Bước tâm nhỏ hơn bán kính giới hạn góc quay ngắn nhất ở `travel/radius` radian; góc nhỏ được cập nhật ngay khi có đủ chuyển động hỗ trợ. Bước lớn từ một bán kính trở lên dùng hướng vận tốc mới ngay. Dùng góc atan2 tránh vector 0 ở trường hợp đối hướng. Không thay measured/prediction velocity, resolver association, ngưỡng cắt vạch, vùng đường hay dedup.

Flag `AI_TWO_WHEEL_HEADING_INERTIA=0` nối từ worker/Compose env_file và khôi phục đường heading .93. Xe bốn bánh, thiếu rect, heading chưa thiết lập hoặc gap quá cửa sổ dùng cách xử lý cũ. Policy/quy ước class, bao gồm van chở hàng là truck, không đổi. Counting.py và mọi rescuer giữ nguyên byte.

100 tracking test = 93 cũ + 7 mới: quay đầu thật, box nhỏ/xe nhanh, góc đối hướng, rollback/vận tốc đo, source clock/gap và fixture số liệu 677 hàng từ trace thật. Fixture 42.229 byte được đóng gói cùng source; không chứa ảnh, video, GT hoặc đường dẫn riêng. Reproducer dùng đầy đủ lịch sử target từ frame 19343, không khởi tạo lạnh ngay sát lỗi.

Track 345897: primary counter .93/flag-off tạo 5 crossing dao động; .94 còn OUT khoảng 811.925 s và IN 816.922 s. Tái lập mở rộng dùng primary + thứ tự gọi anchor-span/heavy-center/two-wheel-center rescuer thật cũng loại chu kỳ quanh 815 s. OUT sớm chưa có GT tương ứng nên không coi là nhãn sai và không khẳng định hết FP. Không thực thi lại model, HumanGuard/deferred rollback, lost-finalization, dispatcher/backend transaction hoặc association toàn clip.

Kiểm tra hình học mở rộng trên 271.208 recorded observations: 195 → 168 proposals, 142 → 143 GT khớp thời gian, giữ toàn bộ 142 GT từng khớp, proposal chưa khớp 53 → 25. Flag-off khôi phục chính xác 195 event cũ. Đây là **bộ kiểm tra có kiểm soát**, không phải 151 event DB hay F1 mới của ứng dụng. Track 354713 IN 793.828 s vẫn có rescuer tại observed frame 19841, source 793.4923 s, trong ±0.75 s; không nới counter để cứu test.

Ba assignment hướng trong phép kiểm tra tốt hơn, một assignment kém hơn quanh GT 606.18197 s. Event OUT đúng của 235019 tại 606.0992026189118 vẫn giữ nguyên time/route/geometry/frame. Proposal IN cạnh tranh của 234512 đã có từ trước, đổi 606.0901768847625 → 606.0994639160751 (khoảng 9.287 ms), trở nên gần GT hơn event OUT khoảng 0.261 ms nên matcher theo thời gian chọn khác. Các OUT 234512 tại 606.0/606.267 vẫn giữ nguyên. Ghi nhận rõ hạn chế này; không đổi matcher, GT hay tuyên bố không có trade-off. **Chưa có benchmark full pipeline .94.**

## Human Guard decision audit

Hàm `human_dominates_two_wheel_candidate` và toàn bộ `HumanGuardTrackPolicy` AST giống .93. Thêm field metadata tùy chọn và helper audit; không tăng lần inference, đổi threshold hoặc tính strike. Cache cùng frame giữ nguồn cũ, interval/out-of-order không được gọi là quan sát mới. Không có decision ghi null; hình học chưa tính ghi `geometry_computed=false` và IoU/coverage null. Lỗi metadata không làm mất decision đã suy luận thành công hoặc ngắt đếm.

14 test mới gọi worker methods/NumPy verifier thực với model double có kiểm soát; kiểm fresh/same-frame/interval/out-of-order/unavailable, rider release, strike không đếm đôi, lỗi audit, finite whitelist, bỏ path/private fields, giới hạn và parser trace cũ. 3 Node test kiểm scope đúng identity, scores/frame sai kiểu và giới hạn 8. UI hiện rõ khi chỉ có track gần timecode, chưa biết identity GT.

Bookkeeping tối đa 256 track/frame, không ghi model response/ảnh crop/path; mỗi cửa sổ chẩn đoán giữ 8 bản ghi. Bỏ audit cho bốn bánh không có guardcache/context, giữ lịch sử guard nếu class đổi. Ước lượng synthetic trên 264.972 quan sát hai bánh của input: thêm khoảng 88,8–169,3 MB JSON chưa nén tùy độ đầy đủ của decision; đây không phải đo gzip/inference mới. Giới hạn export nén 128 MiB và cơ chế trace warning giữ nguyên. HumanGuard 143399 ở 397 s chưa có crop opinions trong trace cũ: không giảm threshold/TTL/bypass chỉ từ confidence primary/periodic khác nguồn.

## Môi trường và chạy trên Windows

Runtime Python 3.12.14, Node 24.19.0, NumPy/Pydantic/ReportLab/openpyxl/pypdf có sẵn. Không có pytest, FastAPI/SQLAlchemy/Alembic/httpx/httpx2, cv2/Torch, PowerShell hoặc Docker. Chưa thực thi HTTP/ORM/PostgreSQL/migration live, npm install/audit/Vite build với phiên bản pin, browser/React DOM hay GPU/full-video replay. Các module report/PDF/font/license và kiểm tra cũ được giữ byte-exact; không chạy lại PDF render không liên quan. Hướng dẫn Windows dưới đây chạy bộ kiểm tra Docker chính thức và vẫn cần môi trường/model của bạn.

Migration `0108_guard_audit_v0594` → parent `0107_reports_guard_v0593`, chỉ đổi schema_version .94, downgrade .93; không cập nhật GT/events. Không push GitHub hay tạo Release thật trong lượt này.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.94 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Chạy lại cùng clip/vạch/model, sao chép GT đã review và xuất benchmark ZIP sau khi có GT để đo bản .94. Không tạo lại Admin. Các phần sau là lịch sử kiểm chứng được giữ nguyên.

---

# V0.5.93 — Kiểm chứng source, báo cáo và sửa nối ID

## Kết quả hiện tại

| Phạm vi | Đã thực thi |
|---|---:|
| AI algorithms/worker helpers offline | 663 đạt |
| Backend pure algorithms/helpers offline | 129 đạt |
| Scripts unittest | 79 đạt |
| Benchmark gate standalone functions | 5 đạt |
| Backup worker standalone functions | 4 đạt |
| Frontend Node tests | 30 đạt |
| **Tổng kiểm tra thực thi** | **910 đạt, 0 lỗi** |
| HTTP/ORM integration chưa chạy | **63**, gồm 62 cũ và 1 SQLite report test mới |
| Supplementary report UI checks | 7/7 Babel/Node VM có kiểm soát; không cộng vào 910 |
| Local release checks | 38: 17 executed, 14 static, 4 simulation, 3 Bash syntax; không cộng vào 910 |

Đây **không phải full pytest**. Runtime hiện tại Python 3.12.14 / Node 24.19.0 / npm 11.9.0, có NumPy/Pydantic/ReportLab/openpyxl/pypdf nhưng thiếu pytest/FastAPI/SQLAlchemy/Alembic/httpx/httpx2/cv2/Torch/pwsh/Docker. Một lần thử cài dependency có timeout ngắn không lấy được gói, không tiếp tục lặp cài hay gọi các kiểm tra bị loại là đã chạy.

Các Python test function thực tế chạy bằng harness với fixture tối thiểu approx/raises/tmp_path/monkeypatch; worker/backend helpers trích AST để tránh import HTTP/ORM chưa có. Dispatcher dùng queue/thread với HTTP được kiểm soát. Scripts unittest và frontend node --test chạy bằng runtime thực.

Giữ đủ **926 Python test identity cũ**, thêm 17 (6 tracking + 11 report), tổng 943 definition. Giữ đủ 19 Node test cũ, thêm 11 thành 30. Không sửa assertion/body của test cũ. 63 integration exclusion gồm 3 AI + 59 backend cũ và 1 report SQLite mới; tổng 880 Python function thực thi + 63 chưa chạy = 943 definition, cộng 30 Node = 910 kiểm tra đạt.

## Rà soát full source

Baseline đúng ZIP .92 người dùng gửi: **641.978 byte / 290 path**, SHA256 `a85220e42e266261f45642d43d43dfeb6c3890ffb86602d6f3950cd34b1c8ed9`. Source .93 giữ đủ 290 path, thêm 10, tổng 300 file. Không đóng gói .env thật, runtime volumes, camera RAR, video, model weights, trace/raw input hoặc caches.

- 203 Python file parse/compile hợp lệ; 107 migration, head `0107_reports_guard_v0593`, parent `0106_cycle_witness_v0592`, revision dưới 32 ký tự. Migration chỉ cập nhật schema_version 0.5.93, downgrade 0.5.92.
- 29 PowerShell script UTF-8 không BOM / CRLF; các text source/config khác giữ LF. Historical contract và các lệnh cũ được giữ lại.
- 1.071 source predicate PowerShell, 774 internal Python import symbol, 121 frontend runtime-field pair được rà soát, không còn finding. Đây là kiểm tra tĩnh, không phải PowerShell runtime.
- Babel parse 16 JS/JSX file và 43 local import/export symbol đạt, không phải Vite build hoặc React DOM/browser.
- 298 code/config SHA256 đã đóng băng sau các kiểm tra cuối; README/VERIFICATION review và pin riêng trước đóng gói.
- Legacy counting/Gate/worker/classification/Human Guard / backend dedup / matching giữ nguyên byte của .92. Tracking chỉ thay lower bound của đúng một guard 4→1; khôi phục lower bound thì toàn bộ AST algorithm trở về baseline. CSS cũ giữ nguyên byte; report CSS dùng selectors riêng.
- API report router được đăng ký trong backend main; global authentication/RBAC middleware không đổi. Viewer chỉ xem, Admin/Operator export; đường dẫn /export tiếp tục bị viewer từ chối theo policy hiện có.

## Dữ liệu benchmark và trace đã đối chiếu

Benchmark #66/session 193 ZIP có 5 data JSON cùng manifest: kiểm SHA256 và byte lengths đủ 5 file. Dùng hàm match_crossings thực tế của source hiện tại tái tính, tất cả base fields/matching rows khớp report:

| Chỉ số input .92 | Giá trị |
|---|---:|
| GT / AI | 149 / 150 |
| Khớp / Lọt / Dư | 138 / 11 / 12 |
| Recall / Precision / F1 | 92,6174% / 92,0000% / 92,3077% |
| Đúng class / đúng hướng | 136/138 / 136/138 |
| Khớp đủ time/class/direction | 134 |
| AI IN / OUT | 69 / 81 |

RAR 158.592.235 byte, SHA256 `4f433ae6bb9e38d8a2556a1030c962f51830c2995a959e51e8b6918d42591a0f`, có 380 member có đường dẫn an toàn, không trùng, gồm **cả session 192 và 193**. Không nhầm trace 192 thành 193. Trace 193: 196.117.028 byte, SHA256 `4417cbfc80e8401615c7a8a04174bed92b9f2fb09c1fe7e101b8c16aa07726e8`; trace 192: 197.559.471 byte, SHA256 `7ff2972c2f808b3bf556bdb0f97ea588bda8ae60e5d6ba6b4489ca266674daae`.

Mỗi run có 23.650 frame liên tục, 271.208 Gate-track observation, 191 proposal = 191 terminal receipt, 150 created + 41 dedup. Mọi receipt khớp 11 source field của proposal; 150 created khớp đủ 150 DB event. Drain complete/pending 0 / dropped 0; không có bằng chứng rơi event khi gửi backend.

Hai run 192/193 giữ frame/time/hướng/loại/điểm cắt/tracking/outcome/dedup reason; một confidence khác nhẹ tại 86667 IN 250.5291 s. Cùng 150 AI và cùng 11 lọt / 12 dư; .92 thêm audit không giải quyết các lỗi này. Crossing-cycles người dùng gửi là benchmark 65 / session 192; năm cặp được crosswalk duy nhất sang 193 bằng chữ ký chính xác, không gán raw witness 192 cho 193.

GT đang có 0 truck / 1 car / 4 bicycle, AI 2 truck / 0 car / 1 bicycle. Sai loại OUT 641.981 GT car → AI truck và IN 289.449941 GT bicycle → AI motorcycle được xác nhận bằng report. Van IN 882.2898 không có GT trong ±0,75 s; không dùng điều đó để tự xóa AI hoặc đổi van về CAR. Người dùng cần review GT theo clip và quy ước van chở hàng là Xe tải.

## Sửa nối ID và phạm vi hiệu quả

Canonical 251681 bị raw 255061 chiếm đúng một quan sát ở frame 15954, tạo event IN 638.12. Ảnh mục tiêu cho thấy box người đi bộ kế thừa identity/rider của track xe. Proposal 251681 IN 639.7107 gần GT 9635 IN 640.1409 sau đó bị backend same-track-repeat-jitter gộp vào event sớm.

Giữ guard .85 hiện có nhưng mở window gap 4–12 thành 1–12 frame, chỉ cho candidate hai bánh khác raw ID, đủ hai rect và đồng thời direct_jump >1.75 × footprint / predicted_jump >1.50 × footprint. Switch AI_SHORT_GAP_ALIAS_GUARD vẫn là rollback; không thay global distance, prediction threshold, Gate/tolerance/cooldown/dedup/HumanGuard/heading/class.

93 tracking test thực thi, gồm 87 cũ và 6 mới; là subset của 663 AI. Có controls gap 1/2/3, xe nhanh khớp prediction, flag off, bốn bánh/gap > 12/missing rect / known raw.

Reproducer có kiểm soát dùng 158 dòng đo thật của target, resolver thực từ ZIP baseline/current và primary counter/defaults trích từ worker. .92 ghép raw 255061 vào 251681 và phát crossing 15954. .93 để raw 255061 giữ identity riêng, giữ 251681 ở 15957/15997 và primary counter phát IN 639.7106917 s tại observed frame 15996. Trace từ pipeline worker đầy đủ trước đó chọn cùng source clock nhưng gửi ở frame 15997; khác biệt observed frame được ghi rõ. Tắt flag khôi phục kết quả baseline của reproducer.

Đây là replay chọn lọc observations, không chạy detector/tracker/model/HumanGuard/dispatcher/backend dedup toàn pipeline và **không phải F1 mới**. Case 345897 còn anchor dao động theo cạnh box trong lúc center ổn định; không sửa heading thiếu kiểm chứng. Human Guard 143399 dùng cùng raw ID trước crossing, trace thiếu person/rider opinions nên không có căn cứ giảm ngưỡng/TTL/bypass. Không tự thay GT hoặc hứa đã hết 11 lọt / 12 dư.

## Báo cáo nâng cao và exports

Pure aggregation kiểm tra ngày UTC+7 `[start,end)`, giới hạn 366 ngày / 31 ngày theo giờ, zero-fill hour/day/month, tổng IN/OUT/unknown, camera/class/session filters, 5 peak-hour bucket, tie-order, dữ liệu rỗng và giới hạn 100.000 nhóm không âm thầm cắt tổng. SQL query chỉ đọc detected_at/events; video source_time_seconds không bị cộng vào ngày hiện tại hay suy diễn thành ngày quay.

10 pure test báo cáo thực thi; một SQLAlchemy/SQLite integration test chưa chạy và được giữ trong source. XLSX mở lại bằng openpyxl, 5 sheet, numeric cell thật, Unicode và không có formula; CSV UTF-8 BOM xử lý ô có khả năng bị hiểu là formula. PDF có font DejaVuSans nhúng cùng giấy phép, ToUnicode, phân trang + header lặp; pypdf đọc 4 trang và tiếng Việt, Poppler render/xem đủ 4 trang. Tiêu đề section dùng keepWithNext tránh mồ côi bảng. ReportLab thực tế 4.4.9; production/test dependency pin 5.0.1 chưa cài được trong runtime này.

11 Node test mới kiểm tra whole-day/UTC+7/query/export whitelist/totals/NaN chart. 7 kiểm tra Babel/VM có kiểm soát thực thi handler/render với schema backend thực, pending/stale selection, viewer permission, blob download/revoke, HTTP 403 / wrong MIME / unmount; không gọi đây là browser test.

Đối chiếu 150 event thực session 193 qua report helper: 150 / IN 69 / OUT 81 / MC 147 / bike 1 / truck 2, đúng dữ liệu gốc. Đồng hồ detected_at của chúng nằm **15/10/2026, 21h UTC+7** dù file đính kèm 16/10; UI điền ngày theo phiên. Chart/peak thể hiện thời điểm hệ thống ghi nhận, không khẳng định giờ giao thông thực ngoài đời của video replay. Chọn một phiên tránh cộng nhiều lần chạy lại cùng clip.

## Giới hạn và chạy trên Windows

Chưa chạy native PowerShell / Docker / PostgreSQL / HTTP ORM / migration live, pytest với dependency đã pin, npm audit/Vite production build, React DOM/browser, GPU/full video/model replay. Không publish GitHub hoặc tạo Release thật; 38 release check chỉ Git/artifact cục bộ và static/simulation/syntax.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.93 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Trong Báo cáo, chọn camera/phiên và Xem báo cáo trước khi xuất. Để đánh giá bản sửa đếm, chạy lại cùng clip/vạch/model, benchmark mới dùng GT đã review, đối chiếu và xuất ZIP sau khi có GT. Bản này giữ đủ lịch sử source .92; những kết quả các bản cũ ở phần dưới là lịch sử, không phải phép chạy của môi trường hiện tại.

---

# V0.5.92 verification

- Source based on V0.5.91 full source ZIP, benchmark #65 Session #192 and 190 uploaded camera snapshots.
- Verification pipeline: signed ZIP/manifest hash, closed trace, raw source SHA-256 + byte count; 150 AI events, 149 GT, 138 matched, 11 missed, 12 extra, 92.3% F1 unchanged.
- New cycle audit: 5 pairs within 12 seconds; 2 pairs involve unmatched AI; raw-ID evidence changed for 3 pairs. No automatic event suppression, GT edits or claims of improved F1.
- Node frontend test coverage now 19 tests; scripts Python regression suite 79 tests; AI pytest 660, backend pytest 178, backup worker pytest 4. Backend and AI tests use `httpx2` alias to installed `httpx` **only in test interpreter, not in production source**; backend SQLite in-memory; production Docker must be tested on Windows.
- Packaging verified: version-contract, Alembic head <=32 chars, PowerShell CRLF, Python compileall; new script powershell contract and JS UI navigation module.
- Node 22 locally, project requires Node >=26.10; Vite production bundle and Docker/GPU replay not verified in this environment.

# V0.5.91 verification

- Verified ZIP benchmark #64 report, 149 GT / 150 persisted AI / 138 matched / 11 missed / 12 extra.
- Comparator vs #62: identical GT and 150 persisted crossing signatures, no measured performance change.
- New read-only frontend case navigator: 7 Node.js tests and a PowerShell contract.
- Executed: 660 AI tests, 178 backend tests, 71 script tests, 15 frontend Node tests, 4 backup worker tests.
- AI/backend used a temporary `httpx2 -> httpx` import shim outside the source, and backend tests used an in-memory SQLite URL. This does NOT validate the production httpx2 and PostgreSQL stack.
- JSX parsed/transpiled without error using TypeScript 5.x. Vite production build unavailable (Node 22 versus required >=26, package registry DNS blocked).
- No real GPU/video replay performed; no new F1 result can be claimed.

# V0.5.90 — Verified AI-only comparison for unscored benchmark exports

- Input: integrity-verified `traffic-ai-benchmark-62-session-188.zip` (GT 149) and `traffic-ai-benchmark-63-session-190.zip` (GT 0, exported before copy).
- Confirmed identical 150 persisted event signatures, 0 added/removed; reports **no GT metric comparison** because the second ZIP has no GT.
- Later screenshot shows GT 149 / AI 150 / matched 138 / missed 11 / extra 12 / F1 92.3%; those results are NOT in the attached older ZIP.
- Comparison tool validates all six manifest-tracked JSON documents, trace digest, session ID, conservation of AI event count, persistence integrity, video/gate/FPS geometry. For scored pairs it retains existing GT fingerprint/tolerance check and benchmark-gate conservation tests.
- Eleven new tests (including five verified error-queue tests) cover unscored-to-scored, scored-to-unscored, changed AI signatures, forged score, tampered hash, incompatible FPS.
- No inference algorithm change, no measured F1 improvement. Windows/Docker/GPU testing still required by the user.

---

# V0.5.89 — Release packaging, immutable tag safety

- Source from V0.5.88 ZIP; new metadata-only migration `0103_release_eol_v0589`.
- Packaged PowerShell file line endings are CRLF (before any Windows publish run).
- `.gitignore` now excludes downloaded root-level benchmark ZIPs, camera RARs
  and benchmark comparison output (previously eligible for git add -A).
  A publish guard rejects those artifacts if they were already staged.
- `publish.ps1` still refuses to move an existing local/remote Git tag; logs only
  names and statuses of changed files, not file contents.
- Windows V0.5.88 user's supplied log independently verifies existing official
  `test.ps1`, Docker image build/start, GPU service readiness and local HTTPS.
- Local checks after V0.5.89 changes: 660 AI pytest, 178 backend pytest,
  4 backup worker pytest, 60 scripts unittest, 8 frontend node tests:
  **910/910 tests passed**. Backend test environment used a temporary test-only
  `httpx2` shim outside the packaged ZIP; not a substitute for Docker testing.
- Existing-tag error occurred before source push; v0.5.89 publish on Windows
  and GitHub Actions has NOT been executed here.
- No changes to inference or benchmark comparison outcomes; the baseline of
  GT 149 / AI 150 / missed 11 / extra 12 is not claimed to improve.
- Git status in user's repository cannot be inspected from this ZIP; existing
  tag + pending changes may have causes besides CRLF normalization.

---

# V0.5.88 — Verification and limitations

- Root cause: V0.5.67 PowerShell contract pinned obsolete literal `Tổng GT = AI`,
  but V0.5.87 frontend correctly supports competition review when totals differ.
- Refactored presentation predicate into JS module covered by four focused tests.
- Contract now checks the predicate integration, both audit fields, backend regression,
  and explicit equal/unequal count frontend regression cases.
- No AI inference, crossing thresholds, GT marks or benchmark event data modified;
  no measured F1 improvement claimed.
- **Local automated verification:** AI 660/660 (pytest), backend 178/178 (SQLite-memory
  pytest), scripts 55/55 (Python unittest), backup worker 4/4 (pytest), frontend 8/8
  (Node built-in test runner): **905/905**. All Python `compileall` and
  `scripts/version-contract.py` passed.
- The Alembic revision name initially exceeded the historical 32-character limit;
  it was shortened to `0102_temporal_review_v0588` (26 chars). Version checker now
  fails on future oversized migration IDs and has a regression test.
- Backend/AI test runs used a temporary **test-only** `httpx2` import shim outside
  the ZIP because `httpx2` is not installed here; this is not validation of the
  production dependency. Linux Node 22 executed the JS test runner; Vite production
  build requires the project's configured Node 26 environment.
- **Not run:** Windows PowerShell `scripts/test.ps1` as a whole, Docker image builds,
  Windows startup, PostgreSQL integration, Vite production build and GPU inference.
  Rerun the full official test script on the user's Windows host before publishing.

---

# V0.5.87 — Verification and limitations

- Validated completed Benchmark #61 and #62 source archive hashes, compared GT/event crossing signatures, reviewed trace and selected camera JPEGs. The before/after GT 149 / AI 150 / matched 138 / missed 11 / extra 12 is **unchanged**.
- New script `compare-benchmark-exports.py` is read-only; never relabels GT or emits new AI events. New frontend temporal audit block fixes hidden review when GT 149 differs from AI 150.
- Full inference replay with GPU/model/MP4, Windows Docker stack and real PowerShell tests must be performed on the user's machine. No new precision/recall claims.

---

# V0.5.86 — Verification and limitations

- Benchmark #61 / Session #187 ZIP fully validated by the bundled read-only forensic tool (trace compressed/uncompressed SHA256, metadata, delivery drain). Baseline: GT149 AI150 matching138 missed11 extra12, direction2 and class2 mismatches; **these are V0.5.85 values**.
- JPEG RAR inspected with libarchive: 190 images, specific frames 7243, 16050, 22059 visually reviewed. No model weights / original MP4 were supplied in the source ZIP; no GPU inference or 23,650-frame replay done here.
- `tests/test_tracking.py` adds 5 regression scenarios for the new two-wheel 4–12-frame visible-incumbent reservation; existing main counts/gate algorithms unchanged. Before claiming quality improvement, rerun clip and export new benchmark/trace.
- Sandbox automated verification: **660/660 AI pytest**, **178/178 backend pytest** (in-memory SQLite), **4/4 backup-worker pytest**, **47/47 scripts unittest**, **4/4 frontend Node tests** = **893/893 tests passed**. Benchmark forensics validated the supplied ZIP with both compressed and decompressed trace SHA-256, and produced 23 audited cases. Full Python `compileall` passed, `scripts/version-contract.py` passed, TypeScript JSX parser reported **0 syntax diagnostics** for the frontend.
- Missing native `httpx2` package was replaced with a **test-only** `httpx→httpx2` compatibility alias placed outside the ZIP; this is not production validation of `httpx2`. Backend tests used `DATABASE_URL_OVERRIDE=sqlite+pysqlite:///:memory:`; PostgreSQL/live services were not started.
- **Not executed**: `scripts/test.ps1` under Windows PowerShell, Docker stack, GPU/video replay, frontend Vite production build, full HTTP system integration and publish/GitHub Actions. Run `scripts/test.ps1` on the target Windows machine before publishing.

---

## Verification of previous versions

# V0.5.85 — Verification and limitations

## Những phần đã kiểm chứng trong môi trường hiện tại

- AI Service: **655/655 pytest PASS**, bao gồm 4 test mới về alias bất thường, tiếp tục xe nhanh, xe 4 bánh và chế độ rollback.
- Backend: **178/178 pytest PASS** trong SQLite memory, với test token riêng cho CI.
- Backup Worker: **4/4 pytest PASS**.
- Frontend: **4/4 node --test PASS**.
- Công cụ: **47/47 unittest PASS**. Dòng `[FAIL]` của negative test replay là output kỳ vọng; unittest tổng kết OK.
- Tổng cộng **888/888 test đạt**. `scripts/version-contract.py` kiểm tra version và migration chain PASS.
- Lớp tương thích `httpx2` trong lúc test ở đường dẫn ngoài source; **không có trong ZIP**.

## Giới hạn quan trọng

- **Chưa chạy lại GPU/video nguồn** cho V0.5.85. Không có bằng chứng đã giảm 11 lượt lọt / 13 lượt dư ở Benchmark #60.
- **Chưa chạy Docker, PowerShell và Vite production build** trong môi trường này. `test.ps1` trên Windows sẽ kiểm tra chúng trước khi phát hành.
- Guard mới có thể tắt tạm bằng `AI_SHORT_GAP_ALIAS_GUARD=0` để so sánh, sau khi khởi động lại AI Service. Không thay đổi GT hoặc dữ liệu lịch sử.
- Không đóng gói video, trace camera, RAR, `.env` hoặc database người dùng.

## Phân tích nguồn

Xem `docs/session-186-alias-handoff-v0585.md`. Nhóm sự kiện tại 606 giây mới là giả thuyết có bằng chứng quỹ đạo; kết quả cuối phải được xác nhận bằng phiên replay mới.

---

## Xác minh V0.5.84 trước đó

# Traffic AI V0.5.84 - Verification

## Baseline: GT benchmark #59 / Session #185 (V0.5.83)

- Source video: 23,650 frames, 25 FPS.
- GT 149; AI 151; timecode matched 138; strict matched 134.
- Missed 11; extra 13; wrong-direction 2; wrong-class 2.
- The V0.5.84 source has **not** been GPU-replayed against the video; no
  claim of numerical improvement to GT recall or precision is made.

## Implemented

- Dual-provenance Raw ID Reuse Guard: inspect separately measured Raw ID
  trajectory AND canonical-alias handoff to avoid hiding a genuine ID jump
  behind another alias' recent coordinates. Large canonical alias jumps
  remain fail-closed to avoid manufactured vehicle passages.
- Raw observations are pruned with canonical TTL cleanup. The gate,
  cooldown, rescue, class refiners, existing direct-shadow protection,
  backend authorization, backup/restore and PostgreSQL schema are unchanged.
- Read-only ZIP raw-id audit now distinguishes **worker cumulative resets**
  from jumps present in **gate_tracks** sample. Timecodes and GT-nearness are
  review hints only, not proof of a causal relationship.
- V0.5.84 migration is metadata-only; no table schema change.

## Tests run in this environment

| Suite | Result |
|---|---:|
| Backend pytest (SQLite in-memory) | 178/178 PASS |
| AI Service pytest | 651/651 PASS |
| Backup Worker pytest | 4/4 PASS |
| Frontend node --test | 4/4 PASS |
| Scripts stdlib unittest | 47/47 PASS |
| **Total** | **884/884 PASS** |

- Source version/migration chain check: PASS.
- Benchmark #59 trace: gzip SHA-256 verified, 23,650 frames scanned;
  10 worker Raw-ID resets and 0 gate-sampled discontinuities.
- Worker reset nearby missed GT (within 2 seconds): at 58.280s and
  290.160s. This is **not** proof of a false reset or a recovered count.
- Backend/AI tests use a temporary `httpx2` compatibility shim located
  **outside** the ZIP because that dependency is not installed in the
  execution environment. Do not treat the shim as a substitute for a real
  Docker/runtime dependency test.
- Not executed here: PowerShell on Windows, Docker Compose startup,
  PostgreSQL restore, full Vite production build, GPU video replay and
  GitHub Actions on the remote runner.
- Before publishing, run `scripts/test.ps1`, then `scripts/start.ps1` on
  Windows, and compare a fresh GT benchmark. Retain Docker volumes and `.env`.
