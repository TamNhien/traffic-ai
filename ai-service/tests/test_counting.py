from app.counting import CountingLine, LineCrossingCounter


def test_line_crossing_in_is_counted_once() -> None:
    counter = LineCrossingCounter(CountingLine(0.0, 0.5, 1.0, 0.5))
    assert counter.update(10, (50, 25), 100, 100) is None
    assert counter.update(10, (50, 75), 100, 100) == "in"
    assert counter.update(10, (50, 80), 100, 100) is None
    assert counter.in_count == 1


def test_line_crossing_out() -> None:
    counter = LineCrossingCounter(CountingLine(0.0, 0.5, 1.0, 0.5))
    assert counter.update(20, (50, 75), 100, 100) is None
    assert counter.update(20, (50, 25), 100, 100) == "out"
    assert counter.out_count == 1


def test_crossing_outside_segment_is_not_counted() -> None:
    counter = LineCrossingCounter(CountingLine(0.2, 0.5, 0.8, 0.5), segment_margin=0.0)
    assert counter.update(30, (5, 25), 100, 100) is None
    assert counter.update(30, (5, 75), 100, 100) is None
    assert counter.total_crossings == 0


def test_exact_line_frame_does_not_lose_crossing() -> None:
    counter = LineCrossingCounter(CountingLine(0.0, 0.5, 1.0, 0.5))
    assert counter.update(40, (50, 25), 100, 100) is None
    assert counter.update(40, (50, 50), 100, 100) is None
    assert counter.update(40, (50, 75), 100, 100) == "in"


def test_fast_track_segment_crossing_is_counted() -> None:
    counter = LineCrossingCounter(CountingLine(0.1, 0.5, 0.9, 0.5))
    assert counter.update(50, (50, 10), 100, 100) is None
    assert counter.update(50, (50, 90), 100, 100) == "in"
    assert counter.in_count == 1


def test_vehicle_that_never_crosses_is_not_counted() -> None:
    counter = LineCrossingCounter(CountingLine(0.1, 0.5, 0.9, 0.5))
    for y in (10, 20, 30, 35, 38, 32, 25):
        assert counter.update(60, (50, y), 100, 100) is None
    assert counter.total_crossings == 0


def test_same_track_can_cross_in_then_out() -> None:
    counter = LineCrossingCounter(
        CountingLine(0.0, 0.5, 1.0, 0.5),
        dead_band_ratio=0.01,
        rearm_distance_ratio=0.10,
    )
    assert counter.update(70, (50, 20), 100, 100) is None
    assert counter.update(70, (50, 80), 100, 100) == "in"
    # Stay far enough on the new side to re-arm before reversing.
    assert counter.update(70, (50, 90), 100, 100) is None
    assert counter.update(70, (50, 20), 100, 100) == "out"
    assert counter.in_count == 1
    assert counter.out_count == 1
    assert counter.total_crossings == 2
