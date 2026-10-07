from types import SimpleNamespace

from app.worker import PipelineWorker, _PendingGuardCrossing


def _v0563_receipt():
    return {
        "kind": "event_delivery", "audit_only": True,
        "camera_id": 1, "session_id": 2, "tracking_id": -1,
        "vehicle_type": "motorcycle", "direction": "out",
        "source_frame_index": 1737, "source_time_seconds": 69.4566,
        "stage": "backend_acknowledged", "outcome": "deduplicated",
        "attempts": 1, "backend_event_id": 12,
        "dedup_reason": "secondary-reverse-shadow",
    }


def _v0563_execute_finalizer(worker, writer):
    ast, source_path, run = _run_method_ast()
    outer_try = next(node for node in run.body if isinstance(node, ast.Try))
    namespace = {"self": worker, "counter": None, "trace_file": writer, "cap": None}
    exec(compile(ast.fix_missing_locations(ast.Module(body=outer_try.finalbody, type_ignores=[])),
                 str(source_path), "exec"), namespace)


def test_v0563_trace_writer_records_receipts_without_inventing_observation_clock() -> None:
    import io
    import json
    worker = _worker()
    pending = [_v0563_receipt()]

    def drain():
        values = list(pending)
        pending.clear()
        return values

    worker._event_dispatcher = SimpleNamespace(drain_delivery_audits=drain)
    writer = io.StringIO()
    observation = {"frame_index": 1760, "source_time_seconds": 70.36, "crossing_events": 0}
    assert worker._write_benchmark_trace(writer, observation) is writer
    assert worker._write_benchmark_trace(writer, observation) is writer
    rows = [json.loads(line) for line in writer.getvalue().splitlines()]
    assert rows == [_v0563_receipt(), observation, observation]
    assert rows[0]["source_time_seconds"] == 69.4566 and "frame_index" not in rows[0]
    assert worker.state.total_count == 0 and worker.state.last_error is None


def test_v0563_eof_trace_closes_after_late_ack_and_before_session_release() -> None:
    import io
    import json
    worker = _worker()
    worker.state.status = "completed"
    writer = io.StringIO()
    pending, calls, published = [], [], []

    def flush(*, timeout):
        assert timeout is None and worker.state.status == "draining"
        assert not writer.closed
        calls.append("drain")
        pending.append(_v0563_receipt())
        return True

    def drain():
        values = list(pending)
        pending.clear()
        return values

    def close(trace, *, publish):
        assert worker.state.status == "draining" and publish
        published.extend(json.loads(line) for line in trace.getvalue().splitlines())
        trace.close()
        calls.append("close")

    worker._event_dispatcher = SimpleNamespace(stop_and_flush=flush, drain_delivery_audits=drain,
                                               delivery_audit_dropped=3)
    worker._close_and_publish_benchmark_trace = close
    worker._notify_finished = lambda: calls.append(("finish", worker.state.status))
    worker.on_finished = lambda camera_id: calls.append(("release", camera_id))
    _v0563_execute_finalizer(worker, writer)
    assert calls == ["drain", "close", ("finish", "completed"), ("release", 1)]
    assert published[0] == _v0563_receipt()
    assert published[1] == {
        "kind": "delivery_summary", "audit_only": True, "camera_id": 1, "session_id": 2,
        "delivery_drain_complete": True, "delivery_audit_dropped": 3, "pending_events": 0,
    }
    assert writer.closed and not pending


def test_v0563_failed_drain_footer_preserves_error_and_unfinished_delivery() -> None:
    import io
    import json
    worker = _worker()
    worker.state.status = "completed"
    worker.state.pending_events = 1
    writer = io.StringIO()
    rows, finishes = [], []
    worker._event_dispatcher = SimpleNamespace(stop_and_flush=lambda **_kwargs: False,
                                               drain_delivery_audits=lambda: [], delivery_audit_dropped=0)

    def close(trace, **_kwargs):
        rows.extend(json.loads(line) for line in trace.getvalue().splitlines())
        trace.close()

    worker._close_and_publish_benchmark_trace = close
    worker._notify_finished = lambda: finishes.append(worker.state.status)
    worker.on_finished = lambda _camera_id: None
    _v0563_execute_finalizer(worker, writer)
    assert finishes == ["error"] and worker.state.status == "error"
    assert "unfinished accepted events" in worker.state.last_error
    assert len(rows) == 1 and rows[0]["delivery_drain_complete"] is False
    assert rows[0]["pending_events"] == 1 and rows[0]["delivery_audit_dropped"] == 0


