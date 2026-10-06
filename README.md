# Traffic AI V0.5.61 — Span clock + fresh class closure

Nâng cấp từ full source V0.5.60. Đơn vị đếm là **lượt cắt vạch**: cùng phương tiện quay lại và cắt vạch lần nữa được tính thêm một lượt.

## Benchmark đầu vào V0.5.60

Screenshot mới: session166 / benchmark43, sao chép149 GT từ benchmark42.

| Chỉ số | V0.5.60 |
|---|---:|
| Ground truth | 149 |
| AI đếm | 149 |
| Khớp | 134 |
| Lọt không đếm | 15 |
| Đếm dư | 15 |
| Recall / Precision / F1 | 89.9% / 89.9% / 89.9% |
| Class đúng | 98.5% |
| Sai loại | 2 |
| IN / OUT cuối | 70 / 79 |

Integrity OK: worker đề xuất196, backend gộp47, DB149 event có timecode. Nhóm lọt nổi bật gồm **7 anchor đã băng qua vạch nhưng Gate chưa đóng event**, 2 crossing thiếu xác nhận phía sau vạch, 2 cooldown, 1 center qua nhưng motion-leading anchor chưa đủ span, 1 track sát vạch chưa span hai phía, 1 Human Guard loại nhầm và 1 Road Zone loại. Nhóm dư nổi bật gồm 5 gap-rescue, 5 direct, 2 interpolation và 3 event sát GT đã khớp/cùng điểm cắt.

RAR phiên166 có **195 JPG + 1 `session_166_benchmark-trace.jsonl`**, trace raw **194,016,680 byte**. Trace xác nhận tại vùng GT `10:41.981 OUT · Ô tô`, track254023 có hai target-aware GENERAL opinions CAR liên tiếp ở frame16049/16050 với confidence ~0.839/~0.859 nhưng event vẫn bị TRUCK semantic lock giữ. Với GT bicycle `04:49.450`, trace chưa chứng minh đúng bicycle target đã được track ở gate, vì vậy V0.5.61 **không hạ bicycle veto/threshold toàn cục**.

**Chưa replay V0.5.61.** Các thay đổi dưới đây được thiết kế từ trace phiên166 nhưng không được mô tả như đã tăng F1/Recall/Precision. Giữ GT timestamps/class, matching window0.75s, finite gate, Road Zone, cooldown, confidence, dedup và benchmark scoring.

## Thay đổi V0.5.61

### 1. Anchor Span Clock Reconciliation — sửa timecode mà không tự tạo event

Một finite anchor span đã vượt vạch thật nhưng hết cửa sổ post-confirm trước khi primary Gate đóng event có thể giữ lại **chỉ crossing clock**, không giữ quyền đếm. Hint chỉ tồn tại trong cửa sổ ngắn, cùng canonical track + cùng direction, và phải đạt normal-motion/side-depth mạnh hơn mức pending cơ bản; same-direction candidate, approach repair hoặc span có opposite observation đều bị loại.

Khi primary Gate sau đó **tự chấp nhận** event, worker có thể dùng crossing frame đã đo trước đó để timestamp event. Cơ chế này không mở Gate, không tăng tổng lượt, không biến pending hết hạn thành crossing và không thay matching algorithm. Mục tiêu là giảm cặp “lọt + dư” do cùng xe được đóng event muộn hơn timecode vật lý.

### 2. Fresh CAR Crossing Override — hai frame CAR mới có thể thắng TRUCK lock tại đúng crossing

V0.5.61 thêm `recent_four_wheel_wins()`: chỉ nhìn cửa sổ rất ngắn, đếm theo **distinct source frame**, yêu cầu CAR >=0.80 và thắng BUS/TRUCK trên chính frame đó. Crossing-only override yêu cầu ít nhất2 frame CAR mới liên tiếp và frame mới nhất chính là crossing frame.

Override này chỉ đổi **class của event crossing** từ TRUCK→CAR khi bằng chứng mới đủ mạnh; không xóa semantic lock toàn cục, không giảm truck thresholds và không cho một frame CAR đơn lẻ thắng lock. Thiết kế trực tiếp nhắm vào evidence của track254023 ở 10:41.981; cần replay V0.5.61 để xác nhận sai loại thực tế giảm từ2 xuống1.

### 3. Telemetry và regression

Dashboard/trace có thêm `Span clock` và `Truck lock→car`. Thêm regression cho trusted direct timestamp, hint hết hạn/không mở crossing, fresh CAR hai frame và heavy competitor veto. Camera Preview / Vehicle Count và GT / Report giữ bố cục 50/50.

