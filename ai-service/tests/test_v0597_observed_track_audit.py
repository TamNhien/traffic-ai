"""Recorded pair/handoff evidence stays separate from all counting decisions."""
import copy
import json
from pathlib import Path

from app import benchmark_trace
from app.observed_track_audit import (
    OBSERVED_FRAME_LIMIT, OBSERVED_PEER_LIMIT, OBSERVED_RECORD_LIMIT, ObservedTrackAudit,
)


def _fixture():
    return json.loads((Path(__file__).parent / "fixtures/observed-tracks-v0597.json").read_text())


def _rows(case):
    return [{"frame_index": row["frame_index"], "source_time_seconds": row["source_time_seconds"],
             "detections": len(row["tracks"]), "tracks": len(row["tracks"]), "road_tracks": len(row["tracks"]),
             "gate_tracks": row["tracks"]} for row in _fixture()[case]["frames"]]


def _track(tid=7, raw=70, rect=None, velocity=None):
    return {"track_id": tid, "raw_track_id": raw, "rect": rect or [0, 0, 20, 40],
            "measured_velocity": velocity if velocity is not None else [1, 2]}


def _row(frame=1, time=1., tracks=None):
    return {"frame_index": frame, "source_time_seconds": time,
            "gate_tracks": tracks if tracks is not None else [_track()]}


def test_v0597_real_nested_pair_retains_observed_frame_gaps_and_no_identity_claim():
    audit = ObservedTrackAudit(181574)
    for row in _rows("duplicate_candidate"):
        audit.observe(row)
    result = audit.finish()
    peer = next(row for row in result["peers"] if row["tracking_id"] == 182056)
    assert result["identity_proven"] is False and peer["identity_proven"] is False
    assert result["target"]["frames"] == 6 and peer["co_visible_frames"] == 5
    assert peer["first_frame"] == 12305 and peer["last_frame"] == 12318
    assert peer["first_time"] == 492.16 and peer["last_time"] == 492.68
    assert peer["max_consecutive_frames"] == 2  # frame gap 12306 -> 12315 breaks the run.
    assert peer["containment_max"] > .9 and peer["nested_frames"] >= 2
    assert peer["raw_track_ids"] == [182056]


def test_v0597_trace_window_excludes_later_evidence_without_new_trace_pass(monkeypatch, tmp_path):
    rows = _rows("duplicate_candidate")
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path)
    benchmark_trace.trace_path(196).write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    original = ObservedTrackAudit.observe
    calls = []

    def observe(self, row):
        calls.append(row["frame_index"])
        original(self, row)

    monkeypatch.setattr(ObservedTrackAudit, "observe", observe)
    item = benchmark_trace.diagnose_trace(196, [491.92], .75, tracking_ids=[181574])["items"][0]
    peer = item["observed_track_audit"]["peers"][0]
    assert calls == [12299, 12305, 12306, 12315, 12316]
    assert peer["co_visible_frames"] == 4 and peer["last_frame"] == 12316
    assert peer["last_time"] == 492.6 and item["time"] == 491.92


def test_v0597_real_handoffs_record_raw_changes_and_gap_without_stitch_identity():
    audit = ObservedTrackAudit(296297)
    for row in _rows("handoff_candidate"):
        audit.observe(row)
    result = audit.finish()
    assert result["identity_proven"] is False
    assert result["target"]["raw_track_ids"] == [312739, 331821, 332237]
    assert [(row["from_raw_track_id"], row["to_raw_track_id"], row["gap_frames"])
            for row in result["raw_id_handoffs"]] == [(312739, 331821, 18), (331821, 332237, 2)]
    assert result["raw_id_handoffs"][0]["from_frame"] == 18842
    assert result["raw_id_handoffs"][0]["to_time"] == 754.36
    assert result["target"]["filtered_velocity"] == [.869998, 8.2191]
    assert result["target"]["rect_motion"]["gap_frames"] == 30


def test_v0597_historical_missing_rectangles_are_unavailable_not_a_negative_finding():
    audit = ObservedTrackAudit(7)
    audit.observe(_row(tracks=[{"track_id": 7, "raw_track_id": 70}]))
    result = audit.finish()
    assert result["status"] == "unavailable" and result["reason"] == "no_valid_rectangles"
    assert result["target"] is None and result["peers"] == [] and result["identity_proven"] is False


def test_v0597_malformed_nonfinite_extreme_and_boolean_inputs_are_ignored():
    audit = ObservedTrackAudit(7)
    for value in [None, [], float("nan"), float("inf"), 10**1000, True, "1"]:
        audit.observe({"frame_index": value, "source_time_seconds": value, "gate_tracks": [_track()]})
        audit.observe(_row(tracks=[_track(rect=[0, 0, value, 4])]))
        audit.observe(_row(tracks=[_track(velocity=[value, 1])]))
    audit.observe(_row(2, 2., [_track(rect=[0, 0, 1e-200, 1e-200])]))
    result = audit.finish()
    assert result["target"]["frames"] == 1
    json.dumps(result, allow_nan=False)