def test_v0563_receipt_write_failure_disables_trace_without_changing_delivery_state() -> None:
    worker = _worker()
    worker.state.last_error = "existing delivery error"
    worker._event_dispatcher = SimpleNamespace(drain_delivery_audits=lambda: [_v0563_receipt()])
    closed = []

    def fail(_value):
        raise OSError("trace storage full")

    writer = SimpleNamespace(write=fail, close=lambda: closed.append(True))
    assert worker._write_benchmark_trace(writer, {"frame_index": 1760}) is None
    assert closed == [True] and worker.state.total_count == 0
    assert worker.state.last_error == "existing delivery error"
    assert worker.state.benchmark_trace_warning == "Benchmark trace write failed: trace storage full"


def test_v0563_actual_dispatcher_receipt_reaches_worker_trace_and_diagnosis(tmp_path, monkeypatch) -> None:
    from app import async_tasks, benchmark_trace
    worker = _worker()
    for name in ("pending_events", "delivery_failures", "delivered_events", "persisted_events", "deduplicated_events"):
        setattr(worker.state, name, 0)
    sent = []

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, _url, *, json):
            sent.append(dict(json))
            return SimpleNamespace(raise_for_status=lambda: None,
                headers={"X-TrafficAI-Deduplicated": "0"}, json=lambda: {"id": 12})

    monkeypatch.setattr(async_tasks.httpx, "Client", lambda **_kwargs: Client())
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path)
    dispatcher = async_tasks.EventDispatcher("https://local-test.invalid/internal", "test-token", worker.state)
    worker._event_dispatcher = dispatcher
    payload = worker._event_payload(-1, "motorcycle", "out", .82, "private.jpg", 1737, 69.4566,
                                    "interpolated", .5, .4)
    dispatcher.submit(payload)
    dispatcher.start()
    assert dispatcher.stop_and_flush(timeout=None) is True
    with benchmark_trace.trace_path(2).open("w", encoding="utf-8") as writer:
        worker._write_benchmark_trace(writer, {"kind": "delivery_summary", "audit_only": True,
            "camera_id": 1, "session_id": 2, "delivery_drain_complete": True,
            "delivery_audit_dropped": 0, "pending_events": 0})
    result = benchmark_trace.diagnose_trace(2, [69.457], tracking_ids=[-1])["items"][0]
    assert result["reason"] == "crossing_delivery_observed"
    assert result["diagnosis_scope"]["reason"] == "matched_track_delivery"
    receipt = result["event_delivery_audit"]["records"][0]
    assert receipt["tracking_id"] == -1 and receipt["source_time_seconds"] == 69.4566
    assert receipt["outcome"] == "created" and receipt["backend_event_id"] == 12
    assert "snapshot_path" not in receipt and "test-token" not in benchmark_trace.trace_path(2).read_text()
    assert result["diagnosis_scope"]["counters"] == "no_trace_window" and result["max_det"] == 0
    assert sent == [payload] and worker.state.persisted_events == 1


class _Dispatcher:
    def __init__(self) -> None:
        self.payloads = []

    def submit(self, payload) -> None:
        self.payloads.append(payload)

    def stop_and_flush(self, *, timeout=None) -> bool:
        return True


class _Counter:
    def __init__(self) -> None:
        self.revoked = []

    def revoke_last_crossing(self, track_id: int, direction: str) -> None:
        self.revoked.append((track_id, direction))


