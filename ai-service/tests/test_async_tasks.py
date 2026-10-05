from types import SimpleNamespace
import threading
from unittest.mock import patch

from app import async_tasks


def _state():
    return SimpleNamespace(
        pending_events=0, delivery_failures=0, delivered_events=0,
        persisted_events=0, deduplicated_events=0, last_error=None,
        crossing_signature_duplicates=0, two_wheel_signature_duplicates=0,
        two_wheel_spatial_signature_duplicates=0,
        two_wheel_ultra_spatial_signature_duplicates=0,
        same_track_repeat_duplicates=0, direction_flip_duplicates=0,
        secondary_shadow_duplicates=0, direct_shadow_duplicates=0,
        cross_method_shadow_duplicates=0, semantic_shadow_duplicates=0,
        reverse_shadow_duplicates=0,
    )


def _event(track_id=77):
    return {
        "camera_id": 1, "session_id": 2, "tracking_id": track_id,
        "vehicle_type": "motorcycle", "direction": "in",
        "source_frame_index": 519, "source_time_seconds": 20.72,
        "crossing_x": .51, "crossing_y": .62,
        "crossing_method": "direct", "snapshot_path": "camera_1/frame_519.jpg",
    }


class _Response:
    def __init__(self, headers=None):
        self.headers = headers or {}

    def raise_for_status(self):
        pass


class _Client:
    def __init__(self, post):
        self.post = post

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass


def _start_flush(dispatcher):
    result = []
    errors = []
    finished = threading.Event()

    def flush():
        try:
            result.append(dispatcher.stop_and_flush(timeout=None))
        except Exception as exc:
            errors.append(exc)
        finally:
            finished.set()

    thread = threading.Thread(target=flush, daemon=True)
    thread.start()
    return thread, result, errors, finished


def test_v0559_bounded_flush_reports_inflight_request_as_unfinished() -> None:
    entered, release = threading.Event(), threading.Event()
    sent = []

    def post(_url, *, json):
        sent.append(dict(json))
        entered.set()
        assert release.wait(3)
        return _Response()

    state = _state()
    dispatcher = async_tasks.EventDispatcher("https://local-test.invalid/internal", "test", state)
    with patch.object(async_tasks.httpx, "Client", return_value=_Client(post)):
        dispatcher.submit(_event())
        dispatcher.start()
        try:
            assert entered.wait(2)
            assert dispatcher._queue.empty()
            assert dispatcher.stop_and_flush(timeout=0) is False
            assert dispatcher.is_alive() and state.pending_events == 1
            assert state.delivered_events == state.persisted_events == 0
        finally:
            release.set()
            dispatcher.join(2)
    assert not dispatcher.is_alive()
    assert state.pending_events == 0 and state.persisted_events == 1
    assert sent == [_event()]


def test_v0559_unbounded_flush_waits_for_inflight_delivery_completion() -> None:
    entered, release = threading.Event(), threading.Event()
    sent = []

    def post(_url, *, json):
        entered.set()
        assert release.wait(3)
        sent.append(dict(json))
        return _Response()

    state = _state()
    dispatcher = async_tasks.EventDispatcher("https://local-test.invalid/internal", "test", state)
    with patch.object(async_tasks.httpx, "Client", return_value=_Client(post)):
        dispatcher.submit(_event())
        dispatcher.start()
        assert entered.wait(2)
        thread, result, errors, finished = _start_flush(dispatcher)
        try:
            assert dispatcher._stop_event.wait(2)
            assert not finished.is_set() and state.pending_events == 1
            assert state.persisted_events == 0
        finally:
            release.set()
            thread.join(2)
            dispatcher.join(2)
    assert finished.is_set() and result == [True] and errors == []
    assert sent == [_event()] and state.persisted_events == 1 and state.pending_events == 0


def test_v0559_shutdown_drains_accepted_backlog_in_source_order() -> None:
    entered, release = threading.Event(), threading.Event()
    sent = []

    def post(_url, *, json):
        if not sent:
            entered.set()
            assert release.wait(3)
        sent.append(dict(json))
        return _Response()

    state = _state()
    dispatcher = async_tasks.EventDispatcher("https://local-test.invalid/internal", "test", state)
    first, second = _event(77), _event(88)
    second.update(source_frame_index=526, source_time_seconds=21.0, direction="out")
    with patch.object(async_tasks.httpx, "Client", return_value=_Client(post)):
        dispatcher.submit(first)
        dispatcher.submit(second)
        dispatcher.start()
        assert entered.wait(2)
        thread, result, errors, finished = _start_flush(dispatcher)
        try:
            assert dispatcher._stop_event.wait(2)
            assert state.pending_events == 2 and not finished.is_set()
        finally:
            release.set()
            thread.join(2)
            dispatcher.join(2)
    assert result == [True] and errors == [] and sent == [first, second]
    assert state.delivered_events == state.persisted_events == 2 and state.pending_events == 0


