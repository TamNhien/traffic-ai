from types import SimpleNamespace

from app.worker import PipelineWorker, _PendingGuardCrossing


class _Dispatcher:
    def __init__(self) -> None:
        self.payloads = []

    def submit(self, payload) -> None:
        self.payloads.append(payload)


class _Counter:
    def __init__(self) -> None:
        self.revoked = []

    def revoke_last_crossing(self, track_id: int, direction: str) -> None:
        self.revoked.append((track_id, direction))


def _worker() -> PipelineWorker:
    worker = PipelineWorker.__new__(PipelineWorker)
    worker.payload = SimpleNamespace(camera_id=1, session_id=2, model_id=3)
    worker.state = SimpleNamespace(
        total_count=0,
        counts_by_type={"motorcycle": 0, "bicycle": 0, "car": 0, "bus": 0, "truck": 0, "other": 0},
        in_count=0,
        out_count=0,
        direct_crossings=0,
        interpolated_crossings=0,
        rescued_crossings=0,
        human_guard_deferred_commits=0,
        human_guard_pending_crossings=1,
        human_guard_pending_drops=0,
    )
    worker._committed_in_count = 0
    worker._committed_out_count = 0
    worker._pending_guard_crossings = {}
    worker._heavy_center_rescue_tracks = set()
    worker._event_dispatcher = _Dispatcher()
    worker._save_crossing_snapshot = lambda _cv2, _frame, frame_index: f"frame_{frame_index}.jpg"
    return worker


def _pending() -> _PendingGuardCrossing:
    return _PendingGuardCrossing(
        track_id=77,
        label="motorcycle",
        direction="in",
        confidence=0.82,
        frame_index=519,
        source_time_seconds=20.72,
        crossing_method="direct",
        crossing_x=0.51,
        crossing_y=0.62,
        snapshot_frame=object(),
    )


def test_transactional_guard_commit_preserves_original_crossing_metadata() -> None:
    worker = _worker()
    pending = _pending()
    worker._pending_guard_crossings[pending.track_id] = pending

    worker._commit_guard_crossing(object(), pending)

    assert worker.state.total_count == 1
    assert worker.state.in_count == 1
    assert worker.state.out_count == 0
    assert worker.state.direct_crossings == 1
    assert worker.state.human_guard_deferred_commits == 1
    assert worker.state.human_guard_pending_crossings == 0
    assert pending.track_id not in worker._pending_guard_crossings
    payload = worker._event_dispatcher.payloads[0]
    assert payload["tracking_id"] == 77
    assert payload["source_frame_index"] == 519
    assert payload["source_time_seconds"] == 20.72
    assert payload["crossing_x"] == 0.51
    assert payload["crossing_y"] == 0.62


def test_transactional_guard_timeout_drops_without_counting() -> None:
    worker = _worker()
    pending = _pending()
    worker._pending_guard_crossings[pending.track_id] = pending
    counter = _Counter()

    worker._drop_guard_crossing(counter, pending, expired=True)

    assert counter.revoked == [(77, "in")]
    assert worker.state.total_count == 0
    assert worker.state.human_guard_pending_drops == 1
    assert worker.state.human_guard_pending_crossings == 0
    assert worker._event_dispatcher.payloads == []


def test_v0551_guard_rollback_restores_both_gate_passage_states() -> None:
    from app.counting import CountingLine, LineCrossingCounter, VerifiedAnchorSpanRescuer

    line = CountingLine(0.1, 0.5, 0.9, 0.5)
    counter = LineCrossingCounter(line, crossing_cooldown_frames=60)
    span = VerifiedAnchorSpanRescuer(line)
    worker = _worker()
    worker._anchor_span_rescuer = span
    assert counter.register_external_crossing(77, "in", 5, (50, 50)) is True
    span.mark_counted(77, "in", 5)
    before = span.capture_passage_state(77)
    assert counter.register_external_crossing(77, "out", 20, (50, 50), verified_anchor_span=True) is True
    span.mark_counted(77, "out", 20)
    pending = _pending()
    pending.direction = "out"
    pending.span_passage_state = before
    worker._pending_guard_crossings[77] = pending

    worker._drop_guard_crossing(counter, pending, expired=True)

    assert counter.in_count == 1
    assert counter.out_count == 0
    assert counter._tracks[77].counted_directions == {"in"}
    assert counter._tracks[77].last_count_frame == 5
    assert span.capture_passage_state(77) == before
    assert span.finalize_lost(77, 21) is None
    assert worker.state.total_count == 0
    assert worker._event_dispatcher.payloads == []


