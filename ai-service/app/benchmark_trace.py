from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

SNAPSHOT_ROOT = Path(os.getenv("SNAPSHOT_DIR", "/tmp/traffic-ai-snapshots"))
TRACE_ROOT = SNAPSHOT_ROOT / "benchmark-traces"


def trace_path(session_id: int) -> Path:
    return TRACE_ROOT / f"session_{int(session_id)}.jsonl"


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
        })
    return {"available": True, "session_id": int(session_id), "window_seconds": window, "items": result}
