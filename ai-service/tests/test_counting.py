import pytest

from app.counting import CountingLine, LineCrossingCounter, RoadZone


def test_v0553_observed_bracket_ignores_later_same_side_touch_source_time() -> None:
    from app.counting import _GateSample, crossing_frame_between, observed_gate_crossing

    samples = [
        _GateSample(1, (500, 470), -30.0, -1),
        _GateSample(2, (500, 497), -3.0, 0),
        _GateSample(3, (500, 503), 3.0, 0),
        _GateSample(4, (505, 500), 0.0, 0),
        _GateSample(5, (510, 530), 30.0, 1),
    ]
    bracket = observed_gate_crossing(samples, samples[0], samples[-1], (100, 500), (800, 500))
    assert bracket is not None
    left, right, point = bracket
    assert point == (500.0, 500.0)
    assert crossing_frame_between(left, right, point) == pytest.approx(2.5)


def test_v0553_observed_bracket_outside_touch_cannot_erase_real_finite_crossing() -> None:
    from app.counting import _GateSample, observed_gate_crossing

    samples = [
        _GateSample(1, (805, 470), -30.0, -1),
        _GateSample(2, (760, 497), -3.0, 0),
        _GateSample(3, (760, 503), 3.0, 0),
        _GateSample(4, (805, 500), 0.0, 0),
        _GateSample(5, (805, 530), 30.0, 1),
    ]
    bracket = observed_gate_crossing(samples, samples[0], samples[-1], (100, 500), (800, 500))
    assert bracket == (samples[1], samples[2], (760.0, 500.0))
    # A genuine later side change outside the endpoint remains authoritative;
    # selecting the older interior intersection would accept an endpoint detour.
    samples[3] = _GateSample(4, (805, 497), -3.0, 0)
    assert observed_gate_crossing(samples, samples[0], samples[-1], (100, 500), (800, 500)) is None


def test_v0553_anchor_immediate_proposal_waits_for_primary_and_can_post_confirm() -> None:
    from app.counting import VerifiedAnchorSpanRescuer

    line = CountingLine(0.1, 0.5, 0.9, 0.5)
    counter = LineCrossingCounter(line, crossing_cooldown_frames=60)
    span = VerifiedAnchorSpanRescuer(line)
    assert counter.register_external_crossing(5701, "out", 10, (500.0, 500.0))
    span.mark_counted(5701, "out", 10, commit_candidate=False)
    before = span.capture_passage_state(5701)
    assert span.update(5701, (500, 430), 1000, 1000, 30, commit=False) is None
    candidate = span.update(5701, (500, 570), 1000, 1000, 31, commit=False)
    assert candidate == ("in", (500.0, 500.0))
    assert span.capture_passage_state(5701) == before
    assert span.verified_anchor_span_rescues == 0
    assert not span.override_qualified_for(5701)
    accepted = counter.register_external_crossing(5701, candidate[0], 31, candidate[1])
    assert not accepted
    span.note_immediate_handoff_result(5701, accepted)
    assert span.immediate_handoff_rejections == 1
    confirmed = span.update(5701, (500, 585), 1000, 1000, 32, commit=False)
    assert confirmed == candidate
    assert span.override_qualified_for(5701)
    assert span.capture_passage_state(5701) == before
    assert span.post_confirm_closures == 0
    assert counter.register_external_crossing(5701, confirmed[0], 32, confirmed[1], verified_anchor_span=True)
    span.consume_override_qualification(5701)
    span.mark_counted(5701, "in", 32)
    assert span.capture_passage_state(5701)[:2] == (frozenset({"in"}), 32)
    assert span.verified_anchor_span_rescues == span.post_confirm_closures == 1
    span.mark_counted(5701, "in", 32)
    assert span.verified_anchor_span_rescues == span.post_confirm_closures == 1
    span.restore_passage_state(5701, before)
    assert span.verified_anchor_span_rescues == span.post_confirm_closures == 0


def test_v0553_anchor_post_confirm_handoff_can_retry_without_spending_passage() -> None:
    from app.counting import VerifiedAnchorSpanRescuer

    span = VerifiedAnchorSpanRescuer(CountingLine(), immediate_min_normal_ratio=0.95)
    before = span.capture_passage_state(5702)
    assert span.update(5702, (450, 460), 1000, 1000, 20, commit=False) is None
    assert span.update(5702, (500, 540), 1000, 1000, 21, commit=False) is None
    candidate = span.update(5702, (520, 550), 1000, 1000, 22, commit=False)
    assert candidate is not None and candidate[0] == "in"
    crossing_frame = span.crossing_frame_for(5702)
    assert span.capture_passage_state(5702) == before
    assert span.verified_anchor_span_rescues == span.post_confirm_closures == 0
    retry = span.update(5702, (530, 565), 1000, 1000, 23, commit=False)
    assert retry == candidate
    assert span.crossing_frame_for(5702) == crossing_frame
    span.mark_counted(5702, "in", 23)
    assert span.post_confirm_closures == 1
    assert span.crossing_frame_for(5702) == crossing_frame


def test_v0553_anchor_lost_proposal_is_retryable_until_primary_accepts() -> None:
    from app.counting import VerifiedAnchorSpanRescuer

    span = VerifiedAnchorSpanRescuer(CountingLine(), immediate_min_normal_ratio=0.95)
    before = span.capture_passage_state(5703)
    assert span.update(5703, (450, 460), 1000, 1000, 20, commit=False) is None
    assert span.update(5703, (500, 540), 1000, 1000, 21, commit=False) is None
    candidate = span.finalize_lost(5703, 22, commit=False)
    assert candidate is not None and candidate[0] == "in"
    assert span.override_qualified_for(5703)
    assert span.capture_passage_state(5703) == before
    assert span.verified_anchor_span_rescues == span.lost_track_finalizations == 0
    assert span.finalize_lost(5703, 23, commit=False) == candidate
    span.mark_counted(5703, "in", 21)
    assert span.lost_track_finalizations == span.verified_anchor_span_rescues == 1
    assert span.finalize_lost(5703, 24, commit=False) is None


def test_v0553_anchor_guard_rollback_restores_committed_rescue_telemetry_once() -> None:
    from app.counting import VerifiedAnchorSpanRescuer

    for lost in (False, True):
        span = VerifiedAnchorSpanRescuer(CountingLine(), immediate_min_normal_ratio=0.95)
        span.mark_counted(5704, "out", 10, commit_candidate=False)
        before = span.capture_passage_state(5704)
        assert span.update(5704, (450, 460), 1000, 1000, 20, commit=False) is None
        assert span.update(5704, (500, 540), 1000, 1000, 21, commit=False) is None
        candidate = span.finalize_lost(5704, 22, commit=False) if lost else span.update(
            5704, (520, 550), 1000, 1000, 22, commit=False,
        )
        assert candidate is not None
        span.mark_counted(5704, "in", 22)
        assert span.verified_anchor_span_rescues == 1
        assert span.lost_track_finalizations == int(lost)
        assert span.post_confirm_closures == int(not lost)
        span.restore_passage_state(5704, before)
        assert span.capture_passage_state(5704) == before
        assert span.verified_anchor_span_rescues == span.lost_track_finalizations == span.post_confirm_closures == 0
        span.restore_passage_state(5704, before)
        assert span.verified_anchor_span_rescues == 0
        assert span.finalize_lost(5704, 23, commit=False) is None
        assert span.update(5704, (530, 565), 1000, 1000, 23, commit=False) is None


def test_v0553_anchor_candidate_unused_by_primary_does_not_count_as_rescue() -> None:
    from app.counting import VerifiedAnchorSpanRescuer

    span = VerifiedAnchorSpanRescuer(CountingLine())
    assert span.update(5705, (500, 465), 1000, 1000, 1, commit=False) is None
    assert span.update(5705, (500, 535), 1000, 1000, 2, commit=False) is not None
    span.mark_counted(5705, "in", 2, commit_candidate=False)
    assert span.verified_anchor_span_rescues == span.immediate_override_qualifications == 0
    assert span.capture_passage_state(5705)[:2] == (frozenset({"in"}), 2)
    assert span.update(5705, (500, 545), 1000, 1000, 3, commit=False) is None