def _worker() -> PipelineWorker:
    worker = PipelineWorker.__new__(PipelineWorker)
    worker.payload = SimpleNamespace(camera_id=1, session_id=2, model_id=3)
    worker.state = SimpleNamespace(
        status="running",
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
        benchmark_trace_warning=None,
        benchmark_trace_snapshot_path=None,
        benchmark_trace_snapshot_bytes=0,
        benchmark_trace_snapshot_method=None,
        last_error=None,
    )
    worker._committed_in_count = 0
    worker._committed_out_count = 0
    worker._pending_guard_crossings = {}
    worker._heavy_center_rescue_tracks = set()
    worker._class_refine_overrides = {}
    worker._class_refine_decision_audit_this_frame = []
    worker._guard_crossing_proposals_this_frame = []
    worker._event_dispatcher = _Dispatcher()
    worker._jpeg_encoder = SimpleNamespace(is_alive=lambda: False)
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
    assert worker.state.benchmark_trace_warning == "Benchmark trace shutdown failed: trace storage unavailable"
    assert worker.state.last_error is None


def _execute_guard_frame(worker, frame_index, *, active=True, velocity=(0, 2), anchor_velocity=(0, 2), stitched=False, raw_track_id=77):
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
        "current_label": "motorcycle", "stable_label": "motorcycle", "class_hits": 4,
        "analysis_frame": object(), "frame": object(), "rect": (40, 45, 60, 65), "anchor": (50, 65),
        "center": (50, 55), "class_certainty": .9, "raw_track_id": raw_track_id,
        "device": "cpu", "use_half": False, "velocity": velocity,
        "anchor_velocity": anchor_velocity, "stitched": stitched, "cv2": object(),
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
        "primary_label": "motorcycle", "primary_confidence": .82,
        "stable_label": "motorcycle", "class_certainty": .9, "class_hits": 4,
        "class_override": None, "truck_semantic_lock": None,
        "center_signed": .05, "human_guard_status": "pending",
        "raw_track_id": 77, "stitched": False, "rect": [40.0, 45.0, 60.0, 65.0],
        "anchor": [50.0, 65.0], "center": [50.0, 55.0],
        "measured_velocity": [0.0, 2.0], "anchor_velocity": [0.0, 2.0],
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
    clock_audit = next(
        node for node in crossing.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
            and target.value.id == "gate_trace_track" and isinstance(target.slice, ast.Constant)
            and target.slice.value == "crossing_clock_audit" for target in node.targets)
    )
    loop = ast.For(
        target=ast.Name(id="_crossing", ctx=ast.Store()),
        iter=ast.List(elts=[ast.Constant(value=77)], ctx=ast.Load()),
        body=[clock_audit, guard, record, append], orelse=[],
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
        "crossing_frame_float": 101.7, "span_clock_reconciliation_frame": None,
        "selected_crossing_frame": 102.0,
    }

    exec(code, env)

    assert counter.revoked == [(77, "in")]
    assert worker._human_guard_policy.status(77) == "rejected"
    assert env["gate_trace_track"]["human_guard_status"] == "rejected"
    assert env["gate_trace_track"]["crossing_clock_audit"]["producer_decision"] == "human_guard_rejected"
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


def _run_method_ast():
    import ast
    from pathlib import Path

    source_path = Path(__file__).resolve().parents[1] / "app/worker.py"
    module = ast.parse(source_path.read_text(encoding="utf-8"))
    cls = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "PipelineWorker")
    run = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "run")
    return ast, source_path, run


def _execute_trace_dispatch(worker, writer):
    """Execute actual trace and ordinary dispatch branches in production order."""
    import json

    ast, source_path, run = _run_method_ast()
    trace = next(node for node in ast.walk(run) if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "trace_file"
        and any(isinstance(child, ast.Dict) and any(isinstance(key, ast.Constant)
            and key.value == "crossing_events" for key in child.keys) for child in ast.walk(node)))
    dispatch = next(node for node in ast.walk(run) if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name) and node.test.id == "pending_crossing_events")
    for node in ast.walk(trace):
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name) and node.value.value.id == "self"
            and node.value.attr == "state" and not hasattr(worker.state, node.attr)):
            setattr(worker.state, node.attr, 0)
    worker.state.source_fps = 25.0
    worker._bicycle_xframe_audit_this_frame = []
    counter_fields = {
        node.attr: 0 for node in ast.walk(trace)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
        and node.value.id == "counter"
    }
    env = {
        "self": worker, "trace_file": writer, "frame_index": 522,
        "counter": SimpleNamespace(**counter_fields), "anchor_span_rescuer": SimpleNamespace(approach_span_candidates=0, approach_span_rescues=0),
        "frame_start_deferred_commits": 0, "gate_trace_tracks": [], "json": json,
        "pending_crossing_events": [(77, "motorcycle", "in", .82, 519, 20.72, "direct", .51, .62)],
        "cv2": object(), "frame": object(),
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[trace, dispatch], type_ignores=[])), str(source_path), "exec"), env)
    return env