def test_v0559_shutdown_closes_admission_without_counting_rejected_event() -> None:
    state = _state()
    dispatcher = async_tasks.EventDispatcher("https://local-test.invalid/internal", "test", state)
    assert dispatcher.stop_and_flush(timeout=0) is True
    try:
        dispatcher.submit(_event())
    except RuntimeError as exc:
        assert "not accepted" in str(exc)
    else:
        raise AssertionError("Stopped dispatcher must reject late admission")
    assert dispatcher._queue.unfinished_tasks == 0
    assert state.pending_events == state.delivery_failures == 0


def test_v0559_submit_and_shutdown_share_atomic_admission_boundary() -> None:
    entered, release = threading.Event(), threading.Event()
    sent, producer_errors = [], []
    state = _state()
    dispatcher = async_tasks.EventDispatcher("https://local-test.invalid/internal", "test", state)
    original_put = dispatcher._queue.put

    def delayed_put(payload, **kwargs):
        entered.set()
        assert release.wait(3)
        original_put(payload, **kwargs)

    def produce():
        try:
            dispatcher.submit(_event())
        except Exception as exc:
            producer_errors.append(exc)

    def post(_url, *, json):
        sent.append(dict(json))
        return _Response()

    dispatcher._queue.put = delayed_put
    with patch.object(async_tasks.httpx, "Client", return_value=_Client(post)):
        dispatcher.start()
        producer = threading.Thread(target=produce, daemon=True)
        producer.start()
        assert entered.wait(2)
        thread, result, errors, finished = _start_flush(dispatcher)
        try:
            assert not dispatcher._stop_event.is_set() and not finished.is_set()
        finally:
            release.set()
            producer.join(2)
            thread.join(2)
            dispatcher.join(2)
    assert producer_errors == errors == [] and result == [True]
    assert sent == [_event()] and state.persisted_events == 1 and state.pending_events == 0


def test_v0559_retries_preserve_original_source_clock_and_clear_recovered_error() -> None:
    state, sent, delays = _state(), [], []

    def post(_url, *, json):
        sent.append(dict(json))
        if len(sent) < 3:
            raise RuntimeError("local retryable failure")
        return _Response()

    dispatcher = async_tasks.EventDispatcher("https://local-test.invalid/internal", "test", state)
    with patch.object(async_tasks.httpx, "Client", return_value=_Client(post)), \
            patch.object(async_tasks.time, "sleep", side_effect=delays.append):
        dispatcher.submit(_event())
        dispatcher.start()
        assert dispatcher.stop_and_flush(timeout=None) is True
    assert sent == [_event()] * 3 and delays == [.12, .24]
    assert state.delivery_failures == 2 and state.delivered_events == state.persisted_events == 1
    assert state.pending_events == 0 and state.last_error is None


def test_v0559_exhausted_retries_are_terminal_without_inventing_persistence() -> None:
    state, sent, delays = _state(), [], []

    def post(_url, *, json):
        sent.append(dict(json))
        raise RuntimeError("local terminal failure")

    dispatcher = async_tasks.EventDispatcher("https://local-test.invalid/internal", "test", state)
    with patch.object(async_tasks.httpx, "Client", return_value=_Client(post)), \
            patch.object(async_tasks.time, "sleep", side_effect=delays.append):
        dispatcher.submit(_event())
        dispatcher.start()
        assert dispatcher.stop_and_flush(timeout=None) is True
    assert sent == [_event()] * 5 and delays == [.12, .24, .36, .48]
    assert state.delivery_failures == 5 and state.pending_events == 0
    assert state.delivered_events == state.persisted_events == 0
    assert state.last_error == "Event delivery attempt 5 failed: local terminal failure"


def test_v0559_deduplicated_completion_preserves_delivery_accounting() -> None:
    state, sent = _state(), []

    def post(_url, *, json):
        sent.append(dict(json))
        return _Response({"X-TrafficAI-Deduplicated": "1", "X-TrafficAI-Dedup-Reason": "crossing-signature"})

    dispatcher = async_tasks.EventDispatcher("https://local-test.invalid/internal", "test", state)
    with patch.object(async_tasks.httpx, "Client", return_value=_Client(post)):
        dispatcher.submit(_event())
        dispatcher.start()
        assert dispatcher.stop_and_flush(timeout=None) is True
    assert state.delivered_events == state.deduplicated_events == state.crossing_signature_duplicates == 1
    assert state.persisted_events == state.pending_events == 0 and sent == [_event()]


def test_v0559_dead_dispatcher_with_unfinished_work_is_not_a_flush() -> None:
    state, errors = _state(), []
    dispatcher = async_tasks.EventDispatcher("https://local-test.invalid/internal", "test", state)

    def failed_client(**_kwargs):
        raise RuntimeError("local client initialization failure")

    with patch.object(async_tasks.httpx, "Client", side_effect=failed_client), \
            patch.object(threading, "excepthook", side_effect=lambda args: errors.append(args.exc_value)):
        dispatcher.submit(_event())
        dispatcher.start()
        dispatcher.join(2)
        assert dispatcher.stop_and_flush(timeout=0) is False
    assert not dispatcher.is_alive() and state.pending_events == 1
    assert len(errors) == 1 and str(errors[0]) == "local client initialization failure"
    assert state.persisted_events == state.delivered_events == 0
