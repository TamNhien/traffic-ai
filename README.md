# Traffic AI V0.5.57 — Anchor lifecycle và bằng chứng benchmark

Nâng cấp từ full source V0.5.56. Đơn vị đếm là **lượt cắt vạch**: cùng phương tiện quay lại và cắt vạch lần nữa được tính thêm một lượt.

## Benchmark đầu vào V0.5.56

Screenshot mới: session160 / benchmark39, sao chép149 GT từ benchmark38.

| Chỉ số | V0.5.55 | V0.5.56 |
|---|---:|---:|
| Ground truth | 149 | 149 |
| AI đếm | 152 | 152 |
| Khớp | 136 | 135 |
| Lọt không đếm | 13 | 14 |
| Đếm dư | 16 | 17 |
| Recall | 91.3% | 90.6% |
| Precision | 89.5% | 88.8% |
| F1 | 90.4% | 89.7% |
| Class đúng | 98.5% | 98.5% |
| Sai loại | 2 | 2 |

V0.5.56 giảm một lượt khớp; tổng AI không phản ánh mức chính xác từng lượt. Worker đề xuất 208, backend gộp 56, Human Guard loại 31; DB có 152 event có timecode. IN 75 / OUT 77; loại xe149 motorcycle, 1 bicycle, 2 truck. Các counter direct/interpolation/rescue là bước candidate, không cộng thành tổng DB cuối.

RAR hiện tại có **429 JPG:222 ảnh cũ giống hệt từng byte từ lượt V0.5.55 và207 ảnh mới**. Không có JSONL/model scores. Đã xem toàn bộ11 contact sheet và các ảnh mục tiêu; không dùng overlay cũ để kết luận hành vi V0.5.56.

Ở lượt mới, passage scooter#19086 chỉ có frame 1648 với anchor chéo; năm frame nhảy cạnh ở lượt trước thuộc ảnh cũ. Gần289.68s, người áo xanh dắt xe đạp chưa có box, cạnh một scooter đã được box; tới292.36s, chiếc xe đạp được box motorcycle#110090(conf.47). Chưa có event/track export để xác định AI event nào đã ghép với GTbicycle289.450. Van gần641.96s vẫn rawtruck#254023(conf.80). Các ảnh không đủ để gắn từng chẩn đoán quanh timecode với phương tiện GT.

**Chưa replay V0.5.57**. Các số trên là benchmark đầu vào; các source regression dưới đây không chứng minh đã cải thiện F1 hoặc sửa hai hàng sai loại của clip.

## Thay đổi V0.5.57

### Heading sống cùng canonical identity

V0.5.56 loại bước nhảy ngang/dọc nhưng blend tốc độ có thể đưa anchor của xe đang đi lên từ cạnh trên trở lại đáy bbox khi giảm tốc. Regression tái hiện quỹ đạo center luôn đi lên nhưng phát thêm crossing IN giả sau OUT.

Worker nay lấy heading đã xác lập từ `anchor_velocity_for()` riêng cho anchor. Heading được cập nhật khi |vx|+|vy| đạt ngưỡng full-leading 1.5 hiện có; khi chậm/đứng lại, giữ heading đó. `velocity_for()` vẫn trả vận tốc đo thực cho stitching và Human Guard. Track chưa có heading tin cậy giữ startup blend cũ; alias chuyển heading theo source frame, expiry xóa cùng identity. Cleanup chạy trước raw-ID lookup để ID quay lại sau expiry không hồi sinh vận tốc cũ.

Đảo chiều thật nhưng rất chậm dưới 1.5 vẫn giữ heading trước đến khi có chuyển động đủ tin cậy, nên thời điểm crossing có thể trễ. Cần replay để đánh giá; không mở gate hoặc giảm ngưỡng cooldown/Road Zone.

### Pending sau merge và clock hình học

Pending được xét lại same-direction eligibility theo passage mới nhất sau canonical merge. Proof từ alias không được mượn tuổi của passage cũ để tạo qualified override sát passage vừa đếm. Return ngược hướng hoặc cùng hướng đã đủ thời hạn vẫn giữ rule hiện có. Giá trị clock hình học NaN/infinity không còn bị clamp thành timestamp lùi giả; dùng frame quan sát nếu clock không hợp lệ.

### Consensus đã đạt điều kiện được áp dụng đúng

Một bicycle consensus nhiều frame/nguồn đủ điều kiện có fused score khoảng.8277 trước đây bị xét lại như one-shot và mất vì ngưỡng .90. Worker lưu proof đúng canonical track, source frame và tuplelabel/score, rồi áp dụng quyết định consensus đã được kiểm chứng. Cache retry cùng frame không chạy model/tăng counter lại; tuple khác, frame khác hoặc chỉ có one-shot không được mượn proof. Giữ threshold one-shot .90, điều kiện winning-frame/source/hits/margin, truck semantic protection và TTL.

