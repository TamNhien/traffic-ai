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
    worker._bicycle_context_xframe_last_scan = {}
    worker._bicycle_xframe_audit_this_frame = []
    worker._bicycle_context_rescue_tracks = set()
    worker._class_refine_overrides = {}
    worker._class_refine_consensus_proof = {}
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
        "bicycle_context_xframe_interval": 4,
        "bicycle_context_xframe_gate_distance_ratio": .070,
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


def _prescan_candidate(worker, track_id, anchor, *, track_on_road=True):
    return worker._bicycle_xframe_scan_candidate(
        track_id, 100, "motorcycle", .30, anchor,
        (100, 500), (900, 500), 1000, 1000, (anchor[0] - 10, anchor[1] - 10, anchor[0] + 10, anchor[1] + 10),
        track_on_road=track_on_road,
    )


def test_v0553_infinite_line_extension_cannot_starve_finite_gate_prescan() -> None:
    from app.classification import prioritize_bicycle_xframe_candidates

    worker = _worker()
    extension = _prescan_candidate(worker, 1, (1200, 500))
    crossing = _prescan_candidate(worker, 2, (500, 550))

    # The extension has zero signed distance to the infinite line, but it is
    # 300 px beyond the visible gate and would previously win the only slot.
    assert extension is None
    assert crossing is not None
    selected = prioritize_bicycle_xframe_candidates([crossing], 1)
    assert selected[0][2] == 2
    assert selected[0][0] == .05


def test_v0553_outside_road_candidate_cannot_consume_prescan_budget() -> None:
    worker = _worker()
    assert _prescan_candidate(worker, 1, (500, 500), track_on_road=False) is None
    assert _prescan_candidate(worker, 2, (500, 510)) is not None


def test_v0553_endpoint_prescan_keeps_configured_radius_and_budget() -> None:
    from app.classification import prioritize_bicycle_xframe_candidates

    worker = _worker()
    near = _prescan_candidate(worker, 1, (940, 530))
    far = _prescan_candidate(worker, 2, (960, 560))
    interior = _prescan_candidate(worker, 3, (500, 540))
    assert near is not None and near[0] == .05
    assert far is None
    assert prioritize_bicycle_xframe_candidates([near, interior], 1) == [interior]


def test_v0553_degenerate_gate_and_consumed_frame_are_ineligible_for_prescan() -> None:
    worker = _worker()
    assert worker._bicycle_xframe_scan_candidate(
        7, 100, "motorcycle", .30, (500, 500), (500, 500), (500, 500),
        1000, 1000, (490, 490, 510, 510), track_on_road=True,
    ) is None
    worker._bicycle_context_xframe_last_consumed[7] = 100
    assert _prescan_candidate(worker, 7, (500, 500)) is None


def test_v0553_delayed_context_call_cannot_regress_cache_or_erase_newer_trail() -> None:
    worker = _worker()
    calls = []
    worker._context_two_wheel_from_model = lambda *args: calls.append(args[-1]) or (.16, .01)
    assert worker._scan_bicycle_xframe_context(7, 104, object(), object(), "cpu", False) is True
    before = list(worker._bicycle_context_xframe_trail[7])

    assert worker._observe_bicycle_context(7, 100, object(), object(), "cpu", False) == []
    worker._record_bicycle_xframe_observations(7, 100, [("domain", .9, 0)])
    assert worker._scan_bicycle_xframe_context(7, 100, object(), object(), "cpu", False) is False
    assert worker._refine_bicycle_context(7, 100, object(), object(), "cpu", False, .3) is None

    assert worker._bicycle_context_xframe_trail[7] == before
    assert worker._bicycle_context_last_observation[7][0] == 104
    assert len(calls) == 2
    assert worker.state.bicycle_context_checks == 0


def test_v0553_duplicate_prescan_cannot_increment_evidence_or_scan_telemetry() -> None:
    worker = _worker()
    calls = []
    worker._context_two_wheel_from_model = lambda *args: calls.append(args[-1]) or (.16, .01)
    assert worker._scan_bicycle_xframe_context(7, 104, object(), object(), "cpu", False) is True
    assert worker._scan_bicycle_xframe_context(7, 104, object(), object(), "cpu", False) is False
    assert len(calls) == 2
    assert worker.state.bicycle_context_xframe_scans == 1
    assert len(worker._bicycle_context_xframe_trail[7]) == 2


def test_v0553_old_context_cannot_reseed_consumed_passage() -> None:
    worker = _worker()
    worker._bicycle_context_xframe_last_consumed[7] = 104
    worker._record_bicycle_xframe_observations(7, 100, [("domain", .9, 0)])
    worker._record_bicycle_xframe_observations(7, 104, [("general", .9, 0)])
    assert 7 not in worker._bicycle_context_xframe_trail
    assert worker._scan_bicycle_xframe_context(7, 100, object(), object(), "cpu", False) is False


def test_v0553_absolute_bicycle_rescue_cannot_bypass_target_motorcycle_veto() -> None:
    worker = _worker()
    worker._context_two_wheel_from_model = lambda *_args: (.80, .99)

    assert worker._refine_bicycle_context(7, 104, object(), object(), "cpu", False, .30) is None
    assert worker.state.bicycle_context_rescues == 0
    assert worker.state.bicycle_context_weak_motor_rescues == 0
    assert 7 not in worker._class_refine_overrides
    assert worker._bicycle_context_xframe_last_consumed[7] == 104
    assert 7 not in worker._bicycle_context_xframe_trail


def test_v0553_motor_only_source_vetoes_other_source_absolute_bicycle_vote() -> None:
    worker = _worker()
    worker._context_two_wheel_from_model = lambda *args: (
        (.95, .01) if args[-1] is worker._refiner_model else (0, .80)
    )

    assert worker._refine_bicycle_context(7, 104, object(), object(), "cpu", False, .30) is None
    assert worker.state.bicycle_context_rescues == 0
    assert worker._bicycle_context_last_observation[7][1][1] == ("general", 0, .80)


def test_v0553_delayed_class_refiner_cannot_replace_newer_source_observation() -> None:
    worker = _worker()
    worker._class_refine_last_observation = {7: (104, ("bicycle", .95))}

    assert worker._observe_class_refiner(
        7, 100, object(), object(), "motorcycle", "cpu", False, force=True,
    ) == (None, False)
    assert worker._class_refine_last_observation[7] == (104, ("bicycle", .95))


def test_v0553_cached_class_override_cannot_apply_to_older_source_frame() -> None:
    worker = _worker()
    worker._truck_semantic_lock = SimpleNamespace(resolve=lambda *_args: None)
    worker._class_refine_overrides[7] = ("bicycle", .95, 104)

    assert worker._class_override_for(7, 100, "motorcycle") is None
    assert worker._class_refine_overrides[7] == ("bicycle", .95, 104)


def test_v0553_delayed_class_refinement_cannot_replace_newer_override() -> None:
    worker = _worker()
    worker._class_refine_overrides[7] = ("bicycle", .95, 104)

    assert worker._remember_class_refinement(
        7, 100, "motorcycle", "motorcycle", .95, 10, "motorcycle", ("motorcycle", .99),
    ) is None
    assert worker._class_refine_overrides[7] == ("bicycle", .95, 104)


def test_v0553_budget_skipped_crossing_consumes_context_before_late_scan() -> None:
    worker = _worker()
    worker._bicycle_context_xframe_trail[7] = [(100, "domain", .19, .01)]
    calls = []
    worker._context_two_wheel_from_model = lambda *_args: calls.append(1) or (.16, .01)

    # Geometry accepted this track while another crossing spent the one-frame
    # context slot. A prescan queued before geometry must not reseed it later.
    worker._consume_bicycle_context_passage(7, 104)
    assert worker._scan_bicycle_xframe_context(7, 104, object(), object(), "cpu", False) is False

    assert 7 not in worker._bicycle_context_xframe_trail
    assert calls == []
    assert worker.state.bicycle_context_xframe_scans == 0


def test_v0553_return_crossing_requires_fresh_context_after_direct_bicycle_event() -> None:
    worker = _worker()
    worker._bicycle_context_xframe_trail[7] = [(100, "domain", .19, .01)]
    worker._consume_bicycle_context_passage(7, 104)
    worker._context_two_wheel_from_model = lambda *args: (
        (.16, .01) if args[-1] is worker._general_refiner_model else None
    )

    assert worker._refine_bicycle_context(7, 108, object(), object(), "cpu", False, .51) is None
    audit = worker._bicycle_xframe_audit_this_frame[-1]
    assert audit["context_frames"] == [108]
    assert audit["reason"] == "insufficient_frames"


def test_v0554_pre_gate_refinement_uses_finite_distance_for_extensions() -> None:
    worker = _worker()
    gate = ((100, 500), (900, 500), 1000, 1000)

    assert worker._finite_gate_distance_ratio((1200, 500), *gate) == .30
    assert worker._finite_gate_distance_ratio((500, 550), *gate) == .05
    assert worker._finite_gate_distance_ratio((940, 530), *gate) == .05
    assert worker._finite_gate_distance_ratio((500, 500), (500, 500), (500, 500), 1000, 1000) == float("inf")


def test_v0554_absolute_context_cannot_erase_recent_target_motorcycle_veto() -> None:
    worker = _worker()
    worker._bicycle_context_xframe_trail[7] = [(100, "domain", .19, .70)]
    worker._context_two_wheel_from_model = lambda *_args: (.80, .01)

    assert worker._refine_bicycle_context(7, 104, object(), object(), "cpu", False, .30) is None
    assert worker.state.bicycle_context_rescues == 0
    assert 7 not in worker._class_refine_overrides


def test_v0554_expired_target_motorcycle_vote_does_not_veto_fresh_absolute_context() -> None:
    worker = _worker()
    worker._bicycle_context_xframe_trail[7] = [(80, "domain", .19, .70)]
    worker._context_two_wheel_from_model = lambda *_args: (.80, .01)

    decision = worker._refine_bicycle_context(7, 104, object(), object(), "cpu", False, .30)
    assert decision is not None and decision[0] == "bicycle"
    assert worker.state.bicycle_context_rescues == 1


