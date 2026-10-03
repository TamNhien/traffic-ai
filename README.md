# Traffic AI V0.5.54 — Gate Path và Competitive Evidence

Nâng cấp trực tiếp từ full source V0.5.53. Đơn vị đếm là **lượt cắt vạch**: cùng một phương tiện quay lại và cắt vạch lần nữa được tính thêm một lượt.

## Benchmark đầu vào V0.5.53

Hai screenshot mới ghi nhận session 157 / benchmark 36:

| Chỉ số | V0.5.53 |
|---|---:|
| Ground truth | 149 |
| AI đếm | 154 |
| Khớp | 136 |
| Lọt không đếm | 13 |
| Đếm dư | 18 |
| Recall | 91.3% |
| Precision | 88.3% |
| F1 | 89.8% |
| Class đúng | 97.1% |
| Sai loại | 4 |

Worker đề xuất 234 event, backend gộp 80, Human Guard loại 37. Lọt gồm anchor span 5, gần vạch chưa span 3, center-only 1 và cooldown 4. Dư gồm rescue 8, direct 5, interpolation 4 và gần GT đã khớp/cùng điểm cắt 1. Tổng đếm/khớp chưa đổi so với V0.5.52; class đúng giảm từ 98.5% xuống 97.1%.

Đã đọc hai screenshot và giải nén an toàn 233 snapshot JPG, kích thước 1440 × 811, frame 3–23454. Tại 01:18.730, GT motorcycle nhưng event AI bicycle; crop frame 1971 cho thấy người áo đỏ đội mũ trên xe máy, trong khi overlay trước context vẫn ghi motorcycle. Tại 04:49.450, người áo xanh dắt xe đạp có giỏ cạnh xe máy đỏ đứng yên vẫn được AI gán motorcycle. Hai lỗi class còn lại không hiển thị trong phần screenshot đã gửi; không suy diễn chúng từ nhãn snapshot.

Snapshot không có điểm model context đầy đủ hoặc quỹ đạo liên tục. Clip hoàn chỉnh chưa có trong môi trường đóng gói. Các số trên là **đầu vào V0.5.53**; chưa có benchmark replay V0.5.54.

## Thay đổi V0.5.54

### Road Zone xét đường đi quan sát được

Cả bốn gate dùng bracket thực chứng minh đổi phía và các điểm quan sát trên đường đi để kiểm tra Road Zone. Chord nối hai stable endpoints không còn thay thế bracket cắt vạch thực. Giữ các điều kiện finite segment, jump, anchor margin và normal motion.

Anchor pending đã hết hạn hoặc bị loại không được mở lại từ cùng đoạn history với deadline mới. History thực sự về sau vẫn có thể chứng minh một lượt quay lại. External crossing kiểm tra frame geometry hữu hạn, không lớn hơn frame phát sự kiện và phải mới hơn crossing đã chấp nhận. Khi nối alias, armed/cooldown excursion đi cùng passage mới nhất.

### Bằng chứng xe đạp phải thắng bằng chứng xe máy

Context matcher giữ giới hạn khoảng cách tâm ngay cả khi hai box có độ overlap lớn. Accumulator bỏ confidence bằng zero/không hữu hạn và gộp callback trùng frame/class/source trước khi giới hạn history; dữ liệu trùng không đẩy các frame thật ra khỏi lịch sử.

Temporal rescue chỉ dùng các frame trước crossing mà xe đạp thắng bằng chứng xe máy, với diversity từ các nguồn thắng thực. Frame hòa, nguồn có điểm zero hoặc source chỉ thắng ở frame hiện tại không được mượn làm hỗ trợ thời gian. Mọi nhánh context rescue dùng cùng motor veto trên observation gốc, kể cả observation chỉ có motorcycle. Crossing được chấp nhận tiêu thụ evidence của passage vừa kết thúc và giữ evidence mới hơn.

Ngân sách class refine trước crossing cũng dùng khoảng cách tới **đoạn vạch hữu hạn**; track gần phần kéo dài của đường thẳng không chiếm slot refine của xe gần vạch thật. Không thay đổi các ngưỡng phân loại hoặc dedup toàn cục, không ép class theo timestamp GT.