def test_v0553_anchor_accepted_passage_discards_opposite_tail_of_long_history() -> None:
    from app.counting import VerifiedAnchorSpanRescuer

    span = VerifiedAnchorSpanRescuer(CountingLine(), history_gap_frames=90)
    assert span.update(5706, (500, 465), 1000, 1000, 1, commit=False) is None
    assert span.update(5706, (500, 535), 1000, 1000, 2, commit=False) is not None
    span.mark_counted(5706, "in", 2)
    for frame in range(3, 35):
        assert span.update(5706, (500, 550), 1000, 1000, frame, commit=False) is None
    assert span.verified_anchor_span_rescues == 1
    assert span.post_confirm_closures == 0


def test_v0553_primary_sync_discards_anchor_history_older_than_accepted_frame() -> None:
    from app.counting import VerifiedAnchorSpanRescuer

    span = VerifiedAnchorSpanRescuer(CountingLine(), history_gap_frames=90)
    assert span.update(5707, (500, 465), 1000, 1000, 10, commit=False) is None
    # The primary gate accepted frame11, so the secondary update was skipped in
    # that frame. Its last sample is pre-crossing and cannot seed a new passage.
    span.mark_counted(5707, "in", 11, commit_candidate=False)
    for frame in range(12, 40):
        assert span.update(5707, (500, 550), 1000, 1000, frame, commit=False) is None
    assert span.verified_anchor_span_rescues == 0


def test_v0553_verified_external_override_cannot_rewind_accepted_source_clock() -> None:
    counter = LineCrossingCounter(CountingLine(), crossing_cooldown_frames=60)
    assert counter.register_external_crossing(5708, "in", 30, (500, 500), mode="direct")
    for frame in (29, 30):
        for direction in ("in", "out"):
            assert not counter.register_external_crossing(
                5708, direction, frame, (510, 500), verified_anchor_span=True,
            )
            assert counter.external_rejection_reason_for(5708) == "stale-source-frame"
            assert counter._tracks[5708].last_count_frame == 30
            assert counter.crossing_point_for(5708) == (500, 500)
    assert counter.total_crossings == 1
    assert counter.verified_same_direction_overrides == counter.verified_cooldown_overrides == 0
    # Stronger measured evidence for a genuinely later passage can still use
    # the existing override even before the ordinary cooldown expires.
    assert counter.register_external_crossing(
        5708, "out", 31, (510, 500), verified_anchor_span=True,
    )
    assert counter.total_crossings == 2
    assert counter.verified_cooldown_overrides == 1


def test_v0553_anchor_alias_merge_keeps_geometry_of_latest_accepted_passage() -> None:
    from app.counting import VerifiedAnchorSpanRescuer

    span = VerifiedAnchorSpanRescuer(CountingLine(), immediate_min_normal_ratio=0.95)
    assert span.update(5709, (450, 460), 1000, 1000, 10, commit=False) is None
    assert span.update(5709, (500, 540), 1000, 1000, 11, commit=False) is None
    # Confirmation can arrive later than a crossing issued by another alias;
    # source geometry must stay attached to the chosen accepted passage clock.
    assert span.update(5709, (510, 550), 1000, 1000, 16, commit=False) is not None
    span.mark_counted(5709, "in", 16)
    source_frame = span.crossing_frame_for(5709)
    assert span.update(5710, (500, 535), 1000, 1000, 13, commit=False) is None
    assert span.update(5710, (500, 465), 1000, 1000, 14, commit=False) is not None
    span.mark_counted(5710, "out", 14)
    assert span.crossing_frame_for(5710) > source_frame
    span.merge_track(5709, 5710)
    assert span.capture_passage_state(5710)[:2] == (frozenset({"in"}), 16)
    assert span.crossing_frame_for(5710) == source_frame


def test_v0552_primary_confirmation_ignores_repeated_and_older_source_frames() -> None:
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5), side_confirm_samples=2,
        fast_confirm_distance_ratio=0.0, bracket_confirm=False, late_geometry_confirm=False,
    )
    assert counter.update(5601, (500, 465), 1000, 1000, 10) is None
    assert counter.update(5601, (500, 520), 1000, 1000, 11) is None
    assert counter.update(5601, (500, 530), 1000, 1000, 11) is None
    assert counter.update(5601, (500, 550), 1000, 1000, 9) is None
    assert counter.total_crossings == 0
    assert counter.update(5601, (500, 550), 1000, 1000, 12) == "in"
    assert counter.total_crossings == 1


def test_v0552_primary_alias_merge_preserves_one_observation_per_frame() -> None:
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5), side_confirm_samples=2,
        fast_confirm_distance_ratio=0.0, bracket_confirm=False, late_geometry_confirm=False,
    )
    assert counter.update(5602, (500, 465), 1000, 1000, 10) is None
    assert counter.update(5602, (500, 520), 1000, 1000, 11) is None
    assert counter.update(5603, (510, 530), 1000, 1000, 11) is None
    counter.merge_track(5603, 5602)
    assert [item.frame_index for item in counter._tracks[5602].history] == [10, 11]
    assert counter._tracks[5602].side_streak == 1
    assert counter.update(5602, (510, 540), 1000, 1000, 11) is None
    assert counter.total_crossings == 0
    assert counter.update(5602, (510, 550), 1000, 1000, 12) == "in"


def test_v0552_all_gate_paths_reject_an_observed_detour_around_finite_endpoint() -> None:
    from app.counting import HeavyVehicleCrossingRescuer, TwoWheelCenterCrossingRescuer, VerifiedAnchorSpanRescuer

    for gate_type in (LineCrossingCounter, VerifiedAnchorSpanRescuer, HeavyVehicleCrossingRescuer, TwoWheelCenterCrossingRescuer):
        gate = gate_type(CountingLine(0.1, 0.5, 0.8, 0.5))
        # Stable endpoints form an apparently perfect normal chord at x=760,
        # but every actually observed gate bracket goes outside the x=800 end.
        points = ((760, 470), (805, 497), (805, 503), (760, 530), (760, 555))
        for frame, point in enumerate(points, 1):
            assert gate.update(5604, point, 1000, 1000, frame) is None, gate_type.__name__
        if isinstance(gate, VerifiedAnchorSpanRescuer):
            assert gate.finalize_lost(5604, 6) is None
            assert gate.verified_anchor_span_rescues == 0
        elif isinstance(gate, LineCrossingCounter):
            assert gate.total_crossings == 0
        else:
            assert gate.rescues == 0


def test_v0552_all_gate_paths_recover_the_actual_neutral_sample_intersection() -> None:
    from app.counting import HeavyVehicleCrossingRescuer, TwoWheelCenterCrossingRescuer, VerifiedAnchorSpanRescuer

    for gate_type in (LineCrossingCounter, VerifiedAnchorSpanRescuer, HeavyVehicleCrossingRescuer, TwoWheelCenterCrossingRescuer):
        gate = gate_type(CountingLine(0.1, 0.5, 0.8, 0.5))
        # The stable endpoint chord lies outside x=800, but the actual neutral
        # observations prove an interior gate crossing at x=760, frame 2.5.
        for frame, point in enumerate(((805, 470), (760, 497), (760, 503)), 1):
            assert gate.update(5605, point, 1000, 1000, frame) is None
        result = gate.update(5605, (805, 530), 1000, 1000, 4)
        if isinstance(gate, VerifiedAnchorSpanRescuer):
            assert result is None
            result = gate.update(5605, (805, 555), 1000, 1000, 5)
        if isinstance(gate, LineCrossingCounter):
            assert result == "in"
            assert gate.crossing_point_for(5605) == (760.0, 500.0)
        else:
            assert result == ("in", (760.0, 500.0)), gate_type.__name__
        assert gate.crossing_frame_for(5605) == pytest.approx(2.5)