def test_v0554_losing_temporal_bicycle_votes_cannot_prove_context_rescue() -> None:
    worker = _worker()
    for frame in (100, 102):
        worker._refine_consensus.update(7, frame, "bicycle", .40, "domain")
        worker._refine_consensus.update(7, frame, "motorcycle", .80, "general")
    worker._context_two_wheel_from_model = lambda *args: (
        (.30, .01) if args[-1] is worker._general_refiner_model else None
    )

    assert worker._refine_bicycle_context(7, 104, object(), object(), "cpu", False, .30) is None
    assert worker.state.bicycle_context_temporal_rescues == 0
    assert worker.state.bicycle_context_competitive_rescues == 0


def test_v0554_crossing_frame_refiner_is_not_a_second_pre_crossing_temporal_hit() -> None:
    worker = _worker()
    worker._refine_consensus.update(7, 100, "bicycle", .40, "domain")
    worker._refine_consensus.update(7, 104, "bicycle", .40, "general")
    worker._context_two_wheel_from_model = lambda *args: (
        (.30, .01) if args[-1] is worker._general_refiner_model else None
    )

    assert worker._refine_bicycle_context(7, 104, object(), object(), "cpu", False, .30) is None
    assert worker.state.bicycle_context_temporal_rescues == 0


def test_v0554_context_proposal_waits_for_guard_before_rescue_commit() -> None:
    worker = _worker()
    worker._context_two_wheel_from_model = lambda *_args: (.80, .01)
    trace = {}

    decision = worker._refine_bicycle_context(
        7, 104, object(), object(), "cpu", False, .30, commit=False, decision_trace=trace,
    )

    assert decision is not None and decision[0] == "bicycle"
    assert trace["method"] == "absolute"
    assert worker.state.bicycle_context_rescues == 0
    assert worker._bicycle_context_rescue_tracks == set()
    assert 7 not in worker._class_refine_overrides
    assert worker._bicycle_context_xframe_last_consumed[7] == 104
    worker._commit_bicycle_context_rescue(7, 104, decision, trace["method"], remember_override=False)
    assert worker.state.bicycle_context_rescues == 1
    assert 7 not in worker._class_refine_overrides


def test_v0554_passage_consumes_semantic_votes_without_erasing_future_samples() -> None:
    worker = _worker()
    worker._refine_consensus.update(7, 100, "bicycle", .90, "domain")
    worker._refine_consensus.update(7, 104, "motorcycle", .80, "general")
    worker._refine_consensus.update(7, 108, "bicycle", .60, "general")

    worker._consume_bicycle_context_passage(7, 104)

    assert worker._refine_consensus.support(7, 104, "bicycle") == (0, 0.0, 0.0)
    assert worker._refine_consensus.support(7, 104, "motorcycle") == (0, 0.0, 0.0)
    assert worker._refine_consensus.support(7, 108, "bicycle") == (1, .60, .60)


def test_v0554_deferred_context_commit_keeps_newer_semantic_override() -> None:
    worker = _worker()
    worker._class_refine_overrides[7] = ("motorcycle", .99, 108)

    worker._commit_bicycle_context_rescue(7, 104, ("bicycle", .80), "absolute")

    assert worker.state.bicycle_context_rescues == 1
    assert worker._class_refine_overrides[7] == ("motorcycle", .99, 108)


def test_v0554_context_audit_exposes_proposal_scores_without_claiming_guard_commit() -> None:
    worker = _worker()
    worker._context_two_wheel_from_model = lambda *_args: (.80, .01)
    trace = {}

    decision = worker._refine_bicycle_context(
        7, 104, object(), (20, 20, 60, 80), "cpu", False, .52,
        commit=False, decision_trace=trace,
    )

    assert decision is not None
    record = trace["audit"]
    assert record["kind"] == "bicycle_context"
    assert record["branch"] == "absolute"
    assert record["decision_accepted"] is True
    assert record["commit_status"] == "proposed"
    assert record["primary_confidence"] == .52
    assert record["target_rect"] == [20.0, 20.0, 60.0, 80.0]
    assert record["temporal_hits"] == 0
    assert record["context_frames"] == [104]
    assert record["observations"] == [
        {"frame_index": 104, "source": "domain", "bicycle": .80, "motorcycle": .01},
        {"frame_index": 104, "source": "general", "bicycle": .80, "motorcycle": .01},
    ]
    assert len([row for row in worker._bicycle_xframe_audit_this_frame if row.get("kind") == "bicycle_context"]) == 1


def test_v0554_veto_context_audit_keeps_the_contradictory_source_frame() -> None:
    worker = _worker()
    worker._bicycle_context_xframe_trail[7] = [(100, "domain", .19, .70)]
    worker._context_two_wheel_from_model = lambda *_args: (.80, .01)
    trace = {}

    assert worker._refine_bicycle_context(
        7, 104, object(), object(), "cpu", False, .30, commit=False, decision_trace=trace,
    ) is None
    record = trace["audit"]
    assert record["decision_accepted"] is False
    assert record["commit_status"] == "not_applicable"
    assert record["reason"] == "motorcycle_source_veto"
    assert record["context_frames"] == [100, 104]
    assert record["observations"][0] == {
        "frame_index": 100, "source": "domain", "bicycle": .19, "motorcycle": .70,
    }


def _class_worker() -> PipelineWorker:
    from app.classification import TruckSemanticLock, VehicleClassPolicy

    worker = _worker()
    worker._class_policy = VehicleClassPolicy()
    worker._truck_semantic_lock = TruckSemanticLock()
    worker._truck_tracks_seen = set()
    worker._truck_class_rescue_tracks = set()
    worker._bicycle_class_rescue_tracks = set()
    worker._class_consensus_rescue_tracks = set()
    worker._class_refine_last_observation = {}
    worker._class_refine_last_check = {}
    worker.class_override_ttl_frames = 180
    worker.bicycle_override_ttl_frames = 60
    worker.heavy_override_ttl_frames = 240
    worker.refine_max_per_frame = 1
    worker.refine_at_crossing = True
    worker.refine_max_lag = .35
    worker.class_refine_gate_distance_ratio = .11
    worker.class_refine_interval = 10
    worker.class_refine_heavy_interval = 45
    worker.refine_consensus_min_hits = 2
    worker.bicycle_consensus_conf = .78
    worker.truck_consensus_conf = .52
    worker.bicycle_consensus_min_hits = 3
    worker.bicycle_consensus_margin = .18
    worker.bicycle_consensus_min_strong = .36
    worker.bicycle_consensus_min_sources = 2
    worker.bicycle_consensus_single_source_strong = .82
    worker.payload = SimpleNamespace(source_type="video")
    worker.state.playback_lag_seconds = 0.0
    for name in (
        "class_refine_checks", "domain_refine_checks", "general_refine_checks",
        "class_consensus_rescues", "truck_class_rescues", "bicycle_class_rescues",
        "truck_tracks_seen", "truck_semantic_locks",
    ):
        setattr(worker.state, name, 0)
    return worker


def _execute_frame_class_work(worker, tracks, *, initial_used=0, frame_index=100, label="motorcycle", source_path=None):
    """Execute the real production loop's class-work statements in track order.

    Only camera transport/inference is supplied by the fixture. This deliberately
    runs the production frame sections instead of reimplementing their budget
    algorithm; the V0.5.54 sections spend the first slot before a later crossing.
    """
    import ast
    from pathlib import Path
    import app.worker as worker_module

    source_path = Path(source_path or worker_module.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "PipelineWorker")
    run = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "run")
    track_loop = next(
        node for node in ast.walk(run) if isinstance(node, ast.For)
        and isinstance(node.target, ast.Name) and node.target.id == "item_index"
    )

    def assigned_names(node):
        return {
            item.id for target in getattr(node, "targets", ()) for item in ast.walk(target)
            if isinstance(item, ast.Name)
        }

    start = next(index for index, node in enumerate(track_loop.body) if "line_a" in assigned_names(node))
    end = next(index for index, node in enumerate(track_loop.body) if "locked_truck" in assigned_names(node))
    crossing = next(
        node for node in track_loop.body if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name) and node.test.id == "direction"
    )
    stop = next(index for index, node in enumerate(crossing.body) if "context_trace" in assigned_names(node))
    deferred = next((
        node for node in ast.walk(run) if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "_run_deferred_class_refinements"
    ), None)

    def compile_nodes(nodes):
        return compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(source_path), "exec")

    collect_code = compile_nodes(track_loop.body[start:end])
    crossing_code = compile_nodes(crossing.body[:stop])
    env = {
        "self": worker, "frame_index": frame_index, "width": 1000, "height": 1000,
        "analysis_frame": object(), "device": "cpu", "use_half": False,
        "counter": SimpleNamespace(road_zone=None, line=SimpleNamespace(denormalize=lambda *_: ((100, 500), (900, 500)))),
        "vehicle_family": __import__("app.classification", fromlist=["vehicle_family"]).vehicle_family,
        "AMBIGUOUS_CLASSES": {"bicycle", "motorcycle", "car", "bus", "truck"},
        "refines_used_this_frame": initial_used, "periodic_class_refine_candidates": [],
        "crossing_class_refine_track_ids": set(),
    }
    for tid, anchor, crossing_direction in tracks:
        env.update({
            "track_id": tid, "anchor": anchor, "rect": (anchor[0] - 10, anchor[1] - 10, anchor[0] + 10, anchor[1] + 10),
            "current_label": label, "stable_label": label, "display_label": label,
            "base_display_label": label, "class_certainty": .95, "class_hits": 10,
            "confidence_f": .30, "direction": crossing_direction,
            "gate_trace_track": {},
        })
        exec(collect_code, env)
        if crossing_direction:
            exec(crossing_code, env)
    if deferred is not None:
        exec(compile_nodes([deferred]), env)
    return env


def test_v0555_ordinary_track_before_crossing_cannot_spend_crossing_budget() -> None:
    worker = _class_worker()
    calls = []
    worker._observe_class_refiner = lambda track, *_args, **kwargs: (
        calls.append((track, kwargs["force"])) or (("motorcycle", .8), True)
    )

    env = _execute_frame_class_work(worker, [(1, (500, 550), None), (2, (500, 510), "IN")])

    assert calls == [(2, True)]
    assert env["refines_used_this_frame"] == 1


def test_v0555_periodic_queue_ranks_finite_gate_proximity_after_crossings() -> None:
    worker = _class_worker()
    calls = []
    worker._observe_class_refiner = lambda track, *_args, **kwargs: (
        calls.append((track, kwargs["force"])) or (("motorcycle", .8), True)
    )

    env = _execute_frame_class_work(worker, [(1, (500, 590), None), (2, (500, 510), None)])

    assert calls == [(2, False)]
    assert env["refines_used_this_frame"] == 1


