from app.runtime import PipelineState
from app.worker import PipelineWorker


def test_custom_best_pt_uses_hybrid_role_detection_heuristic() -> None:
    assert PipelineWorker._looks_like_custom_model('/data/models/traffic-ai-v0513-run-3-best.pt') is True
    assert PipelineWorker._looks_like_custom_model('/data/models/best.pt') is True
    assert PipelineWorker._looks_like_custom_model('yolo26s.pt') is False
    assert PipelineWorker._looks_like_custom_model('yolo26m.pt') is False


def test_pipeline_state_exposes_untracked_and_detector_telemetry() -> None:
    state = PipelineState(camera_id=1, session_id=2)
    assert state.untracked_detections == 0
    assert state.detector_model_name is None
    assert state.hybrid_mode is False


def test_local_video_has_no_startup_grace_but_rtsp_keeps_guard(monkeypatch) -> None:
    from app.worker import startup_grace_frames_for_source

    monkeypatch.setenv("AI_VIDEO_STARTUP_GRACE_FRAMES", "0")
    monkeypatch.setenv("AI_GATE_STARTUP_GRACE_FRAMES", "12")
    assert startup_grace_frames_for_source("video") == 0
    assert startup_grace_frames_for_source("rtsp") == 12