def test_v0552_center_rescuers_count_alternating_passages_in_out_in() -> None:
    from app.counting import HeavyVehicleCrossingRescuer, TwoWheelCenterCrossingRescuer

    for gate_type in (HeavyVehicleCrossingRescuer, TwoWheelCenterCrossingRescuer):
        gate = gate_type(CountingLine(0.1, 0.5, 0.9, 0.5))
        assert gate.update(5606, (500, 460), 1000, 1000, 1) is None
        assert gate.update(5606, (500, 540), 1000, 1000, 2)[0] == "in"
        assert gate.update(5606, (500, 460), 1000, 1000, 3)[0] == "out"
        assert gate.update(5606, (500, 540), 1000, 1000, 4)[0] == "in"
        assert gate.rescues == 3
        assert gate.update(5606, (500, 550), 1000, 1000, 5) is None


def test_v0552_center_proposals_remain_retryable_until_primary_accepts() -> None:
    from app.counting import HeavyVehicleCrossingRescuer, TwoWheelCenterCrossingRescuer

    for gate_type in (HeavyVehicleCrossingRescuer, TwoWheelCenterCrossingRescuer):
        gate = gate_type(CountingLine(0.1, 0.5, 0.9, 0.5))
        empty = gate.capture_passage_state(5607)
        assert gate.update(5607, (500, 460), 1000, 1000, 1, commit=False) is None
        assert gate.update(5607, (500, 540), 1000, 1000, 2, commit=False)[0] == "in"
        assert gate.capture_passage_state(5607) == empty
        assert gate.rescues == 0
        assert gate.crossing_frame_for(5607) == pytest.approx(1.5)
        # No accepted primary handoff yet: a later sample must retain the proof.
        assert gate.update(5607, (500, 550), 1000, 1000, 3, commit=False)[0] == "in"
        gate.mark_counted(5607, "in", 3)
        assert gate.rescues == 1
        assert gate.capture_passage_state(5607)[:2] == (frozenset({"in"}), 3)
        assert gate.crossing_frame_for(5607) == pytest.approx(1.5)
        assert gate.update(5607, (500, 560), 1000, 1000, 4, commit=False) is None


def test_v0552_center_guard_rollback_restores_prior_cycle_and_clears_rejected_proof() -> None:
    from app.counting import HeavyVehicleCrossingRescuer, TwoWheelCenterCrossingRescuer

    for gate_type in (HeavyVehicleCrossingRescuer, TwoWheelCenterCrossingRescuer):
        gate = gate_type(CountingLine(0.1, 0.5, 0.9, 0.5))
        assert gate.update(5608, (500, 460), 1000, 1000, 10) is None
        assert gate.update(5608, (500, 540), 1000, 1000, 11)[0] == "in"
        prior = gate.capture_passage_state(5608)
        assert gate.update(5608, (500, 460), 1000, 1000, 20, commit=False)[0] == "out"
        gate.mark_counted(5608, "out", 20)
        assert gate.rescues == 2
        gate.restore_passage_state(5608, prior)
        assert gate.capture_passage_state(5608) == prior
        assert gate.rescues == 1
        gate.restore_passage_state(5608, prior)
        assert gate.rescues == 1
        assert gate.update(5608, (500, 460), 1000, 1000, 21) is None
        assert gate.update(5608, (500, 540), 1000, 1000, 22) is None


def test_v0552_center_alias_merge_keeps_latest_passage_and_unique_frame_evidence() -> None:
    from app.counting import HeavyVehicleCrossingRescuer, TwoWheelCenterCrossingRescuer

    for gate_type in (HeavyVehicleCrossingRescuer, TwoWheelCenterCrossingRescuer):
        gate = gate_type(CountingLine(0.1, 0.5, 0.9, 0.5))
        gate.mark_counted(5609, "out", 10)
        gate.mark_counted(5610, "in", 20)
        assert gate.update(5609, (500, 460), 1000, 1000, 30) is None
        assert gate.update(5610, (510, 460), 1000, 1000, 30) is None
        gate.merge_track(5610, 5609)
        assert gate.capture_passage_state(5609)[:2] == (frozenset({"in"}), 20)
        assert len(gate._tracks[5609].history) == 1
        assert gate.update(5609, (500, 540), 1000, 1000, 30) is None
        assert gate.update(5609, (500, 540), 1000, 1000, 31) is None
        assert gate.update(5609, (500, 460), 1000, 1000, 32)[0] == "out"


def test_v0552_unused_center_candidate_does_not_increment_committed_rescues() -> None:
    from app.counting import HeavyVehicleCrossingRescuer, TwoWheelCenterCrossingRescuer

    for gate_type in (HeavyVehicleCrossingRescuer, TwoWheelCenterCrossingRescuer):
        gate = gate_type(CountingLine(0.1, 0.5, 0.9, 0.5))
        assert gate.update(5611, (500, 460), 1000, 1000, 1, commit=False) is None
        assert gate.update(5611, (500, 540), 1000, 1000, 2, commit=False)[0] == "in"
        # The strict primary gate won; center evidence was not the event source.
        gate.mark_counted(5611, "in", 2, commit_candidate=False)
        assert gate.rescues == 0
        assert gate.capture_passage_state(5611)[:2] == (frozenset({"in"}), 2)
        assert gate.crossing_frame_for(5611) is None


def test_v0551_continuous_approach_recovers_oblique_last_box_only_after_post_confirm() -> None:
    from app.counting import VerifiedAnchorSpanRescuer

    rescue = VerifiedAnchorSpanRescuer(CountingLine(0.1, 0.5, 0.9, 0.5))
    assert rescue.update(5511, (500.0, 465.0), 1000, 1000, 30) is None
    assert rescue.update(5511, (480.0, 493.0), 1000, 1000, 31) is None
    # Last-pair normal motion is 15 / hypot(50, 15) < 0.40. The measured
    # monotone approach passes the same limit over its entire bounded path.
    assert rescue.update(5511, (530.0, 508.0), 1000, 1000, 32) is None
    assert rescue.approach_span_candidates == 1
    assert rescue.immediate_candidate_for(5511) is False
    assert rescue.override_qualified_for(5511) is False
    confirmed = rescue.update(5511, (530.0, 535.0), 1000, 1000, 33)
    assert confirmed is not None and confirmed[0] == "in"
    assert confirmed[1][0] == pytest.approx(480.0 + 50.0 * 7.0 / 15.0)
    assert rescue.crossing_frame_for(5511) == pytest.approx(31.0 + 7.0 / 15.0)
    assert rescue.approach_span_rescues == 1
    assert rescue.post_confirm_closures == 1
    assert rescue.override_qualified_for(5511) is True


def test_v0551_approach_fallback_rejects_reversal_and_total_path_jump() -> None:
    from app.counting import VerifiedAnchorSpanRescuer

    reversing = VerifiedAnchorSpanRescuer(CountingLine(0.1, 0.5, 0.9, 0.5))
    for frame, point in enumerate(((500, 465), (480, 493), (480, 497), (480, 493), (530, 508)), 1):
        assert reversing.update(5512, point, 1000, 1000, frame) is None
    assert reversing.approach_span_candidates == 0

    jumping = VerifiedAnchorSpanRescuer(CountingLine(0.1, 0.5, 0.9, 0.5))
    # The endpoint chord is small, but the observed detour exceeds the unchanged
    # 0.12 diagonal jump bound. Selecting the older chord must not hide it.
    for frame, point in enumerate(((500, 460), (450, 490), (570, 510)), 1):
        assert jumping.update(5513, point, 1000, 1000, frame) is None
    assert jumping.approach_span_candidates == 0


def test_v0551_strong_approach_fallback_still_needs_observed_post_confirmation() -> None:
    from app.counting import VerifiedAnchorSpanRescuer

    rescue = VerifiedAnchorSpanRescuer(CountingLine(0.1, 0.5, 0.9, 0.5))
    assert rescue.update(5530, (500, 440), 1000, 1000, 1) is None
    assert rescue.update(5530, (480, 485), 1000, 1000, 2) is None
    assert rescue.update(5530, (550, 515), 1000, 1000, 3) is None
    assert rescue.approach_span_candidates == 1
    # Aggregate normal motion exceeds 0.55 and side depth exceeds 0.014,
    # but this repaired approach still cannot close merely on disappearance.
    assert rescue.finalize_lost(5530, 4) is None
    assert rescue.lost_track_finalizations == 0
    assert rescue.override_qualified_for(5530) is False
    confirmed = rescue.update(5530, (550, 535), 1000, 1000, 4)
    assert confirmed is not None and confirmed[0] == "in"
    assert rescue.post_confirm_closures == 1
    assert rescue.approach_span_rescues == 1


