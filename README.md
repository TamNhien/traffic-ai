# Traffic AI V0.5.101 — Sửa HumanGuard deferred crossing / Raw-ID Guard

**Bản sửa lỗi kế thừa đầy đủ V0.5.100.** Khắc phục 6 bài kiểm thử AI thất bại trong `tests/test_guard_transaction.py`: test fixture dựng `PipelineWorker.__new__` mà không chạy `__init__`, vì vậy thuộc tính `_raw_handoff_guard_enabled` không tồn tại ở nhánh `_commit_guard_crossing`. Bản mới coi guard tùy chọn là tắt khi chưa khởi tạo, nhưng khi worker thực bật vẫn lưu passage đã xác nhận.

**An toàn giao dịch:** Raw-ID guard chỉ ghi lịch sử một crossing HumanGuard deferred sau khi `EventDispatcher.submit(...)` hoàn tất, tránh chặn nhầm lượt sau nếu dispatcher từ chối sự kiện. Thêm ba regression test: worker thiếu thuộc tính guard; guard bật và ghi đúng một passage sau admission; dispatcher lỗi không để lại ghi nhận giả. Không chỉnh GT, event lịch sử, thuật toán phân loại hoặc giá trị benchmark. Alembic `0115_guard_commit_v05101` chỉ cập nhật `schema_version`, không tạo/xóa bảng.

**Chạy Windows (giữ nguyên `.env`, data, models và PostgreSQL volumes):**

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
# Khi kiểm thử/chạy ổn và có gh: .\scripts\publish.ps1
```

**Kết quả chạy trên máy của bạn với V0.5.100:** backend 195 đạt, AI 729 đạt / 6 lỗi (log ngày 18-10). V0.5.101 được kiểm thử lại độc lập; xem `VERIFICATION.md` cho phạm vi và giới hạn môi trường. Không tuyên bố F1 thay đổi cho tới khi chạy một phiên video và xuất benchmark mới.

---

# Traffic AI V0.5.100 — Verified raw-ID handoff suppression

**Nâng cấp full source từ V0.5.99, lần này có thay đổi runtime worker**. Dữ liệu benchmark #72 / session #199 có 149 GT / 150 AI / 143 khớp / 6 lọt / 7 dư và giống hệt #71 / session #198 theo chữ ký crossing. Đây là số của phiên đã chạy, **không phải** kết quả inference mới với V0.5.100.

## Sửa lỗi đếm trùng khi raw tracker ID chuyển qua hai canonical

Trong trace cả hai phiên, frame 12304 có raw ID `182056` nằm dưới canonical `181574`; frame 12305 raw ID này chuyển sang canonical `182056` với box IoU 0.7003; hai canonical nhận OUT tại 491.920 và 492.200 giây, với điểm cắt cách nhau Δx=0.009272, Δy=0.002097. Dấu hiệu này đủ để tạo guard *rất hẹp* thay vì chặn các xe chỉ vì cùng timecode.

`app.raw_handoff_guard.RawHandoffCrossingGuard` quan sát trực tuyến raw/canonical ID, đòi hỏi tất cả điều kiện: **cùng raw ID được quan sát dưới hai canonical khác nhau** (đổi trong tối đa 3 frame), IoU box khi handoff ≥0.64, canonical cũ có passage thực sự được commit trong 12 frame, cùng hướng IN hoặc OUT, event mới là `direct`, thời gian sau handoff ≤10 frame, điểm cắt x lệch ≤0.025 và y lệch ≤0.018. Không dùng GT, tên video, session ID, danh sách track ID cố định hay matcher để sửa đầu ra; không chặn xe khác raw ID dù rất gần nhau. Chính sách áp dụng cho `video` với 2 bánh, giữ nguyên RTSP/stream và 4 bánh. Nếu cần A/B, đặt `AI_VERIFIED_RAW_HANDOFF_GUARD=0` trong `.env` rồi chạy lại. Mặc định `1` trên local video.

Bộ bảo vệ chỉ chặn ghi thêm event worker/DB khi có bằng chứng; canonical bị chặn vẫn giữ trạng thái gate đã xác nhận để không bắn lại cùng passage ngay sau đó. Trace lưu `producer_decision=verified_raw_handoff_duplicate_suppressed`, kèm raw/owner ID, IoU, Δframe, Δxy; Dashboard / Thông số kỹ thuật hiển thị **Raw-ID trùng được chặn**. Không thay đổi GT, benchmark matcher, rule class, Human Guard, dedup backend hay mật khẩu Admin.

**Replay shadow** `scripts/audit-raw-handoff.py` (`.ps1` trên Windows) xác minh manifest/CRC/SHA trace, quét đủ 23.650 frame và xuất JSON/Markdown; cả #71 và #72 cho **1 ứng viên** cùng vị trí 492.200s trong 167 đề xuất. Đây là mô phỏng offline từ dữ liệu track cũ, không phải xác nhận F1 mới. Chưa có mô phỏng lại full-video YOLO/tracker sau bản sửa, và có rủi ro hiếm khi raw ID bị ByteTrack tái sử dụng cho hai xe chồng lấp; có thể tắt guard để so đối chứng.

## Cập nhật, kiểm tra, chạy và xuất bản

Giữ nguyên `.env`, `.git`, models, MP4, ảnh camera, storage và PostgreSQL volumes; không khởi tạo lại Admin. Metadata schema `0114_raw_handoff_v05100` nối `0113_passage_evidence_v0599`, không chỉnh bảng hoặc record cũ.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1

# Phân tích lại export đã lưu; không chạy GPU và không tự sửa điểm:
.\scripts\audit-raw-handoff.ps1 -Export ".\traffic-ai-benchmark-72-session-199.zip" -OutputDirectory ".\raw-handoff-audit"

# Chỉ khi test/chạy ổn thì phát hành tự động:
.\scripts\publish.ps1
```

Chạy lại AI **một lần** với cùng `clip1.mp4` và cùng hình học vạch, tạo benchmark mới rồi sao chép GT từ #72 để so sánh. **Không khẳng định** trước rằng sẽ giảm từ 7 xuống 6 dư hoặc tăng F1: đây mới là counterfactual dựa trên trace cũ. Hai GT không có đề xuất crossing gần 392.179s và 591.091s vẫn phải rà detector/track riêng, không tự sinh lượt ảo.

---

# Traffic AI V0.5.99 - Verified Passage Evidence Review

**Nâng cấp từ V0.5.98; không tự chỉnh thuật toán counting/detector.** Phân tích benchmark mới #71 / session #198 bằng full export ZIP và 166 JPG trong RAR (giải nén riêng). 149 GT / 150 AI / 143 khớp / 6 lọt / 7 dư: dữ liệu từ lượt chạy V0.5.98, **không phải** kết quả inference sau khi nâng cấp. 4 trong 6 mốc GT chưa khớp có event AI đã được matcher ghép sang GT khác, không đủ bằng chứng nói detector bỏ sót; 2 GT còn lại không có event đã lưu tương ứng trong tolerance. 1 AI extra ở khoảng 491.920 giây có chỉ dấu hàng xóm hình học, nhưng chưa xác lập cùng xe. Van/xe tải tại 882.290 giây có snapshot ngay vùng vạch; không loại tự động.

**Giao diện:** trong báo cáo Benchmark thêm ghi chú V0.5.99 phân biệt số GT cạnh tranh ghép timecode với số GT chưa có event DB trong cửa sổ ghép, có kiểm tra phạm vi/chỉ số để không hiện dữ liệu thiếu nhất quán. 4 bài kiểm tra Node mới bảo vệ logic này.

**Tính năng mới:** `scripts/audit-error-evidence.py` / `audit-error-evidence.ps1`: xác minh CRC, manifest SHA256, SHA256 trace giải nén và delivery footer qua benchmark-forensics hiện có; tạo **13 hồ sơ rà soát** theo timecode với tình trạng matcher, event GT đã chiếm AI, khung hình/track hai phía, crossing proposal / delivery receipt gần thời điểm, cùng ảnh JPG gần nhất (nếu đã giải nén). Ảnh chỉ được liên kết khi cách source time tối đa **1 giây** và dùng FPS phiên từ snapshot đã xác minh. Kết quả xuất `passage-evidence.json`, `.csv`, `.md`; không ghi DB, không sửa GT, không tự gộp hoặc xóa event/track. Gần nhau về thời gian, xuất hiện ở hai phía vạch và JPG tĩnh đều **không chứng minh** cùng xe.

Ví dụ sau khi sao chép bản full source, export benchmark đã tải và (nếu cần) giải nén RAR vào thư mục ảnh:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1

# Đọc hồ sơ benchmark đã export, không cần chạy lại AI/benchmark.
.\scripts\audit-error-evidence.ps1 -Export ".\traffic-ai-benchmark-71-session-198.zip" -OutputDirectory ".\passage-evidence-audit"

# Có thể truyền ảnh JPG đã giải nén từ RAR để ghép hình theo frame/timecode.
.\scripts\audit-error-evidence.ps1 -Export ".\traffic-ai-benchmark-71-session-198.zip" -CameraImages ".\camera_1" -OutputDirectory ".\passage-evidence-audit"

