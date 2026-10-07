# Traffic AI V0.5.63 — Mẫu class sát vạch và phản hồi backend

Nâng cấp từ đúng full source V0.5.62 đã giao: giữ đủ **191 đường dẫn cũ**, thêm migration0077. Đơn vị đếm là **lượt cắt vạch**; cùng phương tiện quay lại và cắt vạch lần nữa được tính thêm một lượt.

## Benchmark đầu vào V0.5.62

Ảnh mới: session168 / benchmark45, sao chép149 GT từ benchmark44.

| Chỉ số | V0.5.62 đã chạy trên máy người dùng |
|---|---:|
| Ground truth / AI đếm | 149 / 149 |
| Khớp | 135 |
| Lọt / dư | 14 / 14 |
| Recall / Precision / F1 | 90.6% / 90.6% / 90.6% |
| Class đúng / sai loại | 98.5% / 2 |
| IN / OUT | 68 / 81 |

So với ảnh V0.5.61: khớp134→135, F1 89.9%→90.6%, lọt/dư15→14; class99.3%→98.5%. Hai hàng sai loại: xe đạp04:49.450 IN→xe máy và ô tô10:41.981 OUT→xe tải. Worker195 proposal, backend gộp46, DB149 timed events, Human Guard loại30; Integrity OK. Phân bốAI146 xe máy/1 xe đạp/2 xe tải.

RAR mới có **194 JPG duy nhất + 1 JSONL**, tất cả ảnh phiên168/1440×811; đã xem5 contact sheet và ảnh mục tiêu. Trace196,204,733byte /23,652 dòng gồm23,650 observation và2 metadata header;195 proposal gồm194 `committed_before_submit` và1 `submitted_after_guard`. Có42 canonical âm, không còn nhóm canonical trùng trong cùng frame ở trace này. Đây là kiểm tra input thực, không chứng minh mọi track đã ghép đúng danh tính vật lý.

**Chưa replay V0.5.63, chưa có F1 mới.** Giữ GT149, matching window0.75s, global matching, model/taxonomy, Road Zone và Gate/cooldown/dedup. `counting.py`, `tracking.py`, `classification.py` và test tương ứng giữ nguyên byte từ .62.

## Thay đổi V0.5.63

### Lấy mẫu thêm TRUCK gần đoạn vạch bằng ngân sách còn dư

Trace quanh ô tô10:41.981 cho thấy vấn đề cadence. Trong .61, canonical254023 có CAR.838867 ởf16049 vàCAR.858887 ở crossingf16050: đủ hai frame liên tiếp theo policy .80 hiện có. Trong .62, CAR.716797 trước đó ởf16007, f16049 không suy luận; crossingf16050 chỉ có một CAR win, nên live TRUCK lock vẫn thắng. Đây là thiếu mẫu bằng chứng trước crossing, không phải lỗi cache/source clock .62 đã sửa.

`.63` giữ queue thường và crossing ưu tiên trước. Sau lượt thường, nếu còn slot thì lấy mẫu frame hiện tại cho TRUCK có lock còn hiệu lực gần **đoạn vạch hữu hạn**. Không lấy frame tương lai, không đổi .80/hai frame liên tiếp/TTL/veto/consensus; giữ ưu tiên periodic MC/bicycle và `AI_REFINE_MAX_PER_FRAME=2`. Xa đoạn vạch/lock hết hạn hoặc future lock không được lấy thêm.

217 test class/context đạt, gồm11 mới. Actual .62 ZIP differential:210 control đạt +5 assertion regression; .63 đạt215 assertion chung, không dùng thiếu helper mới làm bằng chứng lỗi. Probe4 pha cadence cho cùng opinions có kiểm soát cho thấy lấy mẫu thêm giảm phụ thuộc pha. Đây không phải inference/replay model thật.

Inference cục bộ có thể tăng khi còn slot; khi ngân sách đã dùng hết thì không hứa có CAR proof thứ hai. Sampling chỉ tạo cơ hội thu bằng chứng, không tạo nhãn hoặc crossing. Lỗi xe đạp04:49.450 vẫn có dấu vết detect muộn/target khác; không hạ bicycle veto để ép khớp GT.

### Ghi phản hồi backend cho từng event đã xử lý

Dispatcher thêm queue audit giới hạn1024. Sau khi request hoàn tất retry policy, ghi một terminal record với camera/session/canonical, class/hướng, **source frame/time gốc**, method/điểm cắt, số lần thử, outcome và event ID backend hợp lệ nếu có:

| Outcome | Ý nghĩa |
|---|---|
| created | Backend trả header xác nhận tạo event |
| deduplicated | Backend trả header gộp trùng, kèm reason đã whitelist |
| acknowledged_unknown | Response thành công nhưng backend cũ không nêu tạo hay gộp |
| failed | Request đã hết retry mà chưa nhận response thành công |

Record không chứa token, backend URL, snapshot/model path, response body hay error text. Body thiếu/không phải JSON hoặc ID bool/không phải positive integer không chặn delivery. Audit lỗi/queue đầy không retry HTTP thêm, không đổi counters; queue đầy tăng `delivery_audit_dropped`. Client không khởi tạo được vẫn có pending/flush=False như .62, không tự tạo terminal receipt cho việc chưa xử lý.

Worker là writer JSONL duy nhất, drain receipts trong lúc chạy và **sau dispatcher EOF drain, trước close/publish/gzip**. Footer `delivery_summary` ghi drain complete/pending/dropped của **toàn phiên**, không tạo observation frame/time giả. Lỗi trace vẫn không chặn delivery. Camera/session giữ trạng thái draining đến khi delivery và optional artifact closure kết thúc.

### Diagnosis phân biệt proposal và kết quả gửi

