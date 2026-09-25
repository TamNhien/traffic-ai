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