def test_v0551_immediate_guard_reject_restores_secondary_clock() -> None:
    from app.counting import CountingLine, LineCrossingCounter, VerifiedAnchorSpanRescuer

    line = CountingLine(0.1, 0.5, 0.9, 0.5)
    counter = LineCrossingCounter(line, crossing_cooldown_frames=60)
    span = VerifiedAnchorSpanRescuer(line)
    worker = _worker()
    worker._anchor_span_rescuer = span
    before = span.capture_passage_state(77)
    assert counter.register_external_crossing(77, "in", 10, (50, 50)) is True
    span.mark_counted(77, "in", 10)

    worker._rollback_guard_crossing(counter, 77, "in", before)

    assert counter.total_crossings == 0
    assert span.capture_passage_state(77) == before
    assert counter.register_external_crossing(77, "in", 12, (50, 50)) is True
    assert counter.total_crossings == 1


def test_v0552_pending_guard_restores_every_secondary_passage_and_rescue() -> None:
    from app.counting import (
        CountingLine, HeavyVehicleCrossingRescuer, LineCrossingCounter,
        TwoWheelCenterCrossingRescuer, VerifiedAnchorSpanRescuer,
    )

    line = CountingLine(.1, .5, .9, .5)
    counter = LineCrossingCounter(line)
    worker = _worker()
    span = worker._anchor_span_rescuer = VerifiedAnchorSpanRescuer(line)
    heavy = worker._heavy_rescuer = HeavyVehicleCrossingRescuer(line)
    two_wheel = worker._two_wheel_rescuer = TwoWheelCenterCrossingRescuer(line)
    before = [gate.capture_passage_state(77) for gate in (span, heavy, two_wheel)]
    for center in (heavy, two_wheel):
        assert center.update(77, (50, 46), 100, 100, 10, commit=False) is None
        candidate = center.update(77, (50, 54), 100, 100, 11, commit=False)
        assert candidate is not None and candidate[0] == "in"
        assert center.rescues == 0
    assert counter.register_external_crossing(77, "in", 11, (50, 50)) is True
    for gate in (span, heavy, two_wheel):
        gate.mark_counted(77, "in", 11)
    assert heavy.rescues == two_wheel.rescues == 1
    pending = _pending()
    pending.span_passage_state, pending.heavy_passage_state, pending.two_wheel_passage_state = before
    pending.heavy_rescue_was_recorded = False
    worker._heavy_center_rescue_tracks.add(77)
    worker.state.heavy_center_rescues = 1
    worker._pending_guard_crossings[77] = pending

    worker._drop_guard_crossing(counter, pending, expired=True)

    assert [gate.capture_passage_state(77) for gate in (span, heavy, two_wheel)] == before
    assert heavy.rescues == two_wheel.rescues == 0
    assert worker.state.two_wheel_center_rescues == 0
    assert worker._heavy_center_rescue_tracks == set()
    assert worker.state.heavy_center_rescues == 0
    assert counter.total_crossings == 0
    assert worker.state.total_count == 0
    assert worker._event_dispatcher.payloads == []