def test_v0597_repeated_frame_does_not_inflate_count_and_conflict_is_disclosed():
    audit = ObservedTrackAudit(7)
    audit.observe(_row())
    audit.observe(_row())
    audit.observe(_row(tracks=[_track(rect=[1, 1, 21, 41])]))
    result = audit.finish()
    assert result["status"] == "unavailable" and result["conflicting_frames"] == 1
    assert result["reason"] == "conflicting_observations" and result["target"] is None
    assert result["peers"] == result["raw_id_handoffs"] == []


def test_v0597_conflicting_repeated_peer_retracts_prior_pair_evidence():
    audit = ObservedTrackAudit(7)
    audit.observe(_row(tracks=[_track(), _track(8, 80)]))
    audit.observe(_row(tracks=[_track(), _track(8, 80, [100, 100, 120, 140])]))
    result = audit.finish()
    assert result["status"] == "unavailable" and result["peers"] == []
    assert result["conflicting_frames"] == 1


def test_v0597_conflicting_same_frame_canonical_aliases_cannot_prove_pair():
    audit = ObservedTrackAudit(7)
    audit.observe(_row(tracks=[_track(), _track(raw=71), _track(8, 80)]))
    result = audit.finish()
    assert result["status"] == "unavailable" and result["conflicting_frames"] == 1
    assert result["peers"] == []


def test_v0597_rect_motion_uses_observed_positions_not_filtered_velocity():
    audit = ObservedTrackAudit(7)
    audit.observe(_row(1, 1., [_track(velocity=[0, 100])]))
    audit.observe(_row(3, 1.1, [_track(rect=[2, -4, 22, 36], velocity=[0, 100])]))
    target = audit.finish()["target"]
    assert target["rect_motion"] == {"dx": 2., "dy": -4., "gap_frames": 2, "pixels_per_frame": [1., -2.]}
    assert target["filtered_velocity"] == [0., 100.]


def test_v0597_pair_counts_include_co_visible_observations_before_overlap():
    audit = ObservedTrackAudit(7)
    audit.observe(_row(1, 1., [_track(), _track(8, 80, [100, 100, 120, 140])]))
    audit.observe(_row(2, 1.04, [_track(), _track(8, 80, [1, 1, 19, 39])]))
    peer = audit.finish()["peers"][0]
    assert peer["co_visible_frames"] == 2 and peer["containment_min"] == 0.
    assert peer["containment_max"] == 1. and peer["max_consecutive_frames"] == 2


def test_v0597_bound_unique_frames_peer_output_and_disclose_truncation():
    audit = ObservedTrackAudit(7)
    for frame in range(1, OBSERVED_FRAME_LIMIT + 4):
        audit.observe(_row(frame, frame / 25., [_track(), *[_track(tid, tid) for tid in range(20, 40)]]))
    result = audit.finish()
    assert result["target"]["frames"] == OBSERVED_FRAME_LIMIT
    assert len(result["peers"]) == OBSERVED_RECORD_LIMIT and result["truncated"] is True
    assert len(audit.peers) == OBSERVED_PEER_LIMIT


def test_v0597_overlapping_peer_can_replace_disjoint_slot_with_truncation():
    audit = ObservedTrackAudit(7)
    audit.observe(_row(1, 1., [_track(), *[_track(tid, tid, [100, 100, 120, 140]) for tid in range(20, 36)]]))
    audit.observe(_row(2, 1.04, [_track(), _track(99, 99, [1, 1, 19, 39])]))
    result = audit.finish()
    assert result["peers"][0]["tracking_id"] == 99 and result["truncated"] is True


def test_v0597_raw_id_change_is_not_inferred_between_different_canonical_tracks():
    audit = ObservedTrackAudit(7)
    audit.observe(_row(1, 1., [_track()]))
    audit.observe(_row(2, 1.04, [_track(8, 80)]))
    result = audit.finish()
    assert result["target"]["frames"] == 1 and result["raw_id_handoffs"] == []


def test_v0597_out_of_order_rows_are_disclosed_without_backward_handoff():
    audit = ObservedTrackAudit(7)
    audit.observe(_row(3, 3., [_track(raw=73)]))
    audit.observe(_row(1, 1., [_track(raw=71)]))
    result = audit.finish()
    assert result["out_of_order_frames"] == 1 and result["raw_id_handoffs"] == []
    assert result["target"]["first_frame"] == 1 and result["target"]["last_frame"] == 3


def test_v0597_review_evidence_does_not_mutate_input_rows_or_share_output_records():
    rows = _rows("duplicate_candidate")
    before = copy.deepcopy(rows)
    audit = ObservedTrackAudit(181574)
    for row in rows:
        audit.observe(row)
    first = audit.finish()
    first["peers"][0]["tracking_id"] = 0
    first["target"]["filtered_velocity"][0] = 999
    first["peers"][0]["peer_filtered_velocity"][0] = 999
    assert audit.finish()["peers"][0]["tracking_id"] == 182056
    assert audit.finish()["target"]["filtered_velocity"][0] != 999
    assert audit.finish()["peers"][0]["peer_filtered_velocity"][0] != 999
    assert rows == before
