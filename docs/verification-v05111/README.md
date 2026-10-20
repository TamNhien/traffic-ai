# Traffic AI V0.5.111 verification

Scope: human-readable local benchmark ZIP path diagnostics only. No AI counting or Ground Truth changes.

Validated on supplied `traffic-ai-benchmark-80-session-207-recovered-v110.zip`:
- ZIP central directory and CRC valid.
- `audit-gate-coverage.py --expected-session 207 --require-provenance`: succeeded.
- 23,650 frames, 11 unmatched cases; 271,208 per-track gate-decision samples.
- Report preserved: GT 149 / AI 148 / matched 143 / missed 6 / extra 5. Runtime evidence 0.5.109.

Tests executed:
- `python -m unittest discover -s scripts/tests -p 'test_*.py' -q`: 187 executed, 186 passed, 1 skipped.
- `python -m pytest -q scripts/tests/test_benchmark_gate.py`: 5 passed, 1 intentional duplicate ZIP-member warning in a negative test.
- `node --test frontend/tests/*.test.js`: 47 passed.
- `python scripts/version-contract.py`: OK for 0.5.111, migration 0125.

Limitations:
- PowerShell was unavailable in the test runtime; on Windows run `scripts/test.ps1` for native syntax and Docker checks.
- AI inference, Docker Compose deployment, GPU, and full backend/AI test suites were not rerun for this read-only CLI fix.
- No new benchmark scores are claimed.