def test_v0558_trace_write_failure_still_dispatches_original_crossing_once() -> None:
    worker = _worker()
    worker.state.last_error = "existing inference error"

    class BrokenTrace:
        closed = False

        def write(self, _value):
            raise OSError("No space left on device")

        def close(self):
            self.closed = True

    writer = BrokenTrace()

    env = _execute_trace_dispatch(worker, writer)

    assert env["trace_file"] is None
    assert writer.closed
    assert worker.state.last_error == "existing inference error"
    assert worker.state.benchmark_trace_warning == "Benchmark trace write failed: No space left on device"
    assert len(worker._event_dispatcher.payloads) == 1
    event = worker._event_dispatcher.payloads[0]
    assert event["tracking_id"] == 77 and event["direction"] == "in"
    assert event["source_frame_index"] == 519 and event["source_time_seconds"] == 20.72
    assert event["crossing_x"] == .51 and event["crossing_y"] == .62


def test_v0558_trace_write_close_failure_cannot_interrupt_event_dispatch() -> None:
    worker = _worker()

    class BrokenTrace:
        def write(self, _value):
            raise OSError("trace write unavailable")

        def close(self):
            raise OSError("trace flush unavailable")

    env = _execute_trace_dispatch(worker, BrokenTrace())

    assert env["trace_file"] is None
    assert worker.state.benchmark_trace_snapshot_path is None
    assert worker.state.last_error is None
    assert len(worker._event_dispatcher.payloads) == 1


def test_v0558_healthy_trace_keeps_source_clock_and_session_identity() -> None:
    import io
    import json

    worker = _worker()
    writer = io.StringIO()
    env = _execute_trace_dispatch(worker, writer)
    row = json.loads(writer.getvalue())

    assert env["trace_file"] is writer and not writer.closed
    assert row["camera_id"] == 1 and row["session_id"] == 2
    assert row["frame_index"] == 522 and row["source_time_seconds"] == 20.84
    assert len(worker._event_dispatcher.payloads) == 1
    assert worker.state.benchmark_trace_warning is None


def test_v0562_frame_trace_identifies_proposal_without_claiming_persistence() -> None:
    import io
    import json

    worker = _worker()
    writer = io.StringIO()
    _execute_trace_dispatch(worker, writer)
    row = json.loads(writer.getvalue())
    assert len(row["crossing_proposals"]) == row["crossing_events"] == 1
    proposal = row["crossing_proposals"][0]
    assert proposal["stage"] == "committed_before_submit"
    assert proposal["observed_frame_index"] == 522
    assert proposal["source_frame_index"] == 519
    assert proposal["source_time_seconds"] == 20.72
    payload = worker._event_dispatcher.payloads[0]
    for key in ("tracking_id", "vehicle_type", "direction", "confidence", "source_frame_index",
                "source_time_seconds", "crossing_method", "crossing_x", "crossing_y"):
        assert proposal[key] == payload[key]
    assert "snapshot_path" not in proposal and "model_id" not in proposal
    assert "persisted" not in proposal and worker.state.benchmark_trace_warning is None


def test_v0562_guard_commit_audit_keeps_original_clock_and_producer_stage() -> None:
    worker = _worker()
    pending = _pending()
    pending.observed_frame_index = 522
    worker._pending_guard_crossings[77] = pending
    worker._commit_guard_crossing(object(), pending)
    audit = worker._guard_crossing_proposals_this_frame[0]
    assert audit["stage"] == "submitted_after_guard"
    assert audit["observed_frame_index"] == 522
    assert audit["source_frame_index"] == 519 and audit["source_time_seconds"] == 20.72
    assert audit["tracking_id"] == 77 and audit["direction"] == "in"
    assert audit["crossing_x"] == .51 and audit["crossing_y"] == .62
    assert len(worker._event_dispatcher.payloads) == 1 and worker.state.total_count == 1


