import pytest

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


def test_diagonal_sidewalk_jump_through_road_zone_is_rejected() -> None:
    zone = RoadZone(0.30, 0.0, 0.70, 0.0, 0.70, 1.0, 0.30, 1.0)
    counter = LineCrossingCounter(CountingLine(0.0, 0.5, 1.0, 0.5), road_zone=zone)
    # The segment intersects the yellow line inside the road polygon, but both
    # observations are outside the drivable polygon. V0.5.12 must fail closed.
    assert counter.update(304, (10, 20), 100, 100, 1) is None
    assert counter.update(304, (90, 80), 100, 100, 2) is None
    assert counter.total_crossings == 0
    assert counter.rejected_outside_road == 1


def test_self_crossing_road_zone_is_rejected_at_counter_creation() -> None:
    bad_zone = RoadZone(0.20, 0.20, 0.80, 0.80, 0.80, 0.20, 0.20, 0.80)
    with pytest.raises(ValueError, match="self-intersecting"):
        LineCrossingCounter(CountingLine(0.3, 0.5, 0.7, 0.5), road_zone=bad_zone)


def test_crossing_engine_v6_classifies_consecutive_crossing_as_direct() -> None:
    counter = LineCrossingCounter(CountingLine(0.1, 0.5, 0.9, 0.5), interpolation_gap_frames=3)
    assert counter.update(901, (50, 20), 100, 100, 10) is None
    assert counter.update(901, (50, 80), 100, 100, 11) == "in"
    assert counter.direct_crossings == 1
    assert counter.interpolated_crossings == 0
    assert counter.rescued_crossings == 0
    assert counter.crossing_mode_for(901) == "direct"


def test_crossing_engine_v6_dead_band_crossing_is_interpolated_not_rescue() -> None:
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        dead_band_ratio=0.06,
        interpolation_gap_frames=3,
    )
    assert counter.update(902, (50, 35), 100, 100, 1) is None
    assert counter.update(902, (50, 49), 100, 100, 2) is None
    assert counter.update(902, (50, 65), 100, 100, 3) == "in"
    assert counter.direct_crossings == 0
    assert counter.interpolated_crossings == 1
    assert counter.rescued_crossings == 0
    assert counter.crossing_mode_for(902) == "interpolated"


def test_crossing_engine_v6_small_observation_gap_is_interpolated() -> None:
    counter = LineCrossingCounter(CountingLine(0.1, 0.5, 0.9, 0.5), interpolation_gap_frames=3)
    assert counter.update(903, (50, 20), 100, 100, 1) is None
    assert counter.update(903, (50, 80), 100, 100, 3) == "in"
    assert counter.interpolated_crossings == 1
    assert counter.rescued_crossings == 0


def test_crossing_engine_v6_long_gap_remains_rescue() -> None:
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        history_gap_frames=45,
        interpolation_gap_frames=3,
    )
    assert counter.update(904, (50, 20), 100, 100, 2) is None
    assert counter.update(904, (52, 82), 100, 100, 9) == "in"
    assert counter.direct_crossings == 0
    assert counter.interpolated_crossings == 0
    assert counter.rescued_crossings == 1
    assert counter.crossing_breakdown == {"direct": 0, "interpolated": 0, "rescued": 1}


def test_crossing_engine_v7_startup_grace_does_not_replay_old_crossing() -> None:
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        startup_grace_frames=12,
        side_confirm_samples=2,
    )
    assert counter.update(1001, (50, 20), 100, 100, 1) is None
    assert counter.update(1001, (50, 80), 100, 100, 2) is None
    for frame in range(3, 14):
        assert counter.update(1001, (50, 82), 100, 100, frame) is None
    assert counter.total_crossings == 0


def test_crossing_engine_v7_requires_destination_side_confirmation() -> None:
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        side_confirm_samples=2,
        startup_grace_frames=0,
    )
    assert counter.update(1002, (50, 20), 100, 100, 10) is None
    assert counter.update(1002, (50, 80), 100, 100, 11) is None
    assert counter.rejected_unconfirmed_side == 1
    assert counter.update(1002, (50, 82), 100, 100, 12) == "in"
    assert counter.in_count == 1


def test_crossing_engine_v7_cooldown_blocks_rapid_direction_flip() -> None:
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        dead_band_ratio=0.01,
        rearm_distance_ratio=0.10,
        crossing_cooldown_frames=60,
        startup_grace_frames=0,
    )
    assert counter.update(1003, (50, 20), 100, 100, 10) is None
    assert counter.update(1003, (50, 80), 100, 100, 11) == "in"
    assert counter.update(1003, (50, 90), 100, 100, 12) is None
    assert counter.update(1003, (50, 20), 100, 100, 20) is None
    assert counter.out_count == 0
    assert counter.rejected_cooldown >= 1


def test_crossing_engine_v7_allows_tiny_anchor_road_edge_error() -> None:
    zone = RoadZone(0.20, 0.0, 0.80, 0.0, 0.80, 1.0, 0.20, 1.0)
    counter = LineCrossingCounter(
        CountingLine(0.0, 0.5, 1.0, 0.5),
        road_zone=zone,
        road_anchor_margin_ratio=0.02,
        startup_grace_frames=0,
    )
    assert counter.update(1004, (19, 20), 100, 100, 1) is None
    assert counter.update(1004, (50, 80), 100, 100, 2) == "in"
    assert counter.road_edge_rescues == 1


def test_crossing_engine_v71_fast_destination_can_bypass_second_confirmation() -> None:
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        side_confirm_samples=2,
        fast_confirm_distance_ratio=0.18,
        startup_grace_frames=0,
    )
    assert counter.update(1101, (50, 20), 100, 100, 10) is None
    assert counter.update(1101, (50, 80), 100, 100, 11) == "in"
    assert counter.fast_confirm_rescues == 1


def test_crossing_engine_v71_adaptive_cooldown_allows_real_turnaround_after_far_rearm() -> None:
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        dead_band_ratio=0.01,
        rearm_distance_ratio=0.10,
        crossing_cooldown_frames=60,
        adaptive_cooldown=True,
        cooldown_release_ratio=0.30,
        startup_grace_frames=0,
    )
    assert counter.update(1102, (50, 20), 100, 100, 10) is None
    assert counter.update(1102, (50, 80), 100, 100, 11) == "in"
    assert counter.update(1102, (50, 95), 100, 100, 12) is None
    assert counter.update(1102, (50, 20), 100, 100, 20) == "out"
    assert counter.adaptive_cooldown_releases == 1


def test_crossing_engine_v71_rejects_implausible_long_gap_rescue() -> None:
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        history_gap_frames=45,
        interpolation_gap_frames=3,
        rescue_max_jump_ratio=0.20,
        startup_grace_frames=0,
    )
    assert counter.update(1103, (10, 20), 100, 100, 1) is None
    # Huge diagonal ID-switch-like jump crossing the line.
    assert counter.update(1103, (90, 80), 100, 100, 12) is None
    assert counter.rejected_rescue_validation == 1


def test_crossing_can_be_revoked_by_downstream_human_guard() -> None:
    counter = LineCrossingCounter(CountingLine(0.1, 0.5, 0.9, 0.5))
    assert counter.update(1104, (50, 20), 100, 100, 1) is None
    assert counter.update(1104, (50, 80), 100, 100, 2) == "in"
    assert counter.in_count == 1
    counter.revoke_last_crossing(1104, "in")
    assert counter.in_count == 0
    assert counter.total_crossings == 0
