# Traffic AI V0.5.55 — Refinement Admission và Passage Lifecycle

Nâng cấp từ full source V0.5.54. Đơn vị đếm là **lượt cắt vạch**: cùng phương tiện quay lại và cắt vạch lần nữa được tính thêm một lượt.

## Benchmark đầu vào V0.5.54

Screenshot ghi nhận session 158 / benchmark 37, GT sao chép từ benchmark 36:

| Chỉ số | V0.5.54 |
|---|---:|
| Ground truth | 149 |
| AI đếm | 152 |
| Khớp | 136 |
| Lọt không đếm | 13 |
| Đếm dư | 16 |
| Recall | 91.3% |
| Precision | 89.5% |
| F1 | 90.4% |
| Class đúng | 98.5% |
| Sai loại | 2 |

So với V0.5.53, dư giảm 18 → 16, F1 tăng 89.8% → 90.4%, class đúng tăng 97.1% → 98.5%; số khớp/lọt chưa đổi. Worker đề xuất 231 event, backend gộp 79, Human Guard loại 37; DB có 152 event với timecode. Lọt: anchor span 5, gần vạch chưa span 3, center-only 1, cooldown 4. Dư: rescue 8, direct 5, interpolation 2, gần GT đã khớp/cùng điểm cắt 1.

Hai lỗi loại xe đang hiển thị: 04:49.450 IN GT bicycle → AI motorcycle và 10:41.981 OUT GT car → AI truck. Snapshot gần 04:49 cho thấy người áo xanh dắt xe đạp và một xe máy riêng bên cạnh; box motorcycle yếu xuất hiện trên vùng giỏ/bánh trước ở frame sau. Chưa đủ dữ liệu để xác định tracking ID của event đã ghép tại đúng crossing. Van ở 10:41 có overlay truck; taxonomy GT và output model vẫn là hai nguồn cần đối chiếu.

Ở chuỗi snapshot 65.88–66.28 s, cùng track motorcycle có bốn proposal IN/OUT xen kẽ gần đầu vạch. Overlay nằm trước backend dedup nên không thể coi chúng là bốn event dư đã lưu. Đây là dấu hiệu để rà soát quỹ đạo và pending lifecycle, không dùng để ép số benchmark.

Các số trên là **đầu vào V0.5.54**. Chưa có replay/benchmark V0.5.55; các regression dưới đây chứng minh lỗi source và hành vi sửa, không chứng minh mức tăng F1 hoặc class của clip.

## Thay đổi V0.5.55

### Refiner chọn đúng target và xét class đối nghịch

Matcher thường tuân thủ giới hạn khoảng cách tâm, kể cả box lớn overlap target. Bản trước đã áp dụng guard ở Bicycle Context nhưng matcher refiner thường vẫn có nhánh overlap vượt giới hạn.

Consensus truck/bus và truck semantic lock dùng các frame thắng thật trước car/bus/truck, đồng thời xét tổng evidence của class đối nghịch còn hiệu lực. Nhãn truck xuất hiện nhiều lần nhưng thua ô tô hoặc hòa nguồn khác không tạo quyền promote. Một-frame correction cũng phải thắng các nguồn cùng target. Giữ các ngưỡng, decay và taxonomy; vẫn bảo toàn control xe tải yếu được xác nhận lặp lại hợp lệ.

### Crossing được dùng ngân sách trước suy luận định kỳ

Worker thu các candidate refine định kỳ, xử lý crossing trong thứ tự geometry hiện có, rồi dùng phần ngân sách còn lại cho candidate gần đoạn vạch hữu hạn nhất. Track đã crossing không bị refine định kỳ lại trong cùng frame. Tổng refine_max_per_frame giữ nguyên; track thường xuất hiện trước trong iterator không chiếm slot của crossing thật ở sau.

Đọc cached override tại crossing giữ frame gốc và TTL gốc. Inference không có opinion dương/hữu hạn không được biến consensus cũ thành observation mới để gia hạn override hoặc tăng rescue. Bằng chứng mới hợp lệ tiếp tục có thể cập nhật consensus.

### Guard đo quỹ đạo thực và kiểm tra pending sau merge

Cả bốn gate đo chiều dài đường đi từ các mẫu quan sát trong span, gồm neutral samples, khi xét normal motion/jump. Chord ngắn nối hai đầu không còn che một excursion lớn ở giữa. Với hai observation, phép đo giữ đúng khoảng cách cũ; các bent-path hợp lệ vẫn được kiểm tra bảo toàn.

