from app.tracking import TrackContinuityResolver, motion_leading_anchor


def _anchor_velocity(resolver: TrackContinuityResolver, canonical: int):
    # Differential runs against the delivered .56 ZIP exercise its actual
    # velocity-based anchor behavior before the dedicated heading API existed.
    getter = getattr(resolver, 'anchor_velocity_for', resolver.velocity_for)
    return getter(canonical)


def _v0558_quiet_upward_identity(raw_id=101):
    resolver = TrackContinuityResolver(max_gap_frames=10)
    resolver.resolve(raw_id, (500., 400.), 'motorcycle', 10, 1000, 1000)
    resolver.resolve(raw_id, (500., 388.), 'motorcycle', 11, 1000, 1000)
    for frame in range(12, 28):
        resolver.resolve(raw_id, (500., 388.), 'motorcycle', frame, 1000, 1000)
    return resolver


def test_v0558_sustained_slow_downward_reversal_keeps_real_finite_gate_crossing() -> None:
    from app.counting import CountingLine, LineCrossingCounter, RoadZone

    resolver = TrackContinuityResolver()
    resolver.resolve(101, (500., 400.), 'motorcycle', 10, 1000, 1000)
    resolver.resolve(101, (500., 388.), 'motorcycle', 11, 1000, 1000)
    counter = LineCrossingCounter(CountingLine(.1, .5, .9, .5), road_zone=RoadZone(), startup_grace_frames=0)
    directions = []
    for offset in range(101):
        cy, frame = 388. + offset, 11 + offset
        if offset:
            resolver.resolve(101, (500., cy), 'motorcycle', frame, 1000, 1000)
        anchor = motion_leading_anchor((460., cy-40., 540., cy+40.), _anchor_velocity(resolver, 101))
        result = counter.update(101, anchor, 1000, 1000, frame)
        if result:
            directions.append(result)
    assert resolver.velocity_for(101) == (0., 1.)
    assert _anchor_velocity(resolver, 101)[1] > 0
    assert directions == ['in']


def test_v0558_sustained_slow_upward_reversal_keeps_real_finite_gate_crossing() -> None:
    from app.counting import CountingLine, LineCrossingCounter, RoadZone

    resolver = TrackContinuityResolver()
    resolver.resolve(102, (500., 600.), 'motorcycle', 10, 1000, 1000)
    resolver.resolve(102, (500., 612.), 'motorcycle', 11, 1000, 1000)
    counter = LineCrossingCounter(CountingLine(.1, .5, .9, .5), road_zone=RoadZone(), startup_grace_frames=0)
    directions = []
    for offset in range(145):
        cy, frame = 612. - offset, 11 + offset
        if offset:
            resolver.resolve(102, (500., cy), 'motorcycle', frame, 1000, 1000)
        anchor = motion_leading_anchor((460., cy-40., 540., cy+40.), _anchor_velocity(resolver, 102))
        result = counter.update(102, anchor, 1000, 1000, frame)
        if result:
            directions.append(result)
    assert resolver.velocity_for(102) == (0., -1.)
    assert _anchor_velocity(resolver, 102)[1] < 0
    assert directions == ['out']


def test_v0558_one_opposite_frame_then_stop_cannot_rotate_retained_anchor() -> None:
    resolver = _v0558_quiet_upward_identity()
    before = _anchor_velocity(resolver, 101)
    resolver.resolve(101, (500., 389.4), 'motorcycle', 28, 1000, 1000)
    assert _anchor_velocity(resolver, 101) == before
    for frame in range(29, 36):
        resolver.resolve(101, (500., 389.4), 'motorcycle', frame, 1000, 1000)
        assert _anchor_velocity(resolver, 101) == before


def test_v0558_alternating_small_jitter_cannot_supply_sustained_reverse_travel() -> None:
    from app.counting import CountingLine, LineCrossingCounter

    resolver = _v0558_quiet_upward_identity()
    before = _anchor_velocity(resolver, 101)
    counter = LineCrossingCounter(CountingLine(.1, .35, .9, .35), startup_grace_frames=0)
    for frame in range(28, 58):
        cy = 389.4 if frame % 2 == 0 else 388.
        resolver.resolve(101, (500., cy), 'motorcycle', frame, 1000, 1000)
        assert _anchor_velocity(resolver, 101) == before
        anchor = motion_leading_anchor((460., cy-40., 540., cy+40.), _anchor_velocity(resolver, 101))
        assert counter.update(101, anchor, 1000, 1000, frame) is None
    assert counter.total_crossings == 0


