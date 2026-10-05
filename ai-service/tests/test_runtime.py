from types import SimpleNamespace

from app.runtime import PipelineRegistry, PipelineState


def test_each_pipeline_state_starts_with_fresh_session_counters() -> None:
    first = PipelineState(camera_id=1, session_id=10)
    first.total_count = 7
    first.in_count = 4
    first.out_count = 3
    first.counts_by_type["car"] = 5

    second = PipelineState(camera_id=1, session_id=11)
    assert second.total_count == 0
    assert second.in_count == 0
    assert second.out_count == 0
    assert second.counts_by_type == {
        "motorcycle": 0,
        "bicycle": 0,
        "car": 0,
        "bus": 0,
        "truck": 0,
        "other": 0,
    }
    assert first.counts_by_type is not second.counts_by_type


def _finishing_registry(status="completed", *, alive=True):
    registry = PipelineRegistry()
    state = PipelineState(camera_id=1, session_id=163, status=status)
    state.total_count = state.persisted_events = 149
    worker = SimpleNamespace(is_alive=lambda: alive)
    registry._workers[1] = worker
    registry._states[1] = state
    return registry, state, worker


def test_v0559_registry_finish_rpc_phase_public_get_and_list_remain_draining() -> None:
    registry, state, _worker = _finishing_registry()

    public = registry.get(1)
    listed = registry.list()

    assert public["status"] == listed[0]["status"] == "draining"
    assert public["pending_events"] == 0 and public["persisted_events"] == 149
    assert state.status == "completed"
    public["counts_by_type"]["car"] = 99
    assert state.counts_by_type["car"] == 0


def test_v0559_registry_preserves_terminal_finish_payload_for_every_outcome() -> None:
    for terminal in ("completed", "stopped", "error"):
        registry, state, _worker = _finishing_registry(terminal)
        state.last_error = "original failure" if terminal == "error" else None

        public = registry.get(1)

        assert public["status"] == registry.list()[0]["status"] == "draining"
        assert state.status == terminal and public["last_error"] == state.last_error


def test_v0559_registry_preserves_active_and_already_draining_public_states() -> None:
    for active in ("starting", "warming", "running", "draining"):
        registry, state, _worker = _finishing_registry(active)

        assert registry.get(1)["status"] == registry.list()[0]["status"] == active
        assert state.status == active


def test_v0559_registry_dead_worker_exposes_settled_terminal_outcome() -> None:
    for terminal in ("completed", "stopped", "error"):
        registry, state, _worker = _finishing_registry(terminal, alive=False)

        assert registry.get(1)["status"] == registry.list()[0]["status"] == terminal
        assert state.status == terminal


def test_v0559_registry_rejects_new_replay_until_finish_callback_releases_camera() -> None:
    registry, state, _worker = _finishing_registry()

    try:
        registry.start(SimpleNamespace(camera_id=1, session_id=164))
    except ValueError as exc:
        assert str(exc) == "Pipeline already running for this camera"
    else:
        raise AssertionError("Finish RPC still owns this camera")

    assert registry.get(1)["status"] == "draining" and state.status == "completed"
    assert registry._states[1].session_id == 163


def test_v0559_registry_finish_callback_exposes_terminal_then_allows_fresh_replay(monkeypatch) -> None:
    import app.worker as worker_module

    registry, old_state, _worker = _finishing_registry()
    starts = []

    class NextWorker:
        def __init__(self, *, payload, state, on_finished):
            self.payload = payload
            self.state = state
            self.on_finished = on_finished

        def start(self):
            starts.append(self.payload.session_id)

        def is_alive(self):
            return True

    monkeypatch.setattr(worker_module, "PipelineWorker", NextWorker)
    registry._on_finished(1)
    assert registry.get(1)["status"] == registry.list()[0]["status"] == "completed"

    result = registry.start(SimpleNamespace(camera_id=1, session_id=164))

    assert starts == [164] and result["status"] == "starting"
    assert result["session_id"] == 164 and result["total_count"] == result["persisted_events"] == 0
    assert registry.get(1)["status"] == "starting"
    assert old_state.status == "completed" and old_state.total_count == 149
