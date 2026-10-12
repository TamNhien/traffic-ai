# Traffic AI V0.5.83 — Verification

- Source: full source V0.5.82 + V0.5.83 benchmark direction evidence, UI and
  `gt-replay-witness` CLI. One Alembic head: `0097_direction_audit_v0583`.
- Baseline benchmark #57 Session #182: **GT 149 / AI 152 / timecode matched 139 /
  missed 10 / extra 13**, plus **3 wrong-direction pairs, 2 wrong-class pairs,
  134 pairs correct on all three dimensions**.
- Session #183 raw trace extracted from `camera_1(20261012-142939).rar`:
  replay delta **DB 152 -> 151**, removed **1**, introduced **0**, decision flips **0**.
  Lost 290.064s OUT event had a wrong-direction historical match with GT IN
  at 289.824s. Not proof of a newly missed *physical* vehicle.
- Executed tests: **Backend 178/178, AI Service 646/646, Backup Worker 4/4,
  frontend Node unit 4/4, offline tooling/versions/replay/GT witness 45/45**.
  Total **877/877 tests passed**. Backend and AI used a temporary compatibility
  wrapper for unavailable `httpx2` in the test environment; not shipped in source.
- `scripts/version-contract.py` **PASS**; Python compile and ZIP integrity check
  are separate from GPU/Docker validations.
- Limitations: Vite production build was not verified because npm could not
  download required packages in this environment. No Windows PowerShell, live
  Docker migration or GPU counting replay was executed here. The algorithm
  counting thresholds remain unchanged, so **11 missed / 13 extra have not
  been fixed or verified to improve**.

---

# V0.5.82 — Verification (Raw ID Reuse Guard)

- Input: `traffic-ai-v0.5.81-full-source.zip` and user-provided `traffic-ai-benchmark-57-session-182.zip` (GT=149, saved AI=152, matched=139, missed=10, extra=13).
- Actual code changes: `ai-service/app/tracking.py` adds a guarded fresh canonical for implausible short-gap same-raw-ID teleport; prevents immediate re-stitch with detached canonical; worker tracks telemetry. New `Raw ID reset` appears in state API, dashboard, and gate trace. Does NOT change GT, database crossing assignments, model weights or global Gate/rescue thresholds.
- Diagnostic CLI `scripts/raw-id-audit.py` validates SHA-256 compressed trace against manifest, streams frame evidence, outputs read-only JSON/Markdown. On Benchmark #57 Session #182: 23,650 frames, 0 qualifying large same-Raw-ID jumps *in gate-visible sample stream*; this is **not evidence of improved accuracy**. Source benchmark metrics remain unchanged until V0.5.82 GPU replay is executed on Windows.
- Automated test results: **AI Service 646/646**, **Backend 175/175**, **Backup Worker 4/4**, **Frontend (Node) 4/4**, **Offline/Version/Replay/Audit 39/39**. **Total 868/868**, in the available local test environment. `ai-service/tests/test_tracking.py`: 73 tests, including 6 new V0.5.82 regression cases. Each suite executed here, not inferred from prior releases.
- `scripts/version-contract.py`: PASS, single Alembic head `0096_raw_id_reuse_v0582`, parent `0095_quiet_startup_v0581`. Frontend and runtime metadata are 0.5.82. Python `compileall`: PASS. CLI audit of original ZIP verified compressed trace and processed 23,650 frames.
- **Frontend production Vite build not verified:** npm offline installation failed with `ENOTCACHED` for `@vitejs/plugin-react`. Frontend unit tests passed; Windows/Docker `test.ps1` still needs to build the release UI.
- No native PowerShell, Docker/GPU replay, physical PostgreSQL or GitHub Release were executed in this environment. Run `scripts/test.ps1` and replay the camera on Windows before publishing.
- Backend + AI tests use SQLite/in-memory and an ephemeral `httpx2` → `httpx` adapter outside packaged source. CI and user's `scripts/test.ps1` use normal pinned dependencies.

---

# V0.5.81 — Verification of quiet startup and pip warning policy

- Input source: V0.5.80 full-source ZIP. Only startup console text, temporary pip test environment, release metadata and test contracts changed; counting/tracking/backend business logic stays identical.
- `scripts/version-contract.py`: PASS; Alembic has one head `0095_quiet_startup_v0581` with parent `0094_incumbent_identity_v0580`.
- `scripts/tests/test_startup_silence_v0581.py`: 4/4 PASS. Checks bounded polling / `healthy` success / no normal countdown / error diagnostics retained / pip root warning scoped only to disposable backup-worker container.
- Full local checks: backend 175/175, AI Service 640/640, Backup Worker 4/4, frontend Node unit 4/4, scripts stdlib offline 36/36 = **859/859** tests passed.
- Backend and AI tests used a temporary `httpx2` to installed `httpx` compatibility alias **outside** the deliverable, because pinned dependency `httpx2` is unavailable in this environment. This is not a native Docker/Python 3.14 test.
- `scripts/tests/test_version_contract.py`: 4/4 PASS. Python `compileall` passed.
- User-provided Benchmark #57 / Session #182 remains GT 149 / AI 152 / matched 139 / missed 10 / extra 13. No AI accuracy change claimed for this release.
- This environment does not provide PowerShell or Docker runtime and does not run NVIDIA replay. The user must run `scripts/test.ps1` and `scripts/start.ps1` on Windows to verify end-to-end startup. The full suite results from earlier versions are not automatically attributed to this release.