## Thay đổi V0.5.60

### Stop 200 legacy không còn làm backend trả 502 giả

Log thực tế cho thấy `test_v0554_stale_stop_preserves_newer_active_camera` thất bại vì mock/legacy acknowledgment chỉ có `status_code=200`, còn V0.5.59 gọi bắt buộc `response.json()`. Route stop nay chỉ đọc payload khi response có `json()` callable. Vì vậy acknowledgment 200 kiểu cũ vẫn được xử lý như không có AI state; session/camera tiếp tục theo ownership guard hiện có thay vì phát sinh 502 do `AttributeError`.

Khi response có `json()`, validation mới của V0.5.59 vẫn giữ nguyên: payload phải là object; payload list/string hoặc JSON lỗi vẫn trả 502. Semantics `draining`, `pending_events`, đúng camera/session, `db.refresh(session)` và latest-owner guard không bị nới.

Đã thêm 2 regression V0.5.60 cho acknowledgment 200 không có `json()` và cho payload JSON không phải object. Không thay matching window, GT, finite gate, Road Zone, cooldown, confidence, class/refiner, dedup hoặc counting thresholds.

## Thay đổi V0.5.59

### Ghép raw ID không chiếm identity của xe khác

Ảnh và trace xác nhận hai xe cùng hiện diện: rider trước của canonical328328 đã đi lên phía trên, nhưng f18860 raw331821 của xe phía dưới được stitched sang328328. Center từ(922.803,212.580) tại f18857 sang(927,390.075), lệch ngược hướng lớn; heading đổi xuống và anchor xuống453.141. Đây là **ghép hai đối tượng khác nhau**, không đủ để quy mọi dao động sau đó hoặc17 event dư vào lỗi này.

Resolver nay nhận bbox thực từ worker. Chỉ khi gán raw ID mới cho xe hai bánh, prior velocity đã đạt ngưỡng heading1.5 và hai bbox có dữ liệu, mới kiểm tra chuyển động ngược hướng. Candidate bị loại khi reverse travel vượt cả expected travel theo gap, half-diagonal của hai bbox và1.5×gap. Bbox uncertainty giữ fragment thật có center lệch nhỏ; f18872 fragment của xe sau vẫn được gộp. Cùng raw ID đảo chiều, giảm tốc, slow-reversal certificate .58 và four-wheel perspective stitching giữ nguyên. Legacy caller không truyền bbox giữ API cũ.

Repro source thực f18860: .58 trả328328/stitchedTrue; .59 trả331821/stitchedFalse và không đổi heading rider trước. Có74/1275 known stitch trong trace thỏa rejection predicate, **không phải74 stitch đã chứng minh sai hoặc dự đoán tổng đếm .59**. Xe thật đảo chiều mạnh đồng thời đổi raw ID có thể bắt đầu canonical mới; cần replay đánh giá tradeoff. Bbox/heading dao động của fragment cùng xe vẫn cần kiểm tra riêng.

### Truck lock dùng frame primary thật

24 truck observations cuối ở frame100 có thể tiếp tục chiếm smoother history khi frame101–125 chỉ có car. Trước đây stabletruck gia hạn lock tới121 dù frame truck thật cuối là100. Nay worker lấy source clock primary truck từ smoother; primary/refiner phải còn trong TTL, không có future clock, và lock lấy bằng chứng qualified mới nhất. Không thay confidence hoặc taxonomy; caller legacy không có clock giữ tương thích.

Trace actual289.45s cho thấy GT bicycle chưa được track ở gate. Context target105044 tại f7243 là **motorcycle khác**, domain/general bicycle0 và generalMC.823; veto không phải từ crop của GT bicycle. Canonical110070 xuất hiện đầu f7273/t290.88s, đã downstream; bicycle display xuất hiện sau đó. Không giảm veto để sửa nhầm target. Van254023 thiếu ordinary opinion trong trace .58 nên chưa kết luận primary/refiner gây nhãn truck hoặc đã sửa GTcar641.981.

Trace mới bổ sung audit class cho inference thật, giới hạn theo budget; cache/stale không tạo observation mới. Lưu target rect, domain/general opinion hoặcNone, consensus clock/TTL, primary/stable label/confidence/hits và read-only override/truck-lock clocks. Metadata không tăng model calls, counters, tuổi lock hoặc thay kết quả class.

