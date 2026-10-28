"""Read-only worker source identity and trace schema contract (V0.5.118)."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

TRACE_RUNTIME_VERSION = '0.5.118'
TRACE_GATE_DECISION_SCHEMA = 1


def source_fingerprint() -> str:
    """Digest exact source bytes in a fixed order, not mutable volume/config data."""
    folder = Path(__file__).resolve().parent
    digest = sha256()
    for name in ('worker.py', 'counting.py', 'trace_identity.py','finite_endpoint_guard.py', 'road_gate_diagnostics.py', 'benchmark_trace.py', 'classification.py', 'tracking.py', 'fragment_ownership.py', 'policy_snapshot.py'):
        content = (folder / name).read_bytes()
        digest.update(name.encode('utf-8') + b'\0' + str(len(content)).encode('ascii') + b'\0' + content)
    return digest.hexdigest()


def metadata() -> dict:
    return {
        'ai_runtime_version': TRACE_RUNTIME_VERSION,
        'worker_source_sha256': source_fingerprint(),
        'gate_decision_schema_version': TRACE_GATE_DECISION_SCHEMA,
        'gate_decision_scope': 'per-gate-track-v1',
    }
