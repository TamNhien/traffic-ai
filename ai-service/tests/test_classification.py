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
