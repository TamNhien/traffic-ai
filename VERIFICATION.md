# V0.5.97 — Kiểm chứng rà soát hình học và đổi raw ID

Baseline là ZIP .96 SHA256 `bb4609315117077df430f2382a126abf57fd6365e138369b2b106b6e4256ed27`, 313 file. V0.5.97 thêm bằng chứng đọc từ trace và giao diện xem video trước/sau; không đổi thuật toán detector, tracking, counting, class policy, Human Guard, rescuer, dedup, matcher hoặc GT.

## Input và đối chiếu benchmark thực tế

Input mới: `traffic-ai-benchmark-69-session-196.zip`, SHA256 `871887eb3326d48c7949f3aa643dded85f26dddf498b0fd9a4a8d1b9a43c5c55`. Bảy member an toàn/CRC tốt; sáu member dữ liệu khớp toàn bộ SHA/size trong manifest, gzip đọc đến EOF. Trace có 23.650 frame liên tục, source time 0..945.96 s ở 25 fps. Bytes trace từ RAR giống gzip export sau giải nén.

167 proposal = 166 committed_before_submit + 1 submitted_after_guard. Có 167 delivery receipt, 150 created + 17 deduplicated; 150 created tương ứng đủ tập event DB, mọi source field khớp. Drain complete, pending/dropped 0, mỗi acknowledgement một lần thử. Không có bằng chứng mất lượt do gửi backend.

Đối chiếu đủ cả export #68/195 và #69/196: 149 GT tương đương theo thời gian/frame/hướng/loại/note; config byte-exact. 149 AI event cũ giữ nguyên source time/frame/direction/class/track/method/xy/confidence. Thêm duy nhất motorcycle IN 143399 tại 397.0209 s khớp GT 397.288 s. Matcher source thật tái tạo cả hai report: matched 142→143, lọt 7→6, dư 7→7; F1 0.953020→0.956522; strict match 137→138. Không có GT lọt mới hoặc FP mới trong phép đối chiếu này.

6 GT chưa ghép: 59.446 IN, 237.042 OUT, 289.824 IN, 392.179 OUT, 406.488 OUT, 591.091 IN bicycle. 7 event chưa ghép: 15369 OUT 54.296, 110284 OUT 292.864, 181574 OUT 491.920, 191795 OUT 519.418, 368014 OUT 808.000, 345897 OUT 811.925, 286434 truck IN 882.290. Gần thời gian không chứng minh cùng phương tiện.

## Bằng chứng ảnh và lựa chọn triển khai

Ảnh frame 12299/12306 cho thấy một xe máy với hai box 181574/182056; hai track cùng hiện ở 5 frame được giữ trong fixture. Trước crossing thứ hai chỉ có hai quan sát cặp; vận tốc lọc cosine khoảng 0.989 nhưng dịch chuyển tâm box thực giữa hai frame cosine khoảng 0.717. Predicate thử nghiệm có thể chọn đúng cặp này trên clip nhưng cũng nhận một convoy bị che trong phản ví dụ hình học. Vì vậy .97 chỉ đưa ra bằng chứng rà soát, không bật rule suppression theo cặp này. Audit dùng quan sát cả trước/sau trong cửa sổ; không phải cơ chế chống trùng chạy nhân quả tại thời điểm event.

Track 296297 đổi raw 312739→331821 từ frame 18842→18860, gap 18 frame và tâm box dịch khoảng 236 px. Token mới sau đó đi lên nhưng crossing rescue đã ghi IN. Frame đầu token mới thiếu motion riêng; không mở rộng/nới ngưỡng alias guard chỉ từ một mẫu.

Ảnh frame 7243: người dắt xe đạp và xe máy track 25767 là hai đối tượng riêng; không đổi track xe máy để khớp nhãn GT bicycle. Frame 13355 có hỗ trợ bicycle từ general refiner nhưng không đủ hai nguồn theo policy hiện tại. Ảnh frame 16050 là van chở hàng phù hợp truck; ảnh frame 22059 cho thấy van cắt vạch IN thật. Không tự đổi GT hoặc loại event van. Tại 591.091 s thiếu track/proposal ở vạch và không có ảnh đúng thời điểm/raw detections, nên chưa chứng minh tầng nào gây lọt; road-zone reason là heuristic toàn frame.

