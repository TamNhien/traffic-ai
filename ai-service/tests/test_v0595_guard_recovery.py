"""Recorded opinion replay; model inference and full-clip F1 are outside this test.

The trace stores PERSON IoU/coverage but no PERSON rectangle. Inject only these
recorded geometry metrics; execute the real decision predicate, policy and worker
cache. A placeholder PERSON rectangle is not a reconstructed model detection.
"""
import json
from pathlib import Path
from types import SimpleNamespace

from app import human_guard
from app.human_guard import HumanGuardDecision, HumanGuardTrackPolicy, human_dominates_two_wheel_candidate
from app.worker import PipelineWorker


def _recording():
    return json.loads((Path(__file__).parent / "fixtures/human-guard-recovery-v0595.json").read_text())


def _recorded_decision(monkeypatch, sample):
    evidence = sample["audit"]["decision"]
    monkeypatch.setattr(human_guard, "box_iou", lambda *_args: evidence["overlap_iou"])
    monkeypatch.setattr(human_guard, "coverage_of_target", lambda *_args: evidence["target_coverage"])
    target = tuple(sample["target_rect"])
    decision = human_dominates_two_wheel_candidate(
        target, sample["target_label"], sample["target_confidence"],
        target if evidence["person_detected"] else None,
        evidence["person_confidence"], evidence["vehicle_confidence"],
        evidence["nearby_vehicle_confidence"], evidence["speed_ratio"],
    )
    decision.audit_evidence = dict(evidence)
    return decision


def _worker():
    worker = PipelineWorker.__new__(PipelineWorker)
    worker._human_guard_policy = HumanGuardTrackPolicy(required_strikes=2)
    worker._human_guard_last_check = {}
    worker._human_guard_last_observation = {}
    worker._human_rider_tracks_seen = set()
    worker._human_guard_model = object()
    worker._human_guard_ids = [0, 3]
    worker.human_guard_check_interval = 8
    worker.state = SimpleNamespace(human_guard_rejections=0, rider_guard_rescues=0)
    return worker


def test_v0595_recorded_rider_releases_old_rejection_and_reuses_source_frame(monkeypatch):
    worker = _worker()
    recording = _recording()
    assert recording["origin"]["session_id"] == 195
    actions, calls = {}, []
    for sample in recording["observations"]:
        frame = sample["frame_index"]
        assert sample["raw_track_id"] == 143399
        assert sample["audit"]["decision_frame_index"] == frame
        assert sample["source_time_seconds"] == (frame - 1) / 25
        decision = _recorded_decision(monkeypatch, sample)

        def verify(*_args, **_kwargs):
            calls.append(frame)
            return decision

        worker._verify_human_candidate = verify
        args = (143399, frame, None, sample["target_rect"], sample["target_label"],
                sample["target_confidence"], "cpu", False)
        # Replay one observed crop per frame. Forced delivery requests may ask
        # again; they must reuse the same semantic decision and policy action.
        action, actual_decision = worker._observe_human_guard(*args, force=True)
        assert actual_decision is decision
        assert worker._observe_human_guard(*args, force=True) == (action, decision)
        actions[frame] = action
    assert actions[9806] == "rejected"
    assert actions[9822] == "released"
    assert actions[9880] == "pending"
    assert actions[9896] == "rider"
    assert actions[9929] == actions[9938] == "rider"
    assert len(calls) == len(set(calls)) == len(recording["observations"])
    assert worker.state.rider_guard_rescues == 1
    assert worker._human_guard_policy.is_rejected(143399) is False
    assert worker._human_guard_policy.is_rider(143399) is True


def test_v0595_recorded_crossing_needs_competing_direct_evidence(monkeypatch):
    samples = {row["frame_index"]: row for row in _recording()["observations"]}
    supported = _recorded_decision(monkeypatch, samples[9929])
    assert supported.rider_supported is True and supported.reason == "rider_evidence"
    assert supported.reject is supported.hard_reject is False
    assert supported.person_confidence == .327637 and supported.vehicle_confidence == .44751
    assert supported.overlap_iou == .304425 and supported.target_coverage == .355148
    # This later crop has motion but noncompetitive direct evidence. It cannot
    # release a rejection by itself; prior positive evidence owns the recovery.
    ambiguous = _recorded_decision(monkeypatch, samples[9938])
    assert ambiguous.rider_supported is False and ambiguous.reject is False
    policy = HumanGuardTrackPolicy(required_strikes=1)
    assert policy.observe(143399, HumanGuardDecision(True), frame_index=9937) == "rejected"
    assert policy.observe(143399, ambiguous, frame_index=9938) == "rejected"


def test_v0595_weak_direct_nearby_and_motion_keep_geometry_neutral():
    policy = HumanGuardTrackPolicy(required_strikes=1)
    assert policy.observe(7, HumanGuardDecision(True), frame_index=1) == "rejected"
    # A tall target with a small PERSON overlap, next to strong nearby bike
    # evidence, cannot use the existing nearby/motion route in this early branch.
    for frame, person, direct in ((2, .90, .80), (3, .10, .19)):
        neutral = human_dominates_two_wheel_candidate(
            (0, 0, 50, 100), "motorcycle", .6, (0, 0, 50, 30), person,
            direct, .95, .02,
        )
        assert neutral.rider_supported is False and neutral.reject is False
        assert policy.observe(7, neutral, frame_index=frame) == "rejected"


def test_v0595_original_missing_person_wide_and_other_class_preconditions_hold():
    for target, label, person in (
        ((0, 0, 50, 100), "motorcycle", None),
        ((0, 0, 100, 50), "motorcycle", (0, 0, 100, 50)),
        ((0, 0, 50, 100), "car", (0, 0, 50, 100)),
    ):
        decision = human_dominates_two_wheel_candidate(target, label, .6, person, .2, .95, .95, .02)
        assert decision.reject is False and decision.rider_supported is False
    pedestrian = human_dominates_two_wheel_candidate(
        (0, 0, 50, 100), "motorcycle", .4, (0, 0, 50, 100), .95, .01, .0, .0,
    )
    assert pedestrian.reject is pedestrian.hard_reject is True
    policy = HumanGuardTrackPolicy(required_strikes=2)
    assert policy.observe(7, pedestrian, frame_index=1) == "pending"
    assert policy.observe(7, pedestrian, frame_index=1) == "pending"
    assert policy.observe(7, pedestrian, frame_index=2) == "rejected"


def test_v0595_invalid_scores_cannot_release_geometry_neutral_rejection():
    for person, direct in (
        (float("nan"), .9), (float("inf"), .9), (float("-inf"), .9),
        (-.1, .9), (1.1, .99), (.3, float("nan")), (.3, float("inf")),
        (.3, float("-inf")), (.3, -.1), (.3, 1.1),
    ):
        policy = HumanGuardTrackPolicy(required_strikes=1)
        assert policy.observe(7, HumanGuardDecision(True), frame_index=1) == "rejected"
        decision = human_dominates_two_wheel_candidate(
            (0, 0, 50, 100), "motorcycle", .6, (0, 0, 50, 30), person,
            direct, .95, .02,
        )
        assert decision.rider_supported is False and decision.reject is False
        assert policy.observe(7, decision, frame_index=2) == "rejected"
