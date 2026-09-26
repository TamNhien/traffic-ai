from app.tracking import TrackContinuityResolver, motion_leading_anchor


def test_keeps_existing_raw_id() -> None:
    resolver = TrackContinuityResolver(max_gap_frames=10, max_distance_ratio=0.1)
    c1, stitched1 = resolver.resolve(7, (100, 100), "car", 1, 1000, 500)
    c2, stitched2 = resolver.resolve(7, (110, 110), "car", 2, 1000, 500)
    assert c1 == 7
    assert c2 == 7
    assert stitched1 is False
    assert stitched2 is False


def test_stitches_short_id_switch_across_gap() -> None:
    resolver = TrackContinuityResolver(max_gap_frames=20, max_distance_ratio=0.14)
    canonical, _ = resolver.resolve(10, (400, 220), "truck", 10, 1000, 600)
    new_canonical, stitched = resolver.resolve(44, (410, 300), "bus", 17, 1000, 600)
    assert canonical == 10
    assert new_canonical == 10
    assert stitched is True
    assert resolver.stitch_count == 1


def test_does_not_merge_two_visible_tracks() -> None:
    resolver = TrackContinuityResolver(max_gap_frames=12, max_distance_ratio=0.1)
    canonical, _ = resolver.resolve(10, (400, 220), "car", 10, 1000, 600)
    new_canonical, stitched = resolver.resolve(44, (405, 225), "car", 11, 1000, 600, {canonical})
    assert new_canonical == 44
    assert stitched is False


def test_does_not_stitch_different_vehicle_family() -> None:
    resolver = TrackContinuityResolver(max_gap_frames=12, max_distance_ratio=0.1)
    resolver.resolve(10, (400, 220), "motorcycle", 10, 1000, 600)
    canonical, stitched = resolver.resolve(44, (405, 225), "truck", 12, 1000, 600)
    assert canonical == 44
    assert stitched is False


def test_stitched_identity_preserves_crossing_history() -> None:
    from app.counting import CountingLine, LineCrossingCounter

    resolver = TrackContinuityResolver(max_gap_frames=20, max_distance_ratio=0.14)
    counter = LineCrossingCounter(CountingLine(0.1, 0.5, 0.9, 0.5), dead_band_ratio=0.005, history_gap_frames=20)

    canonical, _ = resolver.resolve(10, (500, 180), "car", 10, 1000, 600)
    assert counter.update(canonical, (500, 180), 1000, 600, 10) is None
    resolver.resolve(10, (501, 220), "car", 11, 1000, 600)

    canonical2, stitched = resolver.resolve(91, (505, 410), "car", 16, 1000, 600)
    assert stitched is True
    assert canonical2 == canonical
    assert counter.update(canonical2, (505, 410), 1000, 600, 16) == "in"
    assert counter.total_crossings == 1


def test_motion_leading_anchor_changes_with_direction() -> None:
    rect = (10.0, 20.0, 30.0, 60.0)
    assert motion_leading_anchor(rect, (0.0, 5.0)) == (20.0, 60.0)
    assert motion_leading_anchor(rect, (0.0, -5.0)) == (20.0, 20.0)
    assert motion_leading_anchor(rect, (5.0, 0.0)) == (30.0, 40.0)
    assert motion_leading_anchor(rect, (-5.0, 0.0)) == (10.0, 40.0)


def test_duplicate_heavy_raw_id_can_alias_existing_canonical() -> None:
    resolver = TrackContinuityResolver(max_gap_frames=30, max_distance_ratio=0.14)
    canonical, _ = resolver.resolve(10, (400, 220), "truck", 10, 1000, 600)
    assert canonical == 10
    resolver.alias_raw_id(44, canonical)
    aliased, stitched = resolver.resolve(44, (405, 225), "bus", 11, 1000, 600)
    assert aliased == 10
    assert stitched is False


def test_v0528_heavy_vehicle_anchor_insets_large_box_from_road_edge() -> None:
    rect = (10.0, 20.0, 30.0, 100.0)
    assert motion_leading_anchor(rect, (0.0, 5.0), inset_ratio=0.20) == (20.0, 84.0)
    assert motion_leading_anchor(rect, (0.0, -5.0), inset_ratio=0.20) == (20.0, 36.0)


def test_v0528_heavy_inset_anchor_keeps_van_crossing_inside_road_zone() -> None:
    from app.counting import CountingLine, LineCrossingCounter, RoadZone

    zone = RoadZone(0.0, 0.0, 1.0, 0.0, 1.0, 0.86, 0.0, 0.86)
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        road_zone=zone,
        startup_grace_frames=0,
    )
    before = motion_leading_anchor((40.0, 0.0, 60.0, 50.0), (0.0, 8.0), inset_ratio=0.16)
    after = motion_leading_anchor((40.0, 35.0, 60.0, 95.0), (0.0, 8.0), inset_ratio=0.16)
    assert before[1] < 50.0
    assert after[1] < 86.0  # raw leading edge y=95 would be outside the Road Zone
    assert counter.update(1401, before, 100, 100, 10) is None
    assert counter.update(1401, after, 100, 100, 11) == "in"
    assert counter.rejected_outside_road == 0


def test_v0529_heavy_track_can_stitch_across_longer_van_gap() -> None:
    resolver = TrackContinuityResolver(
        max_gap_frames=30,
        max_distance_ratio=0.14,
        heavy_max_gap_frames=90,
        heavy_max_distance_ratio=0.18,
    )
    canonical, _ = resolver.resolve(101, (520, 160), "truck", 100, 1440, 810)
    resolver.resolve(101, (525, 190), "truck", 101, 1440, 810)
    stitched_id, stitched = resolver.resolve(909, (545, 360), "car", 145, 1440, 810)
    assert stitched is True
    assert stitched_id == canonical
    assert resolver.heavy_stitch_count == 1


def test_v0529_two_wheel_does_not_use_heavy_stitch_window() -> None:
    resolver = TrackContinuityResolver(
        max_gap_frames=30,
        max_distance_ratio=0.14,
        heavy_max_gap_frames=90,
        heavy_max_distance_ratio=0.18,
    )
    resolver.resolve(201, (520, 160), "motorcycle", 100, 1440, 810)
    stitched_id, stitched = resolver.resolve(202, (540, 330), "motorcycle", 145, 1440, 810)
    assert stitched is False
    assert stitched_id == 202