# Chỉ publish khi đã test/kiểm tra trên máy thật thành công.
.\scripts\publish.ps1
```

Bản .99 có migration metadata `0113_passage_evidence_v0599`, parent `0112_clock_owner_v0598`; không thay đổi cấu trúc dữ liệu hay mật khẩu Admin. Hãy so benchmark của **phiên chạy mới** với GT có cùng video/vạch trước khi tuyên bố chỉ số AI thay đổi. Mục tiêu của công cụ mới là phân loại bằng chứng để nhắm đúng lỗi, không tuyên bố đã giảm từ 6/7.

---

# Traffic AI V0.5.98 — Giữ đúng lượt sở hữu mốc thời gian crossing

Sửa lỗi mốc thời gian của một đoạn quỹ đạo cũ còn đi theo alias sau khi gộp track vào một track đã nhận lượt cắt vạch mới hơn. Lỗi này có thể kéo timestamp của event về lượt trước và gây sai ghép benchmark. Bộ đếm không được tự tạo thêm event từ timestamp hint.

Ví dụ tái hiện bằng API thật: track 1 có hint IN tại frame 11.5 từ đoạn quỹ đạo kết thúc frame 13; track 2 đã nhận OUT ở frame 18. Bản cũ gộp 1→2 rồi vẫn trả hint 11.5 khi hỏi IN ở frame 22. Bản .98 loại hint đã hết vòng đời này.

Kiểm tra dựa vào frame **kết thúc đoạn quỹ đạo**, theo cùng điều kiện đang dùng cho pending span; không so thẳng timestamp nội suy với frame xác nhận. Vì vậy đoạn kết thúc frame 13 vẫn hợp lệ sau xác nhận frame 12, dù điểm cắt nội suy là frame 11.5. Hint hợp lệ và lượt xe quay lại vẫn có kiểm thử bảo vệ.

## Kiểm thử và dữ liệu mới

**1.002 kiểm thử offline/Node đạt, 0 lỗi**. Có 16 regression mới dùng hình học và các API rescuer thật: bản .97 đạt 12/sai 4; bản .98 đạt 16/16. Giữ nguyên toàn bộ test cũ và 79 contract Assert. Chỉ sửa ba hàm quản lý clock hint trong counting.py; các ngưỡng geometry, tracking, Human Guard, class policy, dedup và matcher được giữ nguyên.

Đã kiểm đầy đủ export #70/session 197 và đối chiếu #69/196: cùng 149 GT, config và đủ 150 event trên các trường source; cả hai đều **143 khớp / 6 lọt / 7 dư, F1 95.6522%**. Có thay đổi ở scheduling/class-refiner audit, nên không coi toàn bộ trace giống nhau. Lỗi hint vừa sửa được tái lập độc lập, chưa được chứng minh là nguyên nhân sáu lượt lọt hoặc bảy lượt dư trong clip này.

Chưa chạy Docker/PowerShell native hoặc inference đầy đủ .98 tại môi trường đóng gói. Chi tiết kiểm chứng và giới hạn nằm trong VERIFICATION.md.

## Cập nhật và đo bản .98

Giải nén chép đè source, giữ .env, .git, models, video, snapshots, volumes và dữ liệu hiện có. Migration metadata mới `0112_clock_owner_v0598`, parent `0111_count_review_v0597`. Không tạo lại Admin.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.98 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443 rồi Ctrl+F5. Để đo thay đổi timestamp .98, chạy AI **một lần**, tạo benchmark cho phiên mới rồi sao chép GT từ #70 nếu vẫn cùng clip/vạch. Đối chiếu lại #70 chỉ chấm dữ liệu đã lưu của phiên 197; thao tác đó không chạy lại AI. Các phần dưới là lịch sử giữ nguyên.

---

# Traffic AI V0.5.97 — Rà soát track chồng lấp và đổi ID

Bản này bổ sung bằng chứng quỹ đạo cho các ca AI đếm dư, sai hướng và sai loại. Sau khi cập nhật source và khởi động, chọn Benchmark #69, bấm **Đối chiếu lại**, rồi mở **Track chồng lấp và đổi ID** trong ca cần xem. Các nút Đầu/Cuối hoặc Trước/Sau đưa video tới đúng các quan sát đã lưu trong trace phiên 196; không cần tạo thêm benchmark để đọc lại bằng chứng này.

## Chức năng mới

- Hiện các track đồng thời có box lồng nhau, số frame cùng xuất hiện, mức phủ box nhỏ và mốc thời gian quan sát. Track của event gần nhất đã khớp GT được nhận diện từ event đã lưu, thay vì đoán từ ID gần nhau.
- Phân biệt dịch chuyển tâm box quan sát được với vận tốc đã lọc. Hai loại số đo có thể khác nhau đáng kể khi box rung hoặc ID ghép sai.
- Hiện lần đổi raw ID trong cùng canonical track, khoảng cách frame và dịch chuyển tâm box; có nút xem video trước/sau.
- Các ca dư và sai hướng có thêm dấu vết worker đề xuất crossing và phản hồi backend. Bằng chứng luôn gắn với track của event AI đang xem.

Các số đo chồng box và raw ID phục vụ rà soát, không tự kết luận hai track là cùng phương tiện. Bộ đếm, matcher và GT giữ nguyên; đặc biệt hai xe đi sát nhau có thể tạo hình học tương tự một xe bị tách box. Trace thiếu hình học không được bù bằng quan sát giả.

## Đối chiếu dữ liệu bạn gửi

Đã kiểm CRC, manifest SHA/size và gzip của cả hai bản export; 149 GT tương đương và config giống từng byte. Toàn bộ 149 event cũ không đổi, chỉ thêm xe máy IN track 143399 tại 397.0209 s, khớp GT 397.288 s.

| Chỉ số | #68 / 195 | #69 / 196 |
|---|---:|---:|
| GT | 149 | 149 |
| AI đã lưu | 149 | 150 |
| Khớp / lọt / dư | 142 / 7 / 7 | 143 / 6 / 7 |
| F1 đếm | 95.3020% | 95.6522% |
| Khớp cả thời gian, loại và hướng | 137 | 138 |

Ảnh giao diện phiên 196 bạn gửi hiển thị V0.5.96; số liệu #69 là kết quả export của phiên đó, không phải điểm inference mới của .97. Trace không ghi build hash/version nên không độc lập xác minh được chính xác bytes runtime. Cặp 181574/182056 quanh 492 s có ảnh một xe máy với hai box lồng nhau. Track 296297 quanh 754 s có lần đổi raw ID qua gap 18 frame cần xem lại. Các trường hợp này được đưa vào kiểm thử và bằng chứng rà soát; không xóa event theo timecode để làm giảm số dư.

Ảnh van chở hàng tại 641.98 s phù hợp quy ước xe tải của dự án dù GT ghi ô tô; van quay lại tại 882.29 s cũng có ảnh cắt vạch IN thật. Hãy đối chiếu GT bằng video trước khi sửa nhãn. Không tự đổi hai trường hợp này. 6 lượt lọt và 7 lượt dư trong export vẫn là số liệu được giữ để kiểm tra.

## Cập nhật và chạy

Giải nén chép đè source vào thư mục dự án, giữ .env, .git, models, video, snapshots và các volume/dữ liệu hiện có. Không tạo lại tài khoản Admin. Migration metadata mới: `0111_count_review_v0597`, parent `0110_pycache_v0596`.

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

Mở https://traffic-ai.test:8443 rồi Ctrl+F5. Chi tiết kiểm thử và giới hạn xem VERIFICATION.md. Các mục dưới đây là lịch sử giữ nguyên.

---

# Traffic AI V0.5.96 — Sửa cache Python khi chạy test Docker

Bản này xử lý lỗi trong log .95: kiểm tra source báo đúng version mới, nhưng ba test backend vẫn nhận `0.5.94` thay vì `0.5.95`.

## Nguyên nhân đã tái hiện

Hai ZIP .94/.95 trước đó đóng các file với cùng thời gian 00:00 ngày 17/10. Riêng `backend/app/main.py` đổi version nhưng vẫn cùng kích thước 1181 byte. Python có thể xem bytecode `.pyc` cũ là hợp lệ vì timestamp và kích thước đều khớp, dù nội dung source đã đổi. `compileall` mặc định cũng có thể bỏ qua cache này.

Đã tái hiện bằng chính bytes `main.py` của hai ZIP và loader CPython thật: source .95 nhưng code cache còn .94; dùng cache prefix mới đọc đúng .95. Chỉ thêm `-B` hoặc `PYTHONDONTWRITEBYTECODE=1` không đủ để ngăn đọc cache cũ.

## Sửa trong .96

- Cả **20 lệnh Docker Python** của `test.ps1` dùng `PYTHONPYCACHEPREFIX=/tmp/traffic-ai-test-pycache` và `PYTHONDONTWRITEBYTECODE=1`. Prefix nằm trong filesystem riêng của container `--rm`, không nằm trong source bind mount. Mỗi container có cache riêng; `compileall` cũng ghi cache vào prefix này.
- Bổ sung pattern cache đệ quy trong `.dockerignore` của backend/AI để không đưa `.pyc` lồng trong thư mục vào image. Pattern `**` theo [Docker Docs](https://docs.docker.com/build/concepts/context/).
- ZIP .96 dùng timestamp build UTC mới; audit kiểm tra các Python file đã thay đổi có timestamp khác ZIP .95.
- Thêm 8 regression dùng tiến trình Python thật cho trường hợp cùng mtime/kích thước, no-write flag, cache prefix mới/cũ và compileall. Giữ nguyên các test phiên bản hiện có.

**955 kiểm thử offline/Node đạt.** Source gồm đủ các chức năng .95: khôi phục rider có bằng chứng trực tiếp, Docker readiness, điểm neo ổn định, báo cáo Excel/CSV/PDF, phân quyền, backup và benchmark. Bản này không thay thuật toán AI hoặc điểm benchmark.

Log Windows bạn gửi đã xác nhận harness Docker readiness **26 assertions đạt**; backend có 186 đạt/3 lỗi version trong hai lần chạy .95. Đây không phải log chạy .96. Kiểm chứng .96 ở môi trường hiện tại chưa có Docker/PowerShell/HTTP ORM đầy đủ; chi tiết xem VERIFICATION.md.

## Test, chạy và tự động phát hành

Chép full source vào dự án hiện có, giữ `.env`, `.git`, models, video và volumes. Các lệnh dưới không yêu cầu xóa cache trên máy hoặc tạo lại Admin.

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

Mở https://traffic-ai.test:8443 rồi Ctrl+F5. Migration `0110_pycache_v0596`, parent `0109_docker_guard_v0595`, chỉ đồng bộ schema_version .96. Các mục bên dưới là lịch sử giữ nguyên.

---

# Traffic AI V0.5.95 — Khôi phục rider có bằng chứng và kiểm tra Docker

Tiếp tục từ full source V0.5.94. Giữ điểm neo ổn định, báo cáo Excel/CSV/PDF, dashboard, phân quyền, backup, benchmark và toàn bộ chức năng cũ.

## Sửa HumanGuard giữ trạng thái chặn khi đã có bằng chứng xe

Trace session 195 xác định track 143399 bị chặn từ frame 9806. Tại frame 9822, model kiểm tra cùng crop đã cho xe trực tiếp 0.700684, PERSON 0.672363; nhưng box PERSON không đủ chiếm ưu thế hình học nên hàm trả neutral trước khi xét bằng chứng xe. Neutral giữ nguyên trạng thái rejected, làm các candidate quanh 397 s tiếp tục bị loại.

Bản .95 xét **bằng chứng xe trực tiếp cạnh tranh** trong đúng nhánh hình học PERSON chưa đủ chiếm ưu thế, dùng nguyên comparator có sẵn `direct >= max(0.20, person - confidence_margin - 0.03)`. Confidence phải là giá trị hợp lệ trong `[0,1]`. Bằng chứng đủ mạnh trả `rider_supported`, để chính sách hiện có khôi phục rider; không hạ ngưỡng, tăng inference hay sửa số lần xác nhận.

Xe lân cận hoặc chuyển động riêng lẻ không được dùng để khôi phục ở nhánh này. Các điều kiện thiếu PERSON, box không giống người, class khác và nhánh hình học PERSON đã chiếm ưu thế giữ cách xử lý cũ. Cùng frame vẫn dùng một quyết định cache; toàn bộ `HumanGuardTrackPolicy`, tracking, counter, rescuer và backend dedup giữ nguyên.

Tái lập có kiểm soát 26 quan sát thật bằng các ý kiến/IoU/coverage đã ghi, với predicate/policy/cache thật: .94 giữ rejected; .95 khôi phục tại frame 9822 và rider tại candidate frame 9929/9938. Trace không có PERSON rectangle nên phép kiểm tra dùng các chỉ số hình học đã ghi, **không phải inference lại ảnh hoặc benchmark toàn clip**. Fixture số liệu cùng các kiểm tra người đứng cạnh xe/score không hợp lệ được đóng gói trong source.

## Sửa lỗi Docker chưa chạy trong log Windows

Log bạn gửi báo thiếu pipe `dockerDesktopLinuxEngine`. Lỗi gốc là Docker Linux engine chưa kết nối được; thông báo không tạo được PostgreSQL volume chỉ là lỗi theo sau.

- `start.ps1` kiểm tra engine trước khi sửa `.env`, tạo secret/chứng chỉ hoặc query volume. Query volume thất bại dừng rõ ràng, không coi đó là volume chưa tồn tại.
- `test.ps1` kiểm tra engine trước test đầu tiên cần Docker. Engine Linux sẵn sàng trả ngay, không có thời gian ngủ cố định.
- Khi xác minh đúng Windows/context `desktop-linux`/pipe cục bộ, script có thể mở Docker Desktop một lần và chờ engine trong thời hạn 120 giây. Mỗi lệnh probe có deadline riêng và đọc stdout/stderr đồng thời. Desktop đã mở chỉ được chờ, không mở lại.
- Docker CLI chưa cài, Windows containers, endpoint/context khác chưa sẵn sàng hoặc hết thời gian sẽ có thông báo xử lý rõ. Không tự đổi Docker context, restart service/WSL, xóa volume hay thay dữ liệu.
- Bộ kiểm tra PowerShell độc lập daemon được chạy trên host trước preflight trong `test.ps1`; môi trường kiểm chứng hiện tại chưa có PowerShell nên phần native này chưa chạy tại đây. Kết quả chi tiết xem VERIFICATION.md.

## Kết quả input mới

Benchmark #68/session 195 chạy bản .94: **149 GT / 149 AI / 142 khớp / 7 lọt / 7 dư / F1 95,302%**. So với session 194, hết lọt tại 525.21028 s và 816.964611 s, không thêm GT lọt mới. Tổng AI bằng GT vẫn còn 7 lọt và 7 dư, không phải đếm đúng hoàn toàn.

Ba sai loại vẫn giữ nguyên. Hướng startup 0.16 s được sửa nhưng có một assignment sai hướng mới quanh 754.558486 s. Số lần refiner/model phụ cũng khác nên không gán toàn bộ cải thiện cho riêng thay đổi điểm neo. Không tự sửa GT, quy ước van chở hàng là Xe tải hay matcher.

**Chưa có điểm full pipeline của .95.** Cần chạy lại cùng clip/vạch/model với GT đã review để đo hiệu quả sửa rider.

## Test, chạy và tự động phát hành

Chép full source vào dự án hiện có, giữ `.env`, `.git`, models, video và volumes. Không tạo lại Admin.

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

Mở https://traffic-ai.test:8443, Ctrl+F5. Nếu Docker Desktop không ở thư mục/context thông thường, mở ứng dụng thủ công và chờ Engine running trước khi chạy lệnh. Sau replay .95, sao chép GT sang benchmark mới rồi Tải hồ sơ benchmark sau khi có GT.

Migration metadata `0109_docker_guard_v0595`, parent `0108_guard_audit_v0594`; không thay GT/events. Các mục bên dưới là lịch sử được giữ nguyên.

---

# Traffic AI V0.5.94 — Ổn định điểm neo và chẩn đoán Human Guard

Tiếp tục từ đúng full source V0.5.93. Giữ báo cáo giờ/ngày/tháng, Excel/CSV/PDF, phân quyền, backup, dashboard, huấn luyện, benchmark, công cụ audit và quy trình GitHub Release hiện có. Không cần tạo lại tài khoản Admin.

## Sửa dao động hướng ở xe hai bánh

Trace session 194 cho thấy track 345897 có box lớn nhưng tâm chỉ dao động vài pixel; heading đổi mạnh làm điểm neo đi qua vạch và tạo các lượt sớm. Hai event thực được lưu là IN 811.64 s và OUT 815.2484 s; GT IN 816.964961 s còn lọt.

Bản này giới hạn góc đổi hướng của **điểm neo hai bánh** theo quãng đường tâm thực sự di chuyển và bán kính box (nửa đường chéo lớn hơn của box trước/hiện tại, sàn 1.5 px). Khi bước di chuyển nhỏ hơn bán kính, góc đổi tối đa là `travel / radius` radian; độ cong nhỏ có đủ chuyển động hỗ trợ vẫn cập nhật ngay. Bước di chuyển từ một bán kính trở lên cập nhật ngay theo vận tốc mới, như nhánh xử lý trước. Không thay vận tốc đo/dự đoán dùng để nối identity.

Xe bốn bánh, thiếu rect, chưa có heading, khoảng mất dấu dài và chế độ rollback giữ cách xử lý heading của .93. Điểm neo giữ độ lớn ở ngưỡng full-heading, tránh vector bằng 0 khi quay ngược 180°. Không nới Gate, cửa sổ matching, backend dedup, Human Guard hay đổi quy ước van chở hàng là Xe tải. Có thể đối chiếu với .93 bằng `AI_TWO_WHEEL_HEADING_INERTIA=0` trong `.env`; mặc định bật. Guard nối nhầm ID gap 1–12 của .93 vẫn được giữ.

Tái lập có kiểm soát trên 677 hàng của track 345897 bằng heading/counter/rescuer thật còn OUT 811.925 s và IN 816.922 s, loại chu kỳ dao động quanh 815 s. OUT sớm vẫn chưa có GT tương ứng nên không tuyên bố đã hết dư. Kiểm tra mở rộng trên 271.208 observations giữ toàn bộ 142 GT từng khớp thời gian; đây là kiểm tra hình học, không phải số event DB của ứng dụng. Một thay đổi ghép hướng do hai proposal cạnh tranh quanh 606 s được ghi rõ trong VERIFICATION.md.

## Xem bằng chứng Human Guard trên web

Ở **Benchmark Report**, mở **Bằng chứng Human Guard** dưới lượt lọt hoặc sai loại xe. Phiên mới ghi PERSON, xe trực tiếp/xe lân cận, IoU/độ phủ khi đã tính, frame kiểm tra gốc, tuổi cache, số lần xác nhận từ các frame riêng biệt và trạng thái track.

- Phân biệt quan sát mới, cùng frame, chờ chu kỳ kiểm tra, frame cũ, model chưa sẵn sàng và không có kết quả. Thiếu bằng chứng hiển thị `—`, không biến thành confidence 0.
- Nếu GT chưa có identity AI đã ghép, UI ghi rõ đây là **các track gần timecode**, cần xem video để xác định xe GT. Không gán một track lân cận thành xe bị lọt.
- Chỉ giữ tối đa 8 bản ghi chẩn đoán; danh sách ghi trong mỗi frame có giới hạn. Không ghi ảnh crop, đường dẫn nội bộ hoặc response model vào audit. Trace có thể lớn hơn do thêm bằng chứng; chưa đo dung lượng gzip của một lần inference mới.
- Hàm quyết định và chính sách Human Guard giữ nguyên. Dùng lại cache không tạo thêm strike; lỗi ghi audit không chặn quá trình đếm. Trace cũ chưa có trường này không được dựng thêm bằng chứng.

## Kết quả input đã xác minh

Benchmark #67/session 194: **149 GT / 151 AI / 140 khớp / 9 lọt / 11 dư / F1 93,33%**. So với #66/session 193: khớp thêm mốc 534.086505 s và 640.140782 s, hết dư 638.12 s; không có signature lọt/dư mới. Cùng 149 GT theo thứ tự và cấu hình byte giống nhau; chưa chứng minh weights và toàn bộ môi trường inference giống nhau nên không gán mọi cải thiện cho một thay đổi source.

Đính chính mô tả ảnh trong ghi chú .93 bên dưới: track 255061 ở frame 15954/15968 của phiên mới là **box phần thân trên của người đang đi xe máy**, không phải người đi bộ. .93 tách identity này khỏi 251681: OUT 638.6037 s và IN 639.7107 s đều khớp GT. Lỗi đã chứng minh là ghép nhầm hai phương tiện.

**Chưa có điểm benchmark toàn clip của V0.5.94.** Các kiểm tra tái lập dùng observations đã ghi và thuật toán thật, không thay thế một lần chạy detector/tracker/models/Guard/dispatcher/backend toàn pipeline. Kết quả và giới hạn cụ thể xem VERIFICATION.md. Human Guard ở 397 s vẫn cần crop-model opinions của lần chạy mới trước khi quyết định thay ngưỡng. Source không tự sửa GT, class hay timecode.

## Test, chạy và tự động phát hành

Chép đầy đủ source vào `D:\LienThongDH\DoAn\traffic-ai`, giữ `.env`, `.git`, models, video và volumes hiện có.

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

Mở https://traffic-ai.test:8443 rồi Ctrl+F5. Chạy lại cùng clip/vạch/model, sao chép GT đã review sang benchmark mới rồi **Tải hồ sơ benchmark** sau khi có GT. Bằng chứng Human Guard mới xuất hiện từ trace của lần chạy .94. Báo cáo thống kê vẫn có thể đọc phiên 194 đang lưu; chọn đúng phiên để không cộng nhiều lần chạy lại video.

Migration `0108_guard_audit_v0594`, parent `0107_reports_guard_v0593`, chỉ đồng bộ schema_version 0.5.94; không chỉnh dữ liệu GT/events. `publish.ps1` đọc VERSION và giữ quy trình kiểm thử → commit/push → tag → Release, không ghi đè tag cũ. Các mục bên dưới là lịch sử của những bản trước.

---

# Traffic AI V0.5.93 — Báo cáo thống kê và sửa nối ID cự ly ngắn

Bản này tiếp tục từ đúng full source V0.5.92 được cung cấp. Giữ toàn bộ chức năng đăng nhập/phân quyền, backup, huấn luyện, dashboard 50/50, benchmark và công cụ audit cũ.

## Báo cáo thống kê nâng cao

Mở **Báo cáo** trên thanh điều hướng. Chọn camera, một phiên đếm, khoảng ngày và loại xe; nhóm theo **giờ / ngày / tháng** rồi bấm **Xem báo cáo**. Có tổng lượt, IN/OUT/chưa rõ hướng, biểu đồ lưu lượng, bảng theo camera/loại xe và các giờ cao điểm. Phiên mặc định là phiên gần nhất của camera; ngày được điền từ thời điểm bắt đầu/kết thúc phiên.

Báo cáo tính trên **event đã lưu trong PostgreSQL**, không phải số đề xuất worker. Đồng hồ dùng thời điểm hệ thống ghi nhận event theo **UTC+7**, không suy diễn ngày quay video từ hình overlay. Chạy lại cùng video tạo phiên mới; chọn một phiên để tránh cộng nhiều lần replay. Giờ cao điểm là từng khoảng một giờ có lưu lượng cao nhất trong khoảng ngày, không phải trung bình giờ trong ngày.

- Xuất **Excel .xlsx thật**, CSV UTF-8 BOM và PDF tiếng Việt có font nhúng, phân trang. Export có cùng bộ lọc với báo cáo đang xem; đổi bộ lọc phải xem lại trước khi tải.
- Viewer được đọc; Admin/Operator được tải. API mới vẫn qua authentication/RBAC hiện có.
- Giao diện chọn ngày cuối bao gồm cả ngày; API chuyển thành khoảng `[start, end)` theo UTC+7. Tối đa 366 ngày, báo cáo theo giờ tối đa 31 ngày. Query SQL tổng hợp có giới hạn 100.000 nhóm và báo lỗi khi vượt, không trả tổng thiếu.
- API: `GET /api/reports/traffic`, `GET /api/reports/traffic/export?format=xlsx|csv|pdf`, `GET /api/reports/sessions`.

## Sửa một nguyên nhân đếm dư và che mất lượt thật

Trace session 193 cho thấy raw 255061 được ghép vào canonical 251681 chỉ một frame 15954. Ảnh tại cửa sổ này cho thấy box người đi bộ nhận lịch sử track xe; event IN 638.12 s được lưu trước, còn proposal của track 251681 tại 639.7107 s bị backend gộp. GT 9635 nằm 640.1409 s. Không nới cửa sổ dedup để giữ thêm cả event sớm lẫn event sau.

V0.5.93 mở điều kiện kiểm tra mâu thuẫn nối ID hai bánh có sẵn từ gap 4–12 xuống gap 1–12 frame. Chỉ chặn khi đủ hai bounding box và đồng thời khoảng cách trực tiếp lẫn vị trí dự đoán đều vượt ngưỡng footprint hiện có. Xe nhanh khớp dự đoán, bốn bánh, gap > 12, raw ID đã có mapping và chế độ tắt guard giữ đường xử lý cũ. Gate, heading, Human Guard, backend dedup, class/taxonomy và matching/tolerance không đổi.

Reproducer dùng resolver và primary counter thật trên 158 dòng đo mục tiêu: .92 ghép raw 255061 vào 251681 và tạo crossing sớm; .93 giữ identity riêng và track 251681 tạo IN tại 639.7106917 s. Đây là tái lập có kiểm soát trên đoạn đo, chưa phải detector/tracker/HumanGuard/dispatcher replay toàn clip.

**Chưa có F1 mới của .93.** Benchmark #66/session 193 hiện tại vẫn 149 GT / 150 AI / 138 khớp / 11 lọt / 12 dư / F1 92,3%. Session 192 và 193 có cùng crossing signatures và kết quả dedup; bản .92 chủ yếu thêm audit nên không giải quyết hết các lỗi này. Case anchor dao động quanh 815–817 s và Human Guard ở 397 s vẫn cần thêm bằng chứng; không tự thay ngưỡng để ép điểm.

GT đang có 0 Xe tải, 1 Ô tô; van OUT 641.981 s vẫn được gán GT Ô tô trong khi AI là Xe tải. Van IN 882.2898 s chưa có GT gần trong cửa sổ ±0,75 s. Giữ quy ước van chở hàng là Xe tải và review nhãn/thời điểm trên clip; source không tự sửa GT.

## Kiểm thử, chạy và phát hành

Chép source vào dự án hiện tại, giữ `.env`, `.git`, volumes, models và video của bạn. Không cần tạo lại tài khoản Admin.

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

Mở https://traffic-ai.test:8443, Ctrl+F5. Chạy lại cùng clip/vạch/model để đo kết quả bản mới; benchmark mới sao chép GT đã review rồi **Tải hồ sơ benchmark** sau khi có GT. Báo cáo thống kê có thể dùng phiên 193 hiện có để kiểm tra 150 lượt theo thời điểm ghi nhận thực tế. Trong dữ liệu được gửi, các event thuộc 15/10 theo UTC+7 dù file được gửi 16/10; chọn phiên sẽ điền ngày tương ứng.

Migration `0107_reports_guard_v0593`, parent `0106_cycle_witness_v0592`, chỉ đồng bộ schema_version 0.5.93; không sửa dữ liệu GT/events. ReportLab 5.0.1 được thêm vào dependencies cho PDF; font DejaVuSans và giấy phép được đóng gói. Kết quả kiểm tra cụ thể/giới hạn môi trường xem VERIFICATION.md.

---

# Traffic AI V0.5.92 — Verified Crossing-Cycle and Raw-ID Evidence Audit

- **Phân tích chu kỳ cắt vạch trên cùng canonical tracking ID** với cửa sổ tối đa 30 giây (mặc định 12 giây). Đối chiếu cả `matched_items` và `false_positive_items`, kèm bằng chứng raw ByteTrack ID từ trace JSONL đã xác thực manifest/hash.
- **Web Benchmark Report:** phần mở rộng "Các lượt dùng chung tracking ID" cho phép bấm vào cả hai timecode; phân biệt cặp có AI dư. Không tự xem các lượt IN→OUT là đếm trùng, vì một xe quay lại là một lượt hợp lệ.
- **Lệnh CLI/PowerShell `scripts/audit-crossing-cycles.ps1`** xuất `crossing-cycles.json`, `crossing-cycles.csv` (UTF-8 BOM) và Markdown để xem từng cặp; kiểm tra trace nguồn đóng, checksum và uncompressed size, không cần chạy inference.
- **Benchmark #65 / Session #192**: GT 149, AI 150, khớp 138, lọt 11, dư 12, F1 92,3%. Phát hiện 5 cặp cùng canonical trong 12 giây, 2 cặp liên quan AI dư, 3 cặp raw ID khác nhau gần event. **Không tự xóa lượt AI hoặc thay GT.** Xem `docs/benchmark-65-cycle-audit-v0592.md`.
- **Tăng phiên bản `0.5.92`**, migration metadata `0106_cycle_witness_v0592`; kiểm thử hồi quy CLI và JavaScript, PowerShell contract; giữ toàn bộ security, PostgreSQL, dashboard, benchmark, GitHub publication của các bản trước.
- **Giới hạn:** chỉ nâng cấp truy vết và trình duyệt lỗi, thuật toán đếm không đổi; chưa chạy lại GPU/video với V0.5.92 nên không có cơ sở nói F1 tăng. Source ZIP không bao gồm dữ liệu camera/video, model weights hoặc `.env` thật.

**Chạy trên Windows:** `cd D:\LienThongDH\DoAn\traffic-ai` → `Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File` → `.\scripts\test.ps1` → `.\scripts\start.ps1`. Khi kiểm thử thành công, dùng `.\scripts\publish.ps1` với tag mới `v0.5.92` (không ghi đè tag cũ).

**Xuất báo cáo chu kỳ:** `.\scripts\audit-crossing-cycles.ps1 -Export '.\traffic-ai-benchmark-65-session-192.zip' -OutputDirectory '.\crossing-cycle-audit'`.

---

# Traffic AI V0.5.91 — Benchmark Timecode Review Navigator

- **Rà soát 23 mốc lỗi ngay trên web:** sau khi benchmark đã có GT, phần Benchmark Report có bộ lọc `Tất cả / Lọt / Dư / Gần-cạnh tranh timecode` và điều hướng `← Trước / Sau →`. Chọn mốc sẽ **tạm dừng clip** và đưa video đến **0,4 giây trước** timecode; có thể bấm frame-by-frame bằng các nút cũ.
- **Tách trình xem với thuật toán đếm:** không thay đổi Ground Truth, sự kiện AI đã lưu, threshold, Gate, dedup, tracker hay kết quả F1. Điều hướng chỉ dùng report được backend trả về; khi GT = 0 thì không giả tạo danh sách lỗi.
- **Benchmark #64 / Session #191** (ZIP đã xác thực): GT 149, AI 150, khớp 138, lọt 11, dư 12, F1 92,3%. Đối chiếu benchmark #62: cùng 150 crossing, không có lượt AI được sửa hoặc khôi phục. Xem `docs/benchmark-64-review-v0591.md`.
- **7 test frontend mới** cho thứ tự mốc, lọc, timecode không hợp lệ, trường hợp GT trống và không thay đổi báo cáo. Bổ sung PowerShell UI contract và metadata migration `0105_review_nav_v0591`.
- **Không khẳng định cải thiện AI** trước khi chạy lại clip bằng model thật và xác minh từng trường hợp với GT đã duyệt. Nếu không có cảnh video đủ sát, chỉ ghi `cần xem clip`, không tự xóa event.

**Cài và chạy:** `cd D:\LienThongDH\DoAn\traffic-ai` → `Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File` → `.\scripts\test.ps1` → `.\scripts\start.ps1`. Khi chạy ổn và rà soát Git: `.\scripts\publish.ps1` (tag `v0.5.91`, không ghi đè tag cũ).

---

# Traffic AI V0.5.90 — Verified AI-only Replay Comparison + GT Export Freshness

- **Sửa quy trình đối chiếu khi ZIP được xuất trước lúc chép Ground Truth:** vẫn xác thực checksum JSON/trace, session, geometry và so sánh chính xác sự kiện AI đã lưu; KHÔNG tính hoặc suy ra F1/lọt/dư nếu một trong hai ZIP chưa có GT.
- **Sau khi sao chép GT trên web**, thông báo hướng dẫn xuất hồ sơ ZIP mới; ZIP đã tải trước đó không tự cập nhật.
- **Benchmark #63 / Session #190:** ảnh mới cho thấy 149 GT / 150 AI / khớp 138 / lọt 11 / dư 12 / F1 92.3%, nhưng ZIP #63 cũ vẫn có GT 0. So sánh AI-only với ZIP #62 đã xác minh 150 chữ ký sự kiện giống nhau, không có lượt crossing được thêm hoặc xóa.
- Thêm công cụ `scripts/review-benchmark-errors.ps1` xuất `review-queue.csv`, `.md`, `.json` để duyệt tất cả **11 lượt lọt / 12 lượt dư** của benchmark #62 theo timecode, kèm dấu hiệu cạnh tranh; không tự gộp xe hay thay GT.
- Thêm **11 hồi quy** cho GT-free comparison, từ chối hash/nguồn/điểm số không nhất quán. Migration metadata `0104_ai_export_v0590`; giữ các chức năng, quản trị, bảo mật và script cũ.
- Thuật toán AI không thay đổi, chưa có bằng chứng nâng Precision / Recall. Muốn so sánh hiệu quả sau khi đủ GT, xuất lại ZIP #63.

**Lấy danh sách review:** `.\scripts\review-benchmark-errors.ps1 -Export ".\traffic-ai-benchmark-62-session-188.zip" -OutputDirectory ".\benchmark-review"`.

**Chạy:** `cd D:\LienThongDH\DoAn\traffic-ai` → `Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File` → `.\scripts\test.ps1` → `.\scripts\start.ps1`. Sau khi kiểm tra ổn: `.\scripts\publish.ps1` (tag mới `v0.5.90`, không ghi đè tag cũ).

---

# Traffic AI V0.5.89 — Release EOL Preflight + Immutable Tag Diagnostics

**Sửa quy trình phát hành từ log Windows V0.5.88:** `scripts/test.ps1` và
`start.ps1` thành công, nhưng `publish.ps1` dừng ở bước 4 vì tag `v0.5.88` đã tồn
tại trong khi working tree còn thay đổi. Đây là bảo vệ cần giữ nguyên: tuyệt đối
không tự ghi đè hay dời tag cũ.

- **Full-source chuẩn hóa CRLF ngay khi đóng gói** cho toàn bộ `*.ps1`; các file
  code/config khác giữ LF theo `.gitattributes`. `normalize-line-endings.ps1`
  sẽ không tạo biến đổi file khi chạy trên bản ZIP này, nếu không có chỉnh sửa mới.
- **Kiểm thử hồi quy trên package** (`scripts/tests/test_release_eol_v0589.py`):
  kiểm CRLF mọi PowerShell, Git EOL policy, cảnh báo tag có chẩn đoán,
  và LF ở source/config. `scripts/test.ps1` chạy bộ test này trước bước build.
- **Publish diagnostics**: khi tag đã có và Git còn thay đổi, in `git status --short`
  và `git diff --cached --name-status`, không lộ nội dung file; vẫn dừng an toàn.
- **Git ignore an toàn:** bỏ qua ZIP benchmark, RAR camera và thư mục kết quả so sánh
  trong thư mục dự án; không tự đưa dữ liệu lớn vào `git add -A`. Nếu các tệp
  đã bị stage từ lần publish trước, script dừng và hướng dẫn bỏ stage an toàn.
- **Phiên bản mới `0.5.89`**, migration `0103_release_eol_v0589` chỉ đồng bộ
  `schema_version`. Không sửa thuật toán AI, benchmark hay dữ liệu phương tiện.

**Lưu ý quan trọng:** log cho biết 9 file `.ps1` đã được chuyển line endings,
nhưng không cung cấp `git diff` nên chưa thể khẳng định *chỉ* các file đó làm
Git dirty; `.gitattributes` có thể chuẩn hóa nội dung khi stage. Nếu có thay đổi
khác trên máy Windows, nên rà soát trước khi phát hành. Bản mới dùng tag
`v0.5.89`, không ghi đè `v0.5.88`.

## Kiểm thử, khởi chạy và phát hành

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
# Khi đã kiểm tra chạy ổn định:
.\scripts\publish.ps1
```