def test_v0551_approach_fallback_requires_actual_finite_crossing_and_road_path() -> None:
    from app.counting import VerifiedAnchorSpanRescuer

    outside_gate = VerifiedAnchorSpanRescuer(CountingLine(0.1, 0.5, 0.9, 0.5))
    for frame, point in enumerate(((780, 470), (905, 493), (950, 508)), 1):
        assert outside_gate.update(5514, point, 1000, 1000, frame) is None
    assert outside_gate.verified_anchor_span_rescues == 0

    zone = RoadZone(0.49, 0.0, 0.60, 0.0, 0.60, 1.0, 0.49, 1.0)
    outside_road = VerifiedAnchorSpanRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5), road_zone=zone, road_margin_ratio=0.005,
    )
    # An older endpoint-to-endpoint chord lies on the roadway while its actual
    # intermediate box sample leaves it. Every observed anchor must pass ROI.
    for frame, point in enumerate(((500, 465), (480, 493), (530, 508)), 1):
        assert outside_road.update(5515, point, 1000, 1000, frame) is None
    assert outside_road.approach_span_candidates == 0


def test_v0551_post_confirm_requires_distinct_source_frames() -> None:
    from app.counting import VerifiedAnchorSpanRescuer

    rescue = VerifiedAnchorSpanRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5), immediate_min_normal_ratio=0.95,
    )
    assert rescue.update(5516, (450, 460), 1000, 1000, 10) is None
    assert rescue.update(5516, (500, 540), 1000, 1000, 11) is None
    assert rescue.update(5516, (510, 560), 1000, 1000, 11) is None
    assert rescue.override_qualified_for(5516) is False
    assert rescue.update(5516, (510, 560), 1000, 1000, 12)[0] == "in"
    assert rescue.post_confirm_closures == 1


def test_v0551_pending_span_cannot_confirm_from_box_jump_or_outside_road() -> None:
    from app.counting import VerifiedAnchorSpanRescuer

    jumping = VerifiedAnchorSpanRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5), immediate_min_normal_ratio=0.95,
    )
    assert jumping.update(5517, (450, 460), 1000, 1000, 10) is None
    assert jumping.update(5517, (500, 540), 1000, 1000, 11) is None
    # A neutral sample also has to pass the jump guard; it cannot conceal a
    # large alias jump before a later destination confirmation.
    assert jumping.update(5517, (900, 500), 1000, 1000, 12) is None
    assert jumping.update(5517, (900, 550), 1000, 1000, 13) is None
    assert jumping.post_confirm_closures == 0
    assert jumping.finalize_lost(5517, 14) is None

    zone = RoadZone(0.4, 0.0, 0.6, 0.0, 0.6, 1.0, 0.4, 1.0)
    outside_road = VerifiedAnchorSpanRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5), road_zone=zone, immediate_min_normal_ratio=0.95,
    )
    assert outside_road.update(5518, (450, 460), 1000, 1000, 10) is None
    assert outside_road.update(5518, (500, 540), 1000, 1000, 11) is None
    assert outside_road.update(5518, (620, 560), 1000, 1000, 12) is None
    assert outside_road.post_confirm_closures == 0
    assert outside_road.finalize_lost(5518, 13) is None


def test_v0551_track_loss_does_not_close_opposite_side_jitter_without_return() -> None:
    from app.counting import VerifiedAnchorSpanRescuer

    rescue = VerifiedAnchorSpanRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5), immediate_min_normal_ratio=0.95,
    )
    assert rescue.update(5519, (450, 460), 1000, 1000, 10) is None
    assert rescue.update(5519, (500, 540), 1000, 1000, 11) is None
    assert rescue.update(5519, (500, 480), 1000, 1000, 12) is None
    assert rescue.finalize_lost(5519, 13) is None
    assert rescue.lost_track_finalizations == 0
    assert rescue.update(5519, (500, 565), 1000, 1000, 13)[0] == "in"


def test_v0551_span_merge_keeps_latest_passage_clock_and_single_frame_evidence() -> None:
    from app.counting import VerifiedAnchorSpanRescuer

    rescue = VerifiedAnchorSpanRescuer(CountingLine(0.1, 0.5, 0.9, 0.5))
    rescue.mark_counted(5520, "in", 40)
    rescue.mark_counted(5521, "out", 10)
    rescue.merge_track(5520, 5521)
    assert rescue.capture_passage_state(5521)[:2] == (frozenset({"in"}), 40)
    assert rescue.update(5521, (500, 460), 1000, 1000, 50) is None
    assert rescue.update(5521, (500, 540), 1000, 1000, 51) is None
    assert rescue.update(5521, (500, 560), 1000, 1000, 52) is None
    assert rescue.same_direction_overrides == 0


def test_v0551_secondary_semantic_rollback_restores_prior_clock_and_drops_pending() -> None:
    from app.counting import VerifiedAnchorSpanRescuer

    rescue = VerifiedAnchorSpanRescuer(CountingLine(0.1, 0.5, 0.9, 0.5))
    empty = rescue.capture_passage_state(5522)
    rescue.mark_counted(5522, "in", 10)
    prior = rescue.capture_passage_state(5522)
    assert rescue.update(5522, (500, 430), 1000, 1000, 30) is None
    rescue.mark_counted(5522, "out", 31)
    rescue.restore_passage_state(5522, prior)
    assert rescue.capture_passage_state(5522) == prior
    assert rescue.finalize_lost(5522, 32) is None
    assert rescue.update(5522, (500, 570), 1000, 1000, 32) is None
    rescue.restore_passage_state(5522, empty)
    assert rescue.capture_passage_state(5522) == empty


def test_v0551_primary_external_rollback_preserves_prior_passage_and_is_idempotent() -> None:
    counter = LineCrossingCounter(CountingLine(), crossing_cooldown_frames=60)
    assert counter.register_external_crossing(
        5523, "in", 10, (500, 500), mode="direct", crossing_frame=9.5,
    ) is True
    assert counter.register_external_crossing(
        5523, "out", 20, (510, 500), mode="rescued", crossing_frame=19.5,
        verified_anchor_span=True,
    ) is True
    assert counter.revoke_last_crossing(5523, "in") is False
    assert counter.total_crossings == 2
    assert counter.revoke_last_crossing(5523, "out") is True
    assert counter.in_count == 1 and counter.out_count == 0
    assert counter.crossing_point_for(5523) == (500, 500)
    assert counter.crossing_frame_for(5523) == 9.5
    assert counter.crossing_mode_for(5523) == "direct"
    assert counter.direct_crossings == 1 and counter.rescued_crossings == 0
    assert counter.verified_cooldown_overrides == 0
    assert counter._tracks[5523].last_count_frame == 10
    assert counter.revoke_last_crossing(5523, "out") is False
    assert counter.total_crossings == 1
    assert counter.register_external_crossing(5523, "in", 30, (500, 500)) is False
    assert counter.external_rejection_reason_for(5523) == "same-direction"
    assert counter.register_external_crossing(5523, "out", 65, (500, 500)) is False
    assert counter.external_rejection_reason_for(5523) == "cooldown"


def test_v0551_primary_geometry_rollback_keeps_previous_accepted_cycle() -> None:
    counter = LineCrossingCounter(CountingLine())
    assert counter.update(5524, (50, 20), 100, 100, 1) is None
    assert counter.update(5524, (50, 80), 100, 100, 2) == "in"
    prior_frame = counter.crossing_frame_for(5524)
    assert counter.update(5524, (50, 90), 100, 100, 3) is None
    assert counter.update(5524, (50, 20), 100, 100, 4) == "out"
    assert counter.revoke_last_crossing(5524, "out") is True
    assert counter.in_count == 1 and counter.out_count == 0
    assert counter.crossing_frame_for(5524) == prior_frame
    assert counter._tracks[5524].last_count_frame == 2
    # The rejected OUT does not unlock another IN, and its span is not replayed.
    assert counter.update(5524, (50, 20), 100, 100, 5) is None
    assert counter.update(5524, (50, 80), 100, 100, 6) is None
    assert counter.total_crossings == 1