def test_v0555_multiple_crossings_preserve_existing_total_refiner_budget() -> None:
    worker = _class_worker()
    calls = []
    worker._observe_class_refiner = lambda track, *_args, **kwargs: (
        calls.append((track, kwargs["force"])) or (("motorcycle", .8), True)
    )

    env = _execute_frame_class_work(worker, [(1, (500, 510), "IN"), (2, (500, 515), "OUT")])

    assert calls == [(1, True)]
    assert env["refines_used_this_frame"] == 1


def test_v0555_disabled_class_refinement_performs_no_periodic_or_crossing_inference() -> None:
    worker = _class_worker()
    worker.refine_at_crossing = False
    calls = []
    worker._observe_class_refiner = lambda *_args, **_kwargs: calls.append(1) or (None, True)

    env = _execute_frame_class_work(worker, [(1, (500, 550), None), (2, (500, 510), "IN")])

    assert calls == []
    assert env["refines_used_this_frame"] == 0


def test_v0555_cache_fallback_crossing_keeps_original_override_expiry() -> None:
    worker = _class_worker()
    worker._class_refine_overrides[7] = ("bicycle", .95, 50)

    env = _execute_frame_class_work(worker, [(7, (500, 510), "IN")], initial_used=1)

    assert env["event_label"] == "bicycle"
    assert worker._class_refine_overrides[7] == ("bicycle", .95, 50)
    assert worker._class_override_for(7, 111, "motorcycle") is None
    assert worker.state.bicycle_class_rescues == 0


def test_v0555_fresh_crossing_refiner_can_establish_new_override_clock() -> None:
    worker = _class_worker()
    worker._class_refine_overrides[7] = ("bicycle", .91, 50)
    worker._observe_class_refiner = lambda *_args, **_kwargs: (("bicycle", .96), True)

    env = _execute_frame_class_work(worker, [(7, (500, 510), "IN")])

    assert env["event_label"] == "bicycle"
    assert worker._class_refine_overrides[7] == ("bicycle", .96, 100)
    assert worker._class_override_for(7, 111, "motorcycle") == ("bicycle", .96)


def test_v0555_stronger_car_refiner_blocks_single_frame_truck_preference() -> None:
    worker = _class_worker()
    assert worker._prefer_refinement_candidate("car", [("truck", .60), ("car", .90)]) == ("car", .90)
    assert worker._prefer_refinement_candidate("car", [("bus", .60), ("car", .90)]) == ("car", .90)


def test_v0555_tied_four_wheel_opinions_cannot_force_minority_preference() -> None:
    worker = _class_worker()
    assert worker._prefer_refinement_candidate("car", [("car", .60), ("truck", .60)]) == ("car", .60)
    assert worker._prefer_refinement_candidate("car", [("truck", .60), ("car", .60)]) == ("car", .60)
    assert worker._prefer_refinement_candidate("car", [("truck", .60), ("bus", .60)]) is None


def test_v0555_winning_truck_refiner_keeps_existing_promotion_threshold() -> None:
    worker = _class_worker()
    assert worker._prefer_refinement_candidate("car", [("car", .40), ("truck", .48)]) == ("truck", .48)


def test_v0555_losing_truck_frames_cannot_create_worker_semantic_lock() -> None:
    worker = _class_worker()
    for frame in (90, 95):
        worker._refine_consensus.update(7, frame, "truck", .60, "domain")
        worker._refine_consensus.update(7, frame, "car", .90, "general")

    assert worker._refresh_truck_semantic_lock(7, 100, "car", .95, 10) is None
    assert worker._truck_semantic_lock.resolve(7, 100, "car") is None
    assert worker._truck_tracks_seen == set()


def test_v0555_winning_truck_frames_can_create_worker_semantic_lock() -> None:
    worker = _class_worker()
    for frame in (90, 95):
        worker._refine_consensus.update(7, frame, "truck", .60, "domain")
        worker._refine_consensus.update(7, frame, "car", .20, "general")

    lock = worker._refresh_truck_semantic_lock(7, 100, "car", .95, 10)
    assert lock is not None and lock[0] == "truck"
    assert worker._truck_tracks_seen == {7}


def _seed_weak_truck_consensus(worker):
    worker._refine_consensus.update(7, 90, "truck", .31, "domain")
    worker._refine_consensus.update(7, 95, "truck", .35, "general")
    worker._class_refine_overrides[7] = ("truck", .55, 50)


def test_v0555_no_opinion_refiner_cannot_restart_old_consensus_override_lifetime() -> None:
    worker = _class_worker()
    _seed_weak_truck_consensus(worker)
    calls = []
    worker._refine_crossing_label = lambda *_args, **_kwargs: calls.append(1) or None

    refined, inferred = worker._observe_class_refiner(
        7, 100, object(), object(), "car", "cpu", False, force=True,
    )
    remembered = worker._remember_class_refinement(
        7, 100, "car", "car", .95, 10, "car", refined,
    )

    assert inferred is True and len(calls) == 2
    assert remembered == ("truck", .55)
    assert worker._class_refine_overrides[7] == ("truck", .55, 50)
    assert refined is None
    assert worker._class_refine_last_observation[7] == (100, None)
    assert worker.state.class_consensus_rescues == 0
    assert worker.state.class_refine_checks == 1
    assert worker._class_override_for(7, 291, "car") is None
    # A same-frame retry reuses the no-opinion result without a new budget cost.
    assert worker._observe_class_refiner(7, 100, object(), object(), "car", "cpu", False, force=True) == (None, False)
    assert len(calls) == 2


def test_v0555_nonfinite_zero_or_wrong_family_refiner_opinions_are_not_fresh_evidence() -> None:
    for opinion in (("truck", 0.0), ("truck", float("nan")), ("truck", float("inf")), ("bicycle", .95)):
        worker = _class_worker()
        _seed_weak_truck_consensus(worker)
        worker._refine_crossing_label = lambda *_args, **_kwargs: opinion

        refined, inferred = worker._observe_class_refiner(
            7, 100, object(), object(), "car", "cpu", False, force=True,
        )

        assert (refined, inferred) == (None, True)
        assert worker._class_refine_last_observation[7] == (100, None)
        assert worker.state.class_consensus_rescues == 0
        assert worker._refine_consensus.support(7, 100, "bicycle") == (0, 0.0, 0.0)


def test_v0555_fresh_target_opinion_can_complete_existing_weak_truck_consensus() -> None:
    worker = _class_worker()
    _seed_weak_truck_consensus(worker)
    worker._refine_crossing_label = lambda *_args, **kwargs: (
        ("truck", .12) if kwargs["model"] is worker._refiner_model else None
    )

    refined, inferred = worker._observe_class_refiner(
        7, 100, object(), object(), "car", "cpu", False, force=True,
    )
    remembered = worker._remember_class_refinement(
        7, 100, "car", "car", .95, 10, "car", refined,
    )

    assert inferred is True and refined is not None and refined[0] == "truck"
    assert remembered is not None and remembered[0] == "truck"
    assert worker._class_refine_overrides[7][2] == 100
    assert worker.state.class_consensus_rescues == 1
    assert worker._class_override_for(7, 291, "car") is not None


def _v0557_consensus_worker():
    worker = _class_worker()
    # Use the configured production policy, including the unchanged .90
    # threshold for an ordinary single-frame bicycle opinion.
    worker._class_policy.bicycle_refine_override_conf = .90
    worker.bicycle_consensus_min_hits = 4
    worker.bicycle_consensus_margin = .16
    worker.bicycle_consensus_min_strong = .45
    worker.bicycle_consensus_min_sources = 2
    worker.bicycle_consensus_single_source_strong = .88
    for frame, source in ((100, "domain"), (110, "general"), (120, "domain")):
        worker._refine_consensus.update(7, frame, "bicycle", .35, source)
    worker._refine_crossing_label = lambda *_args, **kwargs: (
        ("bicycle", .50) if kwargs["model"] is worker._general_refiner_model else None
    )
    return worker


def test_v0557_accepted_temporal_bicycle_consensus_reaches_crossing_below_single_frame_threshold() -> None:
    worker = _v0557_consensus_worker()
    refined, inferred = worker._observe_class_refiner(
        7, 130, object(), object(), "motorcycle", "cpu", False, force=True,
    )
    assert inferred and refined is not None and refined[0] == "bicycle"
    assert .78 <= refined[1] < .90
    result = worker._resolve_crossing_class_refinement(
        7, 130, "motorcycle", "motorcycle", .99, 20, "motorcycle", refined,
    )
    assert result[0] == "bicycle"
    assert worker._class_refine_overrides[7] == ("bicycle", refined[1], 130)
    assert worker.state.class_consensus_rescues == 1
    assert worker.state.bicycle_class_rescues == 1
    # Reading the completed correction preserves its original bounded lifetime.
    assert worker._class_override_for(7, 190, "motorcycle")[0] == "bicycle"
    assert worker._class_override_for(7, 191, "motorcycle") is None


def test_v0557_one_shot_bicycle_score_cannot_borrow_consensus_policy() -> None:
    worker = _v0557_consensus_worker()
    result = worker._resolve_crossing_class_refinement(
        7, 130, "motorcycle", "motorcycle", .99, 20, "motorcycle", ("bicycle", .83),
    )
    assert result[0] == "motorcycle"
    assert worker.state.bicycle_class_rescues == 0


def test_v0557_same_frame_consensus_retry_reuses_its_proof_without_inference_or_rescue_duplication() -> None:
    worker = _v0557_consensus_worker()
    original, inferred = worker._observe_class_refiner(
        7, 130, object(), object(), "motorcycle", "cpu", False, force=True,
    )
    assert inferred
    worker._refine_crossing_label = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("retry inferred"))
    retry, inferred = worker._observe_class_refiner(
        7, 130, object(), object(), "motorcycle", "cpu", False, force=True,
    )
    assert retry == original and not inferred
    assert worker._resolve_crossing_class_refinement(
        7, 130, "motorcycle", "motorcycle", .99, 20, "motorcycle", retry,
    )[0] == "bicycle"
    assert worker.state.class_refine_checks == 1
    assert worker.state.class_consensus_rescues == 1
    assert worker.state.bicycle_class_rescues == 1


