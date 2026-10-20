"""V0.5.110: lazy repair only a terminal, session-bound trace."""
import json
import gzip
from concurrent.futures import ThreadPoolExecutor
from app import benchmark_trace as bt


def _write(tmp_path, session=207, *, closed=True, wrong_session=False):
    path=bt.trace_path(session)
    path.parent.mkdir(parents=True,exist_ok=True)
    rows=[{'kind':'session_metadata','session_id':session,'source_frame_count':2},
          {'kind':'geometry_metadata','session_id':session},
          {'camera_id':1,'session_id':session,'frame_index':1,'source_time_seconds':0.0},
          {'camera_id':1,'session_id':session,'frame_index':2,'source_time_seconds':0.04}]
    if closed:
        rows.append({'kind':'delivery_summary','session_id':session+1 if wrong_session else session,
                     'delivery_drain_complete':True,'pending_events':0})
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf8')
    return path


def test_v05110_repair_publishes_completed_trace_without_touching_source(tmp_path, monkeypatch):
    monkeypatch.setattr(bt,'TRACE_ROOT',tmp_path)
    source=_write(tmp_path)
    before=source.read_bytes()
    assert bt.closed_compressed_trace(207) is None
    path,cert=bt.ensure_closed_compressed_trace(207)
    assert gzip.decompress(path.read_bytes())==before==source.read_bytes()
    assert cert['closed'] is True and cert['source_bytes']==len(before)
    assert bt.ensure_closed_compressed_trace(207)[0]==path


def test_v05110_active_or_incomplete_trace_refuses_lazy_repair(tmp_path, monkeypatch):
    monkeypatch.setattr(bt,'TRACE_ROOT',tmp_path)
    _write(tmp_path,closed=False)
    assert bt.ensure_closed_compressed_trace(207) is None
    assert sorted(x.name for x in tmp_path.iterdir()) == ['session_207.jsonl']


def test_v05110_wrong_session_footer_refuses_repair(tmp_path, monkeypatch):
    monkeypatch.setattr(bt,'TRACE_ROOT',tmp_path)
    _write(tmp_path,wrong_session=True)
    assert bt.ensure_closed_compressed_trace(207) is None


def test_v05110_raw_size_limit_fails_closed(tmp_path,monkeypatch):
    monkeypatch.setattr(bt,'TRACE_ROOT',tmp_path)
    _write(tmp_path)
    monkeypatch.setattr(bt,'TRACE_LAZY_SOURCE_MAX_BYTES',3)
    assert bt.ensure_closed_compressed_trace(207) is None


def test_v05110_parallel_recovery_serializes_certification(tmp_path,monkeypatch):
    monkeypatch.setattr(bt,'TRACE_ROOT',tmp_path)
    _write(tmp_path)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(bt.ensure_closed_compressed_trace,[207]*3))
    assert all(x is not None for x in results)
    assert len({x[1]['compressed_sha256'] for x in results})==1