def test_v0552_immediate_guard_reject_keeps_previous_center_direction_and_clock() -> None:
    from app.counting import (
        CountingLine, HeavyVehicleCrossingRescuer, LineCrossingCounter,
        TwoWheelCenterCrossingRescuer, VerifiedAnchorSpanRescuer,
    )

    line = CountingLine(.1, .5, .9, .5)
    counter = LineCrossingCounter(line, crossing_cooldown_frames=60)
    worker = _worker()
    gates = (
        VerifiedAnchorSpanRescuer(line), HeavyVehicleCrossingRescuer(line),
        TwoWheelCenterCrossingRescuer(line),
    )
    worker._anchor_span_rescuer, worker._heavy_rescuer, worker._two_wheel_rescuer = gates
    assert counter.register_external_crossing(77, "in", 5, (50, 50)) is True
    for gate in gates:
        gate.mark_counted(77, "in", 5)
    before = [gate.capture_passage_state(77) for gate in gates]
    worker._heavy_center_rescue_tracks.add(77)
    worker.state.heavy_center_rescues = 1
    assert counter.register_external_crossing(77, "out", 20, (50, 50), verified_anchor_span=True) is True
    for gate in gates:
        gate.mark_counted(77, "out", 20)

    worker._rollback_guard_crossing(counter, 77, "out", *before, heavy_rescue_was_recorded=True)

    assert [gate.capture_passage_state(77) for gate in gates] == before
    assert counter.in_count == 1
    assert counter.out_count == 0
    assert counter._tracks[77].last_count_frame == 5
    assert worker._heavy_center_rescue_tracks == {77}
    assert worker.state.heavy_center_rescues == 1


def test_v0553_delayed_human_guard_cannot_add_a_strike_from_older_pixels() -> None:
    worker = _worker()
    worker._human_guard_last_observation = {77: (104, "pending", object())}
    worker._human_guard_policy = SimpleNamespace(status=lambda _tid: "pending")
    calls = []
    worker._verify_human_candidate = lambda *_args, **_kwargs: calls.append(1)

    assert worker._observe_human_guard(
        77, 100, object(), object(), "motorcycle", .30, "cpu", False, force=True,
    ) == ("pending", None)
    assert calls == []
    assert worker._human_guard_last_observation[77][0] == 104


def test_v0553_guard_rollback_refreshes_committed_span_and_override_telemetry() -> None:
    from app.counting import CountingLine, LineCrossingCounter, VerifiedAnchorSpanRescuer

    line = CountingLine(.1, .5, .9, .5)
    counter = LineCrossingCounter(line, crossing_cooldown_frames=60)
    span = VerifiedAnchorSpanRescuer(line)
    worker = _worker()
    worker._anchor_span_rescuer = span
    before = span.capture_passage_state(77)
    assert span.update(77, (50, 47), 100, 100, 10, commit=False) is None
    candidate = span.update(77, (50, 53), 100, 100, 11, commit=False)
    assert candidate is not None
    direction, point = candidate
    assert counter.register_external_crossing(
        77, direction, 11, point, crossing_frame=span.crossing_frame_for(77), verified_anchor_span=True,
    ) is True
    span.mark_counted(77, direction, 11, commit_candidate=True)
    worker._refresh_anchor_span_telemetry(counter)
    assert worker.state.verified_anchor_span_rescues == 1

    worker._rollback_guard_crossing(counter, 77, direction, before)

    assert worker.state.verified_anchor_span_rescues == 0
    assert worker.state.post_confirm_closures == 0
    assert worker.state.anchor_span_immediate_overrides == 0
    assert worker.state.anchor_span_lost_finalizations == 0
    assert worker.state.anchor_span_same_direction_overrides == 0
    assert worker.state.anchor_span_cooldown_overrides == 0
    assert span.capture_passage_state(77) == before
    assert counter.total_crossings == 0


def _enable_context_commit(worker):
    worker._bicycle_context_rescue_tracks = set()
    worker._class_refine_overrides = {}
    worker.state.bicycle_context_rescues = 0
    worker.state.bicycle_context_weak_motor_rescues = 0
    worker._bicycle_xframe_audit_this_frame = []


