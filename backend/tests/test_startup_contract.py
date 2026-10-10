"""V0.5.69 startup orchestration regression, independent of Docker runtime."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_v0569_stage_order_and_finite_wait() -> None:
    source = (ROOT / "scripts" / "start.ps1").read_text(encoding="utf-8")
    markers = ("Stage 1/4: PostgreSQL", "Stage 2/4: Backend", "Stage 3/4: AI Service", "Stage 4/4: Frontend")
    positions = [source.index(marker) for marker in markers]
    assert positions == sorted(positions)
    assert 'Wait-ContainerHealthy "traffic-ai-postgres" 120' in source
    assert 'Wait-ContainerHealthy "traffic-ai-backend" 180' in source
    assert 'Wait-ContainerHealthy "traffic-ai-service" 240' in source
    assert 'up -d --build --no-deps backend' in source
    assert 'up -d --build --no-deps ai-service' in source


def test_v0569_startup_diagnostics_do_not_delete_volumes() -> None:
    source = (ROOT / "scripts" / "start.ps1").read_text(encoding="utf-8")
    diag = (ROOT / "scripts" / "diagnose-startup.ps1").read_text(encoding="utf-8")
    assert 'logs --tail 80 postgres' in source
    assert 'logs --tail 200 backend' in source
    assert 'docker compose -f docker-compose.yml ps -a' in diag
    assert 'docker inspect --format' in diag
    for content in (source, diag):
        assert 'down -v' not in content
        assert 'volume rm' not in content
        assert 'volume prune' not in content


def test_v0569_alembic_version_column_is_only_changed_when_needed() -> None:
    source = (ROOT / "backend" / "entrypoint.sh").read_text(encoding="utf-8")
    assert "character_maximum_length" in source
    assert "int(current_length) < 128" in source
    assert "ALTER COLUMN version_num TYPE VARCHAR(128)" in source
    assert "SET LOCAL lock_timeout" in source
    assert "PGOPTIONS=" in source
    assert "statement_timeout=150000" in source


def test_v0570_credential_preflight_precedes_backend_and_uses_tcp_scram() -> None:
    script = (ROOT / "scripts" / "start.ps1").read_text(encoding="utf-8")
    assert 'function Test-ConfiguredPostgresPassword' in script
    assert 'PGPASSWORD="$POSTGRES_PASSWORD"' in script
    assert 'psql -h 127.0.0.1' in script
    assert script.index('Test-ConfiguredPostgresPassword))') < script.index('Stage 2/4: Backend')
    assert 'repair-postgres-auth.ps1' in script


def test_v0570_template_secret_does_not_rotate_existing_database_volume() -> None:
    script = (ROOT / "scripts" / "start.ps1").read_text(encoding="utf-8")
    guard = script.index("if ($existingDbVolume -eq 'traffic_ai_postgres_data')")
    generate = script.index('$newDbSecret =')
    assert guard < generate
    assert 'Không tự đổi DB secret' in script


def test_v0570_password_recovery_uses_psql_prompt_never_plaintext_sql() -> None:
    source = (ROOT / "scripts" / "repair-postgres-auth.ps1").read_text(encoding="utf-8")
    assert '-c "\\password $dbUser"' in source
    assert 'docker exec -it' in source
    assert 'PGPASSWORD="$POSTGRES_PASSWORD"' in source
    assert 'ALTER ROLE' not in source
    assert 'ALTER USER' not in source
    assert 'down -v' not in source
    assert 'volume rm' not in source
    assert 'pg_hba.conf' in source and 'Không đổi pg_hba.conf' in source


def test_v0570_backend_fails_fast_on_invalid_pg_password() -> None:
    entry = (ROOT / "backend" / "entrypoint.sh").read_text(encoding="utf-8")
    assert 'password authentication failed' in entry
    assert 'raise SystemExit(' in entry
    assert 'repair-postgres-auth.ps1' in entry
