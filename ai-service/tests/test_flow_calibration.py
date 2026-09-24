import pytest

from app.flow_calibration import FlowCalibrator


def test_flow_calibrator_proposes_road_corridor_and_perpendicular_line():
    c = FlowCalibrator(history_frames=2000)
    # Synthetic two-way traffic moving diagonally down-right/up-left inside a corridor.
    for track_id in range(1, 9):
        lane = -0.09 if track_id % 2 else 0.08
        reverse = track_id > 4
        for i in range(18):
            t = i / 17
            if reverse:
                t = 1 - t
            x = 0.28 + 0.44 * t + lane
            y = 0.18 + 0.66 * t - lane * 0.18
            c.add(track_id, (x * 1000, y * 700), 1000, 700, frame_index=track_id * 30 + i)

    stats = c.stats()
    assert stats["ready"] is True
    assert stats["moving_track_count"] >= 8
    result = c.proposal()
    g = result["geometry"]
    assert result["quality"] > 0.35
    assert result["moving_track_count"] == 8
    assert all(0 <= g[key] <= 1 for key in g)

    # Proposed count line should be much more perpendicular than parallel to flow.
    line_dx = g["line_x2"] - g["line_x1"]
    line_dy = g["line_y2"] - g["line_y1"]
    flow = result["dominant_direction"]
    dot = abs(line_dx * flow["x"] + line_dy * flow["y"])
    line_mag = max((line_dx**2 + line_dy**2) ** 0.5, 1e-6)
    assert dot / line_mag < 0.2


def test_flow_calibrator_rejects_insufficient_motion():
    c = FlowCalibrator()
    for track_id in range(2):
        for i in range(4):
            c.add(track_id, (100 + i, 100 + i), 1000, 700, frame_index=i)
    assert c.stats()["ready"] is False
    with pytest.raises(ValueError, match="Chưa đủ dữ liệu"):
        c.proposal()