### Context chỉ có hiệu lực cho crossing được xác nhận

Pipeline thật đề xuất class với `commit=False`. Chỉ sau khi Human Guard chấp nhận mới tăng rescue metrics; pending bị loại hoặc hết hạn không được tính như crossing đã cứu. Kết quả context của một crossing không tạo TTL override cho lượt kế tiếp.

Trace lưu frame quan sát gốc, nhánh quyết định, điểm xe đạp/xe máy từng nguồn và trạng thái proposed/pending/accepted/rejected/expired. EOF ghi trạng thái hết hạn mà không giả lập thêm frame inference hoặc làm tăng diagnostic delta. Lỗi ghi trace không ngăn cleanup crossing pending và shutdown.

Báo cáo **Sai loại phương tiện** truy vấn trace theo thời gian event AI, lọc đúng tracking ID và có mục mở rộng **Bằng chứng phân loại xe đạp**. Đề xuất của model và kết quả xác nhận crossing được hiển thị riêng. Trace mới chỉ có với session chạy V0.5.54; session cũ không được tự tạo evidence.

### Session và báo cáo giữ đúng camera/lượt chạy

Backend kiểm tra session tồn tại và thuộc camera trước khi trả lại event dedup. Event gửi trễ sau finish cập nhật tổng persisted của đúng session. Finish retry giữ lần ended_at đầu tiên; finish/start-error/stop cũ không ghi đè trạng thái camera đã thuộc session mới hơn.

Benchmark audit chọn candidate gần điểm cắt nhất trong radius hiện có và tie-break ổn định, thay vì chỉ chọn candidate đầu tiên trong radius. Giữ scoring, GT và cửa sổ ghép; miss_reason_counts chỉ tính các lượt lọt.

Các số Fast/Bracket/Late/adaptive là diagnostic ở bước candidate validation, không phải tổng event đã lưu sau Human Guard/backend dedup. Rescue semantic được ghi sau khi crossing được xác nhận.

## Version, môi trường và database

| Thành phần | Giá trị |
|---|---|
| VERSION / Frontend / Backend / AI Service | 0.5.54 |
| Alembic head | `0068_gate_semantics_v0554` |
| Parent | `0067_candidate_evidence_v0553` |
| schema_version | 0.5.54 |
| npm trong Docker / CI / packageManager | 12.2.0 |
| Node.js trong Docker / CI | 26.10.0 |

Migration chỉ cập nhật schema version, không xóa GT/dữ liệu. Giữ frame sạch cho model, backend semantic shadow và bố cục Camera Preview / Vehicle Count, GT / Report 50/50.

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

Publish tự đọc VERSION để tạo tag **v0.5.54**, mặc định repository `TamNhien/traffic-ai`. Script kiểm thử source đã chuẩn hóa, commit/push/tag, chờ đúng Actions run theo tag/SHA/push và tạo Release có ZIP, TAR.GZ, README, SHA256SUMS. Fallback CLI bổ sung đủ asset từ tag và hoàn tất Release tạo dở.

Nếu bị gián đoạn, xử lý lỗi mạng/quyền truy cập rồi chạy lại `publish.ps1` khi source không đổi. Thay đổi source sau tag đã có cần tăng version; script không di chuyển hoặc ghi đè tag. `-NoWait` chỉ đẩy source/tag rồi trả về khi Release còn đang chờ.

Đổi repository đích hoặc chạy lại workflow của tag đã có:

```powershell
.\scripts\publish.ps1 -Owner TEN_GITHUB -Repository TEN_REPO

gh workflow run release.yml --repo TamNhien/traffic-ai -f tag=v0.5.54
```

Khi dùng npm ngoài Docker trên Windows, Node.js cần 26.10.0 trở lên:

```powershell
npm install -g npm@latest
npm --version
```

Chi tiết kiểm tra thực hiện và giới hạn môi trường đóng gói có trong `VERIFICATION.md`.