---

# V0.5.80 — Verification

- Benchmark #56 Session #180 (dữ liệu đầu vào): GT 149, AI 152, matched 139, missed 10, extra 13.
- Giữ 2 xe đang xuất hiện gần nhau tách biệt; không dùng GT để chọn ID runtime.
- Phát lại đầy đủ 23.650 frame cần chạy trên máy có model/video/GPU của người dùng; không thể suy diễn chỉ số mới từ test unit.
- Test thực thi trong môi trường hiện tại: AI 640/640; backend 175/175; scripts/offline 32/32; backup worker 4/4; frontend unit 4/4. **Tổng 855/855 đạt.**
- Backend/AI được chạy với shim `httpx2` → `httpx` đặt NGOÀI source chỉ để kiểm thử, không đóng gói shim. PostgreSQL thực tế, PowerShell và Vite/Docker GPU replay chưa được xác minh trong môi trường này.
- Test chi tiết và giới hạn xác minh được ghi dưới đây cùng thông tin các bản trước.

---

# V0.5.79 Verification — Release version mismatch hotfix

- Observed user failure: `scripts/test.ps1:326`, `VERSION must be 0.5.77, current: 0.5.78`, before backend/AI/frontend tests.
- Fix: make PowerShell contract dynamic, verify cross-component version and single Alembic head; provide Python release checker and two negative regression cases (old hardcoded PowerShell version, stale frontend package).
- Version and health metadata synchronized to 0.5.79; new migration 0093 only updates `system_settings.schema_version`.
- AI counting core and V0.5.78 deduplication algorithm unchanged. No new benchmark result, no claim of 0 missed/extra.
- Current environment: **175/175 backend**, **635/635 AI**, **4/4 backup worker**, **4/4 frontend Node**, **32/32 stdlib offline tests**, **5/5 benchmark gate pytest tests**; **855/855** cases passed. All Python sources compiled. The Python release metadata checker passes, and four focused tests include negative cases for stale source version.
- Backend/AI tested under Python 3.13 with `DATABASE_URL_OVERRIDE=sqlite+pysqlite:///:memory:` and a temporary HTTPX compatibility alias **outside the ZIP** (not a Docker/Python 3.14 release-environment run). Actual PowerShell parsing, Docker Compose build/start, PostgreSQL migration and GPU playback have **not** been verified here; run `scripts/test.ps1` on Windows before publishing.

---

# V0.5.78 Verification — direct-shadow ID switch

- Evidence: Benchmark #179 verified manifest, 149 GT and 153 events, complete trace. At 491.920 and 492.200, two direct/out/motorcycle events from different IDs are 0.008587 apart; RAR frame_12299 and frame_12306 visually show overlapping detection boxes on the same motorcycle.
- Offline reproduction using `app.benchmarking.match_crossings`: baseline 149 GT / 153 AI / 139 matched / 10 missed / 14 extra. Applying the new narrow guard to the saved DB event snapshot predicts 149 / 152 / 139 / 10 / 13. This is **not a new AI session**, and no claim is made that remaining errors have been fixed.
- Runtime backend guard gets only event time, normalized geometry, method, direction, class, track ID; no Ground Truth. `backend/app/shadow_guard.py` is shared with offline evaluator.
- Source V0.5.78 only changes the direct/direct near-point deduplication rule; counting engine, rescue branches, model weights and camera config are unchanged. Database migration updates metadata only, preserving data.
- New tests: 3 backend endpoint/helper regressions and 7 offline evaluator regressions. CI and PowerShell checks updated.
- Actual code tests in this packaging environment: backend **175/175**, AI Service **635/635**, backup worker **4/4**, offline benchmark/replay/forensics **33/33**, frontend Node unit **4/4**. **851/851 test cases passed**; Python compileall passed. Backend and AI used a temporary local `httpx2` compatibility alias not included in the ZIP. Node v22 could run unit tests; Vite build with pinned Node v26 was not performed.
- Alembic static revision graph shows one head `0092_direct_shadow_v0578`, parent `0091_gt_forensics_v0577`.
- Actual GPU replay, PostgreSQL, Docker, GitHub Actions and PowerShell startup require verification on target Windows; do not claim 0 missed / 0 extra.

---

# V0.5.77 Verification — startup and benchmark case forensics

