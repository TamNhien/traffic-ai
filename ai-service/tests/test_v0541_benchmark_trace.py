import json


def test_v0559_streaming_trace_skips_malformed_records_without_losing_valid_rows(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    bt.trace_path(90).write_text('null\n[]\n1\n{invalid\n{"source_time_seconds":10,"detections":1,"tracks":1,"road_tracks":1}\n')
    item = bt.diagnose_trace(90, [10.0])["items"][0]
    assert item["max_det"] == item["max_track"] == item["max_road"] == 1
    assert item["reason"] == "crossing_gate_miss"


def test_v0559_duplicate_windows_share_observation_work_and_return_independent_items(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    _write_trace_scope_rows(bt, 91, [{"source_time_seconds":10,"detections":1,"tracks":1,"road_tracks":1}])
    original = bt._TraceWindow.observe
    calls = []

    def observe(self, row):
        calls.append(self.target)
        original(self, row)

    monkeypatch.setattr(bt._TraceWindow, "observe", observe)
    items = bt.diagnose_trace(91, [10.0] * 5000)["items"]
    assert len(items) == 5000 and calls == [10.0]
    assert items[0] == items[-1] and items[0] is not items[-1]
    assert items[0]["gate_span_audit"] is not items[-1]["gate_span_audit"]


def test_v0559_unordered_trace_refreshes_only_selected_context_keys_without_reordering(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    proposals = [{"kind":"bicycle_context", "track_id":i, "frame_index":250, "commit_status":"pending"} for i in range(10)]
    latest = [{**proposals[2], "commit_status":"accepted"}, {**proposals[9], "commit_status":"expired"}]
    rows = [{"source_time_seconds":12, "bicycle_xframe_decision_audit": [latest[0]]},
            {"source_time_seconds":10, "detections":1, "tracks":1, "road_tracks":1,
             "bicycle_xframe_decision_audit":proposals},
            {"source_time_seconds":3, "audit_only":True, "bicycle_xframe_decision_audit":latest},
            {"source_time_seconds":20, "bicycle_xframe_decision_audit":[{**proposals[0], "commit_status":"accepted"}]}]
    _write_trace_scope_rows(bt, 92, rows)
    item = bt.diagnose_trace(92, [10])["items"][0]
    assert [a["track_id"] for a in item["bicycle_context_audit"]] == list(range(2, 10))
    assert item["bicycle_context_audit"][0] == latest[0]
    assert item["bicycle_context_audit"][-1] == latest[-1]
    assert item["max_det"] == 1


def test_v0559_streaming_trace_retains_first_label_and_exact_inclusive_window(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    rows = [{"source_time_seconds":time,"detections":1,"tracks":1,"road_tracks":1,
             "gate_tracks":[{"track_id":4,"label":label,"anchor_signed":signed,"center_signed":signed}]}
            for time, label, signed in [(9.5,"bicycle",-0.02),(10.5,"motorcycle",0.02),(10.6,"truck",1.0)]]
    _write_trace_scope_rows(bt, 93, rows)
    item = bt.diagnose_trace(93, [10], window_seconds=0.5, tracking_ids=[4])["items"][0]
    geometry = item["gate_span_audit"]["anchor_span"][0]
    assert geometry["label"] == "bicycle" and geometry["anchor_max"] == 0.02
    assert item["reason"] == "crossing_anchor_span_reject"


def _write_trace_scope_rows(bt, session_id, rows):
    bt.trace_path(session_id).write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_v0557_unidentified_neighbor_span_is_time_window_evidence(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    rows = [{"source_time_seconds": time, "detections": 2, "tracks": 1, "road_tracks": 1,
             "gate_tracks": [{"track_id": 5, "label": "motorcycle", "anchor_signed": signed,
                              "center_signed": signed}]}
            for time, signed in [(9.9, -0.02), (10.1, 0.02)]]
    _write_trace_scope_rows(bt, 82, rows)
    item = bt.diagnose_trace(82, [10.0])["items"][0]
    # This motorcycle's span does not identify a missed bicycle in the same
    # time window. Preserve the diagnostic hint, mark its actual provenance.
    assert item["reason"] == "crossing_anchor_span_reject"
    assert item["gate_span_audit"]["anchor_span"][0]["track_id"] == 5
    assert item["diagnosis_scope"] == {
        "reason": "nearby_time_window", "geometry": "nearby_time_window",
        "counters": "frame_global", "tracking_id": None,
    }
    assert item["gate_span_audit"]["geometry_scope"] == "nearby_time_window"


def test_v0557_matched_geometry_filters_neighbor_span_before_reason_selection(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    rows = [{"source_time_seconds": time, "detections": 2, "tracks": 2, "road_tracks": 2,
             "gate_tracks": [
                 {"track_id": 4, "label": "bicycle", "anchor_signed": 0.01, "center_signed": 0.03},
                 {"track_id": 5, "label": "motorcycle", "anchor_signed": signed, "center_signed": signed},
             ]} for time, signed in [(9.9, -0.02), (10.1, 0.02)]]
    _write_trace_scope_rows(bt, 83, rows)
    item = bt.diagnose_trace(83, [10.0], tracking_ids=[4])["items"][0]
    assert item["reason"] == "crossing_near_no_span"
    assert item["gate_span_audit"]["anchor_span"] == []
    assert [entry["track_id"] for entry in item["gate_span_audit"]["near_no_span"]] == [4]
    assert item["diagnosis_scope"] == {
        "reason": "matched_track_geometry", "geometry": "matched_track",
        "counters": "frame_global", "tracking_id": 4,
    }
    assert item["gate_span_audit"]["geometry_scope"] == "matched_track"


def test_v0557_frame_global_rejection_reasons_stay_unverified_with_matched_geometry(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    cases = [
        ("detector_miss", {"detections": 0}, {}),
        ("tracker_miss", {"tracks": 0}, {}),
        ("road_zone_reject", {"road_tracks": 0}, {}),
        ("road_zone_reject", {}, {"rejected_outside_road": 1}),
        ("crossing_cooldown_reject", {}, {"rejected_cooldown": 1}),
        ("crossing_confirmation_reject", {}, {"rejected_unconfirmed_side": 1}),
    ]
    for expected_reason, frame_totals, later_counter in cases:
        rows = [{"source_time_seconds": time, "detections": 2, "tracks": 2, "road_tracks": 2,
                 "gate_tracks": [{"track_id": 4, "anchor_signed": signed, "center_signed": signed}],
                 **frame_totals} for time, signed in [(9.9, -0.02), (10.1, 0.02)]]
        rows[-1].update(later_counter)
        _write_trace_scope_rows(bt, 84, rows)
        item = bt.diagnose_trace(84, [10.0], tracking_ids=[4])["items"][0]
        assert item["reason"] == expected_reason
        assert item["gate_span_audit"]["anchor_span"][0]["track_id"] == 4
        assert item["diagnosis_scope"]["geometry"] == "matched_track"
        assert item["diagnosis_scope"]["reason"] == "nearby_time_window"
        assert item["diagnosis_scope"]["counters"] == "frame_global"


def test_v0557_unknown_requested_track_has_no_matched_geometry(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    rows = [{"source_time_seconds": time, "detections": 1, "tracks": 1, "road_tracks": 1,
             "gate_tracks": [{"track_id": 5, "anchor_signed": signed, "center_signed": signed}]}
            for time, signed in [(9.9, -0.02), (10.1, 0.02)]]
    _write_trace_scope_rows(bt, 85, rows)
    item = bt.diagnose_trace(85, [10.0], tracking_ids=[99])["items"][0]
    assert item["reason"] == "crossing_gate_miss"
    assert item["gate_span_audit"]["anchor_span"] == []
    assert item["diagnosis_scope"] == {
        "reason": "nearby_time_window", "geometry": "no_track_evidence",
        "counters": "frame_global", "tracking_id": 99,
    }


def test_v0557_empty_window_does_not_claim_requested_track_evidence(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    assert bt.diagnose_trace(86, [10.0], tracking_ids=[4])["available"] is False
    bt.trace_path(86).write_text("", encoding="utf-8")
    item = bt.diagnose_trace(86, [10.0], tracking_ids=[4])["items"][0]
    assert item["reason"] == "no_trace_window"
    assert item["diagnosis_scope"] == {
        "reason": "no_trace_window", "geometry": "no_track_evidence",
        "counters": "no_trace_window", "tracking_id": 4,
    }
    assert item["gate_span_audit"]["geometry_scope"] == "no_track_evidence"


def test_v0557_audit_only_geometry_does_not_invent_frame_counter_evidence(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    rows = [{"source_time_seconds": time, "audit_only": True,
             "gate_tracks": [{"track_id": 4, "anchor_signed": signed, "center_signed": signed}]}
            for time, signed in [(9.9, -0.02), (10.1, 0.02)]]
    _write_trace_scope_rows(bt, 87, rows)
    item = bt.diagnose_trace(87, [10.0], tracking_ids=[4])["items"][0]
    assert item["reason"] == "no_trace_window"
    assert item["gate_span_audit"]["anchor_span"][0]["track_id"] == 4
    assert item["diagnosis_scope"]["geometry"] == "matched_track"
    assert item["diagnosis_scope"]["reason"] == "no_trace_window"
    assert item["diagnosis_scope"]["counters"] == "no_trace_window"


def test_v0557_far_matched_track_does_not_turn_missing_gate_into_proven_failure(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    _write_trace_scope_rows(bt, 88, [{"source_time_seconds": 10.0,
        "detections": 1, "tracks": 1, "road_tracks": 1,
        "gate_tracks": [{"track_id": 4, "anchor_signed": 0.2, "center_signed": 0.3}]}])
    item = bt.diagnose_trace(88, [10.0], tracking_ids=[4])["items"][0]
    assert item["reason"] == "crossing_gate_miss"
    assert item["diagnosis_scope"]["geometry"] == "matched_track"
    assert item["diagnosis_scope"]["reason"] == "nearby_time_window"
    assert item["diagnosis_scope"]["counters"] == "frame_global"


def test_v0541_gate_span_audit_splits_anchor_center_and_near(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    path = bt.trace_path(77)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"source_time_seconds": 9.9, "detections": 1, "tracks": 1, "road_tracks": 1,
         "rejected_outside_road": 0, "rejected_unconfirmed_side": 0, "rejected_cooldown": 0,
         "road_edge_rescues": 0, "crossing_events": 0,
         "gate_tracks": [{"track_id": 4, "label": "motorcycle", "anchor_signed": -0.02, "center_signed": -0.01}]},
        {"source_time_seconds": 10.1, "detections": 1, "tracks": 1, "road_tracks": 1,
         "rejected_outside_road": 0, "rejected_unconfirmed_side": 0, "rejected_cooldown": 0,
         "road_edge_rescues": 0, "crossing_events": 0,
         "gate_tracks": [{"track_id": 4, "label": "motorcycle", "anchor_signed": 0.02, "center_signed": 0.01}],
         "bicycle_xframe_decision_audit": [{"track_id": 4, "reason": "insufficient_frames", "accepted": False}]},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    item = bt.diagnose_trace(77, [10.0])["items"][0]
    assert item["reason"] == "crossing_anchor_span_reject"
    assert item["gate_span_audit"]["anchor_span"][0]["track_id"] == 4
    assert item["bicycle_xframe_audit"][0]["reason"] == "insufficient_frames"


def test_v0554_context_audit_preserves_source_scores_and_final_guard_status(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    proposal = {"kind": "bicycle_context", "track_id": 4, "frame_index": 250,
                "branch": "temporal", "decision_accepted": True, "commit_status": "pending",
                "observations": [{"frame_index": 249, "source": "general", "bicycle": 0.6, "motorcycle": 0.7}]}
    rejected = {**proposal, "commit_status": "rejected"}
    legacy = {"track_id": 4, "reason": "insufficient_frames", "accepted": False}
    rows = [{"source_time_seconds": 10.0, "bicycle_xframe_decision_audit": [legacy, proposal]},
            {"source_time_seconds": 10.2, "bicycle_xframe_decision_audit": [legacy, proposal, rejected]}]
    bt.trace_path(78).write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    item = bt.diagnose_trace(78, [10.0])["items"][0]
    assert item["bicycle_context_audit"] == [rejected]
    assert item["gate_span_audit"]["bicycle_context_audit"] == [rejected]
    assert all(audit.get("kind") != "bicycle_context" for audit in item["bicycle_xframe_audit"])
    assert rejected["decision_accepted"] is True  # Proposal accepted; guard rejected.
    assert rejected["observations"][0]["motorcycle"] == 0.7


def test_v0554_context_audit_bounds_distinct_decisions_not_repeated_snapshots():
    from app.benchmark_trace import _gate_span_audit
    records = [{"kind": "bicycle_context", "track_id": i, "frame_index": 250,
                "commit_status": "pending"} for i in range(10)]
    accepted = {**records[0], "commit_status": "accepted"}
    rows = [{"bicycle_xframe_decision_audit": records},
            {"bicycle_xframe_decision_audit": records + [accepted] * 12}]
    audit = _gate_span_audit(rows)
    assert [item["track_id"] for item in audit["bicycle_context_audit"]] == list(range(3, 10)) + [0]
    assert audit["bicycle_context_audit"][-1]["commit_status"] == "accepted"
    assert audit["bicycle_xframe_audit"] == []


def test_v0554_eof_audit_only_does_not_invent_cooldown_rejections(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    pending = {"kind": "bicycle_context", "track_id": 4, "frame_index": 250,
               "commit_status": "pending"}
    expired = {**pending, "commit_status": "expired"}
    rows = [{"source_time_seconds": 10.0, "detections": 1, "tracks": 1, "road_tracks": 1,
             "rejected_cooldown": 7, "bicycle_xframe_decision_audit": [pending]},
            {"source_time_seconds": 10.0, "audit_only": True,
             "bicycle_xframe_decision_audit": [expired]}]
    bt.trace_path(79).write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    item = bt.diagnose_trace(79, [10.0])["items"][0]
    assert item["cooldown_reject_delta"] == 0
    assert item["reason"] == "crossing_gate_miss"
    assert item["bicycle_context_audit"] == [expired]
    bt.trace_path(79).write_text(json.dumps(rows[-1]) + "\n")
    audit_only = bt.diagnose_trace(79, [10.0])["items"][0]
    assert audit_only["reason"] == "no_trace_window"
    assert audit_only["bicycle_context_audit"] == [expired]


def test_v0555_matched_track_audit_is_selected_before_dense_scene_limit(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    records = [{"kind": "bicycle_context", "track_id": i, "frame_index": 250,
                "commit_status": "rejected"} for i in range(12)]
    bt.trace_path(80).write_text(json.dumps({"source_time_seconds": 10.0,
        "bicycle_xframe_decision_audit": records}) + "\n")
    result = bt.diagnose_trace(80, [10.0, 10.0], tracking_ids=[0, 11])
    assert [item["bicycle_context_audit"] for item in result["items"]] == [[records[0]], [records[11]]]
    unknown = bt.diagnose_trace(80, [10.0])["items"][0]
    assert len(unknown["bicycle_context_audit"]) == 8


def test_v0555_delayed_guard_outcome_updates_original_crossing_only(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    proposal = {"kind": "bicycle_context", "track_id": 4, "frame_index": 250,
                "commit_status": "pending", "decision_accepted": True}
    accepted = {**proposal, "commit_status": "accepted"}
    later = {**proposal, "frame_index": 450, "commit_status": "rejected"}
    rows = [{"source_time_seconds": 10.0, "detections": 1, "tracks": 1, "road_tracks": 1,
             "rejected_cooldown": 3, "bicycle_xframe_decision_audit": [proposal]},
            {"source_time_seconds": 12.0, "rejected_cooldown": 99,
             "bicycle_xframe_decision_audit": [accepted, later]}]
    bt.trace_path(81).write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    item = bt.diagnose_trace(81, [10.0], tracking_ids=[4])["items"][0]
    assert item["bicycle_context_audit"] == [accepted]
    assert item["cooldown_reject_delta"] == 0
    assert item["max_det"] == 1


def test_v0555_trace_track_filters_do_not_mix_legacy_or_gate_geometry():
    from app.benchmark_trace import _gate_span_audit
    rows = [{"bicycle_xframe_decision_audit": [{"track_id": 5, "accepted": True}],
             "gate_tracks": [{"track_id": 5, "anchor_signed": -0.1, "center_signed": -0.1}]},
            {"gate_tracks": [{"track_id": 5, "anchor_signed": 0.1, "center_signed": 0.1}]}]
    audit = _gate_span_audit(rows, tracking_id=4)
    assert audit["bicycle_xframe_audit"] == []
    assert audit["anchor_span"] == []
    assert _gate_span_audit(rows)["anchor_span"][0]["track_id"] == 5


def test_v0555_trace_schema_rejects_misaligned_tracking_ids():
    import pytest
    from pydantic import ValidationError
    from app.schemas import BenchmarkTraceDiagnoseRequest
    assert BenchmarkTraceDiagnoseRequest(times=[10, 20]).tracking_ids is None
    assert BenchmarkTraceDiagnoseRequest(times=[10, 20], tracking_ids=[4, None]).tracking_ids == [4, None]
    with pytest.raises(ValidationError):
        BenchmarkTraceDiagnoseRequest(times=[10, 20], tracking_ids=[4])


def test_v0558_numeric_trace_schema_rejects_nonfinite_requested_times():
    import pytest
    from pydantic import ValidationError
    from app.schemas import BenchmarkTraceDiagnoseRequest

    for source_time in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValidationError):
            BenchmarkTraceDiagnoseRequest(times=[10.0, source_time], tracking_ids=[77, None])


def test_v0558_numeric_trace_schema_preserves_finite_times_and_alignment():
    from app.schemas import BenchmarkTraceDiagnoseRequest

    assert BenchmarkTraceDiagnoseRequest().times == []
    request = BenchmarkTraceDiagnoseRequest(times=[-1.0, 0.0, 10.6203], tracking_ids=[None, 3, 77])
    assert request.times == [-1.0, 0.0, 10.6203]
    assert request.tracking_ids == [None, 3, 77]
    assert request.window_seconds == 0.60


def _v0562_geometry_header(session_id=94):
    return {"kind": "geometry_metadata", "audit_only": True, "session_id": session_id,
            "coordinate_system": "normalized_processed_frame", "frame_width": 100,
            "frame_height": 100, "line": [[0.2, 0.5], [0.8, 0.5]]}


def _v0562_gate_row(frame, anchor, center=None, *, track_id=4):
    center = anchor if center is None else center
    return {"frame_index": frame, "source_time_seconds": frame / 100,
            "detections": 1, "tracks": 1, "road_tracks": 1,
            "gate_tracks": [{"track_id": track_id, "label": "motorcycle",
                             "anchor": list(anchor), "center": list(center),
                             "anchor_signed": (anchor[1] - 50) / 100,
                             "center_signed": (center[1] - 50) / 100}]}


def _v0562_diagnose_rows(bt, tmp_path, monkeypatch, rows, *, time=1, track_id=4):
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    _write_trace_scope_rows(bt, 94, rows)
    return bt.diagnose_trace(94, [time], tracking_ids=[track_id])["items"][0]


def test_v0562_actual_trace_extension_is_not_a_finite_anchor_span(tmp_path, monkeypatch):
    import app.benchmark_trace as bt
    # Session 167, raw 10 -> 15831, canonical 13014 at frames 1354/1355.
    # Both measured intersections lie beyond the visible right endpoint 1092.528.
    header = {"kind": "geometry_metadata", "audit_only": True, "session_id": 94,
              "coordinate_system": "normalized_processed_frame", "frame_width": 1440,
              "frame_height": 811, "line": [[0.343, 0.479], [0.7587, 0.385]]}
    evidence = [(1354, 54.12, [1353.877, 362.213], [1327.501, 348.024], 0.101843, 0.080378),
                (1355, 54.16, [1138.465, 208.928], [1159.5, 229.8], -0.119206, -0.090399)]
    rows = [header] + [{"frame_index": frame, "source_time_seconds": time,
        "detections": 1, "tracks": 1, "road_tracks": 1,
        "gate_tracks": [{"track_id": 13014, "label": "motorcycle", "anchor": anchor,
                         "center": center, "anchor_signed": signed, "center_signed": csigned}]}
        for frame, time, anchor, center, signed, csigned in evidence]
    item = _v0562_diagnose_rows(bt, tmp_path, monkeypatch, rows, time=54.14, track_id=13014)
    gate = item["gate_span_audit"]
    assert item["reason"] == "crossing_outside_segment_geometry"
    assert gate["anchor_span"] == gate["center_only_span"] == []
    assert gate["extension_only_span"][0]["track_id"] == 13014
    assert gate["extension_only_span"][0]["anchor_extension_only"] is True
    assert gate["extension_only_span"][0]["anchor_finite_span"] is False
    assert gate["geometry_basis"] == "finite_segment_observations"
    assert item["diagnosis_scope"]["reason"] == "matched_track_geometry"
    # Removing header preserves the historical signed-distance API.
    legacy = _v0562_diagnose_rows(bt, tmp_path, monkeypatch, rows[1:], time=54.14, track_id=13014)
    assert legacy["reason"] == "crossing_anchor_span_reject"
    assert "geometry_basis" not in legacy["gate_span_audit"]


def test_v0562_finite_span_keeps_neighbor_provenance_and_frame_global_counters(tmp_path, monkeypatch):
    import app.benchmark_trace as bt
    rows = [_v0562_geometry_header(), _v0562_gate_row(99, (40, 40)), _v0562_gate_row(101, (40, 60))]
    item = _v0562_diagnose_rows(bt, tmp_path, monkeypatch, rows, track_id=None)
    gate = item["gate_span_audit"]
    assert item["reason"] == "crossing_anchor_span_reject"
    assert [value["track_id"] for value in gate["anchor_span"]] == [4]
    assert gate["extension_only_span"] == gate["unverified_span"] == []
    assert gate["anchor_span"][0]["anchor_finite_span"] is True
    assert gate["anchor_span"][0]["geometry_unverified"] is False
    assert item["diagnosis_scope"]["reason"] == "nearby_time_window"
    assert item["diagnosis_scope"]["counters"] == "frame_global"


def test_v0562_center_finite_span_does_not_promote_anchor_extension(tmp_path, monkeypatch):
    import app.benchmark_trace as bt
    rows = [_v0562_geometry_header(), _v0562_gate_row(99, (90, 40), (40, 40)),
            _v0562_gate_row(101, (90, 60), (40, 60))]
    item = _v0562_diagnose_rows(bt, tmp_path, monkeypatch, rows)
    assert item["reason"] == "crossing_center_only_span"
    assert item["gate_span_audit"]["anchor_span"] == []
    assert item["gate_span_audit"]["center_only_span"][0]["track_id"] == 4


def test_v0562_observed_detour_cannot_replace_extension_with_sparse_chord(tmp_path, monkeypatch):
    import app.benchmark_trace as bt
    rows = [_v0562_geometry_header()] + [_v0562_gate_row(frame, point)
        for frame, point in [(98, (40, 40)), (99, (90, 40)), (100, (90, 60)), (101, (40, 60))]]
    item = _v0562_diagnose_rows(bt, tmp_path, monkeypatch, rows)
    assert item["reason"] == "crossing_outside_segment_geometry"
    assert item["gate_span_audit"]["anchor_span"] == []


def test_v0562_visible_endpoint_and_neutral_touch_preserve_real_span(tmp_path, monkeypatch):
    import app.benchmark_trace as bt
    rows = [_v0562_geometry_header()] + [_v0562_gate_row(frame, point)
        for frame, point in [(99, (20, 40)), (100, (20, 50)), (101, (20, 60))]]
    item = _v0562_diagnose_rows(bt, tmp_path, monkeypatch, rows)
    assert item["reason"] == "crossing_anchor_span_reject"
    assert item["gate_span_audit"]["anchor_span"][0]["track_id"] == 4


def test_v0562_conflicting_same_frame_aliases_make_geometry_unverified(tmp_path, monkeypatch):
    import app.benchmark_trace as bt
    rows = [_v0562_geometry_header(), _v0562_gate_row(99, (40, 40)),
            _v0562_gate_row(99, (40, 60)), _v0562_gate_row(101, (40, 60))]
    item = _v0562_diagnose_rows(bt, tmp_path, monkeypatch, rows)
    assert item["reason"] == "crossing_unverified_span"
    assert item["gate_span_audit"]["anchor_span"] == []
    assert item["gate_span_audit"]["unverified_span"][0]["track_id"] == 4
    assert item["gate_span_audit"]["unverified_span"][0]["geometry_unverified"] is True
    assert item["gate_span_audit"]["unverified_span"][0]["anchor_finite_span"] is False


def test_v0562_identical_duplicate_rows_do_not_invalidate_finite_geometry(tmp_path, monkeypatch):
    import app.benchmark_trace as bt
    before = _v0562_gate_row(99, (40, 40))
    rows = [_v0562_geometry_header(), before, before, _v0562_gate_row(101, (40, 60))]
    item = _v0562_diagnose_rows(bt, tmp_path, monkeypatch, rows)
    assert item["reason"] == "crossing_anchor_span_reject"
    assert item["gate_span_audit"]["unverified_span"] == []


def test_v0562_unordered_observation_clocks_do_not_prove_a_finite_path(tmp_path, monkeypatch):
    import app.benchmark_trace as bt
    rows = [_v0562_geometry_header(), _v0562_gate_row(101, (40, 60)), _v0562_gate_row(99, (40, 40))]
    item = _v0562_diagnose_rows(bt, tmp_path, monkeypatch, rows)
    assert item["reason"] == "crossing_unverified_span"
    assert item["gate_span_audit"]["anchor_span"] == []


def test_v0562_sparse_gap_above_audit_bound_is_unverified(tmp_path, monkeypatch):
    import app.benchmark_trace as bt
    header = _v0562_geometry_header()
    for gap, reason in [(45, "crossing_anchor_span_reject"), (46, "crossing_unverified_span")]:
        rows = [header, _v0562_gate_row(78, (40, 40)), _v0562_gate_row(78 + gap, (40, 60))]
        item = _v0562_diagnose_rows(bt, tmp_path, monkeypatch, rows)
        assert item["reason"] == reason
        assert item["gate_span_audit"]["geometry_max_gap_frames"] == 45


def test_v0562_missing_points_and_mismatched_signed_coordinates_are_unverified(tmp_path, monkeypatch):
    import app.benchmark_trace as bt
    for malformed in ("missing", "mismatch", "nonfinite"):
        before = _v0562_gate_row(99, (40, 40))
        if malformed == "missing":
            before["gate_tracks"][0].pop("anchor")
        elif malformed == "mismatch":
            before["gate_tracks"][0]["anchor_signed"] = -0.3
        else:
            before["gate_tracks"][0]["anchor"][0] = float("nan")
        rows = [_v0562_geometry_header(), before, _v0562_gate_row(101, (40, 60))]
        item = _v0562_diagnose_rows(bt, tmp_path, monkeypatch, rows)
        assert item["reason"] == "crossing_unverified_span"
        assert item["gate_span_audit"]["anchor_span"] == []


def test_v0562_malformed_geometry_header_preserves_legacy_result_exactly(tmp_path, monkeypatch):
    import app.benchmark_trace as bt
    rows = [_v0562_gate_row(99, (40, 40)), _v0562_gate_row(101, (40, 60))]
    legacy = _v0562_diagnose_rows(bt, tmp_path, monkeypatch, rows)
    malformed_headers = [
        {**_v0562_geometry_header(), "line": [[0.2, 0.5], [0.2, 0.5]]},
        {**_v0562_geometry_header(), "line": [[0.2, 0.5], [float("nan"), 0.5]]},
        {**_v0562_geometry_header(), "line": [[0.2, 0.5], [1.2, 0.5]]},
        {**_v0562_geometry_header(), "frame_width": 0},
        {**_v0562_geometry_header(), "coordinate_system": "unknown"},
        {**_v0562_geometry_header(), "line": None},
    ]
    for header in malformed_headers:
        assert _v0562_diagnose_rows(bt, tmp_path, monkeypatch, [header] + rows) == legacy


def test_v0562_direct_and_streaming_gate_audits_use_same_recorded_geometry(tmp_path, monkeypatch):
    import app.benchmark_trace as bt
    header = _v0562_geometry_header()
    rows = [_v0562_gate_row(99, (90, 40)), _v0562_gate_row(101, (90, 60))]
    direct = bt._gate_span_audit(rows, tracking_id=4, geometry_metadata=header)
    streaming = _v0562_diagnose_rows(bt, tmp_path, monkeypatch, [header] + rows)["gate_span_audit"]
    assert direct == streaming == bt._gate_span_audit([header] + rows, tracking_id=4)
    assert "geometry_basis" not in bt._gate_span_audit(rows, tracking_id=4)
