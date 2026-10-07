from __future__ import annotations

import json
import os
import shutil
import gzip
from bisect import bisect_left, bisect_right
from collections import deque
from hashlib import sha256
from math import inf, isfinite, nextafter

from app.counting import segment_crossing_point, signed_distance
from pathlib import Path
from typing import Iterable
from uuid import uuid4

SNAPSHOT_ROOT = Path(os.getenv("SNAPSHOT_DIR", "/tmp/traffic-ai-snapshots"))
TRACE_ROOT = SNAPSHOT_ROOT / "benchmark-traces"
TRACE_EXPORT_MAX_BYTES = 128 * 1024 * 1024


def trace_path(session_id: int) -> Path:
    return TRACE_ROOT / f"session_{int(session_id)}.jsonl"


def compressed_trace_path(session_id: int) -> Path:
    return TRACE_ROOT / f"session_{int(session_id)}.jsonl.gz"


def _closed_trace_metadata_path(session_id: int) -> Path:
    return TRACE_ROOT / f"session_{int(session_id)}.closed.json"


def _trace_signature(path: Path) -> list[int]:
    status = path.stat()
    return [status.st_dev, status.st_ino, status.st_size, status.st_mtime_ns, status.st_ctime_ns]


class _BoundedCompressedWriter:
    def __init__(self, handle) -> None:
        self.handle = handle
        self.size = 0
        self.digest = sha256()

    def write(self, data: bytes) -> int:
        if self.size + len(data) > TRACE_EXPORT_MAX_BYTES:
            raise OSError("Compressed benchmark trace exceeds the export limit")
        written = self.handle.write(data)
        if written != len(data):
            raise OSError("Incomplete compressed benchmark trace write")
        self.size += written
        self.digest.update(data[:written])
        return written

    def flush(self) -> None:
        self.handle.flush()


