from app.runtime import PipelineState


def test_each_pipeline_state_starts_with_fresh_session_counters() -> None:
    first = PipelineState(camera_id=1, session_id=10)
    first.total_count = 7
    first.in_count = 4
    first.out_count = 3
    first.counts_by_type["car"] = 5

    second = PipelineState(camera_id=1, session_id=11)
    assert second.total_count == 0
    assert second.in_count == 0
    assert second.out_count == 0
    assert second.counts_by_type == {
        "motorcycle": 0,
        "bicycle": 0,
        "car": 0,
        "bus": 0,
        "truck": 0,
        "other": 0,
    }
    assert first.counts_by_type is not second.counts_by_type
