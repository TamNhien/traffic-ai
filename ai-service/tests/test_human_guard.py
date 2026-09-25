from app.human_guard import (
    HumanGuardTrackPolicy,
    human_dominates_two_wheel_candidate,
    is_person_like_two_wheel_box,
    nearby_two_wheel_support,
)


def test_tall_pedestrian_box_can_be_screened() -> None:
    assert is_person_like_two_wheel_box((100, 100, 160, 240)) is True


def test_person_dominating_motorcycle_candidate_is_rejected() -> None:
    decision = human_dominates_two_wheel_candidate(
        (100, 100, 160, 240),
        "motorcycle",
        0.52,
        (102, 98, 159, 242),
        0.83,
        vehicle_evidence_confidence=0.04,
        nearby_vehicle_evidence_confidence=0.0,
        speed_ratio=0.0005,
    )
    assert decision.reject is True
    assert decision.reason == "person_dominates_two_wheel"


def test_rider_with_competitive_motorcycle_evidence_is_kept() -> None:
    decision = human_dominates_two_wheel_candidate(
        (100, 100, 210, 250),
        "motorcycle",
        0.64,
        (125, 95, 185, 220),
        0.88,
        vehicle_evidence_confidence=0.84,
    )
    assert decision.reject is False


def test_wide_motorcycle_box_is_not_rejected_by_human_guard() -> None:
    decision = human_dominates_two_wheel_candidate(
        (100, 130, 250, 240),
        "motorcycle",
        0.50,
        (140, 100, 205, 230),
        0.91,
        vehicle_evidence_confidence=0.10,
    )
    assert decision.reject is False


def test_nearby_motorcycle_below_person_rescues_real_rider() -> None:
    # Mirrors the supplied camera archive: PERSON evidence is tall, while the
    # scooter body sits below the rider and only weakly overlaps the target.
    decision = human_dominates_two_wheel_candidate(
        (100, 70, 165, 220),
        "motorcycle",
        0.42,
        (102, 68, 163, 218),
        0.86,
        vehicle_evidence_confidence=0.04,
        nearby_vehicle_evidence_confidence=0.62,
        speed_ratio=0.0035,
    )
    assert decision.reject is False
    assert decision.rider_supported is True
    assert decision.reason == "rider_evidence"


def test_weak_nearby_noise_does_not_rescue_pedestrian() -> None:
    decision = human_dominates_two_wheel_candidate(
        (100, 70, 165, 220),
        "motorcycle",
        0.40,
        (101, 69, 164, 221),
        0.88,
        vehicle_evidence_confidence=0.02,
        nearby_vehicle_evidence_confidence=0.05,
        speed_ratio=0.0008,
    )
    assert decision.reject is True
    assert decision.rider_supported is False


def test_nearby_two_wheel_support_requires_lower_close_vehicle() -> None:
    target = (100, 80, 160, 220)
    assert nearby_two_wheel_support(target, (90, 170, 180, 280), 400, 400) is True
    assert nearby_two_wheel_support(target, (250, 170, 340, 280), 400, 400) is False
    assert nearby_two_wheel_support(target, (95, 0, 170, 60), 400, 400) is False


def test_track_policy_needs_temporal_confirmation_for_pedestrian() -> None:
    policy = HumanGuardTrackPolicy(required_strikes=2)
    decision = human_dominates_two_wheel_candidate(
        (100, 100, 160, 240), "motorcycle", 0.45, (101, 99, 160, 241), 0.62,
        vehicle_evidence_confidence=0.02, nearby_vehicle_evidence_confidence=0.0, speed_ratio=0.0009,
    )
    assert decision.reject is True
    assert decision.hard_reject is False
    assert policy.observe(7, decision) == "pending"
    assert policy.is_rejected(7) is False
    assert policy.observe(7, decision) == "rejected"
    assert policy.is_rejected(7) is True


def test_rider_evidence_can_release_previously_rejected_track() -> None:
    policy = HumanGuardTrackPolicy(required_strikes=1)
    pedestrian = human_dominates_two_wheel_candidate(
        (100, 100, 160, 240), "motorcycle", 0.40, (101, 99, 160, 241), 0.90,
        vehicle_evidence_confidence=0.01, nearby_vehicle_evidence_confidence=0.0, speed_ratio=0.0005,
    )
    assert policy.observe(11, pedestrian) == "rejected"
    rider = human_dominates_two_wheel_candidate(
        (100, 100, 160, 240), "motorcycle", 0.42, (101, 99, 160, 241), 0.84,
        vehicle_evidence_confidence=0.03, nearby_vehicle_evidence_confidence=0.61, speed_ratio=0.003,
    )
    assert policy.observe(11, rider) == "released"
    assert policy.is_rejected(11) is False
    assert policy.is_rider(11) is True
