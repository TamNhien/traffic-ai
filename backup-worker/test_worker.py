"""Isolated Python stdlib worker tests, no PostgreSQL dependency."""
import importlib.util
import json
import os
from pathlib import Path

os.environ.setdefault('POSTGRES_DB','traffic_ai_db')
os.environ.setdefault('POSTGRES_USER','traffic_admin')
os.environ.setdefault('POSTGRES_PASSWORD','test-only')
spec=importlib.util.spec_from_file_location('traffic_backup_worker', Path(__file__).with_name('worker.py'))
worker=importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def test_backup_custom_dump_and_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(worker,'ROOT',tmp_path)
    monkeypatch.setattr(worker,'ARCHIVES',tmp_path/'archives')
    monkeypatch.setattr(worker,'JOBS',tmp_path/'jobs')
    worker.ARCHIVES.mkdir()
    worker.JOBS.mkdir()
    def fake_run(cmd,timeout=0):
        if cmd[0]=='pg_dump':
            Path(cmd[cmd.index('--file')+1]).write_bytes(b'PGDMPexample')
        return ''
    monkeypatch.setattr(worker,'run',fake_run)
    meta=worker.backup('a'*32,automatic=True)
    assert meta['bytes']==12 and meta['automatic']
    assert (worker.ARCHIVES/('a'*32+'.dump')).read_bytes()==b'PGDMPexample'
    assert worker.backup.__doc__ is None or isinstance(worker.backup.__doc__,str)


def test_restore_checks_checksum_before_postgres_commands(tmp_path,monkeypatch):
    monkeypatch.setattr(worker,'ARCHIVES',tmp_path)
    ident='b'*32
    (tmp_path/(ident+'.dump')).write_bytes(b'PGDMPdamaged')
    (tmp_path/(ident+'.json')).write_text(json.dumps({'sha256':'0'*64,'bytes':12,'pg_major':18}))
    def forbidden(*args,**kwargs):
        raise AssertionError('No restore commands before checksum verification')
    monkeypatch.setattr(worker,'run',forbidden)
    try:
        worker.restore(ident)
        raise AssertionError('Expected checksum rejection')
    except RuntimeError as exc:
        assert 'checksum' in str(exc)


def test_restore_failure_before_swap_preserves_live_db(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, 'ROOT', tmp_path)
    monkeypatch.setattr(worker, 'ARCHIVES', tmp_path/'archives')
    worker.ARCHIVES.mkdir()
    ident = 'c'*32
    archive=worker.ARCHIVES/(ident+'.dump')
    archive.write_bytes(b'PGDMPvalid-structure-placeholder')
    meta={'sha256':worker.digest_file(archive), 'bytes':archive.stat().st_size,'pg_major':18}
    (worker.ARCHIVES/(ident+'.json')).write_text(json.dumps(meta))
    commands=[]
    def fake_run(cmd, timeout=3600, database=None):
        commands.append(cmd)
        if cmd[0]=='pg_restore' and '--list' not in cmd:
            raise RuntimeError('simulated pg_restore failure')
        return ''
    monkeypatch.setattr(worker, 'run', fake_run)
    try:
        worker.restore(ident)
        raise AssertionError('Expected failure')
    except RuntimeError as exc:
        assert 'simulated' in str(exc)
    assert not any('RENAME TO' in str(cmd) for cmd in commands)
    assert not (tmp_path/'restore-maintenance.flag').exists()


def test_restore_switch_is_fenced_and_retains_old_db(tmp_path,monkeypatch):
    monkeypatch.setattr(worker,'ROOT',tmp_path)
    monkeypatch.setattr(worker,'ARCHIVES',tmp_path/'archives')
    worker.ARCHIVES.mkdir()
    ident='d'*32
    dump=worker.ARCHIVES/(ident+'.dump')
    dump.write_bytes(b'PGDMPplaceholder')
    (worker.ARCHIVES/(ident+'.json')).write_text(json.dumps({
        'sha256':worker.digest_file(dump),'bytes':dump.stat().st_size,'pg_major':18
    }))
    commands=[]
    def fake_run(cmd, timeout=3600, database=None):
        commands.append(cmd)
        return ''
    monkeypatch.setattr(worker,'run',fake_run)
    result=worker.restore(ident)
    assert result['restored_database']=='traffic_ai_db'
    assert result['rollback_database']=='traffic_old_'+ident[:12]
    assert not (tmp_path/'restore-maintenance.flag').exists()
    assert any('ALTER DATABASE' in str(command) and 'COMMIT' in str(command) for command in commands)
