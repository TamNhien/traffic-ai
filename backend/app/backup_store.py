"""Filesystem job bridge: web/backend cannot access Docker socket or pg_dump credentials.
Only the isolated backup-worker executes PostgreSQL tools; all paths are server-derived.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
from datetime import datetime, timezone

ROOT = Path(os.getenv('BACKUP_STORAGE_DIR', '/data/backups'))
ID = re.compile(r'^[a-f0-9]{32}$')
MAX_UPLOAD = 1024 * 1024 * 1024  # compressed bytes; configurable only downward through reverse-proxy


def dirs():
    for name in ('archives', 'jobs', 'incoming'):
        (ROOT / name).mkdir(parents=True, exist_ok=True, mode=0o700)


def safe_id(value):
    if not ID.fullmatch(value or ''):
        raise ValueError('Mã bản sao lưu không hợp lệ')
    return value


def atomic_json(path, data):
    path = Path(path)
    temp = path.with_name('.' + path.name + '.' + secrets.token_hex(6))
    with temp.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def read_json(path):
    with Path(path).open(encoding='utf-8') as f:
        return json.load(f)


def new_job(action, backup_id=None, initiated_by=None):
    if action not in ('backup', 'restore'):
        raise ValueError('Unsupported action')
    dirs()
    if backup_id is not None:
        safe_id(backup_id)
    ident = secrets.token_hex(16)
    job = {'id': ident, 'action': action, 'backup_id': backup_id,
           'status': 'queued', 'created_at': datetime.now(timezone.utc).isoformat(),
           'initiated_by': initiated_by, 'message': 'Đang chờ bộ xử lý backup'}
    atomic_json(ROOT / 'jobs' / (ident + '.json'), job)
    return job


def get_jobs(limit=30):
    dirs()
    return sorted((read_json(p) for p in (ROOT / 'jobs').glob('*.json') if ID.fullmatch(p.stem)),
                  key=lambda item: item.get('created_at', ''), reverse=True)[:limit]


def get_backups():
    dirs()
    rows = []
    for meta_path in (ROOT / 'archives').glob('*.json'):
        if not ID.fullmatch(meta_path.stem):
            continue
        try:
            meta = read_json(meta_path)
            archive = ROOT / 'archives' / (meta_path.stem + '.dump')
            if not archive.is_file() or archive.is_symlink():
                continue
            if meta.get('id') != meta_path.stem or archive.stat().st_size != meta.get('bytes'):
                continue
            rows.append(meta)
        except (ValueError, OSError, json.JSONDecodeError):
            continue
    return sorted(rows, key=lambda item: item.get('created_at', ''), reverse=True)


def backup_path(ident):
    safe_id(ident)
    path = ROOT / 'archives' / (ident + '.dump')
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(ident)
    return path


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def get_schedule():
    defaults={'automatic': os.getenv('BACKUP_AUTO_ENABLED', 'true').lower() in ('true','1','yes'),
              'hours': int(os.getenv('BACKUP_INTERVAL_HOURS','24')),
              'retention': int(os.getenv('BACKUP_RETENTION_COUNT','14'))}
    path=ROOT/'schedule.json'
    try:
        configured=read_json(path)
        if (isinstance(configured.get('automatic'),bool)
            and type(configured.get('hours')) is int and 1<=configured['hours']<=720
            and type(configured.get('retention')) is int and 1<=configured['retention']<=365):
            return {k:configured[k] for k in defaults}
    except (OSError,ValueError,KeyError,TypeError):
        pass
    return defaults