- Source analysis: confirmed undefined `$root` on final V0.5.76 start.ps1 line 474 after Gateway. Fixed to `$ProjectRoot` which is initialized before execution.
- Verified unit tests: **172/172 backend**, **635/635 AI Service**, **4/4 backup worker**, **4/4 frontend Node tests**; additionally **26/26** offline benchmark/replay/forensics pytest tests (5 + 15 + 6). Backend and AI used an `httpx2`-to-`httpx` test-only compatibility shim in this container; this shim is NOT in the deliverable. `compileall` passed; Alembic single head `0091_gt_forensics_v0577`. Docker, PowerShell and production Vite build on Windows were NOT run.
- Added six unit tests for verified benchmark ZIP, complete trace, SHA-256 rejection, missing delivery footer, no-trace explicit warning and CLI output. New PowerShell source contract checks the startup path, version and migration chain.
- Camera Session #177/#178 images and trace (23,650 frames) do NOT include all 149 user-annotated GT entries; they cannot independently identify exact 10 missed and 14 extra physical events.
- Counting core unchanged; 0 missed / 0 extra was **not verified** and must not be represented as fixed.
- Docker/Windows/GPU runtime must be retested on user's machine before release.

---

# Verification V0.5.76 — GitHub Actions backend CI 401 failures

**Root cause:** `.github/workflows/ci-release-reusable.yml` did not inject `AI_SHARED_TOKEN`; `scripts/test.ps1` already did, so 18 direct-event tests called `_assert_ai_token` with blank settings and got 401.

**Fix:** CI test-only env var + test module's local temporary fixture + negative fail-closed security test. Production token check remains unchanged.

**User replay evidence:** Sessions #177 and #178 yielded DB 153 each, no event differences. Session #178 GT 149 / matched 139 / missed 10 / extra 14. No AI accuracy claim.

**Tests executed for V0.5.76 in the packaging environment:** backend **172 passed** (including new negative auth test), AI Service **635 passed**, backup-worker **4 passed**, replay-diff **15 passed**, benchmark gate **5 passed**, frontend Node unit tests **4 passed**, Python `compileall` passed. `test_app.py` alone also passed **87/87** without any `AI_SHARED_TOKEN` environment variable. Alembic reports a single head `0090_ci_token_v0576`.

**Limitations:** Packaging environment could not fetch pinned `httpx2` due DNS error; backend and AI tests used a temporary test-only `httpx2` → installed `httpx` alias which is **NOT** included in the source ZIP. Local FastAPI/SQLAlchemy/pytest versions also differ from GitHub CI pins. Docker Engine, GitHub Actions CI runner, PowerShell parser, PostgreSQL migration/restore, GPU replay and full Vite build have **not** been executed in this container. Re-run `scripts/test.ps1` and GitHub Actions on the target environment before publishing. These tests do not prove a change in benchmark GT accuracy.

---

# Verification V0.5.75 — Replay Drift Audit

- Base archive: `traffic-ai-v0.5.74-full-source.zip`; preserve Backup/Restore and all core counting thresholds.
- New modules: `scripts/replay-diff.py`, `scripts/compare-replays.ps1`, `scripts/tests/test_replay_diff.py`; historical run analysis in `docs/replay-session-174-vs-175.md`.
- New Alembic head: `0089_replay_drift_v0575` → `0088_backup_scheduler_v0574`; schema_version updated to 0.5.75 without data schema changes.
- Replay #174 (195 proposals/149 created/46 deduplicated) vs #175 (192/153/39): proposal pairs 187, removed 8, introduced 5; decision changes 6; created pairs 148, only #174 1 and only #175 5. Audit strict FAIL=expected, because the replay results demonstrably differ; not proof of true missed/extra vehicles. Check `docs/` for timecodes.
- Tests: 171/171 backend, 635/635 AI Service, 4/4 frontend unit, 4/4 backup worker, 5/5 benchmark gate, 15/15 replay-audit unit. Python compileall passed. Backend/AI test runs used temporary `httpx2` compatibility alias only in the test environment, excluded from ZIP.
- Docker/PowerShell/Vite build with pinned Node v26 and PostgreSQL restore integration were not run in this packaging environment. Source ZIP is not evidence of a live AI accuracy improvement. User must run scripts/test.ps1 and test with PostgreSQL before publishing.

---

# Kiểm thử Traffic AI V0.5.74

## Kết quả đo được trong môi trường đóng gói

- `backend`: **171 passed** — gồm 8 regression mới: RBAC/CSRF, tạo job, symlink guard, ZIP upload/roundtrip, file giả, xác nhận restore, maintenance fence, schedule cập nhật. `PYTHONPATH` dùng shim `httpx2` → `httpx` **chỉ trong quá trình test**, không đóng gói, nên không thay thế kiểm thử thực tế.
- `ai-service`: **635 passed** — thuật toán AI giữ nguyên V0.5.73, shim giống backend.
- `backup-worker`: **4 passed** — kiểm thử archive và checksum reject bằng subprocess fake.
- `frontend`: **4 passed** với `node --test frontend/tests/*.test.js`.
- `python3 -m compileall` backend, migration, backup-worker: đạt.
- Không thể chạy `npm install`/Vite build vì NPM registry trả lỗi `EAI_AGAIN`; chưa có Docker Engine nên **chưa xác nhận Docker Compose thực tế, PostgreSQL backup/restore thực tế hoặc PowerShell parse/run**.

