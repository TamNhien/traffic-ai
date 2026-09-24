from datetime import datetime, timezone
from pathlib import Path
import importlib.metadata
import os
import platform
import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.runtime import registry
from app.schemas import AnnotationBulkAcceptRequest, AnnotationSaveRequest, DatasetAutoLabelRequest, DatasetExtractRequest, DatasetPrepareRequest, DatasetPurgeRequest, PipelineStart, SourceValidationRequest, TrainingStartRequest
from app.sources import inspect_source, list_video_sources, read_source_preview, resolve_video_path
from app.training import auto_label, dataset_stats, extract_frames, prepare_dataset, purge_dataset, reset_dataset_labels, training_registry
from app.annotation import accept_safe_annotations, get_annotation, get_annotation_image, list_annotations, save_annotation

APP_VERSION = '0.5.14'
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
        'pipeline': 'yolo26s-bytetrack-full-detect-road-count-v5.14',
        'model': os.getenv('AI_MODEL_NAME', 'yolo26s.pt'),
        'device': os.getenv('AI_DEVICE', 'auto'),
        'performance': {
            'imgsz': int(os.getenv('AI_IMGSZ', '640')),
            'process_max_width': int(os.getenv('AI_PROCESS_MAX_WIDTH', '1440')),
            'stream_every_n': int(os.getenv('AI_STREAM_EVERY_N', '2')),
            'refine_at_crossing': os.getenv('AI_REFINE_AT_CROSSING', '1'),
            'refine_model': os.getenv('AI_REFINE_MODEL_NAME', 'yolo26m.pt'),
            'refine_background_warmup': os.getenv('AI_REFINE_BACKGROUND_WARMUP', '1'),
            'track_stitch_max_gap': int(os.getenv('AI_STITCH_MAX_GAP', '30')),
            'gate_roi': os.getenv('AI_GATE_ROI', '1'),
            'detection_roi': os.getenv('AI_DETECTION_ROI', 'full'),
            'road_roi_margin': float(os.getenv('AI_ROAD_ROI_MARGIN', '0.02')),
            'gate_roi_margin': float(os.getenv('AI_GATE_ROI_MARGIN', '0.16')),
            'gate_segment_margin': float(os.getenv('AI_GATE_SEGMENT_MARGIN', '0.0')),
            'gate_history_gap': int(os.getenv('AI_GATE_HISTORY_GAP', '45')),
            'async_event_writer': True,
            'async_stream_encoder': True,
            'native_video_playback': os.getenv('AI_NATIVE_VIDEO_PREVIEW', '1'),
            'video_pacing': os.getenv('AI_VIDEO_PACE', '1'),
            'mjpeg_new_frames_only': True,
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




@app.get('/media/video')
def local_video_media(source_url: str = Query(..., min_length=1)) -> FileResponse:
    """Serve a local MP4/video directly to the browser with HTTP Range support.

    The dashboard uses this path for smooth native playback. AI inference remains
    independent, so variable inference/JPEG latency no longer makes the clip
    appear to freeze or jump.
    """
    try:
        path = resolve_video_path(source_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail='Video not found')
    return FileResponse(
        path,
        media_type='video/mp4' if path.suffix.lower() in {'.mp4', '.m4v'} else None,
        headers={
            'Cache-Control': 'no-store',
            'Accept-Ranges': 'bytes',
            'X-Content-Type-Options': 'nosniff',
        },
    )


@app.post('/datasets/extract')
def dataset_extract(payload: DatasetExtractRequest) -> dict:
    try:
        source = resolve_video_path(payload.source_url)
        if not source.exists():
            raise ValueError(f"Không tìm thấy video: {payload.source_url}")
        return extract_frames(source, payload.slug, payload.every_n_frames, payload.max_images, payload.smart_dedupe, payload.min_change_ratio)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post('/datasets/autolabel')
def dataset_autolabel(payload: DatasetAutoLabelRequest) -> dict:
    try:
        return auto_label(payload.slug, payload.model_path, payload.confidence)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post('/datasets/prepare')
def dataset_prepare(payload: DatasetPrepareRequest) -> dict:
    try:
        return prepare_dataset(payload.slug, payload.train_ratio, payload.val_ratio, payload.seed)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get('/datasets/{slug}/stats')
def dataset_statistics(slug: str) -> dict:
    try:
        return dataset_stats(slug)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get('/datasets/{slug}/annotations')
def dataset_annotations(
    slug: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
    review_mode: str = Query(default='priority'),
) -> dict:
    try:
        return list_annotations(slug, offset=offset, limit=limit, review_mode=review_mode)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get('/datasets/{slug}/annotations/{image_name}')
def dataset_annotation(slug: str, image_name: str) -> dict:
    try:
        return get_annotation(slug, image_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail='Không tìm thấy ảnh annotation.') from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get('/datasets/{slug}/images/{image_name}')
def dataset_annotation_image(slug: str, image_name: str) -> FileResponse:
    try:
        path = get_annotation_image(slug, image_name)
        return FileResponse(path, headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail='Không tìm thấy ảnh annotation.') from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.put('/datasets/{slug}/annotations/{image_name}')
def dataset_annotation_save(slug: str, image_name: str, payload: AnnotationSaveRequest) -> dict:
    try:
        return save_annotation(slug, image_name, [box.model_dump() for box in payload.boxes], payload.reviewed, payload.difficult)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail='Không tìm thấy ảnh annotation.') from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post('/datasets/{slug}/annotations/accept-safe')
def dataset_annotations_accept_safe(slug: str, payload: AnnotationBulkAcceptRequest) -> dict:
    try:
        return accept_safe_annotations(slug, payload.min_confidence)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post('/datasets/{slug}/reset-labels')
def dataset_reset_labels(slug: str) -> dict:
    try:
        return reset_dataset_labels(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail='Không tìm thấy dataset.') from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post('/datasets/purge')
def dataset_purge(payload: DatasetPurgeRequest) -> dict:
    try:
        return purge_dataset(payload.slug, payload.run_ids, payload.purge_training_runs)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post('/training/start', status_code=201)
def training_start(payload: TrainingStartRequest) -> dict:
    try:
        return training_registry.start(
            run_id=payload.run_id, dataset_slug=payload.dataset_slug, base_model=payload.base_model,
            epochs=payload.epochs, imgsz=payload.imgsz, batch=payload.batch, device=payload.device,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get('/training')
def training_runs() -> list[dict]:
    return training_registry.list()


@app.get('/training/{run_id}')
def training_status(run_id: int) -> dict:
    try:
        return training_registry.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail='Training run not found') from exc


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
    # Yield only newly encoded frames. The old loop retransmitted the same JPEG
    # every 30 ms while inference was busy, wasting bandwidth/CPU and making the
    # browser's MJPEG timing more erratic.
    last_sequence = -1
    timeout = float(os.getenv('AI_MJPEG_WAIT_TIMEOUT', '2.0'))
    while True:
        sequence, jpeg = registry.wait_for_jpeg(camera_id, last_sequence, timeout=timeout)
        if jpeg is None:
            try:
                state = registry.get(camera_id)
            except KeyError:
                break
            if state.get('status') in {'completed', 'stopped', 'error'}:
                break
            continue
        last_sequence = sequence
        yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n'


@app.get('/streams/{camera_id}.mjpg')
def stream(camera_id: int):
    try:
        registry.get(camera_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail='Pipeline not found') from exc
    return StreamingResponse(
        mjpeg_frames(camera_id),
        media_type='multipart/x-mixed-replace; boundary=frame',
        headers={
            'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
            'Pragma': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )
