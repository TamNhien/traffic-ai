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


def _execute_frame_class_work(worker, tracks, *, initial_used=0):
    """Execute the real production loop's class-work statements in track order.

    Only camera transport/inference is supplied by the fixture. This deliberately
    runs the production frame sections instead of reimplementing their budget
    algorithm; the V0.5.54 sections spend the first slot before a later crossing.
    """
    import ast
    from pathlib import Path
    import app.worker as worker_module

    source_path = Path(worker_module.__file__)
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
        "self": worker, "frame_index": 100, "width": 1000, "height": 1000,
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
            "current_label": "motorcycle", "stable_label": "motorcycle", "display_label": "motorcycle",
            "base_display_label": "motorcycle", "class_certainty": .95, "class_hits": 10,
            "confidence_f": .30, "direction": crossing_direction,
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
