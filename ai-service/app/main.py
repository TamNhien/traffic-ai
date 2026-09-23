from datetime import datetime, timezone
from pathlib import Path
import importlib.metadata
import os
import platform
import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.runtime import registry
from app.schemas import PipelineStart, SourceValidationRequest
from app.sources import inspect_source, list_video_sources, read_source_preview

APP_VERSION = '0.4.0'
app = FastAPI(title='Traffic AI Service', version=APP_VERSION)
SNAPSHOT_DIR = Path(os.getenv('SNAPSHOT_DIR', '/tmp/traffic-ai-snapshots'))
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
app.mount('/snapshots', StaticFiles(directory=SNAPSHOT_DIR), name='snapshots')


def _pkg_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


@app.get('/health')
def health() -> dict:
    gpu = {'available': False, 'name': None}
    torch_version = _pkg_version('torch')
    try:
        import torch
        gpu['available'] = bool(torch.cuda.is_available())
        if gpu['available']:
            gpu['name'] = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return {
        'status': 'ready',
        'service': 'ai-service',
        'version': APP_VERSION,
        'pipeline': 'yolo26s-bytetrack-realtime-gate-v4',
        'model': os.getenv('AI_MODEL_NAME', 'yolo26s.pt'),
        'device': os.getenv('AI_DEVICE', 'auto'),
        'performance': {
            'imgsz': int(os.getenv('AI_IMGSZ', '640')),
            'process_max_width': int(os.getenv('AI_PROCESS_MAX_WIDTH', '1440')),
            'stream_every_n': int(os.getenv('AI_STREAM_EVERY_N', '2')),
            'refine_at_crossing': os.getenv('AI_REFINE_AT_CROSSING', '1'),
            'refine_model': os.getenv('AI_REFINE_MODEL_NAME', 'yolo26m.pt'),
            'track_stitch_max_gap': int(os.getenv('AI_STITCH_MAX_GAP', '30')),
            'gate_roi': os.getenv('AI_GATE_ROI', '1'),
            'gate_roi_margin': float(os.getenv('AI_GATE_ROI_MARGIN', '0.22')),
            'async_event_writer': True,
            'async_stream_encoder': True,
        },
        'gpu': gpu,
        'active_pipelines': len([p for p in registry.list() if p['status'] in {'starting', 'warming', 'running'}]),
        'runtime': {
            'python': platform.python_version(),
            'fastapi': _pkg_version('fastapi'),
            'uvicorn': _pkg_version('uvicorn'),
            'ultralytics': _pkg_version('ultralytics'),
            'torch': torch_version,
            'opencv': _pkg_version('opencv-python-headless'),
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


@app.get('/sources/videos')
def video_sources() -> list[dict]:
    return list_video_sources()


@app.post('/sources/validate')
def validate_source(payload: SourceValidationRequest, probe: bool = Query(default=False)) -> dict:
    return inspect_source(payload.source_type, payload.source_url, probe=probe)


@app.post('/sources/preview')
def source_preview(payload: SourceValidationRequest) -> Response:
    try:
        jpeg = read_source_preview(payload.source_type, payload.source_url)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(content=jpeg, media_type='image/jpeg', headers={'Cache-Control': 'no-store'})


@app.get('/pipelines')
def pipelines() -> list[dict]:
    return registry.list()


@app.post('/pipelines/start', status_code=201)
def start_pipeline(payload: PipelineStart) -> dict:
    source_check = inspect_source(payload.source_type, payload.source_url, probe=payload.source_type == 'video')
    if not source_check.get('valid'):
        raise HTTPException(status_code=422, detail=source_check.get('message', 'Nguồn video/camera không hợp lệ.'))
    try:
        return registry.start(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get('/pipelines/{camera_id}')
def pipeline_status(camera_id: int) -> dict:
    try:
        return registry.get(camera_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail='Pipeline not found') from exc


@app.post('/pipelines/{camera_id}/stop')
def stop_pipeline(camera_id: int) -> dict:
    try:
        return registry.stop(camera_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail='Pipeline not found') from exc


def mjpeg_frames(camera_id: int):
    while True:
        jpeg = registry.latest_jpeg(camera_id)
        if jpeg is None:
            time.sleep(0.1)
            continue
        yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n'
        time.sleep(0.03)


@app.get('/streams/{camera_id}.mjpg')
def stream(camera_id: int):
    try:
        registry.get(camera_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail='Pipeline not found') from exc
    return StreamingResponse(mjpeg_frames(camera_id), media_type='multipart/x-mixed-replace; boundary=frame')