def test_v0551_primary_merge_rollback_preserves_other_alias_prior_passage() -> None:
    counter = LineCrossingCounter(CountingLine())
    assert counter.register_external_crossing(5525, "out", 10, (510, 500), mode="direct") is True
    assert counter.register_external_crossing(5526, "in", 20, (520, 500), mode="rescued") is True
    counter.merge_track(5526, 5525)
    assert counter.crossing_point_for(5525) == (520, 500)
    assert counter.revoke_last_crossing(5525, "in") is True
    assert counter.in_count == 0 and counter.out_count == 1
    assert counter.crossing_point_for(5525) == (510, 500)
    assert counter.crossing_mode_for(5525) == "direct"
    assert counter._tracks[5525].last_count_frame == 10
    assert counter.register_external_crossing(5525, "out", 30, (510, 500)) is False


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




def test_v0541_direction_is_screen_stable_when_gate_endpoints_are_reversed() -> None:
    # Even if a user drags/stores the line right-to-left, top -> bottom must stay IN.
    counter = LineCrossingCounter(CountingLine(0.9, 0.5, 0.1, 0.5))
    assert counter.line.x1 == pytest.approx(0.1)
    assert counter.line.x2 == pytest.approx(0.9)
    assert counter.update(541, (50, 25), 100, 100) is None
    assert counter.update(541, (50, 75), 100, 100) == "in"
    assert counter.in_count == 1

    reverse = LineCrossingCounter(CountingLine(0.9, 0.5, 0.1, 0.5))
    assert reverse.update(542, (50, 75), 100, 100) is None
    assert reverse.update(542, (50, 25), 100, 100) == "out"
    assert reverse.out_count == 1

    # The same screen-direction contract also holds for a slanted gate.
    slanted = LineCrossingCounter(CountingLine(0.8, 0.45, 0.2, 0.55))
    assert slanted.update(543, (50, 25), 100, 100) is None
    assert slanted.update(543, (50, 75), 100, 100) == "in"
    assert slanted.in_count == 1


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


def test_crossing_engine_v72_bracket_confirm_accepts_strong_finite_crossing() -> None:
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        side_confirm_samples=2,
        fast_confirm_distance_ratio=0.0,
        bracket_confirm=True,
        bracket_confirm_min_normal_ratio=0.55,
        bracket_confirm_max_gap_frames=2,
        startup_grace_frames=0,
    )
    assert counter.update(1201, (50, 44), 100, 100, 10) is None
    assert counter.update(1201, (50, 56), 100, 100, 11) == "in"
    assert counter.bracket_confirm_rescues == 1


def test_crossing_engine_v72_bracket_confirm_does_not_accept_parallel_jitter() -> None:
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        side_confirm_samples=2,
        fast_confirm_distance_ratio=0.0,
        bracket_confirm=True,
        bracket_confirm_min_normal_ratio=0.80,
        bracket_confirm_max_gap_frames=2,
        startup_grace_frames=0,
    )
    assert counter.update(1202, (15, 49), 100, 100, 10) is None
    # Large lateral movement with only a tiny normal component must stay rejected.
    assert counter.update(1202, (85, 51), 100, 100, 11) is None
    assert counter.bracket_confirm_rescues == 0


def test_v0528_video_origin_rescue_counts_vehicle_already_straddling_gate() -> None:
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        startup_grace_frames=0,
        origin_rescue_frames=20,
        origin_rescue_distance_ratio=0.065,
        origin_rescue_min_normal_ratio=0.30,
    )
    # The normal motion-leading anchor is already beyond the line when ByteTrack
    # first assigns an ID, but the box centre is still straddling the gate.
    assert counter.update(1301, (50, 80), 100, 100, 3, origin_probe=(50, 52)) is None
    assert counter.update(1301, (50, 84), 100, 100, 4, origin_probe=(50, 62)) == "in"
    assert counter.origin_rescues == 1
    assert counter.in_count == 1


def test_v0528_video_origin_rescue_rejects_track_that_started_far_from_gate() -> None:
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        origin_rescue_frames=20,
        origin_rescue_distance_ratio=0.065,
        origin_rescue_min_normal_ratio=0.30,
    )
    assert counter.update(1302, (50, 80), 100, 100, 3, origin_probe=(50, 70)) is None
    assert counter.update(1302, (50, 86), 100, 100, 4, origin_probe=(50, 82)) is None
    assert counter.origin_rescues == 0


def test_v0528_video_origin_rescue_rejects_parallel_startup_jitter() -> None:
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        origin_rescue_frames=20,
        origin_rescue_distance_ratio=0.065,
        origin_rescue_min_normal_ratio=0.30,
    )
    assert counter.update(1303, (20, 80), 100, 100, 3, origin_probe=(20, 51)) is None
    assert counter.update(1303, (80, 82), 100, 100, 4, origin_probe=(80, 53)) is None
    assert counter.origin_rescues == 0


def test_v0529_heavy_center_rescue_recovers_large_van_when_primary_anchor_misses() -> None:
    from app.counting import HeavyVehicleCrossingRescuer

    zone = RoadZone(0.10, 0.0, 0.90, 0.0, 0.95, 1.0, 0.05, 1.0)
    rescue = HeavyVehicleCrossingRescuer(
        CountingLine(0.20, 0.50, 0.80, 0.50),
        road_zone=zone,
        history_gap_frames=90,
        min_normal_ratio=0.20,
        road_margin_ratio=0.02,
    )
    assert rescue.update(1501, (50, 28), 100, 100, 10) is None
    result = rescue.update(1501, (52, 78), 100, 100, 45)
    assert result is not None
    direction, point = result
    assert direction == "in"
    assert 20 <= point[0] <= 80
    assert rescue.rescues == 1


def test_v0529_external_heavy_rescue_marks_primary_counter_to_prevent_duplicate() -> None:
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        crossing_cooldown_frames=60,
    )
    assert counter.update(1502, (50, 20), 100, 100, 10) is None
    assert counter.register_external_crossing(1502, "in", 20, (50, 50), mode="rescued") is True
    assert counter.in_count == 1
    assert counter.rescued_crossings == 1
    # The normal anchor later crosses, but the same direction is already known.
    assert counter.update(1502, (50, 80), 100, 100, 21) is None
    assert counter.in_count == 1


def test_v0530_merge_track_preserves_preline_history_for_four_wheel_alias() -> None:
    line = CountingLine(0.2, 0.5, 0.8, 0.5)
    counter = LineCrossingCounter(line, side_confirm_samples=1, crossing_cooldown_frames=0)
    assert counter.update(10, (500.0, 350.0), 1000, 800, frame_index=10) is None
    # A cross-class duplicate was already alive as another canonical ID on the
    # opposite side; neither ID alone has a complete trajectory.
    assert counter.update(20, (500.0, 430.0), 1000, 800, frame_index=11) is None
    counter.merge_track(10, 20)
    direction = counter.update(20, (500.0, 460.0), 1000, 800, frame_index=12)
    assert direction in {"in", "out"}


def test_v0531_crossing_frame_is_interpolated_at_physical_gate_intersection() -> None:
    counter = LineCrossingCounter(CountingLine(0.1, 0.5, 0.9, 0.5), side_confirm_samples=1)
    assert counter.update(1601, (50, 20), 100, 100, 100) is None
    assert counter.update(1601, (50, 80), 100, 100, 120) == "in"
    crossing_frame = counter.crossing_frame_for(1601)
    assert crossing_frame is not None
    assert abs(crossing_frame - 110.0) < 1e-6


def test_v0531_heavy_rescue_exposes_interpolated_crossing_frame() -> None:
    from app.counting import HeavyVehicleCrossingRescuer

    rescue = HeavyVehicleCrossingRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        history_gap_frames=90,
        min_normal_ratio=0.20,
    )
    assert rescue.update(1602, (50, 20), 100, 100, 200) is None
    assert rescue.update(1602, (50, 80), 100, 100, 240) is not None
    crossing_frame = rescue.crossing_frame_for(1602)
    assert crossing_frame is not None
    assert abs(crossing_frame - 220.0) < 1e-6


