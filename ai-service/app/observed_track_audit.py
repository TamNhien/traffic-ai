"""Bounded review evidence from recorded rectangles, never a counting policy."""
from __future__ import annotations

from math import isfinite


OBSERVED_FRAME_LIMIT = 256
OBSERVED_TRACKS_PER_FRAME = 64
OBSERVED_PEER_LIMIT = 16
OBSERVED_RECORD_LIMIT = 4
OBSERVED_HANDOFF_LIMIT = 8


def _integer(value):
    return type(value) is int and abs(value) <= 2**53 - 1


def _number(value):
    return type(value) in (int, float) and abs(value) <= 1_000_000 and isfinite(value)


def _vector(value, length):
    return (list(map(float, value)) if isinstance(value, (list, tuple)) and len(value) == length
            and all(_number(number) for number in value) else None)


def _sample(item, frame, time):
    if not isinstance(item, dict) or not _integer(item.get("track_id")):
        return None
    rect = _vector(item.get("rect"), 4)
    if rect is None or rect[2] - rect[0] < .001 or rect[3] - rect[1] < .001:
        return None
    raw = item.get("raw_track_id")
    return {"frame": frame, "time": time, "rect": rect,
            "raw": raw if _integer(raw) else None,
            "velocity": _vector(item.get("measured_velocity"), 2),
            "tracking_id": item["track_id"]}


def _center(sample):
    x1, y1, x2, y2 = sample["rect"]
    return [(x1 + x2) / 2, (y1 + y2) / 2]


def _motion(first, last):
    gap = last["frame"] - first["frame"]
    if gap <= 0 or last["time"] <= first["time"]:
        return None
    before, after = _center(first), _center(last)
    dx, dy = after[0] - before[0], after[1] - before[1]
    return {"dx": round(dx, 6), "dy": round(dy, 6), "gap_frames": gap,
            "pixels_per_frame": [round(dx / gap, 6), round(dy / gap, 6)]}


def _bounds(first, last):
    return {"first_frame": first["frame"], "last_frame": last["frame"],
            "first_time": first["time"], "last_time": last["time"]}