def test_v0554_guard_drop_does_not_commit_proposed_context_label_or_rescue() -> None:
    worker = _worker()
    _enable_context_commit(worker)
    pending = _pending()
    pending.label = "bicycle"
    pending.bicycle_context_method = "weak_motor"
    pending.bicycle_context_audit = {"kind": "bicycle_context", "decision_accepted": True, "commit_status": "pending"}
    worker._pending_guard_crossings[pending.track_id] = pending

    worker._drop_guard_crossing(_Counter(), pending, expired=True)

    assert worker.state.bicycle_context_rescues == 0
    assert worker.state.bicycle_context_weak_motor_rescues == 0
    assert worker._class_refine_overrides == {}
    assert worker.state.counts_by_type["bicycle"] == 0
    assert worker._bicycle_xframe_audit_this_frame[-1]["decision_accepted"] is True
    assert worker._bicycle_xframe_audit_this_frame[-1]["commit_status"] == "expired"


def test_v0554_guard_commit_records_context_rescue_for_original_passage_only() -> None:
    worker = _worker()
    _enable_context_commit(worker)
    pending = _pending()
    pending.label = "bicycle"
    pending.bicycle_context_method = "weak_motor"
    pending.bicycle_context_audit = {"kind": "bicycle_context", "decision_accepted": True, "commit_status": "pending"}
    pending.observed_frame_index = 522
    worker._class_refine_overrides[77] = ("motorcycle", .99, 526)
    worker._pending_guard_crossings[pending.track_id] = pending

    worker._commit_guard_crossing(object(), pending)

    assert worker.state.bicycle_context_rescues == 1
    assert worker.state.bicycle_context_weak_motor_rescues == 1
    assert worker._class_refine_overrides[77] == ("motorcycle", .99, 526)
    assert worker.state.counts_by_type["bicycle"] == 1
    payload = worker._event_dispatcher.payloads[0]
    assert payload["source_frame_index"] == 519
    assert payload["source_time_seconds"] == 20.72
    assert worker._bicycle_xframe_audit_this_frame[-1]["commit_status"] == "accepted"


def test_v0554_eof_flush_persists_expiry_at_original_observation_clock() -> None:
    import io
    import json

    worker = _worker()
    _enable_context_commit(worker)
    worker.state.source_fps = 25.0
    worker.state.processed_frames = 999
    pending = _pending()
    pending.label = "bicycle"
    pending.bicycle_context_method = "weak_motor"
    pending.observed_frame_index = 522
    pending.bicycle_context_audit = {
        "kind": "bicycle_context", "track_id": 77, "frame_index": 522,
        "decision_accepted": True, "commit_status": "pending",
    }
    worker._pending_guard_crossings[77] = pending
    trace = io.StringIO()
    # This row is already on disk when EOF is reached.
    trace.write(json.dumps({"source_time_seconds": 20.84, "bicycle_xframe_decision_audit": [dict(pending.bicycle_context_audit)]}) + "\n")

    worker._expire_guard_crossings(_Counter(), trace)

    rows = [json.loads(line) for line in trace.getvalue().splitlines()]
    assert len(rows) == 2
    assert rows[0]["bicycle_xframe_decision_audit"][0]["commit_status"] == "pending"
    assert rows[1]["audit_only"] is True
    assert rows[1]["frame_index"] == 522
    assert rows[1]["source_time_seconds"] == 20.84
    assert rows[1]["bicycle_xframe_decision_audit"][0]["commit_status"] == "expired"
    assert "detections" not in rows[1] and "crossing_events" not in rows[1]
    assert worker.state.human_guard_pending_crossings == 0
    assert worker.state.human_guard_pending_drops == 1
    assert worker.state.bicycle_context_rescues == 0
    assert worker._event_dispatcher.payloads == []