def test_v0531_external_crossing_preserves_geometric_source_frame() -> None:
    counter = LineCrossingCounter(CountingLine(0.1, 0.5, 0.9, 0.5))
    assert counter.register_external_crossing(1603, "out", 260, (50, 50), mode="rescued", crossing_frame=251.25)
    assert abs((counter.crossing_frame_for(1603) or 0.0) - 251.25) < 1e-6


def test_v0532_direct_crossing_keeps_observed_frame() -> None:
    from app.counting import select_event_crossing_frame
    frame, corrected, clamped = select_event_crossing_frame(100, 99.1, "direct")
    assert frame == 100.0
    assert not corrected
    assert not clamped


def test_v0532_interpolated_time_sync_is_bounded() -> None:
    from app.counting import select_event_crossing_frame
    frame, corrected, clamped = select_event_crossing_frame(100, 80.0, "interpolated", max_interpolated_shift_frames=6)
    assert frame == 94.0
    assert corrected and clamped


def test_v0532_rescue_time_sync_clamps_long_gap() -> None:
    from app.counting import select_event_crossing_frame
    frame, corrected, clamped = select_event_crossing_frame(100, 60.0, "rescued", max_rescued_shift_frames=18)
    assert frame == 82.0
    assert corrected and clamped


def test_v0532_short_rescue_keeps_geometric_time() -> None:
    from app.counting import select_event_crossing_frame
    frame, corrected, clamped = select_event_crossing_frame(100, 88.0, "rescued", max_rescued_shift_frames=18)
    assert frame == 88.0
    assert corrected and not clamped


def test_v0534_two_wheel_center_rescue_accepts_strong_finite_crossing() -> None:
    from app.counting import TwoWheelCenterCrossingRescuer

    road = RoadZone(0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0)
    rescue = TwoWheelCenterCrossingRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        road_zone=road,
        history_gap_frames=12,
        min_normal_ratio=0.42,
        max_jump_ratio=0.50,
        min_side_distance_ratio=0.006,
        segment_edge_ratio=0.04,
    )
    assert rescue.update(501, (50, 35), 100, 100, 1) is None
    result = rescue.update(501, (51, 68), 100, 100, 3)
    assert result is not None
    assert result[0] == "in"
    assert rescue.crossing_mode_for(501) == "interpolated"


def test_v0534_two_wheel_center_rescue_rejects_line_parallel_jitter() -> None:
    from app.counting import TwoWheelCenterCrossingRescuer

    road = RoadZone(0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0)
    rescue = TwoWheelCenterCrossingRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5), road_zone=road, min_normal_ratio=0.55
    )
    assert rescue.update(502, (20, 48), 100, 100, 1) is None
    assert rescue.update(502, (82, 52), 100, 100, 2) is None
    assert rescue.rescues == 0


def test_v0534_two_wheel_center_rescue_rejects_endpoint_crossing() -> None:
    from app.counting import TwoWheelCenterCrossingRescuer

    road = RoadZone(0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0)
    rescue = TwoWheelCenterCrossingRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        road_zone=road,
        segment_edge_ratio=0.08,
        max_jump_ratio=0.50,
    )
    assert rescue.update(503, (11, 30), 100, 100, 1) is None
    assert rescue.update(503, (11, 70), 100, 100, 2) is None
    assert rescue.rescues == 0


def test_v0534_two_wheel_center_rescue_rejects_long_jump() -> None:
    from app.counting import TwoWheelCenterCrossingRescuer

    road = RoadZone(0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0)
    rescue = TwoWheelCenterCrossingRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        road_zone=road,
        max_jump_ratio=0.10,
        min_normal_ratio=0.2,
    )
    assert rescue.update(504, (15, 20), 100, 100, 1) is None
    assert rescue.update(504, (85, 80), 100, 100, 2) is None
    assert rescue.rejected_jump == 1


def test_v0541_verified_anchor_span_immediate_recovery_is_strict_secondary_gate():
    from app.counting import CountingLine, VerifiedAnchorSpanRescuer
    rescue = VerifiedAnchorSpanRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        min_normal_ratio=0.40,
        immediate_min_normal_ratio=0.68,
        min_side_distance_ratio=0.006,
        immediate_min_side_distance_ratio=0.012,
    )
    assert rescue.update(7, (500, 460), 1000, 1000, 1) is None
    result = rescue.update(7, (500, 540), 1000, 1000, 2)
    assert result is not None and result[0] == "in"
    assert rescue.verified_anchor_span_rescues == 1
    assert rescue.post_confirm_closures == 0


def test_v0541_post_confirm_closure_waits_for_later_destination_sample():
    from app.counting import CountingLine, VerifiedAnchorSpanRescuer
    rescue = VerifiedAnchorSpanRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        min_normal_ratio=0.35,
        immediate_min_normal_ratio=0.95,
        post_confirm_samples=2,
    )
    assert rescue.update(8, (480, 485), 1000, 1000, 10) is None
    assert rescue.update(8, (500, 515), 1000, 1000, 11) is None
    result = rescue.update(8, (515, 535), 1000, 1000, 12)
    assert result is not None and result[0] == "in"
    assert rescue.post_confirm_closures == 1


def test_v0541_verified_anchor_span_rejects_line_parallel_motion():
    from app.counting import CountingLine, VerifiedAnchorSpanRescuer
    rescue = VerifiedAnchorSpanRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        min_normal_ratio=0.60,
    )
    assert rescue.update(9, (100, 490), 1000, 1000, 1) is None
    assert rescue.update(9, (900, 510), 1000, 1000, 2) is None
    assert rescue.rejected_validation >= 1


def test_v0541_verified_anchor_span_mark_counted_prevents_secondary_duplicate():
    from app.counting import CountingLine, VerifiedAnchorSpanRescuer
    rescue = VerifiedAnchorSpanRescuer(CountingLine(0.1, 0.5, 0.9, 0.5))
    rescue.mark_counted(10, "in")
    assert rescue.update(10, (500, 460), 1000, 1000, 1) is None
    assert rescue.update(10, (500, 540), 1000, 1000, 2) is None


def test_v0543_post_confirm_tolerates_one_opposite_jitter_sample():
    from app.counting import CountingLine, VerifiedAnchorSpanRescuer
    rescue = VerifiedAnchorSpanRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        min_normal_ratio=0.35, immediate_min_normal_ratio=0.95,
        post_confirm_samples=2, post_confirm_opposite_samples=2,
    )
    assert rescue.update(4301, (480, 485), 1000, 1000, 10) is None
    assert rescue.update(4301, (500, 515), 1000, 1000, 11) is None
    # One tracker-box bounce must not cancel a geometry-proven pending span.
    assert rescue.update(4301, (500, 484), 1000, 1000, 12) is None
    result = rescue.update(4301, (500, 535), 1000, 1000, 13)
    assert result is not None and result[0] == "in"
    assert rescue.post_confirm_jitter_holds == 1
    assert rescue.post_confirm_closures == 1


def test_v0543_post_confirm_still_rejects_sustained_opposite_return():
    from app.counting import CountingLine, VerifiedAnchorSpanRescuer
    rescue = VerifiedAnchorSpanRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        min_normal_ratio=0.35, immediate_min_normal_ratio=0.95,
        post_confirm_samples=2, post_confirm_opposite_samples=2,
    )
    assert rescue.update(4302, (480, 485), 1000, 1000, 10) is None
    assert rescue.update(4302, (500, 515), 1000, 1000, 11) is None
    assert rescue.update(4302, (500, 484), 1000, 1000, 12) is None
    assert rescue.update(4302, (500, 480), 1000, 1000, 13) is None
    assert rescue.post_confirm_jitter_holds == 1
    assert rescue.post_confirm_closures == 0


