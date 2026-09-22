from datetime import datetime, timezone
from pathlib import Path
import importlib.metadata
import os
import platform
import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.runtime import registry
from app.schemas import PipelineStart, SourceValidationRequest
from app.sources import inspect_source, list_video_sources

APP_VERSION = '0.2.9'
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
        'pipeline': 'yolo-bytetrack-line-crossing',
        'model': os.getenv('AI_MODEL_NAME', 'yolo26n.pt'),
        'device': os.getenv('AI_DEVICE', 'auto'),
        'gpu': gpu,
        'active_pipelines': len([p for p in registry.list() if p['status'] in {'starting', 'running'}]),
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