## Cần xác minh thêm trên máy Windows

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

1. Đăng nhập Admin: phải thấy mục Backup / Restore, còn Viewer/Operator không có quyền gọi API `/api/admin/backups`.
2. Xác thực postgres + backup worker: `docker compose ps`, `docker compose logs backup-worker`.
3. Nhấn Sao lưu ngay; job phải hoàn thành, danh sách có dump mới, tải ZIP hợp lệ `manifest.json`, `database.dump`.
4. Kiểm tra lịch backup tùy chỉnh, sau 10 giây worker nhận lịch mới.
5. **Trên máy thử**: nhập ZIP và restore vào database tạm rồi switch, kiểm tra dữ liệu, user, benchmark, events. Backup DB trước khi restore, không thực hiện diễn tập trên production.
6. Kiểm tra restart backend & Alembic sau restore; cấu hình `.env` phù hợp PostgreSQL 18 và source file assets có đủ.

## Tiêu chí chưa xác minh

- End-to-end rollback/restore giao dịch thật bằng `pg_restore` PostgreSQL 18 trong Docker Desktop Windows.
- Build Vite thực tế và toàn bộ docker-compose image build.
- Performance/retention trên DB lớn; đường truyền upload ZIP > 1 GiB không được hỗ trợ ở bản này.

# VERIFICATION — Traffic AI V0.5.73 (11/10/2026)

## Nguyên nhân và phạm vi sửa

- API V0.5.72 khai báo regex ASCII, vì vậy tên đăng nhập `Đạt` bị HTTP 422; đây **không phải thao tác tạo thành công**. Giao diện lỗi 422 mảng JSON bị ép thành `[object Object]`. V0.5.73 giải quyết tại server, database và frontend.
- Hỗ trợ username Unicode NFC + khóa casefold duy nhất; migration backfill không xóa bảng hay dữ liệu; UI báo lỗi rõ, xác nhận ID 201, hiển thị tài khoản mới và tải lại bằng no-store.
- RAR Session #175: trace đã được trích xuất và kiểm tra, metadata `frame_policy=all-frames`, 23.650 frame, worker 192 crossing đề xuất. Screenshot cùng benchmark: GT 149, DB 153, khớp 139, lọt 10, dư 14. RAR **không có đầy đủ `ground-truth.json` và `events.json`**; không sửa thuật toán crossing và không khẳng định đạt 0/0.

## Kiểm thử thực hiện

- Backend: **163/163 PASSED** (bao gồm 3 test mới `test_v0573_usernames.py`); sử dụng SQLite in-memory + lớp chuyển tiếp `httpx2` sang `httpx` **chỉ trong môi trường test**, không đóng gói shim; các tính năng bảo mật CSRF/Argon2id/RBAC vẫn được kiểm thử.
- AI Service: **635/635 PASSED**; cùng lớp tương thích `httpx2` trong sandbox; không sửa thuật toán AI của V0.5.72.
- Frontend: **4/4 PASSED** (`npm test`, Node built-in test); JSX parseDiagnostics **0** với TypeScript. Các bài test Node không phải build Vite thật.
- Benchmark release gate: **5/5 PASSED**, chỉ là kiểm thử chất lượng export ZIP được giả lập; không phải kết quả GT/AI mới của Session #175.
- Compile Python backend + migration thành công; Alembic/PowerShell contract có bản mới.

## Chưa xác nhận / cần kiểm tra trên Windows

- `npm run build` Vite + audit NPM + Docker Compose build (môi trường sandbox thiếu `node_modules` và Docker Desktop), migration với PostgreSQL thật, tương tác tạo user bằng trình duyệt thật.
- Chưa có dữ liệu GT đầy đủ để tối ưu Recall/Precision Session #175. Cần ZIP từ nút **Tải hồ sơ benchmark** chứa `manifest.json`, `report.json`, `ground-truth.json`, `events.json`.
- Khi chạy `scripts/test.ps1` phải bật Docker Desktop Linux containers trước; sau khi test thành công mới chạy `scripts/start.ps1` và nhập lại tài khoản `Đạt` nếu lượt trước đã bị 422.

---

# VERIFICATION — Traffic AI V0.5.72 (10/10/2026)

## Nguồn dữ liệu và phân tích

- Đọc source V0.5.70 từ ZIP và source V0.5.71; 5 file lõi đếm/trace/benchmark trùng byte.
- Giải nén và đọc được `session_174_benchmark-trace.jsonl` từ `camera_1(20261010-144752).rar`: 23.650 frame, 195 proposal, 195 acknowledgment (149 created, 46 deduplicated), 325 rejection validation rescue, 69 long-gap rejection. Các chỉ số này không tự xác thực được 149 GT vì RAR không có `ground-truth.json` và `events.json`.