Giữ nguyên `.git`, `.env`, PostgreSQL volumes, `models/`, `videos/` và dữ liệu
runtime khi cập nhật source. Nếu Git báo có file chỉnh sửa, sử dụng
`git status --short` để kiểm tra; không force tag, không hard reset dữ liệu.

---

# Traffic AI V0.5.88 — Temporal Review Contract Compatibility Fix

**Sửa lỗi thực tế từ Windows `scripts/test.ps1` tại V0.5.67:** test trước đó phụ thuộc nguyên văn
`Tổng GT = AI`, trong khi V0.5.87 đã thay UI để luôn cho review các trường hợp cạnh tranh
timecode **kể cả khi 149 GT khác 150 AI**. Đây là lỗi kiểm thử hồi quy lỗi thời, không phải
lỗi tính toán benchmark.

- Tách chính sách hiện cảnh báo `shouldShowTemporalCompetitionReview()` vào
  `frontend/src/benchmark-review.js`, có thể kiểm thử độc lập bằng Node.
- UI vẫn hiện cạnh tranh thời gian khi audit có bằng chứng, bất kể GT = AI hay GT != AI;
  vẫn ẩn khi không có bằng chứng hoặc GT chưa đủ để chấm điểm. Không chạm logic ghép
  timecode, nhãn GT, điểm số, DB events hay thuật toán AI.
- `scripts/test.ps1` kiểm tra sự hiện diện của chính sách và test cả hai trường hợp,
  không phụ thuộc câu chữ giao diện. Bổ sung 4 unit tests frontend.
- Tăng phiên bản đồng bộ lên `0.5.88` và Alembic migration `0102` chỉ cập nhật
  `schema_version`; không đổi dữ liệu nghiệp vụ.

## Chạy trên Windows

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Sau khi test và chạy thực tế ổn định mới phát hành bằng ` .\scripts\publish.ps1 `.
Không chạy lại tạo tài khoản Admin. Khi cập nhật nguồn, giữ nguyên `.env`, volumes
PostgreSQL, video, trọng số mô hình. Không thay đổi số liệu Benchmark #62:
GT 149 / AI 150 / khớp 138 / lọt 11 / dư 12 (F1 92,3%).

---

# Traffic AI V0.5.87 — Verified Cross-Benchmark Regression + Temporal Competition Review

Tiếp tục từ **V0.5.86**. Benchmark #62 / Session #188: GT **149**, AI **150**, khớp **138**, lọt **11**, dư **12**, sai hướng **2**, sai loại **2** (F1 **92,3%**). Công cụ so sánh bằng chứng đã xác nhận 150 chữ ký crossing và 149 mốc GT trong #61 và #62 giống nhau (ngoại trừ các ID/metadata phiên chạy). **V0.5.86 chưa cải thiện F1 trên clip kiểm chứng này.**

