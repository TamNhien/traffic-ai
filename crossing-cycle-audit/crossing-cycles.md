# Kiểm tra chu kỳ qua vạch · Benchmark #65

- 150 event AI; 5 cặp dùng chung canonical ID trong 12 giây.
- 2 cặp có ít nhất một event AI chưa khớp GT.
- 3 cặp có bằng chứng raw ID khác nhau ở khung hình gần event.
- Không loại/trừ event hoặc tính lại F1 tự động.

| Hai event AI | Thời gian (s) | Hướng | Track | Raw-ID evidence | GT dư? |
|---|---:|---|---:|---|---|
| 12992 → 12996 | 8.570 | out → in | 86667 | raw_alias_changed | Không |
| 12998 → 13000 | 8.195 | out → in | 95080 | insufficient_frame_witness | Không |
| 13030 → 13031 | 7.041 | out → in | 175996 | raw_alias_changed | Không |
| 13044 → 13045 | 5.995 | in → out | 248105 | raw_alias_changed | Có |
| 13077 → 13079 | 3.608 | in → out | 345897 | same_raw_observed | Có |

**Lưu ý:** Một xe quay lại cắt vạch được tính thêm lượt. Cùng ID không chứng minh cùng xe.