def test_v0557_consensus_proof_cannot_escape_its_track_frame_or_score() -> None:
    for tid, frame, confidence in ((8, 130, None), (7, 131, None), (7, 130, .84)):
        worker = _v0557_consensus_worker()
        refined, _inferred = worker._observe_class_refiner(
            7, 130, object(), object(), "motorcycle", "cpu", False, force=True,
        )
        assert refined is not None
        opinion = refined if confidence is None else ("bicycle", confidence)
        result = worker._resolve_crossing_class_refinement(
            tid, frame, "motorcycle", "motorcycle", .99, 20, "motorcycle", opinion,
        )
        assert result[0] == "motorcycle"
        assert worker.state.bicycle_class_rescues == 0


def test_v0557_insufficient_winning_source_diversity_cannot_make_consensus_proof() -> None:
    worker = _v0557_consensus_worker()
    worker._refine_consensus = RefineEvidenceAccumulator()
    for frame in (100, 110, 120):
        worker._refine_consensus.update(7, frame, "bicycle", .35, "general")
    refined, _inferred = worker._observe_class_refiner(
        7, 130, object(), object(), "motorcycle", "cpu", False, force=True,
    )
    assert worker._resolve_crossing_class_refinement(
        7, 130, "motorcycle", "motorcycle", .99, 20, "motorcycle", refined,
    )[0] == "motorcycle"
    assert worker._class_refine_consensus_proof == {}
    assert worker.state.class_consensus_rescues == 0


def test_v0557_refiner_history_reads_cannot_extend_truck_lock_source_deadline() -> None:
    worker = _class_worker()
    for frame in (90, 95):
        worker._refine_consensus.update(7, frame, "truck", .99, "domain")
    assert worker._refresh_truck_semantic_lock(7, 100, "car", .99, 20)[0] == "truck"
    for frame in range(101, 211):
        assert worker._refresh_truck_semantic_lock(7, frame, "car", .99, 20)[0] == "truck"
    # No new truck opinion followed source frame95; TTL remains450 frames.
    assert worker._truck_semantic_lock.resolve(7, 545, "car")[0] == "truck"
    assert worker._truck_semantic_lock.resolve(7, 546, "car") is None


def test_v0557_new_winning_truck_opinion_can_refresh_refiner_source_deadline() -> None:
    worker = _class_worker()
    for frame in (90, 95):
        worker._refine_consensus.update(7, frame, "truck", .99, "domain")
    worker._refresh_truck_semantic_lock(7, 100, "car", .99, 20)
    worker._refine_consensus.update(7, 200, "truck", .80, "general")
    assert worker._refresh_truck_semantic_lock(7, 200, "car", .99, 20)[0] == "truck"
    assert worker._truck_semantic_lock.resolve(7, 650, "car")[0] == "truck"
    assert worker._truck_semantic_lock.resolve(7, 651, "car") is None


def test_v0557_qualified_primary_truck_refresh_keeps_current_detector_clock() -> None:
    worker = _class_worker()
    for frame in (90, 95):
        worker._refine_consensus.update(7, frame, "truck", .99, "domain")
    worker._refresh_truck_semantic_lock(7, 100, "car", .99, 20)
    assert worker._refresh_truck_semantic_lock(7, 210, "truck", .90, 6)[0] == "truck"
    assert worker._truck_semantic_lock.resolve(7, 660, "car")[0] == "truck"
    assert worker._truck_semantic_lock.resolve(7, 661, "car") is None


def test_v0559_worker_smoothing_does_not_renew_primary_truck_from_car_observations() -> None:
    from app.classification import TrackLabelSmoother, TruckSemanticLock

    worker = _class_worker()
    worker._labels = TrackLabelSmoother(history=24)
    worker._truck_semantic_lock = TruckSemanticLock(ttl_frames=30)
    for frame in range(77, 126):
        current_label = "truck" if frame <= 100 else "car"
        worker._labels.update(7, current_label, .90 if current_label == "truck" else .10, frame_index=frame)
        stable_label, certainty, hits = worker._labels.stable_label(7, current_label)
        worker._refresh_truck_semantic_lock(7, frame, stable_label, certainty, hits)
    assert worker._truck_semantic_lock.resolve(7, 130, "car")
    assert worker._truck_semantic_lock.resolve(7, 131, "car") is None


def test_v0559_worker_merged_primary_history_keeps_actual_truck_clock() -> None:
    from app.classification import TrackLabelSmoother, TruckSemanticLock

    worker = _class_worker()
    worker._labels = TrackLabelSmoother(history=24)
    worker._truck_semantic_lock = TruckSemanticLock(ttl_frames=30)
    for frame in (90, 95, 100):
        worker._labels.update(7, "truck", .90, frame_index=frame)
    worker._labels.update(8, "car", .10, frame_index=110)
    worker._labels.merge_track(7, 8)
    stable_label, certainty, hits = worker._labels.stable_label(8, "car")
    assert worker._refresh_truck_semantic_lock(8, 110, stable_label, certainty, hits)
    assert worker._truck_semantic_lock.resolve(8, 130, "car")
    assert worker._truck_semantic_lock.resolve(8, 131, "car") is None


def test_v0559_worker_new_refiner_source_outlives_retained_primary_source() -> None:
    from app.classification import TrackLabelSmoother, TruckSemanticLock

    worker = _class_worker()
    worker._labels = TrackLabelSmoother(history=24)
    worker._truck_semantic_lock = TruckSemanticLock(ttl_frames=30)
    for frame in (90, 95, 100):
        worker._labels.update(7, "truck", .90, frame_index=frame)
    worker._labels.update(7, "car", .10, frame_index=120)
    for frame in (105, 110):
        worker._refine_consensus.update(7, frame, "truck", .80, "domain")
    stable_label, certainty, hits = worker._labels.stable_label(7, "car")
    assert worker._refresh_truck_semantic_lock(7, 120, stable_label, certainty, hits)
    assert worker._truck_semantic_lock.resolve(7, 140, "car")
    assert worker._truck_semantic_lock.resolve(7, 141, "car") is None


def test_v0559_worker_future_primary_pixels_do_not_inflate_valid_refiner_lock() -> None:
    from app.classification import TrackLabelSmoother, TruckSemanticLock

    worker = _class_worker()
    worker._labels = TrackLabelSmoother(history=24)
    worker._truck_semantic_lock = TruckSemanticLock(ttl_frames=30)
    for frame in (121, 122, 123):
        worker._labels.update(7, "truck", .90, frame_index=frame)
    for frame in (105, 110):
        worker._refine_consensus.update(7, frame, "truck", .80, "domain")
    stable_label, certainty, hits = worker._labels.stable_label(7, "car")
    result = worker._refresh_truck_semantic_lock(7, 120, stable_label, certainty, hits)
    assert result is not None and result[0] == "truck" and result[1] < 1.0
    assert worker._truck_semantic_lock.resolve(7, 140, "car")
    assert worker._truck_semantic_lock.resolve(7, 141, "car") is None


def test_v0557_canonical_merge_carries_only_newest_consensus_proof() -> None:
    worker = _class_worker()
    worker._class_refine_consensus_proof = {7: (130, ("truck", .83)), 8: (125, ("bus", .81))}
    worker._labels = SimpleNamespace(merge_track=lambda *_args: None)
    for name in (
        "_seen_track_ids", "_truck_crossing_tracks", "_bicycle_tracks_seen",
        "_heavy_anchor_tracks", "_heavy_center_rescue_tracks",
    ):
        setattr(worker, name, set())
    worker._merge_canonical_track_state(7, 8, SimpleNamespace(merge_track=lambda *_args: None), None)
    assert 7 not in worker._class_refine_consensus_proof
    assert worker._class_refine_consensus_proof[8] == (130, ("truck", .83))


def test_v0557_consensus_proof_preserves_existing_truck_semantic_protection() -> None:
    worker = _class_worker()
    worker._truck_semantic_lock.observe(7, 120, stable_label="truck", certainty=.90, hits=6)
    worker._class_refine_consensus_proof[7] = (130, ("bus", .63))
    result = worker._remember_class_refinement(
        7, 130, "car", "car", .99, 20, "car", ("bus", .63),
    )
    assert result == ("truck", .90)
    # The eligible lock still protects the decision, while the cache retains
    # the actual underlying consensus rather than copying the lock's label.
    assert worker._class_refine_overrides[7] == ("bus", .63, 130)


def test_v0557_consensus_proof_cannot_cross_vehicle_family() -> None:
    worker = _class_worker()
    worker._class_refine_consensus_proof[7] = (130, ("bicycle", .83))
    assert worker._remember_class_refinement(
        7, 130, "car", "car", .99, 20, "car", ("bicycle", .83),
    ) is None
    assert worker._class_refine_overrides == {}


def _v0558_historical_bicycle_worker(confidence=.99):
    worker = _v0557_consensus_worker()
    worker._refine_consensus = RefineEvidenceAccumulator()
    worker._class_refine_consensus_source_frame = {}
    for frame, source in ((100, "domain"), (110, "general"), (120, "domain"), (130, "general")):
        worker._refine_consensus.update(7, frame, "bicycle", confidence, source)
    worker._refine_crossing_label = lambda *_args, **_kwargs: ("motorcycle", .10)
    return worker


def test_v0558_expired_bicycle_consensus_cannot_restart_override_or_rescue() -> None:
    worker = _v0558_historical_bicycle_worker()
    worker._class_refine_overrides[7] = ("bicycle", .99, 130)
    refined, inferred = worker._observe_class_refiner(
        7, 200, object(), object(), "motorcycle", "cpu", False, force=True,
    )
    assert inferred and refined is None
    assert worker._class_refine_overrides[7] == ("bicycle", .99, 130)
    assert worker._class_refine_consensus_proof == {}
    assert worker.state.class_consensus_rescues == 0
    assert worker._resolve_crossing_class_refinement(
        7, 200, "motorcycle", "motorcycle", .99, 20, "motorcycle", refined,
    )[0] == "motorcycle"
    assert worker.state.bicycle_class_rescues == 0


def test_v0558_eligible_historical_consensus_keeps_last_winning_source_deadline() -> None:
    worker = _v0558_historical_bicycle_worker(.50)
    refined, inferred = worker._observe_class_refiner(
        7, 140, object(), object(), "motorcycle", "cpu", False, force=True,
    )
    assert inferred and refined is not None and refined[0] == "bicycle"
    assert .78 <= refined[1] < .90
    assert worker._resolve_crossing_class_refinement(
        7, 140, "motorcycle", "motorcycle", .99, 20, "motorcycle", refined,
    )[0] == "bicycle"
    assert worker._class_refine_overrides[7][2] == 130
    assert worker._class_override_for(7, 190, "motorcycle")[0] == "bicycle"
    assert worker._class_override_for(7, 191, "motorcycle") is None


