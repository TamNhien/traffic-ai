#!/bin/sh
set -eu

echo "[Traffic AI Backend] Waiting for PostgreSQL..."
python - <<'PY'
import time
from sqlalchemy import create_engine, text
from app.core.config import settings

last_error = None
for attempt in range(1, 31):
    try:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
            if conn.dialect.name == "postgresql":
                # Alembic mặc định tạo alembic_version.version_num là VARCHAR(32).
                # V0.5.3 từng có revision ID dài 38 ký tự nên startup bị lỗi.
                exists = conn.execute(text(
                    "SELECT to_regclass('public.alembic_version') IS NOT NULL"
                )).scalar()
                if exists:
                    # Do not take an ACCESS EXCLUSIVE table lock on every boot.
                    # Older installations may still need the Alembic revision
                    # column to be widened to 128 characters exactly once.
                    current_length = conn.execute(text(
                        "SELECT character_maximum_length FROM information_schema.columns "
                        "WHERE table_schema=current_schema() "
                        "AND table_name='alembic_version' AND column_name='version_num'"
                    )).scalar()
                    if current_length is not None and int(current_length) < 128:
                        conn.execute(text("SET LOCAL lock_timeout = '5s'"))
                        conn.execute(text(
                            "ALTER TABLE alembic_version "
                            "ALTER COLUMN version_num TYPE VARCHAR(128)"
                        ))
                        print("[Traffic AI Backend] Alembic revision column widened once.", flush=True)
                    # Update the historic long revision ID only if necessary.
                    legacy_revision = conn.execute(text(
                        "SELECT 1 FROM alembic_version "
                        "WHERE version_num='0017_ai_test_dependency_isolation_v053' LIMIT 1"
                    )).scalar()
                    if legacy_revision:
                        conn.execute(text("SET LOCAL lock_timeout = '5s'"))
                        conn.execute(text(
                            "UPDATE alembic_version "
                            "SET version_num='0017_ai_test_dep_v053' "
                            "WHERE version_num='0017_ai_test_dependency_isolation_v053'"
                        ))
        print(f"[Traffic AI Backend] PostgreSQL ready (attempt {attempt}).", flush=True)
        break
    except Exception as exc:
        if "password authentication failed" in str(exc).lower():
            raise SystemExit(
                "[Traffic AI Backend] PostgreSQL rejected the configured password. "
                "Use scripts/repair-postgres-auth.ps1 on the host; no volumes were changed."
            ) from None
        last_error = exc
        print(f"[Traffic AI Backend] PostgreSQL not ready ({attempt}/30): {exc}", flush=True)
        time.sleep(2)
else:
    raise SystemExit(f"PostgreSQL did not become ready: {last_error}")
PY

echo "[Traffic AI Backend] Applying Alembic migrations..."
if ! PGOPTIONS="-c lock_timeout=15000 -c statement_timeout=150000" alembic upgrade head; then
  echo "[Traffic AI Backend] ERROR: Alembic migration failed." >&2
  echo "[Traffic AI Backend] Current revision:" >&2
  alembic current || true
  echo "[Traffic AI Backend] Migration heads:" >&2
  alembic heads || true
  exit 1
fi

echo "[Traffic AI Backend] Starting FastAPI on 0.0.0.0:8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
