"""Alias clock hints must belong to the latest accepted passage lifecycle.

All hints below come from real observed geometry through public rescuer APIs.
They can timestamp an independently accepted event, but cannot create a count.
"""
from app.counting import CountingLine, VerifiedAnchorSpanRescuer


def _gate():
    return VerifiedAnchorSpanRescuer(
        CountingLine(0.1, 0.5, 0.9, 0.5),
        max_jump_ratio=0.2,
        post_confirm_max_gap_frames=6,
        clock_reconcile_max_gap_frames=32,
    )


def _pending(gate, track_id=1, start_frame=10):
    assert gate.update(track_id, (500, 470), 1000, 1000, start_frame, commit=False) is None
    assert gate.update(track_id, (500, 530), 1000, 1000, start_frame + 3, commit=False) is None


def _hint(gate, track_id=1, start_frame=10):
    _pending(gate, track_id, start_frame)
    assert gate.update(track_id, (500, 540), 1000, 1000, start_frame + 10, commit=False) is None


def _rescues(gate):
    return (
        gate.verified_anchor_span_rescues, gate.post_confirm_closures,
        gate.lost_track_finalizations, gate.immediate_override_qualifications,
        gate.same_direction_overrides, gate.cooldown_overrides,
        gate.approach_span_rescues, gate.road_edge_span_rescues,
    )


def test_v0598_stale_source_hint_cannot_precede_newer_target_passage():
    gate = _gate()
    _hint(gate)
    gate.mark_counted(2, "out", 18)
    gate.merge_track(1, 2)
    assert gate.reconciliation_crossing_frame_for(2, "in", 22) is None
    assert gate.capture_passage_state(2)[:2] == (frozenset({"out"}), 18)


def test_v0598_stale_target_hint_cannot_precede_newer_source_passage():
    gate = _gate()
    _hint(gate, 2)
    gate.mark_counted(1, "out", 18)
    gate.merge_track(1, 2)
    assert gate.reconciliation_crossing_frame_for(2, "in", 22) is None
    assert gate.capture_passage_state(2)[:2] == (frozenset({"out"}), 18)


def test_v0598_hint_endpoint_equal_to_latest_acceptance_is_obsolete():
    gate = _gate()
    _hint(gate)
    gate.mark_counted(2, "out", 13)
    gate.merge_track(1, 2)
    assert gate.reconciliation_crossing_frame_for(2, "in", 22) is None


def test_v0598_fresh_endpoint_keeps_interpolated_clock_before_confirmation():
    gate = _gate()
    _hint(gate)
    gate.mark_counted(2, "out", 12)
    gate.merge_track(1, 2)
    # The span ended at 13, after acceptance 12. Its geometric crossing 11.5
    # must not be compared to the confirmation clock as though they were equal.
    assert gate.reconciliation_crossing_frame_for(2, "in", 22) == 11.5


def test_v0598_unowned_alias_hint_remains_available_without_prior_passage():
    gate = _gate()
    _hint(gate)
    gate.merge_track(1, 2)
    assert gate.reconciliation_crossing_frame_for(2, "in", 22) == 11.5
    assert gate.capture_passage_state(2)[:2] == (frozenset(), -10_000)


def test_v0598_new_hint_after_older_accepted_passage_remains_available():
    gate = _gate()
    gate.mark_counted(2, "out", 5)
    _hint(gate)
    gate.merge_track(1, 2)
    assert gate.reconciliation_crossing_frame_for(2, "in", 22) == 11.5
    assert gate.capture_passage_state(2)[:2] == (frozenset({"out"}), 5)


def test_v0598_direction_mismatch_does_not_consume_valid_clock_hint():
    gate = _gate()
    _hint(gate)
    assert gate.reconciliation_crossing_frame_for(1, "out", 22) is None
    assert gate.reconciliation_crossing_frame_for(1, "in", 22) == 11.5


def test_v0598_pending_span_clock_after_older_passage_remains_available():
    gate = _gate()
    gate.mark_counted(2, "out", 5)
    _pending(gate)
    gate.merge_track(1, 2)
    assert gate.reconciliation_crossing_frame_for(2, "in", 14) == 11.5
    assert _rescues(gate) == (0,) * 8
    assert gate.capture_passage_state(2)[:2] == (frozenset({"out"}), 5)


