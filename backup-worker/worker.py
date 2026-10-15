"""Isolated PostgreSQL 18 backup & offline-staging restore worker (stdlib only).
Never accepts network requests; backend communicates via constrained on-disk jobs.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
from datetime import datetime, timezone, timedelta

ROOT = Path('/backups')
ARCHIVES = ROOT / 'archives'
JOBS = ROOT / 'jobs'
HOST = os.getenv('POSTGRES_HOST', 'postgres')
PORT = os.getenv('POSTGRES_PORT', '5432')
DB = os.environ['POSTGRES_DB']
USER = os.environ['POSTGRES_USER']
PG_ENV = {**os.environ, 'PGPASSWORD': os.environ['POSTGRES_PASSWORD'], 'PGCONNECT_TIMEOUT': '10'}
MIN_HOURS = max(1, min(720, int(os.getenv('BACKUP_INTERVAL_HOURS', '24'))))
RETENTION = max(1, min(365, int(os.getenv('BACKUP_RETENTION_COUNT', '14'))))
AUTO = os.getenv('BACKUP_AUTO_ENABLED', 'true').lower() in ('1', 'true', 'yes')


def utc():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    temp = path.with_name('.' + path.name + '.' + secrets.token_hex(6))
    with temp.open('x', encoding='utf-8') as out:
        json.dump(value, out, ensure_ascii=False)
        out.flush(); os.fsync(out.fileno())
    os.replace(temp, path)


def run(cmd, timeout=3600, database=None):
    # no shell, credentials only via environment, capped wall time
    env = {**PG_ENV}
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode:
        # Do not log connection strings, secrets or untrusted SQL from archive
        raise RuntimeError(f'PostgreSQL command failed (exit {result.returncode}): {result.stderr[:250]}')
    return result.stdout


def base_cmd(name, database=DB):
    return [name, '-h', HOST, '-p', PORT, '-U', USER, '-d', database]


def digest_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def metadata(ident, archive, automatic=False):
    return {'id':ident, 'database':DB, 'created_at':utc(), 'bytes':archive.stat().st_size,
            'sha256':digest_file(archive), 'format':'postgresql-custom', 'pg_major':18,
            'automatic':automatic, 'version':'0.5.92'}


def schedule():
    default={'automatic':AUTO,'hours':MIN_HOURS,'retention':RETENTION}
    try:
        entry=json.loads((ROOT/'schedule.json').read_text(encoding='utf-8'))
        if (isinstance(entry.get('automatic'),bool)
            and type(entry.get('hours')) is int and 1<=entry['hours']<=720
            and type(entry.get('retention')) is int and 1<=entry['retention']<=365):
            return entry
    except (ValueError,OSError,KeyError,TypeError):
        pass
    return default


def prune():
    scheduled = []
    for p in ARCHIVES.glob('*.json'):
        try:
            entry = json.loads(p.read_text(encoding='utf-8'))
            if entry.get('automatic'):
                scheduled.append((entry.get('created_at',''), p))
        except (OSError, ValueError):
            continue
    scheduled.sort(reverse=True)
    # Retain manually triggered archives (administrator owns their deletion policy).
    for _, path in scheduled[schedule()['retention']:]:
        archive = path.with_suffix('.dump')
        archive.unlink(missing_ok=True)
        path.unlink(missing_ok=True)


def backup(ident=None, automatic=False):
    ident = ident or secrets.token_hex(16)
    if not (len(ident) == 32 and all(c in '0123456789abcdef' for c in ident)):
        raise RuntimeError('Invalid backup ID')
    dest = ARCHIVES / (ident + '.dump')
    temp = ARCHIVES / ('.' + ident + '.partial')
    if dest.exists():
        raise RuntimeError('Archive already exists')
    try:
        run([*base_cmd('pg_dump'), '--format=custom', '--compress=6', '--no-owner', '--no-acl', '--file', str(temp)], timeout=7200)
        if not temp.is_file() or temp.stat().st_size == 0:
            raise RuntimeError('Empty archive')
        run(['pg_restore', '--list', str(temp)], timeout=180)
        os.replace(temp, dest)
        meta = metadata(ident, dest, automatic)
        atomic_json(ARCHIVES / (ident + '.json'), meta)
        prune()
        return meta
    finally:
        temp.unlink(missing_ok=True)


def restore(ident):
    """Restore to NEW DB, verify success, then switch names, keeping previous DB for rollback.
    Never use pg_restore --clean against the live DB. Database swap is a short interruption;
    backend and worker connections are forcibly disconnected at cutover.
    """
    meta_path = ARCHIVES / (ident + '.json')
    dump = ARCHIVES / (ident + '.dump')
    if not dump.is_file() or dump.is_symlink() or not meta_path.is_file():
        raise RuntimeError('Backup does not exist')
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    if meta['sha256'] != digest_file(dump) or meta['bytes'] != dump.stat().st_size:
        raise RuntimeError('Backup checksum mismatch')
    if int(meta.get('pg_major', 0)) != 18:
        raise RuntimeError('PostgreSQL major mismatch; use PostgreSQL 18')
    run(['pg_restore', '--list', str(dump)], 180)
    suffix = ident[:12]
    stage = f'traffic_stage_{suffix}'
    previous = f'traffic_old_{suffix}'
    if any(len(s) > 63 for s in (DB, stage, previous)):
        raise RuntimeError('PostgreSQL identifier too long')
    # Safe identifiers: generated stage/previous only; target DB comes from trusted env.
    import re
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', DB):
        raise RuntimeError('Database identifier must contain only ASCII letters, digits, underscores')
    admin = base_cmd('psql', 'postgres') + ['-v', 'ON_ERROR_STOP=1', '-X', '-q', '-A', '-t']
    def sql(query):
        return run([*admin, '-c', query], 180)
    sql(f'CREATE DATABASE "{stage}" TEMPLATE template0')
    try:
        run([*base_cmd('pg_restore', stage), '--no-owner', '--no-acl', '--exit-on-error', '--single-transaction', str(dump)], 7200)
        # No cutover until restored DB passes essential integrity checks.
        run([*base_cmd('psql', stage), '-v', 'ON_ERROR_STOP=1', '-X', '-c',
             'SELECT count(*) FROM alembic_version'], 180)
        # Do not allow API/AI writes during the short cutover. Old DB is retained.
        # ALTER DATABASE RENAME is transactional; either both names swap or none do.
        flag = ROOT / 'restore-maintenance.flag'
        flag.write_text(ident, encoding='ascii')
        try:
            sql(f'''BEGIN;
                 SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('{DB}', '{stage}') AND pid <> pg_backend_pid();
                 ALTER DATABASE "{DB}" RENAME TO "{previous}";
                 ALTER DATABASE "{stage}" RENAME TO "{DB}";
                 COMMIT;''')
        finally:
            flag.unlink(missing_ok=True)
        return {'restored_database': DB, 'rollback_database': previous,
                'notice': 'Khôi phục thành công; DB cũ được giữ lại để hoàn tác. Khởi động lại backend/AI để áp dụng.'}
    except Exception:
        # Failure before swap leaves live database intact and available.
        try:
            sql(f'''SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{stage}';''')
            sql(f'DROP DATABASE IF EXISTS "{stage}"')
        except Exception:
            pass
        raise


def work(job_path):
    job = json.loads(job_path.read_text(encoding='utf-8'))
    if job.get('status') != 'queued' or job.get('id') != job_path.stem:
        return
    if job.get('action') not in ('backup', 'restore'):
        return
    job.update(status='running', started_at=utc(), message='Đang thực thi trên PostgreSQL')
    atomic_json(job_path, job)
    try:
        if job['action'] == 'backup':
            result = backup(job['id'])
            job.update(backup_id=result['id'], result=result)
        else:
            result = restore(job['backup_id'])
            job.update(result=result)
        job.update(status='completed', message='Hoàn tất')
    except Exception as exc:
        job.update(status='failed', message=str(exc)[:350])
    job['finished_at'] = utc()
    atomic_json(job_path, job)


def main():
    for directory in (ROOT, ARCHIVES, JOBS, ROOT/'incoming'):
        directory.mkdir(parents=True, exist_ok=True)
    print('Traffic AI backup-worker V0.5.92 ready', flush=True)
    # Persist schedule across container restarts; a failed automatic run is retried after 15 min.
    retry_after = 0.0
    while True:
        try:
            for job_path in sorted(JOBS.glob('*.json'), key=lambda p: p.stat().st_mtime):
                if len(job_path.stem) == 32 and all(c in '0123456789abcdef' for c in job_path.stem):
                    work(job_path)
            config = schedule()
            if config['automatic'] and time.monotonic() >= retry_after:
                metas = []
                for p in ARCHIVES.glob('*.json'):
                    try:
                        item = json.loads(p.read_text(encoding='utf-8'))
                        if item.get('automatic'):
                            metas.append(datetime.fromisoformat(item['created_at']))
                    except (ValueError, KeyError, OSError):
                        pass
                if not metas or max(metas) <= datetime.now(timezone.utc) - timedelta(hours=config['hours']):
                    try:
                        backup(automatic=True)
                    except Exception:
                        retry_after = time.monotonic() + 900
                        raise
        except Exception as exc:
            print(f'[Backup] Task failed: {str(exc)[:300]}', flush=True)
        time.sleep(10)

if __name__ == '__main__':
    main()
