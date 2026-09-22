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
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"[Traffic AI Backend] PostgreSQL ready (attempt {attempt}).", flush=True)
        break
    except Exception as exc:
        last_error = exc
        print(f"[Traffic AI Backend] PostgreSQL not ready ({attempt}/30): {exc}", flush=True)
        time.sleep(2)
else:
    raise SystemExit(f"PostgreSQL did not become ready: {last_error}")
PY

echo "[Traffic AI Backend] Applying Alembic migrations..."
if ! alembic upgrade head; then
  echo "[Traffic AI Backend] ERROR: Alembic migration failed." >&2
  echo "[Traffic AI Backend] Current revision:" >&2
  alembic current || true
  echo "[Traffic AI Backend] Migration heads:" >&2
  alembic heads || true
  exit 1
fi

echo "[Traffic AI Backend] Starting FastAPI on 0.0.0.0:8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
