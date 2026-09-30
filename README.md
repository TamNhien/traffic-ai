# Traffic AI V0.5.49 — Precision Recovery Closure 9.5

V0.5.49 tiếp tục trực tiếp từ V0.5.48 theo replay mới: **GT 149 / AI 156 / khớp 136 / lọt 13 / dư 20 / Recall 91.3% / Precision 87.2% / F1 89.2% / class đúng 98.5%**. So với mốc V0.5.47 (AI 155 / dư 19), V0.5.48 tăng đúng một event dư sau khi mở transactional hand-off cho Immediate Verified Anchor Span. Bản này đóng lại nhánh rủi ro đó nhưng giữ các recovery đã có bằng chứng hậu-vạch.

## Điểm chính V0.5.49

- **Immediate Span cooldown rollback:** Immediate Verified Anchor Span vẫn được phát hiện và vẫn có thể đăng ký khi primary gate hợp lệ, nhưng không còn quyền bypass `same-direction`/`cooldown`. `Post-Confirm` và `track-lost finalize` vẫn được `verified_anchor_span` override vì có thêm bằng chứng phía sau vạch.
- **Canonical-Lineage Rescue Guard:** long-gap `rescued` trên canonical track đã đổi raw ByteTrack ID phải có thêm destination-side confirmation hoặc geometry mạnh hơn (normal motion, side depth, jump bound). Direct crossing và single-ID rescue không bị siết.
- **Direct → Secondary Shadow Closure:** bổ sung dedup cực hẹp cho cặp cùng class/cùng hướng có đúng một `direct` và một `rescued/interpolated`; `direct/direct` không bị mở rộng thêm.
- **Giữ Precision Closure cũ:** same-track repeat, direction flip, secondary/reverse shadow, long-gap guard, Human Guard, passage-cycle state và Direct Ultra-Spatial Shadow của V0.5.48 vẫn giữ nguyên.
- **Telemetry mới:** `Span tức thời loại`, `Lineage rescue loại`, `FP cross-method`; `Span tức thời giữ` là immediate candidate được primary gate chấp nhận bình thường, không còn là cooldown override.
- Dashboard Camera Preview / Vehicle Count và Ground Truth / Benchmark Report tiếp tục cân 50/50, các list audit giữ `scrollbar-gutter` để không che nội dung.

## Version / database

- `VERSION = 0.5.49`
- Frontend / Backend / AI Service = `0.5.49`
- Alembic head: `0063_precision_recovery_v0549`
- `schema_version = 0.5.49`

## Kiểm thử

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
```

Khởi động:

```powershell
.\scripts\start.ps1
```

Mở `https://traffic-ai.test:8443` và nhấn `Ctrl + F5`.

Kiểm tra database:

```powershell
.\scripts\verify-database.ps1
```

Sau khi replay benchmark ổn, phát hành chỉ với một lệnh:

```powershell
.\scripts\publish.ps1
```

`publish.ps1` chạy test → commit/push → tag theo `VERSION` → GitHub Actions → GitHub Release → upload ZIP/README.

## Mốc benchmark

- V0.5.47: **GT 149 / AI 155 / khớp 136 / lọt 13 / dư 19 / Precision 87.7%**.
- V0.5.48 replay hiện tại: **GT 149 / AI 156 / khớp 136 / lọt 13 / dư 20 / Precision 87.2%**.
- V0.5.49 được thiết kế để trả Immediate Span về fail-closed khi cooldown/same-direction, đồng thời chặn rescue shadow sau ID-switch mà không nới Gate. Kết quả benchmark cuối phải được xác nhận bằng chính clip `clip1(9).mp4` và camera snapshot của phiên mới.
