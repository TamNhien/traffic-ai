"""Read-only gate decision provenance must never change accepted crossings."""
from app.counting import CountingLine, LineCrossingCounter


def _gate(**kwargs):
    return LineCrossingCounter(CountingLine(.2,.5,.8,.5),**kwargs)


def test_primary_reason_is_current_frame_only():
    gate=_gate()
    assert gate.primary_decision_for(7) is None
    assert gate.update(7,(50,30),100,100,frame_index=1) is None
    assert gate.primary_decision_for(7,1)=='no-opposite-side-observation'
    assert gate.primary_decision_for(7,2) is None
    assert gate.update(7,(50,70),100,100,frame_index=2)=='in'
    assert gate.primary_decision_for(7,2)=='primary-accepted'
    assert gate.in_count==1 and gate.out_count==0


def test_decision_duplicate_observation_is_not_counted_twice():
    gate=_gate()
    gate.update(7,(50,30),100,100,frame_index=1)
    assert gate.update(7,(50,70),100,100,frame_index=1) is None
    assert gate.primary_decision_for(7,1)=='duplicate-frame-observation'
    assert gate.in_count==0


def test_accepted_event_remains_accepted_without_diagnostic_side_effect():
    gate=_gate()
    gate.update(7,(50,30),100,100,frame_index=1)
    assert gate.update(7,(50,70),100,100,frame_index=2)=='in'
    for _ in range(5): assert gate.primary_decision_for(7,2)=='primary-accepted'
    assert gate.in_count==1 and gate.out_count==0


def test_off_finite_gate_is_a_review_reason_not_a_crossing():
    gate=_gate()
    gate.update(9,(10,30),100,100,frame_index=1)
    assert gate.update(9,(10,70),100,100,frame_index=2) is None
    assert gate.primary_decision_for(9,2)=='outside-finite-gate'
    assert gate.in_count==0


def test_startup_and_deadband_are_separate_from_failures():
    gate=_gate(startup_grace_frames=2)
    assert gate.update(2,(50,30),100,100,frame_index=1) is None
    assert gate.primary_decision_for(2,1)=='startup-grace'
    assert gate.update(2,(50,50),100,100,frame_index=3) is None
    assert gate.primary_decision_for(2,3)=='inside-dead-band'
    assert gate.in_count==0


def test_original_strict_gate_behavior_unchanged():
    observed=_gate()
    for frame,y in enumerate([30,40,55,70],start=1):
        observed.update(30,(50,y),100,100,frame_index=frame)
    assert observed.in_count==1
    assert observed.out_count==0