## Kiểm thử thực hiện

- **AI service: 635/635 passed**, gồm 4 bài kiểm thử mới V0.5.72 cho deterministic tracking order + confidence tie-break.
- **Backend: 160/160 passed** (không chỉnh thuật toán match GT/backend event).
- **Benchmark Gate CLI: 5/5 passed** — tự tạo ZIP giả lập có SHA-256 để kiểm thử FAIL trường hợp 149/149/135, PASS 149/149/149, và chặn dữ liệu thiếu GT, integrity lỗi, baseline sai.
- Python compile: `python -m compileall` cho `backend/app`, `backend/tests`, `backend/alembic`, `ai-service/app`, `ai-service/tests`, `scripts/benchmark-gate.py`.
- 635 + 160 + 5 = **800 bài kiểm thử Python đạt** tại sandbox. Backend và AI dùng **httpx2 → httpx shim test-only ở ngoài source ZIP** do `httpx2==2.13.0` không tải được trong môi trường này; không thay file requirements hay mã production.

## Chưa kiểm thử / chưa thể khẳng định

- Chưa chạy thành công `scripts/test.ps1` bằng PowerShell trên Windows, Docker Desktop Linux Engine, image pinned httpx2, inference YOLO trên GPU, benchmark GT/AI đầy đủ hay `npm run build` của Vite trên máy Windows. Phải chạy các bước đó **trước `publish.ps1`**.
- **Chưa xác nhận V0.5.72 giảm 14 lọt và 14 dư thành 0**: cần xuất `Tải hồ sơ benchmark` (report + GT marks + events) và video gốc/GT đồng nhất để đo lại; không thể khẳng định từ số lượng trace proposal.
- Đầu ra của `check-benchmark.ps1` chỉ là guard đối với dữ liệu benchmark đã xuất; không điều chỉnh điểm benchmark và không tự chứng nhận hiệu năng AI.

---

# VERIFICATION — Traffic AI V0.5.71

V0.5.71 tập trung vào giao diện bảo mật và chính sách mật khẩu, không tác động thuật toán nhận diện/đếm. Kết quả kiểm thử trong môi trường sandbox (2026-10-10):

- **Backend 160/160 pass** với Python 3.13 / pytest 9 / SQLAlchemy + SQLite memory / FastAPI. Bao gồm các luồng Auth, role, CSRF, phiên, 4 nhóm ký tự, Unicode, độ dài, write-path API và tương thích mật khẩu đang sử dụng ở V0.5.70.
- **AI Service 631/631 pass** trong cùng môi trường mô phỏng; không thay logic AI.
- Tổng **791/791** tests thành công. Sử dụng `httpx2 -> httpx` shim ngoài thư mục source ZIP để chạy local do sandbox không có package `httpx2`; Docker test thật sử dụng dependency được khai báo trong requirements.
- `security.jsx`, `password-security.jsx`, `main.jsx` đều vượt qua bước kiểm tra cú pháp JSX bằng TypeScript parser.
- Không thể chạy `npm install`/`npm run build` trong sandbox do không truy cập được registry NPM (`EAI_AGAIN`); **chưa xác nhận bản build Vite/browser thực tế**. Chưa chạy PowerShell Windows, Docker Compose, HTTPS runtime hoặc PostgreSQL thật. Cần thực hiện `scripts/test.ps1` và `scripts/start.ps1` trên máy Windows trước khi publish.
- Alembic `0085_password_policy_v0571` chỉ tăng schema version; không sửa dữ liệu người dùng hoặc khóa tài khoản có password cũ.

---

# VERIFICATION — Traffic AI V0.5.70

Log khách hàng xác nhận PostgreSQL healthy nhưng Backend không đăng nhập được: `FATAL: password authentication failed for user traffic_admin`. V0.5.70 thêm preflight TCP/SCRAM fail-fast, script password repair tương tác, và chặn tự đổi mật khẩu khi volume cũ tồn tại. Kết quả kiểm thử trong môi trường sandbox: **157/157 Backend** và **631/631 AI Service** pass (tổng **788**). Dùng SQLite memory và test-only `httpx2 -> httpx` shim bên ngoài source ZIP; chưa chạy Docker/PowerShell Windows thật, PostgreSQL SCRAM thật hoặc thay mật khẩu database của người dùng. Chưa thao tác trực tiếp trên PostgreSQL thật của người dùng; họ phải tự xác nhận bằng `scripts/repair-postgres-auth.ps1` rồi chạy `scripts/test.ps1` / `scripts/start.ps1`. Không có lệnh reset/drop dữ liệu.

# Traffic AI V0.5.69 verification

- Root symptom: Compose can wait indefinitely at Backend Waiting when the
  PostgreSQL/Backend migration or healthcheck fails. The screenshot alone
  does not identify the underlying error.
