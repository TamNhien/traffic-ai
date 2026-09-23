from app.counting import CountingLine, LineCrossingCounter, RoadZone


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


def test_history_rescues_crossing_across_missed_frames() -> None:
    counter = LineCrossingCounter(CountingLine(0.1, 0.5, 0.9, 0.5), history_gap_frames=12)
    assert counter.update(80, (50, 20), 100, 100, 1) is None
    # No observations for several frames; the track reappears on the other side.
    assert counter.update(80, (52, 82), 100, 100, 7) == "in"
    assert counter.rescued_crossings == 1


def test_parallel_motion_along_gate_is_not_counted() -> None:
    counter = LineCrossingCounter(CountingLine(0.1, 0.5, 0.9, 0.5))
    for frame, x in enumerate((20, 30, 40, 50, 60, 70), start=1):
        assert counter.update(90, (x, 42), 100, 100, frame) is None
    assert counter.total_crossings == 0


def test_near_endpoint_but_outside_visible_line_is_not_counted() -> None:
    counter = LineCrossingCounter(CountingLine(0.2, 0.5, 0.8, 0.5), segment_margin=0.0)
    assert counter.update(101, (81, 20), 100, 100, 1) is None
    assert counter.update(101, (81, 80), 100, 100, 2) is None
    assert counter.total_crossings == 0
    assert counter.rejected_outside_segment == 1


def test_exact_visible_endpoint_can_count() -> None:
    counter = LineCrossingCounter(CountingLine(0.2, 0.5, 0.8, 0.5), segment_margin=0.0)
    assert counter.update(102, (80, 20), 100, 100, 1) is None
    assert counter.update(102, (80, 80), 100, 100, 2) == "in"


def test_very_fast_crossing_with_long_observation_gap_is_rescued() -> None:
    counter = LineCrossingCounter(CountingLine(0.1, 0.5, 0.9, 0.5), history_gap_frames=45)
    assert counter.update(103, (50, 8), 100, 100, 3) is None
    assert counter.update(103, (52, 92), 100, 100, 28) == "in"
    assert counter.rescued_crossings == 1


def test_multiple_tracks_crossing_same_frame_are_all_counted() -> None:
    counter = LineCrossingCounter(CountingLine(0.1, 0.5, 0.9, 0.5))
    for track_id, x in ((201, 25), (202, 50), (203, 75)):
        assert counter.update(track_id, (x, 20), 100, 100, 1) is None
    for track_id, x in ((201, 25), (202, 50), (203, 75)):
        assert counter.update(track_id, (x, 80), 100, 100, 2) == "in"
    assert counter.in_count == 3


def test_sidewalk_crossing_is_rejected_by_road_zone() -> None:
    zone = RoadZone(0.20, 0.0, 0.80, 0.0, 0.80, 1.0, 0.20, 1.0)
    counter = LineCrossingCounter(CountingLine(0.0, 0.5, 1.0, 0.5), road_zone=zone)
    assert counter.update(301, (8, 20), 100, 100, 1) is None
    assert counter.update(301, (8, 80), 100, 100, 2) is None
    assert counter.total_crossings == 0
    assert counter.rejected_outside_road == 1


def test_roadway_crossing_inside_road_zone_is_counted() -> None:
    zone = RoadZone(0.20, 0.0, 0.80, 0.0, 0.80, 1.0, 0.20, 1.0)
    counter = LineCrossingCounter(CountingLine(0.0, 0.5, 1.0, 0.5), road_zone=zone)
    assert counter.update(302, (50, 20), 100, 100, 1) is None
    assert counter.update(302, (50, 80), 100, 100, 2) == "in"
    assert counter.in_count == 1


def test_fast_crossing_still_counts_when_road_zone_is_valid() -> None:
    zone = RoadZone(0.15, 0.0, 0.85, 0.0, 0.85, 1.0, 0.15, 1.0)
    counter = LineCrossingCounter(CountingLine(0.1, 0.5, 0.9, 0.5), road_zone=zone, history_gap_frames=45)
    assert counter.update(303, (50, 8), 100, 100, 2) is None
    assert counter.update(303, (52, 92), 100, 100, 22) == "in"
    assert counter.rescued_crossings == 1
