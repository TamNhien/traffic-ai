# Traffic AI V0.5.107 release verification

## Bug and resolution
- User Windows log stopped in `scripts/test.ps1` at the V0.5.106 endpoint precision tests:
  `python:3.14.7-slim` does not include pytest, but the script invoked `python -m pytest`.
- Converted the existing three endpoint policy regressions to unittest.TestCase and
  replaced the bare-slim command with `python -S -m unittest discover`.
- Added two regression checks that run the tests with site packages disabled and
  verify the test script does not call pytest or pip in this Docker stage.
- The regular AI pytest suite still discovers all three tests.
- No change to runtime crossing thresholds, model, GT, database event data or UI layout.

## Verified locally
- Release version and Alembic single-head contract: PASS, version 0.5.107.
- Python source compilation: PASS (Python 3.13).
- Endpoint regression under `python -S`: **3 passed**.
- New endpoint runner contract: **2 passed**.
- AI full pytest with **local test-only httpx2->httpx module alias**:
  **750 passed** (three endpoint tests included).
- Script Python unittest suite: **142 passed, 1 skipped** (143 total).
- Frontend native Node tests: **47 passed** (host Node v22; production requires v26).
- Backend selected isolated tests: **18 passed** using a SQLite test DB and
  test-only httpx alias. Full backend suite was attempted but exceeded the
  execution time limit after partial progress; not claimed as passed.
- Old release source manifest preserved; ZIP CRC validated and caches excluded.

## Not verified in this environment
- Full `scripts/test.ps1` and full Docker image build on Windows PowerShell.
- Production dependency `httpx2`, persistent PostgreSQL migration, GPU inference,
  model accuracy/F1 and real-time camera playback.
- NPM package install/build and GitHub release.

The absence of `pytest` was a test-only dependency error; no revised benchmark
accuracy score is claimed for this version.