Anchor pending được kiểm tra lại theo thứ tự các source frame duy nhất sau merge alias trước khi confirm/finalize. Jump, rời Road Zone hoặc sustained reverse đã nằm trong history không bị một mẫu local cuối che mất. Crossing thật về sau vẫn có điểm và thời gian nguồn riêng. Giữ finite segment, Road Zone và các ngưỡng motion/jump/cooldown.

### Trace đúng track và trạng thái cuối của crossing

Backend gửi tracking_ids tương ứng mỗi timecode. AI chọn audit đúng track trước giới hạn tám record, tránh xe khác trong cảnh đông đẩy mất evidence cần xem. Các kết quả guard đến muộn được cập nhật theo cùng (track_id, frame quan sát), kể cả nằm ngoài cửa sổ timecode; quyết định mới của passage khác không được gắn vào crossing cũ.

Báo cáo phân biệt evidence của **track đã ghép với GT** và evidence của **các track gần timecode khi chưa biết ID**. Detector/cooldown diagnostics vẫn lấy từ frame trong cửa sổ, không bị record kết quả đến muộn làm tăng delta. Request có số tracking_ids khác số times bị validation loại.

### Đếm backend và release bootstrap

Event delivery và session finish khóa camera rồi session trong cùng thứ tự, tải lại giá trị ORM trước các đọc dedup/tổng event và cập nhật. Hourly bucket cũng được refresh. Các kiểm tra source/query bảo vệ stale identity-map; concurrency PostgreSQL vẫn cần chạy trên môi trường dự án.

Benchmark dùng thứ tự ổn định (source_time_seconds, id) khi timestamp bằng nhau. Giữ mục tiêu ghép theo thời gian, cửa sổ scoring và các ngưỡng dedup.

GitHub bootstrap dùng quiet probe cục bộ cho repository/origin chưa tồn tại, xử lý theo exit code rồi chạy fallback create/add. Quy trình publish tiếp tục test, commit, push, tạo tag bất biến và hoàn tất Release có đủ assets.

## Version, môi trường và database

| Thành phần | Giá trị |
|---|---|
| VERSION / Frontend / Backend / AI Service | 0.5.55 |
| Alembic head | `0069_refine_admission_v0555` |
| Parent | `0068_gate_semantics_v0554` |
| schema_version | 0.5.55 |
| npm trong Docker / CI / packageManager | 12.2.0 |
| Node.js trong Docker / CI | 26.10.0 |

Migration cập nhật schema version, giữ GT/dữ liệu. Bố cục Camera Preview / Vehicle Count và GT / Report vẫn chia 50/50. Fast/Bracket/Late/adaptive là diagnostic ở bước candidate validation; tổng event cuối lấy từ DB sau Human Guard và dedup.

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

Mở **https://traffic-ai.test:8443**, nhấn `Ctrl + F5`. Chạy lại đúng clip, cùng vạch/Road Zone; tạo benchmark cho session mới, sao chép GT 149 từ benchmark tương thích và bấm **Đối chiếu lại**.

Nếu chưa đăng nhập GitHub CLI, chạy một lần:

```powershell
gh auth login
gh auth setup-git
```

Nếu chưa cấu hình Git author, đặt `git config --global user.name` và `git config --global user.email` bằng thông tin của bạn.

Publish tự đọc VERSION để tạo tag **v0.5.55**, mặc định repository `TamNhien/traffic-ai`. Script kiểm thử source đã chuẩn hóa, commit/push/tag, chờ đúng Actions run theo tag/SHA/push và tạo Release có ZIP, TAR.GZ, README, SHA256SUMS. Fallback CLI bổ sung đủ asset từ tag và hoàn tất Release tạo dở.

Nếu bị gián đoạn, xử lý lỗi mạng/quyền truy cập rồi chạy lại `publish.ps1` khi source không đổi. Thay đổi source sau tag đã có cần tăng version; script không di chuyển hoặc ghi đè tag. `-NoWait` chỉ đẩy source/tag rồi trả về khi Release còn đang chờ.

Đổi repository đích hoặc chạy lại workflow của tag đã có:

```powershell
.\scripts\publish.ps1 -Owner TEN_GITHUB -Repository TEN_REPO

gh workflow run release.yml --repo TamNhien/traffic-ai -f tag=v0.5.55
```

Khi dùng npm ngoài Docker trên Windows, Node.js cần 26.10.0 trở lên:

```powershell
npm install -g npm@latest
npm --version
```

Chi tiết kiểm tra thực hiện và giới hạn môi trường đóng gói có trong `VERIFICATION.md`.