def test_v0554_eof_without_context_audit_does_not_write_an_analyzed_frame() -> None:
    import io

    worker = _worker()
    pending = _pending()
    worker._pending_guard_crossings[pending.track_id] = pending
    trace = io.StringIO()

    worker._expire_guard_crossings(_Counter(), trace)
    worker._expire_guard_crossings(_Counter(), trace)

    assert trace.getvalue() == ""
    assert worker.state.human_guard_pending_drops == 1
    assert worker.state.total_count == 0


def test_v0554_eof_trace_io_failure_still_revokes_every_pending_passage() -> None:
    worker = _worker()
    _enable_context_commit(worker)
    for track_id in (77, 78):
        pending = _pending()
        pending.track_id = track_id
        pending.bicycle_context_audit = {
            "kind": "bicycle_context", "track_id": track_id, "frame_index": 522,
            "decision_accepted": True, "commit_status": "pending",
        }
        worker._pending_guard_crossings[track_id] = pending

    class BrokenTrace:
        def write(self, _value):
            raise OSError("trace storage unavailable")

    counter = _Counter()
    worker._expire_guard_crossings(counter, BrokenTrace())

    assert counter.revoked == [(77, "in"), (78, "in")]
    assert worker.state.human_guard_pending_drops == 2
    assert worker._pending_guard_crossings == {}
    assert worker.state.total_count == 0
    assert worker._event_dispatcher.payloads == []
    assert worker.state.last_error == "Benchmark trace shutdown failed: trace storage unavailable"


def _execute_guard_frame(worker, frame_index, *, active=True):
    """Execute actual per-frame expiry and tracked follow-up in source order.

    Compiling these source blocks avoids importing inference/HTTP dependencies,
    while retaining the ordering that previously let a visible track commit at
    the very same deadline that expired an absent track.
    """
    import ast
    from pathlib import Path
    from app.counting import signed_distance

    source_path = Path(__file__).resolve().parents[1] / "app/worker.py"
    module = ast.parse(source_path.read_text(encoding="utf-8"))
    cls = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "PipelineWorker")
    run = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "run")
    track_loop = next(
        node for node in ast.walk(run) if isinstance(node, ast.For)
        and isinstance(node.target, ast.Name) and node.target.id == "item_index"
    )

    def assigned_name(node, name):
        return any(
            isinstance(item, ast.Name) and item.id == name
            for target in getattr(node, "targets", ()) for item in ast.walk(target)
        )

    expiry_assignment = next(node for node in ast.walk(run) if assigned_name(node, "expired_guard_crossings"))
    expiry_loop = next(
        node for node in ast.walk(run) if isinstance(node, ast.For)
        and isinstance(node.iter, ast.Name) and node.iter.id == "expired_guard_crossings"
    )
    first_guard_node = min(
        index for index, node in enumerate(track_loop.body)
        if assigned_name(node, "buffered") or assigned_name(node, "anchor_signed")
    )
    last_guard_node = next(index for index, node in enumerate(track_loop.body) if assigned_name(node, "xframe_candidate"))
    guard_loop = ast.For(
        target=ast.Name(id="_active_track", ctx=ast.Store()),
        iter=ast.Name(id="_active_tracks", ctx=ast.Load()),
        body=track_loop.body[first_guard_node:last_guard_node], orelse=[],
    )
    ast.copy_location(guard_loop, track_loop.body[first_guard_node])
    code = compile(ast.fix_missing_locations(ast.Module(
        body=sorted([expiry_assignment, expiry_loop, guard_loop], key=lambda node: node.lineno), type_ignores=[],
    )), str(source_path), "exec")
    calls = []
    worker._observe_human_guard = lambda *_args, **_kwargs: calls.append(frame_index) or (worker._frame_guard_action, None)
    worker._draw_detection = lambda *_args: None
    worker._human_guard_policy = SimpleNamespace(
        status=lambda _tid: "pending" if _tid in worker._pending_guard_crossings else "keep",
        is_rider=lambda _tid: True,
    )
    env = {
        "self": worker, "counter": _Counter(), "frame_index": frame_index,
        "track_id": 77, "confidence_f": .82, "display_label": "motorcycle",
        "analysis_frame": object(), "frame": object(), "rect": (40, 45, 60, 65), "anchor": (50, 65),
        "center": (50, 55), "class_certainty": .9, "raw_track_id": 77,
        "device": "cpu", "use_half": False, "velocity": (0, 2), "cv2": object(),
        "line_a": (10, 50), "line_b": (90, 50), "width": 100, "height": 100,
        "gate_trace_tracks": [], "signed_distance": signed_distance,
        "TWO_WHEEL_LABELS": {"bicycle", "motorcycle"},
        "is_person_like_two_wheel_box": lambda _rect: False,
        "_active_tracks": [77] if active else [],
    }
    exec(code, env)
    return calls, env["counter"], env["gate_trace_tracks"]