- **Verified Cross-Benchmark Regression** (`scripts/compare-benchmark-exports.py`): so sánh trực tiếp hai ZIP `Tải hồ sơ benchmark` mà không cần đăng nhập hay kết nối DB; kiểm tra SHA-256 JSON/trace, session, cùng video/vạch/FPS/GT/cửa sổ ghép, so sánh chữ ký sự kiện AI độc lập với ID tracker và DB. Từ chối so sánh khi dữ liệu nguồn/GT không tương thích.
- **Báo cáo JSON + Markdown tiếng Việt**: thể hiện tất cả delta Recall/Precision/F1/lọt/dư, số event thêm/bớt và GT lỗi xuất hiện/hết; chỉ coi ghép timecode là bằng chứng thời gian, không chứng minh danh tính vật lý hay tự sửa GT. Có lệnh PowerShell `scripts/compare-benchmark-exports.ps1` để kiểm tra các phiên trong tương lai.
- **Sửa lỗi hiển thị review benchmark:** trước đây khối cạnh tranh thời gian chỉ hiện khi tổng GT = tổng AI (`count_totals_equal`). Ở #62 (149 ≠ 150), khối bị ẩn dù có 4 mốc lọt bị event DB khác nhận và 2 AI dư sát GT đã ghép. V0.5.87 luôn cho phép mở `Đối chiếu GT/AI có trường hợp cạnh tranh thời gian` khi có chứng cứ, bất kể tổng GT/AI khác nhau, nhưng mặc định thu gọn để tránh kéo dài giao diện.
- **7 unit tests** mới và contract PowerShell cho so sánh 2 ZIP, từ chối GT khác, phát hiện sửa file sau khi xuất, cùng hiệu ứng GUI. Thêm migration `0101` chỉ cập nhật `schema_version`, không sửa data DB, GT hoặc thuật toán counting.

**Không tinh chỉnh Gate/Tracker theo những cặp chỉ gần thời gian:** trong ảnh camera 519–520s có nhiều xe gần vạch, 638s có nhiều sự kiện cạnh nhau. Việc xóa event mà chưa chứng minh cùng xe có thể tăng lọt. Để nâng độ chính xác AI thực tế cần chạy inference toàn bộ clip cùng trọng số và kiểm chứng từng instance. Phiên bản này cải thiện quy trình chẩn đoán và tính minh bạch, không cam kết giảm lọt/dư.

## Chạy sau giải nén trên Windows

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

## So sánh 2 hồ sơ benchmark

```powershell
.\scripts\compare-benchmark-exports.ps1 -Prior ".\traffic-ai-benchmark-61-session-187.zip" -Current ".\traffic-ai-benchmark-62-session-188.zip" -OutputDirectory ".\benchmark-comparison"
```

Khi test và chạy AI ổn định, phát hành một lệnh: `.\scripts\publish.ps1`. Tài khoản Admin đã tồn tại, không chạy tạo lại.

---

# Traffic AI V0.5.86 — Visible-Incumbent Reservation + Benchmark #61 Forensics

Tiếp tục từ **V0.5.85**. Baseline thực tế Benchmark #61 / Session #187: GT **149**, AI **150**, khớp timecode **138**, lọt **11**, dư **12**, sai loại **2**, sai hướng **2** (Recall **92,6%**, Precision **92,0%**, F1 **92,3%**). Đây là kết quả **V0.5.85**, không phải replay V0.5.86.

- **Visible-Incumbent Reservation (4–12 frame):** nếu xe hai bánh trước đó bị che trong 4–12 frame, raw tracker cũ và raw tracker mới **cùng hiện diện trong cùng một frame**, và raw cũ nằm gần hơn đáng kể vị trí canonical cuối, bảo lưu canonical cho raw cũ. Chặn raw mới chiếm sai danh tính do thứ tự xử lý; không tạo lượt đếm mới và không mở rộng Gate/Road Zone/cooldown.
- Chỉ hoạt động khi có bằng chứng đủ từ `visible_raw_centers`, không ảnh hưởng trường hợp xe thật trở lại bằng raw mới nhưng raw cũ không hiện diện. Xe 4 bánh vẫn giữ ngưỡng 3 frame. Có thể A/B rollback bằng `AI_SHORT_GAP_ALIAS_GUARD=0` rồi khởi động lại dịch vụ.
- **Vehicle Count dễ đọc:** tổng lượt DB/IN/OUT và số lượng theo từng loại xe được giữ trên cùng. Các chỉ số worker, bộ lọc, refiner chuyển vào mục mở rộng **Thông số kỹ thuật**; nhắc rõ những giá trị Trực tiếp/Nội suy/Rescue là đề xuất worker, có thể cao hơn tổng đã lưu ở backend do dedup/Human Guard.
- **Session #187 forensics:** kiểm tra SHA256 trace và hồ sơ benchmark, đọc ảnh camera xuất kèm tại frame 7243 (người dắt xe đạp và xe máy cùng khu vực), frame 16050/22059 (van chở hàng). Tại 641,931s GT hiện gán Ô tô nhưng AI gán Xe tải; phải kiểm tra quy ước GT, không tự sửa GT. Khác biệt khớp timecode không chứng minh AI đã nhận đúng đối tượng.
- Thêm **5 test** cho khả năng giữ raw incumbent, xe quay lại thật, incumbent ở xa, rollback và xe 4 bánh. Migration `0100` metadata-only, không chạm events/GT, giữ cơ chế backup/restore.

**Giới hạn:** không có môi trường Docker/GPU và trọng số model để chạy lại 23.650 frame. Chưa thể khẳng định F1/Recall mới đã tăng hoặc lọt/dư mới đã giảm. Sau khi chạy lại clip, xuất ZIP benchmark mới để đánh giá đối chứng.

## Lệnh PowerShell

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Sau khi xác nhận chạy ổn và các kiểm tra đạt, dùng ` .\scripts\publish.ps1 ` để test → commit/push → tag → GitHub Release. Tài khoản Admin đã có, không cần tạo lại.

---

# Traffic AI V0.5.85 — Short-Gap Alias Handoff Evidence Guard

Nâng cấp từ **V0.5.84**. Benchmark #60 / Session #186 cho thấy GT 149 / AI 151 / khớp timecode 138 / lọt 11 / dư 13. Thay đổi bộ ghép danh tính dựa trên quỹ đạo, không đọc GT lúc chạy.

- **Short-Gap Alias Evidence Guard:** chặn ByteTrack token mới chiếm nhầm danh tính xe máy/xe đạp cũ sau mất 4–12 frame nếu cả khoảng cách thực tế (>1,75 lần đường chéo hộp xe) và lệch dự đoán vận tốc (>1,50 lần) đều lớn.
- **Fast motion preservation:** xe chạy nhanh vẫn được nối nếu phù hợp hướng chuyển động, không chặn chỉ vì quãng đường lớn; không thay guard cho xe 4 bánh.
- Có thể đặt `AI_SHORT_GAP_ALIAS_GUARD=0` trong `.env` để A/B so sánh nếu có hồi quy, nhưng cần khởi động lại AI Service.
- Dashboard/trace có chỉ số `short_gap_alias_rejections`, tách khỏi `raw_id_discontinuities`.
- Bài test tái hiện frame 15143→15152 từ Session #186, xe chạy nhanh và xe bốn bánh.
- Migration 0099 chỉ cập nhật schema_version; không đổi cấu trúc PostgreSQL. Giữ Backup/Restore, phân quyền và model.

**Chưa chạy GPU replay.** Không thể kết luận đã giảm 11 lượt lọt / 13 dư trước khi chạy lại video. Nếu benchmark hồi quy, giữ source/backup trước và gửi ZIP benchmark mới.

## Lệnh PowerShell

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Sau khi chạy và kiểm thử ổn: `.\scripts\publish.ps1`. Không tạo lại tài khoản Admin.

---

## Lịch sử nâng cấp trước

# Traffic AI V0.5.84 — Per-Raw Provenance for ByteTrack Aliases

Nâng cấp từ full source V0.5.83. V0.5.84 xử lý trường hợp **Raw ID
thực sự bị tái sử dụng nhưng vị trí Canonical ID đã được alias khác cập nhật
nên che khuất bước nhảy**. Bộ kiểm tra mới dùng lịch sử theo từng Raw ID
**và** bảo vệ gián đoạn lớn của Canonical ID khi đổi alias. Trường hợp
hai ID cùng lái một danh tính qua hai vị trí không thể liên tục vẫn bị
tách để tránh crossing ảo. Không thay ngưỡng chuyển động Gate/rescue.

- Lưu raw-token position/rect/frame độc lập với Canonical ID; phát hiện
  teleport cả khi bị vị trí alias khác che khuất, đồng thời giữ quy tắc
  an toàn chống nối quỹ đạo Canonical vượt quãng đường bất thường.
- Xóa quan sát raw khi canonical hết TTL. Không đổi ngưỡng Gate, rescue,
  cooldown, thời gian giao sự kiện hoặc GT.
- `audit-raw-id.ps1` phân biệt số reset cộng dồn trên **toàn bộ frame** với
  jump tìm thấy trong `gate_tracks` (chỉ các track được trace quanh vạch).
  Ghi timecode và frame khi counter tăng, hỗ trợ đối chiếu video.
- Thêm 5 bài test cho alias có/không có lịch sử đo, teleport bị che, teleport thật và TTL;
  đồng bộ metadata, migrations, script test và hợp đồng CI.
- Benchmark #59 Session #185 (GT 149, AI 151, khớp timecode 138,
  strict 134, lọt 11, dư 13, sai hướng 2, sai loại 2) là **baseline**.
  **Chưa có GPU replay để khẳng định V0.5.84 cải thiện các con số này.**

## Chạy/kiểm thử sau nâng cấp

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Sau khi chạy ổn định, phát hành GitHub bằng `.\scripts\publish.ps1`.
Tài khoản Admin đã tồn tại, **không chạy** `create-admin.ps1`.

---

# Traffic AI V0.5.83 — Direction-aware Benchmark + Replay Regression Witness

Nâng cấp từ **V0.5.82**. Bổ sung chỉ số đánh giá đúng timecode + hướng + loại xe,
giao diện hiển thị các cặp GT/AI sai hướng và công cụ chứng cứ sự kiện biến mất
khi chạy lại cùng clip. Không sửa GT, không thay ngưỡng thuật toán AI và không
can thiệp dữ liệu PostgreSQL.

## V0.5.83 — Những thay đổi

- `strict_matches`, `strict_precision`, `strict_recall`, `strict_f1` chỉ công nhận
  các cặp timecode khớp **đồng thời đúng IN/OUT và loại phương tiện**.
- `direction_mismatches` và `direction_mismatch_items` chỉ rõ từng GT/AI sai hướng;
  nút timecode trên giao diện cho phép xem lại video. Các chỉ số `matched`,
  `missed`, `false_positives`, `counting_recall` truyền thống không đổi.
- `scripts/compare-gt-replays.ps1`: so sánh reference ZIP benchmark với trace
  chạy mới, báo những event mất/xuất hiện và chứng cứ hướng GT đã ghép trước đó.
  Sử dụng `-Strict` để fail khi có thay đổi; không dùng PASS làm chứng nhận accuracy.
- Benchmark #57 / Session #182: 139 cặp khớp timecode; **3 sai hướng**, **2 sai loại**,
  **134 cặp khớp đủ 3 điều kiện**. Trace Session #183 giảm còn 151 event, mất
  một event OUT tại 290.064s; baseline event này đã từng ghép GT IN tại 289.824s.
- `test.ps1`, GitHub Actions và migration `0097_direction_audit_v0583` tích hợp
  kiểm tra mới. Chỉ nâng metadata schema version; không sửa bảng DB.

### Kiểm tra chênh lệch Session #182 và #183

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\compare-gt-replays.ps1 `
  -ReferenceBenchmark .\traffic-ai-benchmark-57-session-182.zip `
  -CurrentTrace .\session_183_benchmark-trace.jsonl `
  -OutputDirectory .\gt-replay-witness-report `
  -Strict
```

Trace Session #183 là file JSONL trong bộ camera RAR, cần giải nén trước; hoặc
sử dụng ZIP “Tải hồ sơ benchmark” #183 và truyền trực tiếp làm `-CurrentTrace`.
Với trace hiện tại, `-Strict` **dự kiến FAIL** vì một event biến mất.

> **Chưa có kết quả GPU replay chứng minh 11 lọt / 13 dư được giảm.**
> Bản này cải thiện đo lường, phát hiện hồi quy và bằng chứng chấm điểm,
> không âm thầm điều chỉnh thuật toán đếm dựa trên giả định về GT.

---

# Traffic AI V0.5.82 — Raw ID Reuse Guard + Gate Trace Audit 10.1

**Nâng cấp từ full source V0.5.81.** Tập trung ngăn ByteTrack tái sử dụng cùng Raw Track ID cho xe khác ngay gần vạch đếm, gây kế thừa nhầm quỹ đạo, class và trạng thái crossing. Không thay đổi các ngưỡng Gate, cooldown, rescue hoặc chống trùng đã có.

- **Same-Raw Identity Discontinuity Guard:** Nếu cùng Raw Track ID bất ngờ nhảy rất xa trong tối đa 3 frame, đồng thời vượt 18% đường chéo toàn ảnh **và** hơn 3 lần đường chéo hai hộp detection, hệ thống tách danh tính mới. Chỉ tách khi có đủ hai hộp và tọa độ quan sát; không đoán danh tính bằng nhãn GT hay tổng đếm.
- **Chống tái ghép sai:** Raw ID vừa được tách không thể lập tức stitch lại Canonical ID đã bị loại. Các canonical track còn tồn tại được giữ riêng để tiếp tục theo dõi nếu đối tượng thật xuất hiện trở lại.
- **Telemetry:** Bổ sung số `Raw ID reset` trên dashboard, trạng thái phiên AI và benchmark trace để xác nhận bảo vệ có kích hoạt khi phát video. Mặc định 0 nếu không phát hiện lỗi.
- **Audit độc lập:** `scripts/audit-raw-id.ps1` đọc ZIP **Tải hồ sơ benchmark** đã đóng, xác minh SHA-256 của trace và tạo `raw-id-audit.json` / `raw-id-audit.md` với các frame nghi ngờ, không sửa GT/event.
- Có thể chỉnh `AI_STITCH_RAW_REUSE_JUMP_RATIO` trong `.env` (mặc định `0.18`; `0` tắt guard) nhưng không nên giảm ngưỡng khi thiếu bằng chứng, vì nguy cơ chặt đứt đường đi xe nhanh.
- **Phân tích Benchmark #57 Session #182** (23.650 frame): GT 149 / AI 152 / khớp 139 / lọt 10 / dư 13. Audit mới cho **0 sự kiện nhảy Raw ID cực đoan gần vạch** theo ngưỡng trên. Điều này **không có nghĩa đã sửa 10 lọt / 13 dư**; cần phát lại để đo. Nhiều sự kiện gap/ID đổi đã có hướng di chuyển hợp lý nên không thể áp quy tắc loại theo khoảng cách chung.
- Migration `0096_raw_id_reuse_v0582` chỉ cập nhật `schema_version` sang `0.5.82`. PostgreSQL, tài khoản, backup/restore, video/model và GT không bị sửa.

## Lệnh PowerShell đầy đủ

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

.\scripts\test.ps1
.\scripts\start.ps1
```

