from app.human_guard import human_dominates_two_wheel_candidate, is_person_like_two_wheel_box


def test_tall_pedestrian_box_can_be_screened() -> None:
    assert is_person_like_two_wheel_box((100, 100, 160, 240)) is True


def test_person_dominating_motorcycle_candidate_is_rejected() -> None:
    decision = human_dominates_two_wheel_candidate(
        (100, 100, 160, 240),
        "motorcycle",
        0.52,
        (102, 98, 159, 242),
        0.83,
        vehicle_evidence_confidence=0.14,
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
