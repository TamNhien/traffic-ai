from types import SimpleNamespace

import numpy as np

from app.classification import RefineEvidenceAccumulator
from app.worker import PipelineWorker


def _worker() -> PipelineWorker:
    worker = PipelineWorker.__new__(PipelineWorker)
    worker._refiner_model = object()
    worker._general_refiner_model = object()
    worker._refine_ids = [1]
    worker._general_refine_ids = [1]
    worker._bicycle_context_last_observation = {}
    worker._bicycle_context_xframe_trail = {}
    worker._bicycle_context_xframe_last_consumed = {}
    worker._bicycle_xframe_audit_this_frame = []
    worker._bicycle_context_rescue_tracks = set()
    worker._class_refine_overrides = {}
    worker._refine_consensus = RefineEvidenceAccumulator()
    worker.state = SimpleNamespace(**{name: 0 for name in (
        "bicycle_context_checks", "bicycle_context_target_matches",
        "bicycle_context_rescues", "bicycle_context_weak_motor_rescues",
        "bicycle_context_competitive_rescues", "bicycle_context_near_margin_rescues",
        "bicycle_context_temporal_rescues", "bicycle_context_xframe_scans",
        "bicycle_context_xframe_rescues", "bicycle_context_xframe_audit_rejects",
        "bicycle_context_xframe_audit_accepts",
    )})
    for name, value in {
        "bicycle_context_rescue_enabled": True,
        "bicycle_context_dual_conf": .72,
        "bicycle_context_single_conf": .90,
        "bicycle_context_min_source_conf": .18,
        "bicycle_context_min_strong": .34,
        "bicycle_context_weak_motor_max_conf": .62,
        "bicycle_context_weak_motor_dual_conf": .58,
        "bicycle_context_weak_motor_min_strong": .24,
        "bicycle_context_competitive_max_motor_conf": .55,
        "bicycle_context_competitive_min_source_conf": .12,
        "bicycle_context_competitive_source_margin": .06,
        "bicycle_context_competitive_dual_conf": .34,
        "bicycle_context_competitive_fused_margin": .08,
        "bicycle_context_competitive_single_conf": .55,
        "bicycle_context_near_margin_max_motor_conf": .50,
        "bicycle_context_near_margin_min_source_conf": .10,
        "bicycle_context_near_margin_source_win": .02,
        "bicycle_context_near_margin_motor_veto": .08,
        "bicycle_context_near_margin_dual_conf": .28,
        "bicycle_context_near_margin_fused_margin": .02,
        "bicycle_context_xframe_enabled": True,
        "bicycle_context_xframe_history": 18,
        "bicycle_context_xframe_max_motor_conf": .52,
        "bicycle_context_xframe_min_source_conf": .08,
        "bicycle_context_xframe_min_frames": 2,
        "bicycle_context_xframe_min_sources": 2,
        "bicycle_context_xframe_source_win": .015,
        "bicycle_context_xframe_motor_veto": .10,
        "bicycle_context_xframe_min_strong": .14,
        "bicycle_context_xframe_dual_conf": .30,
        "bicycle_context_xframe_fused_margin": .015,
        "bicycle_context_temporal_min_hits": 2,
        "bicycle_context_temporal_conf": .50,
        "bicycle_context_temporal_strong": .26,
        "bicycle_context_temporal_combined": .72,
    }.items():
        setattr(worker, name, value)
    return worker


def test_v0552_preview_drawing_cannot_modify_analysis_pixels() -> None:
    worker = _worker()
    worker.process_max_width = 1440
    source = np.zeros((80, 100, 3), dtype=np.uint8)
    analysis, preview = worker._prepare_processing_frames(object(), source)

    # Simulate boxes/text painted before crossing-time context inference.
    preview[20:60, 25:75] = (0, 255, 255)

    assert not np.shares_memory(analysis, preview)
    assert np.count_nonzero(analysis) == 0
    assert np.count_nonzero(source) == 0
    assert np.count_nonzero(preview) > 0


def test_v0552_crossing_frame_contributes_second_context_source_before_audit() -> None:
    worker = _worker()
    worker._bicycle_context_xframe_trail[7] = [(100, "domain", .19, .01)]
    worker._context_two_wheel_from_model = lambda *_args: (
        (.16, .01) if _args[-1] is worker._general_refiner_model else None
    )

    decision = worker._refine_bicycle_context(7, 104, object(), object(), "cpu", False, .51)

    assert decision is not None and decision[0] == "bicycle"
    assert worker.state.bicycle_context_xframe_rescues == 1
    audit = worker._bicycle_xframe_audit_this_frame[-1]
    assert audit["reason"] == "accepted"
    assert audit["context_frames"] == [100, 104]
    assert audit["current_frame_sources"] == ["general"]
    assert 7 not in worker._bicycle_context_xframe_trail