Audit sau khi tải ZIP từ giao diện Benchmark:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\audit-raw-id.ps1 -ExportZip .\benchmark-182.zip -OutputDirectory .\raw-id-audit-report
```

Sau khi kiểm tra máy Windows/Docker và benchmark ổn định, phát hành GitHub bằng ` .\scripts\publish.ps1 `. **Không chạy `create-admin.ps1`** vì Admin đã tồn tại.

---

# Traffic AI V0.5.81 — Quiet Startup + Backup Worker pip Test Hygiene

**Nâng cấp trực tiếp từ V0.5.80**, không thay đổi thuật toán đếm AI, model, mật khẩu, database hoặc hành vi Backup/Restore. Bản này sửa hiển thị khi chạy test và khởi động.

- Trong `scripts/test.ps1`, chỉ riêng bước Backup Worker unit test được thêm biến môi trường `PIP_ROOT_USER_ACTION=ignore` và `PIP_DISABLE_PIP_VERSION_CHECK=1` vào **container Docker dùng một lần**. Tránh cảnh báo pip cài bằng root trong container; **không** tắt cảnh báo/lỗi của Docker, PowerShell, pytest hoặc quy trình vận hành thật.
- Trong `scripts/start.ps1`, bỏ log thời gian chờ `Waiting for ... (starting, Xs/Ys)` và `healthy after Ns`; khi thành công chỉ hiển thị `[OK] <container> healthy.`.
- **Vẫn chờ container ready và giữ các giới hạn an toàn 120/180/240 giây** cùng healthchecks, thông báo timeout, trạng thái failed và log chẩn đoán khi lỗi. Không thay đổi độ trễ hoặc cho phép khởi động bỏ qua service lỗi.
- Thêm 4 bài kiểm thử hợp đồng console/startup. Chạy trong `scripts/test.ps1` và GitHub Actions, ngăn lần nâng cấp sau vô tình đưa bộ đếm thời gian chờ trở lại.
- Đồng bộ `VERSION=0.5.81`, API, frontend, AI Service, Backup Worker, favicon cache; migration `0095_quiet_startup_v0581` chỉ cập nhật `schema_version`, không thay đổi bảng dữ liệu.
- Benchmark #57 / Session #182 từ máy người dùng: GT 149 / AI 152 / khớp 139 / lọt 10 / dư 13. **V0.5.81 không sửa lỗi đếm**; không dùng việc tắt log để tuyên bố cải thiện Recall/Precision.

## Chạy trên Windows (tài khoản Admin đã tồn tại)

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Kiểm tra source
.\scripts\test.ps1

# Khởi động hệ thống
.\scripts\start.ps1
```

Sau khi chạy và kiểm thử ổn định, xuất bản bằng ` .\scripts\publish.ps1 `. Nếu timeout hoặc service unhealthy, `start.ps1` vẫn thông báo lỗi và in log chẩn đoán; chỉ ẩn dòng đếm giây trong lúc chờ.

---

# Traffic AI V0.5.80 — Incumbent Identity Protection (Cross-ID Anti-Swap)

**Nâng cấp từ V0.5.79; giữ nguyên PostgreSQL, tài khoản, Backup/Restore và chính sách chống đếm trùng V0.5.78.**

- Từ benchmark #56 / Session #180: 149 GT / 152 AI / khớp 139 / lọt 10 / dư 13. Cải thiện so với #179 là giảm 1 dư; số lượt lọt vẫn 10.
- Trace quanh 606 giây thể hiện hai raw ByteTrack cùng hiện diện nhưng canonical identities đổi chỗ khi một raw ID mới được xét trước raw ID đã hiện diện. Chỉ dùng khoảng cách crossing để xóa một event có thể gộp nhầm hai xe thật.
- **V0.5.80** thêm snapshot vị trí Raw Track ID của toàn frame trước khi ghép canonical: một canonical có incumbent vừa xuất hiện ở gần vị trí trước đó được bảo vệ khỏi các raw ID mới có điểm ở xa hơn rõ rệt. Không giữ chỗ cho incumbent đã biến mất, không thay ngưỡng vạch đếm/rescue. Có bài test cho chủ sở hữu quay lại, ID mới, ID cũ mất và trường hợp tracker nhảy quá xa.
- Đường tracking hiện có giữ tương thích khi không cung cấp snapshot; snapshot chỉ thêm xác thực quyền ưu tiên chủ ID và không dựa trên nhãn GT để đếm.
- **Kết quả cần kiểm chứng:** thay đổi danh tính có thể làm khác crossing. Chưa chạy GPU trên clip gốc; **không cam kết giảm từ 10 lọt / 13 dư** trước khi phát lại. Report của phiên #180 là baseline, không phải kết quả V0.5.80.
- Migration `0094_incumbent_identity_v0580` chỉ cập nhật schema_version, không thay đổi bảng. Đồng bộ VERSION/frontend/backend/AI/backup và kiểm tra hợp đồng phát hành.

## Lệnh chạy PowerShell (Admin đã tồn tại)

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Khi vận hành/benchmark được kiểm tra ổn định: ` .\scripts\publish.ps1 `.

---

# Traffic AI V0.5.79 — Release Version Consistency Hotfix

**Sửa lỗi chặn `scripts/test.ps1` khi `VERSION=0.5.78` nhưng contract vẫn cố định 0.5.77.** Bản sửa tăng release lên V0.5.79, dựa hoàn toàn trên source V0.5.78.

- Thay so sánh version cứng bằng so khớp file `VERSION` với frontend, backend, AI Service, backup worker và metadata sao lưu; kiểm tra các query cache favicon/manifest.
- Quét Alembic revision graph để xác nhận chỉ một head, đầy đủ parent và `schema_version` trong head trùng `VERSION`. Bảo toàn migration và dữ liệu cũ. Migration mới `0093_version_contract_v0579` chỉ sửa metadata phiên bản.
- Thêm `scripts/version-contract.py`, bài test tái hiện hardcode/stale package và kiểm tra trong cả `scripts/test.ps1`, `.github/workflows/ci.yml` và `ci-release-reusable.yml`.
- Đồng bộ API/health version, frontend, AI Service, backup worker và file icon cache; **không thay đổi logic AI crossing, các ngưỡng chống trùng, mật khẩu, quyền truy cập hoặc dữ liệu PostgreSQL**.
- Vẫn chưa chứng minh 0 lọt/0 dư. Kết quả Benchmark #179 mới nhất: GT 149, AI 153, khớp 139, lọt 10, dư 14. V0.5.78 dự đoán offline loại được 1 dư nhưng chưa replay thực tế.

## Chạy thử và khởi động Windows

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Sau khi test và chạy ổn, phát hành bằng ` .\scripts\publish.ps1 `; không chạy `create-admin.ps1` vì tài khoản Admin đã tồn tại.

---

# Traffic AI V0.5.78 — Bounded Direct Shadow Closure + GT-Verified Counterfactual

**Nâng cấp từ V0.5.77; giữ nguyên cấu hình camera, AI model, PostgreSQL, tài khoản và Backup/Restore.**

### V0.5.78 thay đổi gì?

- Sửa **một lỗi đếm trùng đã có bằng chứng ảnh và GT** của Session #179: tại t=491.920/492.200 giây, cùng xe máy có hai hộp/track ID khác nhau ở cùng vị trí crossing, đều là `direct`, `out`, `motorcycle`. Khoảng cách crossing chuẩn hóa 0.008587, dt 0.28 s. Bản cũ không loại vì giới hạn 0.006.
- Backend nâng **duy nhất** DIRECT/DIRECT cùng lớp/hướng khác ID lên **dt ≤ 0.32 giây và khoảng cách ≤ 0.009** cho đuôi mới; **giữ nguyên** guard cũ dt ≤ 0.42 giây, khoảng cách ≤ 0.006. Không thay điều kiện các crossing `rescued/interpolated` hoặc các trường hợp khác hướng/khác loại; thêm module thuần `backend/app/shadow_guard.py` để source và phân tích offline dùng chung đúng một quy tắc.
- Thêm `scripts/evaluate-direct-shadow.ps1` đọc `Tải hồ sơ benchmark` để **giả lập** bộ lọc từ AI events, không đọc GT trước khi chọn ứng viên, đối chiếu lại GT bằng thuật toán benchmark hiện có. Kiểm tra manifest SHA-256; không ghi vào PostgreSQL hay thay đổi GT.
- Thêm kiểm thử hồi quy cho hai track chồng nhau, giữ xe khác vị trí, hướng/loại khác nhau, guard thời gian chặt và checksum hỏng. Migration Alembic `0092_direct_shadow_v0578.py` chỉ tăng `system_settings.schema_version`; không thay bảng dữ liệu.

### Benchmark #179 (từ ZIP người dùng cung cấp)

| Dữ liệu | Trước | Giả lập V0.5.78 trên events cũ |
|---|---:|---:|
| Ground Truth | 149 | 149 |
| AI | 153 | 152 |
| Khớp | 139 | 139 |
| Lọt | 10 | 10 |
| Dư | 14 | 13 |

**Cảnh báo về chất lượng:** số cột giả lập chỉ chứng minh tác động có thể có trên event snapshot có sẵn; không phải kết quả replay model GPU với thuật toán mới. 10 lượt lọt và 13 lượt dư khác vẫn chưa được chứng minh khắc phục. Không ghép lại các event theo GT lúc chạy AI, không ép tổng AI = 149, không thay ảnh/trace/GT. Các dạng lọt do anchor/Gate/track loss và dư do cứu gap cần được kiểm chứng riêng trước khi thay đổi ngưỡng lớn.

### Lệnh chạy và kiểm tra

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Không cần `create-admin.ps1`. Để đánh giá offline:

```powershell
.\scripts\evaluate-direct-shadow.ps1 -ExportZip .\benchmark-179.zip -OutputDirectory .\shadow-report
```

Chỉ phát hành sau khi kiểm thử chạy tốt tại máy người dùng bằng `.\scripts\publish.ps1`.

---

# Traffic AI V0.5.77 — Startup Path Fix + Verified GT Case Forensics

**Khắc phục blocker V0.5.76:** `scripts/start.ps1` dùng biến `$root` chưa khai báo khi đọc `VERSION`, khiến PowerShell dừng ở bước Gateway với `Cannot bind argument to parameter 'Path' because it is null`. Đã sửa thành `$ProjectRoot`, biến được khởi tạo ngay đầu script. Có contract kiểm tra để tránh tái phát.

**Phân tích GT–AI từng sự kiện (chỉ đọc):** thêm `scripts/benchmark-forensics.py` và `scripts/analyze-benchmark.ps1`. Nhận **ZIP Tải hồ sơ benchmark** đã đối chiếu, xác minh `manifest.json`, SHA-256 của từng thành phần, kiểm tra đúng các số đếm bảo toàn `matched + missed = GT`, `matched + extra = AI`, và xuất `cases.json` / `cases.md` liệt kê chính xác từng GT bị lọt và từng AI event bị dư. Nếu ZIP có trace đóng đầy đủ, đối chiếu cửa sổ ±1 giây quanh từng timecode với quan sát track hai phía vạch, event được backend ghi, phương pháp crossing. Kiểm tra SHA-256 của cả trace nén và dữ liệu giải nén, giới hạn dung lượng, từ chối trace thiếu metadata/geometry/footer. Nếu không có trace, báo thiếu rõ ràng và chỉ cung cấp bằng chứng từ báo cáo backend.

**Phạm vi thay đổi:** không chỉnh Ground Truth, không xóa/ép event AI, không thay thuật toán đếm, model, vạch đếm, Road Zone, ngưỡng rescue hoặc cơ chế backend dedup. Giữ nguyên Backup/Restore, tài khoản, dữ liệu DB. Migration `0091_gt_forensics_v0577.py` chỉ đổi `system_settings.schema_version`, nối từ V0.5.76.

**Quan trọng về độ chính xác:** Session #177/#178 ổn định 153→153 nhưng vẫn GT=149 / matched=139 / missed=10 / extra=14. Bộ RAR của camera có 196 MB/frame trace nhưng **không chứa toàn bộ 149 GT đã đánh dấu**, vì vậy chưa thể sửa 10/14 có kiểm chứng. Kết quả của tool mới là chẩn đoán, **không phải** bản AI đã đạt 0 lọt/0 dư. Cần ZIP benchmark đầy đủ (có `ground-truth.json`, `events.json`, `report.json`) để triển khai/tối ưu thuật toán đúng các sự kiện sai và so sánh hồi quy sau đó.

### Cách chạy chuẩn

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Sau khi hoàn thành benchmark của Session #178, nhấn **Tải hồ sơ benchmark**, lưu vào thư mục source với tên `benchmark-178.zip`, chạy:

```powershell
.\scripts\analyze-benchmark.ps1 -ExportZip .\benchmark-178.zip -OutputDirectory .\benchmark-forensics-report
.\scripts\check-benchmark.ps1 -ExportZip .\benchmark-178.zip -MaxMissed 0 -MaxExtra 0
```

Lệnh `check-benchmark.ps1` phải báo FAIL khi còn 10 lượt lọt / 14 lượt dư. Đây là fail đúng theo chất lượng, không phải lỗi script. Gửi ZIP `benchmark-178.zip` để đối chiếu từng GT với event, sửa thuật toán mà không tạo false positive mới. Sau khi test/chạy tốt, xuất bản bằng ` .\scripts\publish.ps1 ` (không cần tạo lại Admin).

---

# Traffic AI V0.5.76 — GitHub Actions AI token regression fix

- **Fix GitHub Actions backend test (18 failures):** workflows now provide a **test-only** `AI_SHARED_TOKEN` (previously only `scripts/test.ps1` supplied it).
- `backend/tests/test_app.py` uses a temporary, per-test fixture to configure the internal RPC token even on standalone pytest machines without `.env`. After each test the original setting is restored.
- New negative regression test asserts missing, empty, wrong tokens and blank server secret all **fail with HTTP 401**. Production `_assert_ai_token` is unchanged and fail-closed.
- No change to detection/tracking/crossing or Gate, no count threshold change. Sessions #177 and #178 replay identically (153 events; removed 0, introduced 0, decision flips 0), **but** GT=149, matches=139, missed=10, extra=14; replay stability is not GT accuracy.
- Alembic `0090_ci_token_v0576`: updates only `system_settings.schema_version`; the source retains backup/restore and all previous features.
- For a true GT-accuracy fix, export a full **Tải hồ sơ benchmark** ZIP with ground-truth, event list and report. RAR frames/trace alone cannot establish which of the 10/14 cases are genuine algorithm errors versus matching issues.

## PowerShell sau khi nâng cấp

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Nếu mọi kiểm tra đạt, phát hành qua `./scripts/publish.ps1` trong PowerShell (lệnh thực tế: `.\scripts\publish.ps1`). Không cần tạo lại Admin.

---

# Traffic AI V0.5.75 — Replay Drift Audit / Stability Gate

## V0.5.75 bổ sung chức năng gì?

**Kế thừa nguyên vẹn V0.5.74**: Backup/Restore PostgreSQL, lịch sao lưu, chuyển máy, tài khoản Unicode, Argon2id, phân quyền, camera, dataset và benchmark. Thuật toán đếm, ngưỡng Gate/ROI/rescue/cooldown/FP closure **không bị tự động nới hoặc chỉnh** trong phiên bản này vì chưa có file ZIP đối chiếu GT/AI hoàn chỉnh cho Session #175.

- **Replay Drift Audit** (`scripts/replay-diff.py`): phát hiện chênh lệch của hai lần chạy cùng video theo **source timecode, hướng IN/OUT và tọa độ crossing**; không phụ thuộc raw tracker ID hoặc mã event database (có thể đổi qua lần chạy).
- Nhận đầu vào dạng **ZIP “Tải hồ sơ benchmark”** từ giao diện (nếu chứa `benchmark-trace.jsonl.gz`/`.jsonl`), hoặc file `session_<id>_benchmark-trace.jsonl`/`.jsonl.gz` trong thư mục camera. Với ZIP, bắt buộc manifest đúng schema và SHA-256 của trace phải khớp.
- **Kiểm tra tương thích chặt**: session phải khác nhau, camera ID, FPS, số frame và Road Zone/đường đếm phải giống nhau; trace đủ tất cả frame, delivery đã drain, không rơi acknowledgement. ZIP thiếu trace, lỗi dữ liệu hoặc checksum → FAIL thay vì đưa ra kết quả giả.
- **Ghép 1–1 toàn cục** trong cửa sổ 0,75 giây và 0,025 đơn vị tọa độ chuẩn hóa (thay đổi được), phân biệt crossing mới, crossing mất, **backend thay đổi quyết định lưu/loại**, timecode dịch >2 frame. Xuất `replay-diff.json` và `replay-diff.md` với những timecode cần xem lại.
- **Chế độ strict** dành cho regression: FAIL (exit 1) khi event DB chỉ còn ở một run hoặc quyết định dedup đổi; lỗi dữ liệu không hợp lệ trả exit 2. Mặc định chỉ tạo báo cáo, không tự đổi tham số AI hay GT.
- Thêm PowerShell `scripts/compare-replays.ps1`, 15 unit tests stdlib mới tích hợp `scripts/test.ps1`, migration Alembic `0089_replay_drift_v0575` tiếp nối V0.5.74 (chỉ thay `system_settings.schema_version`). Không sửa bảng người dùng, dữ liệu hoặc restore.
- Kèm báo cáo thực tế `docs/replay-session-174-vs-175.md` từ hai trace gốc do người dùng gửi; **không kèm trace 196 MB/video/ảnh cá nhân** trong source.

