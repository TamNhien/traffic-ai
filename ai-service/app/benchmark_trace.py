from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

SNAPSHOT_ROOT = Path(os.getenv("SNAPSHOT_DIR", "/tmp/traffic-ai-snapshots"))
TRACE_ROOT = SNAPSHOT_ROOT / "benchmark-traces"


def trace_path(session_id: int) -> Path:
    return TRACE_ROOT / f"session_{int(session_id)}.jsonl"


def _gate_span_audit(rows: list[dict]) -> dict:
    tracks: dict[int, dict[str, list[float] | str]] = {}
    xframe_audits: list[dict] = []
    for row in rows:
        for audit in row.get("bicycle_xframe_decision_audit", []) or []:
            if isinstance(audit, dict):
                xframe_audits.append(audit)
        for item in row.get("gate_tracks", []) or []:
            try:
                tid = int(item.get("track_id"))
                anchor = float(item.get("anchor_signed"))
                center = float(item.get("center_signed"))
            except (TypeError, ValueError):
                continue
            bucket = tracks.setdefault(tid, {"anchor": [], "center": [], "label": str(item.get("label", ""))})
            bucket["anchor"].append(anchor)
            bucket["center"].append(center)
    anchor_span = []
    center_only = []
    near = []
    for tid, item in tracks.items():
        anchors = item["anchor"]
        centers = item["center"]
        a_span = bool(anchors) and min(anchors) < -0.006 and max(anchors) > 0.006
        c_span = bool(centers) and min(centers) < -0.006 and max(centers) > 0.006
        min_abs = min([abs(v) for v in anchors] or [999.0])
        summary = {
            "track_id": tid, "label": item["label"],
            "anchor_min": round(min(anchors), 6) if anchors else None,
            "anchor_max": round(max(anchors), 6) if anchors else None,
            "center_min": round(min(centers), 6) if centers else None,
            "center_max": round(max(centers), 6) if centers else None,
        }
        if a_span:
            anchor_span.append(summary)
        elif c_span:
            center_only.append(summary)
        elif min_abs <= 0.020:
            near.append(summary)
    return {
        "anchor_span": anchor_span, "center_only_span": center_only, "near_no_span": near,
        "bicycle_xframe_audit": xframe_audits[-8:],
    }


def diagnose_trace(session_id: int, times: Iterable[float], window_seconds: float = 0.60) -> dict:
    path = trace_path(session_id)
    if not path.exists():
        return {"available": False, "session_id": int(session_id), "items": []}
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    window = max(0.05, min(2.0, float(window_seconds)))
    result = []
    for raw_time in times:
        target = max(0.0, float(raw_time))
        nearby = [row for row in rows if abs(float(row.get("source_time_seconds", -9999.0)) - target) <= window]
        if not nearby:
            result.append({"time": target, "reason": "no_trace_window", "max_det": 0, "max_track": 0, "max_road": 0})
            continue
        max_det = max(int(row.get("detections", 0)) for row in nearby)
        max_track = max(int(row.get("tracks", 0)) for row in nearby)
        max_road = max(int(row.get("road_tracks", 0)) for row in nearby)
        event_frames = sum(int(row.get("crossing_events", 0)) for row in nearby)
        outside_road_delta = max(int(row.get("rejected_outside_road", 0)) for row in nearby) - min(int(row.get("rejected_outside_road", 0)) for row in nearby)
        confirm_delta = max(int(row.get("rejected_unconfirmed_side", 0)) for row in nearby) - min(int(row.get("rejected_unconfirmed_side", 0)) for row in nearby)
        cooldown_delta = max(int(row.get("rejected_cooldown", 0)) for row in nearby) - min(int(row.get("rejected_cooldown", 0)) for row in nearby)
        road_edge_rescue_delta = max(int(row.get("road_edge_rescues", 0)) for row in nearby) - min(int(row.get("road_edge_rescues", 0)) for row in nearby)
        gate_audit = _gate_span_audit(nearby)
        if max_det <= 0:
            reason = "detector_miss"
        elif max_track <= 0:
            reason = "tracker_miss"
        elif max_road <= 0 or outside_road_delta > 0:
            reason = "road_zone_reject"
        elif cooldown_delta > 0:
            reason = "crossing_cooldown_reject"
        elif confirm_delta > 0:
            reason = "crossing_confirmation_reject"
        else:
            if gate_audit["anchor_span"]:
                reason = "crossing_anchor_span_reject"
            elif gate_audit["center_only_span"]:
                reason = "crossing_center_only_span"
            elif gate_audit["near_no_span"]:
                reason = "crossing_near_no_span"
            else:
                reason = "crossing_gate_miss"
        result.append({
            "time": target,
            "reason": reason,
            "max_det": max_det,
            "max_track": max_track,
            "max_road": max_road,
            "crossing_events_nearby": event_frames,
            "outside_road_delta": outside_road_delta,
            "confirmation_reject_delta": confirm_delta,
            "cooldown_reject_delta": cooldown_delta,
            "road_edge_rescue_delta": road_edge_rescue_delta,
            "gate_span_audit": gate_audit,
            "bicycle_xframe_audit": gate_audit["bicycle_xframe_audit"],
        })
    return {"available": True, "session_id": int(session_id), "window_seconds": window, "items": result}
