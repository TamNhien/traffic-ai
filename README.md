# Traffic AI V0.5.58 — Trace lifecycle và source clock

Nâng cấp từ full source V0.5.57. Đơn vị đếm là **lượt cắt vạch**: cùng phương tiện quay lại và cắt vạch lần nữa được tính thêm một lượt.

## Benchmark đầu vào V0.5.57

Screenshot: session161 / benchmark40, sao chép149 GT từ benchmark39.

| Chỉ số | V0.5.56 | V0.5.57 |
|---|---:|---:|
| Ground truth | 149 | 149 |
| AI đếm | 152 | 149 |
| Khớp | 135 | 132 |
| Lọt không đếm | 14 | 17 |
| Đếm dư | 17 | 17 |
| Recall | 90.6% | 88.6% |
| Precision | 88.8% | 88.6% |
| F1 | 89.7% | 88.6% |
| Class đúng | 98.5% | 98.5% |
| Sai loại | 2 | 2 |

Tổng AI bằng GT vẫn có17 lọt và17 dư. Ba lượt khớp giảm đều ở IN:75→72; OUT giữ77. Worker đề xuất198, backend gộp49, Human Guard loại32; DB149 event có timecode, integrityOK. Loại xe146 motorcycle,1 bicycle,2 truck. Counter direct43/interpolation82/rescue73 là bước candidate, không phải tổng DB cuối.

RAR lần này có **197 JPG duy nhất, đều mang prefix session161**, không có ảnh trộn từ phiên cũ và không có JSONL/model scores. Đã xem cả5 contact sheet cùng ảnh mục tiêu. Rider#328328 vẫn có cyan anchor dao động ở754.36–754.96s; các tọa độ này giống hệt ảnh cùng frame của .56. Bbox thay đổi kích thước và raw ID phân mảnh vẫn cần trace để xác định tác động tới event. Chưa thể gắn ba IN bị mất với một nguyên nhân cụ thể.

Hai lỗi loại chưa thay đổi:04:49.450 IN bicycle→motorcycle và10:41.981 OUT car→truck. Ảnh289.68s có người dắt xe đạp chưa được box, cạnh scooter riêng; tới292.36s có box MC#110090 confidence.47. Van641.96s vẫn rawtruck#254023 confidence.80. Không đủ event/track provenance để kết luận các sửa class đã giải quyết hai GT này.

**Chưa replay V0.5.58**. Các số trên là benchmark đầu vào; kiểm tra source không chứng minh đã tăng F1 hoặc sửa các hàng GT của clip. Giữ matching window, GT timestamp/class, finite gate, Road Zone, cooldown và threshold class/dedup.

## Thay đổi V0.5.58

### Đảo chiều chậm có chứng cứ hữu hạn

Heading V0.5.57 được giữ khi xe giảm tốc, nhưng có thể giữ mãi khi xe thật sự đảo chiều dưới ngưỡng1.5. Repro source thật: sau khi xác lập đi lên, center đi xuống1px/frame liên tục; .56 có IN qua finite gate còn .57 không có dù cạnh trước đã qua vạch. Chiều ngược lại cũng tái hiện.

V0.5.58 xác nhận hướng mới bằng **hai observation liên tiếp khác source frame**, vận tốc đo trên.75 và chuyển động thực ngược heading cũ, tích lũy ít nhất1.5px theo hướng ngược. Gap phải trong giới hạn stitching hiện có. Dừng, chuyển động thuận, mạnh đủ ngưỡng, gap lớn, alias fusion hoặc expiry xóa chứng cứ chưa hoàn tất. Duplicate/stale frame không được sửa motion history. Sau xác nhận, heading được chuẩn hóa tới ngưỡng full-leading hiện có; vận tốc thực vẫn dùng cho stitching/Human Guard.

Anchor đổi cạnh dẫn một lần khi đảo chiều chậm được xác nhận. Bbox biến dạng hoặc hướng mạnh thay đổi nhanh vẫn có thể làm anchor dao động; sửa này chưa được chứng minh giải quyết chuỗi ảnh#328328. Cần replay đầy đủ để đánh giá tradeoff và thời điểm crossing.

### Consensus dùng tuổi bằng chứng thật

Một bicycle consensus cũ có thể vẫn thắng history khi frame hiện tại chỉ có opinion motorcycle yếu; trước đây worker dùng frame truy vấn để gia hạn override. Nay certificate vẫn ràng buộc đúng decision frame/tuple, nhưng TTL tính từ **frame cuối minority thực sự thắng**. History đã hết tuổi không được tăng rescue counter, gia hạn nhãn hoặc đổi thành one-shot mới. Opinion thắng mới có thể gia hạn; one-shot đủ điều kiện vẫn dùng frame hiện tại.

`TrackLabelSmoother` nhận source frame từ worker. Canonical merge sắp xếp history theo frame thật, giữ opinion mạnh nhất mỗi frame và không đẩy24 nhãn truck cũ ra sau24 nhãn car mới để tạo truck consensus giả. Caller không truyền frame vẫn giữ ABI history hai phần tử. Không đổi ngưỡng confidence/TTL hoặc ép nhãn theo GT.

### Trace lỗi không làm mất dispatch của frame