def test_v0558_current_losing_bicycle_opinion_cannot_renew_consensus_clock() -> None:
    worker = _v0558_historical_bicycle_worker()
    worker._refine_crossing_label = lambda *_args, **kwargs: (
        ("bicycle", .30) if kwargs["model"] is worker._refiner_model else ("motorcycle", .40)
    )
    refined, _inferred = worker._observe_class_refiner(
        7, 140, object(), object(), "motorcycle", "cpu", False, force=True,
    )
    assert refined is not None and refined[0] == "bicycle"
    worker._remember_class_refinement(7, 140, "motorcycle", "motorcycle", .99, 20, "motorcycle", refined)
    assert worker._class_refine_overrides[7][2] == 130


def test_v0558_new_winning_bicycle_opinion_can_renew_expired_history() -> None:
    worker = _v0558_historical_bicycle_worker()
    worker._refine_crossing_label = lambda *_args, **kwargs: (
        ("bicycle", .99) if kwargs["model"] is worker._refiner_model else ("motorcycle", .10)
    )
    refined, inferred = worker._observe_class_refiner(
        7, 200, object(), object(), "motorcycle", "cpu", False, force=True,
    )
    assert inferred and refined is not None and refined[0] == "bicycle"
    assert worker._resolve_crossing_class_refinement(
        7, 200, "motorcycle", "motorcycle", .99, 20, "motorcycle", refined,
    )[0] == "bicycle"
    assert worker._class_refine_overrides[7][2] == 200
    assert worker._class_override_for(7, 260, "motorcycle")[0] == "bicycle"
    assert worker._class_override_for(7, 261, "motorcycle") is None


def test_v0558_expired_truck_consensus_obeys_configured_override_lifetime() -> None:
    worker = _class_worker()
    worker.heavy_override_ttl_frames = 30
    for frame, source in ((90, "domain"), (95, "general")):
        worker._refine_consensus.update(7, frame, "truck", .50, source)
    worker._refine_crossing_label = lambda *_args, **_kwargs: ("car", .10)
    refined, inferred = worker._observe_class_refiner(
        7, 140, object(), object(), "car", "cpu", False, force=True,
    )
    assert inferred and refined is None
    assert worker._resolve_crossing_class_refinement(
        7, 140, "car", "car", .99, 20, "car", refined,
    )[0] == "car"
    assert worker.state.class_consensus_rescues == 0
    assert worker._class_refine_overrides == {}


def test_v0558_expired_certificate_cannot_fall_through_as_high_one_shot_score() -> None:
    worker = _class_worker()
    worker._class_refine_consensus_proof[7] = (200, ("bicycle", .95))
    worker._class_refine_consensus_source_frame = {7: (200, 130)}
    assert worker._resolve_crossing_class_refinement(
        7, 200, "motorcycle", "motorcycle", .99, 20, "motorcycle", ("bicycle", .95),
    )[0] == "motorcycle"
    assert worker._class_refine_overrides == {}
    assert worker.state.bicycle_class_rescues == 0


def test_v0558_ordinary_high_one_shot_refinement_keeps_current_source_clock() -> None:
    worker = _class_worker()
    assert worker._resolve_crossing_class_refinement(
        7, 200, "motorcycle", "motorcycle", .99, 20, "motorcycle", ("bicycle", .95),
    )[0] == "bicycle"
    assert worker._class_refine_overrides[7] == ("bicycle", .99, 200)


def test_v0558_older_consensus_source_cannot_replace_newer_class_override() -> None:
    worker = _class_worker()
    worker._class_refine_overrides[7] = ("motorcycle", .99, 150)
    worker._class_refine_consensus_proof[7] = (160, ("bicycle", .95))
    worker._class_refine_consensus_source_frame = {7: (160, 130)}
    assert worker._remember_class_refinement(
        7, 160, "motorcycle", "motorcycle", .99, 20, "motorcycle", ("bicycle", .95),
    ) == ("motorcycle", .99)
    assert worker._class_refine_overrides[7] == ("motorcycle", .99, 150)


def test_v0558_canonical_merge_carries_consensus_source_clock_with_decision_proof() -> None:
    worker = _class_worker()
    worker._class_refine_consensus_proof = {7: (150, ("truck", .83)), 8: (140, ("bus", .81))}
    worker._class_refine_consensus_source_frame = {7: (150, 130), 8: (140, 135)}
    worker._labels = SimpleNamespace(merge_track=lambda *_args: None)
    for name in (
        "_seen_track_ids", "_truck_crossing_tracks", "_bicycle_tracks_seen",
        "_heavy_anchor_tracks", "_heavy_center_rescue_tracks",
    ):
        setattr(worker, name, set())
    worker._merge_canonical_track_state(7, 8, SimpleNamespace(merge_track=lambda *_args: None), None)
    assert worker._class_refine_consensus_proof[8] == (150, ("truck", .83))
    assert worker._class_refine_consensus_source_frame == {8: (150, 130)}


def test_v0558_future_consensus_source_cannot_create_current_correction() -> None:
    worker = _class_worker()
    worker._class_refine_consensus_proof[7] = (200, ("bicycle", .95))
    worker._class_refine_consensus_source_frame = {7: (200, 201)}
    assert worker._resolve_crossing_class_refinement(
        7, 200, "motorcycle", "motorcycle", .99, 20, "motorcycle", ("bicycle", .95),
    )[0] == "motorcycle"
    assert worker._class_refine_overrides == {}


def test_v0559_class_audit_records_actual_target_and_independent_model_opinions_once() -> None:
    worker = _class_worker()
    calls = []
    def infer(*_args, **kwargs):
        calls.append(kwargs["model"])
        return ("truck", .40) if kwargs["model"] is worker._refiner_model else ("car", .90)
    worker._refine_crossing_label = infer
    rect = (10.0, 20.0, 30.0, 40.0)
    result = worker._observe_class_refiner(7, 100, object(), rect, "car", "cpu", False, force=True)
    assert result == (("car", .90), True)
    audit = worker._class_refine_decision_audit_this_frame
    assert len(audit) == 1 and len(calls) == 2
    assert audit[0]["track_id"] == 7 and audit[0]["frame_index"] == 100
    assert audit[0]["target_label"] == "car" and audit[0]["target_rect"] == list(rect)
    assert audit[0]["attempted_sources"] == ["domain", "general"]
    assert audit[0]["opinions"] == {
        "domain": {"label": "truck", "confidence": .40, "source_frame_index": 100},
        "general": {"label": "car", "confidence": .90, "source_frame_index": 100},
    }
    assert audit[0]["refined"] == {"label": "car", "confidence": .90}
    assert audit[0]["winning_source_frame_index"] == 100
    assert not audit[0]["consensus"] and audit[0]["ttl_eligible"]
    checks = (worker.state.class_refine_checks, worker.state.domain_refine_checks, worker.state.general_refine_checks)
    assert worker._observe_class_refiner(7, 100, object(), rect, "car", "cpu", False, force=True) == (("car", .90), False)
    assert worker._observe_class_refiner(7, 99, object(), rect, "car", "cpu", False, force=True) == (None, False)
    assert len(audit) == 1 and len(calls) == 2
    assert checks == (worker.state.class_refine_checks, worker.state.domain_refine_checks, worker.state.general_refine_checks)


def test_v0559_class_audit_no_target_opinion_does_not_read_or_renew_old_consensus() -> None:
    worker = _v0558_historical_bicycle_worker()
    worker._class_refine_overrides[7] = ("bicycle", .99, 130)
    worker._refine_crossing_label = lambda *_args, **_kwargs: None
    refined, inferred = worker._observe_class_refiner(7, 160, object(), object(), "motorcycle", "cpu", False, force=True)
    assert inferred and refined is None
    audit = worker._class_refine_decision_audit_this_frame[0]
    assert audit["opinions"] == {"domain": None, "general": None}
    assert audit["refined"] is None and audit["winning_source_frame_index"] is None
    assert not audit["consensus"] and not audit["ttl_eligible"]
    assert worker._class_refine_overrides[7][2] == 130
    assert worker.state.class_consensus_rescues == 0


def test_v0559_class_audit_keeps_expired_consensus_source_clock_without_returning_it() -> None:
    worker = _v0558_historical_bicycle_worker()
    worker._class_refine_overrides[7] = ("bicycle", .99, 130)
    refined, inferred = worker._observe_class_refiner(7, 200, object(), object(), "motorcycle", "cpu", False, force=True)
    assert inferred and refined is None
    audit = worker._class_refine_decision_audit_this_frame[0]
    assert audit["frame_index"] == 200 and audit["winning_source_frame_index"] == 130
    assert audit["consensus"] and not audit["ttl_eligible"] and audit["refined"] is None
    assert worker._class_refine_overrides[7][2] == 130
    assert worker.state.class_consensus_rescues == 0


def test_v0559_class_audit_keeps_eligible_consensus_source_distinct_from_decision() -> None:
    worker = _v0558_historical_bicycle_worker()
    worker._class_refine_overrides[7] = ("bicycle", .99, 130)
    refined, inferred = worker._observe_class_refiner(7, 160, object(), object(), "motorcycle", "cpu", False, force=True)
    assert inferred and refined is not None and refined[0] == "bicycle"
    audit = worker._class_refine_decision_audit_this_frame[0]
    assert audit["frame_index"] == 160 and audit["winning_source_frame_index"] == 130
    assert audit["consensus"] and audit["ttl_eligible"]
    assert audit["refined"] == {"label": refined[0], "confidence": refined[1]}
    assert worker._class_refine_overrides[7][2] == 130


def test_v0559_class_audit_storage_cap_does_not_change_inference_or_decisions() -> None:
    worker = _class_worker()
    calls = []
    worker._refine_crossing_label = lambda *_args, **kwargs: calls.append(kwargs["model"]) or ("car", .90)
    for tid in (7, 8):
        assert worker._observe_class_refiner(tid, 100, object(), object(), "car", "cpu", False, force=True) == (("car", .90), True)
    assert len(worker._class_refine_decision_audit_this_frame) == worker.refine_max_per_frame == 1
    assert len(calls) == 4 and worker.state.class_refine_checks == 2
    worker._class_refine_decision_audit_this_frame = []
    assert worker._observe_class_refiner(7, 101, object(), object(), "car", "cpu", False, force=True) == (("car", .90), True)
    assert worker._class_refine_decision_audit_this_frame[0]["frame_index"] == 101