def test_v0558_duplicate_and_stale_frame_cannot_confirm_or_rewrite_motion() -> None:
    resolver = _v0558_quiet_upward_identity()
    before = _anchor_velocity(resolver, 101)
    resolver.resolve(101, (500., 389.4), 'motorcycle', 28, 1000, 1000)
    velocity = resolver.velocity_for(101)
    for frame in (28, 28, 27, 26):
        resolver.resolve(101, (500., 390.8), 'motorcycle', frame, 1000, 1000)
        assert _anchor_velocity(resolver, 101) == before
        assert resolver.velocity_for(101) == velocity
    resolver.resolve(101, (500., 390.8), 'motorcycle', 29, 1000, 1000)
    assert 0 < resolver.velocity_for(101)[1] < 1.5
    assert _anchor_velocity(resolver, 101)[1] >= 1.5


def test_v0558_long_observation_gap_discards_unconfirmed_reversal() -> None:
    resolver = _v0558_quiet_upward_identity()
    before = _anchor_velocity(resolver, 101)
    resolver.resolve(101, (500., 389.4), 'motorcycle', 28, 1000, 1000)
    resolver.resolve(101, (500., 404.8), 'motorcycle', 39, 1000, 1000)
    assert _anchor_velocity(resolver, 101) == before
    resolver.resolve(101, (500., 406.2), 'motorcycle', 40, 1000, 1000)
    assert _anchor_velocity(resolver, 101) == before
    resolver.resolve(101, (500., 407.6), 'motorcycle', 41, 1000, 1000)
    assert _anchor_velocity(resolver, 101)[1] >= 1.5


def test_v0558_alias_fusion_does_not_merge_single_frame_turn_certificates() -> None:
    resolver = _v0558_quiet_upward_identity()
    resolver.resolve(202, (100., 400.), 'motorcycle', 10, 1000, 1000, {101})
    resolver.resolve(202, (100., 388.), 'motorcycle', 11, 1000, 1000, {101})
    for frame in range(12, 28):
        resolver.resolve(202, (100., 388.), 'motorcycle', frame, 1000, 1000, {101})
    resolver.resolve(101, (500., 389.4), 'motorcycle', 28, 1000, 1000)
    resolver.resolve(202, (100., 389.4), 'motorcycle', 28, 1000, 1000, {101})
    before = _anchor_velocity(resolver, 101)
    assert resolver.alias_raw_id(202, 101) == 202
    assert _anchor_velocity(resolver, 202) == (0., 0.)
    assert _anchor_velocity(resolver, 101) == before
    resolver.resolve(101, (500., 390.8), 'motorcycle', 29, 1000, 1000)
    assert _anchor_velocity(resolver, 101) == before
    resolver.resolve(101, (500., 392.2), 'motorcycle', 30, 1000, 1000)
    assert _anchor_velocity(resolver, 101)[1] >= 1.5


def test_v0558_expired_identity_cannot_reuse_unconfirmed_reversal() -> None:
    resolver = _v0558_quiet_upward_identity()
    resolver.resolve(101, (500., 389.4), 'motorcycle', 28, 1000, 1000)
    resolver.resolve(101, (500., 390.8), 'motorcycle', 109, 1000, 1000)
    assert resolver.velocity_for(101) == (0., 0.)
    assert _anchor_velocity(resolver, 101) == (0., 0.)
    resolver.resolve(101, (500., 392.2), 'motorcycle', 110, 1000, 1000)
    assert _anchor_velocity(resolver, 101) == resolver.velocity_for(101)
    assert 0 < _anchor_velocity(resolver, 101)[1] < 1.5