Trước đây ghi JSONL trước dispatch có thể ném OSError và bỏ event đang chờ dù geometry đã commit. Nay lỗi mở/ghi/đóng trace chỉ tắt phần trace, ghi `benchmark_trace_warning`, và cho luồng event tiếp tục. Warning tách khỏi lỗi pipeline `last_error`; event giữ source frame/time gốc. Repro lỗi write .57 gửi0/1 event; .58 gửi1/1 và đóng writer lỗi.

Trace chỉ được đưa vào thư mục camera **sau khi writer đóng thành công**. Cùng filesystem dùng hardlink nguyên tử, filesystem không hỗ trợ dùng copy nguyên tử; publication lỗi không để lộ file dở hoặc ngắt shutdown. Canonical endpoint vẫn giữ nguyên. Lỗi ghi audit EOF không công bố camera artifact. Trace đang chạy hoặc bị lỗi chưa được coi là hồ sơ hoàn tất.

Header phiên chỉ có camera/session/FPS/frame policy; không tạo frame giả hay chứa secrets. Mỗi gate observation bổ sung bbox, center/anchor, raw ID, stitched, vận tốc đo và heading giữ lại. Các trường này giúp phân biệt chuyển động thật với bbox/identity biến động; không đổi scoring/reason ranking.

### Số hữu hạn và Annotation Studio đúng ảnh

Pydantic từ chối NaN/infinity ở event/GT timecode, session FPS/duration, benchmark tolerance và timecodes/window chẩn đoán. Giữ nullable fields, giới hạn và clamp hữu hạn hiện có. Validation chạy trước khi clock không hợp lệ đi vào database/scoring/JSON.

Annotation Studio ràng buộc index, annotation, save và bulk accept với dataset/version/filter cùng selection/request hiện tại. ChuyểnA→B→A hoặc reload cùng ảnh vô hiệu hóa phản hồi trước. Box cũ bị ẩn và không được lưu lên ảnh mới; thao tác sửa box/flags được chặn khi chưa tải đúng annotation hoặc đang lưu. Phản hồi/error save đến muộn không ghi đè ảnh mới hay tải lại index của selection cũ. Một effect tải annotation sau khi index xác nhận ảnh; index đến muộn không tải lại ảnh đã được chỉnh sửa và làm mất sửa đổi.

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
| benchmark-trace.jsonl | Trace gốc nếu còn trên AI service và <=128MiB |

API: `GET /api/benchmarks/{id}/export`; AI nội bộ: `GET /benchmark-traces/{session_id}/download`. Nếu trace thiếu/quá lớn/timeout, manifest ghi lý do và report ZIP vẫn tải được. Export không sửa GT/event/tổng đếm, không cắt trace để giả thành đầy đủ. Với session đang chạy, trace/event có thể tiếp tục tăng; tải sau khi hoàn tất.

URL metadata bỏ user/password/query/fragment; video chỉ giữ tên. Không lấy environment/settings, đường dẫn model hoặc video/model weights. Geometry camera hiện tại không được coi là cấu hình inference lịch sử. Gửi ZIP này cùng screenshot để có liên kết event/track. Sau khi trace đóng thành công, V0.5.58 còn lưu `session_<id>_benchmark-trace.jsonl` cùng JPG trong thư mục `camera_<id>`; khi nén ảnh, giữ kèm JSONL đó. Nếu trace lỗi, UI báo riêng và hồ sơ có thể thiếu dữ liệu; chỉ RAR JPG không cung cấp raw model scores hay provenance đầy đủ.

## Version, môi trường và database

| Thành phần | Giá trị |
|---|---|
| VERSION / Frontend / Backend / AI Service | 0.5.58 |
| Alembic head | `0072_trace_lifecycle_v0558` |
| Parent | `0071_anchor_lifecycle_v0557` |
| schema_version | 0.5.58 |
| npm trong Docker / CI / packageManager | 12.2.0 |
| Node.js trong Docker / CI | 26.10.0 |

Giữ pin npm/Node đã cập nhật và quy trình publish test→commit→push→tag→Release. Migration 0072 chỉ cập nhật schema version, giữ dữ liệu/GT. Camera Preview/Vehicle Count và GT/Report giữ bố cục 50/50. Chi tiết **513 test functions offline**, frontend timing checks và các giới hạn môi trường trong `VERIFICATION.md`.

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

Publish tự đọc VERSION để tạo tag **v0.5.58**, mặc định repository `TamNhien/traffic-ai`. Script kiểm thử source đã chuẩn hóa, commit/push/tag, chờ đúng Actions run theo tag/SHA/push và tạo Release có ZIP, TAR.GZ, README, SHA256SUMS. Fallback CLI bổ sung đủ asset từ tag và hoàn tất Release tạo dở.

Nếu bị gián đoạn, xử lý lỗi mạng/quyền truy cập rồi chạy lại `publish.ps1` khi source không đổi. Thay đổi source sau tag đã có cần tăng version; script không di chuyển hoặc ghi đè tag. `-NoWait` chỉ đẩy source/tag rồi trả về khi Release còn đang chờ.

Đổi repository đích hoặc chạy lại workflow của tag đã có:

```powershell
.\scripts\publish.ps1 -Owner TEN_GITHUB -Repository TEN_REPO

gh workflow run release.yml --repo TamNhien/traffic-ai -f tag=v0.5.58
```

Khi dùng npm ngoài Docker trên Windows, Node.js cần 26.10.0 trở lên:

```powershell
npm install -g npm@latest
npm --version
```

Chi tiết kiểm tra thực hiện và giới hạn môi trường đóng gói có trong `VERIFICATION.md`.