### Kết quả Replay Audit thực tế (hai trace 23.650 frame)

| Chỉ số | Session #174 | Session #175 |
|---|---:|---:|
| Worker đề xuất crossing | 195 | 192 |
| Backend ghi event | 149 | 153 |
| Backend từ chối trùng | 46 | 39 |

Trong cửa sổ so sánh mặc định: **187 đề xuất ghép gần nhau, 8 đề xuất chỉ có ở #174, 5 đề xuất chỉ có ở #175, 6 đề xuất đổi trạng thái/reason; 1 event DB chỉ có ở #174 và 5 event DB chỉ có ở #175**. Kết quả strict trả FAIL đúng. Đây là **dao động giữa hai lần phát lại, không phải số xe lọt/dư xác định**; các ghép chỉ dựa timecode/vị trí, không xác minh danh tính vật lý. Trace hiện chưa chứa hash nội dung clip nên vẫn phải tự xác nhận sử dụng cùng video.

### Kiểm tra, chạy trên Windows PowerShell

Dùng source ZIP mới, giữ nguyên `.env`, volumes PostgreSQL và Backup, model/video/dataset. Không chạy `docker compose down -v`, không tạo lại Admin.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

### So sánh hai phiên và xuất báo cáo

Trong trang Ground Truth Benchmark của mỗi session đã hoàn tất, bấm **Tải hồ sơ benchmark** để có hai ZIP. Nếu ZIP bị thiếu trace, hãy lấy file `session_XXX_benchmark-trace.jsonl` đã được lưu cùng ảnh camera, hoặc export lại sau khi chạy xong; tool từ chối ZIP thiếu trace.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

# Thay đường dẫn bằng hai ZIP tải thực tế từ web
.\scripts\compare-replays.ps1 -PreviousTrace .\benchmark-174.zip -CurrentTrace .\benchmark-175.zip -OutputDirectory .\replay-diff-report

# Kiểm tra nghiêm ngặt: chủ động báo lỗi nếu các lần phát lại không nhất quán
.\scripts\compare-replays.ps1 -PreviousTrace .\benchmark-174.zip -CurrentTrace .\benchmark-175.zip -OutputDirectory .\replay-diff-report -Strict
```

Mở `replay-diff-report/replay-diff.md` để xem timecode, hoặc xem `replay-diff.json` cho công cụ xử lý tiếp. Có thể thay đường dẫn ZIP bằng `.jsonl`/`.jsonl.gz`. Tool yêu cầu Python >=3.10 trên Windows, không cần Ultralytics/GPU để phân tích.

**Điểm Ground Truth bắt buộc kiểm riêng** (không thay bằng Replay Drift Audit):

```powershell
.\scripts\check-benchmark.ps1 -ExportZip .\benchmark-175.zip -MaxMissed 0 -MaxExtra 0
```

Chỉ khi đã kiểm tra/test ổn định mới phát hành GitHub với `./scripts/publish.ps1` hoặc trong PowerShell:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\publish.ps1
```

### Giới hạn kiểm thử / chất lượng AI

- **Backend 171/171**, **AI 635/635**, **frontend unit 4/4**, **backup worker 4/4**, **benchmark gate 5/5** và **Replay Audit 15/15** đạt trong môi trường kiểm thử. Backend/AI cần lớp tương thích `httpx2` ở môi trường hiện tại; lớp đó **không đóng gói vào source**. Đã thử công cụ mới trực tiếp với hai file trace 196 MB (không chứa GT toàn bộ). 
- Chưa chạy `npm run build` với Node v26/Vite v8, Docker Compose/PostgreSQL thật, migration và GPU/replay video thực tế trên Windows ở môi trường đóng gói. Hãy chạy `test.ps1` trên máy của bạn trước khi publish.
- **Không cam kết giảm 10 lượt lọt / 14 lượt dư** của Session #175; chỉ sau khi cung cấp ZIP benchmark hoàn chỉnh mới có thể đối chiếu GT–AI và hiệu chỉnh thuật toán một cách có căn cứ.

---

# Traffic AI V0.5.74 — PostgreSQL Backup & Restore / Migration Kit

## Mới trong V0.5.74

**Nền V0.5.73 được giữ nguyên** (Unicode users / security / counting). Không thay đổi thuật toán đếm hay tham số AI; benchmark Session #175 vẫn chưa có bằng chứng để kết luận đã giải quyết 10 lọt / 14 dư.

- Trang **Admin → Backup / Restore** (`#backups`): sao lưu thủ công, xem bản sao, tải `.dump` PostgreSQL 18, tải ZIP chuyển máy, tải ZIP/.dump lên máy mới, yêu cầu khôi phục, theo dõi tác vụ và lỗi.
- Service `backup-worker` riêng, xây từ `postgres:18.6`: dùng `pg_dump -Fc`, `pg_restore --list`, SHA-256, ghi tệp tạm rồi thay tên atomically; không cấp Docker socket cho backend.
- **Backup tự động** mặc định 24 giờ/lần, giữ 14 bản tự động; có thể chỉnh lịch trực tiếp trên web (1–720 giờ; giữ 1–365 bản). Chỉ bản tự động cũ bị dọn; không tự xóa backup thủ công/import.
- **Khôi phục thận trọng**: kiểm tra SHA-256 → tạo database tạm → `pg_restore --exit-on-error --single-transaction` → kiểm tra `alembic_version` → tạm khóa API và đổi tên database; database cũ được giữ dưới tên `traffic_old_<12 ký tự>` để có thể hoàn tác. Một khoảng gián đoạn kết nối là cần thiết. Sau khi thành công, chạy lại `start.ps1` để backend migration và AI khởi động trở lại.
- Gói ZIP chuyển máy chỉ chứa `database.dump`, `manifest.json`, `TRANSFER.txt`, **không chứa `.env`, khóa bí mật hoặc file model/video**. ZIP phải giữ kín vì dữ liệu PostgreSQL chứa thông tin người dùng và sự kiện camera.
- Migration `0088_backup_scheduler_v0574.py` tiếp nối V0.5.73, chỉ cập nhật schema version, không sửa bảng dữ liệu. Danh mục backup lưu độc lập trong Docker volume **`traffic_ai_backup_data`**; PostgreSQL tiếp tục dùng `traffic_ai_postgres_data`.

### Kiểm tra & chạy trên Windows

Giải nén lên `D:\LienThongDH\DoAn\traffic-ai` sau khi đã lưu bản sao của `.env`, volume database và các thư mục dữ liệu hiện có. **Không chạy `docker compose down -v`**. Docker Desktop cần ở chế độ Linux containers và đang chạy.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Kiểm tra backup worker và volume:

```powershell
docker compose ps
docker compose logs --tail 80 backup-worker
docker volume inspect traffic_ai_postgres_data
docker volume inspect traffic_ai_backup_data
```

Khi mọi bài test và các thao tác sao lưu/thử khôi phục thực tế đã ổn định, phát hành:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\publish.ps1
```

Không chạy `create-admin.ps1`: tài khoản Admin hiện tại đã có.

### Di chuyển sang máy khác

1. Máy cũ: dừng các phiên AI đang chạy để có ảnh chụp trạng thái nhất quán cho cả dữ liệu file ngoài PostgreSQL; vào **Backup / Restore → Sao lưu ngay**. Chờ tác vụ *Hoàn thành*, bấm **Tải ZIP chuyển máy**.
2. Sao lưu riêng **`.env`** (chứa mật khẩu PostgreSQL và token nội bộ), `models/`, `videos/`, `snapshots/`, `datasets/`, `training-runs/`, `gateway/certs/` nếu cần. Tránh chia sẻ các file nhạy cảm qua kênh công khai. Không nên ghi đè `.env` của máy đích khi đã có DB khác mà không kiểm tra mật khẩu.
3. Máy mới: cài Docker Desktop Linux containers, chép source V0.5.74 và các thư mục cần thiết, cấu hình `.env` hợp lệ, chạy `start.ps1` để khởi tạo PostgreSQL 18 và người dùng Admin ban đầu trên máy đích (nếu hoàn toàn mới có thể cần quy trình bootstrap Admin hiện hành). Tài khoản từ nguồn sẽ được đưa sang khi restore.
4. Trên máy đích, đăng nhập Admin → **Backup / Restore → Nhập bản sao lưu** → chọn ZIP. Hệ thống kiểm tra cấu trúc và checksum; *chưa thay dữ liệu*. Sau đó chọn bản mới nhập, nhập đúng `KHOI PHUC traffic_ai_db` (hoặc tên DB đang cấu hình), xác nhận cảnh báo và chờ trạng thái *Hoàn thành*.
5. Chạy lại `start.ps1` để áp dụng Alembic sau khi chuyển database. Đăng nhập bằng tài khoản Admin/mật khẩu từ máy nguồn, kiểm tra Camera / GT / Benchmark / người dùng / các thư mục video & model.

**Cảnh báo:** khôi phục khi người dùng hoặc AI còn đang ghi dữ liệu có thể làm mất các thay đổi kể từ thời điểm backup. Cần tạm dừng AI, sao lưu máy đích trước khi restore, đảm bảo đủ dung lượng cho cả database tạm và database cũ. Không có bảo đảm zero-downtime. Nếu job restore thất bại **trước lúc swap**, dữ liệu DB đang hoạt động không bị thay thế. Nếu restore thành công, database cũ vẫn còn trong PostgreSQL và có thể được quản trị viên phục hồi thủ công sau khi dừng dịch vụ; không tự động xóa database cũ.

**Giới hạn:** web upload tối đa 1 GiB; nếu dữ liệu lớn hơn, phải chuyển bằng `pg_dump/pg_restore` hoặc nâng đồng bộ giới hạn gateway/API sau khi đánh giá dung lượng. Các tệp model/video không nằm trong PostgreSQL và phải chuyển riêng. Hệ thống này chưa được kiểm thử phục hồi thực tế với Docker Desktop Windows trong môi trường đóng gói, vì vậy cần diễn tập backup/restore trên máy thử trước khi dùng với dữ liệu quan trọng.

### Kết quả kiểm thử mã nguồn

- Backend **171/171**; AI Service **635/635**; Node frontend unit **4/4**; backup-worker riêng **4/4**.
- Python compileall chạy thành công. Backend/AI suite trong môi trường đóng gói dùng shim chỉ phục vụ kiểm thử cho dependency `httpx2` vì không có gói chính xác trong môi trường; shim **không có trong source ZIP**.
- Chưa thực hiện được Docker PostgreSQL restore tích hợp và `npm run build` vì môi trường này không có Docker Engine và NPM registry không phản hồi. Trên máy Windows, `test.ps1` chạy build / test với Docker và npm theo đúng dependency pin của source.

---

## Lịch sử V0.5.73 và các bản trước

# Traffic AI V0.5.73 — Unicode Accounts + Reliable Creation Feedback

## Nguyên nhân tài khoản không được tạo trong V0.5.72

Ở trang Admin, tên đăng nhập **`Đạt`** có chữ `Đ`, trong khi backend phiên bản cũ khai báo regex `^[A-Za-z0-9_.-]+$`; FastAPI trả HTTP **422** vì đầu vào không hợp lệ, không lưu `users`. Frontend chuyển cấu trúc lỗi `detail: [{...}]` thành chuỗi **`[object Object]`** rồi trình bày trong hộp thông báo chung màu xanh. Đây không phải thông báo tạo thành công. **Không cần tạo lại Admin**.

## Nâng cấp V0.5.73

1. **Tạo tài khoản Unicode tiếng Việt**: chấp nhận `Đạt`, `Nhiên`, `Phạm-Vĩnh.Đạt`, chữ số, `_`, `.`, `-`; không cho khoảng trắng, emoji, ký tự vô hình/điều khiển, ký tự đặc biệt. Username dài 3–80 ký tự; họ tên có thể dùng dấu và khoảng trắng bình thường.
2. **Chuẩn hóa đăng nhập NFC + Unicode casefold**, lưu khóa `users.username_key` có **UNIQUE index** ở PostgreSQL. Chống tài khoản trùng do chữ hoa/chữ thường hoặc dấu Unicode tổ hợp; tên hiển thị vẫn giữ nguyên. `Đạt` / `đạt` / `ĐẠT` cùng một định danh. Rate limit đăng nhập dùng cùng khóa chuẩn hóa; giữ Argon2id, RBAC, CSRF và session cookie.
3. **Thông báo thao tác chính xác**: kiểm tra tên đăng nhập ngay khi gõ, phân biệt lỗi (đỏ), thành công (xanh), cần kiểm tra lại (vàng). Trích xuất thông báo FastAPI 422 theo trường, không hiện `[object Object]` và không làm lộ mật khẩu.
4. **Lưu là phải hiển thị**: khi server trả HTTP 201 kèm `id` và `username`, giao diện đưa người dùng vừa tạo vào danh sách, xóa bộ lọc tìm kiếm, tô viền tài khoản mới và tải lại danh sách bằng `cache: no-store`. Nếu GET thất bại, vẫn giữ tài khoản đã được server xác nhận và báo rõ lỗi tải danh sách; nếu bị từ chối POST, không xóa form hoặc thông báo tạo thành công.
5. **Migration** `0087_unicode_usernames_v0573`: backfill `username_key` từ toàn bộ tài khoản đã tồn tại, tạo chỉ mục duy nhất, nâng schema version lên `0.5.73`. Có kiểm tra xung đột canonical để **dừng migration thay vì xóa/đè tài khoản**. Vẫn giữ toàn bộ người dùng, hash mật khẩu, GT, event và session; Postgres khởi động sẽ áp dụng Alembic tự động.
6. Thêm regression backend cho Unicode/tên trùng/đăng nhập/tính bền vững, kiểm thử Node cho thông báo lỗi và regex, thêm contract V0.5.73 vào `scripts/test.ps1`. Gói giữ toàn bộ source V0.5.72.

**Session #175 ngày 11/10/2026:** GT 149 / AI lưu 153 / khớp 139 / lọt 10 / dư 14 / F1 92,1%. Trace 23.650 frame cho thấy worker đề xuất 192 crossing. Chưa có GT + database events đầy đủ trong RAR nên **không chỉnh ngưỡng thuật toán AI trong V0.5.73**; tuyệt đối không coi bản này đạt 0 lọt / 0 dư. Hãy xuất ZIP **Tải hồ sơ benchmark** để xác minh đủ từng lượt.

### Cập nhật source và chạy đúng thứ tự (Windows PowerShell)

Giải nén **full source ZIP** vào `D:\LienThongDH\DoAn\traffic-ai`, giữ file `.env`, các model/video cá nhân và **PostgreSQL volume**; nên sao lưu database trước migration, tuyệt đối không xóa volume hoặc tạo lại Admin. Docker Desktop phải ở trạng thái Engine running. Sau đó:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

# Mở khóa toàn bộ script PowerShell
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Kiểm tra source
.\scripts\test.ps1

# Khởi động hệ thống (tự chạy migration)
.\scripts\start.ps1
```

Sau khi trình duyệt đã tải phiên bản V0.5.73 (**Ctrl + F5** nếu còn cache), vào **Quản lý người dùng & phân quyền**, tạo lại tài khoản **`Đạt`** nếu yêu cầu trước đó đã bị HTTP 422 (tức chưa hề được lưu). Thông báo thành công phải có `@Đạt` và mã số `#id`; kiểm tra ngay trong danh sách và thử đăng nhập bằng mật khẩu tạm để buộc đổi mật khẩu lần đầu.

Nếu cần đánh giá benchmark trước khi phát hành, xuất ZIP hồ sơ benchmark và chạy:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\check-benchmark.ps1 -ExportZip .\benchmark-latest.zip -MaxMissed 0 -MaxExtra 0
```

Chỉ khi `test.ps1`, khởi động và benchmark đều đạt yêu cầu mới phát hành bằng:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\publish.ps1
```