def test_v0543_anchor_span_allows_tiny_road_corridor_calibration_edge_only():
    from app.counting import CountingLine, RoadZone, VerifiedAnchorSpanRescuer
    # Road polygon ends at x=0.50. Crossing at x=0.504 is outside strict ROI but
    # inside the dedicated 0.006 secondary-rescue margin.
    zone = RoadZone(0.10, 0.0, 0.50, 0.0, 0.50, 1.0, 0.10, 1.0)
    rescue = VerifiedAnchorSpanRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5), road_zone=zone,
        road_margin_ratio=0.010, road_corridor_margin_ratio=0.006,
        min_normal_ratio=0.40, immediate_min_normal_ratio=0.68,
    )
    assert rescue.update(4303, (504, 480), 1000, 1000, 1) is None
    result = rescue.update(4303, (504, 540), 1000, 1000, 2)
    assert result is not None and result[0] == "in"
    assert rescue.road_edge_span_rescues == 1


def test_v0543_same_track_can_count_same_direction_on_a_later_passage_cycle():
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        dead_band_ratio=0.01, rearm_distance_ratio=0.10,
        crossing_cooldown_frames=5, startup_grace_frames=0,
    )
    assert counter.update(4304, (50, 20), 100, 100, 10) is None
    assert counter.update(4304, (50, 80), 100, 100, 11) == "in"
    assert counter.update(4304, (50, 90), 100, 100, 12) is None
    # Keep the same canonical ID alive beyond cooldown while well away.
    assert counter.update(4304, (50, 90), 100, 100, 16) is None
    # A genuine loop crosses OUT, then later IN again under the same track ID.
    assert counter.update(4304, (50, 20), 100, 100, 17) == "out"
    assert counter.update(4304, (50, 10), 100, 100, 23) is None
    assert counter.update(4304, (50, 80), 100, 100, 24) == "in"
    assert counter.in_count == 2
    assert counter.out_count == 1
    assert counter.passage_cycle_rearms >= 2


def test_v0544_adaptive_rearm_waits_minimum_frames_before_releasing_passage_cycle():
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        dead_band_ratio=0.01,
        rearm_distance_ratio=0.10,
        crossing_cooldown_frames=60,
        adaptive_cooldown=True,
        cooldown_release_ratio=0.20,
        passage_rearm_min_frames=10,
        startup_grace_frames=0,
    )
    assert counter.update(4401, (50, 20), 100, 100, 1) is None
    assert counter.update(4401, (50, 80), 100, 100, 2) == "in"
    # Move well away immediately. V0.5.43 could clear the passage here because
    # the release distance was already reached; V0.5.44 must hold it.
    assert counter.update(4401, (50, 95), 100, 100, 3) is None
    assert counter._tracks[4401].counted_directions == {"in"}
    # A fast bounce back through the line remains inside the protected interval.
    assert counter.update(4401, (50, 20), 100, 100, 4) is None
    assert counter.rejected_cooldown >= 1
    assert counter._tracks[4401].counted_directions == {"in"}


def test_v0545_long_gap_rescue_tail_requires_stronger_normal_motion():
    line = CountingLine(0.1, 0.5, 0.9, 0.5)
    normal_rescue = LineCrossingCounter(
        line,
        history_gap_frames=20,
        interpolation_gap_frames=3,
        min_perpendicular_ratio=0.10,
        rescue_strict_gap_frames=5,
        rescue_strict_min_normal_ratio=0.50,
        rescue_strict_max_jump_ratio=0.90,
        rescue_strict_min_side_distance_ratio=0.05,
    )
    assert normal_rescue.update(4501, (10, 40), 100, 100, 1) is None
    # Gap == strict threshold: retain the V0.5.44 rescue behaviour.
    assert normal_rescue.update(4501, (90, 60), 100, 100, 6) == "in"
    assert normal_rescue.rejected_long_gap_rescue == 0

    strict_tail = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        history_gap_frames=20,
        interpolation_gap_frames=3,
        min_perpendicular_ratio=0.10,
        rescue_strict_gap_frames=5,
        rescue_strict_min_normal_ratio=0.50,
        rescue_strict_max_jump_ratio=0.90,
        rescue_strict_min_side_distance_ratio=0.05,
    )
    assert strict_tail.update(4502, (10, 40), 100, 100, 1) is None
    # Same geometry but one frame deeper into the long-gap tail: base gate would
    # accept it, V0.5.45 rejects because motion is mostly parallel to the gate.
    assert strict_tail.update(4502, (90, 60), 100, 100, 7) is None
    assert strict_tail.rejected_long_gap_rescue == 1
    assert strict_tail.rejected_rescue_validation == 1


def test_v0546_passage_cycle_requires_opposite_crossing_before_same_direction_recount():
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        dead_band_ratio=0.01,
        rearm_distance_ratio=0.10,
        crossing_cooldown_frames=5,
        passage_rearm_min_frames=5,
        startup_grace_frames=0,
    )
    assert counter.update(4601, (50, 20), 100, 100, 1) is None
    assert counter.update(4601, (50, 80), 100, 100, 2) == "in"

    # Bounce back while the gate is still disarmed. This is not a confirmed OUT
    # traversal and therefore must not unlock a second IN event.
    assert counter.update(4601, (50, 20), 100, 100, 3) is None
    assert counter.update(4601, (50, 20), 100, 100, 7) is None
    assert counter._tracks[4601].armed is True
    assert counter._tracks[4601].counted_directions == {"in"}
    assert counter.update(4601, (50, 80), 100, 100, 8) is None
    assert counter.rejected_same_direction_cycle == 1
    assert counter.in_count == 1

    # A real opposite traversal closes the previous cycle and makes a later IN
    # eligible again under the same canonical tracking ID.
    assert counter.update(4601, (50, 20), 100, 100, 9) == "out"
    assert counter.update(4601, (50, 10), 100, 100, 14) is None
    assert counter.update(4601, (50, 80), 100, 100, 15) == "in"
    assert counter.in_count == 2
    assert counter.out_count == 1


def test_v0546_external_crossing_keeps_only_latest_passage_direction():
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        crossing_cooldown_frames=0,
    )
    assert counter.register_external_crossing(4602, "in", 10, (50.0, 50.0)) is True
    assert counter.register_external_crossing(4602, "in", 20, (50.0, 50.0)) is False
    assert counter.rejected_same_direction_cycle == 1
    assert counter.register_external_crossing(4602, "out", 30, (50.0, 50.0)) is True
    assert counter._tracks[4602].counted_directions == {"out"}
    assert counter.register_external_crossing(4602, "in", 40, (50.0, 50.0)) is True


def test_v0547_verified_anchor_span_can_override_same_direction_only_after_post_confirm():
    from app.counting import CountingLine, LineCrossingCounter, VerifiedAnchorSpanRescuer

    line = CountingLine(0.1, 0.5, 0.9, 0.5)
    counter = LineCrossingCounter(line, crossing_cooldown_frames=60)
    rescue = VerifiedAnchorSpanRescuer(
        line,
        min_normal_ratio=0.40,
        immediate_min_normal_ratio=0.95,
        same_direction_min_frames=16,
        post_confirm_samples=2,
    )
    assert counter.register_external_crossing(4701, "in", 10, (500.0, 500.0)) is True
    rescue.mark_counted(4701, "in", 10)

    assert rescue.update(4701, (450, 460), 1000, 1000, 30) is None
    assert rescue.update(4701, (500, 540), 1000, 1000, 31) is None
    candidate = rescue.update(4701, (510, 565), 1000, 1000, 32)
    assert candidate is not None and candidate[0] == "in"
    assert rescue.same_direction_overrides == 1
    assert rescue.override_qualified_for(4701) is True

    direction, crossing = candidate
    assert counter.register_external_crossing(
        4701, direction, 32, crossing, verified_anchor_span=True,
        crossing_frame=rescue.crossing_frame_for(4701),
    ) is True
    assert counter.verified_same_direction_overrides == 1
    assert counter.verified_cooldown_overrides == 1


def test_v0547_unverified_external_crossing_cannot_bypass_precision_closure():
    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5), crossing_cooldown_frames=60
    )
    assert counter.register_external_crossing(4702, "in", 10, (50.0, 50.0)) is True
    assert counter.register_external_crossing(4702, "in", 32, (50.0, 50.0)) is False
    assert counter.rejected_same_direction_cycle == 1
    assert counter.verified_same_direction_overrides == 0
    assert counter.verified_cooldown_overrides == 0


