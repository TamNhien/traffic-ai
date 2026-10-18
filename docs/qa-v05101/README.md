# Test log V0.5.101 (Linux sandbox)

AI and backend tests use a **temporary external compatibility shim** for missing `httpx2`: `from httpx import *`. No shim is included in source ZIP. Results demonstrate regression fix, **not** full certified production Docker run with pinned httpx2/Python 3.14 and PostgreSQL. Full `scripts/test.ps1` on Windows must still pass.

| Log | Command / Result |
|---|---|
| `ai.txt` | AI unit tests: 738 passed |
| `backend.txt` | Backend tests: 195 passed |
| `scripts.txt` | Script tests excluding cache: 101 passed / 1 skip, 38 subtests |
| `script-cache.txt` | 8 passed / 21 subtests |
| `frontend.txt` | Node 22 frontend tests: 47 passed (only tests; no build) |
| `version.txt` | Version-migration consistency: pass |

The previous user's Windows result was 6 failed + 729 passed for AI V0.5.100; tests here verify V0.5.101 fixes that failure signature. No new inference benchmark claimed.
