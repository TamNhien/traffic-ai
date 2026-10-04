from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

SNAPSHOT_ROOT = Path(os.getenv("SNAPSHOT_DIR", "/tmp/traffic-ai-snapshots"))
TRACE_ROOT = SNAPSHOT_ROOT / "benchmark-traces"


def trace_path(session_id: int) -> Path:
    return TRACE_ROOT / f"session_{int(session_id)}.jsonl"


def _context_decision_key(audit: dict) -> tuple[int, int] | None:
    if audit.get("kind") != "bicycle_context":
        return None
    try:
        return int(audit["track_id"]), int(audit["frame_index"])
    except (KeyError, TypeError, ValueError):
        return None


def _gate_span_audit(rows: list[dict], tracking_id: int | None = None, context_updates: list[dict] | None = None) -> dict:
    tracks: dict[int, dict[str, list[float] | str]] = {}
    xframe_audits: list[dict] = []
    context_audits: dict[tuple[int, int], dict] = {}
    for row in rows:
        for audit in row.get("bicycle_xframe_decision_audit", []) or []:
            if isinstance(audit, dict):
                if tracking_id is not None and audit.get("track_id") != tracking_id:
                    continue
                if audit.get("kind") == "bicycle_context":
                    key = _context_decision_key(audit)
                    if key is None:
                        continue
                    # Rolling snapshots repeat a proposal; a later guard outcome
                    # replaces it while keeping the source observation identity.
                    context_audits.pop(key, None)
                    context_audits[key] = audit
                else:
                    xframe_audits.append(audit)
        for item in row.get("gate_tracks", []) or []:
            try:
                tid = int(item.get("track_id"))
                anchor = float(item.get("anchor_signed"))
                center = float(item.get("center_signed"))
            except (TypeError, ValueError):
                continue
            if tracking_id is not None and tid != tracking_id:
                continue
            bucket = tracks.setdefault(tid, {"anchor": [], "center": [], "label": str(item.get("label", ""))})
            bucket["anchor"].append(anchor)
            bucket["center"].append(center)
    # A guard outcome may arrive outside the requested observation window.
    # Refresh only identities already observed in that window; unrelated later
    # decisions cannot be attached to the matched crossing.
    for row in context_updates or []:
        for audit in row.get("bicycle_xframe_decision_audit", []) or []:
            if not isinstance(audit, dict):
                continue
            key = _context_decision_key(audit)
            if key in context_audits:
                context_audits[key] = audit
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
        # A gate observation belongs to a known benchmark track only when the
        # caller supplied its identity and that identity was present here. A
        # nearby vehicle's geometry cannot identify an otherwise missed GT row.
        "geometry_scope": ("matched_track" if tracking_id is not None else "nearby_time_window")
        if tracks else "no_track_evidence",
        "bicycle_xframe_audit": xframe_audits[-8:],
        "bicycle_context_audit": list(context_audits.values())[-8:],
    }


def _diagnosis_scope(reason: str, gate_audit: dict, tracking_id: int | None) -> dict:
    geometry_scope = gate_audit["geometry_scope"]
    # Detection, rejection, and event counters are frame totals. Supplying a
    # matched ID filters geometry/audits; it does not make those totals belong
    # to that individual vehicle or prove why its crossing was missed.
    reason_scope = "nearby_time_window"
    if reason == "no_trace_window":
        reason_scope = "no_trace_window"
    elif geometry_scope == "matched_track" and reason in {
        "crossing_anchor_span_reject", "crossing_center_only_span", "crossing_near_no_span",
    }:
        reason_scope = "matched_track_geometry"
    return {
        "reason": reason_scope,
        "geometry": geometry_scope,
        "counters": "no_trace_window" if reason == "no_trace_window" else "frame_global",
        "tracking_id": tracking_id,
    }


def diagnose_trace(session_id: int, times: Iterable[float], window_seconds: float = 0.60, *, tracking_ids: Iterable[int | None] | None = None) -> dict:
    targets = list(times)
    target_tracks = list(tracking_ids) if tracking_ids is not None else [None] * len(targets)
    if len(target_tracks) != len(targets):
        raise ValueError("tracking_ids must align with times")
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
    for raw_time, tracking_id in zip(targets, target_tracks):
        target = max(0.0, float(raw_time))
        nearby = [row for row in rows if abs(float(row.get("source_time_seconds", -9999.0)) - target) <= window]
        gate_audit = _gate_span_audit(nearby, tracking_id=tracking_id, context_updates=rows)
        nearby = [row for row in nearby if not row.get("audit_only")]
        if not nearby:
            result.append({"time": target, "reason": "no_trace_window", "max_det": 0, "max_track": 0, "max_road": 0,
                           "diagnosis_scope": _diagnosis_scope("no_trace_window", gate_audit, tracking_id),
                           "gate_span_audit": gate_audit,
                           "bicycle_xframe_audit": gate_audit["bicycle_xframe_audit"],
                           "bicycle_context_audit": gate_audit["bicycle_context_audit"]})
            continue
        max_det = max(int(row.get("detections", 0)) for row in nearby)
        max_track = max(int(row.get("tracks", 0)) for row in nearby)
        max_road = max(int(row.get("road_tracks", 0)) for row in nearby)
        event_frames = sum(int(row.get("crossing_events", 0)) for row in nearby)
        outside_road_delta = max(int(row.get("rejected_outside_road", 0)) for row in nearby) - min(int(row.get("rejected_outside_road", 0)) for row in nearby)
        confirm_delta = max(int(row.get("rejected_unconfirmed_side", 0)) for row in nearby) - min(int(row.get("rejected_unconfirmed_side", 0)) for row in nearby)
        cooldown_delta = max(int(row.get("rejected_cooldown", 0)) for row in nearby) - min(int(row.get("rejected_cooldown", 0)) for row in nearby)
        road_edge_rescue_delta = max(int(row.get("road_edge_rescues", 0)) for row in nearby) - min(int(row.get("road_edge_rescues", 0)) for row in nearby)
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
            "diagnosis_scope": _diagnosis_scope(reason, gate_audit, tracking_id),
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
            "bicycle_context_audit": gate_audit["bicycle_context_audit"],
        })
    return {"available": True, "session_id": int(session_id), "window_seconds": window, "items": result}