def test_v0562_failed_guard_admission_never_claims_submitted_event() -> None:
    import pytest

    worker = _worker()
    pending = _pending()
    worker._pending_guard_crossings[77] = pending

    def closed_dispatcher(_payload):
        raise RuntimeError("Dispatcher admission closed")

    worker._event_dispatcher.submit = closed_dispatcher
    with pytest.raises(RuntimeError, match="admission closed"):
        worker._commit_guard_crossing(object(), pending)
    assert worker._guard_crossing_proposals_this_frame == []
    assert worker.state.human_guard_deferred_commits == 0
    assert worker._event_dispatcher.payloads == []


def test_v0562_proposal_metadata_preserves_signed_identity_without_side_effects() -> None:
    worker = _worker()
    audit = worker._crossing_proposal_metadata(
        -3, "car", "out", .9, 16050, 641.9812345, "direct", .51234567, .61234567,
        stage="committed_before_submit", observed_frame_index=16051,
    )
    assert audit["tracking_id"] == -3 and audit["vehicle_type"] == "car"
    assert audit["source_time_seconds"] == 641.9812
    assert audit["crossing_x"] == .512346 and audit["crossing_y"] == .612346
    assert worker.state.total_count == 0 and worker._event_dispatcher.payloads == []
    assert "snapshot_path" not in audit and "model_id" not in audit


def _execute_trace_startup(worker, path):
    ast, source_path, run = _run_method_ast()
    startup = next(node for node in ast.walk(run) if isinstance(node, ast.If)
        and any(isinstance(child, ast.Assign) and any(isinstance(target, ast.Name)
            and target.id == "path" for target in child.targets) for child in ast.walk(node))
        and any(isinstance(child, ast.Attribute) and child.attr == "benchmark_trace_enabled" for child in ast.walk(node)))
    warming = next(node for node in ast.walk(run) if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant) and node.value.value == "warming")
    worker.payload.source_type = "video"
    worker.benchmark_trace_enabled = True
    worker.state.source_fps = 25.0
    worker.state.frame_policy = "all-frames"
    env = {
        "self": worker, "trace_file": None, "source_frame_count": 23650,
        "trace_path": lambda _session_id: path,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[startup, warming], type_ignores=[])), str(source_path), "exec"), env)
    return env


def test_v0558_trace_open_failure_allows_video_warmup() -> None:
    worker = _worker()

    def failed_open(*_args, **_kwargs):
        raise OSError("trace permission denied")

    path = SimpleNamespace(parent=SimpleNamespace(mkdir=lambda **_kwargs: None), open=failed_open)

    env = _execute_trace_startup(worker, path)

    assert env["trace_file"] is None
    assert worker.state.status == "warming"
    assert worker.state.last_error is None
    assert worker.state.benchmark_trace_warning == "Benchmark trace open failed: trace permission denied"


def test_v0558_session_trace_header_contains_no_synthetic_observation_or_secrets() -> None:
    import io
    import json

    worker = _worker()
    worker.payload.source_url = "rtsp://user:secret@example/camera?token=secret"
    writer = io.StringIO()
    path = SimpleNamespace(parent=SimpleNamespace(mkdir=lambda **_kwargs: None), open=lambda *_args, **_kwargs: writer)

    env = _execute_trace_startup(worker, path)
    header = json.loads(writer.getvalue())

    assert env["trace_file"] is writer
    assert header == {
        "kind": "session_metadata", "audit_only": True, "camera_id": 1, "session_id": 2,
        "source_fps": 25.0, "source_frame_count": 23650, "frame_policy": "all-frames",
    }
    assert "source_time_seconds" not in header and "frame_index" not in header
    assert "secret" not in writer.getvalue()


