# Traffic AI V0.5.53 — Candidate Eligibility và Passage Evidence

Nâng cấp trực tiếp từ full source V0.5.52. Đơn vị đếm là **lượt cắt vạch**: cùng một phương tiện quay lại và cắt vạch lần nữa được tính thêm một lượt.

## Benchmark đầu vào V0.5.52

Hai screenshot mới ghi nhận session 156 / benchmark 35:

| Chỉ số | V0.5.52 |
|---|---:|
| Ground truth | 149 |
| AI đếm | 154 |
| Khớp | 136 |
| Lọt không đếm | 13 |
| Đếm dư | 18 |
| Recall | 91.3% |
| Precision | 88.3% |
| F1 | 89.8% |
| Class đúng | 98.5% |

Worker đề xuất 237 event, backend gộp 83, Human Guard loại 37. Lọt gồm anchor span 5, gần vạch chưa span 3, center-only 1 và cooldown 4. Dư gồm rescue 6, direct 4, gần GT đã khớp/cùng điểm cắt 6 và interpolation 2.

Đã đọc hai screenshot và giải nén 236 snapshot JPG trong `camera_1(20261003-035459).rar`, kích thước 1440 × 811, từ frame 3 tới 23454. Tại 04:49.450, ảnh cho thấy người áo xanh dắt xe đạp có giỏ cạnh xe máy đỏ đứng yên; model gán motorcycle. Tại 10:41.981 là van kín trắng/xanh: GT car, model truck. Snapshot không đủ để kết luận taxonomy van hoặc kiểm chứng toàn bộ quỹ đạo của 13 lượt lọt.

Clip hoàn chỉnh chưa tải được vào môi trường đóng gói. Các số trên là **đầu vào V0.5.52**; chưa có kết quả replay V0.5.53.

## Thay đổi V0.5.53

### Anchor Span chỉ commit sau khi gate chính nhận

Immediate, post-confirm và lost-finalize cung cấp proposal cho worker. Worker dùng `commit=False`, chỉ ghi passage và rescue telemetry khi gate chính chấp nhận đúng proposal. Gate chính loại không làm mất clock/hướng của passage trước hoặc tiêu thụ sớm bằng chứng hậu-vạch.

Human Guard rollback phục hồi passage trước và hoàn tác rescue telemetry của proposal bị loại. Candidate không được chọn không tính như rescue. History của lượt đã chấp nhận được cắt khỏi phía tiếp cận cũ, tránh đề xuất lại cùng span khi cấu hình history dài. Khi nối alias, metadata crossing đi cùng passage đã chấp nhận mới nhất, không lấy max từ geometry của lượt khác.

### Bằng chứng giao vạch và clock nguồn

Đoạn cắt vạch thực không bị một lần chạm zero-distance rồi quay lại cùng phía ghi đè. Chạm vạch ngoài đầu đoạn hữu hạn sau crossing cũng không xóa crossing thật. Timecode lấy từ bracket chứng minh đổi phía; các guard finite segment, Road Zone, jump và normal motion được giữ.

Verified override không được ghi passage ở frame cũ hoặc cùng frame với passage đã chấp nhận. Override hợp lệ ở source frame mới tiếp tục dùng điều kiện geometry đang có.

### Bicycle Context dành ngân sách cho đoạn vạch thật

Pre-scan chỉ đưa vào hàng đợi track trên Road Zone, đủ điều kiện confidence và nằm trong bán kính hiện có quanh **đoạn vạch hữu hạn**. Khoảng cách tới đường thẳng kéo dài không còn làm track ở ngoài đầu vạch chiếm slot scan.

Context, class refiner và Human Guard không dùng frame cũ để ghi đè cache/override/evidence mới. Frame trùng không tạo thêm lượt inference hoặc thêm strike. Sau mỗi crossing được chấp nhận, kể cả class đã là bicycle, không còn slot context hoặc lost-finalize, trail được tiêu thụ; pre-scan xếp hàng từ trước trong cùng frame không gieo lại evidence cho lượt kế tiếp.

