from app.classification import TrackLabelSmoother, VehicleClassPolicy


def test_track_label_smoothing_resists_one_frame_bus_truck_flip() -> None:
    smoother = TrackLabelSmoother(history=10)
    for confidence in (0.82, 0.88, 0.79, 0.84):
        smoother.update(1, "truck", confidence)
    smoother.update(1, "bus", 0.91)
    label, certainty, hits = smoother.stable_label(1, "bus")
    assert label == "truck"
    assert hits == 4
    assert certainty > 0.6


def test_bicycle_requires_repeated_strong_bicycle_evidence() -> None:
    policy = VehicleClassPolicy(bicycle_certainty=0.75, bicycle_hits=4)
    label, _ = policy.final_label("bicycle", "bicycle", 0.82, 5, ("bicycle", 0.71))
    assert label == "bicycle"


def test_ambiguous_bicycle_defaults_to_motorcycle() -> None:
    policy = VehicleClassPolicy(bicycle_certainty=0.75, bicycle_hits=4)
    label, _ = policy.final_label("bicycle", "bicycle", 0.62, 2, ("motorcycle", 0.58))
    assert label == "motorcycle"


def test_heavy_vehicle_refiner_can_correct_bus_truck_flip() -> None:
    policy = VehicleClassPolicy()
    label, confidence = policy.final_label("bus", "bus", 0.61, 3, ("truck", 0.73))
    assert label == "truck"
    assert confidence >= 0.73


def test_display_suppresses_weak_bicycle_flip_as_motorcycle() -> None:
    policy = VehicleClassPolicy(bicycle_certainty=0.80, bicycle_hits=5)
    assert policy.display_label("bicycle", "bicycle", 0.64, 2, 0.77) == "motorcycle"


def test_display_allows_repeated_strong_bicycle_evidence() -> None:
    policy = VehicleClassPolicy(bicycle_certainty=0.80, bicycle_hits=5)
    assert policy.display_label("bicycle", "bicycle", 0.91, 7, 0.84) == "bicycle"


def test_very_strong_primary_bicycle_can_survive_without_refiner() -> None:
    policy = VehicleClassPolicy(strong_bicycle_certainty=0.90, strong_bicycle_hits=8)
    label, _ = policy.final_label("bicycle", "bicycle", 0.94, 10, None)
    assert label == "bicycle"


def test_target_refiner_ignores_high_confidence_neighbor() -> None:
    from app.classification import RefineCandidate, select_target_refinement

    target = (40.0, 40.0, 140.0, 180.0)
    candidates = [
        # Unrelated parked motorcycle in the same expanded crop.
        RefineCandidate("motorcycle", 0.96, (170.0, 45.0, 250.0, 170.0)),
        # Lower-confidence target-matched bicycle.
        RefineCandidate("bicycle", 0.66, (46.0, 48.0, 136.0, 176.0)),
    ]
    match = select_target_refinement(target, candidates)
    assert match is not None
    assert match.label == "bicycle"
    assert match.confidence == 0.66


def test_refiner_can_rescue_bicycle_from_motorcycle_biased_primary() -> None:
    policy = VehicleClassPolicy(bicycle_refine_override_conf=0.58)
    label, confidence = policy.final_label(
        "motorcycle", "motorcycle", 0.96, 18, ("bicycle", 0.66)
    )
    assert label == "bicycle"
    assert confidence >= 0.96


def test_target_refiner_can_promote_small_car_shaped_truck() -> None:
    policy = VehicleClassPolicy(truck_refine_override_conf=0.48)
    label, confidence = policy.final_label(
        "car", "car", 0.94, 24, ("truck", 0.53)
    )
    assert label == "truck"
    assert confidence >= 0.94


def test_weak_truck_refiner_does_not_override_stable_car() -> None:
    policy = VehicleClassPolicy(truck_refine_override_conf=0.48)
    label, _ = policy.final_label("car", "car", 0.94, 24, ("truck", 0.31))
    assert label == "car"


def test_target_refiner_stays_inside_target_vehicle_family() -> None:
    from app.classification import RefineCandidate, select_target_refinement

    target = (40.0, 40.0, 180.0, 190.0)
    candidates = [
        RefineCandidate("motorcycle", 0.97, (45.0, 45.0, 175.0, 185.0)),
        RefineCandidate("truck", 0.56, (48.0, 47.0, 178.0, 188.0)),
    ]
    match = select_target_refinement(target, candidates, target_family="four-wheel")
    assert match is not None
    assert match.label == "truck"