Truck semantic lock dùng source frame của bằng chứng truck thắng mới nhất. Đọc lại cùng history không gia hạn lock theo frame truy vấn; primary truck đủ điều kiện vẫn cập nhật theo detector frame hiện tại. Ví dụ bằng chứng cuối frame 95 với TTL 450 không được giữ tới 600 chỉ vì đã đọc history ở frame 210. Không ép van thànhcar theoGT.

### Human Guard và trace đúng transaction

Decision trung lập trả về trạng thái canonical: pedestrian đã xác nhận vẫn rejected đến khi có rider evidence hợp lệ. Xóa provisional strike chưa đủ điều kiện vẫn trảkeep. Action dùng để authorize event và status dùng trong overlay/trace nay thống nhất.

Trace cộng deferred commit đã dispatch trực tiếp vào `crossing_events` của frame xác nhận, không đếm đôi ordinary/lost queue và không mang lại sang frame tiếp theo. Event payload vẫn giữ source frame/time gốc; trace row là thời điểm quan sát/xác nhận.

Snapshot mới có tên `session_<id>_<UTC>_frame_<n>.jpg` trong thư mục camera, giúp phân biệt các lượt chạy nếu nén chung. Writer thất bại trảNone, không đưa URL ảnh chưa được lưu vào event. Ảnh cũ giữ nguyên tên; không tự gán lại session cho archive hiện tại.

### Chẩn đoán có scope và báo cáo đúng phiên

`diagnosis_scope` phân biệt geometry của track đã xác định với dấu hiệu của các xe quanh timecode. DET/track/road/cooldown/confirmation là counter toàn khung, không được coi là nguyên nhân riêng của một xe GT. ID không có observation không được coi là track đã xác minh. Reason ranking và scoring giữ nguyên.

Frontend hiển thị **Dấu hiệu quanh timecode** và ghi chưa gắn với xeGT khi evidence chưa xác định identity; report cũ thiếu scope cũng được coi là chưa xác định. Đổi benchmark/camera hoặc reload cùng ID vô hiệu hóa phản hồi cũ, kể cả chuyểnA→B→A; kết quả load/reconcile chậm không ghi đè phiên mới.

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

URL metadata bỏ user/password/query/fragment; video chỉ giữ tên. Không lấy environment/settings, đường dẫn model hoặc video/model weights. Geometry camera hiện tại không được coi là cấu hình inference lịch sử. Gửi ZIP này cùng screenshot để có liên kết event/track; chỉRAR ảnh không cung cấp raw model scores hay provenance đầy đủ.

## Version, môi trường và database

| Thành phần | Giá trị |
|---|---|
| VERSION / Frontend / Backend / AI Service | 0.5.57 |
| Alembic head | `0071_anchor_lifecycle_v0557` |
| Parent | `0070_benchmark_evidence_v0556` |
| schema_version | 0.5.57 |
| npm trong Docker / CI / packageManager | 12.2.0 |
| Node.js trong Docker / CI | 26.10.0 |

Giữ pin npm/Node đã cập nhật và quy trình publish test→commit→push→tag→Release. Migration 0071 chỉ cập nhật schema version, giữ dữ liệu/GT. Camera Preview/Vehicle Count và GT/Report giữ bố cục 50/50. Chi tiết **459 offline assertions**, frontend timing checks và các giới hạn môi trường trong `VERIFICATION.md`.

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

Publish tự đọc VERSION để tạo tag **v0.5.57**, mặc định repository `TamNhien/traffic-ai`. Script kiểm thử source đã chuẩn hóa, commit/push/tag, chờ đúng Actions run theo tag/SHA/push và tạo Release có ZIP, TAR.GZ, README, SHA256SUMS. Fallback CLI bổ sung đủ asset từ tag và hoàn tất Release tạo dở.

Nếu bị gián đoạn, xử lý lỗi mạng/quyền truy cập rồi chạy lại `publish.ps1` khi source không đổi. Thay đổi source sau tag đã có cần tăng version; script không di chuyển hoặc ghi đè tag. `-NoWait` chỉ đẩy source/tag rồi trả về khi Release còn đang chờ.

Đổi repository đích hoặc chạy lại workflow của tag đã có:

```powershell
.\scripts\publish.ps1 -Owner TEN_GITHUB -Repository TEN_REPO

gh workflow run release.yml --repo TamNhien/traffic-ai -f tag=v0.5.57
```

Khi dùng npm ngoài Docker trên Windows, Node.js cần 26.10.0 trở lên:

```powershell
npm install -g npm@latest
npm --version
```

Chi tiết kiểm tra thực hiện và giới hạn môi trường đóng gói có trong `VERIFICATION.md`.
