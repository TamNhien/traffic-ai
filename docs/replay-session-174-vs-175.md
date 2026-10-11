# Traffic AI V0.5.75 — Replay Drift Audit

Session #174 → #175

> **Không phải điểm benchmark GT.** Replay pairs are time/position/direction candidates, not proven physical vehicle IDs. Trace metadata has no clip SHA-256; verify that the videos are identical. Only a complete Ground Truth benchmark can determine missed/extra counts.

| Chỉ số | Lần trước | Lần sau |
|---|---:|---:|
| Crossing đề xuất | 195 | 192 |
| Event được ghi | 149 | 153 |
| Event bị chống trùng | 46 | 39 |

| Dấu hiệu biến động | Số lượt |
|---|---:|
| Đề xuất ghép gần nhau | 187 |
| Đề xuất chỉ có lần trước | 8 |
| Đề xuất chỉ có lần sau | 5 |
| Đề xuất đổi quyết định | 6 |
| Event ghi DB ghép gần nhau | 148 |
| Event DB chỉ có lần trước | 1 |
| Event DB chỉ có lần sau | 5 |
| Đề xuất lệch timecode >2 frame | 2 |

## Sự kiện cần kiểm tra (timecode theo video)

### Đổi quyết định

- 75.658s → 75.658s · deduplicated (secondary-shadow-signature) → created (-)
- 242.719s → 242.696s · deduplicated (same-track-repeat-jitter) → created (-)
- 246.720s → 246.720s · deduplicated (crossing-signature) → created (-)
- 492.168s → 492.200s · deduplicated (same-track-repeat-jitter) → created (-)
- 606.090s → 605.957s · deduplicated (same-track-direction-flip) → deduplicated (secondary-reverse-shadow)
- 606.267s → 606.266s · deduplicated (same-track-repeat-jitter) → deduplicated (two-wheel-spatial-signature)

### Mất event DB so với lần trước

- 392.218s / frame 9806 · OUT motorcycle · rescued @ [0.67135, 0.40475]

### Event DB mới xuất hiện

- 69.716s / frame 1744 · OUT motorcycle · interpolated @ [0.57849, 0.42575]
- 242.696s / frame 6068 · OUT motorcycle · rescued @ [0.67424, 0.4041]
- 290.064s / frame 7253 · OUT motorcycle · interpolated @ [0.45029, 0.45474]
- 692.547s / frame 17315 · IN motorcycle · interpolated @ [0.46254, 0.45197]
- 904.040s / frame 22602 · OUT motorcycle · direct @ [0.38313, 0.46993]

## Kết luận có giới hạn

Các chênh lệch nêu trên là **biến động giữa hai lượt phát lại**, không thể tự gán là GT lọt hoặc đếm dư. Để sửa thuật toán dựa trên bằng chứng, hãy xuất **Tải hồ sơ benchmark** cho đúng phiên đã chạy và đánh giá bằng `scripts/check-benchmark.ps1`.
