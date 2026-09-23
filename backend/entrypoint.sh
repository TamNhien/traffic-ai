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
                    conn.execute(text(
                        "ALTER TABLE alembic_version "
                        "ALTER COLUMN version_num TYPE VARCHAR(128)"
                    ))
                    # Tương thích nếu một môi trường từng lưu revision ID dài sau khi
                    # quản trị viên tự nới cột thủ công.
                    conn.execute(text(
                        "UPDATE alembic_version "
                        "SET version_num='0017_ai_test_dep_v053' "
                        "WHERE version_num='0017_ai_test_dependency_isolation_v053'"
                    ))
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
