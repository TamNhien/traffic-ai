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