def test_v0558_confirmed_slow_turn_keeps_cardinal_inset_while_coasting() -> None:
    resolver = _v0558_quiet_upward_identity()
    for frame, cy in ((28, 389.4), (29, 390.8), (30, 390.8), (31, 390.8)):
        resolver.resolve(101, (500., cy), 'truck', frame, 1000, 1000)
    assert 0 < resolver.velocity_for(101)[1] < .75
    assert motion_leading_anchor((460., 350.8, 540., 430.8), _anchor_velocity(resolver, 101), .16) == (500., 418.)


def test_v0558_confirmed_slow_reversal_cannot_cross_outside_finite_gate() -> None:
    from app.counting import CountingLine, LineCrossingCounter

    resolver = TrackContinuityResolver()
    resolver.resolve(103, (950., 400.), 'motorcycle', 10, 1000, 1000)
    resolver.resolve(103, (950., 388.), 'motorcycle', 11, 1000, 1000)
    counter = LineCrossingCounter(CountingLine(.1, .5, .9, .5), startup_grace_frames=0)
    for offset in range(101):
        cy, frame = 388. + offset, 11 + offset
        if offset:
            resolver.resolve(103, (950., cy), 'motorcycle', frame, 1000, 1000)
        anchor = motion_leading_anchor((910., cy-40., 990., cy+40.), _anchor_velocity(resolver, 103))
        assert counter.update(103, anchor, 1000, 1000, frame) is None
    assert counter.total_crossings == 0


def test_v0558_confirmed_slow_reversal_cannot_cross_outside_road_zone() -> None:
    from app.counting import CountingLine, LineCrossingCounter, RoadZone

    resolver = TrackContinuityResolver()
    resolver.resolve(104, (850., 400.), 'motorcycle', 10, 1000, 1000)
    resolver.resolve(104, (850., 388.), 'motorcycle', 11, 1000, 1000)
    zone = RoadZone(.2, .2, .8, .2, .8, .8, .2, .8)
    counter = LineCrossingCounter(CountingLine(.1, .5, .9, .5), road_zone=zone, startup_grace_frames=0)
    for offset in range(101):
        cy, frame = 388. + offset, 11 + offset
        if offset:
            resolver.resolve(104, (850., cy), 'motorcycle', frame, 1000, 1000)
        anchor = motion_leading_anchor((810., cy-40., 890., cy+40.), _anchor_velocity(resolver, 104))
        assert counter.update(104, anchor, 1000, 1000, frame) is None
    assert counter.total_crossings == 0


def test_v0557_decelerating_upward_track_cannot_invent_opposite_crossing() -> None:
    from app.counting import CountingLine, LineCrossingCounter

    resolver = TrackContinuityResolver()
    gate = LineCrossingCounter(
        CountingLine(), side_confirm_samples=2, crossing_cooldown_frames=60,
        passage_rearm_min_frames=16, fast_confirm_distance_ratio=.018,
        adaptive_cooldown=True, cooldown_release_ratio=.055,
        rescue_min_normal_ratio=.28, rescue_max_jump_ratio=.26,
        rescue_min_side_distance_ratio=.010, rescue_strict_gap_frames=18,
        rescue_strict_min_normal_ratio=.40, rescue_strict_max_jump_ratio=.20,
        rescue_strict_min_side_distance_ratio=.014, bracket_confirm=True,
        late_geometry_confirm=True,
    )
    directions = []
    for index in range(25):
        cy = 540.0 if index == 0 else 528.0 - (index - 1) * .2
        canonical, _ = resolver.resolve(1, (500.,cy), 'motorcycle',100+index,1000,1000)
        anchor = motion_leading_anchor((460.,cy-80.,540.,cy+80.),_anchor_velocity(resolver,canonical))
        direction = gate.update(canonical,anchor,1000,1000,100+index)
        if direction:
            directions.append(direction)
    assert resolver.velocity_for(1)[1] < 0
    assert abs(resolver.velocity_for(1)[1]) < .75
    assert directions == ['out']
    assert gate.in_count == 0


