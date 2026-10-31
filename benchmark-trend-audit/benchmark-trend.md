# Traffic AI — đối chiếu nhiều phiên benchmark (chỉ đọc)

- Các benchmark: **#88, #89, #90**
- Tất cả SHA-256 và GT/source/geometry tương thích: **True**.
- Chữ ký AI giống nhau giữa mọi lần: **True** (không chứng minh đúng GT).
- Chính sách AI hiệu lực giống nhau: **True**.
- Hồ sơ lỗi lần cuối: **13**, lặp qua tất cả phiên: **13**, mới: **0**.
- Các chỉ số chấm giữ nguyên: **True**.

| Timecode | Lỗi | Lặp tất cả | Trọng tâm cần xem |
|---|---|---|---|
| 00:00:54.294 | extra | Có | Rescued crossing gap |
| 00:00:58.984 | direction | Có | Direction conflict |
| 00:00:59.446 | missed | Có | Congested gate / close timestamps |
| 00:03:57.042 | missed | Có | Congested gate / close timestamps |
| 00:04:49.450 | class | Có | Vehicle-class conflict |
| 00:04:49.824 | missed | Có | Congested gate / close timestamps |
| 00:04:52.862 | extra | Có | Interpolated crossing / geometry |
| 00:06:46.488 | missed | Có | Congested gate / close timestamps |
| 00:09:51.091 | missed | Có | Bicycle detector / track / gate review |
| 00:10:41.981 | class | Có | Vehicle-class conflict |
| 00:12:34.558 | direction | Có | Direction conflict |
| 00:12:39.520 | extra | Có | Possible adjacent/duplicate tracks |
| 00:14:42.291 | extra | Có | Interpolated crossing / geometry |

## Giới hạn và an toàn
- Three matching runs do not prove the same physical vehicle identity.
- No auto-suppression, auto-counting, GT changes, DB edits or model fine-tuning is performed.
- Review actual video and contiguous trace before changing the counting or classification policy.
- The comparison is of recorded events, not an independent GPU replay.