def test_v0559_geometry_metadata_records_canonical_line_road_and_actual_dimensions() -> None:
    from app.counting import CountingLine, LineCrossingCounter, RoadZone
    worker = _worker()
    counter = LineCrossingCounter(CountingLine(0.9, 0.5, 0.1, 0.3), road_zone=RoadZone())
    metadata = worker._benchmark_geometry_metadata(counter, 1440, 810, (1080, 1920, 3))
    assert metadata["line"] == [[0.1, 0.3], [0.9, 0.5]]
    assert metadata["road_zone"] == counter.road_zone.normalized_points()
    assert metadata["frame_width"] == 1440 and metadata["frame_height"] == 810
    assert metadata["source_frame_width"] == 1920 and metadata["source_frame_height"] == 1080
    assert metadata["camera_id"] == 1 and metadata["session_id"] == 2
    assert metadata["audit_only"] is True
    assert "source_time_seconds" not in metadata and "frame_index" not in metadata


def test_v0559_compression_failure_preserves_raw_camera_publication(tmp_path, monkeypatch) -> None:
    import app.worker as worker_module
    worker = _worker()
    worker.snapshot_root = tmp_path
    monkeypatch.setattr(worker_module, "publish_closed_trace", lambda *_args, **_kwargs: {
        "path":"camera_1/session_2_benchmark-trace.jsonl", "bytes":41, "method":"hardlink"})

    def fail_compression(_session_id):
        raise OSError("compression storage full")

    monkeypatch.setattr(worker_module, "publish_compressed_trace", fail_compression)
    worker._close_and_publish_benchmark_trace(SimpleNamespace(close=lambda: None))
    assert worker.state.benchmark_trace_snapshot_path == "camera_1/session_2_benchmark-trace.jsonl"
    assert worker.state.benchmark_trace_snapshot_bytes == 41
    assert worker.state.benchmark_trace_warning == "Benchmark trace compression failed: compression storage full"
    assert worker.state.last_error is None


def test_v0558_camera_trace_publication_waits_for_successful_close(tmp_path, monkeypatch) -> None:
    import app.worker as worker_module

    worker = _worker()
    worker.snapshot_root = tmp_path
    calls = []
    writer = SimpleNamespace(closed=False)
    writer.close = lambda: setattr(writer, "closed", True)

    def publish(camera_id, session_id, *, snapshot_root):
        assert writer.closed
        calls.append((camera_id, session_id, snapshot_root))
        return {"path": "camera_1/session_2_benchmark-trace.jsonl", "bytes": 41, "method": "hardlink"}

    monkeypatch.setattr(worker_module, "publish_closed_trace", publish)

    worker._close_and_publish_benchmark_trace(writer)

    assert calls == [(1, 2, tmp_path)]
    assert worker.state.benchmark_trace_snapshot_path == "camera_1/session_2_benchmark-trace.jsonl"
    assert worker.state.benchmark_trace_snapshot_bytes == 41
    assert worker.state.benchmark_trace_snapshot_method == "hardlink"


def test_v0558_close_failure_never_publishes_camera_trace(tmp_path, monkeypatch) -> None:
    import app.worker as worker_module

    worker = _worker()
    worker.snapshot_root = tmp_path
    worker.state.last_error = "existing delivery error"
    calls = []
    monkeypatch.setattr(worker_module, "publish_closed_trace", lambda *_args, **_kwargs: calls.append(1))

    def failed_close():
        raise OSError("trace flush unavailable")

    worker._close_and_publish_benchmark_trace(SimpleNamespace(close=failed_close))

    assert calls == [] and worker.state.benchmark_trace_snapshot_path is None
    assert worker.state.last_error == "existing delivery error"
    assert worker.state.benchmark_trace_warning == "Benchmark trace close failed: trace flush unavailable"


