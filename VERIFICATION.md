# V0.5.85 — Verification and limitations

## Những phần đã kiểm chứng trong môi trường hiện tại

- AI Service: **655/655 pytest PASS**, bao gồm 4 test mới về alias bất thường, tiếp tục xe nhanh, xe 4 bánh và chế độ rollback.
- Backend: **178/178 pytest PASS** trong SQLite memory, với test token riêng cho CI.
- Backup Worker: **4/4 pytest PASS**.
- Frontend: **4/4 node --test PASS**.
- Công cụ: **47/47 unittest PASS**. Dòng `[FAIL]` của negative test replay là output kỳ vọng; unittest tổng kết OK.
- Tổng cộng **888/888 test đạt**. `scripts/version-contract.py` kiểm tra version và migration chain PASS.
- Lớp tương thích `httpx2` trong lúc test ở đường dẫn ngoài source; **không có trong ZIP**.

## Giới hạn quan trọng

- **Chưa chạy lại GPU/video nguồn** cho V0.5.85. Không có bằng chứng đã giảm 11 lượt lọt / 13 lượt dư ở Benchmark #60.
- **Chưa chạy Docker, PowerShell và Vite production build** trong môi trường này. `test.ps1` trên Windows sẽ kiểm tra chúng trước khi phát hành.
- Guard mới có thể tắt tạm bằng `AI_SHORT_GAP_ALIAS_GUARD=0` để so sánh, sau khi khởi động lại AI Service. Không thay đổi GT hoặc dữ liệu lịch sử.
- Không đóng gói video, trace camera, RAR, `.env` hoặc database người dùng.

## Phân tích nguồn

Xem `docs/session-186-alias-handoff-v0585.md`. Nhóm sự kiện tại 606 giây mới là giả thuyết có bằng chứng quỹ đạo; kết quả cuối phải được xác nhận bằng phiên replay mới.

---

## Xác minh V0.5.84 trước đó

# Traffic AI V0.5.84 - Verification

## Baseline: GT benchmark #59 / Session #185 (V0.5.83)

- Source video: 23,650 frames, 25 FPS.
- GT 149; AI 151; timecode matched 138; strict matched 134.
- Missed 11; extra 13; wrong-direction 2; wrong-class 2.
- The V0.5.84 source has **not** been GPU-replayed against the video; no
  claim of numerical improvement to GT recall or precision is made.

## Implemented

- Dual-provenance Raw ID Reuse Guard: inspect separately measured Raw ID
  trajectory AND canonical-alias handoff to avoid hiding a genuine ID jump
  behind another alias' recent coordinates. Large canonical alias jumps
  remain fail-closed to avoid manufactured vehicle passages.
- Raw observations are pruned with canonical TTL cleanup. The gate,
  cooldown, rescue, class refiners, existing direct-shadow protection,
  backend authorization, backup/restore and PostgreSQL schema are unchanged.
- Read-only ZIP raw-id audit now distinguishes **worker cumulative resets**
  from jumps present in **gate_tracks** sample. Timecodes and GT-nearness are
  review hints only, not proof of a causal relationship.
- V0.5.84 migration is metadata-only; no table schema change.

## Tests run in this environment

| Suite | Result |
|---|---:|
| Backend pytest (SQLite in-memory) | 178/178 PASS |
| AI Service pytest | 651/651 PASS |
| Backup Worker pytest | 4/4 PASS |
| Frontend node --test | 4/4 PASS |
| Scripts stdlib unittest | 47/47 PASS |
| **Total** | **884/884 PASS** |

- Source version/migration chain check: PASS.
- Benchmark #59 trace: gzip SHA-256 verified, 23,650 frames scanned;
  10 worker Raw-ID resets and 0 gate-sampled discontinuities.
- Worker reset nearby missed GT (within 2 seconds): at 58.280s and
  290.160s. This is **not** proof of a false reset or a recovered count.
- Backend/AI tests use a temporary `httpx2` compatibility shim located
  **outside** the ZIP because that dependency is not installed in the
  execution environment. Do not treat the shim as a substitute for a real
  Docker/runtime dependency test.
- Not executed here: PowerShell on Windows, Docker Compose startup,
  PostgreSQL restore, full Vite production build, GPU video replay and
  GitHub Actions on the remote runner.
- Before publishing, run `scripts/test.ps1`, then `scripts/start.ps1` on
  Windows, and compare a fresh GT benchmark. Retain Docker volumes and `.env`.
