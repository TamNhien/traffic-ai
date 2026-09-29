# Traffic AI V0.5.47 — Balanced Recall Recovery 9.3

V0.5.47 tiếp tục từ V0.5.46 và benchmark hiện tại: Recall cần được khôi phục nhưng **không quay lại over-count V0.5.45**. Bản này giữ nguyên Precision Closure 9.2 / passage-cycle / reverse-shadow của V0.5.46, chỉ mở recovery khi trajectory có bằng chứng hình học đủ mạnh.

## Điểm chính V0.5.47

- **Verified Anchor Span conditional override:** Gate cùng hướng không còn bị khóa tuyệt đối khi chính track đó đã chứng minh span qua **finite counting segment**. Same-direction candidate không được immediate-close; bắt buộc chờ xác nhận hậu-vạch hoặc track-loss closure mạnh.
- **Cooldown override có điều kiện:** chỉ secondary Verified Anchor Span đã qua finite segment + normal motion + side depth + post-side/lost strong confirmation mới được vượt cooldown. Primary Gate và các rescue khác giữ nguyên cooldown.
- **Pending crossing track-loss finalization:** pending span đã qua đầy đủ geometry/road/motion validation được finalize nếu track biến mất ngay sau vạch và evidence đạt ngưỡng mạnh. Disappearance tự nó không tạo crossing. Two-wheel đang Human Guard pending/rejected vẫn fail-closed.
- **Giữ FP closure V0.5.46:** same-track repeat jitter, direction flip, secondary shadow, reverse shadow và long-gap rescue-tail guard không bị nới.
- Telemetry mới: `Span cùng hướng +`, `Cooldown span +`, `Track mất finalize`.
- Dashboard: `Camera Preview` / `Vehicle Count` cân 50/50 trên desktop. Benchmark `GT` / `Report` cân 50/50; các danh sách `Sai loại`, `Lọt`, `Dư` dùng cùng width/padding và scrollbar gutter ổn định.

## Version / database

- `VERSION = 0.5.47`
- Frontend / Backend / AI Service = `0.5.47`
- Alembic head: `0061_balanced_recall_v0547`
- `schema_version = 0.5.47`

## Kiểm thử

Chạy:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
```

Start:

```powershell
.\scripts\start.ps1
```

Mở `https://traffic-ai.test:8443` và nhấn `Ctrl + F5`.

Database:

```powershell
.\scripts\verify-database.ps1
```

Publish sau khi replay benchmark ổn:

```powershell
.\scripts\publish.ps1
```

Script publish tiếp tục chạy test → commit/push → tag theo VERSION → GitHub Actions → GitHub Release → upload ZIP/README.

## Baseline tham chiếu

V0.5.45: GT 149 / AI 178 / khớp 141 / lọt 8 / dư 37 / Recall 94.6% / Precision 79.2% / F1 86.2% / class đúng 98.6%. V0.5.47 nhắm phục hồi Recall so với V0.5.46 bằng recovery có điều kiện, không mở Gate toàn cục.
