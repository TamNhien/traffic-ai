# Traffic AI V0.5.75 — Replay Drift Audit

Session #177 → #178

> **Không phải điểm benchmark GT.** Replay pairs are time/position/direction candidates, not proven physical vehicle IDs. Trace metadata has no clip SHA-256; verify that the videos are identical. Only a complete Ground Truth benchmark can determine missed/extra counts.

| Chỉ số | Lần trước | Lần sau |
|---|---:|---:|
| Crossing đề xuất | 192 | 192 |
| Event được ghi | 153 | 153 |
| Event bị chống trùng | 39 | 39 |

| Dấu hiệu biến động | Số lượt |
|---|---:|
| Đề xuất ghép gần nhau | 192 |
| Đề xuất chỉ có lần trước | 0 |
| Đề xuất chỉ có lần sau | 0 |
| Đề xuất đổi quyết định | 0 |
| Event ghi DB ghép gần nhau | 153 |
| Event DB chỉ có lần trước | 0 |
| Event DB chỉ có lần sau | 0 |
| Đề xuất lệch timecode >2 frame | 0 |

## Sự kiện cần kiểm tra (timecode theo video)

### Đổi quyết định

Không có.

### Mất event DB so với lần trước

Không có.

### Event DB mới xuất hiện

Không có.

## Kết luận có giới hạn

Các chênh lệch nêu trên là **biến động giữa hai lượt phát lại**, không thể tự gán là GT lọt hoặc đếm dư. Để sửa thuật toán dựa trên bằng chứng, hãy xuất **Tải hồ sơ benchmark** cho đúng phiên đã chạy và đánh giá bằng `scripts/check-benchmark.ps1`.