def test_v0547_track_loss_finalizes_only_strong_geometry_proven_pending_span():
    from app.counting import CountingLine, VerifiedAnchorSpanRescuer

    rescue = VerifiedAnchorSpanRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        min_normal_ratio=0.40,
        immediate_min_normal_ratio=0.95,
        lost_finalize_min_normal_ratio=0.55,
        lost_finalize_min_side_distance_ratio=0.014,
        post_confirm_max_gap_frames=6,
    )
    assert rescue.update(4703, (450, 460), 1000, 1000, 20) is None
    assert rescue.update(4703, (500, 540), 1000, 1000, 21) is None
    finalized = rescue.finalize_lost(4703, 22)
    assert finalized is not None and finalized[0] == "in"
    assert rescue.lost_track_finalizations == 1
    assert rescue.override_qualified_for(4703) is True

    weak = VerifiedAnchorSpanRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        min_normal_ratio=0.40,
        immediate_min_normal_ratio=0.95,
        lost_finalize_min_normal_ratio=0.80,
        lost_finalize_min_side_distance_ratio=0.014,
    )
    assert weak.update(4704, (400, 480), 1000, 1000, 20) is None
    assert weak.update(4704, (500, 520), 1000, 1000, 21) is None
    assert weak.finalize_lost(4704, 22) is None
    assert weak.lost_track_finalizations == 0



def test_v0549_immediate_verified_span_does_not_bypass_primary_cooldown():
    from app.counting import CountingLine, LineCrossingCounter, VerifiedAnchorSpanRescuer

    line = CountingLine(0.1, 0.5, 0.9, 0.5)
    counter = LineCrossingCounter(line, crossing_cooldown_frames=60)
    rescue = VerifiedAnchorSpanRescuer(
        line,
        min_normal_ratio=0.40,
        immediate_min_normal_ratio=0.68,
        immediate_min_side_distance_ratio=0.012,
    )

    assert counter.register_external_crossing(4901, "out", 10, (500.0, 500.0)) is True
    rescue.mark_counted(4901, "out", 10)
    assert rescue.update(4901, (500.0, 430.0), 1000, 1000, 30) is None
    candidate = rescue.update(4901, (500.0, 570.0), 1000, 1000, 31)
    assert candidate is not None and candidate[0] == "in"
    assert rescue.immediate_candidate_for(4901) is True
    assert rescue.override_qualified_for(4901) is False

    direction, crossing = candidate
    accepted = counter.register_external_crossing(
        4901, direction, 31, crossing, mode="rescued",
        crossing_frame=rescue.crossing_frame_for(4901),
        verified_anchor_span=rescue.override_qualified_for(4901),
    )
    rescue.note_immediate_handoff_result(4901, accepted)
    assert accepted is False
    assert counter.external_rejection_reason_for(4901) == "cooldown"
    assert rescue.immediate_handoff_rejections == 1
    assert rescue.verified_anchor_span_rescues == 0
    assert counter.verified_cooldown_overrides == 0

    # The rejected immediate hand-off must stay fail-closed for that frame but
    # preserve its geometry-proven pending span. A distinct destination-side
    # observation can still earn the stronger Post-Confirm override.
    confirmed = rescue.update(4901, (500.0, 585.0), 1000, 1000, 32)
    assert confirmed is not None and confirmed[0] == "in"
    assert rescue.override_qualified_for(4901) is True
    assert rescue.post_confirm_closures == 1
    direction2, crossing2 = confirmed
    assert counter.register_external_crossing(
        4901, direction2, 32, crossing2, mode="rescued",
        crossing_frame=rescue.crossing_frame_for(4901), verified_anchor_span=True,
    ) is True
    assert counter.verified_cooldown_overrides == 1


def test_v0549_lineage_long_gap_waits_for_destination_confirmation_or_strong_geometry():
    from app.counting import CountingLine, LineCrossingCounter

    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        history_gap_frames=20, interpolation_gap_frames=3,
        rescue_min_normal_ratio=0.20, rescue_max_jump_ratio=0.40, rescue_min_side_distance_ratio=0.002,
        lineage_rescue_guard=True, lineage_rescue_min_normal_ratio=0.80,
        lineage_rescue_max_jump_ratio=0.12, lineage_rescue_min_side_distance_ratio=0.018,
        lineage_rescue_confirm_samples=2,
    )
    # Oblique stitched rescue: first destination sample is held, second confirms.
    assert counter.update(4902, (420.0, 470.0), 1000, 1000, 10, lineage_size=2) is None
    assert counter.update(4902, (620.0, 530.0), 1000, 1000, 16, lineage_size=2) is None
    assert counter.rejected_lineage_rescue == 1
    assert counter.update(4902, (630.0, 545.0), 1000, 1000, 17, lineage_size=2) == "in"

    strong = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        history_gap_frames=20, interpolation_gap_frames=3,
        rescue_min_normal_ratio=0.20, rescue_max_jump_ratio=0.40, rescue_min_side_distance_ratio=0.002,
        lineage_rescue_guard=True, lineage_rescue_min_normal_ratio=0.70,
        lineage_rescue_max_jump_ratio=0.18, lineage_rescue_min_side_distance_ratio=0.014,
        lineage_rescue_confirm_samples=2,
    )
    assert strong.update(4903, (500.0, 420.0), 1000, 1000, 10, lineage_size=2) is None
    assert strong.update(4903, (500.0, 580.0), 1000, 1000, 16, lineage_size=2) == "in"
    assert strong.rejected_lineage_rescue == 0


def test_v0548_immediate_override_stays_fail_closed_for_weak_span():
    from app.counting import CountingLine, VerifiedAnchorSpanRescuer

    rescue = VerifiedAnchorSpanRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        min_normal_ratio=0.40,
        immediate_min_normal_ratio=0.90,
        immediate_min_side_distance_ratio=0.020,
    )
    assert rescue.update(4802, (420.0, 480.0), 1000, 1000, 10) is None
    # Valid finite span, but too shallow/oblique for immediate self-confirmation.
    assert rescue.update(4802, (580.0, 520.0), 1000, 1000, 11) is None
    assert rescue.override_qualified_for(4802) is False
    assert rescue.immediate_override_qualifications == 0


def test_v0550_late_geometry_confirm_recovers_short_gap_after_full_geometry_audit():
    from app.counting import CountingLine, LineCrossingCounter

    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        interpolation_gap_frames=3,
        side_confirm_samples=2,
        bracket_confirm=True,
        bracket_confirm_min_normal_ratio=0.55,
        bracket_confirm_max_gap_frames=2,
        late_geometry_confirm=True,
        late_geometry_confirm_min_normal_ratio=0.48,
        late_geometry_confirm_max_jump_ratio=0.08,
        late_geometry_confirm_min_side_distance_ratio=0.008,
        late_geometry_confirm_max_gap_frames=3,
    )
    assert counter.update(5501, (500.0, 470.0), 1000, 1000, 10) is None
    # Gap 3 is outside the older bracket-confirm window, but the finite segment,
    # side depth, jump and normal motion are all strong enough for the late audit.
    assert counter.update(5501, (500.0, 530.0), 1000, 1000, 13) == "in"
    assert counter.late_geometry_confirms == 1
    assert counter.rejected_unconfirmed_side == 0


def test_v0550_late_geometry_confirm_stays_fail_closed_for_oblique_jitter():
    from app.counting import CountingLine, LineCrossingCounter

    counter = LineCrossingCounter(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        interpolation_gap_frames=3,
        side_confirm_samples=2,
        bracket_confirm=False,
        late_geometry_confirm=True,
        late_geometry_confirm_min_normal_ratio=0.48,
        late_geometry_confirm_max_jump_ratio=0.20,
        late_geometry_confirm_min_side_distance_ratio=0.008,
        late_geometry_confirm_max_gap_frames=3,
    )
    assert counter.update(5502, (400.0, 490.0), 1000, 1000, 20) is None
    assert counter.update(5502, (600.0, 510.0), 1000, 1000, 23) is None
    assert counter.late_geometry_confirms == 0
    assert counter.rejected_unconfirmed_side == 1