def test_v0552_one_source_on_two_frames_cannot_replace_independent_sources() -> None:
    worker = _worker()
    worker._bicycle_context_xframe_trail[7] = [(100, "domain", .19, .01)]
    worker._context_two_wheel_from_model = lambda *_args: (
        (.16, .01) if _args[-1] is worker._refiner_model else None
    )

    assert worker._refine_bicycle_context(7, 104, object(), object(), "cpu", False, .51) is None
    assert worker._bicycle_xframe_audit_this_frame[-1]["reason"] == "insufficient_sources"


def test_v0552_two_sources_on_one_frame_cannot_replace_distinct_frames() -> None:
    worker = _worker()
    worker._context_two_wheel_from_model = lambda *_args: (
        (.19, .01) if _args[-1] is worker._refiner_model else (.16, .01)
    )

    assert worker._refine_bicycle_context(7, 104, object(), object(), "cpu", False, .51) is None
    assert worker._bicycle_xframe_audit_this_frame[-1]["reason"] == "insufficient_frames"


def test_v0552_cross_frame_source_motorcycle_veto_is_preserved() -> None:
    worker = _worker()
    worker._bicycle_context_xframe_trail[7] = [(100, "domain", .19, .50)]
    worker._context_two_wheel_from_model = lambda *_args: (
        (.16, .01) if _args[-1] is worker._general_refiner_model else None
    )

    assert worker._refine_bicycle_context(7, 104, object(), object(), "cpu", False, .51) is None
    assert worker._bicycle_xframe_audit_this_frame[-1]["reason"] == "motorcycle_source_veto"


def test_v0552_prescan_crossing_and_late_scan_share_one_observation() -> None:
    worker = _worker()
    calls = []

    def infer(*args):
        calls.append(args[-1])
        return (.19, .01) if args[-1] is worker._refiner_model else (.16, .01)

    worker._context_two_wheel_from_model = infer
    worker._scan_bicycle_xframe_context(7, 104, object(), object(), "cpu", False)
    assert len(worker._bicycle_context_xframe_trail[7]) == 2
    assert worker._refine_bicycle_context(7, 104, object(), object(), "cpu", False, .51) is None
    worker._scan_bicycle_xframe_context(7, 104, object(), object(), "cpu", False)

    assert len(calls) == 2
    assert worker.state.bicycle_context_xframe_scans == 1
    assert 7 not in worker._bicycle_context_xframe_trail


def test_v0552_immediate_context_rescue_also_consumes_old_passage_evidence() -> None:
    worker = _worker()
    worker._bicycle_context_xframe_trail[7] = [(100, "domain", .19, .01)]
    worker._context_two_wheel_from_model = lambda *_args: (.8, .01)

    decision = worker._refine_bicycle_context(7, 104, object(), object(), "cpu", False, .51)
    worker._scan_bicycle_xframe_context(7, 104, object(), object(), "cpu", False)

    assert decision is not None and decision[0] == "bicycle"
    assert 7 not in worker._bicycle_context_xframe_trail
    assert worker.state.bicycle_context_xframe_scans == 0


def test_v0552_context_collection_honors_configured_cross_frame_floor() -> None:
    worker = _worker()
    worker.bicycle_context_pad_x = 1.10
    worker.bicycle_context_pad_y = .85
    worker.refine_imgsz = 640

    class _Tensor:
        def __init__(self, values):
            self.values = values

        def cpu(self):
            return self

        def int(self):
            return self

        def tolist(self):
            return self.values

    class _Boxes:
        xyxy = _Tensor([[20, 20, 60, 80]])
        cls = _Tensor([0])
        conf = _Tensor([.09])

        def __len__(self):
            return 1

    model = SimpleNamespace(predict=lambda *_args, **_kwargs: [
        SimpleNamespace(boxes=_Boxes(), names={0: "bicycle"})
    ])
    frame = np.zeros((120, 100, 3), dtype=np.uint8)
    args = (frame, (20, 20, 60, 80), "cpu", False, [0], model)

    assert worker._context_two_wheel_from_model(*args) == (.09, 0.0)
    worker.bicycle_context_xframe_enabled = False
    assert worker._context_two_wheel_from_model(*args) == (0.0, 0.0)