def _deadline_worker(*, action="rider"):
    worker = _worker()
    pending = _pending()
    pending.observed_frame_index = 522
    worker._pending_guard_crossings[77] = pending
    worker.human_guard_pending_max_frames = 12
    worker._frame_guard_action = action
    return worker


def test_v0556_visible_return_at_guard_deadline_expires_before_follow_up() -> None:
    worker = _deadline_worker()

    calls, counter, _ = _execute_guard_frame(worker, 534)

    assert calls == []
    assert counter.revoked == [(77, "in")]
    assert worker.state.human_guard_pending_drops == 1
    assert worker.state.total_count == 0
    assert worker._event_dispatcher.payloads == []


def test_v0556_visible_return_after_guard_deadline_cannot_resurrect_crossing() -> None:
    worker = _deadline_worker()

    calls, counter, _ = _execute_guard_frame(worker, 540)

    assert calls == []
    assert counter.revoked == [(77, "in")]
    assert worker.state.human_guard_pending_drops == 1
    assert worker.state.total_count == 0


def test_v0556_guard_deadline_uses_observed_frame_and_keeps_event_source_clock() -> None:
    worker = _deadline_worker()

    calls, counter, _ = _execute_guard_frame(worker, 533)

    assert calls == [533]
    assert counter.revoked == []
    assert worker.state.human_guard_pending_drops == 0
    assert worker.state.total_count == 1
    payload = worker._event_dispatcher.payloads[0]
    assert payload["source_frame_index"] == 519
    assert payload["source_time_seconds"] == 20.72


def test_v0556_missing_track_keeps_same_guard_expiry_rule() -> None:
    worker = _deadline_worker()

    calls, counter, tracks = _execute_guard_frame(worker, 534, active=False)

    assert calls == [] and tracks == []
    assert counter.revoked == [(77, "in")]
    assert worker.state.human_guard_pending_drops == 1
    assert worker.state.total_count == 0


def test_v0556_pending_guard_trace_keeps_visible_geometry_without_committing() -> None:
    worker = _deadline_worker(action="pending")

    calls, counter, tracks = _execute_guard_frame(worker, 523)

    assert calls == [523] and counter.revoked == []
    assert tracks == [{
        "track_id": 77, "label": "motorcycle", "anchor_signed": .15,
        "center_signed": .05, "human_guard_status": "pending",
    }]
    assert worker.state.total_count == 0
    assert worker._event_dispatcher.payloads == []
    assert 77 in worker._pending_guard_crossings