### Giữ bằng chứng phản đối motorcycle

Motor veto xét cả observation chỉ có motorcycle và mọi frame/nguồn đã match target, trước khi lọc bicycle confidence hoặc chọn source-best. Nhánh absolute/temporal rescue trong worker dùng cùng veto với near-margin và cross-frame.

Cross-frame cần bicycle thắng trên ít nhất hai source frame. Frame chỉ có bằng chứng thua không chứng minh temporal support. Frame bicycle thắng yếu hơn source-best vẫn được giữ để xét diversity. Giữ nguyên hai nguồn, hai frame, motor veto và các ngưỡng chấp nhận.

Truck Semantic Lock giữ đúng family, không đọc/refresh lock từ source frame cũ và không đưa confidence đã hết hạn sang lock mới. Không ép class theo hai timestamp trong benchmark.

### Backend xử lý đúng lượt cũ và thứ tự gửi

Retry cùng ID/hướng được đối chiếu với các passage của track trong session, thay vì chỉ event có database ID mới nhất. Retry của lượt IN cũ sau một chu kỳ IN → OUT → IN được trả lại event đã lưu, không tăng tổng.

Ưu tiên source seconds, rồi source frame, rồi thời gian nhận khi không còn clock nguồn để so. Fixed frame windows không ghi đè thời gian video ở FPS thấp; hai lượt thật gửi gần nhau không bị coi là retry chỉ vì wall clock gần nhau. Khi kiểm tra jitter, chọn passage lân cận theo nguồn thay vì thứ tự database.

Benchmark audit ưu tiên candidate gần điểm cắt, tránh cáo buộc xe ở làn khác chỉ vì timestamp gần hơn hoặc crossing direct/direct ngược hướng. Diagnostic thêm `near_matched_ai_event_id`; không đổi scoring, GT hay ngưỡng dedup.

## Version, môi trường và database

| Thành phần | Giá trị |
|---|---|
| VERSION / Frontend / Backend / AI Service | 0.5.53 |
| Alembic head | `0067_candidate_evidence_v0553` |
| Parent | `0066_observed_path_v0552` |
| schema_version | 0.5.53 |
| npm trong Docker / CI / packageManager | 12.2.0 |
| Node.js trong Docker / CI | 26.10.0 |

Migration chỉ cập nhật schema version, không xóa GT/dữ liệu. Giữ các guard V0.5.52, frame sạch cho model, backend semantic shadow và bố cục Camera Preview / Vehicle Count, GT / Report 50/50. Không hạ ngưỡng chấp nhận toàn cục.

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

Publish tự đọc VERSION để tạo tag **v0.5.53**, mặc định repository `TamNhien/traffic-ai`. Script kiểm thử source đã chuẩn hóa, commit/push/tag, chờ đúng Actions run theo tag/SHA/push và tạo Release có ZIP, TAR.GZ, README, SHA256SUMS. Fallback CLI bổ sung đủ asset từ tag và hoàn tất Release tạo dở.

Nếu bị gián đoạn, xử lý lỗi mạng/quyền truy cập rồi chạy lại `publish.ps1` khi source không đổi. Thay đổi source sau tag đã có cần tăng version; script không di chuyển hoặc ghi đè tag. `-NoWait` chỉ đẩy source/tag rồi trả về khi Release còn đang chờ.

Đổi repository đích hoặc chạy lại workflow của tag đã có:

```powershell
.\scripts\publish.ps1 -Owner TEN_GITHUB -Repository TEN_REPO

gh workflow run release.yml --repo TamNhien/traffic-ai -f tag=v0.5.53
```

Khi dùng npm ngoài Docker trên Windows, Node.js cần 26.10.0 trở lên:

```powershell
npm install -g npm@latest
npm --version
```

Chi tiết kiểm tra thực hiện và giới hạn môi trường đóng gói có trong `VERIFICATION.md`.
