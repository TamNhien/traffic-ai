#!/usr/bin/env python3
"""V0.5.110: recover an omitted benchmark trace from a matching camera RAR.

This is a *derived* evidence ZIP, not an official AI-service trace certificate.
The backend's report, GT, events, session, and config stay byte-for-byte identical.
No AI crossings, GT marks, scoring or policy decisions are changed.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, BadZipFile

MAX_SOURCE_BYTES = 512 * 1024 * 1024
MAX_TRANSPORT_BYTES = 128 * 1024 * 1024
MAX_JSON_BYTES = 16 * 1024 * 1024
REQUIRED = ('report.json', 'ground-truth.json', 'events.json', 'session.json', 'config.json')


class RecoveryError(ValueError):
    pass


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fp:
        for block in iter(lambda: fp.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _find_7zip() -> str | None:
    candidates = [shutil.which('7z'), shutil.which('7za'), shutil.which('7zz')]
    if os.name == 'nt':
        candidates += [str(Path(os.getenv('ProgramFiles', 'C:\\Program Files')) / '7-Zip' / '7z.exe'),
                       str(Path(os.getenv('ProgramFiles(x86)', 'C:\\Program Files (x86)')) / '7-Zip' / '7z.exe')]
    return next((str(c) for c in candidates if c and Path(c).is_file()), None)


@contextmanager
def source_stream(*, camera_rar: Path | None, trace_jsonl: Path | None, session: int):
    if (camera_rar is None) == (trace_jsonl is None):
        raise RecoveryError('Specify exactly one of --camera-rar or --trace-jsonl')
    if trace_jsonl is not None:
        with trace_jsonl.open('rb') as fp:
            yield fp
        return
    tool = _find_7zip()
    if not tool:
        raise RecoveryError('7-Zip not found. Install 7-Zip or extract the RAR and use --trace-jsonl')
    # Pass the expected member by its exact session-bound name. No shell,
    # wildcards, path traversal or extraction to the working directory.
    member = f'session_{session}_benchmark-trace.jsonl'
    proc = subprocess.Popen([tool, 'e', '-so', str(camera_rar.resolve()), member],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        assert proc.stdout is not None
        yield proc.stdout
        proc.stdout.close()
        if proc.wait(timeout=20) != 0:
            raise RecoveryError('RAR member missing, corrupt, or 7-Zip extraction failed')
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def _source_metadata(archive: ZipFile) -> tuple[dict, dict, dict[str, bytes]]:
    names = archive.namelist()
    if len(names) != len(set(names)) or any(k not in names for k in (*REQUIRED, 'manifest.json')):
        raise RecoveryError('Invalid or incomplete benchmark ZIP')
    payload = {}
    for name in (*REQUIRED, 'manifest.json'):
        if not 0 < archive.getinfo(name).file_size <= MAX_JSON_BYTES:
            raise RecoveryError(f'Invalid JSON member size: {name}')
        payload[name] = archive.read(name)
    try:
        manifest = json.loads(payload['manifest.json'])
        report = json.loads(payload['report.json'])
        session = json.loads(payload['session.json'])
    except (UnicodeError, ValueError) as exc:
        raise RecoveryError('Invalid JSON in original export') from exc
    if (manifest.get('format') != 'traffic-ai-benchmark-diagnostics' or manifest.get('schema_version') != 1
            or not isinstance(session.get('id'), int)
            or session['id'] != manifest.get('session_id') or report.get('session_id') != session['id']
            or report.get('benchmark', {}).get('id') != manifest.get('benchmark_id')):
        raise RecoveryError('Original export session/report identity mismatch')
    trace = manifest.get('trace', {})
    if trace.get('available') or 'benchmark-trace.jsonl.gz' in names or 'benchmark-trace.jsonl' in names:
        raise RecoveryError('Original export already includes a trace; will not replace evidence')
    for name in REQUIRED:
        entry = manifest.get('files', {}).get(name, {})
        if entry.get('bytes') != len(payload[name]) or entry.get('sha256') != hashlib.sha256(payload[name]).hexdigest():
            raise RecoveryError(f'Original manifest integrity mismatch: {name}')
    if report.get('ground_truth_total') != report.get('matched', 0) + report.get('missed', 0):
        raise RecoveryError('Ground Truth score conservation failed')
    if report.get('ai_total') != report.get('matched', 0) + report.get('false_positives', 0):
        raise RecoveryError('AI score conservation failed')
    return manifest, session, {k: payload[k] for k in REQUIRED}


def _compress_and_verify(raw, dest: Path, session: int, max_source: int = MAX_SOURCE_BYTES,
                         max_transport: int = MAX_TRANSPORT_BYTES) -> dict:
    digest = hashlib.sha256()
    bytes_read = 0
    frames = 0
    first_frame = None
    last_frame = None
    metadata = None
    geometry = False
    footer = False
    line_count = 0
    last_kind = None
    with dest.open('wb') as output, gzip.GzipFile(filename='', fileobj=output, mode='wb',
                                                   mtime=0, compresslevel=6) as compressed:
        for line in raw:
            bytes_read += len(line)
            line_count += 1
            if bytes_read > max_source or len(line) > 4 * 1024 * 1024:
                raise RecoveryError('Raw trace exceeds bounded source/row size')
            if not line.endswith(b'\n'):
                raise RecoveryError('Incomplete trace line')
            digest.update(line)
            compressed.write(line)
            if output.tell() > max_transport:
                raise RecoveryError('Compressed trace exceeds bounded ZIP transport size')
            try:
                record = json.loads(line)
            except (UnicodeError, ValueError) as exc:
                raise RecoveryError('Invalid trace JSONL record') from exc
            kind = record.get('kind')
            last_kind = kind
            if line_count == 1 and kind != 'session_metadata':
                raise RecoveryError('Missing first session metadata record')
            if kind == 'session_metadata':
                if metadata is not None or record.get('session_id') != session:
                    raise RecoveryError('Duplicate or mismatched trace session metadata')
                metadata = record
            elif kind == 'geometry_metadata':
                if geometry or record.get('session_id') != session:
                    raise RecoveryError('Invalid geometry metadata')
                geometry = True
            elif kind == 'delivery_summary':
                if footer or record.get('session_id') != session or record.get('delivery_drain_complete') is not True \
                        or record.get('pending_events') != 0:
                    raise RecoveryError('Incomplete/duplicate delivery footer')
                footer = True
            if kind is None and 'frame_index' in record:
                if footer:
                    raise RecoveryError('Frame found after terminal delivery footer')
                idx = record['frame_index']
                if type(idx) is not int or idx != frames + 1 or record.get('session_id') != session:
                    raise RecoveryError('Frame sequence invalid or belongs to another session')
                frames += 1
                if first_frame is None:
                    first_frame = idx
                last_frame = idx
    if not metadata or not geometry or not footer or frames < 1 or last_kind != 'delivery_summary':
        raise RecoveryError('Trace is not closed or lacks complete frame evidence')
    expected = metadata.get('source_frame_count')
    if type(expected) is not int or frames != expected:
        raise RecoveryError(f'Trace frame count {frames} differs from expected {expected}')
    if dest.stat().st_size > max_transport:
        raise RecoveryError('Compressed trace exceeds bounded ZIP transport size')
    return {'source_bytes': bytes_read, 'source_sha256': digest.hexdigest(),
            'compressed_bytes': dest.stat().st_size, 'compressed_sha256': _sha256_file(dest),
            'frame_count': frames, 'line_count': line_count, 'runtime_version': metadata.get('ai_runtime_version')}


def recover(export: Path, out: Path, *, camera_rar: Path | None = None,
            trace_jsonl: Path | None = None, max_source: int = MAX_SOURCE_BYTES,
            max_transport: int = MAX_TRANSPORT_BYTES) -> dict:
    export, out = Path(export).resolve(), Path(out).resolve()
    if out == export or out.exists():
        raise RecoveryError('Output must be a new file; original evidence cannot be overwritten')
    with ZipFile(export) as zipped:
        manifest, session, payload = _source_metadata(zipped)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.traffic-trace-recovery-', dir=out.parent) as tmp:
        compressed_path = Path(tmp) / 'trace.jsonl.gz'
        with source_stream(camera_rar=camera_rar, trace_jsonl=trace_jsonl, session=session['id']) as raw:
            result = _compress_and_verify(raw, compressed_path, session['id'], max_source, max_transport)
        trace_name = 'benchmark-trace.jsonl.gz'
        manifest['files'][trace_name] = {'bytes': result['compressed_bytes'], 'sha256': result['compressed_sha256']}
        manifest['trace'] = {
            'available': True, 'reason': 'available', 'bytes': result['compressed_bytes'],
            'max_bytes': MAX_TRANSPORT_BYTES, 'encoding': 'gzip', 'closed': True,
            'source_bytes': result['source_bytes'], 'source_sha256': result['source_sha256'],
            'compressed_sha256': result['compressed_sha256'],
            'recovered_from_camera_archive': camera_rar is not None,
        }
        manifest['recovery'] = {
            'derived_evidence': True, 'source': 'camera-rar' if camera_rar is not None else 'local-jsonl',
            'source_filename': (camera_rar or trace_jsonl).name,
            'original_trace_status': 'omitted',
            'certification': 'independent JSONL/frame/footer and SHA-256 verification, not original AI-service attestation',
        }
        manifest.setdefault('notes', []).append(
            'DERIVED EVIDENCE: original report, GT, events, session, config kept byte-for-byte; '
            'trace recovered and independently certified. No GT/event/score changes.')
        temporary_zip = Path(tmp) / 'recovered.zip'
        with ZipFile(temporary_zip, 'w') as archive:
            for name, data in payload.items():
                archive.writestr(name, data, compress_type=ZIP_DEFLATED)
            archive.write(compressed_path, arcname=trace_name, compress_type=ZIP_STORED)
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        with ZipFile(temporary_zip) as check:
            if check.testzip() is not None:
                raise RecoveryError('Result ZIP CRC failed')
        os.replace(temporary_zip, out)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Recover an omitted Traffic AI benchmark trace; never changes GT or AI scores')
    parser.add_argument('--export', type=Path, required=True)
    parser.add_argument('--camera-rar', type=Path)
    parser.add_argument('--trace-jsonl', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = recover(args.export, args.output, camera_rar=args.camera_rar, trace_jsonl=args.trace_jsonl)
    except (RecoveryError, BadZipFile, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f'[ERROR] Trace recovery stopped: {exc}', file=sys.stderr)
        return 2
    print(f"[OK] Recovered {result['frame_count']} frames from runtime {result['runtime_version']}; "
          f"compressed {result['source_bytes']} -> {result['compressed_bytes']} bytes")
    print(f'[OK] Saved derived evidence: {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