def test_v0558_eof_audit_failure_disables_artifact_publication(tmp_path, monkeypatch) -> None:
    import app.worker as worker_module

    worker = _worker()
    _enable_context_commit(worker)
    worker.snapshot_root = tmp_path
    pending = _pending()
    pending.bicycle_context_audit = {"kind": "bicycle_context", "track_id": 77, "frame_index": 522, "commit_status": "pending"}
    worker._pending_guard_crossings[77] = pending
    calls = []
    monkeypatch.setattr(worker_module, "publish_closed_trace", lambda *_args, **_kwargs: calls.append(1))

    class BrokenTrace:
        closed = False

        def write(self, _value):
            raise OSError("trace storage unavailable")

        def close(self):
            self.closed = True

    writer = BrokenTrace()
    ast, source_path, run = _run_method_ast()
    outer_try = next(node for node in run.body if isinstance(node, ast.Try))
    close = next(node for node in outer_try.finalbody if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "_close_and_publish_benchmark_trace")
    prefix = outer_try.finalbody[:outer_try.finalbody.index(close) + 1]
    counter = _Counter()
    exec(compile(ast.fix_missing_locations(ast.Module(body=prefix, type_ignores=[])), str(source_path), "exec"),
        {"self": worker, "counter": counter, "trace_file": writer, "cap": None})

    assert writer.closed and calls == []
    assert worker._pending_guard_crossings == {} and counter.revoked == [(77, "in")]
    assert worker.state.total_count == 0


def test_v0558_gate_trace_distinguishes_bbox_geometry_and_heading_evidence() -> None:
    worker = _deadline_worker(action="pending")

    _, _, tracks = _execute_guard_frame(
        worker, 523, velocity=(.01, -.04), anchor_velocity=(0, 2), stitched=True, raw_track_id=88,
    )

    track = tracks[0]
    assert track["track_id"] == 77 and track["raw_track_id"] == 88 and track["stitched"] is True
    assert track["rect"] == [40, 45, 60, 65] and track["anchor"] == [50, 65] and track["center"] == [50, 55]
    assert track["measured_velocity"] == [.01, -.04] and track["anchor_velocity"] == [0, 2]
    assert track["primary_label"] == track["stable_label"] == "motorcycle"
    assert track["primary_confidence"] == .82 and track["class_certainty"] == .9 and track["class_hits"] == 4
    assert track["class_override"] is None and track["truck_semantic_lock"] is None
    assert track["human_guard_status"] == "pending"
    assert worker.state.total_count == 0 and worker._event_dispatcher.payloads == []


def test_v0559_worker_drains_accepted_events_before_restoring_completed_status() -> None:
    worker = _worker()
    worker.state.status = "completed"
    calls = []

    def flush(*, timeout):
        calls.append((timeout, worker.state.status))
        worker.state.persisted_events = 1
        return True

    worker._event_dispatcher = SimpleNamespace(stop_and_flush=flush)
    worker._drain_events_before_finish()

    assert calls == [(None, "draining")]
    assert worker.state.status == "completed" and worker.state.persisted_events == 1
    assert worker.state.last_error is None


def test_v0559_worker_drain_preserves_explicit_stopped_terminal_status() -> None:
    worker = _worker()
    worker.state.status = "stopped"
    worker._event_dispatcher = SimpleNamespace(stop_and_flush=lambda **_kwargs: True)

    worker._drain_events_before_finish()

    assert worker.state.status == "stopped" and worker.state.last_error is None


def test_v0559_worker_drain_marks_dead_dispatcher_unfinished_work_as_error() -> None:
    worker = _worker()
    worker.state.status = "completed"
    worker._event_dispatcher = SimpleNamespace(stop_and_flush=lambda **_kwargs: False)

    worker._drain_events_before_finish()

    assert worker.state.status == "error"
    assert worker.state.last_error == "Event dispatcher shutdown failed: Event dispatcher stopped with unfinished accepted events"


def test_v0559_worker_drain_keeps_original_fatal_error() -> None:
    worker = _worker()
    worker.state.status = "error"
    worker.state.last_error = "original inference failure"
    worker._event_dispatcher = SimpleNamespace(stop_and_flush=lambda **_kwargs: False)

    worker._drain_events_before_finish()

    assert worker.state.status == "error" and worker.state.last_error == "original inference failure"


def test_v0559_worker_drain_exception_is_reported_before_finish() -> None:
    worker = _worker()
    worker.state.status = "stopped"

    def flush(**_kwargs):
        raise RuntimeError("local shutdown failure")

    worker._event_dispatcher = SimpleNamespace(stop_and_flush=flush)
    worker._drain_events_before_finish()

    assert worker.state.status == "error"
    assert worker.state.last_error == "Event dispatcher shutdown failed: local shutdown failure"


