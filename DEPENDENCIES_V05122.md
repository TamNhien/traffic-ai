# Traffic AI V0.5.122 — Dependency & Framework Refresh

Release date: 2026-10-29. Base: the user's V0.5.121 full-source archive.
This is a dependency/runtime upgrade. It is not an improved AI-counting benchmark release.

## Upgraded direct dependencies

| Layer | From V0.5.121 | V0.5.122 |
| --- | --- | --- |
| React / React DOM | 19.3.0 | 19.3.1 |
| @vitejs/plugin-react | 6.1.1 | 6.1.2 |
| FastAPI (backend + AI) | 0.141.1 | 0.162.0 |
| Uvicorn | 0.53.0 | 0.54.0 |
| SQLAlchemy | 2.0.54 | 2.1.6 |
| Alembic | 1.20.0 | 1.20.1 |
| Pydantic | 2.13.5 | 2.14.1 |
| pydantic-settings | 2.15.0 | 2.16.2 |
| HTTPX2 | 2.13.0 | 2.16.0 |
| ReportLab | 5.0.1 | 5.1.0 |
| PyTorch | 2.14.0 | 2.15.0 |
| TorchVision | 0.29.0 | 0.29.2 |
| Ultralytics | 8.4.158 | 8.4.192 |
| NumPy (AI test) | 2.4.6 | 2.5.4 |
| pytest (dev/test) | 9.1.1 | 9.2.0 |
| Python container | 3.14.7 | 3.14.10 |
| Node.js container / CI | 26.10.0 | 26.13.0 |
| npm | 12.2.0 | 12.2.1 |
| pip | 26.2.1 | 26.2.2 |
| Nginx | 1.31.6 | 1.31.8 |

## Retained stable, already-current pins

- Vite 8.3.5, Rolldown 1.2.15 (exact override, avoids previously observed E404 for 1.2.16), source-map-js 1.2.2.
- OpenCV Python Headless 5.0.0.93, PyYAML 6.0.3, Psycopg 3.3.6, Argon2-cffi 25.1.0.
- PostgreSQL Docker image 18.6 — keep the existing external volume unchanged.
- Docker images use exact version tags, not `latest`. Backward-incompatible PostgreSQL major upgrade is not attempted.

TorchVision 0.29.2 explicitly supports PyTorch >=2.14 per its upstream release notes. PyTorch 2.15 may change GPU wheels/CUDA dependencies; actual CUDA driver compatibility needs a live test.

## Scope and invariants

- New Alembic migration 0136_dependencies_v05122 updates only `system_settings.schema_version` and downgrades it to 0.5.121 if rolled back. Prior migration files are unmodified.
- No alterations to counting/tracking/classification/benchmark matching or ground-truth records.
- `scripts/test.ps1` retains its npm audit gate and includes a new stdlib-only dependency verification step.
- `.env`, mounted video/model/training files and external PostgreSQL volume are not embedded in this source ZIP and must be preserved on upgrade.

## Installation and verification limits

The packaging environment cannot reach npm/PyPI registries, cannot run Docker or Windows PowerShell and does not have a CUDA GPU. Hence `npm install`, `npm audit`, Vite production build, Python 3.14 Docker dependency resolution, SQLAlchemy 2.1 integration, live PostgreSQL migration and GPU inference **have not been validated here**. Static version assertions and offline tests do not prove end-to-end compatibility.

After backing up your .env and database, unpack to `D:\LienThongDH\DoAn\traffic-ai` and run:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

If Docker caches an old image, run `docker compose build --pull` (with the existing environment) then `scripts/start.ps1`. Do not run `docker compose down -v` or delete external PostgreSQL volume. If npm registry returns E404 again, collect the failing package URL and npm debug log rather than bypassing audit.

## Public version references (checked 2026-10-29)

- https://reactjs.dev/ ; https://www.npmjs.com/package/@vitejs/plugin-react
- https://pypi.org/project/fastapi/ ; https://pypi.org/project/SQLAlchemy/
- https://pypi.org/project/torch/ ; https://github.com/pytorch/vision/releases
- https://pypi.org/project/ultralytics/ ; https://pypi.org/project/pydantic/
- https://nodejs.org/en/blog ; https://hub.docker.com/_/python ; https://hub.docker.com/_/nginx
- https://www.npmjs.com/package/rolldown