def test_v0557_neutral_verifier_cannot_commit_confirmed_pedestrian_crossing() -> None:
    """Execute the real crossing authorization branch without inference/HTTP."""
    import ast
    from pathlib import Path
    from app.human_guard import HumanGuardDecision, HumanGuardTrackPolicy

    worker = _worker()
    worker._human_guard_policy = HumanGuardTrackPolicy(required_strikes=2)
    worker._human_guard_policy.observe(77, HumanGuardDecision(reject=True), frame_index=100)
    worker._human_guard_policy.observe(77, HumanGuardDecision(reject=True), frame_index=101)
    worker._human_guard_last_check = {}
    worker._human_guard_last_observation = {}
    worker._human_rider_tracks_seen = set()
    worker._verify_human_candidate = lambda *_args, **_kwargs: HumanGuardDecision(reject=False)
    worker._draw_detection = lambda *_args: None
    source_path = Path(__file__).resolve().parents[1] / "app/worker.py"
    module = ast.parse(source_path.read_text(encoding="utf-8"))
    cls = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "PipelineWorker")
    run = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "run")
    crossing = next(
        node for node in ast.walk(run) if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name) and node.test.id == "direction"
    )
    guard = next(
        node for node in crossing.body if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name) and node.test.left.id == "event_label"
        and isinstance(node.test.ops[0], ast.In)
    )
    record = next(
        node for node in crossing.body if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "_record_committed_crossing"
    )
    append = next(
        node for node in crossing.body if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
        and isinstance(node.value.func.value, ast.Name)
        and node.value.func.value.id == "pending_crossing_events"
    )
    loop = ast.For(
        target=ast.Name(id="_crossing", ctx=ast.Store()),
        iter=ast.List(elts=[ast.Constant(value=77)], ctx=ast.Load()),
        body=[guard, record, append], orelse=[],
    )
    code = compile(ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[])), str(source_path), "exec")
    counter = _Counter()
    env = {
        "self": worker, "counter": counter, "track_id": 77, "frame_index": 102,
        "event_label": "motorcycle", "event_confidence": .82, "direction": "in",
        "analysis_frame": object(), "rect": (40, 45, 60, 65), "frame": object(),
        "device": "cpu", "use_half": False, "velocity": (0, 2), "cv2": object(),
        "anchor": (50, 65), "class_certainty": .9, "raw_track_id": 77,
        "context_trace": {}, "span_passage_state": None, "heavy_passage_state": None,
        "two_wheel_passage_state": None, "heavy_rescue_was_recorded": False,
        "gate_trace_track": {}, "TWO_WHEEL_LABELS": {"bicycle", "motorcycle"},
        "pending_crossing_events": [], "crossing_method": "direct",
        "event_frame_index": 102, "source_time_seconds": 4.04, "crossing_x": .5, "crossing_y": .5,
    }

    exec(code, env)

    assert counter.revoked == [(77, "in")]
    assert worker._human_guard_policy.status(77) == "rejected"
    assert env["gate_trace_track"]["human_guard_status"] == "rejected"
    assert worker.state.total_count == 0
    assert env["pending_crossing_events"] == []
    assert worker._event_dispatcher.payloads == []


def _capture_crossing_trace_counter(worker):
    """Capture actual per-frame initialization and evaluate the actual trace field."""
    import ast
    from pathlib import Path

    source_path = Path(__file__).resolve().parents[1] / "app/worker.py"
    module = ast.parse(source_path.read_text(encoding="utf-8"))
    cls = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "PipelineWorker")
    run = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "run")
    trace = next(
        node for node in ast.walk(run) if isinstance(node, ast.Dict)
        and any(isinstance(key, ast.Constant) and key.value == "crossing_events" for key in node.keys)
    )
    expression = next(
        value for key, value in zip(trace.keys, trace.values)
        if isinstance(key, ast.Constant) and key.value == "crossing_events"
    )
    track_loop = next(
        node for node in ast.walk(run) if isinstance(node, ast.For)
        and isinstance(node.target, ast.Name) and node.target.id == "item_index"
    )
    captured_names = {
        node.id for node in ast.walk(expression) if isinstance(node, ast.Name)
    } - {"self", "len", "max", "pending_crossing_events"}
    capture = [
        node for node in ast.walk(run) if isinstance(node, ast.Assign)
        and node.lineno < track_loop.lineno
        and any(isinstance(target, ast.Name) and target.id in captured_names for target in node.targets)
    ]
    env = {"self": worker}
    exec(compile(ast.fix_missing_locations(ast.Module(
        body=sorted(capture, key=lambda node: node.lineno), type_ignores=[],
    )), str(source_path), "exec"), env)
    code = compile(ast.Expression(body=expression), str(source_path), "eval")

    def count(events):
        env["pending_crossing_events"] = events
        return eval(code, env)

    return count


