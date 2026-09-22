from datetime import datetime, timezone
from pathlib import Path
import os
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.runtime import registry
from app.schemas import PipelineStart

app = FastAPI(title="Traffic AI Service", version="0.2.7")
SNAPSHOT_DIR = Path(os.getenv("SNAPSHOT_DIR", "/tmp/traffic-ai-snapshots"))
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/snapshots", StaticFiles(directory=SNAPSHOT_DIR), name="snapshots")


@app.get("/health")
def health() -> dict:
    gpu = {"available": False, "name": None}
    try:
        import torch
        gpu["available"] = bool(torch.cuda.is_available())
        if gpu["available"]:
            gpu["name"] = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return {
        "status": "ready",
        "service": "ai-service",
        "pipeline": "yolo-bytetrack-line-crossing",
        "model": os.getenv("AI_MODEL_NAME", "yolo26n.pt"),
        "device": os.getenv("AI_DEVICE", "auto"),
        "gpu": gpu,
        "active_pipelines": len([p for p in registry.list() if p["status"] in {"starting", "running"}]),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/pipelines")
def pipelines() -> list[dict]:
    return registry.list()


@app.post("/pipelines/start", status_code=201)
def start_pipeline(payload: PipelineStart) -> dict:
    try:
        return registry.start(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/pipelines/{camera_id}")
def pipeline_status(camera_id: int) -> dict:
    try:
        return registry.get(camera_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Pipeline not found") from exc


@app.post("/pipelines/{camera_id}/stop")
def stop_pipeline(camera_id: int) -> dict:
    try:
        return registry.stop(camera_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Pipeline not found") from exc


def mjpeg_frames(camera_id: int):
    while True:
        jpeg = registry.latest_jpeg(camera_id)
        if jpeg is None:
            time.sleep(0.1)
            continue
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        time.sleep(0.03)


@app.get("/streams/{camera_id}.mjpg")
def stream(camera_id: int):
    try:
        registry.get(camera_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Pipeline not found") from exc
    return StreamingResponse(mjpeg_frames(camera_id), media_type="multipart/x-mixed-replace; boundary=frame")