## Tích hợp và giới hạn bằng chứng

`ObservedTrackAudit` đọc cùng các cửa sổ trace đang được chẩn đoán; không chạy thêm model hoặc quét trace riêng. Giới hạn mỗi cửa sổ: 256 frame, 64 track/frame, 16 peer lưu, 4 peer trả ra, 8 lần đổi raw ID; có cờ truncated. Độ phủ là intersection/diện tích box nhỏ; bottom alignment là chênh mép dưới/chiều cao box lớn. Đây là phép đo, không phải xác nhận identity. `max_consecutive_frames` là số frame đồng xuất hiện liên tiếp, không phải số lần nested liên tiếp.

Backend bổ sung target dư và sai hướng bằng time/track của event DB, chiếu lại đúng canonical owner và giới hạn trường số. Frontend từ chối scope/owner/schema sai, số không hữu hạn và identity claim; phân biệt actual box displacement và filtered velocity. Seek controls nằm ngoài nút timecode. Trace cũ thiếu rect/raw/velocity được xử lý như thiếu bằng chứng.

## Kiểm thử .97

| Nhóm thực thi | Đạt |
|---|---:|
| AI offline / worker helpers | 704 |
| Backend offline | 135 |
| Scripts stdlib unittest | 95 |
| Benchmark-gate standalone | 5 |
| Backup-worker standalone | 4 |
| Node built-in tests | 43 |
| Tổng | 986 |

Không có lỗi. Thêm 21 Python và 10 Node tests; giữ nguyên 986 test identities/thân AST Python lịch sử, cả 6 file Node cũ/33 tests và 79 thân hàm Assert lịch sử. Tổng định nghĩa Python hiện tại 1007; đây là số definitions, không phải số test thực thi.

63 HTTP/ORM tests chưa thực thi vẫn đúng danh sách cũ (3 AI, 60 backend). 1 native PowerShell runner skip riêng vì thiếu pwsh, không tính là đạt. Các regression mới gồm fixture thật 181574/182056 và 296297, box/time/owner sai, clock lặp/đảo/xung đột, số không hữu hạn, giới hạn bộ nhớ, peer truncation và projection backend; UI tests giữ actual displacement khác filtered velocity và kiểm tra không sửa input/score.

320 source file; 214 Python parse/compile; 31 PowerShell UTF-8/CRLF không BOM; text khác LF. Đã kiểm 795 internal imports, 1096 literal PowerShell source predicates và 121 cặp UI/runtime. Babel parse 20 JS/JSX và 47 relative import/export symbols. 38 release checks: 17 thực thi Git/artifact cục bộ, 14 static, 4 simulation, 3 Bash syntax; không push GitHub hoặc tạo Release thật.

Replay matcher thật của .96 và .97 trên cùng GT/events cho output giống nhau hoàn toàn và khớp report #69, input không đổi. Replay diagnose_trace thật trên trace 326.237.314 byte, 18 target (6 lọt, 3 sai loại, 7 dư, 2 sai hướng), cửa sổ ±0.75 s: .97 khoảng 4.489 s, peak RSS 21.632 KiB tại đây. Chỉ bỏ field observed_track_audit mới thì toàn bộ diagnosis cũ giống .96. Đây là một lần đo cục bộ, không tuyên bố tăng tốc hoặc bảo đảm timeout trên mọi máy.

Trong cửa sổ mặc định của FP 491.92 s, thực tế trả 4 frame cặp với peer 182056 (12305..12316), không phải toàn bộ 5 frame có trong fixture; cửa sổ kết thúc trước frame 12318. Có 2 frame đồng xuất hiện liên tiếp, sau đó có gap 9 frame. Độ phủ 0.937083..0.999671; target còn có raw handoff 181574→182056 rồi quay lại. Ca sai hướng 296297 trả đúng handoff gap18, tâm box dịch [-56.7605,229.6465] px. Các bằng chứng đã được chiếu lại qua backend và kiểm tra bởi frontend view model.

