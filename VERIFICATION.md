# V0.5.90 — Verified AI-only comparison for unscored benchmark exports

- Input: integrity-verified `traffic-ai-benchmark-62-session-188.zip` (GT 149) and `traffic-ai-benchmark-63-session-190.zip` (GT 0, exported before copy).
- Confirmed identical 150 persisted event signatures, 0 added/removed; reports **no GT metric comparison** because the second ZIP has no GT.
- Later screenshot shows GT 149 / AI 150 / matched 138 / missed 11 / extra 12 / F1 92.3%; those results are NOT in the attached older ZIP.
- Comparison tool validates all six manifest-tracked JSON documents, trace digest, session ID, conservation of AI event count, persistence integrity, video/gate/FPS geometry. For scored pairs it retains existing GT fingerprint/tolerance check and benchmark-gate conservation tests.
- Eleven new tests (including five verified error-queue tests) cover unscored-to-scored, scored-to-unscored, changed AI signatures, forged score, tampered hash, incompatible FPS.
- No inference algorithm change, no measured F1 improvement. Windows/Docker/GPU testing still required by the user.

---

# V0.5.89 — Release packaging, immutable tag safety

- Source from V0.5.88 ZIP; new metadata-only migration `0103_release_eol_v0589`.
- Packaged PowerShell file line endings are CRLF (before any Windows publish run).
- `.gitignore` now excludes downloaded root-level benchmark ZIPs, camera RARs
  and benchmark comparison output (previously eligible for git add -A).
  A publish guard rejects those artifacts if they were already staged.
- `publish.ps1` still refuses to move an existing local/remote Git tag; logs only
  names and statuses of changed files, not file contents.
- Windows V0.5.88 user's supplied log independently verifies existing official
  `test.ps1`, Docker image build/start, GPU service readiness and local HTTPS.
- Local checks after V0.5.89 changes: 660 AI pytest, 178 backend pytest,
  4 backup worker pytest, 60 scripts unittest, 8 frontend node tests:
  **910/910 tests passed**. Backend test environment used a temporary test-only
  `httpx2` shim outside the packaged ZIP; not a substitute for Docker testing.
- Existing-tag error occurred before source push; v0.5.89 publish on Windows
  and GitHub Actions has NOT been executed here.
- No changes to inference or benchmark comparison outcomes; the baseline of
  GT 149 / AI 150 / missed 11 / extra 12 is not claimed to improve.
- Git status in user's repository cannot be inspected from this ZIP; existing
  tag + pending changes may have causes besides CRLF normalization.

---

# V0.5.88 — Verification and limitations

- Root cause: V0.5.67 PowerShell contract pinned obsolete literal `Tổng GT = AI`,
  but V0.5.87 frontend correctly supports competition review when totals differ.
- Refactored presentation predicate into JS module covered by four focused tests.
- Contract now checks the predicate integration, both audit fields, backend regression,
  and explicit equal/unequal count frontend regression cases.
- No AI inference, crossing thresholds, GT marks or benchmark event data modified;
  no measured F1 improvement claimed.
- **Local automated verification:** AI 660/660 (pytest), backend 178/178 (SQLite-memory
  pytest), scripts 55/55 (Python unittest), backup worker 4/4 (pytest), frontend 8/8
  (Node built-in test runner): **905/905**. All Python `compileall` and
  `scripts/version-contract.py` passed.
- The Alembic revision name initially exceeded the historical 32-character limit;
  it was shortened to `0102_temporal_review_v0588` (26 chars). Version checker now
  fails on future oversized migration IDs and has a regression test.
- Backend/AI test runs used a temporary **test-only** `httpx2` import shim outside
  the ZIP because `httpx2` is not installed here; this is not validation of the
  production dependency. Linux Node 22 executed the JS test runner; Vite production
  build requires the project's configured Node 26 environment.
- **Not run:** Windows PowerShell `scripts/test.ps1` as a whole, Docker image builds,
  Windows startup, PostgreSQL integration, Vite production build and GPU inference.
  Rerun the full official test script on the user's Windows host before publishing.

---

# V0.5.87 — Verification and limitations

- Validated completed Benchmark #61 and #62 source archive hashes, compared GT/event crossing signatures, reviewed trace and selected camera JPEGs. The before/after GT 149 / AI 150 / matched 138 / missed 11 / extra 12 is **unchanged**.
- New script `compare-benchmark-exports.py` is read-only; never relabels GT or emits new AI events. New frontend temporal audit block fixes hidden review when GT 149 differs from AI 150.
- Full inference replay with GPU/model/MP4, Windows Docker stack and real PowerShell tests must be performed on the user's machine. No new precision/recall claims.

---

# V0.5.86 — Verification and limitations

- Benchmark #61 / Session #187 ZIP fully validated by the bundled read-only forensic tool (trace compressed/uncompressed SHA256, metadata, delivery drain). Baseline: GT149 AI150 matching138 missed11 extra12, direction2 and class2 mismatches; **these are V0.5.85 values**.
- JPEG RAR inspected with libarchive: 190 images, specific frames 7243, 16050, 22059 visually reviewed. No model weights / original MP4 were supplied in the source ZIP; no GPU inference or 23,650-frame replay done here.
- `tests/test_tracking.py` adds 5 regression scenarios for the new two-wheel 4–12-frame visible-incumbent reservation; existing main counts/gate algorithms unchanged. Before claiming quality improvement, rerun clip and export new benchmark/trace.
- Sandbox automated verification: **660/660 AI pytest**, **178/178 backend pytest** (in-memory SQLite), **4/4 backup-worker pytest**, **47/47 scripts unittest**, **4/4 frontend Node tests** = **893/893 tests passed**. Benchmark forensics validated the supplied ZIP with both compressed and decompressed trace SHA-256, and produced 23 audited cases. Full Python `compileall` passed, `scripts/version-contract.py` passed, TypeScript JSX parser reported **0 syntax diagnostics** for the frontend.
- Missing native `httpx2` package was replaced with a **test-only** `httpx→httpx2` compatibility alias placed outside the ZIP; this is not production validation of `httpx2`. Backend tests used `DATABASE_URL_OVERRIDE=sqlite+pysqlite:///:memory:`; PostgreSQL/live services were not started.
- **Not executed**: `scripts/test.ps1` under Windows PowerShell, Docker stack, GPU/video replay, frontend Vite production build, full HTTP system integration and publish/GitHub Actions. Run `scripts/test.ps1` on the target Windows machine before publishing.

---

## Verification of previous versions

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