def test_v0557_unestablished_heading_preserves_stationary_startup_blend() -> None:
    resolver = TrackContinuityResolver()
    for frame, point in [(10,(500.,500.)),(11,(500.,499.)),(12,(500.,498.))]:
        canonical, _ = resolver.resolve(2,point,'motorcycle',frame,1000,1000)
        assert _anchor_velocity(resolver,canonical) == resolver.velocity_for(canonical)
        for inset in (0.,.16,.45):
            assert motion_leading_anchor((450.,point[1]-80.,550.,point[1]+80.),_anchor_velocity(resolver,canonical),inset) == motion_leading_anchor((450.,point[1]-80.,550.,point[1]+80.),resolver.velocity_for(canonical),inset)


def test_v0557_reliable_reversal_updates_heading_and_keeps_inset_cardinal_geometry() -> None:
    resolver = TrackContinuityResolver()
    for frame, point in [(10,(500.,550.)),(11,(500.,530.)),(12,(500.,529.8)),(13,(500.,529.6))]:
        resolver.resolve(3,point,'truck',frame,1000,1000)
    resolver.resolve(3,(500.,550.),'truck',14,1000,1000)
    velocity = _anchor_velocity(resolver,3)
    assert velocity[1] >= 1.5
    assert motion_leading_anchor((450.,470.,550.,630.),velocity,.16) == (500.,604.4)
    resolver.resolve(3,(500.,500.),'truck',15,1000,1000)
    assert _anchor_velocity(resolver,3)[1] <= -1.5
    assert motion_leading_anchor((450.,420.,550.,580.),_anchor_velocity(resolver,3),.16) == (500.,445.6)


def test_v0557_slow_stitched_id_keeps_established_leading_heading() -> None:
    resolver = TrackContinuityResolver(max_gap_frames=20)
    for index,cy in enumerate([550.,538.,537.8,537.6,537.4,537.2]):
        resolver.resolve(4,(500.,cy),'motorcycle',100+index,1000,1000)
    canonical, stitched = resolver.resolve(44,(500.,537.),'motorcycle',106,1000,1000)
    assert stitched and canonical == 4
    assert abs(resolver.velocity_for(canonical)[1]) < 1.5
    assert motion_leading_anchor((460.,457.,540.,617.),_anchor_velocity(resolver,canonical))[1] == 457.


def test_v0557_alias_fusion_moves_newer_heading_without_leaking_displaced_identity() -> None:
    resolver = TrackContinuityResolver()
    resolver.resolve(5,(100.,500.),'motorcycle',100,1000,1000)
    resolver.resolve(55,(500.,500.),'motorcycle',100,1000,1000,{5})
    resolver.resolve(55,(500.,488.),'motorcycle',101,1000,1000,{5})
    assert resolver.alias_raw_id(55,5) == 55
    assert motion_leading_anchor((50.,420.,150.,580.),_anchor_velocity(resolver,5))[1] == 420.
    assert _anchor_velocity(resolver,55) == (0.,0.)
    resolver.resolve(5,(100.,500.),'motorcycle',102,1000,1000)
    assert resolver.velocity_for(5) == (0.,0.)
    assert motion_leading_anchor((50.,420.,150.,580.),_anchor_velocity(resolver,5))[1] == 420.


def test_v0557_alias_fusion_retains_newer_target_heading_and_target_frame_tie() -> None:
    for target_frame in (101,103):
        resolver = TrackContinuityResolver()
        resolver.resolve(6,(100.,500.),'motorcycle',100,1000,1000)
        resolver.resolve(66,(500.,500.),'motorcycle',100,1000,1000,{6})
        resolver.resolve(66,(500.,488.),'motorcycle',101,1000,1000,{6})
        resolver.resolve(6,(112.,500.),'motorcycle',target_frame,1000,1000,{66})
        resolver.alias_raw_id(66,6)
        assert motion_leading_anchor((62.,420.,162.,580.),_anchor_velocity(resolver,6)) == (162.,500.)


def test_v0557_reused_raw_id_expires_before_refreshing_motion_state() -> None:
    resolver = TrackContinuityResolver(max_gap_frames=10)
    resolver.resolve(7,(500.,550.),'motorcycle',10,1000,1000)
    resolver.resolve(7,(500.,538.),'motorcycle',11,1000,1000)
    resolver.resolve(7,(500.,538.),'motorcycle',92,1000,1000)
    assert resolver.velocity_for(7) == (0.,0.)
    assert _anchor_velocity(resolver,7) == (0.,0.)
    assert motion_leading_anchor((460.,458.,540.,618.),_anchor_velocity(resolver,7)) == (500.,618.)
    assert resolver.lineage_size(7) == 1