def test_v0559_semantic_trace_snapshot_reads_clocks_without_mutation_or_expiry() -> None:
    from app.classification import TruckSemanticLock

    worker = _class_worker()
    worker._truck_semantic_lock = TruckSemanticLock(ttl_frames=30)
    worker._truck_semantic_lock.observe(7, 100, stable_label="truck", certainty=.90, hits=6)
    worker._class_refine_overrides[7] = ("truck", .80, 95)
    before_overrides = dict(worker._class_refine_overrides)
    before_locks = dict(worker._truck_semantic_lock._locks)
    snapshot = worker._class_semantic_snapshot_for(7, 110, "car")
    assert snapshot == {
        "class_override": {"label": "truck", "confidence": .80, "source_frame_index": 95, "expires_after_frame_index": 335},
        "truck_semantic_lock": {"label": "truck", "confidence": .90, "source_frame_index": 100, "expires_after_frame_index": 130},
    }
    assert worker._class_semantic_snapshot_for(7, 94, "car") == {"class_override": None, "truck_semantic_lock": None}
    assert worker._class_semantic_snapshot_for(7, 110, "motorcycle") == {"class_override": None, "truck_semantic_lock": None}
    assert worker._class_semantic_snapshot_for(7, 336, "car") == {"class_override": None, "truck_semantic_lock": None}
    snapshot["class_override"]["confidence"] = .01
    snapshot["truck_semantic_lock"]["source_frame_index"] = 999
    assert worker._class_refine_overrides == before_overrides and worker._truck_semantic_lock._locks == before_locks


def test_v0559_class_audit_invalid_rect_does_not_interrupt_semantic_result() -> None:
    worker = _class_worker()
    worker._refine_crossing_label = lambda *_args, **_kwargs: ("car", .90)
    assert worker._observe_class_refiner(7, 100, object(), (10.0, float("nan"), 30.0, 40.0), "car", "cpu", False, force=True) == (("car", .90), True)
    assert worker._class_refine_decision_audit_this_frame[0]["target_rect"] is None


def test_v0559_class_audit_distinguishes_absent_model_from_no_matched_opinion() -> None:
    worker = _class_worker()
    worker._general_refiner_model = None
    worker._general_refine_ids = []
    worker._refine_crossing_label = lambda *_args, **_kwargs: None
    assert worker._observe_class_refiner(7, 100, object(), object(), "car", "cpu", False, force=True) == (None, True)
    audit = worker._class_refine_decision_audit_this_frame[0]
    assert audit["attempted_sources"] == ["domain"]
    assert audit["opinions"] == {"domain": None, "general": None}
    worker._class_refine_decision_audit_this_frame = []
    worker._refiner_model = None
    assert worker._observe_class_refiner(8, 101, object(), object(), "car", "cpu", False, force=True) == (None, False)
    assert worker._class_refine_decision_audit_this_frame == []


def test_v0561_fresh_car_crossing_override_requires_two_consecutive_target_wins() -> None:
    worker = _class_worker()
    worker.truck_lock_car_demotion_conf = 0.80
    worker.truck_lock_car_demotion_frames = 2
    worker._truck_lock_demotion_tracks = set()
    worker.state.truck_lock_demotion_rescues = 0

    worker._refine_consensus.update(254023, 16049, "car", 0.838867, "general")
    assert worker._fresh_car_crossing_override(254023, 16049, ("car", 0.838867)) is None

    worker._refine_consensus.update(254023, 16050, "car", 0.858887, "general")
    result = worker._fresh_car_crossing_override(254023, 16050, ("car", 0.858887))
    assert result is not None and result[0] == "car" and result[1] > 0.90
    assert worker.state.truck_lock_demotion_rescues == 1


def test_v0561_fresh_car_crossing_override_does_not_beat_stronger_same_frame_truck() -> None:
    worker = _class_worker()
    worker.truck_lock_car_demotion_conf = 0.80
    worker.truck_lock_car_demotion_frames = 2
    worker._truck_lock_demotion_tracks = set()
    worker.state.truck_lock_demotion_rescues = 0

    worker._refine_consensus.update(5, 200, "car", 0.86, "general")
    worker._refine_consensus.update(5, 201, "car", 0.87, "general")
    worker._refine_consensus.update(5, 201, "truck", 0.91, "domain")
    assert worker._fresh_car_crossing_override(5, 201, ("car", 0.87)) is None
    assert worker.state.truck_lock_demotion_rescues == 0


def test_v0562_car_observation_cannot_extend_expired_truck_lock_through_override_cache() -> None:
    from app.classification import TruckSemanticLock

    worker = _class_worker()
    worker._truck_semantic_lock = TruckSemanticLock(ttl_frames=30)
    worker._truck_semantic_lock.observe(7, 100, stable_label="truck", certainty=.90, hits=4)
    assert worker._remember_class_refinement(
        7, 129, "car", "car", .90, 8, "car", ("car", .90),
    ) == ("truck", .90)
    assert worker._class_refine_overrides[7] == ("car", .90, 129)
    assert worker._class_override_for(7, 130, "car") == ("truck", .90)
    assert worker._class_override_for(7, 131, "car") == ("car", .90)
    assert worker.state.truck_class_rescues == 1


def test_v0562_locked_bus_consensus_retains_its_actual_source_clock_and_reappears_after_lock() -> None:
    from app.classification import TruckSemanticLock

    worker = _class_worker()
    worker._truck_semantic_lock = TruckSemanticLock(ttl_frames=30)
    worker._truck_semantic_lock.observe(7, 100, stable_label="truck", certainty=.90, hits=4)
    refined = ("bus", .83)
    worker._class_refine_consensus_proof[7] = (129, refined)
    worker._class_refine_consensus_source_frame = {7: (129, 110)}
    assert worker._remember_class_refinement(
        7, 129, "car", "car", .99, 8, "car", refined,
    ) == ("truck", .90)
    assert worker._class_refine_overrides[7] == ("bus", .83, 110)
    assert worker._class_override_for(7, 131, "car") == refined
    assert worker._class_override_for(7, 350, "car") == refined
    assert worker._class_override_for(7, 351, "car") is None


def test_v0562_rejected_car_demotion_uses_retained_primary_truck_clock() -> None:
    from app.classification import TrackLabelSmoother, TruckSemanticLock

    worker = _class_worker()
    worker._labels = TrackLabelSmoother()
    worker._truck_semantic_lock = TruckSemanticLock(ttl_frames=30)
    for frame in (90, 95, 100):
        worker._labels.update(7, "truck", .90, frame_index=frame)
    worker._labels.update(7, "car", .10, frame_index=129)
    worker._remember_class_refinement(7, 129, "car", "truck", .90, 3, "truck", ("car", .60))
    assert worker._class_refine_overrides[7] == ("truck", .90, 100)
    assert worker._class_override_for(7, 340, "car") == ("truck", .90)
    assert worker._class_override_for(7, 341, "car") is None


def test_v0562_expired_retained_primary_cannot_become_fresh_override() -> None:
    from app.classification import TrackLabelSmoother, TruckSemanticLock

    worker = _class_worker()
    worker._labels = TrackLabelSmoother()
    worker._truck_semantic_lock = TruckSemanticLock(ttl_frames=30)
    for frame in (90, 95, 100):
        worker._labels.update(7, "truck", .90, frame_index=frame)
    assert worker._remember_class_refinement(
        7, 400, "car", "truck", .90, 3, "truck", ("car", .60),
    ) is None
    assert worker._class_refine_overrides == {}
    assert worker._truck_semantic_lock._locks == {}


def test_v0562_future_retained_primary_cannot_become_current_override() -> None:
    from app.classification import TrackLabelSmoother

    worker = _class_worker()
    worker._labels = TrackLabelSmoother()
    for frame in (200, 201, 202):
        worker._labels.update(7, "truck", .90, frame_index=frame)
    assert worker._remember_class_refinement(
        7, 129, "car", "truck", .90, 3, "truck", ("car", .60),
    ) is None
    assert worker._class_refine_overrides == {}
    assert worker._truck_semantic_lock._locks == {}


def test_v0562_older_retained_primary_cannot_replace_newer_qualified_correction() -> None:
    from app.classification import TrackLabelSmoother

    worker = _class_worker()
    worker._labels = TrackLabelSmoother()
    worker._labels.update(7, "truck", .90, frame_index=100)
    worker._class_refine_overrides[7] = ("car", .85, 120)
    assert worker._remember_class_refinement(
        7, 129, "car", "truck", .75, 2, "truck", ("car", .60),
    ) == ("car", .85)
    assert worker._class_refine_overrides[7] == ("car", .85, 120)


def test_v0562_actual_fresh_truck_promotion_keeps_current_clock_and_rescue_counter() -> None:
    worker = _class_worker()
    assert worker._remember_class_refinement(
        7, 129, "car", "car", .80, 8, "car", ("truck", .70),
    ) == ("truck", .80)
    assert worker._class_refine_overrides[7] == ("truck", .80, 129)
    assert worker.state.truck_class_rescues == 1


def test_v0562_genuine_truck_consensus_remains_eligible_after_older_lock_expires() -> None:
    from app.classification import TruckSemanticLock

    worker = _class_worker()
    worker._truck_semantic_lock = TruckSemanticLock(ttl_frames=30)
    worker._truck_semantic_lock.observe(7, 100, stable_label="truck", certainty=.90, hits=4)
    refined = ("truck", .83)
    worker._class_refine_consensus_proof[7] = (129, refined)
    worker._class_refine_consensus_source_frame = {7: (129, 110)}
    assert worker._remember_class_refinement(
        7, 129, "car", "car", .99, 8, "car", refined,
    ) == ("truck", .90)
    assert worker._class_refine_overrides[7] == ("truck", .83, 110)
    assert worker._class_override_for(7, 131, "car") == refined


def test_v0562_verified_fresh_car_crossing_still_overrides_eligible_global_lock() -> None:
    from app.classification import TruckSemanticLock

    worker = _class_worker()
    worker._truck_semantic_lock = TruckSemanticLock(ttl_frames=30)
    worker._truck_semantic_lock.observe(7, 100, stable_label="truck", certainty=.90, hits=4)
    worker._refine_consensus.update(7, 128, "car", .86, "general")
    worker._refine_consensus.update(7, 129, "car", .88, "general")
    result = worker._resolve_crossing_class_refinement(
        7, 129, "car", "car", .90, 8, "car", ("car", .88),
    )
    assert result[0] == "car" and result[1] > .90
    assert worker._truck_semantic_lock._locks[7] == (.90, 100)
    assert worker._class_refine_overrides[7] == ("car", .90, 129)
    assert worker.state.truck_lock_demotion_rescues == 1


