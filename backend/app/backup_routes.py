"""Admin-only backup APIs; PostgreSQL commands run only in isolated backup-worker."""
from __future__ import annotations
import json
import os
from pathlib import Path
import secrets
import zipfile
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask
from app.auth_routes import admin
from app.backup_store import (ROOT, MAX_UPLOAD, atomic_json, backup_path,
                              dirs, get_backups, get_jobs, new_job,
                              read_json, safe_id, sha256_file, get_schedule)

router = APIRouter(prefix='/api/admin/backups', tags=['Backups'])


def find_backup(ident):
    try:
        safe_id(ident)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    item = next((row for row in get_backups() if row['id'] == ident), None)
    if not item:
        raise HTTPException(404, detail='Không tìm thấy bản sao lưu')
    return item


@router.get('')
def index(_=Depends(admin)):
    return {'backups':get_backups(), 'jobs':get_jobs(),
            'settings':get_schedule(),
            'database':os.getenv('POSTGRES_DB','traffic_ai_db')}


class BackupSchedule(BaseModel):
    automatic: bool
    hours: int = Field(ge=1, le=720)
    retention: int = Field(ge=1, le=365)


@router.post('/settings')
def save_schedule(payload:BackupSchedule, _=Depends(admin)):
    dirs()
    atomic_json(ROOT/'schedule.json',payload.model_dump())
    return get_schedule()


@router.post('')
def request_backup(user=Depends(admin)):
    if any(job['status'] in ('queued','running') for job in get_jobs(100)):
        raise HTTPException(409, detail='Đang có tác vụ sao lưu/khôi phục; vui lòng đợi')
    return new_job('backup', initiated_by=user.username)


@router.get('/{backup_id}/download')
def download_dump(backup_id: str, _=Depends(admin)):
    item = find_backup(backup_id)
    path = backup_path(backup_id)
    return FileResponse(path, media_type='application/octet-stream',
                        filename=f'traffic-ai-{backup_id}.dump',
                        headers={'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff'})


@router.get('/{backup_id}/transfer')
def download_transfer(backup_id: str, _=Depends(admin)):
    """Portable ZIP contains pg_dump and integrity metadata, NEVER .env or keys."""
    meta = find_backup(backup_id)
    source = backup_path(backup_id)
    if sha256_file(source) != meta['sha256']:
        raise HTTPException(409, detail='Checksum bản sao lưu không khớp, không thể xuất gói')
    dirs()
    tmp = ROOT/'incoming'/f'.transfer-{secrets.token_hex(16)}.zip'
    try:
        with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as out:
            out.write(source, 'database.dump')
            out.writestr('manifest.json', json.dumps(meta, ensure_ascii=False, indent=2))
            out.writestr('TRANSFER.txt', 'Traffic AI portable PostgreSQL 18 backup.\n'
                         'Import in Admin > Backup/Restore on destination machine.\n'
                         'Includes database only: transfer .env, models, videos, datasets separately.\n'
                         'Keep this ZIP private; it contains account records and operational data.\n')
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return FileResponse(tmp, media_type='application/zip', filename=f'traffic-ai-transfer-{backup_id}.zip',
                        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'},
                        background=BackgroundTask(tmp.unlink, missing_ok=True))


