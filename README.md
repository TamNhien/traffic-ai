# Traffic AI V0.5.62 — Identity riêng và bằng chứng cắt vạch

Nâng cấp từ đúng full source V0.5.61 bạn gửi, giữ toàn bộ 190 đường dẫn cũ và thêm migration0076. Đơn vị đếm là **lượt cắt vạch**: cùng phương tiện quay lại và cắt vạch lần nữa được tính thêm một lượt.

## Benchmark đầu vào V0.5.61

Ảnh mới: session167 / benchmark44, sao chép149 GT từ benchmark43.

| Chỉ số | V0.5.61 |
|---|---:|
| Ground truth / AI đếm | 149 / 149 |
| Khớp | 134 |
| Lọt / dư | 15 / 15 |
| Recall / Precision / F1 | 89.9% / 89.9% / 89.9% |
| Class đúng / sai loại | 99.3% / 1 |
| IN / OUT | 70 / 79 |

Integrity OK: worker đề xuất196, backend gộp47, DB149 event có timecode. So với ảnh V0.5.60, class đúng tăng98.5%→99.3% và sai loại2→1; tổng khớp/F1 giữ nguyên. Lỗi class còn lại: GT xe đạp04:49.450 IN, AI xe máy. Counter Span clock5 và Truck lock→car1 là telemetry của lần chạy đầu vào này.

RAR có **195 JPG duy nhất + 1 JSONL**, tất cả phiên167; đã xem5 contact sheet và ảnh mục tiêu. Trace195,773,106byte /23,652 dòng gồm23,650 observation, session header và geometry header. Geometry thực có processed1440×811/source2960×1668, vạch hữu hạn và Road Zone worker dùng.

**Chưa replay V0.5.62, chưa có F1 mới.** Giữ GT, matching window0.75s, global matching, model/taxonomy, Road Zone, threshold/cooldown/dedup. `counting.py` giữ nguyên byte từ .61, gồm span clock và fresh-CAR crossing đã có.

## Thay đổi V0.5.62

### Tách hai đối tượng đang dùng chung canonical ID

Trace f7273 ghi canonical104160 hai lần: raw107899 ở phía dưới và raw104160 ở phía trên, tọa độ cách nhau rất xa. Resolver cũ có kiểm tra claimed ID khi ghép candidate nhưng fallback `canonical=raw_id` có thể dùng lại ID đang bị chiếm.

Fallback nay tạo canonical riêng khi raw ID trùng canonical đang sống/đã được dùng. ID nội bộ sinh ra là số âm, không tái sử dụng sau TTL và tránh token âm đã thấy; raw ID gốc vẫn giữ nguyên. Identity mới không nhận motion/heading hoặc gate/class history từ đối tượng cũ. Caller bình thường và ngưỡng stitch giữ nguyên, gồm bbox guard .59 và four-wheel recovery.

Replay checkpoint source thực f7272: .61 tạo[104160,104160], .62 tạo[104160,-1]. Vận tốcY ở đối tượng phía trên f7275 từ−400.468 do nhảy giữa hai đối tượng thành−0.04708. Đây là replay state/trace, **không phải replay model/video**. Trace có445 nhóm trùng canonical trên44 ID; không coi đó là445 event sai. Đối tượng đến trước vẫn giữ history cũ; việc tách hiện tại không phục hồi history đã bị trộn ở các frame trước.

### Cache class giữ đúng bằng chứng, không gia hạn TRUCK bằng frame CAR

Source .61 có thể lấy TRUCK lock cũ ghi vào cache refinement bằng frame CAR/BUS mới. Repro: lock source100/TTL30, CAR.90 tại129 bị lock ưu tiên; cache lại ghiTRUCK/source129, nên vẫnTRUCK ở131 khi lock đã hết hạn.

Nay cache lưu correction qualified cùng source clock thật trước khi áp dụng semantic-lock precedence cho kết quả trả về. Nếu policy giữ primary/stable label khác refiner mới, lấy source của đúng label đó; future/expired clock và correction cũ hơn cache đang có bị chặn. TRUCK lock đủ điều kiện vẫn được ưu tiên, fresh-CAR crossing .61 và confidence policy giữ nguyên. Sau lock hết hạn, CAR/BUS qualified có thể trở lại đến TTL gốc của correction; cần replay để đo tác động class thật.

Trace mới có2160 observation mà overrideTRUCKclock mới hơn live-lockclock trên254023/286434; đây là dấu vết cache clock, không phải2160 lỗi class. Xe đạp GT còn sai chưa được box tại frame7243, canonical110070 chỉ xuất hiện7273/t290.88 đã downstream. Target refiner gần đó là motorcycle khác; không hạ bicycle veto để ép sửa GT.

### Chẩn đoán phân biệt đoạn vạch thật và đường kéo dài

Audit cũ chỉ nhìn extrema signed distance nên có thể báo Anchor span khi xe chỉ cắt đường kéo dài ngoài đoạn vạch nhìn thấy. Canonical13014 f1354–1355 giao đường vô hạn tạix1254.631, ngoài đầu vạchx1092.528; .61 báo anchor-span reject.