def test_v0598_pending_span_ending_before_newer_passage_cannot_supply_clock():
    gate = _gate()
    _pending(gate)
    gate.mark_counted(2, "out", 18)
    gate.merge_track(1, 2)
    assert gate.reconciliation_crossing_frame_for(2, "in", 19) is None
    assert gate.finalize_lost(2, 19, commit=False) is None


def test_v0598_hint_age_boundary_and_expiry_survive_alias_merge():
    gate = _gate()
    _hint(gate)
    gate.merge_track(1, 2)
    assert gate.reconciliation_crossing_frame_for(2, "in", 45) == 11.5
    assert gate.reconciliation_crossing_frame_for(2, "in", 46) is None
    assert gate.reconciliation_crossing_frame_for(2, "in", 45) is None


def test_v0598_merging_missing_aliases_preserves_existing_valid_hint():
    gate = _gate()
    _hint(gate)
    gate.merge_track(404, 1)
    gate.merge_track(405, 406)
    assert gate.reconciliation_crossing_frame_for(1, "in", 22) == 11.5
    assert gate.reconciliation_crossing_frame_for(406, "in", 22) is None
    assert _rescues(gate) == (0,) * 8


def test_v0598_repeated_self_merge_preserves_hint_without_creating_passage():
    gate = _gate()
    _hint(gate)
    before = gate.capture_passage_state(1)
    for _ in range(3):
        gate.merge_track(1, 1)
        assert gate.reconciliation_crossing_frame_for(1, "in", 22) == 11.5
    assert gate.capture_passage_state(1) == before
    assert _rescues(gate) == (0,) * 8


def test_v0598_two_valid_hints_choose_latest_endpoint_in_either_merge_order():
    for source, target in ((1, 2), (2, 1)):
        gate = _gate()
        _hint(gate, 1, 10)
        _hint(gate, 2, 20)
        gate.merge_track(source, target)
        assert gate.reconciliation_crossing_frame_for(target, "in", 32) == 21.5
        assert gate.reconciliation_crossing_frame_for(source, "in", 32) is None
        assert _rescues(gate) == (0,) * 8


def test_v0598_newer_valid_hint_survives_beside_obsolete_alias_hint():
    for source, target in ((1, 2), (2, 1)):
        gate = _gate()
        _hint(gate, 1, 10)
        gate.mark_counted(2, "out", 18)
        _hint(gate, 2, 20)
        gate.merge_track(source, target)
        assert gate.reconciliation_crossing_frame_for(target, "in", 32) == 21.5
        assert gate.capture_passage_state(target)[:2] == (frozenset({"out"}), 18)


def test_v0598_hint_queries_do_not_accept_crossing_or_spend_rescue_telemetry():
    gate = _gate()
    gate.mark_counted(2, "out", 5)
    _hint(gate)
    gate.merge_track(1, 2)
    passage_before = gate.capture_passage_state(2)
    telemetry_before = _rescues(gate)
    for frame in (22, 23, 24):
        assert gate.reconciliation_crossing_frame_for(2, "in", frame) == 11.5
        assert gate.finalize_lost(2, frame, commit=False) is None
        assert not gate.override_qualified_for(2)
    assert gate.capture_passage_state(2) == passage_before
    assert _rescues(gate) == telemetry_before == (0,) * 8


def test_v0598_rejecting_old_hint_keeps_later_genuine_crossing_countable():
    gate = _gate()
    _hint(gate)
    gate.mark_counted(2, "out", 18)
    gate.merge_track(1, 2)
    assert gate.reconciliation_crossing_frame_for(2, "in", 22) is None
    assert gate.update(2, (500, 470), 1000, 1000, 30, commit=False) is None
    assert gate.update(2, (500, 530), 1000, 1000, 34, commit=False) is None
    assert gate.update(2, (500, 540), 1000, 1000, 35, commit=False) == ("in", (500, 500))
    gate.mark_counted(2, "in", 35)
    assert gate.capture_passage_state(2)[:2] == (frozenset({"in"}), 35)
    assert gate.crossing_frame_for(2) == 32.0
    assert gate.post_confirm_closures == gate.verified_anchor_span_rescues == 1