def _v0563_locked_truck_candidate(worker, track_id=254023, *, distance=.003365):
    worker._truck_semantic_lock.observe(
        track_id, 16049, stable_label="truck", certainty=.9958174520916362, hits=25,
    )
    worker._class_refine_last_check[track_id] = 16007
    worker._class_refine_last_observation[track_id] = (16007, ("car", .716796875))
    worker._class_refine_overrides[track_id] = ("car", .8829369611178074, 16007)
    return {
        "distance": distance, "confidence": .800781, "track_id": track_id,
        "rect": (906.229431, 262.029603, 1197.227905, 538.287049),
        "current_label": "truck", "stable_label": "truck",
        "certainty": .923315, "hits": 25, "base_display_label": "truck", "display_label": "truck",
    }


def test_v0563_locked_truck_near_gate_samples_missing_previous_car_frame() -> None:
    worker = _class_worker()
    candidate = _v0563_locked_truck_candidate(worker)
    worker._refiner_model = None
    worker._refine_crossing_label = lambda *_args, **_kwargs: (
        "car", .8388671875 if worker._class_refine_last_check[254023] == 16049 else .85888671875,
    )
    worker._refine_consensus.update(254023, 16007, "car", .716796875, "general")

    assert worker._run_deferred_class_refinements(
        [candidate], 16049, object(), "cpu", False, 0, set(),
    ) == 1
    assert worker._class_refine_last_check[254023] == 16049
    assert worker._class_refine_overrides[254023][0::2] == ("car", 16049)
    # Sampling a CAR observation does not globally clear the live TRUCK lock.
    assert worker._class_override_for(254023, 16049, "truck")[0] == "truck"
    refined, inferred = worker._observe_class_refiner(
        254023, 16050, object(), candidate["rect"], "truck", "cpu", False, force=True,
    )
    assert inferred and refined == ("car", .85888671875)
    result = worker._resolve_crossing_class_refinement(
        254023, 16050, "truck", "truck", .9269068210965732, 25, "truck", refined,
    )
    assert result[0] == "car" and result[1] > .97
    assert worker.state.truck_lock_demotion_rescues == 1
    assert worker._truck_semantic_lock.snapshot_for(254023, 16050, "truck") is not None


def test_v0563_lock_prescan_requires_live_current_four_wheel_lock() -> None:
    worker = _class_worker()
    before = dict(worker._truck_semantic_lock._locks)
    assert not worker._truck_lock_prescan_candidate(7, 100, "truck", .01)
    worker._truck_semantic_lock.observe(7, 100, stable_label="truck", certainty=.90, hits=4)
    assert worker._truck_lock_prescan_candidate(7, 100, "truck", .01)
    for label in ("car", "bus", "motorcycle", "bicycle"):
        assert not worker._truck_lock_prescan_candidate(7, 100, label, .01)
    locked = dict(worker._truck_semantic_lock._locks)
    assert not worker._truck_lock_prescan_candidate(7, 99, "truck", .01)
    assert not worker._truck_lock_prescan_candidate(7, 551, "truck", .01)
    assert worker._truck_semantic_lock._locks == locked and before == {}


def test_v0563_lock_prescan_uses_finite_gate_proximity_and_radius() -> None:
    worker = _class_worker()
    worker._truck_semantic_lock.observe(7, 100, stable_label="truck", certainty=.90, hits=4)
    a, b = (100, 500), (900, 500)
    near = worker._finite_gate_distance_ratio((500, 510), a, b, 1000, 1000)
    extension = worker._finite_gate_distance_ratio((1101, 500), a, b, 1000, 1000)
    assert worker._truck_lock_prescan_candidate(7, 100, "truck", near)
    assert not worker._truck_lock_prescan_candidate(7, 100, "truck", extension)
    assert worker._truck_lock_prescan_candidate(7, 100, "truck", .11)
    for distance in (.110001, -.001, float("nan"), float("inf")):
        assert not worker._truck_lock_prescan_candidate(7, 100, "truck", distance)


def test_v0563_due_two_wheel_periodic_work_keeps_priority_over_lock_prescan() -> None:
    for label in ("motorcycle", "bicycle"):
        worker = _class_worker()
        truck = _v0563_locked_truck_candidate(worker)
        ordinary = {**truck, "track_id": 7, "distance": .02, "display_label": label,
                    "current_label": label, "stable_label": label, "base_display_label": label}
        calls = []
        worker._refine_crossing_label = lambda *_args, **kwargs: (
            calls.append(kwargs["target_label"]) or (label, .90)
        )
        assert worker._run_deferred_class_refinements(
            [truck, ordinary], 16049, object(), "cpu", False, 0, set(),
        ) == 1
        assert calls == [label, label]
        assert worker._class_refine_last_check[254023] == 16007
        assert worker._class_refine_last_check[7] == 16049


def test_v0563_lock_prescan_respects_crossing_slots_and_original_max_budget() -> None:
    worker = _class_worker()
    first = _v0563_locked_truck_candidate(worker, 7, distance=.003)
    second = _v0563_locked_truck_candidate(worker, 8, distance=.004)
    calls = []
    worker._refine_crossing_label = lambda *_args, **kwargs: (
        calls.append(kwargs["target_label"]) or ("car", .86)
    )
    assert worker._run_deferred_class_refinements(
        [first, second], 16049, object(), "cpu", False, 1, set(),
    ) == 1
    assert calls == []
    worker.refine_max_per_frame = 2
    assert worker._run_deferred_class_refinements(
        [second, first], 16049, object(), "cpu", False, 1, set(),
    ) == 2
    assert worker._class_refine_last_check[7] == 16049
    assert worker._class_refine_last_check[8] == 16007
    assert len(calls) == 2  # One target inference, with domain + general opinions.


def test_v0563_crossing_target_cannot_receive_a_deferred_lock_prescan() -> None:
    worker = _class_worker()
    candidate = _v0563_locked_truck_candidate(worker)
    calls = []
    worker._observe_class_refiner = lambda *_args, **_kwargs: calls.append(1) or (None, True)
    assert worker._run_deferred_class_refinements(
        [candidate], 16049, object(), "cpu", False, 0, {254023},
    ) == 0
    assert calls == []


def test_v0563_lock_prescan_same_frame_no_opinion_is_one_inference() -> None:
    worker = _class_worker()
    candidate = _v0563_locked_truck_candidate(worker)
    worker.refine_max_per_frame = 3
    worker._refine_crossing_label = lambda *_args, **_kwargs: None
    assert worker._run_deferred_class_refinements(
        [candidate, candidate], 16049, object(), "cpu", False, 0, set(),
    ) == 1
    assert worker.state.class_refine_checks == 1
    assert worker._class_refine_last_observation[254023] == (16049, None)
    assert worker._class_refine_overrides[254023][2] == 16007


def test_v0563_lock_prescan_stronger_same_frame_truck_still_vetoes_car_demotion() -> None:
    for truck_confidence in (.86, .91):
        worker = _class_worker()
        candidate = _v0563_locked_truck_candidate(worker)
        worker._refine_crossing_label = lambda *_args, **kwargs: (
            ("truck", truck_confidence) if kwargs["model"] is worker._refiner_model else ("car", .86)
        )
        assert worker._run_deferred_class_refinements(
            [candidate], 16049, object(), "cpu", False, 0, set(),
        ) == 1
        refined, _ = worker._observe_class_refiner(
            254023, 16050, object(), candidate["rect"], "truck", "cpu", False, force=True,
        )
        result = worker._resolve_crossing_class_refinement(
            254023, 16050, "truck", "truck", .93, 25, "truck", refined,
        )
        assert result[0] == "truck"
        assert worker._refine_consensus.recent_four_wheel_wins(254023, 16050, "car")[0] == 0
        assert getattr(worker.state, "truck_lock_demotion_rescues", 0) == 0


def test_v0563_lock_prescan_missing_model_cannot_create_temporal_evidence() -> None:
    worker = _class_worker()
    candidate = _v0563_locked_truck_candidate(worker)
    worker._refiner_model = worker._general_refiner_model = None
    assert worker._run_deferred_class_refinements(
        [candidate], 16049, object(), "cpu", False, 0, set(),
    ) == 0
    assert worker.state.class_refine_checks == 0
    assert worker._refine_consensus.recent_four_wheel_wins(254023, 16049, "car")[0] == 0


def test_v0563_deferred_away_or_expired_or_future_lock_keeps_periodic_cadence() -> None:
    for frame, distance in ((16049, .12), (16048, .01), (16500, .01)):
        worker = _class_worker()
        candidate = _v0563_locked_truck_candidate(worker, distance=distance)
        # Keep ordinary cadence ineligible even in the future/expired controls.
        worker._class_refine_last_check[254023] = frame - 1
        calls = []
        worker._refine_crossing_label = lambda *_args, **_kwargs: calls.append(1) or ("car", .90)
        assert worker._run_deferred_class_refinements(
            [candidate], frame, object(), "cpu", False, 0, set(),
        ) == 0
        assert calls == []


def test_v0563_one_lock_prescan_cannot_replace_two_consecutive_car_wins() -> None:
    worker = _class_worker()
    candidate = _v0563_locked_truck_candidate(worker)
    worker._refine_crossing_label = lambda *_args, **_kwargs: ("car", .86)
    assert worker._run_deferred_class_refinements(
        [candidate], 16049, object(), "cpu", False, 0, set(),
    ) == 1
    assert worker._fresh_car_crossing_override(254023, 16049, ("car", .86)) is None
    assert worker._fresh_car_crossing_override(254023, 16050, ("car", .86)) is None
    assert getattr(worker.state, "truck_lock_demotion_rescues", 0) == 0


def _v0564_deterministic_class_worker(lag=2.0):
    worker = _class_worker()
    worker.state.deterministic_video_replay = True
    worker.state.frame_policy = "all-frames"
    worker.state.playback_lag_seconds = lag
    return worker


