"""V0.5.74: backup jobs, unsafe uploads, RBAC, CSRF, checksum and restore approval."""
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest
from app import backup_store
from app import backup_routes
from app import auth_middleware
from test_auth_security import auth_env, signin, mutation


@pytest.fixture()
def backup_home(tmp_path, monkeypatch):
    monkeypatch.setattr(backup_store, 'ROOT', tmp_path)
    monkeypatch.setattr(backup_routes, 'ROOT', tmp_path)
    monkeypatch.setattr(auth_middleware, 'ROOT', tmp_path)
    backup_store.dirs()
    return tmp_path


def create_archive(tmp_path):
    content=b'PGDMP' + b'unit-test-dump' * 30
    ident='a'*32
    path=tmp_path/'archives'/f'{ident}.dump'
    path.write_bytes(content)
    meta={'id':ident,'created_at':'2026-10-11T08:00:00+00:00','format':'postgresql-custom',
          'pg_major':18,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest(),
          'automatic':False}
    backup_store.atomic_json(tmp_path/'archives'/f'{ident}.json',meta)
    return meta, content


def test_store_job_ids_are_safe_and_files_are_atomic(backup_home):
    job=backup_store.new_job('backup',initiated_by='admin')
    assert len(job['id']) == 32 and job['status'] == 'queued'
    assert backup_store.get_jobs()[0]['id'] == job['id']
    for val in ('../secrets', '.', 'b'*31, 'B'*32):
        with pytest.raises(ValueError):
            backup_store.safe_id(val)


def test_archive_listing_does_not_follow_symlink(backup_home):
    meta,_=create_archive(backup_home)
    assert backup_store.get_backups()[0]['id']==meta['id']
    (backup_home/'archives'/f"{meta['id']}.dump").unlink()
    (backup_home/'archives'/f"{meta['id']}.dump").symlink_to(__file__)
    assert backup_store.get_backups()==[]


def test_role_csrf_and_admin_creation(auth_env,backup_home):
    client,_=auth_env
    assert client.get('/api/admin/backups').status_code==401
    csrf=signin(client,'viewer','ViewerPassword2026!').json()['csrf_token']
    assert client.get('/api/admin/backups').status_code==403
    assert mutation(client,'/api/admin/backups',csrf=csrf).status_code==403
    client.post('/api/auth/logout',headers={'Origin':'https://testserver','X-CSRF-Token':csrf})
    csrf=signin(client,'admin','AdminPassword2026!').json()['csrf_token']
    assert client.get('/api/admin/backups').status_code==200
    assert mutation(client,'/api/admin/backups').status_code==403
    resp=mutation(client,'/api/admin/backups',csrf=csrf)
    assert resp.status_code==200 and resp.json()['status']=='queued'
    assert mutation(client,'/api/admin/backups',csrf=csrf).status_code==409


def test_transfer_and_import_checksum(auth_env,backup_home):
    client,_=auth_env
    csrf=signin(client,'admin','AdminPassword2026!').json()['csrf_token']
    meta,content=create_archive(backup_home)
    resp=client.get(f"/api/admin/backups/{meta['id']}/transfer")
    assert resp.status_code==200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        assert set(z.namelist())=={'database.dump','manifest.json','TRANSFER.txt'}
        assert z.read('database.dump')==content
        assert '.env' not in z.namelist()
    imported=client.post('/api/admin/backups/import',content=resp.content,
                         headers={'Origin':'https://testserver','X-CSRF-Token':csrf,'Content-Type':'application/zip'})
    assert imported.status_code==200, imported.text
    assert imported.json()['sha256']==meta['sha256']
    assert len(backup_store.get_backups())==2


def test_import_rejects_wrong_signature_and_path_attacks(auth_env,backup_home):
    client,_=auth_env
    csrf=signin(client,'admin','AdminPassword2026!').json()['csrf_token']
    headers={'Origin':'https://testserver','X-CSRF-Token':csrf,'Content-Type':'application/zip'}
    invalid=client.post('/api/admin/backups/import',headers=headers,content=b'0'*300)
    assert invalid.status_code==422
    pack=io.BytesIO()
    with zipfile.ZipFile(pack,'w') as z:
        z.writestr('../escape','unsafe')
        z.writestr('manifest.json','{}')
        z.writestr('database.dump','not a dump')
    unsafe=client.post('/api/admin/backups/import',headers=headers,content=pack.getvalue())
    assert unsafe.status_code==422
    assert not list((backup_home/'archives').glob('*.dump'))


def test_restore_requires_explicit_confirmation(auth_env,backup_home):
    client,_=auth_env
    csrf=signin(client,'admin','AdminPassword2026!').json()['csrf_token']
    meta,_=create_archive(backup_home)
    path='/api/admin/backups/restore'
    assert mutation(client,path,csrf=csrf,body={'backup_id':meta['id'],'confirmation':'yes'}).status_code==422
    res=mutation(client,path,csrf=csrf,body={'backup_id':meta['id'],'confirmation':'KHOI PHUC traffic_ai_db'})
    assert res.status_code==200, res.text
    assert res.json()['status']=='queued' and res.json()['action']=='restore'


def test_maintenance_denies_api_writes(auth_env,backup_home):
    client,_=auth_env
    (backup_home/'restore-maintenance.flag').write_text('some-job')
    assert client.get('/api/health').status_code==503
    assert client.post('/api/auth/login',json={},headers={'Origin':'https://testserver'}).status_code==503


def test_schedule_api_is_admin_only_and_persisted(auth_env,backup_home):
    client,_=auth_env
    csrf=signin(client,'viewer','ViewerPassword2026!').json()['csrf_token']
    assert mutation(client,'/api/admin/backups/settings',csrf=csrf,body={'automatic':True,'hours':6,'retention':7}).status_code==403
    client.post('/api/auth/logout',headers={'Origin':'https://testserver','X-CSRF-Token':csrf})
    csrf=signin(client,'admin','AdminPassword2026!').json()['csrf_token']
    assert mutation(client,'/api/admin/backups/settings',csrf=csrf,body={'automatic':True,'hours':0,'retention':1}).status_code==422
    valid=mutation(client,'/api/admin/backups/settings',csrf=csrf,body={'automatic':False,'hours':8,'retention':5})
    assert valid.status_code==200 and valid.json()=={'automatic':False,'hours':8,'retention':5}
    assert client.get('/api/admin/backups').json()['settings']==valid.json()