Môi trường hiện tại Python 3.12.14 / Node 24.19.0, khác runtime pin Python 3.14.7 / Node >=26.10.0 / npm12.2.0. Chưa chạy .97 native PowerShell/Docker, full pytest HTTP/ORM, PostgreSQL/migration live, npm install/audit/Vite production build, trình duyệt hoặc GPU/full-video inference. Không cài thêm dependency. 955 test của .96 được chạy lại làm baseline và ghi riêng, không cộng vào 986. F1 95.6522% thuộc export phiên 196 do bạn gửi; ảnh giao diện hiển thị .96 nhưng trace không có version/build hash để độc lập xác minh bytes runtime. Không suy ra F1 .97 hoặc số lượt lọt/dư sau inference mới.

## Sử dụng

Giữ .env/.git/models/video/snapshots/volumes khi chép source. Cache test vẫn tách khỏi source như .96; ZIP dùng timestamp UTC build mới và kiểm tránh trùng timestamp cũ của Python member đổi bytes. Migration metadata `0111_count_review_v0597`, parent `0110_pycache_v0596`, chỉ nâng schema_version .97 / downgrade .96.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.97 và Release
.\scripts\publish.ps1
```

Chọn benchmark #69 rồi Đối chiếu lại để đọc bằng chứng từ trace hiện có. Không tạo lại Admin. Các mục dưới đây là lịch sử, không phải các phép chạy .97 mới.

---

# V0.5.96 — Kiểm chứng sửa Python bytecode cache

Baseline là full source .95, SHA256 `0966e3d02e908b7ee11cb5936afda3a75ad46cf20e436e5edbc49b998ec9dd4d`, 311 file. Bản .96 sửa môi trường chạy test và cách đóng gói. Không sửa predicate HumanGuard, tracking, counter, worker, rescuer, dedup, matcher hoặc GT.

## Log mới do người dùng cung cấp

File `Văn bản đã dán (1)(20261017-124555).txt` có hai lần chạy .95. Mỗi lần đều qua static version contract `0.5.95`, migration `0109_docker_guard_v0595`, host Docker readiness **26 assertions** và các bước Docker trước backend tests.

Backend pytest mỗi lần: **186 passed / 3 failed**, lần lượt 8.18 s và 8.63 s. Ba lỗi là `test_root_metadata`, `test_backend_version_metadata`, `test_v0533_version`: app trả .94 trong khi VERSION đọc từ source là .95. Hai lần lặp cùng scenario không được cộng thành 52 native tests hoặc 372 backend tests mới. Đây là bằng chứng người dùng chạy Windows/Docker .95, không phải .96 tại môi trường này. Lỗi `[ERROR]`/`[FAIL]` trong các test âm về replay trước đó là output dự kiến và các test đó vẫn `ok`.

## Tái lập nguyên nhân bằng source đã gửi

Lấy chính `backend/app/main.py` từ ZIP .94 và .95: mỗi file 1181 byte, khác version; cả hai có ZIP timestamp `2026-10-17 00:00:00`. Tạo `.pyc` timestamp-based bằng CPython rồi chép bytes .95 lên cùng mtime/kích thước. Tiến trình Python riêng dùng SourceFileLoader thật nhận code constants .94, mặc dù source đọc trực tiếp có .95.

| Cách đọc source sau overlay | Kết quả tái lập |
|---|---|
| Cache mặc định | Còn code .94 |
| `-B` | Còn code .94 |
| Chỉ `PYTHONDONTWRITEBYTECODE=1` | Còn code .94 |
| `PYTHONPYCACHEPREFIX` mới | Code .95 |

Reproducer không thực thi FastAPI hoặc gọi HTTP endpoint: nó kiểm đúng bytecode mà loader import sẽ nhận. Vì vậy không gọi đây là chạy lại ba backend HTTP test trong môi trường hiện tại. Bằng chứng dùng artifact thật và cơ chế CPython thật phù hợp trực tiếp với lỗi version trong log; không sửa expected version để làm test đạt.

8 regression mới gồm subprocess import thật, no-write flags, prefix mới, prefix cũ bị tái dùng, compileall với prefix riêng và coverage các Docker Python calls. Bộ kiểm tra chạy trên Python 3.12.14 tại đây; log Windows dùng Docker Python pin 3.14.7. Chưa chạy lại container 3.14.7 .96 ở môi trường này.

## Thay đổi và rà soát cache

19 lệnh Docker Python cũ giữ nguyên command text khi bỏ hai env flags mới; thêm một bước regression, tổng 20 lệnh đều có prefix `/tmp/traffic-ai-test-pycache` và no-write env. Prefix nằm ngoài `/src` bind mount, không có volume gắn vào nó, và thuộc container `--rm` mới. Việc tái sử dụng một prefix đã chứa cache cũ vẫn có thể gây stale import; regression bao phủ điều đó, nên thiết kế dựa vào cache filesystem mới của từng container chứ không coi prefix string tự nó luôn mới.

`compileall` chủ động tạo bytecode kể cả khi bật no-write, nhưng khi có prefix thì output ở `/tmp` của container. `.dockerignore` không áp dụng cho bind mount khi chạy test; nó bảo vệ build context riêng. Backend/AI được bổ sung `**/__pycache__`, `**/*.pyc`, `**/*.pyo`, giữ các rule cũ. Docker hỗ trợ `**` cho mọi độ sâu; tham khảo [tài liệu build context chính thức](https://docs.docker.com/build/concepts/context/). Chưa gọi Docker build/matcher thực tế tại đây, không dùng Python glob giả làm Docker để tuyên bố đã build.

Node Docker command byte-exact .95. Docker readiness helper, native harness, start.ps1 và toàn bộ thuật toán AI giữ nguyên .95; chỉ metadata version trong app main/backup đổi .96. Không xóa cache/source/data trên máy người dùng, không đổi cache Docker toàn hệ thống hoặc đặt env host lâu dài.

Cách đóng ZIP chuyển từ mốc 00:00 cố định sang UTC build timestamp (độ phân giải DOS 2 giây), có kiểm tra tránh trùng timestamp của các Python member đã thay đổi so với .95. Audit ZIP yêu cầu mtime mới cho từng Python member cũ có bytes đổi. Cache isolation vẫn cần thiết và không phụ thuộc timestamp archive.

## Kiểm thử .96 thực thi tại đây

| Nhóm | Đạt |
|---|---:|
| AI offline / worker helpers | 689 |
| Backend offline | 129 |
| Scripts stdlib unittest | 95 |
| Benchmark-gate standalone | 5 |
| Backup-worker standalone | 4 |
| Node built-in tests | 33 |
| Tổng | 955 |

63 HTTP/ORM test chưa thực thi vẫn đúng danh sách lịch sử (3 AI, 60 backend). 1 conditional native PowerShell runner mới từ .95 tiếp tục bỏ qua vì thiếu pwsh tại đây; bằng chứng 26 assertions Windows đã đạt nằm trong log người dùng .95 và được ghi riêng. Không cộng native assertions hoặc các phép tái lập bổ sung vào 955.

978 Python test identities/thân AST cũ và cả 6 Node test file cũ (33 tests) giữ nguyên byte/AST tương ứng. Thêm 8 Python regression, tổng 986 definitions. Toàn bộ 79 thân hàm Assert lịch sử giữ nguyên. Không nới test hoặc sửa expected version; test metadata tiếp tục so với VERSION hiện hành.

313 source file; 210 Python parse/compile; 31 PowerShell UTF-8/CRLF không BOM, text khác LF. 790 internal imports, 1090 literal PowerShell source predicates, 121 cặp UI/runtime; Babel 18 JS/JSX / 45 import-export symbols. 311 code/config hashes đóng băng, README/VERIFICATION được duyệt riêng trước archive audit. Source retains đủ 311 baseline paths, chỉ thêm test và migration.

38 release checks đạt: 17 Git/artifact cục bộ thực thi, 14 static, 4 simulation, 3 Bash syntax. Không push GitHub hoặc tạo Release thật.

## Giới hạn và sử dụng

Chưa thực thi .96 native PowerShell/Docker, full pytest HTTP/ORM, PostgreSQL/migration live, pinned npm install/audit/Vite build, browser hoặc GPU/full-video inference. Python 3.12.14 và Node 24.19.0 có sẵn; môi trường thiếu pytest/FastAPI/SQLAlchemy/Alembic/httpx/httpx2/cv2/Torch/pwsh/Docker. Các kết quả runtime khác ở phần lịch sử không được coi là phép chạy .96 mới.

Benchmark #68/session 195 (bản .94) vẫn là kết quả gần nhất: 149 GT / 149 AI / 142 khớp / 7 lọt / 7 dư, F1 95.302%. .96 không thay thuật toán nên không tạo hoặc suy ra F1 mới. Bản .95 khôi phục rider cần đánh giá bằng lần inference mới sau khi quy trình test chạy thông suốt.

Migration metadata `0110_pycache_v0596`, parent `0109_docker_guard_v0595`, chỉ đổi schema_version .96 / downgrade .95; không sửa GT/events. Giữ .env/.git/models/video/volumes khi chép source.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.96 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Không tạo lại Admin. Các mục sau là lịch sử giữ nguyên byte.

---

# V0.5.95 — HumanGuard recovery và Docker Linux preflight

Full source tiếp tục đúng ZIP V0.5.94, SHA256 `f3cb76c0dd1562273dec2fa1601d9299eaf26f9b8fd55300aaeac6236640dfe7`, 305 file. Đã thực thi **947 kiểm thử offline/Node, 0 lỗi**; PowerShell native và Docker không có trong môi trường này.

## Kết quả kiểm tra source

| Nhóm thực thi | Đạt |
|---|---:|
| AI offline / worker helpers thực tế | 689 |
| Backend offline | 129 |
| Scripts stdlib unittest | 87 |
| Benchmark-gate standalone | 5 |
| Backup-worker standalone | 4 |
| Node built-in tests | 33 |
| Tổng | 947 |

63 test HTTP/ORM chưa thực thi là đúng danh sách lịch sử (3 AI, 60 backend). Có **1 test mới bỏ qua riêng** vì thiếu `pwsh`: runner của harness PowerShell native. Không gộp trường hợp này vào danh sách loại trừ HTTP/ORM. 8 kiểm tra Python của Docker chỉ xác minh source contract; các kiểm tra subprocess/timeout/chính sách daemon thực tế bằng PowerShell chưa được chạy tại đây. Chúng được tích hợp chạy trên host Windows trước preflight và test đầu tiên cần Docker.

Giữ nguyên toàn bộ 964 Python test identities/thân AST cũ, cả 6 file Node test cũ (33 tests), 79 thân hàm Assert lịch sử. Thêm 5 AI test và 9 Python scripts test definitions, tổng 978 definitions; trong 9 mới có 8 static contract đạt và 1 native runner chưa chạy. Các test cũ không bị sửa hoặc bỏ để làm bản mới đạt.

311 source file, 208 Python parse/compile hợp lệ, 31 PowerShell UTF-8/CRLF không BOM, text khác LF. Đã đối chiếu 790 internal imports, 1087 literal PowerShell source predicates và 121 cặp trường UI/runtime. Babel parse 18 JS/JSX / 45 import-export symbols; frontend ngoài version không đổi. 309 code/config/fixture hashes đóng băng; README/VERIFICATION review riêng, sau đó kiểm CRC/đường dẫn/byte equality của ZIP.

38 kiểm tra release giữ kết quả đạt: 17 Git/artifact cục bộ thực thi, 14 static, 4 mô phỏng, 3 Bash syntax. Không push GitHub/tạo Release thật. Kiểm tra độc lập HumanGuard trên 35.280 tổ hợp box/ý kiến hợp lệ xác nhận thay đổi chỉ thuộc nhánh direct-positive geometry-neutral; các precondition và 10.080 trường hợp PERSON chiếm ưu thế hình học giữ kết quả cũ. Đây là kiểm tra bổ sung, không cộng vào 947.

## Input #68 / session 195 chạy V0.5.94

ZIP bảy member an toàn, CRC và toàn bộ manifest bytes/SHA hợp lệ; gzip được đọc đến EOF. Trace JSONL từ RAR giống tuyệt đối trace giải nén: 325.953.712 byte, SHA256 `1bbc7b8789aece8a57ca94ac02fb7c0a8c83b66380ae4449b12a28d72981fa87`. Có 23.650 frame liên tục; RAR gồm 165 ảnh và một trace session 195.

166 proposal = 28 direct + 95 interpolated + 43 rescued. 166 terminal receipt có source fields khớp toàn bộ, 149 created khớp tập DB events + 17 deduplicated; delivery drain complete, pending/dropped 0. Không có bằng chứng mất event khi gửi backend. 149 GT nội dung/thứ tự clone và config byte-exact so với session 194, giữ đủ các mark cùng semantic.

Matcher thực tế tái tạo mọi base/matched/missed/false-positive field của cả hai báo cáo:

| Chỉ số | #67 / 194 | #68 / 195 |
|---|---:|---:|
| GT / AI | 149 / 151 | 149 / 149 |
| Khớp / Lọt / Dư | 140 / 9 / 11 | 142 / 7 / 7 |
| Recall | 93,9597% | 95,3020% |
| Precision | 92,7152% | 95,3020% |
| F1 | 93,3333% | 95,3020% |
| Đúng class / đúng hướng | 137 / 138 | 139 / 140 |
| Đúng cả time/class/direction | 135 | 137 |

Hết lọt tại GT OUT 525.21028 s → AI 525.3925 s (194513) và GT IN 816.964611 s → AI 816.9225 s (345897). Không có GT lọt mới. Ba mark sai loại giữ nguyên. Hướng startup 0.16 s được sửa, có sai hướng mới tại GT OUT 754.558486 s → AI IN 754.045 s (296297); không tuyên bố không có regression.

FP 491.92 s của 181574 vốn đã tồn tại và khớp ở 194; 195 có proposal/event 182056 OUT 492.2 s gần GT hơn nên matcher đổi ownership, event cũ trở thành unmatched. Chưa chứng minh cùng phương tiện nên không thêm dedup tùy tiện. 345897 vẫn có OUT unmatched 811.925 s dù IN thật 816.9225 s đã được khôi phục. Tổng AI bằng GT không có nghĩa là hết lọt/dư.

Refiner checks 2195 → 1419 và HumanGuard rejections 37 → 38; config/model path không chứng minh cùng weights/model availability/toàn bộ runtime. Điểm 95,302% thuộc lần chạy .94 được gửi, **không phải điểm .95 và không suy ra mọi thay đổi do một fix**.

## Sửa HumanGuard có bằng chứng

Track 143399 bị rejected từ frame 9806. Frame 9822 có direct vehicle 0.700684 / PERSON 0.672363, IoU 0.357267 / coverage 0.463132; PERSON không đủ ưu thế hình học. Hàm .94 trả neutral sớm nên bỏ mất direct evidence, policy giữ rejected. Các candidate frame 9929 (source 397.020933 s) và 9938 (397.374 s) tiếp tục bị chặn; GT quanh 397.288 s vẫn lọt.

.95 đưa comparator **direct_competitive hiện có** lên trước nhánh geometry-neutral, chỉ nhánh này được trả rider_evidence khi direct >= max(0.20, person - confidence_margin - 0.03), cả person/direct trong [0,1]. Không đổi ngưỡng. NaN, ±Inf, âm hoặc >1 không khôi phục ở nhánh mới. Nhánh PERSON chiếm ưu thế hình học, thiếu PERSON, box không giống người, class ngoài hai bánh giữ cách xử lý cũ. Nearby vehicle hoặc motion đơn lẻ vẫn neutral trong nhánh mới; không dùng confidence primary/periodic khác nguồn thay cho crop verifier.

`HumanGuardTrackPolicy`, tracking, counting, toàn bộ rescuer, worker và backend dedup byte-exact .94. Chỉ app/main.py đổi version; human_guard.py là thay đổi AI thuật toán duy nhất. Guard audit schema/caching/stride và số lần inference giữ nguyên.

Fixture 32.425 byte SHA256 `4ed6eddc58b048361108a7331c4b7382773df8dc8486f130532b64dfef8ed5ec` chứa 26 quan sát fresh đã ghi. Kiểm tra predicate/policy/cache thực tế tái tạo đầy đủ mọi decision/action/status .94 trong fixture rồi so với .95: rejected 9806 → released 9822; vẫn có pending 9880 khi có ý kiến bất lợi, rider 9896 và tại candidate 9929/9938. Force cùng frame không gọi verifier lần hai và không tạo thêm strike. Các test bao gồm nearby/motion không đủ, người đi bộ mạnh vẫn cần các frame riêng biệt, precondition cũ và score lỗi.

Trace không có PERSON rectangle/width-ratio; fixture chủ động đưa IoU/coverage đã ghi vào phép kiểm tra, không giả vờ đã tái tạo crop hoặc inference model. Reproducer không chạy lại detector/tracker/guard models, dispatcher/deferred crossing/counter/backend transaction toàn pipeline. Phân tích guard diện rộng còn dữ liệu hình học không tái dựng được nên chỉ là thăm dò; không dùng số lượng track giả định giải phóng làm hiệu quả. **Chưa có F1 .95 hoặc bằng chứng 7 lượt lọt giảm còn bao nhiêu.**

## Docker engine và log Windows

Log .94 cho thấy static contracts đã chạy nhưng lệnh Docker đầu tiên báo pipe `dockerDesktopLinuxEngine` không tồn tại; start sau đó query volume thất bại rồi hiểu nhầm là cần tạo volume. Chưa có bằng chứng volume PostgreSQL hỏng hoặc cần xóa.

Shared `scripts/docker-engine.ps1` chỉ định nghĩa functions khi import. Probe gọi Docker executable qua ProcessStartInfo.ArgumentList, không qua shell, không phụ thuộc $LASTEXITCODE. Đọc stdout/stderr đồng thời; WaitForExit và chờ drain chia chung deadline, timeout dừng process probe và Dispose. Không in stderr/endpoint chứa dữ liệu nhạy cảm.

Engine Linux khỏe được chấp nhận ngay, bao gồm remote/custom context, không ngủ cố định và không lookup context thêm. Khi chưa khỏe, auto mở Desktop chỉ trên Windows + context desktop-linux + endpoint npipe dockerDesktopLinuxEngine đã xác minh. Mở một lần nếu chưa có tiến trình Desktop; nếu đã mở chỉ chờ. Tổng chờ engine cấu hình mặc định 120 giây, mỗi probe tối đa 5 giây theo phần thời gian còn lại. Docker CLI chưa có, Windows engine, remote/custom chưa sẵn sàng hoặc timeout sẽ dừng có hướng dẫn; không tự sửa context/service/WSL hoặc xóa volume.

start.ps1 gọi preflight trước .env/secret/certificate/volume; kiểm LASTEXITCODE của volume ls trước khi quyết định tạo volume. test.ps1 chạy harness host độc lập daemon trước preflight và trước Docker-dependent step đầu tiên. Python source contracts kiểm thứ tự/timeout/dữ liệu; native harness có subprocess thật, stdout+stderr lớn, nonzero exit, hung process và chính sách mocked endpoint/launch/deadline. Các mock nằm trong child script scope, env được khôi phục; **native harness chưa thực thi tại đây vì không có pwsh**.

Toàn bộ dòng lịch sử start/test được giữ nguyên theo thứ tự, chỉ chèn preflight, volume-error check, test invocation và contract .95. User chưa cung cấp log chạy .95, vì vậy không nói Docker Desktop đã được mở hoặc hệ thống Windows của bạn đã sửa xong từ xa.

## Môi trường và lệnh sử dụng

Python 3.12.14 / Node 24.19.0 hiện có; chưa có pytest/FastAPI/SQLAlchemy/Alembic/httpx/httpx2/cv2/Torch/PowerShell/Docker. Không chạy HTTP/ORM/PostgreSQL migration live, pinned npm install/audit/Vite build, browser/React DOM hay GPU/full-video .95. Dependencies pin và các feature/UI cũ giữ nguyên.

Migration `0109_docker_guard_v0595`, parent `0108_guard_audit_v0594`, chỉ đồng bộ schema_version .95/downgrade .94, không sửa GT/events. Không tạo lại Admin, không publish GitHub thật.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.95 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Giữ .env/.git/models/video/volumes khi cập nhật source; chạy lại cùng clip/vạch/model, chép GT đã review rồi xuất benchmark ZIP mới sau khi có GT. Các phần dưới là lịch sử kiểm chứng .94 và các bản trước được giữ nguyên byte.

---

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