- Source change: staged startup with finite health waits (DB 120s, Backend
  180s, AI service 240s); prints DB/backend logs and healthcheck on failure.
  GPU fallback preserved, no database data reset or volume removal.
- Added 2 backend Python regression source tests and a PowerShell contract
  assertion. Final test results are listed below after execution.
- Python/Docker tests in this build environment may not reproduce the
  user's Windows + PostgreSQL runtime. `start.ps1` and `test.ps1` should be
  tested on Windows before publishing to GitHub.

---

# VERIFICATION — Traffic AI V0.5.68

### Đã chạy trực tiếp trong môi trường hiện tại

- Backend `pytest`: **150 passed**, gồm **10 security integration regressions** chạy với TestClient, SQLite StaticPool, dependency override test-only; bao phủ Argon2id salt ngẫu nhiên, CSRF/Origin, cookie flags, không đăng nhập, RBAC Viewer, tạo/khóa/reset user, Admin tự khóa bị từ chối, brute-force limit và thu hồi phiên khi đổi mật khẩu.
- AI Service `pytest`: **631 passed**, không chỉnh sửa logic AI. Tổng **781 pytest passed** với dependency test-only `httpx2->httpx` ngoài ZIP và các thư mục tạm dành cho AI.
- Python source parse AST, migration head/parent chain, frontend JSX parse bằng TypeScript parser, ZIP CRC và path/filename integrity được kiểm tra ở bước đóng gói. Bộ test PowerShell có token AI giả lập riêng và cô lập `node_modules` bằng Docker anonymous volume, tránh lẫn wrapper Windows/Linux.
- **Chưa chạy** pinned `httpx2`/psycopg PostgreSQL integration, Alembic upgrade trên PostgreSQL thật, PowerShell native, Docker Compose, Nginx trong container phiên bản 1.31.6 (chỉ kiểm tra parser trên Nginx 1.26.3 đã thay upstream DNS/cert ở file QA ngoài source: syntax ok), GPU inference, frontend Vite bundling và `npm audit` trong sandbox (npm registry không phản hồi); **không được coi những hạng mục đó đã pass**. `scripts/test.ps1` vẫn bắt buộc kiểm tra toàn bộ trên Windows trước publish.
- Migrate từ schema V0.5.67: không tự thêm admin mặc định; mã hóa mật khẩu bằng Argon2id; AI_shared_token ví dụ cũ sẽ được start.ps1 tạo mới ngẫu nhiên nếu chưa customize.

---

# Kiểm tra lưu trữ V0.5.67 (historical baseline)

## Kết quả thực hiện cho lần nâng cấp này

- Dựa trên full source ZIP V0.5.66 do người dùng tải lên, không hồi quy về bản cũ.
- Trace RAR session172: 23.650 frame records, 195 `event_delivery` (149 `created`, 46 `deduplicated`), một metadata session, một geometry header và một delivery summary. Mốc OUT GT 69.457s có persisted DB event OUT 69.4566s (event10275); không thể kết luận điều kiện ghép GT từ trace không có bản export đầy đủ.
- Backend pytest: **140 passed**, gồm 5 regression V0.5.67; AI pytest: **631 passed**, tổng 771. Do môi trường không cài `httpx2`/`psycopg`, backend dùng SQLite memory và shim `httpx2->httpx` chỉ ở ngoài ZIP; AI dùng shim tương tự và thư mục tạm cho dữ liệu.
- Đây là unit/synthetic integration test của source thực, không xác nhận Docker/PowerShell, model inference/GPU, hoặc F1 mới trên clip. Không chạy lệnh publish/GitHub trong môi trường đóng gói.
- Benchmark matching vẫn nguyên tắc timestamp-only one-to-one ±tolerance. Temporal competition chỉ thêm evidence read-only khi có event thực trong cửa sổ; không sửa GT/event/scores/timeout/dedup.

## Kết quả thực hiện

| Phạm vi | Kết quả |
|---|---|
| Test functions offline thực thi | **731 đạt, 0 lỗi**: 628 AI + 103 backend |
| HTTP/ORM/app integration chưa chạy | **35**: đúng 3 AI + 32 backend identities của .65 |
| Test definitions trong source | **766**: giữ đủ 758 cũ, thêm 8 |
| Kiểm tra tĩnh source/contracts | **645 đạt** |
| Python parse/compile | **135 files** |
| Alembic | **80 migrations**, head/parent hợp lệ, không cycle |
| Release cục bộ | **38 đạt**: 17 executed + 14 static + 4 simulation + 3 Bash syntax |
| Frontend | **57 đạt**: đủ 41 ca cũ + 16 ca mới, Babel/Node VM/controlled JSX |
| Frontend layout/evidence subset | **27 đạt**, thuộc 57 ca trên |
| Full source | **195 files**: 192 UTF-8 text + 3 binary assets |
| Code/config đóng băng sau test | **193 SHA256**, hai tài liệu review riêng |