def test_v0557_trace_counts_deferred_and_ordinary_commits_once_per_frame() -> None:
    worker = _worker()
    pending = _pending()
    pending.observed_frame_index = 522
    worker._pending_guard_crossings[pending.track_id] = pending
    count_this_frame = _capture_crossing_trace_counter(worker)
    ordinary_events = []
    for track_id in (78, 79):
        worker._record_committed_crossing("motorcycle", "out", "direct")
        ordinary_events.append((track_id, "motorcycle", "out"))

    worker._commit_guard_crossing(object(), pending)

    assert worker.state.total_count == 3
    assert len(worker._event_dispatcher.payloads) == 1
    assert worker._event_dispatcher.payloads[0]["source_frame_index"] == 519
    assert worker._event_dispatcher.payloads[0]["source_time_seconds"] == 20.72
    assert worker._event_dispatcher.payloads[0]["snapshot_path"] == "frame_522.jpg"
    assert count_this_frame(ordinary_events) == 3
    # A subsequent ordinary frame must not count the prior deferred event again.
    count_next_frame = _capture_crossing_trace_counter(worker)
    worker._record_committed_crossing("motorcycle", "out", "direct")
    assert count_next_frame([(80, "motorcycle", "out")]) == 1


def _snapshot_saver_from_source():
    import ast
    from datetime import datetime, timezone
    from pathlib import Path

    source_path = Path(__file__).resolve().parents[1] / "app/worker.py"
    module = ast.parse(source_path.read_text(encoding="utf-8"))
    cls = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "PipelineWorker")
    save = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "_save_crossing_snapshot")
    env = {"Path": Path, "datetime": datetime, "timezone": timezone}
    exec(compile(ast.Module(body=[save], type_ignores=[]), str(source_path), "exec"), env)
    return env["_save_crossing_snapshot"]


def test_v0557_snapshot_filename_distinguishes_sessions_on_same_camera(tmp_path) -> None:
    """Verify real naming/path logic; the writer only stands in for JPEG encoding."""
    from pathlib import Path

    save = _snapshot_saver_from_source()
    worker = _worker()
    worker.snapshot_root = tmp_path
    written = []

    def write(path, _frame, _options):
        written.append(Path(path))
        Path(path).write_bytes(b"snapshot writer placeholder")
        return True

    writer = SimpleNamespace(imwrite=write, IMWRITE_JPEG_QUALITY=1)
    first = save(worker, writer, object(), 522)
    worker.payload.session_id = 3
    second = save(worker, writer, object(), 522)

    assert first is not None and second is not None
    assert Path(first).parent == Path(second).parent == Path("camera_1")
    assert "session_2_" in Path(first).name
    assert "session_3_" in Path(second).name
    assert first != second
    assert (tmp_path / first).is_file() and (tmp_path / second).is_file()
    assert written == [tmp_path / first, tmp_path / second]


def test_v0557_failed_snapshot_writer_does_not_return_nonexistent_event_path(tmp_path) -> None:
    save = _snapshot_saver_from_source()
    worker = _worker()
    worker.snapshot_root = tmp_path
    calls = []
    writer = SimpleNamespace(
        imwrite=lambda path, _frame, _options: calls.append(path) or False,
        IMWRITE_JPEG_QUALITY=1,
    )

    snapshot = save(worker, writer, object(), 522)

    assert len(calls) == 1
    assert snapshot is None
    assert list(tmp_path.rglob("*.jpg")) == []
