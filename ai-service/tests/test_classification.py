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
