# Traffic AI V0.5.48 — Benchmark Closure 9.4

V0.5.48 tiếp tục từ V0.5.47 theo benchmark hiện tại **GT 149 / AI 155 / khớp 136 / lọt 13 / dư 19**. Mục tiêu của bản này là xử lý hai điểm còn nổi bật trong audit mà không mở Gate toàn cục: một số **Verified Anchor Span tức thời** đã đủ hình học nhưng bị primary cooldown từ chối ở bước hand-off; đồng thời benchmark vẫn còn một đuôi nhỏ event **direct/direct gần như cùng điểm cắt**.

## Điểm chính V0.5.48

- **Transactional Immediate Span Handoff:** Verified Anchor Span thuộc nhánh immediate vốn đã bắt buộc finite segment + normal motion mạnh + side depth mạnh + gap rất ngắn. V0.5.48 giữ nguyên các điều kiện đó nhưng chuyển trạng thái `override_qualified` sang primary counter khi hand-off, tránh trường hợp rescuer tự commit nhưng `register_external_crossing()` từ chối vì cooldown và làm mất event thật.
- **Không mở same-direction/cooldown toàn cục:** chỉ immediate span đủ chuẩn, post-confirm span và lost-finalize span được quyền bypass có điều kiện. Crossing thường, rescue thường và track chỉ “tới sát vạch” vẫn fail-closed.
- **Direct Ultra-Spatial Shadow Guard:** bổ sung closure cho cross-ID `direct/direct` cùng class, cùng hướng, chỉ khi chênh thời gian `<= 0.42 s` và điểm cắt chuẩn hóa cách nhau `<= 0.006`. Đây là vùng cực hẹp nằm ngoài generic `0.22 s`, nhằm xử lý các event dư “sát GT đã khớp + cùng điểm cắt” mà không gom hai xe thật chạy gần nhau theo điều kiện rộng.
- **Giữ Precision Closure 9.2/9.3:** same-track repeat, direction flip, secondary shadow, reverse shadow, long-gap rescue guard, passage-cycle state và Human Guard không bị nới.
- Telemetry mới: `Span tức thời +` và `FP direct-shadow`.
- Dashboard/Benchmark tiếp tục giữ bố cục 50/50 và scrollbar gutter của V0.5.47.

## Version / database

- `VERSION = 0.5.48`
- Frontend / Backend / AI Service = `0.5.48`
- Alembic head: `0062_benchmark_closure_v0548`
- `schema_version = 0.5.48`

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

`publish.ps1` tiếp tục chạy test → commit/push → tag theo `VERSION` → GitHub Actions → GitHub Release → upload ZIP/README.

## Baseline benchmark dùng để nâng cấp

V0.5.47: **GT 149 / AI 155 / khớp 136 / lọt 13 / dư 19 / Recall 91.3% / Precision 87.7% / F1 89.5% / class đúng 98.5%**. V0.5.48 tập trung vào miss do cooldown/handoff của span đã được chứng minh và FP direct-shadow cực sát; số liệu cuối cần được xác nhận lại bằng replay chính clip/camera của bạn sau khi chạy source mới.