@router.post('/import')
async def import_backup(request: Request, _=Depends(admin)):
    """Stream upload; never unzip arbitrary entries or trust archive-supplied paths."""
    media = request.headers.get('content-type', '').split(';')[0].lower()
    if media not in ('application/zip','application/octet-stream','application/x-zip-compressed'):
        raise HTTPException(415, detail='Chọn tệp .zip chuyển máy hoặc .dump PostgreSQL')
    length = request.headers.get('content-length')
    if length and (not length.isdecimal() or int(length) > MAX_UPLOAD):
        raise HTTPException(413, detail='Tệp vượt giới hạn 1 GB')
    dirs()
    identifier = secrets.token_hex(16)
    temp = ROOT/'incoming'/(identifier + '.upload')
    total = 0
    try:
        with temp.open('xb') as out:
            async for chunk in request.stream():
                total += len(chunk)
                if total > MAX_UPLOAD:
                    raise HTTPException(413, detail='Tệp vượt giới hạn 1 GB')
                out.write(chunk)
        if total < 128:
            raise HTTPException(422, detail='Tệp quá nhỏ, không phải PostgreSQL backup')
        target = ROOT/'archives'/(identifier+'.dump')
        if zipfile.is_zipfile(temp):
            with zipfile.ZipFile(temp) as archive:
                if len(archive.namelist()) != 3 or set(archive.namelist()) != {'database.dump','manifest.json','TRANSFER.txt'}:
                    raise HTTPException(422, detail='Gói chuyển máy không đúng cấu trúc Traffic AI')
                item=archive.getinfo('database.dump')
                if item.file_size > MAX_UPLOAD or item.is_dir():
                    raise HTTPException(413, detail='Database vượt giới hạn 1 GB')
                if archive.getinfo('manifest.json').file_size > 32768 or archive.getinfo('TRANSFER.txt').file_size > 32768:
                    raise HTTPException(422, detail='Metadata gói sao lưu quá lớn')
                manifest=json.loads(archive.read('manifest.json'))
                if manifest.get('format') != 'postgresql-custom' or manifest.get('pg_major') != 18:
                    raise HTTPException(422, detail='Gói không tương thích PostgreSQL 18')
                with archive.open('database.dump') as source, target.open('xb') as out:
                    for chunk in iter(lambda:source.read(1024*1024),b''):
                        out.write(chunk)
                if sha256_file(target) != manifest.get('sha256') or target.stat().st_size != manifest.get('bytes'):
                    raise HTTPException(422, detail='Checksum database không khớp')
        else:
            # Custom-format pg_dump magic. Worker also validates pg_restore --list.
            with temp.open('rb') as f:
                if f.read(5) != b'PGDMP':
                    raise HTTPException(422, detail='Không phải PostgreSQL custom dump')
            os.replace(temp,target)
        if not target.is_file():
            raise HTTPException(422, detail='Không có nội dung sao lưu')
        # zip branch still checks magic to reject unrelated data.
        with target.open('rb') as f:
            if f.read(5) != b'PGDMP':
                raise HTTPException(422, detail='Dữ liệu không phải pg_dump custom')
        meta={'id':identifier, 'database':os.getenv('POSTGRES_DB','traffic_ai_db'),
              'created_at':datetime.now(timezone.utc).isoformat(), 'bytes':target.stat().st_size,
              'sha256':sha256_file(target), 'format':'postgresql-custom', 'pg_major':18,
              'automatic':False,'imported':True,'version':'0.5.118'}
        atomic_json(ROOT/'archives'/(identifier+'.json'),meta)
        return meta
    except (ValueError, json.JSONDecodeError, zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise HTTPException(422, detail=f'Gói backup không hợp lệ: {str(exc)[:140]}') from exc
    finally:
        temp.unlink(missing_ok=True)
        # On any failed import the unregistered dump is not left behind.
        if not (ROOT/'archives'/(identifier+'.json')).is_file():
            (ROOT/'archives'/(identifier+'.dump')).unlink(missing_ok=True)


class RestoreRequest(BaseModel):
    backup_id: str
    confirmation: str


@router.post('/restore')
def request_restore(payload:RestoreRequest, user=Depends(admin)):
    """Require explicit database-specific confirmation; immutable pre-restore DB kept."""
    item=find_backup(payload.backup_id)
    expected='KHOI PHUC '+os.getenv('POSTGRES_DB','traffic_ai_db')
    if payload.confirmation != expected:
        raise HTTPException(422, detail=f'Nhập chính xác: {expected}')
    if any(j['status'] in ('queued','running') for j in get_jobs(100)):
        raise HTTPException(409, detail='Đang có tác vụ khác, không được khôi phục đồng thời')
    if sha256_file(backup_path(item['id'])) != item['sha256']:
        raise HTTPException(422,detail='Checksum tệp không khớp')
    return new_job('restore', backup_id=item['id'], initiated_by=user.username)
