# Session #186 — Short-gap alias evidence, V0.5.85

**Nguồn:** `traffic-ai-benchmark-60-session-186.zip` (`benchmark-trace.jsonl.gz`, `events.json`, `ground-truth.json`, `report.json`) cùng RAR ảnh Session #186. Các mốc dưới đây là quan sát từ trace V0.5.84, **không phải benchmark GPU V0.5.85**.

- 23.650 frame; GT 149; AI 151; khớp timecode 138; lọt 11; dư 13; khớp nghiêm ngặt (hướng + loại + timecode) 134.
- Giây **606.000** (frame 15151): event `12173`, OUT / motorcycle / direct, track `234512`, điểm (0,663173; 0,406601). Report xếp vào nhóm dư.
- Giây **606.2309**: event `12174`, OUT / motorcycle / interpolated, track `235019`, điểm (0,619393; 0,416501), được ghép GT. Đây là **dấu hiệu cần xem lại** của cùng một xe qua hai ID, không thể quyết định xóa event chỉ từ khoảng cách điểm cắt.
- Frame **15143**: raw `235019` có center khoảng (1056,3; 502,0). Frame **15152**: token mới `235659` ở center khoảng (1181,2; 256,2). Điểm đến lệch xa cả quỹ đạo dự đoán lẫn kích thước hai bbox, nhưng thuật toán ghép cũ vẫn có thể lấy nhầm canonical ID vì dùng ngưỡng dựa trên toàn đường chéo ảnh.
- Frame **15154**: raw `235019` quay lại gần (963; 372). Nếu canonical đã bị token lạ chiếm, lịch sử hướng/anchor dùng để chấm crossing có thể bị nhiễu.

**Thay đổi V0.5.85:** kiểm tra footprint+predicted motion trước khi *stitch* Raw ID mới, chỉ cho xe hai bánh mất 4–12 frame; không sử dụng GT trong quyết định. Bài test tái hiện số liệu tại hai thời điểm này, kèm positive test cho xe chạy nhanh.

**Giới hạn:** dù guard chặn được pha stitch bất hợp lý trong test, không thể suy ra trực tiếp số GT khớp hoặc tổng sự kiện sau GPU replay. Cần phát lại video trên máy có model; giữ nguyên 149 GT và đối chiếu chính xác như lần trước.
