from app.classification import TrackLabelSmoother


def test_track_label_smoothing_resists_one_frame_bus_truck_flip() -> None:
    smoother = TrackLabelSmoother(history=10)
    for confidence in (0.82, 0.88, 0.79, 0.84):
        smoother.update(1, "truck", confidence)
    smoother.update(1, "bus", 0.91)
    label, certainty, hits = smoother.stable_label(1, "bus")
    assert label == "truck"
    assert hits == 5
    assert certainty > 0.6