def test_v0564_actual_crossing_collects_second_fresh_car_vote_at_all_replay_lags() -> None:
    # These are controlled refiner opinions, not a claim that this CAR vote
    # will be returned by a model when session 169 is replayed on Windows.
    for lag in (0.0, .36, 2.0):
        worker = _v0564_deterministic_class_worker(lag)
        candidate = _v0563_locked_truck_candidate(worker)
        worker._refiner_model = None
        worker._refine_crossing_label = lambda *_args, **_kwargs: ("car", .86)
        assert worker._run_deferred_class_refinements(
            [candidate], 16049, object(), "cpu", False, 0, set(),
        ) == 1

        env = _execute_frame_class_work(
            worker, [(254023, (500, 510), "OUT")], frame_index=16050, label="truck",
        )

        audit = env["gate_trace_track"]["crossing_class_refinement_audit"]
        assert env["event_label"] == "car"
        assert env["refines_used_this_frame"] == 1
        assert worker.state.class_refine_checks == 2
        assert worker.state.truck_lock_demotion_rescues == 1
        assert worker._truck_semantic_lock.snapshot_for(254023, 16050, "truck") is not None
        assert audit["admission_reason"] == "admitted_deterministic_all_frames"
        assert audit["observed_frame_index"] == 16050
        assert audit["playback_lag_seconds"] == lag
        assert audit["slots_used_before"] == 0 and audit["slot_budget"] == 1
        assert audit["request_inference"] and audit["target_sample_attempted"]
        assert audit["target_opinion_available"]


def test_v0564_crossing_lag_bypass_requires_video_determinism_and_all_frames() -> None:
    for deterministic, policy in ((False, "all-frames"), (True, "live-latest"), (False, "live-latest")):
        worker = _v0564_deterministic_class_worker()
        worker.state.deterministic_video_replay = deterministic
        worker.state.frame_policy = policy
        calls = []
        worker._observe_class_refiner = lambda *_args, **_kwargs: calls.append(1) or (("bicycle", .95), True)

        env = _execute_frame_class_work(worker, [(7, (500, 510), "IN")])

        assert calls == [] and env["refines_used_this_frame"] == 0
        audit = env["gate_trace_track"]["crossing_class_refinement_audit"]
        assert audit["admission_reason"] == "video_lag_limited"
        assert not audit["deterministic_all_frames"]
        assert not audit["request_inference"] and not audit["target_sample_attempted"]


def test_v0564_non_deterministic_video_retains_inclusive_lag_limit() -> None:
    for lag, expected in ((.35, 1), (.350001, 0)):
        worker = _class_worker()
        worker.state.playback_lag_seconds = lag
        calls = []
        worker._observe_class_refiner = lambda *_args, **_kwargs: calls.append(1) or (("motorcycle", .9), True)

        env = _execute_frame_class_work(worker, [(7, (500, 510), "IN")])

        assert len(calls) == expected and env["refines_used_this_frame"] == expected
        assert env["gate_trace_track"]["crossing_class_refinement_audit"]["admission_reason"] == (
            "admitted_video_within_lag" if expected else "video_lag_limited"
        )


def test_v0564_live_source_keeps_existing_crossing_lag_behavior() -> None:
    worker = _v0564_deterministic_class_worker()
    worker.payload.source_type = "rtsp"
    calls = []
    worker._observe_class_refiner = lambda *_args, **_kwargs: calls.append(1) or (("motorcycle", .9), True)

    env = _execute_frame_class_work(worker, [(7, (500, 510), "IN")])

    assert calls == [1] and env["refines_used_this_frame"] == 1
    audit = env["gate_trace_track"]["crossing_class_refinement_audit"]
    assert audit["admission_reason"] == "admitted_live"
    assert not audit["deterministic_all_frames"]


def test_v0564_deterministic_crossing_preserves_disabled_label_and_slot_guards() -> None:
    for disabled, label, initial_used, expected in (
        (True, "motorcycle", 0, "refinement_disabled"),
        (False, "other", 0, "unsupported_label"),
        (False, "motorcycle", 1, "target_budget_exhausted"),
    ):
        worker = _v0564_deterministic_class_worker()
        worker.refine_at_crossing = not disabled
        calls = []
        worker._observe_class_refiner = lambda *_args, **_kwargs: calls.append(1) or (("bicycle", .95), True)

        env = _execute_frame_class_work(worker, [(7, (500, 510), "IN")], initial_used=initial_used, label=label)

        assert calls == [] and env["refines_used_this_frame"] == initial_used
        assert env["gate_trace_track"]["crossing_class_refinement_audit"]["admission_reason"] == expected


def test_v0564_deterministic_multiple_crossings_share_original_frame_budget() -> None:
    worker = _v0564_deterministic_class_worker()
    calls = []
    worker._observe_class_refiner = lambda track, *_args, **_kwargs: calls.append(track) or (("motorcycle", .9), True)

    env = _execute_frame_class_work(worker, [(7, (500, 510), "IN"), (8, (500, 515), "OUT")])

    assert calls == [7] and env["refines_used_this_frame"] == 1
    assert env["gate_trace_track"]["crossing_class_refinement_audit"]["admission_reason"] == "target_budget_exhausted"


def test_v0564_same_frame_crossing_cache_cannot_spend_or_invent_another_opinion() -> None:
    for cached in (None, ("bicycle", .95)):
        worker = _v0564_deterministic_class_worker()
        worker._class_refine_last_observation[7] = (100, cached)
        calls = []
        worker._observe_class_refiner = lambda *_args, **_kwargs: calls.append(1) or (("bicycle", .99), True)

        env = _execute_frame_class_work(worker, [(7, (500, 510), "IN")], initial_used=1)

        assert calls == [] and env["refines_used_this_frame"] == 1
        audit = env["gate_trace_track"]["crossing_class_refinement_audit"]
        assert audit["admission_reason"] == "same_frame_cached"
        assert audit["same_frame_cached"] and not audit["target_sample_attempted"]
        assert audit["target_opinion_available"] is (cached is not None)


def test_v0564_missing_models_cannot_create_crossing_evidence_or_spend_slots() -> None:
    worker = _v0564_deterministic_class_worker()
    worker._refiner_model = worker._general_refiner_model = None

    env = _execute_frame_class_work(worker, [(7, (500, 510), "IN")])

    assert worker.state.class_refine_checks == 0 and env["refines_used_this_frame"] == 0
    assert worker._class_refine_last_observation == {}
    audit = env["gate_trace_track"]["crossing_class_refinement_audit"]
    assert audit["admission_reason"] == "models_unavailable"
    assert not audit["models_available"] and not audit["target_opinion_available"]


def test_v0564_future_observation_is_not_crossing_frame_evidence() -> None:
    worker = _v0564_deterministic_class_worker()
    worker._class_refine_last_observation[7] = (101, ("bicycle", .95))

    env = _execute_frame_class_work(worker, [(7, (500, 510), "IN")])

    assert env["refines_used_this_frame"] == 0
    assert worker._class_refine_last_observation[7] == (101, ("bicycle", .95))
    audit = env["gate_trace_track"]["crossing_class_refinement_audit"]
    assert audit["admission_reason"] == "future_observation_cached"
    assert not audit["target_opinion_available"]


def test_v0564_attempted_sample_without_target_does_not_claim_class_evidence() -> None:
    worker = _v0564_deterministic_class_worker()
    worker._refine_crossing_label = lambda *_args, **_kwargs: None

    env = _execute_frame_class_work(worker, [(7, (500, 510), "IN")])

    assert env["refines_used_this_frame"] == 1 and worker.state.class_refine_checks == 1
    assert worker._class_refine_last_observation[7] == (100, None)
    assert worker._class_refine_overrides == {}
    audit = env["gate_trace_track"]["crossing_class_refinement_audit"]
    assert audit["request_inference"] and audit["target_sample_attempted"]
    assert not audit["target_opinion_available"]
    assert "inference_performed" not in audit


def test_v0564_deterministic_crossing_keeps_stronger_truck_veto_and_two_frame_threshold() -> None:
    for domain, general in ((None, ("car", .79)), (("truck", .91), ("car", .86)), (None, ("car", .86))):
        worker = _v0564_deterministic_class_worker()
        _v0563_locked_truck_candidate(worker)
        worker._refine_crossing_label = lambda *_args, **kwargs: (
            domain if kwargs["model"] is worker._refiner_model else general
        )
        # Only one actual source frame is admitted here: even .86 CAR cannot
        # replace the two distinct consecutive CAR-winning frame contract.
        env = _execute_frame_class_work(worker, [(254023, (500, 510), "OUT")], frame_index=16050, label="truck")

        assert env["event_label"] == "truck" and env["refines_used_this_frame"] == 1
        assert getattr(worker.state, "truck_lock_demotion_rescues", 0) == 0


def test_v0564_deterministic_crossing_does_not_unthrottle_periodic_or_lock_prescan() -> None:
    worker = _v0564_deterministic_class_worker()
    worker._truck_semantic_lock.observe(7, 100, stable_label="truck", certainty=.90, hits=4)
    calls = []
    worker._observe_class_refiner = lambda *_args, **_kwargs: calls.append(1) or (("car", .9), True)

    env = _execute_frame_class_work(worker, [(7, (500, 510), None)], label="truck")

    assert calls == [] and env["refines_used_this_frame"] == 0
    assert env["periodic_class_refine_candidates"] == []


def test_v0564_crossing_admission_audit_uses_selected_source_clock_without_overwriting_observation() -> None:
    import ast
    from pathlib import Path
    import app.worker as worker_module

    worker = _v0564_deterministic_class_worker()
    env = _execute_frame_class_work(worker, [(7, (500, 510), "IN")], frame_index=16050)
    tree = ast.parse(Path(worker_module.__file__).read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "PipelineWorker")
    run = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "run")
    clock_assignments = [
        node for node in ast.walk(run) if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                and target.value.id == "crossing_class_admission" and isinstance(target.slice, ast.Constant)
                and target.slice.value in {"source_frame_index", "source_time_seconds"} for target in node.targets)
    ]
    assert len(clock_assignments) == 2
    # The selected interpolated event clock can precede the actual crossing
    # inference frame. Execute the production assignments without relabeling it.
    env.update({"event_frame_index": 16049, "source_time_seconds": 641.9311})
    exec(compile(ast.fix_missing_locations(ast.Module(body=clock_assignments, type_ignores=[])), worker_module.__file__, "exec"), env)
    audit = env["gate_trace_track"]["crossing_class_refinement_audit"]
    assert audit["observed_frame_index"] == 16050
    assert audit["source_frame_index"] == 16049 and audit["source_time_seconds"] == 641.9311
    assert "confidence" not in audit and "backend_event_id" not in audit