### Giới hạn kiểm tra

Backend 163/163, AI Service 635/635, frontend Node 4/4 và benchmark gate 5/5 đạt trong sandbox tương thích. **Chưa build Vite/NPM thực tế, chưa thử migration với PostgreSQL thực tế hoặc chạy GPU với video gốc.** Kiểm tra Docker / PostgreSQL / browser thực tế bằng `scripts/test.ps1` trên máy Windows trước khi publish. Xem `VERIFICATION.md`.

---

# Traffic AI V0.5.72 — Stable Replay + Benchmark Regression Gate

## Căn cứ từ Session #174 (camera_1 ngày 10/10/2026)

- **GT 149, AI database 149, khớp 135, lọt 14, dư 14, F1 90,6%**. Tổng GT = AI **không** đồng nghĩa với benchmark đúng.
- Trace 23.650 frame: worker đề xuất 195 crossing; backend tạo 149 event và từ chối 46 event (22 `same-track-direction-flip`, 19 `same-track-repeat-jitter`, 3 `crossing-signature`, 1 `secondary-shadow-signature`, 1 `direct-secondary-shadow`). Đây là **telemetry**, không phải căn cứ tự khôi phục các mốc GT.
- So sánh source gốc V0.5.70 với V0.5.71: `ai-service/app/counting.py`, `worker.py`, `tracking.py`, `async_tasks.py` và `backend/app/benchmarking.py` **giống hệt từng byte**. Không thể kết luận giao diện mật khẩu V0.5.71 gây thay đổi thuật toán đếm. Có thể còn các biến đầu vào khác (model/clip/GT/geometry/runtime), chưa có hồ sơ xuất GT/events để xác nhận.

## Những thay đổi thực sự trong V0.5.72

1. **Deterministic MP4 replay — stable track order**: trước khi xử lý continuation/đếm, sắp xếp những detection **đã được ByteTrack gán ID** theo `(raw_track_id, bounding box)`, tránh kế thừa thứ tự mảng từ YOLO/NMS vốn có thể khác giữa các lần chạy. Chỉ áp dụng cho phát lại video với `AI_VIDEO_DETERMINISTIC=1`; không thay ngưỡng vạch, ROI, cứu track, class refinement, cooldown, không bỏ xe hay thêm crossing và không làm chậm camera RTSP. Với CAR/TRUCK/BUS xung đột và confidence **bằng nhau**, dùng tie-break cố định để quyết định ô giữ lại.
2. **Benchmark release quality gate**: thêm `scripts/benchmark-gate.py` và `scripts/check-benchmark.ps1`; nhận **ZIP “Tải hồ sơ benchmark”** từ giao diện (có `report.json`, `ground-truth.json`, `events.json`, `manifest.json`). Xác thực SHA-256/size, GT hiện diện, integrity backend, phương trình `matched + missed = GT` và `matched + extra = AI`; **FAIL nếu số lọt/dư lớn hơn giới hạn**, kể cả khi GT = AI. Không sửa số liệu hay GT.
3. **So sánh baseline đã đo**: baseline JSON ghi kết quả thực tế; khi có baseline chỉ so sánh nếu GT/tolerance/clip geometry tương thích. Không tự gán 0 lọt/0 dư. Có thể thêm `-MaxWrongClass` để chặn sai loại xe.
4. **Migration V0.5.72**: `0086_replay_guard_v0572` tăng duy nhất `system_settings.schema_version`, không đổi bảng, dữ liệu GT, lịch sử event, tài khoản hay mật khẩu. Duy trì bảo mật Argon2id và tính năng tài khoản V0.5.71.

### Lệnh PowerShell mặc định sau mỗi bản build (không tạo lại Admin)

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

# Mở khóa toàn bộ PowerShell scripts
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Kiểm tra source — yêu cầu Docker Desktop đang chạy
.\scripts\test.ps1

# Khởi động hệ thống
.\scripts\start.ps1
```

### Kiểm tra chất lượng trước khi phát hành (bổ sung)

Trong Benchmark Report, chọn **Tải hồ sơ benchmark** sau khi AI hoàn tất phát lại và đã có đủ GT. Sao chép ZIP xuất ra thành `D:\LienThongDH\DoAn\traffic-ai\benchmark-latest.zip` (hoặc dùng đường dẫn thực tế), rồi **mở cửa sổ PowerShell khác**:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\check-benchmark.ps1 -ExportZip .\benchmark-latest.zip -MaxMissed 0 -MaxExtra 0
```

Ví dụ V0.5.71 GT/AI 149/149, khớp 135, lọt 14, dư 14: lệnh trên sẽ **FAIL đúng**, không công nhận chất lượng chỉ bằng số tổng. Sau khi benchmark đạt 0 lọt/0 dư và test/run ổn, phát hành:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\publish.ps1
```

Nếu cần đo baseline của một phiên trước, dùng `python -X utf8 .\scripts\benchmark-gate.py --export .\benchmark-latest.zip --max-missed 14 --max-extra 14 --write-baseline .\benchmark-baseline.json`. Baseline là dữ liệu đã đo, **không** làm thay đổi AI hay việc chấm điểm.

### Giới hạn kiểm chứng

- Có thể test thuần code qua trace + unit test, **không thể xác nhận mức 0 lọt / 0 dư** của V0.5.72 khi chưa có **GT + danh sách event database + clip gốc** cho cùng benchmark và chưa chạy inference GPU Windows. Gói `.rar` của Session #174 chứa ảnh và trace chứ không có bộ GT/event đầy đủ.
- Đợt này hướng vào tính ổn định/tính trung thực của kết quả, **không nới rescue** chỉ để tăng tổng số đếm vì có nguy cơ tăng false positive.
- Xem `VERIFICATION.md` để biết bài nào được test thực tế và giới hạn môi trường.

---

# Traffic AI V0.5.71 — Giao diện bảo mật dọc + Kiểm tra độ mạnh mật khẩu

## Các cải tiến

- **Tài khoản của tôi**: ô mật khẩu hiện tại, mật khẩu mới, xác nhận mật khẩu và nút đổi mật khẩu xếp theo **chiều dọc**, có chiều rộng hợp lý thay vì kéo ngang toàn màn hình.
- **Quản lý người dùng & phân quyền**: các trường tên đăng nhập, họ tên, vai trò, mật khẩu tạm, xác nhận mật khẩu tạm và nút tạo tài khoản theo bố cục một cột, đáp ứng cả desktop/mobile.
- **Hiện / ẩn mật khẩu ngay trong ô nhập** bằng nút biểu tượng mắt, hỗ trợ bàn phím và trợ năng. Áp dụng cho đăng nhập, đổi mật khẩu, tạo tài khoản và đặt lại mật khẩu.
- **Độ mạnh mật khẩu (ước tính)**: thanh chỉ báo Yếu / Trung bình / Mạnh, danh sách điều kiện có dấu kiểm ngay khi nhập. Trạng thái này là thông tin hỗ trợ, không phải phép đo an toàn tuyệt đối.
- **Quy tắc bắt buộc cho MẬT KHẨU MỚI**: 12–128 ký tự, tối đa 512 byte UTF-8, có đủ chữ hoa, chữ thường, số và ký tự đặc biệt (Unicode thuộc nhóm Letter Uppercase, Letter Lowercase, Decimal Digit, Punctuation/Symbol). Dấu cách không được coi là ký tự đặc biệt. Giao diện **và backend** cùng kiểm tra, kể cả khi gọi API trực tiếp. Mật khẩu hiện có không bị vô hiệu hóa khi nâng cấp; sẽ được kiểm tra quy tắc mới lúc người dùng đổi mật khẩu.
- Khi đổi, tạo hoặc reset mật khẩu, người dùng cần **nhập lại mật khẩu xác nhận** trước khi nút thực hiện được kích hoạt. Đặt lại mật khẩu không còn dùng `window.prompt` để nhập mật khẩu, thay bằng form bảo mật ngay trong trang quản lý.
- Tiếp tục băm **Argon2id** (không lưu plaintext), cookie HttpOnly/Secure, CSRF, RBAC và thu hồi phiên cũ sau khi đổi / đặt lại mật khẩu. Không thay thuật toán đếm xe, AI, GT hoặc benchmark.
- Alembic migration `0085_password_policy_v0571` chỉ cập nhật `system_settings.schema_version`; **không đổi cấu trúc bảng hay xóa dữ liệu**. Thêm ba bài kiểm thử hồi quy backend V0.5.71 và contract kiểm tra UI/API trong `scripts/test.ps1`.

## Nâng cấp và chạy trên Windows

Giải nén full source V0.5.71 vào thư mục dự án (giữ `.env` hiện có, dữ liệu PostgreSQL và các video/model cũ nếu đã có), sau đó chạy PowerShell:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\test.ps1
.\scripts\start.ps1
# Khi chạy ổn và đã kiểm tra trực tiếp trên trình duyệt:
.\scripts\publish.ps1
```

Nếu `start.ps1` báo lỗi xác thực PostgreSQL, tham khảo hướng dẫn V0.5.70 **ở bên dưới**; không xóa volume và không tự ý đặt lại mật khẩu database. Khi triển khai, frontend cần được **build lại** từ source để nhận giao diện mới; có thể dùng Ctrl+F5 để bỏ cache trình duyệt.

## Kiểm chứng được trong môi trường phát triển

- Backend: **160/160 tests passed** (bao gồm 3 bài kiểm thử quy tắc mới, API create/change/reset và khả năng đăng nhập với hash cũ).
- AI Service: **631/631 tests passed**; thuật toán AI không sửa đổi.
- Frontend: parse cú pháp JSX qua TypeScript thành công. **Chưa chạy được `npm run build`** trong sandbox vì không kết nối được `registry.npmjs.org`; `scripts/test.ps1` trên máy Windows có Docker sẽ cài dependency, audit và build frontend thật. Chưa thử nghiệm Docker/PowerShell, PostgreSQL thật hoặc UI tương tác bằng trình duyệt trên máy người dùng.

---

# Traffic AI V0.5.70 — PostgreSQL Credential Recovery + Fail-fast Startup

## Vì sao PostgreSQL healthy nhưng Backend không thể start?

Log từ máy Windows xác nhận `FATAL: password authentication failed for user "traffic_admin"` (SQLSTATE 28P01). Cơ sở dữ liệu cũ tồn tại trong `traffic_ai_postgres_data` và có mật khẩu role đã lưu; thay đổi `POSTGRES_PASSWORD` trong `.env` / Docker Compose **không tự đổi mật khẩu role trong database đã khởi tạo**. `pg_isready` có thể báo ready khi authentication của Backend vẫn sai. Không liên quan Argon2id password cho người dùng Dashboard.

### Nâng cấp V0.5.70

1. Chặn startup ngay sau PostgreSQL stage nếu kết nối TCP/SCRAM bằng `POSTGRES_PASSWORD` hiện tại không thành công. Không đợi Backend restart 30 lần rồi timeout 180 giây.
2. Nếu `.env` còn mật khẩu mẫu nhưng đã có named database volume, **không tự sinh secret mới** đè lên cấu hình đang cần khôi phục.
3. Thêm `scripts/repair-postgres-auth.ps1`: dùng `psql \password <role>` nhập mật khẩu ẩn hai lần, không gửi plaintext qua CLI, history, hoặc SQL command. Sau đó xác thực lại bằng TCP/SCRAM. Cần sao chép mật khẩu từ `.env` tại máy cục bộ; không gửi mật khẩu qua chat.
4. Backend thoát sớm, log lý do rõ ràng nếu PostgreSQL từ chối password. Không chỉnh sửa dữ liệu, volume hay bảo mật PostgreSQL; không tắt SCRAM.
5. Thêm bốn regression `test_v0570_*`, contract PowerShell và migration `0084_postgres_auth_guard_v0570` (chỉ tăng `schema_version`). Không đổi AI counting, Gate, benchmark, database event, user Argon2id hoặc RBAC.

### Khôi phục database hiện tại (không xóa dữ liệu)

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
notepad .env
# Xác nhận POSTGRES_PASSWORD có mật khẩu mạnh; KHÔNG chia sẻ giá trị.
# PostgreSQL cần đang chạy:
docker compose up -d --no-deps postgres
.\scripts\repair-postgres-auth.ps1
# Khi được hỏi, dán POSTGRES_PASSWORD từ .env hai lần (ẩn ký tự).
.\scripts\test.ps1
.\scripts\start.ps1
# Khi đã kiểm tra thật sự hoạt động:
.\scripts\publish.ps1
```

Nếu kết nối psql qua Unix socket bị từ chối, **không** chuyển `pg_hba.conf` sang `trust`. Dừng lại và dùng tài khoản DB có quyền truy cập hợp lệ để khôi phục. Lưu ý việc thay đổi mật khẩu role có thể làm các ứng dụng khác dùng chung role mất kết nối; cấu hình của chúng cũng cần đồng bộ.

---

# Traffic AI V0.5.69 - Bounded PostgreSQL/Backend startup diagnostics

V0.5.68 could appear stuck after Docker image build while Compose waited
for backend `service_healthy` for multiple minutes. V0.5.69 stages startup:
PostgreSQL -> Backend/Alembic -> AI Service (GPU with CPU fallback) ->
Frontend/Gateway. Each stage has a finite health timeout and prints logs
when it fails. The system will stop waiting and report the real migration,
connection or healthcheck error instead of silently waiting.

**Important:** A screenshot of `backend Waiting` does not establish why
Backend is unhealthy. This release fixes endless waiting/observability;
it does not claim to fix an unknown database migration error without logs.
The Backend entrypoint avoids unconditional `ALTER TABLE alembic_version` on every boot and sets PostgreSQL lock/statement limits for migration diagnostics.
No destructive DB commands are issued: existing `traffic_ai_postgres_data`
volume, `.env`, model files, camera event data and GT are kept.

Run in PowerShell:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
# If backend still cannot become healthy:
.\scripts\diagnose-startup.ps1
# After startup and functional tests pass:
.\scripts\publish.ps1
```

The old `create-admin.ps1` workflow remains unchanged. Version 0.5.69 is
consistent across Frontend, Backend and AI Service. Alembic head is
`0083_bounded_startup_v0569` (updates schema version only).

---

# Traffic AI V0.5.68 — Quản lý người dùng & bảo mật Argon2id

## Mới: đăng nhập, phân quyền và audit thực sự hoạt động

**Lưu ý khi nâng từ V0.5.67:** Sau khi cập nhật source và chạy `start.ps1`, mọi API/UI dữ liệu (ngoại trừ health) yêu cầu đăng nhập. Không có mật khẩu mặc định và không có API đăng ký công khai. Chạy `scripts/create-admin.ps1` **một lần** trên máy quản trị sau khi backend đã healthy. Database, GT, sự kiện, mô hình và AI counting được giữ nguyên; Alembic revision `0082_security_auth_v0568` bổ sung trường `users.role`, `must_change_password`, `last_login_at` và ba bảng `auth_sessions`, `login_limits`, `security_audit`.

### Mật khẩu: băm chứ không mã hóa có thể giải ngược

Sử dụng **Argon2id** thông qua argon2-cffi 25.1.0, cấu hình `m=65536 KiB (64 MiB), t=3, p=2`, salt 16 byte riêng từng tài khoản, output 32 byte. Không ghi mật khẩu plaintext vào PostgreSQL/log và không cung cấp chức năng giải mã. Yêu cầu 12–128 ký tự, có chữ và số, tối đa 512 byte UTF-8; check_needs_rehash cho các hash Argon2id cũ. Quy tắc này đáp ứng mức tối thiểu Argon2id khuyến nghị trong OWASP Password Storage Cheat Sheet; không khẳng định mật khẩu yếu sẽ được bảo vệ tuyệt đối.

### Kiến trúc xác thực

