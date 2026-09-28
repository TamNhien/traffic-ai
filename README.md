# Traffic AI V0.5.46 — Precision Closure 9.2 + Passage Cycle State + Reverse Shadow Guard

V0.5.46 tiếp tục trực tiếp từ benchmark V0.5.45 mới nhất của `clip1(6).mp4` / `camera_1(20260928-125922).rar`: **GT 149 / AI 178 / khớp 141 / lọt 8 / dư 37 / Recall 94.6% / Precision 79.2% / F1 86.2% / class đúng 98.6%**. Recall đã cao hơn nhưng over-count tăng mạnh, vì vậy bản này **không mở Gate thêm** mà tập trung đóng duplicate/reversal false-positive.

## Thay đổi chính

- **Passage Cycle State 2.0:** `counted_directions` không còn bị xóa chỉ vì track đi xa khỏi vạch. Gate chỉ cho phép cùng canonical track phát lại cùng hướng sau khi đã có một crossing **hướng ngược lại** được xác nhận. Chuỗi thật `IN → OUT → IN` vẫn đếm đủ; bounce/jitter `IN → ... → IN` bị chặn.
- **Fresh-history re-arm:** khi track rời dead-band và Gate được arm lại, history được reset về observation hiện tại; không tái sử dụng cặp điểm trước crossing để phát một event OUT/IN muộn từ lịch sử cũ.
- **Production re-arm guard:** `AI_GATE_PASSAGE_REARM_MIN_FRAMES=16` để adaptive cooldown không cho đảo hướng quá sớm, nhưng không biến tracking ID thành unique suốt phiên. `start.ps1` tự migrate đúng default cũ `10 → 16`, còn giá trị custom khác được giữ nguyên.
- **Same-track physical short-cycle closure:** backend chặn same-direction repeat trong ≤4 s / ≤100 frame bất kể box crossing-point rung; opposite-direction flip trong ≤3 s cũng fail-closed. Event thật ở chu kỳ sau vẫn được lưu.
- **Cross-ID Reverse Shadow Guard:** một `rescued/interpolated` event đổi ID và đổi hướng ngay sát cùng điểm cắt có thể bị gộp; `direct/direct` opposite-direction luôn được giữ để không nuốt hai xe thật chạy ngược chiều.
- **Telemetry mới:** `Gate cùng hướng loại` và `FP reverse shadow` để replay sau biết closure nào đang thực sự giảm dư.
- **RAR audit:** các frame mới tiếp tục cho thấy mật độ xe máy quanh vạch cao và box/tracker có thể đổi ID/hướng trong vài frame; do đó V0.5.46 chỉ nới dedup ở same-track physical cycle hoặc secondary reverse-shadow cực gần, không dùng global cooldown rộng.

## Version / Database

- `VERSION = 0.5.46`
- Frontend / Backend / AI Service = `0.5.46`
- Alembic head: `0060_precision_closure_v0546`
- `schema_version = 0.5.46`
- Migration chỉ cập nhật marker version; không xóa camera, event, session, benchmark, ground truth, dataset, training run hay model.

## Kiểm thử V0.5.46

- AI Service: **163/163**
- Backend: **38/38**
- Tổng Python unit tests: **201/201**
- Có regression cho Passage Cycle State, stale-history re-arm, same-track physical short-cycle và cross-ID reverse-shadow.

Môi trường đóng gói không thay thế vòng Windows/Docker/Node production trên máy đích. Trước khi publish hãy chạy `./scripts/test.ps1` trên máy Windows của dự án.

## Lệnh dùng trên Windows

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
.\scripts\verify-database.ps1
```

Sau khi replay/benchmark ổn, phát hành bằng một lệnh:

```powershell
.\scripts\publish.ps1
```