Canonical20863 có proposal OUT source69.4566 tạiobservation1739; primary Gate replay từ anchors tái hiện69.456629. Ảnh benchmark vẫn báo lọt GT69.457 và nearest DB event70.52. Proposal sát GT không tự chứng minh đúng phương tiện GT hoặc đã lưu DB; cần events.json/ground-truth.json và receipt để xác định downstream cause. Vì chưa có DB export nên không nới Gate/cooldown/dedup.

Khi truy vấn đúng canonical, .62 bỏ qua proposal và vẫn báo Gate reject. `.63` trả `crossing_proposal_observed` hoặc `crossing_delivery_observed` cùng source evidence đã scope. Khi chưa biết canonical của event/GT, các record vẫn là **track lân cận**, reason cũ giữ nguyên; không gắn proposal gần thời gian thành nguyên nhân chắc chắn của GT lọt.

Diagnosis giữ tối đa8 proposal và8 receipt mỗi cửa sổ, whitelist fields và lọc bằng source clock gốc. Guard/ack đến muộn không làm đổi timestamp crossing. Receipt/footer là audit-only: không tăng detection/rejection/event counters hoặc finite geometry evidence. Proposal ghi `backend_persistence=unverified`; backend response không tự chứng minh đúng GT. Traces cũ không có fields mới giữ decoded JSON legacy.

Report thêm mục **Dấu vết crossing và phản hồi backend** ở hàng lọt và sai loại, hiển thị source time, canonical, stage/outcome, event ID và lý do gộp bằng tiếng Việt. API lọc lại đúng matched canonical, bỏ private fields và giữ cap8. Giữ mọi benchmark handler/state và scoring controls; UI additions không đổi GT hay kết quả matching.

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

URL metadata bỏ user/password/query/fragment; video chỉ giữ tên. Không lấy environment/settings, model paths hay video/model weights. Header geometry mới là cấu hình worker thực dùng, ở đúng kích thước frame đã xử lý; camera hiện tại ghi riêng và không thay thế geometry lịch sử. Trace mới có primary/stable class, override/lock source clocks và ordinary domain/general opinions theo target. Audit class chi tiết vẫn nằm trong **raw/gzip trace**. Diagnosis và Report nay thêm proposal/receipt đã lọc theo source clock và canonical; trace cũ không có các fields mới giữ output legacy. Geometry vẫn dùng header lịch sử hợp lệ của worker.

Gửi ZIP hồ sơ cùng screenshot. Khi nén thư mục ảnh camera, giữ `session_<id>_benchmark-trace.jsonl`; chỉ JPG không cung cấp đầy đủ event/track/source-clock provenance.

## Version, môi trường và database

| Thành phần | Giá trị |
|---|---|
| VERSION / Frontend / Backend / AI Service | 0.5.63 |
| Alembic head | `0077_delivery_prescan_v0563` |
| Parent | `0076_identity_audit_v0562` |
| schema_version | 0.5.63 |
| npm trong Docker / CI / packageManager | 12.2.0 |
| Node.js trong Docker / CI | 26.10.0 |

npm12.2.0 đã đối chiếu [npm CLI latest](https://github.com/npm/cli/releases/latest) ngày07/10/2026; giữ Node26.10.0 theo cấu hình hiện có. Giữ quy trình publish test→commit→push→tag→Release. Migration 0077 chỉ cập nhật schema version, giữ dữ liệu/GT. Camera Preview/Vehicle Count và GT/Report giữ bố cục 50/50. V0.5.63 đạt **687 test functions offline**, **591 kiểm tra tĩnh**, **38 kiểm tra release cục bộ** và **30 kiểm tra frontend**. 35 test HTTP/ORM chưa chạy; không kế thừa số full pytest từ tài liệu bản trước. Phạm vi và môi trường được ghi rõ trong `VERIFICATION.md`.

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

Mở **https://traffic-ai.test:8443**, nhấn `Ctrl + F5`. Chạy lại đúng clip, cùng vạch/Road Zone; tạo benchmark cho session mới, sao chép GT 149 từ benchmark45 tương thích và bấm **Đối chiếu lại**. Sau đó bấm **Tải hồ sơ benchmark** để lấy ZIP dùng cho lần phân tích tiếp theo.

Nếu chưa đăng nhập GitHub CLI, chạy một lần:

```powershell
gh auth login
gh auth setup-git
```

Nếu chưa cấu hình Git author, đặt `git config --global user.name` và `git config --global user.email` bằng thông tin của bạn.

Publish tự đọc VERSION để tạo tag **v0.5.63**, mặc định repository `TamNhien/traffic-ai`. Script kiểm thử source đã chuẩn hóa, commit/push/tag, chờ đúng Actions run theo tag/SHA/push và tạo Release có ZIP, TAR.GZ, README, SHA256SUMS. Fallback CLI bổ sung đủ asset từ tag và hoàn tất Release tạo dở.

Nếu bị gián đoạn, xử lý lỗi mạng/quyền truy cập rồi chạy lại `publish.ps1` khi source không đổi. Thay đổi source sau tag đã có cần tăng version; script không di chuyển hoặc ghi đè tag. `-NoWait` chỉ đẩy source/tag rồi trả về khi Release còn đang chờ.

Đổi repository đích hoặc chạy lại workflow của tag đã có:

```powershell
.\scripts\publish.ps1 -Owner TEN_GITHUB -Repository TEN_REPO

gh workflow run release.yml --repo TamNhien/traffic-ai -f tag=v0.5.63
```

Khi dùng npm ngoài Docker trên Windows, dùng Node.js 26.10.0 như cấu hình dự án:

```powershell
npm install -g npm@latest
npm --version
```

Chi tiết kiểm tra thực hiện và giới hạn môi trường đóng gói có trong `VERIFICATION.md`.