731 là test functions thực sự chạy qua offline harness, không phải full pytest. 766 definitions gồm 35 integration chưa chạy. Giữ đủ 758 baseline test identities và đúng 35 integration exclusions; không xóa test hay bỏ thêm integration để đạt số pass.

Thêm 8 backend tests về GT0/AI0, GT0/AI149, không chạy assignment/diagnostics khi GT trống, generator/input preservation, có GT nhưng AI0, valid scored report, chuyển trạng thái sau thêm GT và export JSON null với đủ events. Năm test bodies cũ đổi: 4 health/version assertions lên .66 và 1 startup-artifact fixture thêm GT ở xa; assertion chẩn đoán startup vẫn giữ nguyên.

Actual NumPy 2.3.5/Pydantic 2.13.5 và algorithm modules dùng thư viện thực. Worker/pure backend helpers trích AST để tránh HTTP/ORM imports thiếu; pytest shim chỉ cung cấp approx/raises/tmp_path/monkeypatch. Dispatcher dùng queue/thread/retry thực với HTTP client được kiểm soát. Model opinions là fixture/recorded evidence, không phải inference thật.

## Baseline và input

Baseline đúng ZIP .65 đã giao: **447,906 byte / 194 files**, SHA256 `96f4d7681b8f924da24c42e162e2cb93497c92da0de839e515cd83aa27352b92`. Đã kiểm CRC/safe unique paths và giải nén byte-exact. Source .66 giữ đủ 194 paths, thêm duy nhất migration0080.

Hai ảnh .65 session171/benchmark48 cho thấy AI149, IN68/OUT81; AI146 xe máy +1 xe đạp +2 xe tải, không có CAR. Worker195/backend gộp46/DB149 timed events/Human Guard30/IntegrityOK. Truck lock→car0/truck semantic locks2/truck crossings2; class checks2168.

**Benchmark #48 đang GT0**, có nút sao chép149GT từ benchmark #47 nhưng chưa có GT trong target. Báo cáo cũ FP149/F10% chưa phải score hợp lệ về chất lượng AI. Không có GT/event assignment export hoặc full model replay để đo score .66. Không đổi GT để làm đẹp score.

RAR **81,081,480 byte**, SHA256 `fd48df69f5676d71b21126a68bddaaba997ecc3fee91e4ce469e123351e10927`; 195 safe unique regular members =194 JPEG +1 JSONL. Tất cả194JPEG1440×811 được decode; đã xem5 contact sheets và hai ảnh crossing.

Trace **196,487,992 byte**, SHA256 `069b706128174ef4ba0dfabae3d744467dbc579ecebad5ef5f59af557c3f2e2d`; 23,650 continuous observation frames,195proposals=195terminalreceipts khớp11source fields:149created+46deduplicated, allattempt1, mọi dedupID resolve tới created event. Footer drain_complete=true/pending0/dropped0. Không thấy canonical collision trong cùng frame.

| Lượt van đã sửa trong run .65 | Source / observed frame | Backend event | Kết quả |
|---|---:|---:|---|
| 254023 OUT641.9311s | 16049 /16050 | 10212 | TRUCK |
| −22 IN882.2898s | 22058 /22059 | 10254 | TRUCK |

Cả hai raw crossing audits ghi generic CAR winning frames2, domain0, qualified_truck_requires_domain_car, demotion_accepted=false. Đối chiếu195receipt với session170: tracking/direction/source frame/time/method/x/y/outcome/attempts/dedup reason giữ nguyên sau bỏ session/backend IDs vốn thay đổi giữa các run. Chỉ hai vehicle_type đổi CAR→TRUCK; confidence OUT giữ .995817, IN đổi .994647→.986346 theo truck lock. Đây là bằng chứng từ run người dùng, không phải inference .66 hoặc khẳng định hai canonical là cùng xe vật lý.

## Chính sách readiness và hồi quy

GT0 short-circuit trước global assignment/FP diagnostics. Report thêm report_readiness với status needs_ground_truth, scoring_available=false, reason no_ground_truth. GT/AI totals và raw counts theo class/direction vẫn có; score/count-error scalars, difference/correct_matches là null, assignment/diagnostic lists rỗng. Export roundtrip giữ JSON null, GT[], đủ0hoặc149AIevents và không mutate input.

GT>0 trả ready/scoring_available=true/reasonnull. Backend trường ready cùng metadata này; AI0 vẫn chấm được, matched0/missed=GT/FP0/RecallPrecisionF10%. Có mốc GT không phải chứng nhận annotation đã đầy đủ toàn clip. API chưa có trạng thái xác nhận riêng cho clip đã được kiểm chứng không có xe, nên GT0/AI0 cũng chưa chấm, không tự nhận100%.

