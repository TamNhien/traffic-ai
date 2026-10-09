# Traffic AI V0.5.66 — Chuẩn bị Ground Truth trước khi chấm benchmark

Nâng cấp từ đúng full source **V0.5.65 đã giao**. Bản này bổ sung trạng thái sẵn sàng benchmark và giữ bản sửa van chở hàng thành **Xe tải**. Đơn vị đếm là lượt cắt vạch; một xe quay lại cắt vạch lần nữa được tính thêm một lượt.

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

# Tự test, commit, push GitHub, tạo tag v0.5.66 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443 và **Ctrl+F5**. Với benchmark48, bấm sao chép149GT từ **benchmark47** nếu clip/vạch tương thích. Review GT van quanh10:41.93OUT và14:42.29IN theo quy ước van chở hàng là Xe tải; giữ timecode/hướng theo clip đã kiểm tra. Đối chiếu lại rồi Tải hồ sơ benchmark để có cả GT và AI assignments cho lần phân tích tiếp theo.

Publisher lấy version từ VERSION, kiểm tra source trước khi commit/push/tag và tạo Release. Không force hoặc viết lại tag cũ. Muốn publish cần Git/GitHub CLI, tài khoản đã đăng nhập và quyền vào repository. Lệnh trên thực hiện xuất bản khi bạn chạy; quá trình kiểm tra bản này chỉ dùng Git cục bộ, chưa push hoặc tạo Release thật.

## Phiên bản công nghệ và kiểm tra

VERSION/frontend/API health/start message đồng bộ0.5.66. Alembic head 0080_benchmark_ready_v0566, parent 0079_van_semantics_v0565; migration chỉ cập nhật schema_version0.5.66, downgrade về0.5.65, không thay GT/events/schema.

Docker/CI/packageManager giữ npm12.2.0 và Node26.10.0. npm12.2.0 được đối chiếu [official npm CLI latest](https://github.com/npm/cli/releases/latest) ngày09/10/2026. PowerShell scripts UTF-8 no-BOM/CRLF; source/config text khác LF.

Kết quả cụ thể và phạm vi thực thi nằm trong **VERIFICATION.md**. Offline assertions dùng algorithm modules thực và worker/backend helper trích AST; frontend kiểm bằng Babel/Node VM và JSX có kiểm soát. Môi trường hiện tại không chạy full dependency-pinned pytest, HTTP/ORM/database, native PowerShell, Docker, Vite/browser/GPU/model replay. Không có F1/class accuracy .66 được đo từ clip.