- Session token ngẫu nhiên 256-bit, chỉ lưu SHA-256(token) trong `auth_sessions`; cookie `__Host-traffic_ai_session` có **Secure, HttpOnly, SameSite=Strict, Path=/** và hạn 8 giờ; không sử dụng localStorage, không JWT lưu client. Có thu hồi phiên khi logout, đổi mật khẩu, khóa tài khoản, thay vai trò, hoặc reset mật khẩu.
- CSRF token ràng buộc phiên, backend chỉ lưu SHA-256 của token đó. Mọi POST/PUT/PATCH/DELETE đã đăng nhập cần `X-CSRF-Token` và `Origin` phải trùng origin HTTPS hiện tại. Frontend `secureFetch` tự gắn header. Từ chối request thay đổi trạng thái thiếu token hoặc sai Origin.
- Khóa thử đăng nhập sai sau 5 lần trong 15 phút theo IP và tên tài khoản; phản hồi sai mật khẩu không tiết lộ tên tồn tại; phiên cookie không lưu plaintext trong DB.
- Auth middleware mặc định từ chối mọi `/api/*` chưa đăng nhập (trừ `/api/health` phục vụ Docker và `/api/auth/login`). `/api/internal/*` vẫn phải qua token AI riêng, nhưng **gateway không cho public gọi**. Video browser `/ai/streams/*` cần session hợp lệ; `/ai/media/video` còn cần Operator/Admin; các endpoint AI khác bị chặn tại Nginx.
- Nginx bật TLS, HSTS, CSP hạn chế script-origin, X-Frame-Options DENY, Referrer-Policy, nosniff. PostgreSQL chỉ bind **127.0.0.1:5445** ở host, không công khai trên LAN. Môi trường mới tự sinh mật khẩu PostgreSQL ngẫu nhiên từ template; **mật khẩu PostgreSQL đã tồn tại không tự đổi** để tránh làm mất kết nối với volume dữ liệu cũ. Nếu `.env` cũ vẫn dùng mật khẩu ví dụ, người quản trị nên chủ động đổi trong PostgreSQL và `.env` sau khi sao lưu. `.env` cũ có AI_SHARED_TOKEN ví dụ công khai sẽ được `start.ps1` thay bằng chuỗi ngẫu nhiên; các secret do người dùng tự đặt được giữ nguyên.

### Vai trò và hành vi

| Vai trò | Xem Dashboard/benchmark | Thay đổi camera, AI, GT, dataset, training | Tạo/khóa/sửa user và xem audit |
|---|---|---|---|
| Admin | Có | Có | Có |
| Operator | Có | Có | Không |
| Viewer | Có, chỉ đọc | Không | Không |

Viewer không nhận RTSP source URL từ `/api/cameras`, `/api/sessions` và benchmark JSON (trường `source_url` được che thành `restricted`); endpoint benchmark ZIP export, source inspection và raw ảnh dataset cần Operator trở lên. Các quyền được kiểm tra **tại backend**, không dựa vào ẩn nút UI. Admin không thể tự khóa hoặc tự hạ vai trò; hệ thống từ chối xóa quyền của Admin cuối cùng. Các thao tác đã xác thực (ngoại trừ reads) có audit action/path/HTTP outcome, không lưu body, mật khẩu hoặc query string; audit nhạy cảm (`users.*`, `auth.*`) ghi trong giao dịch. Với thao tác thông thường, audit sau response là best-effort nếu DB bị sự cố — xem giới hạn bên dưới.

### Khởi tạo Admin đầu tiên — không có tài khoản/mật khẩu cố định

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1

# Chạy trên máy chủ quản trị sau khi backend đã healthy.
# Mật khẩu được nhập ẩn, xác nhận 2 lần.
.\scripts\create-admin.ps1
```

Mở `https://traffic-ai.test:8443` và đăng nhập. Khi Admin tạo user mới, tài khoản phải **đổi mật khẩu tạm ngay lần đăng nhập đầu tiên**. Trên sidebar có **Tài khoản** (mọi vai trò) và **Người dùng** (chỉ Admin). Trong Người dùng: tạo user, tìm kiếm, sửa họ tên, phân vai, khóa/mở, reset mật khẩu, thu hồi phiên và xem nhật ký. Trong Tài khoản: tự đổi mật khẩu hoặc đăng xuất tất cả thiết bị. Mỗi lần đổi/reset mật khẩu hoặc đổi vai trò sẽ thu hồi toàn bộ session của user đó.

Sau khi chạy thử ổn, phát hành với **một lệnh**:

```powershell
.\scripts\publish.ps1
```

Tự động dùng `VERSION=0.5.68` tạo tag `v0.5.68` và GitHub Release. Nếu nâng cấp vào cài đặt cũ có user nhưng chưa có Admin, **không cấp Admin tự động**; thực hiện `create-admin.ps1`. Không upload `.env`, `gateway/certs/*.key`, database hoặc model weights vào ZIP/GitHub.

### Bảo mật và giới hạn đã biết

Argon2id dùng băm một chiều, không phải mã hóa đảo ngược. Chưa triển khai WebAuthn/passkeys hoặc MFA/TOTP, chưa có SIEM/tamper-proof external audit, chưa có ký riêng mỗi record audit; không gọi đây là bảo mật tuyệt đối. Logout/revocation kiểm tra trong PostgreSQL cho mỗi request. CSRF dựa vào cùng origin, nhưng phòng chống XSS cũng quan trọng. Kiểm thử thực tế hệ thống dùng Docker/PowerShell, cookies Nginx và chức năng video trên máy Windows vẫn cần thực hiện sau cài đặt. Không thay chính sách benchmark/GT và không khẳng định Recall/F1 cải thiện trong V0.5.68.

Tham khảo OWASP: <https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html> và <https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html>.

---

## Lịch sử phiên bản trước

# Traffic AI — lịch sử V0.5.67: Chẩn đoán cạnh tranh GT ↔ AI theo timecode

Nâng cấp trực tiếp từ **V0.5.66** do người dùng tải lên. Bản này bổ sung trạng thái sẵn sàng benchmark và giữ bản sửa van chở hàng thành **Xe tải**. Đơn vị đếm là lượt cắt vạch; một xe quay lại cắt vạch lần nữa được tính thêm một lượt.

## Nâng cấp V0.5.67 — giải thích "GT = AI nhưng vẫn có lọt/dư"

Ảnh benchmark #49/session #172: **GT 149, AI 149, khớp 135, lọt 14, dư 14, F1 90,6%, class đúng 98,5%**. Đây **không phải hồi quy mới so với benchmark #46/session #169 ở ảnh V0.5.63**: cả hai ảnh đều có 135/14/14. Tổng 149 bằng nhau chỉ là sai số số lượng bằng 0; báo cáo dùng global timestamp matching một-một trong cửa sổ ±0,75 giây nên có thể tồn tại GT không ghép và AI chưa ghép cùng lúc.

Trace trong `camera_1(20261009-124508).rar` có 23.650 observation frames, 195 event-delivery receipts: **149 created, 46 deduplicated**, drain thành công. Ví dụ mốc GT OUT 01:09.457 có event thực **69.4566 giây, track 20863, backend_event_id 10275, outcome created**. Nếu GT này vẫn hiện là chưa ghép, cần xem *AI event đã được sử dụng trong GT nào*, không được coi đây là bằng chứng AI không đếm.

**Backend `temporal_assignment_audit`:** báo cáo bổ sung số GT chưa ghép có event DB gần đó nhưng *đã gán cho GT khác*; số GT không có event DB trong cửa sổ; số AI chưa ghép có GT gần đó nhưng *đã gán AI khác*. Các record evidence kèm ID, chênh lệch thời gian, hướng và `identity_proven: false`. Tối đa 4 cạnh tranh gần nhất mỗi mục, tránh payload lớn.

**Giao diện:** Khi GT tổng bằng AI tổng mà vẫn có miss/FP, hiển thị giải thích cạnh tranh timecode và cảnh báo chỉ số GT chưa ghép không luôn đồng nghĩa xe thật bị AI bỏ sót. Từng thẻ mốc có chú thích phân biệt event đã được ghép GT khác hay hoàn toàn không có event DB trong cửa sổ. Điều chỉnh line-height/overflow để chữ không đè nhau.

**Bất biến quan trọng:** Không tự đổi GT, loại xe, hướng, timecode, tolerance, thuật toán ghép, event hoặc F1. Bản này **cải thiện tính minh bạch chẩn đoán**, không tự nhận tăng độ chính xác đếm. Muốn sửa chính xác 14 cặp vật lý cần ZIP **Tải hồ sơ benchmark** của đúng benchmark #49 (chứa toàn bộ `ground-truth.json`, `events.json`, `report.json`, manifest + trace). Chỉ RAR ảnh/trace không đủ quan hệ GT ↔ event để kết luận 14 pair đều là lỗi AI.

Riêng mốc GT 10:41.981 "Ô tô" nhưng AI "Xe tải" cần kiểm tra lại quy ước xe van chở hàng: V0.5.65/V0.5.66 đã chủ ý giữ nhãn TRUCK theo yêu cầu trước; không tự đổi Ground Truth thành xe tải.

## Kiểm thử V0.5.67

Đã chạy 140 backend + 631 AI pytest pass trong sandbox với SQLite memory và shim test-only `httpx2→httpx` do môi trường thiếu `httpx2`. Đã có 5 regression mới cho trường hợp tổng bằng nhau mà không match, GT cạnh tranh một AI, AI gần GT đã ghép, hướng sai không thay điểm và GT trống không chấm. Chưa chạy Docker/GPU/PowerShell/Vite đầy đủ trong sandbox; sau khi tải ZIP phải chạy `scripts/test.ps1` trên Windows trước khi publish.

## Vấn đề trong kết quả mới

Ảnh và trace V0.5.65, session 171 cho thấy 149 lượt được lưu: 146 xe máy, 1 xe đạp, 2 xe tải; IN 68 / OUT 81. Worker đề xuất 195 lượt, backend gộp 46, Human Guard loại 30. Có 195 terminal receipts, 149 created + 46 deduplicated; drain hoàn tất và pending/dropped đều 0.

Hai lượt van trước đây bị ghi thành Ô tô nay được lưu **TRUCK**:

| Lượt | Canonical | Source / observed frame | Backend event |
|---|---:|---:|---:|
| OUT10:41.931 (641.9311s) | 254023 | 16049 /16050 | 10212 |
| IN14:42.290 (882.2898s) | −22 | 22058 /22059 | 10254 |

Đây là kết quả người dùng đã chạy trên .65, không phải model replay của .66 trong môi trường kiểm tra. So với session 170, 195 receipts giữ tracking/time/frame/direction/method/geometry/outcome; hai class CAR đổi thành TRUCK, confidence IN lấy từ truck lock. Không dùng hai canonical để khẳng định danh tính cùng một xe vật lý.

**Benchmark #48 chưa có GT:** ảnh hiển thị GT 0 / AI 149 và có nút sao chép 149 GT từ benchmark #47. F1 = 0% / 149 đếm dư ở màn hình cũ chưa phải đánh giá hợp lệ về chất lượng AI. Không có GT/event assignment export của phiên mới để kết luận Recall/F1/class accuracy.

## Chức năng mới

### GT trống có trạng thái chuẩn bị riêng

Khi chưa có mốc Ground Truth, báo cáo hiển thị **Chưa có Ground Truth**. Vẫn xem được tổng AI, số AI theo loại xe, Integrity và tải hồ sơ benchmark. Khớp/lọt/dư/sai số/Recall/Precision/F1/class đúng hiển thị dấu **—**; không liệt kê 149 AI là 149 xe đếm dư hoặc gán nguyên nhân nội suy/rescue cho GT trống.

Thông báo hướng dẫn sao chép GT từ benchmark tương thích nếu có, với source/target ID và số GT rõ ràng, hoặc xem clip để đánh dấu. Việc sao chép dùng nút hiện có và yêu cầu bạn bấm; hệ thống không tự tạo hoặc sửa GT từ AI events. Nút Đối chiếu lại chỉ dùng khi benchmark có GT; Tải hồ sơ benchmark vẫn dùng được khi GT = 0.

Có GT nhưng AI = 0 vẫn là một báo cáo được chấm: xe GT chưa ghép là xe lọt, Recall/Precision/F1 bằng 0. Đây là trường hợp khác với thiếu GT. Có mốc GT chỉ xác nhận dữ liệu chấm đã tồn tại, không chứng minh người dùng đã đánh dấu đầy đủ toàn clip.

Hiện chưa có trường xác nhận riêng cho một clip đã được kiểm chứng không có xe. Vì vậy GT = 0 / AI = 0 cũng là chưa có dữ liệu chấm, không tự nhận điểm 100%.

### API và export thống nhất

GET /api/benchmarks/{id}/report và POST /api/benchmarks/{id}/reconcile có thêm:

```json
{"report_readiness":{"status":"needs_ground_truth","scoring_available":false,"reason":"no_ground_truth"}}
```

Với GT>0: status="ready", scoring_available=true, reason=null; trường ready bên ngoài thống nhất với scoring_available, kể cả AI0. Các field cũ của báo cáo có GT giữ nguyên, gồm global temporal matching, tolerance, missed matching audit và diagnostics.

Với GT0, các score/count-error fields là JSON null, các danh sách assignment/missed/false-positive/class-mismatch rỗng. ground_truth_total, ai_total, số GT/AI trong per_class và per_direction vẫn là counts thực; difference/correct_matches chưa chấm lànull. report.json xuất trong hồ sơ giữ đúng trạng thái này, còn events.json vẫn giữ AI events để review.

Client ngoài giao diện cần đọc report_readiness.scoring_available trước khi tính hoặc định dạng điểm; không chuyểnnull thành0%. Giao diện vẫn xử lý báo cáo API cũ qua ground_truth_total, không dùng ready cũ để loại bỏ trường hợp AI0.

## Giữ các chức năng đã nâng cấp

Giữ domain corroboration khi muốn đổi TRUCK semantic lock đang sống thành CAR: hai CAR wins theo source clock và ngưỡng hiện có, đồng thời đủ domain CAR proof; generic CAR đơn độc không tự vượt truck lock. Giữ deterministic all-frame crossing admission, source frame/time của event, refiner budgets/caches, terminal receipts và delivery drain.

Gate/Road Zone/cooldown, tracking, Human Guard, backend dedup, global temporal assignment và tolerance không đổi. Giữ matching audit tối đa4 event đã ghép, disclosure stack tránh chồng chữ và dashboard/GT–Report50/50. Không đổi model weights hoặc taxonomy để làm đẹp score.

## Chạy trên Windows

Giải nén toàn bộ ZIP và chép source vào thư mục dự án hiện tại. Chạy PowerShell:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.67 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443 và **Ctrl+F5**. Với benchmark48, bấm sao chép149GT từ **benchmark47** nếu clip/vạch tương thích. Review GT van quanh10:41.93OUT và14:42.29IN theo quy ước van chở hàng là Xe tải; giữ timecode/hướng theo clip đã kiểm tra. Đối chiếu lại rồi Tải hồ sơ benchmark để có cả GT và AI assignments cho lần phân tích tiếp theo.

Publisher lấy version từ VERSION, kiểm tra source trước khi commit/push/tag và tạo Release. Không force hoặc viết lại tag cũ. Muốn publish cần Git/GitHub CLI, tài khoản đã đăng nhập và quyền vào repository. Lệnh trên thực hiện xuất bản khi bạn chạy; quá trình kiểm tra bản này chỉ dùng Git cục bộ, chưa push hoặc tạo Release thật.

## Phiên bản công nghệ và kiểm tra

VERSION/frontend/API health/start message đồng bộ0.5.67. Alembic head 0081_temporal_audit_v0567, parent 0080_benchmark_ready_v0566; migration chỉ cập nhật schema_version0.5.67, downgrade về0.5.66, không thay GT/events/schema.

Docker/CI/packageManager giữ npm12.2.0 và Node26.10.0. npm12.2.0 được đối chiếu [official npm CLI latest](https://github.com/npm/cli/releases/latest) ngày09/10/2026. PowerShell scripts UTF-8 no-BOM/CRLF; source/config text khác LF.

Kết quả cụ thể và phạm vi thực thi nằm trong **VERIFICATION.md**. Offline assertions dùng algorithm modules thực và worker/backend helper trích AST; frontend kiểm bằng Babel/Node VM và JSX có kiểm soát. Môi trường hiện tại không chạy full dependency-pinned pytest, HTTP/ORM/database, native PowerShell, Docker, Vite/browser/GPU/model replay. Không có F1/class accuracy .66 được đo từ clip.