def publish_compressed_trace(session_id: int) -> dict:
    """Stream a closed writer's exact bytes into an atomic bounded artifact.

    The certificate is published last. A live, replaced, or subsequently
    appended raw trace cannot use an earlier certificate to appear closed.
    Compression failure does not affect the raw endpoint or camera artifact.
    """
    source = trace_path(session_id)
    target = compressed_trace_path(session_id)
    metadata_path = _closed_trace_metadata_path(session_id)
    metadata_path.unlink(missing_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    temporary_metadata = metadata_path.with_name(f".{metadata_path.name}.{uuid4().hex}.tmp")
    source_signature = _trace_signature(source)
    digest = sha256()
    source_bytes = 0
    published = False
    try:
        with source.open("rb") as original, temporary.open("wb") as output:
            bounded = _BoundedCompressedWriter(output)
            with gzip.GzipFile(filename="", mode="wb", fileobj=bounded, mtime=0, compresslevel=6) as compressed:
                while chunk := original.read(64 * 1024):
                    digest.update(chunk)
                    source_bytes += len(chunk)
                    compressed.write(chunk)
        if _trace_signature(source) != source_signature or source_bytes != source_signature[2]:
            raise OSError("Benchmark trace changed during closed publication")
        os.replace(temporary, target)
        published = True
        metadata = {
            "schema_version": 1, "session_id": int(session_id), "closed": True,
            "encoding": "gzip", "source_bytes": source_bytes, "source_sha256": digest.hexdigest(),
            "compressed_bytes": bounded.size, "compressed_sha256": bounded.digest.hexdigest(),
            "source_signature": source_signature, "compressed_signature": _trace_signature(target),
        }
        temporary_metadata.write_text(json.dumps(metadata, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(temporary_metadata, metadata_path)
        return metadata
    except Exception:
        if published:
            target.unlink(missing_ok=True)
        raise
    finally:
        temporary.unlink(missing_ok=True)
        temporary_metadata.unlink(missing_ok=True)


def closed_compressed_trace(session_id: int) -> tuple[Path, dict] | None:
    """Return only a certified artifact whose source and gzip are unchanged."""
    try:
        metadata = json.loads(_closed_trace_metadata_path(session_id).read_text(encoding="utf-8"))
        target = compressed_trace_path(session_id)
        if (not isinstance(metadata, dict) or metadata.get("schema_version") != 1
                or metadata.get("session_id") != int(session_id) or metadata.get("closed") is not True
                or metadata.get("encoding") != "gzip"
                or metadata.get("source_signature") != _trace_signature(trace_path(session_id))
                or metadata.get("compressed_signature") != _trace_signature(target)
                or not 0 < metadata.get("compressed_bytes", 0) <= TRACE_EXPORT_MAX_BYTES
                or metadata.get("compressed_bytes") != target.stat().st_size
                or metadata.get("source_bytes") != trace_path(session_id).stat().st_size):
            return None
        for key in ("source_sha256", "compressed_sha256"):
            value = metadata.get(key)
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                return None
        return target, metadata
    except (OSError, ValueError, TypeError):
        return None


def publish_closed_trace(camera_id: int, session_id: int, *, snapshot_root: Path) -> dict | None:
    """Expose a successfully closed canonical trace beside this session's JPGs.

    The worker calls this only after the sole writer closes successfully. An
    atomic hardlink shares those exact bytes without a second writer or copy;
    filesystems without hardlinks receive one atomic copy of the closed file.
    """
    source = trace_path(session_id)
    if not source.is_file():
        return None
    folder = Path(snapshot_root) / f"camera_{int(camera_id)}"
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"session_{int(session_id)}_benchmark-trace.jsonl"
    target = folder / filename
    temporary = folder / f".{filename}.{uuid4().hex}.tmp"
    method = "hardlink"
    try:
        try:
            os.link(source, temporary)
        except OSError:
            method = "copy"
            shutil.copyfile(source, temporary)
        size = temporary.stat().st_size
        os.replace(temporary, target)
        return {
            "path": target.relative_to(snapshot_root).as_posix(),
            "bytes": size,
            "method": method,
        }
    finally:
        temporary.unlink(missing_ok=True)


def _context_decision_key(audit: dict) -> tuple[int, int] | None:
    if audit.get("kind") != "bicycle_context":
        return None
    try:
        return int(audit["track_id"]), int(audit["frame_index"])
    except (KeyError, TypeError, ValueError):
        return None


def _gate_span_audit(
    rows: list[dict], tracking_id: int | None = None, context_updates: list[dict] | None = None,
    *, geometry_metadata: dict | None = None,
) -> dict:
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
    finite_fields = {}
    geometry = _finite_geometry_context(geometry_metadata or {})
    if geometry is None:
        geometry = next((value for row in rows if (value := _finite_geometry_context(row)) is not None), None)
    if geometry is not None:
        window = _TraceWindow(0.0, tracking_id)
        window.geometry_context = geometry
        for row in rows:
            window.observe(row)
        audited = window.finish()["gate_span_audit"]
        anchor_span, center_only, near = (audited[key] for key in ("anchor_span", "center_only_span", "near_no_span"))
        finite_fields = {key: audited[key] for key in (
            "geometry_basis", "geometry_max_gap_frames", "extension_only_span", "unverified_span",
        )}
    return {
        "anchor_span": anchor_span, "center_only_span": center_only, "near_no_span": near,
        **finite_fields,
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
    elif reason == "crossing_proposal_observed":
        reason_scope = "matched_track_proposal"
    elif reason == "crossing_delivery_observed":
        reason_scope = "matched_track_delivery"
    elif geometry_scope == "matched_track" and reason in {
        "crossing_anchor_span_reject", "crossing_center_only_span", "crossing_near_no_span",
        "crossing_outside_segment_geometry", "crossing_unverified_span",
    }:
        reason_scope = "matched_track_geometry"
    return {
        "reason": reason_scope,
        "geometry": geometry_scope,
        "counters": "no_trace_window" if reason == "no_trace_window" else "frame_global",
        "tracking_id": tracking_id,
    }


TRACE_GEOMETRY_MAX_GAP_FRAMES = 45
TRACE_EVENT_AUDIT_RECORDS_LIMIT = 8
_TRACE_DEDUP_REASONS = frozenset({
    "same-track-delivery-retry", "startup-crossing-signature", "heavy-semantic-signature",
    "crossing-signature", "two-wheel-rescue-signature", "two-wheel-spatial-signature",
    "two-wheel-ultra-spatial-signature", "same-track-repeat-jitter", "same-track-direction-flip",
    "secondary-shadow-signature", "direct-ultra-shadow", "direct-secondary-shadow",
    "semantic-family-shadow", "semantic-family-reverse-shadow", "secondary-reverse-shadow",
})


def _event_audit_record(value: dict, session_id: int, *, delivery: bool) -> dict | None:
    """Project recorded producer/receipt evidence without response bodies or paths."""
    if not isinstance(value, dict):
        return None
    integer_keys = ("camera_id", "session_id", "tracking_id", "source_frame_index")
    if any(type(value.get(key)) is not int for key in integer_keys):
        return None
    if value["camera_id"] < 1 or value["session_id"] != session_id or value["source_frame_index"] < 0:
        return None
    numeric_keys = ("confidence", "source_time_seconds", "crossing_x", "crossing_y")
    try:
        if any(type(value.get(key)) not in (int, float) or not isfinite(value[key]) for key in numeric_keys):
            return None
    except OverflowError:
        return None
    if any(type(value.get(key)) is not str for key in ("vehicle_type", "direction", "crossing_method", "stage")):
        return None
    if (not 0 <= value["confidence"] <= 1 or value["source_time_seconds"] < 0
            or not 0 <= value["crossing_x"] <= 1 or not 0 <= value["crossing_y"] <= 1
            or value.get("vehicle_type") not in {"bicycle", "motorcycle", "car", "bus", "truck"}
            or value.get("direction") not in {"in", "out"}
            or value.get("crossing_method") not in {"direct", "interpolated", "rescued"}):
        return None
    record = {key: value[key] for key in (*integer_keys, "vehicle_type", "direction", *numeric_keys,
                                        "crossing_method")}
    if delivery:
        stage, outcome = value.get("stage"), value.get("outcome")
        if (type(outcome) is not str
                or (stage == "backend_acknowledged" and outcome not in {"created", "deduplicated", "acknowledged_unknown"})
                or (stage == "delivery_failed" and outcome != "failed")
                or stage not in {"backend_acknowledged", "delivery_failed"}
                or type(value.get("attempts")) is not int or value["attempts"] < 1):
            return None
        event_id = value.get("backend_event_id")
        if event_id is not None and (type(event_id) is not int or event_id < 1):
            return None
        reason = value.get("dedup_reason")
        record.update(stage=stage, outcome=outcome, attempts=value["attempts"], backend_event_id=event_id,
                      dedup_reason=reason if isinstance(reason, str) and reason in _TRACE_DEDUP_REASONS else None)
    else:
        stage = value.get("stage")
        observed_frame = value.get("observed_frame_index")
        if (stage not in {"committed_before_submit", "submitted_after_guard"}
                or type(observed_frame) is not int or observed_frame < value["source_frame_index"]):
            return None
        record.update(stage=stage, observed_frame_index=observed_frame)
    return record



def _finite_geometry_context(row: dict) -> tuple | None:
    """Use only the recorded processed-frame geometry, never current settings."""
    if row.get("kind") != "geometry_metadata" or row.get("coordinate_system") != "normalized_processed_frame":
        return None
    try:
        width, height = float(row["frame_width"]), float(row["frame_height"])
        line = row["line"]
        if not isfinite(width) or not isfinite(height) or width <= 0 or height <= 0 or len(line) != 2:
            return None
        points = [tuple(float(value) for value in point) for point in line]
        if any(len(point) != 2 or not all(isfinite(value) and 0 <= value <= 1 for value in point) for point in points):
            return None
        a, b = [(point[0] * width, point[1] * height) for point in points]
        if a == b:
            return None
        if b[0] < a[0]:
            a, b = b, a
        return a, b, max(1.0, min(width, height))
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


class _FiniteTrackAudit:
    """Bounded adjacent-observation evidence; a signed extension is not a gate."""

    def __init__(self, geometry):
        self.geometry = geometry
        self.previous = None
        self.last_sides = [0, 0]
        self.finite = [False, False]
        self.outside = [False, False]
        self.unverified = False

    def observe(self, row, item):
        try:
            frame = int(row["frame_index"])
            if frame < 1 or frame != row["frame_index"]:
                raise ValueError("Invalid source frame")
            points = [tuple(float(value) for value in item[key]) for key in ("anchor", "center")]
            if any(len(point) != 2 or not all(isfinite(value) for value in point) for point in points):
                raise ValueError("Invalid observed point")
            a, b, scale = self.geometry
            distances = [signed_distance(point, a, b) / scale for point in points]
            signed = [float(item[key]) for key in ("anchor_signed", "center_signed")]
            if any(not isfinite(value) or abs(distance - value) > 0.0001 for distance, value in zip(distances, signed)):
                raise ValueError("Signed geometry does not match recorded coordinates")
        except (KeyError, TypeError, ValueError, OverflowError):
            self.unverified = True
            self.previous = None
            return
        sample = frame, points, distances
        if self.previous is not None:
            previous_frame, previous_points, previous_distances = self.previous
            gap = frame - previous_frame
            if gap <= 0:
                # A repeated identical row supplies no new trajectory. Conflicting
                # aliases at one frame or unordered clocks cannot prove a path.
                if gap < 0 or points != previous_points:
                    self.unverified = True
                return
            if gap > TRACE_GEOMETRY_MAX_GAP_FRAMES:
                self.unverified = True
            else:
                for index, (before, after) in enumerate(zip(previous_distances, distances)):
                    side = 1 if after > 0 else -1 if after < 0 else 0
                    crossed = before * after < 0 or (before == 0 and side and self.last_sides[index] == -side)
                    if crossed:
                        point = segment_crossing_point(previous_points[index], points[index], a, b)
                        if point is None:
                            self.outside[index] = True
                        else:
                            self.finite[index] = True
        self.previous = sample
        for index, distance in enumerate(distances):
            if distance:
                self.last_sides[index] = 1 if distance > 0 else -1


class _TraceWindow:
    def __init__(self, target, track):
        self.target = target
        self.track = track
        self.geometry = {}
        self.geometry_context = None
        self.finite_geometry = {}
        self.context = {}
        self.legacy = deque(maxlen=8)
        self.count = 0
        self.maximum = {}
        self.minimum = {}
        self.events = 0
        self.proposal_enabled = False
        self.delivery_enabled = False
        self.proposals = {}
        self.deliveries = {}
        self.proposals_truncated = False
        self.deliveries_truncated = False
        self.delivery_summary = None

    def observe_event_audit(self, record, *, delivery):
        if self.track is not None and record["tracking_id"] != self.track:
            return
        records = self.deliveries if delivery else self.proposals
        key = tuple(record[field] for field in (
            "tracking_id", "source_frame_index", "source_time_seconds", "vehicle_type",
            "direction", "crossing_method", "stage",
        ))
        records.pop(key, None)
        records[key] = record
        if len(records) > TRACE_EVENT_AUDIT_RECORDS_LIMIT:
            records.pop(next(iter(records)))
            if delivery:
                self.deliveries_truncated = True
            else:
                self.proposals_truncated = True

    def observe(self, row):
        if row.get('kind') in ('event_delivery', 'delivery_summary'):
            return
        for audit in row.get('bicycle_xframe_decision_audit', []) or []:
            if not isinstance(audit, dict) or (self.track is not None and audit.get('track_id') != self.track):
                continue
            if audit.get('kind') == 'bicycle_context':
                key = _context_decision_key(audit)
                if key is not None:
                    self.context.pop(key, None)
                    self.context[key] = audit
                    if len(self.context) > 8:
                        self.context.pop(next(iter(self.context)))
            else:
                self.legacy.append(audit)
        for item in row.get('gate_tracks', []) or []:
            try:
                tid = int(item.get('track_id'))
                anchor = float(item.get('anchor_signed'))
                center = float(item.get('center_signed'))
            except (TypeError, ValueError):
                continue
            if self.track is not None and tid != self.track:
                continue
            if self.geometry_context is not None:
                audit = self.finite_geometry.get(tid)
                if audit is None:
                    audit = self.finite_geometry[tid] = _FiniteTrackAudit(self.geometry_context)
                audit.observe(row, item)
            values = self.geometry.get(tid)
            if values is None:
                self.geometry[tid] = [anchor, anchor, center, center, abs(anchor), str(item.get('label', ''))]
            else:
                values[0] = min(values[0], anchor)
                values[1] = max(values[1], anchor)
                values[2] = min(values[2], center)
                values[3] = max(values[3], center)
                values[4] = min(values[4], abs(anchor))
        if row.get('audit_only') or row.get('kind') == 'event_delivery':
            return
        self.count += 1
        self.events += int(row.get('crossing_events', 0))
        for key in ('detections', 'tracks', 'road_tracks', 'rejected_outside_road',
                    'rejected_unconfirmed_side', 'rejected_cooldown', 'road_edge_rescues'):
            value = int(row.get(key, 0))
            self.maximum[key] = max(self.maximum.get(key, value), value)
            self.minimum[key] = min(self.minimum.get(key, value), value)

    def finish(self):
        gate = {'anchor_span': [], 'center_only_span': [], 'near_no_span': [],
                'geometry_scope': ('matched_track' if self.track is not None else 'nearby_time_window')
                if self.geometry else 'no_track_evidence',
                'bicycle_xframe_audit': list(self.legacy),
                'bicycle_context_audit': list(self.context.values())}
        if self.geometry_context is not None:
            gate.update(geometry_basis="finite_segment_observations",
                        geometry_max_gap_frames=TRACE_GEOMETRY_MAX_GAP_FRAMES,
                        extension_only_span=[], unverified_span=[])
        for tid, (amin, amax, cmin, cmax, anear, label) in self.geometry.items():
            item = {'track_id': tid, 'label': label, 'anchor_min': round(amin, 6),
                    'anchor_max': round(amax, 6), 'center_min': round(cmin, 6), 'center_max': round(cmax, 6)}
            anchor_span = amin < -0.006 and amax > 0.006
            center_span = cmin < -0.006 and cmax > 0.006
            audit = self.finite_geometry.get(tid)
            if self.geometry_context is not None:
                verified = audit is not None and not audit.unverified
                item.update(
                    anchor_finite_span=bool(verified and anchor_span and audit.finite[0]),
                    center_finite_span=bool(verified and center_span and audit.finite[1]),
                    anchor_extension_only=bool(verified and anchor_span and audit.outside[0] and not audit.finite[0]),
                    center_extension_only=bool(verified and center_span and audit.outside[1] and not audit.finite[1]),
                    geometry_unverified=not verified,
                )
            if self.geometry_context is None:
                if anchor_span:
                    gate['anchor_span'].append(item)
                elif center_span:
                    gate['center_only_span'].append(item)
                elif anear <= 0.020:
                    gate['near_no_span'].append(item)
            elif audit is None or audit.unverified:
                if anchor_span or center_span:
                    gate['unverified_span'].append(item)
                elif anear <= 0.020:
                    gate['near_no_span'].append(item)
            elif anchor_span and audit.finite[0]:
                gate['anchor_span'].append(item)
            elif center_span and audit.finite[1]:
                gate['center_only_span'].append(item)
            elif (anchor_span and audit.outside[0]) or (center_span and audit.outside[1]):
                gate['extension_only_span'].append(item)
            elif anchor_span or center_span:
                gate['unverified_span'].append(item)
            elif anear <= 0.020:
                gate['near_no_span'].append(item)
        output = {'time': self.target, 'gate_span_audit': gate,
                  'bicycle_xframe_audit': gate['bicycle_xframe_audit'],
                  'bicycle_context_audit': gate['bicycle_context_audit']}
        if not self.count:
            reason = 'no_trace_window'
            output.update(max_det=0, max_track=0, max_road=0)
        else:
            maximum = self.maximum
            minimum = self.minimum
            output.update(max_det=maximum['detections'], max_track=maximum['tracks'], max_road=maximum['road_tracks'],
                          crossing_events_nearby=self.events,
                          outside_road_delta=maximum['rejected_outside_road'] - minimum['rejected_outside_road'],
                          confirmation_reject_delta=maximum['rejected_unconfirmed_side'] - minimum['rejected_unconfirmed_side'],
                          cooldown_reject_delta=maximum['rejected_cooldown'] - minimum['rejected_cooldown'],
                          road_edge_rescue_delta=maximum['road_edge_rescues'] - minimum['road_edge_rescues'])
            if output['max_det'] <= 0:
                reason = 'detector_miss'
            elif output['max_track'] <= 0:
                reason = 'tracker_miss'
            elif output['max_road'] <= 0 or output['outside_road_delta'] > 0:
                reason = 'road_zone_reject'
            elif output['cooldown_reject_delta'] > 0:
                reason = 'crossing_cooldown_reject'
            elif output['confirmation_reject_delta'] > 0:
                reason = 'crossing_confirmation_reject'
            elif gate['anchor_span']:
                reason = 'crossing_anchor_span_reject'
            elif gate['center_only_span']:
                reason = 'crossing_center_only_span'
            elif gate.get('extension_only_span'):
                reason = 'crossing_outside_segment_geometry'
            elif gate.get('unverified_span'):
                reason = 'crossing_unverified_span'
            elif gate['near_no_span']:
                reason = 'crossing_near_no_span'
            else:
                reason = 'crossing_gate_miss'
        if self.proposal_enabled:
            output["crossing_proposal_audit"] = {
                "scope": ("matched_track" if self.track is not None else "nearby_time_window")
                if self.proposals else "no_proposal_evidence",
                "backend_persistence": "unverified", "records": [dict(value) for value in self.proposals.values()],
                "records_limit": TRACE_EVENT_AUDIT_RECORDS_LIMIT, "truncated": self.proposals_truncated,
            }
        if self.delivery_enabled:
            output["event_delivery_audit"] = {
                "scope": ("matched_track" if self.track is not None else "nearby_time_window")
                if self.deliveries else "no_delivery_evidence",
                "records": [dict(value) for value in self.deliveries.values()],
                "records_limit": TRACE_EVENT_AUDIT_RECORDS_LIMIT, "truncated": self.deliveries_truncated,
                "summary_scope": "session_global",
                "dropped_records": self.delivery_summary["delivery_audit_dropped"] if self.delivery_summary else None,
                "delivery_drain_complete": self.delivery_summary["delivery_drain_complete"] if self.delivery_summary else None,
                "pending_events": self.delivery_summary["pending_events"] if self.delivery_summary else None,
            }
        # A known producer proposal cannot be explained as a gate rejection.
        # A receipt records transport/backend acknowledgement, never GT identity.
        if self.track is not None:
            if self.deliveries:
                reason = "crossing_delivery_observed"
            elif self.proposals:
                reason = "crossing_proposal_observed"
        output['reason'] = reason
        output['diagnosis_scope'] = _diagnosis_scope(reason, gate, self.track)
        if not self.count:
            output['diagnosis_scope']['counters'] = "no_trace_window"
        return output


def diagnose_trace(session_id: int, times: Iterable[float], window_seconds: float = 0.60, *, tracking_ids: Iterable[int | None] | None = None) -> dict:
    """Aggregate requested windows without retaining the full JSONL in memory.

    First pass captures counters, gate extrema and bounded source-order audits.
    A second linear pass refreshes only selected context identities, preserving
    delayed guard outcomes even with unordered source times. Both passes read
    the same byte boundary; newly appended live rows belong to the next request.
    """
    targets = list(times)
    target_tracks = list(tracking_ids) if tracking_ids is not None else [None] * len(targets)
    if len(target_tracks) != len(targets):
        raise ValueError("tracking_ids must align with times")
    path = trace_path(session_id)
    if not path.exists():
        return {"available": False, "session_id": int(session_id), "items": []}
    window = max(0.05, min(2.0, float(window_seconds)))
    groups = {}
    requests = []
    for raw_time, tracking_id in zip(targets, target_tracks):
        key = max(0.0, float(raw_time)), tracking_id
        if key not in groups:
            groups[key] = _TraceWindow(*key)
        requests.append(groups[key])
    windows = list(groups.values())
    if not windows:
        return {"available": True, "session_id": int(session_id), "window_seconds": window, "items": []}
    ordered = sorted((item.target, index) for index, item in enumerate(windows))
    target_times = [target for target, _index in ordered]
    with path.open("rb") as handle:
        byte_limit = os.fstat(handle.fileno()).st_size

        def rows():
            handle.seek(0)
            remaining = byte_limit
            while remaining:
                line = handle.readline(remaining)
                if not line:
                    break
                remaining -= len(line)
                try:
                    row = json.loads(line)
                except (ValueError, UnicodeError):
                    continue
                if isinstance(row, dict):
                    yield row

        proposal_schema_seen = False
        delivery_schema_seen = False
        for row in rows():
            if row.get("kind") == "delivery_summary":
                valid = (type(row.get("session_id")) is int and row["session_id"] == int(session_id) and type(row.get("camera_id")) is int
                         and row["camera_id"] > 0 and type(row.get("delivery_drain_complete")) is bool
                         and all(type(row.get(key)) is int and row[key] >= 0
                                 for key in ("delivery_audit_dropped", "pending_events")))
                for item in windows:
                    item.delivery_enabled = True
                    if valid:
                        item.delivery_summary = row
                continue
            # Producer and receipt clocks belong to the original event, even if
            # their carrier observation/acknowledgement arrives much later.
            delivery = row.get("kind") == "event_delivery"
            if "crossing_proposals" in row and not proposal_schema_seen:
                proposal_schema_seen = True
                for item in windows:
                    item.proposal_enabled = True
            if delivery and not delivery_schema_seen:
                delivery_schema_seen = True
                for item in windows:
                    item.delivery_enabled = True
            values = [row] if delivery else row.get("crossing_proposals", [])
            if isinstance(values, list):
                for value in values:
                    if not isinstance(value, dict) or any(
                        key in row and row[key] != value.get(key) for key in ("camera_id", "session_id")
                    ):
                        continue
                    record = _event_audit_record(value, int(session_id), delivery=delivery)
                    if record is None:
                        continue
                    clock = record["source_time_seconds"]
                    lower = bisect_left(target_times, nextafter(clock - window, -inf))
                    upper = bisect_right(target_times, nextafter(clock + window, inf))
                    for position in range(lower, upper):
                        item = windows[ordered[position][1]]
                        if abs(clock - item.target) <= window:
                            item.observe_event_audit(record, delivery=delivery)
            if delivery:
                continue
            geometry = _finite_geometry_context(row)
            if geometry is not None:
                for item in windows:
                    if item.geometry_context is None:
                        item.geometry_context = geometry
                continue
            try:
                clock = float(row.get("source_time_seconds", -9999.0))
            except (TypeError, ValueError):
                continue
            # Expand the search by one representable float, then retain the
            # original abs-distance predicate at both inclusive boundaries.
            lower = bisect_left(target_times, nextafter(clock - window, -inf))
            upper = bisect_right(target_times, nextafter(clock + window, inf))
            for position in range(lower, upper):
                index = ordered[position][1]
                if abs(clock - windows[index].target) <= window:
                    windows[index].observe(row)
        subscribers = {}
        for item in windows:
            for key in item.context:
                subscribers.setdefault(key, []).append(item)
        if subscribers:
            for row in rows():
                for audit in row.get("bicycle_xframe_decision_audit", []) or []:
                    if not isinstance(audit, dict):
                        continue
                    key = _context_decision_key(audit)
                    for item in subscribers.get(key, []):
                        item.context[key] = audit
    return {"available": True, "session_id": int(session_id), "window_seconds": window,
            "items": [item.finish() for item in requests]}