def test_v0557_active_identity_retains_heading_within_existing_expiry() -> None:
    resolver = TrackContinuityResolver(max_gap_frames=10)
    resolver.resolve(8,(500.,550.),'motorcycle',10,1000,1000)
    resolver.resolve(8,(500.,538.),'motorcycle',11,1000,1000)
    resolver.resolve(8,(500.,538.),'motorcycle',90,1000,1000)
    assert resolver.velocity_for(8)[1] < 0
    assert motion_leading_anchor((460.,458.,540.,618.),_anchor_velocity(resolver,8)) == (500.,458.)


def test_v0556_tiny_heading_change_cannot_jump_between_box_edges() -> None:
    from math import dist

    for inset in (0.0, 0.16, 0.45):
        first = motion_leading_anchor((100, 100, 200, 300), (-2, -2.01), inset)
        second = motion_leading_anchor((100, 100, 200, 300), (-2.01, -2), inset)
        assert dist(first, second) < 1.0


def test_v0556_steady_diagonal_track_does_not_alternate_gate_side() -> None:
    from app.counting import CountingLine, LineCrossingCounter

    counter = LineCrossingCounter(CountingLine(0.0, 0.5, 1.0, 0.5), startup_grace_frames=0)
    for index in range(5):
        velocity = (-2, -2.01) if index % 2 == 0 else (-2.01, -2)
        shift = index * 2
        anchor = motion_leading_anchor((100-shift, 100-shift, 200-shift, 300-shift), velocity)
        assert anchor[1] < 150
        assert counter.update(19086, anchor, 300, 300, 10+index) is None
    assert counter.total_crossings == 0


def test_v0556_stationary_cutoff_does_not_create_box_height_jump() -> None:
    from math import dist

    before = motion_leading_anchor((100, 100, 200, 300), (0, -0.749))
    after = motion_leading_anchor((100, 100, 200, 300), (0, -0.751))
    assert dist(before, after) < 1
    assert motion_leading_anchor((100, 100, 200, 300), (0.1, 0.1)) == (150, 300)


def test_v0556_diagonal_anchor_still_counts_a_real_crossing() -> None:
    from app.counting import CountingLine, LineCrossingCounter

    counter = LineCrossingCounter(CountingLine(0.25, 0.5, 0.75, 0.5), startup_grace_frames=0)
    before = motion_leading_anchor((100, 100, 200, 160), (2, 2.01))
    after = motion_leading_anchor((110, 160, 210, 220), (2.01, 2))
    assert before[1] < 180 < after[1]
    assert counter.update(19087, before, 360, 360, 10) is None
    assert counter.update(19087, after, 360, 360, 11) == 'in'
    assert counter.total_crossings == 1


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


def test_v0530_alias_reports_displaced_canonical_for_state_merge() -> None:
    resolver = TrackContinuityResolver(max_gap_frames=30, max_distance_ratio=0.14)
    resolver.resolve(10, (100.0, 100.0), "car", 1, 1000, 800)
    resolver.resolve(20, (500.0, 500.0), "truck", 1, 1000, 800)
    displaced = resolver.alias_raw_id(20, 10)
    assert displaced == 20


def test_v0549_canonical_lineage_tracks_stitched_raw_ids() -> None:
    resolver = TrackContinuityResolver(max_gap_frames=20, max_distance_ratio=0.14)
    canonical, _ = resolver.resolve(10, (400, 220), "motorcycle", 10, 1000, 600)
    assert resolver.lineage_size(canonical) == 1
    stitched_id, stitched = resolver.resolve(44, (410, 300), "motorcycle", 17, 1000, 600)
    assert stitched is True
    assert stitched_id == canonical
    assert resolver.lineage_size(canonical) == 2
    assert resolver.has_lineage_switch(canonical) is True