**1,000 randomized valid-GT cases** của implementation review so với actual delivered .65 ZIP giữ toàn bộ legacy report fields; gồm127GT>0AI0 và1,000input-order checks. Independent review thêm **600 valid-GT cases**,5GT0 cases (AI0/1/2/7/149) và explicit GT>0AI0. Đây là supplemental assertions, không cộng vào731 test functions. Không dùng class/direction để thay đổi temporal matching hoặc nâng score.

Frontend giữ tổng AI/GT/Integrity/export khi GT trống, các score/Δ hiển thị — và không render stale diagnosis lists. Legacy API fallback dùng ground_truth_total; explicit metadata false/needs_ground_truth vẫn chặn score, không dùng legacy ready để bỏ AI0. Nút reconcile disabled khi detail.marks rỗng và handler cũng chặn POST; response needsGT không được tóm tắt là khớpnull/lọtnull/dưnull.

Sao chép vẫn là hành động explicit; source/target IDs và sốGT rõ ràng. Actual handler gửi source47→target48 và reload detail/report/list; không auto-clone. Selection guard tránh phản hồi clone/reconcile cũ thay đổi thông báo của benchmark mới. Existing request guards của list/detail/reconcile được giữ lại.

16 frontend cases mới cover emptyGT+AI149/0, stale diagnostics, scoredGT+AI0/metrics, legacy fallback, metadata precedence, clone available/incompatible, explicit clone POST/refresh/error/stale response, noGT reconcile/noPOST, needsGTresponse, valid/stale reconcile. Giữ đủ41 old check identities.

## Rà soát full source và contracts

Đối chiếu .65 ZIP, toàn bộ17 AI app policy files byteequal, gồm worker/classification/counting/tracking/Human Guard/dispatcher/runtime/trace. Giữ sửa van .65, admission/budgets/caches/semantic TTL/Gate/Road/cooldown/dedup/provenance/drain.

Benchmarking chỉ thêm _empty_ground_truth_report và early return/readiness trong match_crossings. Bỏ đúng các phần additive này thì AST trở về .65;12/13 old module functions byteequal, global matcher/missed matching audit/FP diagnostics/review pairing không đổi. Routes80/81functions byteequal, _build_benchmark_report chỉ thay ready bằng scoring_available. GT CRUD/clone/export không đổi.

Independent Babel parse39 top-level frontend statements: chỉ APP_VERSION và GroundTruthBenchmark đổi;37statements khác giữ đúng byte, gồm toàn bộ App/AnnotationEditor. GroundTruthBenchmark giữ state/effects và các handler khác; chỉ thêm3readiness declarations, đổi2handler clone/reconcile và render readiness. Original3diagnostic row maps giữ nguyên; originalcontrols/handlers giữ, chỉ reconcile thêm điều kiện GT và một nút clone bổ sung tại panel report. CSS byteequal .65, gồm dashboard50/50 và evidence stack. Controlled JSX không phải pixel geometry/browser rendering.

**969 source regex predicates**, **662 internal imported symbols**, **117 frontend runtime-field pairs** được rà soát, không còn findings. Assert-BenchmarkReadinessV0566Contract khai báo/gọi, historical functions/invocations vẫn có. VERSION/frontend/API health/start message0.5.66 đồng bộ;193code/config hashes final đóng băng và so lại khi đóng gói.

Head **0080_benchmark_ready_v0566**, parent **0079_van_semantics_v0565**; upgrade schema_version0.5.66/downgrade0.5.65, không đổi schema/GT/events. Revision dưới32ký tự.17PowerShell scripts UTF-8noBOM/CRLF, source/config text khácLF.

npm Docker/CI/packageManager12.2.0 đối chiếu [official npm CLI latest](https://github.com/npm/cli/releases/latest) ngày09/10/2026; Node pin26.10.0 giữ nguyên. Đây là source contracts, không phải host npm upgrade hoặc native PowerShell chạy thành công.

## Giới hạn và chạy lại trên Windows

Môi trường kiểm tra Python3.12.14/Node24.19.0/npm11.9.0; availability kế thừa .65, không probe/install dependency lặp lại. Thiếu pytest/FastAPI/SQLAlchemy/Alembic/httpx2/cv2/Torch/pwsh/Docker. Không chạy full dependency-pinned pytest, HTTP/ORM/database/migration thực, PowerShell native, Docker/npm audit/Vite build, browser/React DOM, GPU/model/video replay. Integration tests vẫn nguyên trong source để chạy scripts/test.ps1 trên máy đủ Docker.

38releasechecks gồm isolated local Git/workflow artifact execution và static/simulation/Bash syntax đã phân loại; không push GitHub/tạo Release thật. Không có Recall/F1/class accuracy .66 đo từ clip.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.66 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Với benchmark48, sao chép149GT từ benchmark47 nếu cùng clip/vạch; review GT loại van ở10:41.93OUT/14:42.29IN theo quy ước người dùng Xe tải, giữ timecode/hướng theo clip đã kiểm tra. Đối chiếu lại rồi Tải hồ sơ benchmark ZIP để lấy cả GT và AI assignments cho lần phân tích tiếp theo.