### Phiên hoàn tất sau accepted event và callback cuối

Queue rỗng không có nghĩa HTTP event đang gửi đã xong. Repro .58: finish đến trước event, tổng final0 nhưng DB nhận1 sau đó. Dispatcher nay đóng admission nguyên tử, tính pending bằng unfinished jobs gồm in-flight, và flush chỉ báo hoàn tất khi thread đã kết thúc cùng unfinished=0. Bounded timeout trảFalse; worker chờ mọi event đã nhận kết thúc retry trước session finish. Giữ5 attempts, timeout4s, backoff, source frame/time và dedup. Retry hết vẫn là terminal failure, không giả lập đã persist.

Worker vào `draining` từ đầu shutdown. Registry stop trả sớm sau join1s; backend giữ DB session running/camera active khi phản hồi chưa terminal hoặc sai owner. Public registry get/list tiếp tục báo draining khi thread còn gửi finish RPC, giữ terminal gốc cho payload; callback cuối mới mở phiên mới. Frontend khóa restart/geometry trong giai đoạn này, hiển thị pending; stop-and-apply giữ proposal và không PATCH sớm. Phiên có thể chờ lâu hơn khi backend lỗi vì cần kết thúc các retry đã nhận.

### Trace lớn vẫn xuất nguyên vẹn, chẩn đoán dùng ít RAM

Trace thực134.1MiB vượt cap raw128MiB. Gzip streaming sau writer đóng cho file **15,113,380byte**, giải nén khớp từng byte nguồn/SHA256. Artifact và certificate công bố nguyên tử, gồm raw/gzip bytes/hashes cùng stat signatures; gzip lỗi là warning riêng và raw camera trace vẫn dùng được.

Diagnosis đọc streaming hai lượt, giữ counter/geometry extrema và tối đa8 context identities mỗi cửa sổ, rồi cập nhật outcome muộn của chính các identity đó. Duplicate windows dùng chung aggregation. Trên trace thật với149 **mốc yêu cầu kiểm tra** (không phải toàn bộ GT đã export): kết quả JSON khớp hoàn toàn với .58; thời gian6.943→2.104s, peakRSS618,740→13,292KiB. 5000 mốc riêng hoàn tất3.821s/63,104KiB; chỉ là phép đo subprocess tại môi trường kiểm tra, không phải SLA cho GPU service/browser.

Header geometry audit-only được ghi sau frame thật đầu tiên, có canonical line/Road cùng processed/source dimensions; không tạo frame giả. Source event clocks, reason ranking, count thresholds và raw diagnosis API giữ tương thích. Các source contract PowerShell .55 được cập nhật để kiểm tra final context refresh mới, không giữ regex của implementation đã bỏ.

## Hồ sơ benchmark để phân tích lần tiếp theo

Nút **Tải hồ sơ benchmark** trong Report tải `traffic-ai-benchmark-<id>-session-<id>.zip` gồm:

| File | Nội dung |
|---|---|
| manifest.json | ID, thời điểm export, hash/size từng file và trạng thái trace |
| report.json | Báo cáo từ cùng danh sách GT/event được export |
| ground-truth.json | Mốc GT, class, hướng và timecode |
| events.json | Event DB, track, source time/frame và crossing method |
| session.json | Metadata phiên được chọn lọc |
| config.json | Geometry/tolerance benchmark; camera hiện tại ghi riêng |
| benchmark-trace.jsonl.gz | Trace đóng thành công, nén nguyên vẹn và có hash nguồn/gzip |
| benchmark-trace.jsonl | Fallback trace raw từ AI service cũ, nếu <=128MiB |

API: `GET /api/benchmarks/{id}/export`; AI có `/benchmark-traces/{session_id}/download-gzip` cho trace có certificate đóng hợp lệ và `/download` raw tương thích. Backend ưu tiên gzip, fallback raw khi service cũ trả404. Giữ **128MiB cho representation truyền qua HTTP** và deadline20s; backend không giải nén trace vào RAM. Content-Encoding phải identity để không bị HTTP client tự inflate. Manifest có encoding, số byte/hash của nguồn và gzip; hash gzip được kiểm tra với bytes nhận được. Gzip source đã đóng phải còn đúng stat signature; file thay đổi/ghi tiếp hoặc artifact/certificate lỗi không được coi là trace hoàn tất.