def test_target_refiner_rejects_unrelated_neighbor_only() -> None:
    from app.classification import RefineCandidate, select_target_refinement

    target = (40.0, 40.0, 140.0, 180.0)
    candidates = [RefineCandidate("motorcycle", 0.99, (180.0, 40.0, 260.0, 170.0))]
    assert select_target_refinement(target, candidates, target_family="two-wheel") is None


def test_v0527_consensus_requires_distinct_frames() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(history_frames=120)
    evidence.update(7, 100, "bicycle", 0.55, "domain")
    evidence.update(7, 100, "bicycle", 0.65, "general")
    hits, fused, strongest = evidence.support(7, 100, "bicycle")
    assert hits == 1
    assert strongest == 0.65
    assert fused == 0.65
    assert evidence.minority_consensus(7, 100, "motorcycle", min_hits=2, bicycle_confidence=0.60) is None


def test_v0527_repeated_low_bicycle_evidence_can_rescue_motorcycle_track() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(history_frames=120)
    evidence.update(11, 200, "bicycle", 0.38, "general")
    evidence.update(11, 210, "bicycle", 0.39, "general")
    result = evidence.minority_consensus(
        11, 210, "motorcycle", min_hits=2, bicycle_confidence=0.60
    )
    assert result is not None
    assert result[0] == "bicycle"
    assert result[1] >= 0.60


def test_v0527_repeated_low_truck_evidence_can_rescue_car_track() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(history_frames=120)
    evidence.update(12, 300, "truck", 0.31, "domain")
    evidence.update(12, 320, "truck", 0.35, "general")
    result = evidence.minority_consensus(
        12, 320, "car", min_hits=2, truck_confidence=0.52
    )
    assert result is not None
    assert result[0] == "truck"
    assert result[1] >= 0.52


def test_v0527_single_weak_truck_guess_does_not_promote_car() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(history_frames=120)
    evidence.update(13, 400, "truck", 0.44, "general")
    assert evidence.minority_consensus(13, 400, "car", min_hits=2, truck_confidence=0.52) is None


def test_v0529_bicycle_consensus_requires_extra_distinct_frame_when_configured() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(history_frames=120)
    evidence.update(77, 100, "bicycle", 0.48, "general")
    evidence.update(77, 110, "bicycle", 0.49, "domain")
    assert evidence.minority_consensus(
        77,
        110,
        "motorcycle",
        min_hits=2,
        bicycle_confidence=0.60,
        bicycle_min_hits=3,
        bicycle_margin=0.08,
        bicycle_min_strongest=0.34,
    ) is None
    evidence.update(77, 120, "bicycle", 0.50, "general")
    result = evidence.minority_consensus(
        77,
        120,
        "motorcycle",
        min_hits=2,
        bicycle_confidence=0.60,
        bicycle_min_hits=3,
        bicycle_margin=0.08,
        bicycle_min_strongest=0.34,
    )
    assert result is not None
    assert result[0] == "bicycle"


def test_v0529_bicycle_consensus_rejects_when_motorcycle_refiner_support_is_similar() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(history_frames=120)
    for frame, bike, moto in [(100, 0.42, 0.46), (110, 0.44, 0.47), (120, 0.45, 0.48)]:
        evidence.update(88, frame, "bicycle", bike, "domain")
        evidence.update(88, frame, "motorcycle", moto, "general")
    assert evidence.minority_consensus(
        88,
        120,
        "motorcycle",
        min_hits=2,
        bicycle_confidence=0.60,
        bicycle_min_hits=3,
        bicycle_margin=0.08,
        bicycle_min_strongest=0.34,
    ) is None


def test_v0530_truck_semantic_lock_holds_through_closeup_car_flip() -> None:
    from app.classification import TruckSemanticLock

    lock = TruckSemanticLock(ttl_frames=450, min_refiner_hits=2, min_refiner_confidence=0.62)
    assert lock.observe(286423, 21815, stable_label="truck", certainty=0.93, hits=6) == ("truck", 0.93)
    # Same physical van is COCO-car shaped 262 frames later while crossing.
    assert lock.resolve(286423, 22077, "car") == ("truck", 0.93)


def test_v0530_truck_semantic_lock_requires_durable_evidence() -> None:
    from app.classification import TruckSemanticLock

    lock = TruckSemanticLock(ttl_frames=450, min_refiner_hits=2, min_refiner_confidence=0.62)
    assert lock.observe(7, 100, stable_label="car", certainty=0.95, hits=20, refiner_hits=1, refiner_confidence=0.61) is None
    assert lock.resolve(7, 120, "car") is None