class ObservedTrackAudit:
    """One canonical window; only same-frame observations support pair evidence.

    Containment is intersection / smaller rectangle area. Bottom alignment is
    the bottom-edge gap / larger rectangle height. These are measurements for
    visual review, and cannot establish identity or authorize suppression.
    """

    def __init__(self, tracking_id):
        self.tracking_id = tracking_id
        self.frames = {}
        self.first = self.last = None
        self.previous = None
        self.raw_ids = set()
        self.handoffs = []
        self.peers = {}
        self.truncated = False
        self.conflicting_frames = 0
        self.out_of_order_frames = 0

    def observe(self, row):
        if not _integer(self.tracking_id) or not isinstance(row, dict) or row.get("audit_only"):
            return
        frame, time = row.get("frame_index"), row.get("source_time_seconds")
        tracks = row.get("gate_tracks")
        if (not _integer(frame) or frame < 1 or not _number(time) or time < 0
                or not isinstance(tracks, list)):
            return
        if len(tracks) > OBSERVED_TRACKS_PER_FRAME:
            self.truncated = True
        valid = {}
        ambiguous = set()
        for item in tracks[:OBSERVED_TRACKS_PER_FRAME]:
            sample = _sample(item, frame, float(time))
            if sample is None:
                continue
            tid = sample["tracking_id"]
            if tid in valid and sample != valid[tid]:
                ambiguous.add(tid)
            valid[tid] = sample
        for tid in ambiguous:
            valid.pop(tid, None)
        own = valid.get(self.tracking_id)
        if own is None:
            if self.tracking_id in ambiguous:
                self.conflicting_frames += 1
            return
        signature = [(tid, valid[tid]) for tid in sorted(valid)]
        if frame in self.frames:
            if signature != self.frames[frame]:
                self.conflicting_frames += 1
            return
        if len(self.frames) >= OBSERVED_FRAME_LIMIT:
            self.truncated = True
            return
        self.frames[frame] = signature
        if self.first is None or frame < self.first["frame"]:
            self.first = own
        if self.last is None or frame > self.last["frame"]:
            self.last = own
        if own["raw"] is not None:
            if own["raw"] in self.raw_ids or len(self.raw_ids) < OBSERVED_PEER_LIMIT:
                self.raw_ids.add(own["raw"])
            else:
                self.truncated = True
        previous = self.previous
        if previous is not None and frame < previous["frame"]:
            self.out_of_order_frames += 1
        elif previous is not None and time <= previous["time"]:
            self.out_of_order_frames += 1
        else:
            if (previous is not None and own["raw"] is not None and previous["raw"] is not None
                    and own["raw"] != previous["raw"]):
                if len(self.handoffs) < OBSERVED_HANDOFF_LIMIT:
                    motion = _motion(previous, own)
                    self.handoffs.append({"from_raw_track_id": previous["raw"], "to_raw_track_id": own["raw"],
                                          "from_frame": previous["frame"], "to_frame": frame,
                                          "from_time": previous["time"], "to_time": float(time),
                                          "gap_frames": frame - previous["frame"],
                                          "rect_displacement": [motion["dx"], motion["dy"]]})
                else:
                    self.truncated = True
            self.previous = own
        for tid in sorted(valid):
            if tid == self.tracking_id:
                continue
            other = valid[tid]
            a, b = own["rect"], other["rect"]
            area_a = (a[2] - a[0]) * (a[3] - a[1])
            area_b = (b[2] - b[0]) * (b[3] - b[1])
            intersection = max(0., min(a[2], b[2]) - max(a[0], b[0])) * max(0., min(a[3], b[3]) - max(a[1], b[1]))
            containment = intersection / min(area_a, area_b)
            bottom = abs(a[3] - b[3]) / max(a[3] - a[1], b[3] - b[1])
            # Retain co-visible observations before and after overlap as well.
            # The output filters disjoint peers, never their earlier frames.
            state = self.peers.get(tid)
            if state is None:
                if len(self.peers) >= OBSERVED_PEER_LIMIT:
                    self.truncated = True
                    disjoint = [key for key, value in self.peers.items() if value["cmax"] == 0]
                    if containment > 0 and disjoint:
                        self.peers.pop(max(disjoint))
                    else:
                        continue
                state = self.peers[tid] = {"first_own": own, "last_own": own,
                                          "first": other, "last": other, "count": 0, "nested": 0,
                                          "cmin": containment, "cmax": containment,
                                          "bmin": bottom, "bmax": bottom, "raws": set(),
                                          "previous_frame": None, "previous_time": None,
                                          "run": 0, "max_run": 0}
            state["count"] += 1
            state["nested"] += containment >= .90 and bottom <= .07
            state["cmin"], state["cmax"] = min(state["cmin"], containment), max(state["cmax"], containment)
            state["bmin"], state["bmax"] = min(state["bmin"], bottom), max(state["bmax"], bottom)
            if other["raw"] is not None:
                if other["raw"] in state["raws"] or len(state["raws"]) < OBSERVED_PEER_LIMIT:
                    state["raws"].add(other["raw"])
                else:
                    self.truncated = True
            if frame < state["first"]["frame"]:
                state["first"], state["first_own"] = other, own
            if frame > state["last"]["frame"]:
                state["last"], state["last_own"] = other, own
            consecutive = (state["previous_frame"] is not None and frame == state["previous_frame"] + 1
                           and time > state["previous_time"])
            state["run"] = state["run"] + 1 if consecutive else 1
            state["max_run"] = max(state["max_run"], state["run"])
            state["previous_frame"], state["previous_time"] = frame, float(time)

    def finish(self):
        overlapping = [(tid, state) for tid, state in self.peers.items() if state["cmax"] > 0]
        available = bool(self.frames) and not self.conflicting_frames
        result = {"schema_version": 1, "scope": "canonical_track_window", "tracking_id": self.tracking_id,
                  "identity_proven": False, "status": "observed" if available else "unavailable",
                  "reason": "conflicting_observations" if self.conflicting_frames else
                            "recorded_rectangles" if self.frames else "no_valid_rectangles",
                  "target": None, "peers": [],
                  "raw_id_handoffs": [{**value, "rect_displacement": list(value["rect_displacement"])}
                                      for value in self.handoffs] if available else [],
                  "records_limit": OBSERVED_RECORD_LIMIT, "truncated": self.truncated or len(overlapping) > OBSERVED_RECORD_LIMIT,
                  "conflicting_frames": self.conflicting_frames, "out_of_order_frames": self.out_of_order_frames}
        if not available:
            return result
        result["target"] = {"frames": len(self.frames), **_bounds(self.first, self.last),
                            "raw_track_ids": sorted(self.raw_ids), "rect_motion": _motion(self.first, self.last),
                            "filtered_velocity": list(self.last["velocity"]) if self.last["velocity"] is not None else None}
        selected = sorted(overlapping, key=lambda pair: (-pair[1]["nested"], -pair[1]["cmax"], pair[0]))
        for tid, state in selected[:OBSERVED_RECORD_LIMIT]:
            result["peers"].append({"tracking_id": tid, "identity_proven": False,
                                    "co_visible_frames": state["count"], "nested_frames": state["nested"],
                                    "max_consecutive_frames": state["max_run"], **_bounds(state["first"], state["last"]),
                                    "containment_min": round(state["cmin"], 6), "containment_max": round(state["cmax"], 6),
                                    "bottom_alignment_min": round(state["bmin"], 6), "bottom_alignment_max": round(state["bmax"], 6),
                                    "raw_track_ids": sorted(state["raws"]),
                                    "target_rect_motion": _motion(state["first_own"], state["last_own"]),
                                    "peer_rect_motion": _motion(state["first"], state["last"]),
                                    "target_filtered_velocity": list(state["last_own"]["velocity"])
                                    if state["last_own"]["velocity"] is not None else None,
                                    "peer_filtered_velocity": list(state["last"]["velocity"])
                                    if state["last"]["velocity"] is not None else None})
        return result