Nếu trace thiếu/quá lớn/timeout/không hợp lệ, manifest ghi rõ và report ZIP vẫn tải được; không cắt trace hoặc tạo điểm quan sát giả. Tải sau khi phiên hoàn tất. JSONL raw trong thư mục camera và endpoint raw giữ nguyên; gzip canonical giúp **Tải hồ sơ benchmark** bao gồm file phiên163 thực tế lớn hơn128MiB mà không tăng cap.

URL metadata bỏ user/password/query/fragment; video chỉ giữ tên. Không lấy environment/settings, model paths hay video/model weights. Header geometry mới là cấu hình worker thực dùng, ở đúng kích thước frame đã xử lý; camera hiện tại ghi riêng và không thay thế geometry lịch sử. Trace mới có primary/stable class, override/lock source clocks và ordinary domain/general opinions theo target. Những audit class này nằm trong **raw/gzip trace**; diagnosis API và reason ranking cũ giữ kết quả tương thích.

Gửi ZIP hồ sơ cùng screenshot. Khi nén thư mục ảnh camera, giữ `session_<id>_benchmark-trace.jsonl`; chỉ JPG không cung cấp đầy đủ event/track/source-clock provenance.

## Version, môi trường và database

| Thành phần | Giá trị |
|---|---|
| VERSION / Frontend / Backend / AI Service | 0.5.61 |
| Alembic head | `0075_span_clock_class_v0561` |
| Parent | `0074_stop_ack_compat_v0560` |
| schema_version | 0.5.61 |
| npm trong Docker / CI / packageManager | 12.2.0 |
| Node.js trong Docker / CI | 26.10.0 |

npm12.2.0 đã đối chiếu [npm CLI latest](https://github.com/npm/cli/releases/latest) ngày05/10/2026; giữ Node26.10.0 theo cấu hình hiện có. Giữ quy trình publish test→commit→push→tag→Release. Migration 0075 chỉ cập nhật schema version, giữ dữ liệu/GT. Camera Preview/Vehicle Count và GT/Report giữ bố cục 50/50. V0.5.61 đã chạy **644 pytest cases: 528 AI + 116 backend, 0 lỗi** trong môi trường đóng gói với test-only shim `httpx2 -> httpx`; giới hạn và cấu hình kiểm thử được ghi rõ trong `VERIFICATION.md`.

## Đầy đủ lệnh test, start và tự động publish

Giải nén full source vào thư mục dự án; giữ `.env`, video, model weights và dữ liệu đang dùng. Cần Docker Desktop chạy; cần Git/GitHub CLI cho publish và checkout nhánh `main`.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Kiểm tra
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push, tạo tag và GitHub Release
.\scripts\publish.ps1
```

Mở **https://traffic-ai.test:8443**, nhấn `Ctrl + F5`. Chạy lại đúng clip, cùng vạch/Road Zone; tạo benchmark cho session mới, sao chép GT 149 từ benchmark tương thích và bấm **Đối chiếu lại**. Sau đó bấm **Tải hồ sơ benchmark** để lấy ZIP dùng cho lần phân tích tiếp theo.

Nếu chưa đăng nhập GitHub CLI, chạy một lần:

```powershell
gh auth login
gh auth setup-git
```

Nếu chưa cấu hình Git author, đặt `git config --global user.name` và `git config --global user.email` bằng thông tin của bạn.

Publish tự đọc VERSION để tạo tag **v0.5.61**, mặc định repository `TamNhien/traffic-ai`. Script kiểm thử source đã chuẩn hóa, commit/push/tag, chờ đúng Actions run theo tag/SHA/push và tạo Release có ZIP, TAR.GZ, README, SHA256SUMS. Fallback CLI bổ sung đủ asset từ tag và hoàn tất Release tạo dở.

Nếu bị gián đoạn, xử lý lỗi mạng/quyền truy cập rồi chạy lại `publish.ps1` khi source không đổi. Thay đổi source sau tag đã có cần tăng version; script không di chuyển hoặc ghi đè tag. `-NoWait` chỉ đẩy source/tag rồi trả về khi Release còn đang chờ.

Đổi repository đích hoặc chạy lại workflow của tag đã có:

```powershell
.\scripts\publish.ps1 -Owner TEN_GITHUB -Repository TEN_REPO

gh workflow run release.yml --repo TamNhien/traffic-ai -f tag=v0.5.61
```

Khi dùng npm ngoài Docker trên Windows, Node.js cần 26.10.0 trở lên:

```powershell
npm install -g npm@latest
npm --version
```

Chi tiết kiểm tra thực hiện và giới hạn môi trường đóng gói có trong `VERIFICATION.md`.
