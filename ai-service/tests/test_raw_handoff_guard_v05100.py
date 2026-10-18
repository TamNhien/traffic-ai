"""Causal raw-owner handoff guard regression, not GT-score optimization."""
from app.raw_handoff_guard import RawHandoffCrossingGuard


def box(x=840, y=310):
    return (x, y, x + 70, y + 95)


def candidate(g, raw=222, owner=20, frame=12306, x=.598516, y=.421222,
              direction='out', method='direct'):
    return g.duplicate_of(raw, owner, frame, direction, x, y, crossing_method=method)


def setup_handoff():
    g = RawHandoffCrossingGuard()
    g.observe(111, 10, 12299, box())
    g.note_passage(10, 12299, 'out', .607788, .419125)
    g.observe(222, 10, 12304, box())
    g.observe(222, 20, 12305, box(838, 305))
    return g


def test_session199_49192_raw_handoff_is_a_strict_duplicate_candidate():
    g = setup_handoff()
    evidence = candidate(g)
    assert evidence['former_canonical_id'] == 10
    assert evidence['current_canonical_id'] == 20
    assert evidence['shared_raw_track_id'] == 222
    assert evidence['frame_delta'] == 7
    assert g.suppressed == 1
    assert candidate(g) is None  # single consumption


def test_two_independent_close_vehicles_stay_counted_without_shared_raw_id():
    g = setup_handoff()
    assert candidate(g, raw=333) is None
    assert g.suppressed == 0


def test_opposite_direction_counts_new_passage():
    g = setup_handoff()
    assert candidate(g, direction='in') is None


def test_distant_crossing_point_is_distinct_passage():
    g = setup_handoff()
    assert candidate(g, x=.68) is None
    assert candidate(g, y=.50) is None


def test_box_footprints_must_overlap_on_actual_raw_handoff():
    g = RawHandoffCrossingGuard()
    g.observe(222, 10, 12304, box())
    g.note_passage(10, 12299, 'out', .607788, .419125)
    g.observe(222, 20, 12305, box(1050, 310))
    assert candidate(g) is None


def test_stale_raw_handoff_is_not_a_duplicate():
    g = RawHandoffCrossingGuard()
    g.observe(222, 10, 12300, box())
    g.note_passage(10, 12299, 'out', .607788, .419125)
    g.observe(222, 20, 12306, box())
    assert candidate(g) is None


def test_stale_passage_is_not_a_duplicate():
    g = RawHandoffCrossingGuard()
    g.note_passage(10, 12290, 'out', .607788, .419125)
    g.observe(222, 10, 12304, box())
    g.observe(222, 20, 12305, box())
    assert candidate(g) is None


def test_rescued_candidate_does_not_trigger_suppression():
    g = setup_handoff()
    assert candidate(g, method='rescued') is None


def test_same_canonical_handoff_is_not_evidence():
    g = RawHandoffCrossingGuard()
    g.observe(222, 10, 12304, box())
    g.note_passage(10, 12299, 'out', .607788, .419125)
    g.observe(222, 10, 12305, box())
    assert candidate(g, owner=10) is None


def test_bad_coords_missing_or_nonfinite_do_not_suppress():
    g = setup_handoff()
    assert candidate(g, x=None) is None
    assert candidate(g, x=float('nan')) is None
    assert candidate(g, y=-1) is None


def test_delayed_different_vehicle_reusing_raw_can_be_counted():
    g = setup_handoff()
    assert candidate(g, frame=12323) is None


def test_808_case_uses_second_crossing_not_distant_first_one():
    g = RawHandoffCrossingGuard()
    g.note_passage(368014, 20201, 'out', .709556, .396113)
    g.observe(368646, 368014, 20218, box())
    g.note_passage(368014, 20219, 'out', .608216, .419028)
    g.observe(368646, 368646, 20220, box(838, 307))
    evidence = g.duplicate_of(368646, 368646, 20221, 'out', .612214, .418124,
                              crossing_method='direct')
    assert evidence is not None
    assert evidence['former_canonical_id'] == 368014