Audit mới dùng geometry header thực và đoạn nối hai observation liên tiếp: phân biệt finite anchor/center span, extension-only và unverified. Alias khác tọa độ cùng source frame, frame đảo thứ tự, thiếu tọa độ/sign không khớp hoặc gap>45 frame không tạo finite proof. Gap45 là bound của **audit**, không thay ngưỡng Gate. Header không hợp lệ/không có giữ output legacy.

Report có hai nhãn mới: **Quỹ đạo chỉ cắt đường kéo dài ngoài đoạn vạch đếm** và **Chưa đủ quỹ đạo quan sát để xác nhận cắt đoạn vạch**. Giao hình học không chứng minh Road/motion qualification, Gate chấp nhận, backend persist hoặc danh tính GT. Khi chưa có matched tracking ID, bằng chứng vẫn thuộc các track lân cận trong cửa sổ thời gian. Các counter detection/rejection/event vẫn là toàn frame.

### Trace truy được từng proposal và source clock

Full raw/gzip trace thêm `crossing_proposals` với camera/session/canonical, class/hướng/confidence, source frame/time, phương pháp, điểm cắt và producer stage. Proposal trong frame ghi `committed_before_submit`; event được Human Guard xác nhận và dispatcher nhận ghi `submitted_after_guard`. Hai stage này **không khẳng định event đã lưu DB**; cần đối chiếu `events.json` trong ZIP benchmark.

`gate_tracks.crossing_clock_audit` giữ geometric/trusted/selected frame và quyết định Human Guard pending/rejected. Clock gốc không bị đổi khi guard xác nhận muộn. Audit bỏ model ID/snapshot path và không tăng model calls hoặc event count. Raw/gzip giữ toàn bộ metadata; diagnosis chỉ chọn fields hữu ích, không tự gắn mọi proposal lân cận với GT.

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

URL metadata bỏ user/password/query/fragment; video chỉ giữ tên. Không lấy environment/settings, model paths hay video/model weights. Header geometry mới là cấu hình worker thực dùng, ở đúng kích thước frame đã xử lý; camera hiện tại ghi riêng và không thay thế geometry lịch sử. Trace mới có primary/stable class, override/lock source clocks và ordinary domain/general opinions theo target. Audit class vẫn nằm trong **raw/gzip trace**; diagnosis giữ output legacy khi không có geometry header hợp lệ, và bổ sung diễn giải finite geometry khi có header hợp lệ.

Gửi ZIP hồ sơ cùng screenshot. Khi nén thư mục ảnh camera, giữ `session_<id>_benchmark-trace.jsonl`; chỉ JPG không cung cấp đầy đủ event/track/source-clock provenance.

## Version, môi trường và database

| Thành phần | Giá trị |
|---|---|
| VERSION / Frontend / Backend / AI Service | 0.5.62 |
| Alembic head | `0076_identity_audit_v0562` |
| Parent | `0075_span_clock_class_v0561` |
| schema_version | 0.5.62 |
| npm trong Docker / CI / packageManager | 12.2.0 |
| Node.js trong Docker / CI | 26.10.0 |

npm12.2.0 đã đối chiếu [npm CLI latest](https://github.com/npm/cli/releases/latest) ngày06/10/2026; giữ Node26.10.0 theo cấu hình hiện có. Giữ quy trình publish test→commit→push→tag→Release. Migration 0076 chỉ cập nhật schema version, giữ dữ liệu/GT. Camera Preview/Vehicle Count và GT/Report giữ bố cục 50/50. V0.5.62 đạt **649 test functions offline**, **563 kiểm tra tĩnh**, **38 kiểm tra release cục bộ** và **25 kiểm tra frontend**. 35 test HTTP/ORM chưa chạy; không kế thừa số full pytest từ tài liệu bản trước. Phạm vi và môi trường được ghi rõ trong `VERIFICATION.md`.

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

Publish tự đọc VERSION để tạo tag **v0.5.62**, mặc định repository `TamNhien/traffic-ai`. Script kiểm thử source đã chuẩn hóa, commit/push/tag, chờ đúng Actions run theo tag/SHA/push và tạo Release có ZIP, TAR.GZ, README, SHA256SUMS. Fallback CLI bổ sung đủ asset từ tag và hoàn tất Release tạo dở.

Nếu bị gián đoạn, xử lý lỗi mạng/quyền truy cập rồi chạy lại `publish.ps1` khi source không đổi. Thay đổi source sau tag đã có cần tăng version; script không di chuyển hoặc ghi đè tag. `-NoWait` chỉ đẩy source/tag rồi trả về khi Release còn đang chờ.

Đổi repository đích hoặc chạy lại workflow của tag đã có:

```powershell
.\scripts\publish.ps1 -Owner TEN_GITHUB -Repository TEN_REPO

gh workflow run release.yml --repo TamNhien/traffic-ai -f tag=v0.5.62
```

Khi dùng npm ngoài Docker trên Windows, Node.js cần 26.10.0 trở lên:

```powershell
npm install -g npm@latest
npm --version
```

Chi tiết kiểm tra thực hiện và giới hạn môi trường đóng gói có trong `VERIFICATION.md`.