def test_v0559_run_finishes_and_releases_camera_only_after_event_drain() -> None:
    worker = _worker()
    worker.state.status = "completed"
    calls = []

    def flush(*, timeout):
        assert timeout is None and worker.state.status == "draining"
        calls.append("drain")
        worker.state.persisted_events = 1
        return True

    worker._event_dispatcher = SimpleNamespace(stop_and_flush=flush)
    worker._notify_finished = lambda: calls.append(("finish", worker.state.status, worker.state.persisted_events))
    worker.on_finished = lambda camera_id: calls.append(("release", camera_id))
    ast, source_path, run = _run_method_ast()
    outer_try = next(node for node in run.body if isinstance(node, ast.Try))
    drain = next(node for node in outer_try.finalbody if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "_drain_events_before_finish")
    suffix = outer_try.finalbody[outer_try.finalbody.index(drain):]

    exec(compile(ast.fix_missing_locations(ast.Module(body=suffix, type_ignores=[])), str(source_path), "exec"),
        {"self": worker, "terminal_status": "completed", "trace_file": None, "trace_usable": True})

    assert calls == ["drain", ("finish", "completed", 1), ("release", 1)]


def test_v0559_run_enters_draining_before_optional_artifact_publication() -> None:
    worker = _worker()
    worker.state.status = "completed"
    calls = []
    worker._close_and_publish_benchmark_trace = lambda *_args, **_kwargs: calls.append(worker.state.status)
    ast, source_path, run = _run_method_ast()
    outer_try = next(node for node in run.body if isinstance(node, ast.Try))
    close = next(node for node in outer_try.finalbody if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "_close_and_publish_benchmark_trace")
    prefix = outer_try.finalbody[:outer_try.finalbody.index(close) + 1]

    env = {"self": worker, "counter": None, "trace_file": None, "cap": None}
    exec(compile(ast.fix_missing_locations(ast.Module(body=prefix, type_ignores=[])), str(source_path), "exec"), env)

    assert calls == ["draining"] and env["terminal_status"] == "completed"
    assert worker.state.status == "draining"


def test_v0559_worker_drain_restores_terminal_status_captured_before_artifacts() -> None:
    worker = _worker()
    worker.state.status = "draining"
    worker._event_dispatcher = SimpleNamespace(stop_and_flush=lambda **_kwargs: True)

    worker._drain_events_before_finish(terminal_status="completed")

    assert worker.state.status == "completed"


def _execute_registry_stop(state_status, *, alive):
    import ast
    from dataclasses import asdict, dataclass
    from pathlib import Path
    import threading

    source_path = Path(__file__).resolve().parents[1] / "app" / "runtime.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    registry_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "PipelineRegistry")
    stop = next(node for node in registry_class.body if isinstance(node, ast.FunctionDef) and node.name == "stop")
    code = compile(ast.fix_missing_locations(ast.Module(body=[stop], type_ignores=[])), str(source_path), "exec")
    namespace = {"asdict": asdict}
    exec(code, namespace)

    @dataclass
    class State:
        status: str
        pending_events: int = 1

    state, calls = State(state_status), []
    worker = SimpleNamespace(
        stop=lambda: calls.append("stop"),
        join=lambda **kwargs: calls.append(("join", kwargs["timeout"])),
        is_alive=lambda: alive,
    )
    registry = SimpleNamespace(_lock=threading.Lock(), _workers={1: worker}, _states={1: state})
    return namespace["stop"](registry, 1), state, calls


def test_v0559_registry_stop_returns_draining_within_backend_request_budget() -> None:
    result, state, calls = _execute_registry_stop("running", alive=True)

    assert calls == ["stop", ("join", 1.0)]
    assert result == {"status": "draining", "pending_events": 1}
    assert state.status == "running"


def test_v0559_registry_stop_preserves_captured_worker_error_during_drain() -> None:
    result, state, _calls = _execute_registry_stop("error", alive=True)

    assert result["status"] == "draining" and state.status == "error"


def test_v0559_registry_stop_returns_settled_terminal_status() -> None:
    result, state, calls = _execute_registry_stop("stopped", alive=False)

    assert calls == ["stop", ("join", 1.0)]
    assert result["status"] == state.status == "stopped"
