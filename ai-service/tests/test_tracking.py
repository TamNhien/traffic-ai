from app.tracking import TrackContinuityResolver


def test_keeps_existing_raw_id() -> None:
    resolver = TrackContinuityResolver(max_gap_frames=10, max_distance_ratio=0.1)
    c1, stitched1 = resolver.resolve(7, (100, 100), "car", 1, 1000, 500)
    c2, stitched2 = resolver.resolve(7, (110, 110), "car", 2, 1000, 500)
    assert c1 == 7
    assert c2 == 7
    assert stitched1 is False
    assert stitched2 is False


def test_stitches_short_id_switch_across_gap() -> None:
    resolver = TrackContinuityResolver(max_gap_frames=12, max_distance_ratio=0.1)
    canonical, _ = resolver.resolve(10, (400, 220), "truck", 10, 1000, 600)
    new_canonical, stitched = resolver.resolve(44, (410, 275), "bus", 15, 1000, 600)
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

    resolver = TrackContinuityResolver(max_gap_frames=12, max_distance_ratio=0.12)
    counter = LineCrossingCounter(CountingLine(0.1, 0.5, 0.9, 0.5), dead_band_ratio=0.005)

    canonical, _ = resolver.resolve(10, (500, 180), "car", 10, 1000, 600)
    assert counter.update(canonical, (500, 180), 1000, 600) is None
    canonical, _ = resolver.resolve(10, (501, 220), "car", 11, 1000, 600)
    assert counter.update(canonical, (501, 220), 1000, 600) is None

    canonical2, stitched = resolver.resolve(91, (505, 410), "car", 16, 1000, 600)
    assert stitched is True
    assert canonical2 == canonical
    assert counter.update(canonical2, (505, 410), 1000, 600) == "in"
    assert counter.total_crossings == 1
