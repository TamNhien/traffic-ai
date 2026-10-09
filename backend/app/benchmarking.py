from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
from math import inf, isfinite
from typing import Iterable, Mapping, Any
from urllib.parse import urlsplit, urlunsplit
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile


BENCHMARK_TRACE_EXPORT_MAX_BYTES = 128 * 1024 * 1024


class BenchmarkTraceTooLarge(ValueError):
    """The trace cannot fit in one diagnostic download."""


@dataclass(frozen=True, slots=True)
class BenchmarkTraceArchive:
    """Closed gzip bytes and source metadata; the backend never inflates them."""
    content: bytes
    source_bytes: int
    source_sha256: str
    compressed_sha256: str


def read_benchmark_trace_chunks(chunks: Iterable[bytes], max_bytes: int = BENCHMARK_TRACE_EXPORT_MAX_BYTES) -> bytes:
    """Stop reading immediately at the bound; never export a truncated trace."""
    payload = bytearray()
    for chunk in chunks:
        if len(payload) + len(chunk) > max_bytes:
            raise BenchmarkTraceTooLarge("Benchmark trace exceeds the download limit")
        payload.extend(chunk)
    return bytes(payload)


def benchmark_source_identity(source: str | None) -> str | None:
    """Keep clip/stream identity without URL credentials or signed queries."""
    if not source:
        return None
    try:
        parsed = urlsplit(str(source))
        if parsed.scheme.lower() in {"rtsp", "rtsps", "http", "https", "ftp", "sftp"}:
            hostname = parsed.hostname
            if not hostname:
                return "[source omitted]"
            if ":" in hostname:
                hostname = f"[{hostname}]"
            port = f":{parsed.port}" if parsed.port is not None else ""
            return urlunsplit((parsed.scheme, hostname + port, parsed.path, "", ""))
    except ValueError:
        return "[source omitted]"
    if "://" in str(source) and parsed.scheme.lower() != "file":
        return "[source omitted]"
    # Windows and POSIX paths are both possible when importing older sessions.
    # A local file basename is enough to correlate snapshots with their clip.
    return str(source).replace("\\", "/").rsplit("/", 1)[-1].split("?", 1)[0].split("#", 1)[0]


def _benchmark_export_value(value: Any) -> Any:
    """Copy JSON data; sanitize source URLs without mutating the live report."""
    if isinstance(value, Mapping):
        return {
            key: benchmark_source_identity(item) if key == "source_url" else _benchmark_export_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_benchmark_export_value(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


def build_benchmark_export(
    *, report: dict, marks: list[dict], events: list[dict], session: dict,
    config: dict, exported_at: datetime, trace: bytes | BenchmarkTraceArchive | None = None,
    trace_reason: str = "not_found",
) -> bytes:
    """Build a read-only evidence ZIP, with explicit optional trace status."""
    compressed_trace = trace if isinstance(trace, BenchmarkTraceArchive) else None
    trace = compressed_trace.content if compressed_trace is not None else trace
    if trace is not None and len(trace) > BENCHMARK_TRACE_EXPORT_MAX_BYTES:
        raise BenchmarkTraceTooLarge("Benchmark trace exceeds the download limit")
    if trace == b"":
        trace, trace_reason = None, "empty"
    files: dict[str, bytes] = {}
    for filename, payload in (
        ("report.json", report), ("ground-truth.json", marks),
        ("events.json", events), ("session.json", session), ("config.json", config),
    ):
        files[filename] = (json.dumps(
            _benchmark_export_value(payload), ensure_ascii=False,
            allow_nan=False, sort_keys=True, indent=2,
        ) + "\n").encode("utf-8")
    if trace is not None:
        files["benchmark-trace.jsonl.gz" if compressed_trace is not None else "benchmark-trace.jsonl"] = trace
    trace_metadata = {
        "available": trace is not None, "reason": "available" if trace is not None else trace_reason,
        "bytes": len(trace) if trace is not None else 0,
        "max_bytes": BENCHMARK_TRACE_EXPORT_MAX_BYTES,
        "encoding": "gzip" if compressed_trace is not None else "identity",
        "closed": True if compressed_trace is not None else None,
    }
    if compressed_trace is not None and trace is not None:
        # Only the compressed representation is retained in backend memory.
        # Consumers can verify these certified original bytes after unpacking.
        if (not trace.startswith(b"\x1f\x8b") or sha256(trace).hexdigest() != compressed_trace.compressed_sha256
                or compressed_trace.source_bytes < 0
                or len(compressed_trace.source_sha256) != 64
                or any(c not in "0123456789abcdef" for c in compressed_trace.source_sha256)):
            raise ValueError("Invalid compressed benchmark trace metadata")
        trace_metadata.update(source_bytes=compressed_trace.source_bytes,
                              source_sha256=compressed_trace.source_sha256,
                              compressed_sha256=compressed_trace.compressed_sha256)
    manifest = {
        "format": "traffic-ai-benchmark-diagnostics", "schema_version": 1,
        "benchmark_id": report["benchmark"]["id"],
        "session_id": report["session_id"], "exported_at": exported_at.isoformat(),
        "trace": trace_metadata,
        "files": {
            name: {"bytes": len(data), "sha256": sha256(data).hexdigest()}
            for name, data in files.items()
        },
        "notes": [
            "Report and events use the same database event snapshot; no marks or counts were changed.",
            "A running session can append trace rows or deliver more events after this export.",
            "The trace limit applies to transported bytes. Gzip originals are certified at closure; unpacking may require more disk space.",
            "Benchmark geometry is a stored snapshot; camera settings are current, not historical.",
            "Source credentials and URL queries are omitted; videos, snapshots and model weights are not included.",
        ],
    }
    files["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for filename, data in files.items():
            archive.writestr(filename, data, compress_type=ZIP_STORED if filename.endswith(".gz") else ZIP_DEFLATED)
    return output.getvalue()


@dataclass(slots=True)
class TimedCrossing:
    id: int
    source_time_seconds: float
    direction: str
    vehicle_type: str
    tracking_id: int | None = None
    crossing_method: str | None = None
    confidence: float | None = None
    crossing_x: float | None = None
    crossing_y: float | None = None


def _value(item: Any, name: str, default=None):
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _timed(item: Any) -> TimedCrossing:
    tracking_id = _value(item, "tracking_id")
    confidence = _value(item, "confidence")
    return TimedCrossing(
        id=int(_value(item, "id", 0)),
        source_time_seconds=float(_value(item, "source_time_seconds", 0.0)),
        direction=_enum_value(_value(item, "direction", "unknown")),
        vehicle_type=_enum_value(_value(item, "vehicle_type", "other")),
        tracking_id=int(tracking_id) if tracking_id is not None else None,
        crossing_method=str(_value(item, "crossing_method")) if _value(item, "crossing_method") else None,
        confidence=float(confidence) if confidence is not None else None,
        crossing_x=(float(_value(item, "crossing_x")) if _value(item, "crossing_x") is not None else None),
        crossing_y=(float(_value(item, "crossing_y")) if _value(item, "crossing_y") is not None else None),
    )


def _vehicle_family(label: str) -> str:
    if label in {"bicycle", "motorcycle"}:
        return "two-wheel"
    if label in {"car", "bus", "truck"}:
        return "four-wheel"
    return label


def _false_positive_diagnostics(
    false_positive_events: list[TimedCrossing],
    all_ai_events: list[TimedCrossing],
    matched: list[dict],
    tolerance: float,
) -> tuple[list[dict], dict[str, int], str | None]:
    """Explain likely over-count causes without changing benchmark truth.

    These labels are diagnostics, not ground truth. They are intentionally
    conservative: ambiguous unmatched events remain `unmatched_ai_event` rather
    than being force-labeled as duplicate crossings.
    """

    matched_ai_ids = {int(item["ai_event_id"]) for item in matched}
    matched_events = [event for event in all_ai_events if event.id in matched_ai_ids]
    by_track: dict[int, list[TimedCrossing]] = defaultdict(list)
    for event in all_ai_events:
        if event.tracking_id is not None:
            by_track[event.tracking_id].append(event)
    for events in by_track.values():
        events.sort(key=lambda item: item.source_time_seconds)

    diagnostics: list[dict] = []
    reason_counts: Counter[str] = Counter()
    duplicate_window = max(0.35, min(1.25, tolerance * 1.35))

    for event in false_positive_events:
        reason = "unmatched_ai_event"
        detail = "AI có event nhưng không có Ground Truth tương ứng trong cửa sổ ghép."
        near_matched_time_delta = None
        near_matched_spatial_distance = None
        near_matched_crossing_method = None
        near_matched_ai_event_id = None

        if event.source_time_seconds <= 0.50:
            reason = "startup_artifact"
            detail = "Event xuất hiện trong 0,5 giây đầu clip; có khả năng track khởi tạo ngay sát vạch."
        elif event.tracking_id is not None:
            siblings = [
                other for other in by_track.get(event.tracking_id, [])
                if other.id != event.id and abs(other.source_time_seconds - event.source_time_seconds) <= 3.0
            ]
            opposite = [other for other in siblings if other.direction != event.direction]
            if opposite:
                nearest = min(opposite, key=lambda other: abs(other.source_time_seconds - event.source_time_seconds))
                reason = "direction_flip_jitter"
                detail = (
                    f"Cùng canonical track #{event.tracking_id} phát event {nearest.direction.upper()} và "
                    f"{event.direction.upper()} cách nhau {abs(nearest.source_time_seconds-event.source_time_seconds):.2f}s."
                )
            elif siblings:
                nearest = min(siblings, key=lambda other: abs(other.source_time_seconds - event.source_time_seconds))
                reason = "same_track_repeat"
                detail = (
                    f"Cùng canonical track #{event.tracking_id} phát nhiều event cách nhau "
                    f"{abs(nearest.source_time_seconds-event.source_time_seconds):.2f}s."
                )

        if reason == "unmatched_ai_event":
            near_matched = [
                other for other in matched_events
                if abs(other.source_time_seconds - event.source_time_seconds) <= duplicate_window
                and _vehicle_family(other.vehicle_type) == _vehicle_family(event.vehicle_type)
                and other.direction == event.direction
            ]
            if near_matched:
                # A temporally closer vehicle in another lane must not hide a
                # matched event at this actual crossing point. Prefer a spatial
                # candidate inside the existing audit radius; no scoring changes.
                def candidate_key(other: TimedCrossing) -> tuple[int, float, float, int]:
                    spatial_distance = inf
                    if (
                        event.crossing_x is not None and event.crossing_y is not None
                        and other.crossing_x is not None and other.crossing_y is not None
                    ):
                        dx = event.crossing_x - other.crossing_x
                        dy = event.crossing_y - other.crossing_y
                        spatial_distance = (dx * dx + dy * dy) ** 0.5
                        spatial_priority = 0 if spatial_distance <= 0.045 else 2
                    else:
                        spatial_priority = 1
                    # V0.5.54: among candidates inside the same audit radius,
                    # use the closest physical point. Otherwise a temporally
                    # nearer vehicle in an adjacent lane can still hide the
                    # actual same-point rediscovery. IDs break exact ties so
                    # source/input order cannot change diagnostic attribution.
                    return (
                        spatial_priority,
                        spatial_distance if spatial_priority == 0 else inf,
                        abs(other.source_time_seconds - event.source_time_seconds),
                        other.id,
                    )

                nearest = min(near_matched, key=candidate_key)
                dt = abs(nearest.source_time_seconds - event.source_time_seconds)
                near_matched_ai_event_id = nearest.id
                near_matched_time_delta = round(dt, 3)
                near_matched_crossing_method = nearest.crossing_method
                spatial_distance = None
                if (
                    event.crossing_x is not None and event.crossing_y is not None
                    and nearest.crossing_x is not None and nearest.crossing_y is not None
                ):
                    dx = float(event.crossing_x) - float(nearest.crossing_x)
                    dy = float(event.crossing_y) - float(nearest.crossing_y)
                    spatial_distance = (dx * dx + dy * dy) ** 0.5
                    near_matched_spatial_distance = round(spatial_distance, 6)
                if spatial_distance is not None and spatial_distance <= 0.045:
                    reason = "spatial_duplicate_near_gt"
                    detail = (
                        f"AI event khác đã khớp GT cách {dt:.2f}s và điểm cắt chỉ lệch {spatial_distance:.3f}; "
                        f"method {nearest.crossing_method or '?'} → {event.crossing_method or '?'}. "
                        "Khả năng ID switch/duplicate crossing cao."
                    )
                elif spatial_distance is None:
                    reason = "duplicate_near_gt"
                    detail = (
                        f"Có một AI event khác đã khớp GT chỉ cách {dt:.2f}s nhưng event cũ thiếu tọa độ crossing; "
                        "chỉ xem đây là nghi vấn duplicate."
                    )
            if reason == "unmatched_ai_event" and event.crossing_method == "rescued":
                reason = "rescued_gap_unmatched"
                detail = "Event được Crossing Engine cứu qua gap dài nhưng không có GT tương ứng."
            elif reason == "unmatched_ai_event" and event.crossing_method == "interpolated":
                reason = "interpolated_unmatched"
                detail = "Event nội suy qua vạch không có GT tương ứng; cần kiểm tra jitter/dead-band tại timecode này."
            elif reason == "unmatched_ai_event" and event.crossing_method == "direct":
                reason = "direct_unmatched"
                detail = "Event cắt trực tiếp nhưng không có GT; kiểm tra track/anchor có thật sự thuộc xe chạy qua vạch hay không."

        reason_counts[reason] += 1
        diagnostics.append({
            "ai_event_id": event.id,
            "time": round(event.source_time_seconds, 3),
            "direction": event.direction,
            "vehicle_type": event.vehicle_type,
            "tracking_id": event.tracking_id,
            "crossing_method": event.crossing_method,
            "confidence": event.confidence,
            "reason": reason,
            "detail": detail,
            "near_matched_time_delta": near_matched_time_delta,
            "near_matched_spatial_distance": near_matched_spatial_distance,
            "near_matched_crossing_method": near_matched_crossing_method,
            "near_matched_ai_event_id": near_matched_ai_event_id,
        })

    dominant = reason_counts.most_common(1)[0][0] if reason_counts else None
    return diagnostics, dict(reason_counts), dominant


def _attach_unmatched_review_candidates(
    missed_items: list[dict],
    false_positive_events: list[TimedCrossing],
    false_positive_items: list[dict],
    tolerance: float,
) -> int:
    """Link missed GT rows to nearby unmatched AI events for human review.

    This is an *audit-only* pairing. It never changes benchmark metrics or the
    official global temporal assignment.  V0.5.44 uses it to make the two audit
    lists actionable: a missed GT can show the nearest unmatched AI event just
    outside the matching window, and the corresponding false-positive row can
    point back to that GT.  That makes time-sync drift distinguishable from a
    genuine detector/gate miss without silently inflating Recall/Precision.
    """

    if not missed_items or not false_positive_events or not false_positive_items:
        return 0

    # The review window is deliberately wider than the scoring tolerance, but
    # still bounded so unrelated traffic in a dense scene is not paired merely
    # for display. For the default ±0.75 s benchmark this becomes 1.50 s.
    review_window = max(float(tolerance) + 0.25, min(2.0, float(tolerance) * 2.0))
    candidates: list[tuple[float, int, int]] = []
    for miss_index, miss in enumerate(missed_items):
        miss_time = float(miss.get("time", 0.0))
        for event_index, event in enumerate(false_positive_events):
            delta = abs(float(event.source_time_seconds) - miss_time)
            if delta <= review_window:
                candidates.append((delta, miss_index, event_index))

    # Greedy-by-distance is sufficient here because this secondary pairing has
    # no scoring effect. Uniqueness prevents one unmatched AI row from being
    # advertised as the likely candidate for several different GT crossings.
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    used_misses: set[int] = set()
    used_events: set[int] = set()
    fp_by_id = {int(item.get("ai_event_id", -1)): item for item in false_positive_items}
    linked = 0
    for delta, miss_index, event_index in candidates:
        if miss_index in used_misses or event_index in used_events:
            continue
        miss = missed_items[miss_index]
        event = false_positive_events[event_index]
        fp_item = fp_by_id.get(int(event.id))
        if fp_item is None:
            continue

        signed_delta = float(event.source_time_seconds) - float(miss.get("time", 0.0))
        miss["review_candidate"] = {
            "ai_event_id": int(event.id),
            "time": round(float(event.source_time_seconds), 3),
            "delta_seconds": round(signed_delta, 3),
            "outside_scoring_window": abs(signed_delta) > float(tolerance),
            "direction": event.direction,
            "vehicle_type": event.vehicle_type,
            "tracking_id": event.tracking_id,
            "crossing_method": event.crossing_method,
        }
        fp_item["review_ground_truth"] = {
            "ground_truth_id": int(miss.get("ground_truth_id", 0)),
            "time": round(float(miss.get("time", 0.0)), 3),
            "delta_seconds": round(-signed_delta, 3),
            "outside_scoring_window": abs(signed_delta) > float(tolerance),
            "direction": miss.get("direction"),
            "vehicle_type": miss.get("vehicle_type"),
        }
        used_misses.add(miss_index)
        used_events.add(event_index)
        linked += 1
    return linked


def _global_temporal_pairs(
    gt: list[TimedCrossing], ai: list[TimedCrossing], tolerance: float
) -> list[tuple[int, int]]:
    """Order-preserving global one-to-one timestamp assignment.

    The older greedy matcher could consume a flexible AI event for an early GT
    mark and then leave a later GT mark unmatched even though a 2-pair solution
    existed. V0.5.27 first maximizes the number of timestamp-valid matches, then
    minimizes the total absolute time error. Vehicle class and direction are *not*
    used in the assignment, so class/direction accuracy remain independent metrics.
    """

    n, m = len(gt), len(ai)
    matches = [[0] * (m + 1) for _ in range(n + 1)]
    cost = [[0.0] * (m + 1) for _ in range(n + 1)]
    op = [[None] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        op[i][0] = "skip_gt"
    for j in range(1, m + 1):
        op[0][j] = "skip_ai"

    def key(option: tuple[int, float, str]) -> tuple[int, float, int]:
        count, total_cost, action = option
        priority = {"match": 3, "skip_gt": 2, "skip_ai": 1}[action]
        return count, -total_cost, priority

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            options: list[tuple[int, float, str]] = [
                (matches[i - 1][j], cost[i - 1][j], "skip_gt"),
                (matches[i][j - 1], cost[i][j - 1], "skip_ai"),
            ]
            delta = abs(ai[j - 1].source_time_seconds - gt[i - 1].source_time_seconds)
            if delta <= tolerance:
                options.append((matches[i - 1][j - 1] + 1, cost[i - 1][j - 1] + delta, "match"))
            best = max(options, key=key)
            matches[i][j], cost[i][j], op[i][j] = best

    pairs: list[tuple[int, int]] = []
    i, j = n, m
    while i > 0 or j > 0:
        action = op[i][j]
        if action == "match":
            pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif action == "skip_gt":
            i -= 1
        elif action == "skip_ai":
            j -= 1
        elif i > 0:
            i -= 1
        elif j > 0:
            j -= 1
    pairs.reverse()
    return pairs


def _missed_matching_audit(
    mark: TimedCrossing,
    gt: list[TimedCrossing],
    ai: list[TimedCrossing],
    pairs: list[tuple[int, int]],
    tolerance: float,
) -> dict | None:
    """Expose nearby events already used by the current temporal assignment.

    A missed mark's unmatched review candidate is a different list: an event
    close to this mark may already belong to another GT pair. Use the actual
    pair indices and unrounded source clocks so this explanation cannot imply
    that the backend lost an event or that two marks are the same vehicle.
    """
    if not isfinite(mark.source_time_seconds) or not isfinite(tolerance):
        return None
    neighbors: list[tuple[float, int, int, int]] = []
    for gt_index, ai_index in pairs:
        assigned = gt[gt_index]
        event = ai[ai_index]
        if not isfinite(assigned.source_time_seconds) or not isfinite(event.source_time_seconds):
            continue
        delta = event.source_time_seconds - mark.source_time_seconds
        if abs(delta) <= tolerance:
            neighbors.append((abs(delta), event.id, gt_index, ai_index))
    if not neighbors:
        return None
    neighbors.sort()
    records: list[dict] = []
    for _, _, gt_index, ai_index in neighbors[:4]:
        assigned = gt[gt_index]
        event = ai[ai_index]
        records.append({
            "ai_event_id": event.id,
            "ai_time": event.source_time_seconds,
            "delta_seconds": event.source_time_seconds - mark.source_time_seconds,
            "tracking_id": event.tracking_id,
            "direction": event.direction,
            "vehicle_type": event.vehicle_type,
            "assigned_ground_truth_id": assigned.id,
            "assigned_ground_truth_time": assigned.source_time_seconds,
            "assigned_ground_truth_direction": assigned.direction,
            "assigned_ground_truth_vehicle_type": assigned.vehicle_type,
            "assigned_delta_seconds": event.source_time_seconds - assigned.source_time_seconds,
        })
    return {
        "scope": "temporal_neighbor_assignment",
        "identity_scope": "physical_identity_unproven",
        "ground_truth_time": mark.source_time_seconds,
        "window_seconds": tolerance,
        "nearby_matched_events": records,
        "omitted_count": max(0, len(neighbors) - len(records)),
    }



def _attach_temporal_assignment_evidence(
    gt: list[TimedCrossing],
    ai: list[TimedCrossing],
    pairs: list[tuple[int, int]],
    missed_items: list[dict],
    false_positive_items: list[dict],
    tolerance: float,
) -> dict:
    """Audit timestamp competition without inventing physical vehicle identities.

    A GT mark can remain unmatched even with a persisted event inside its
    scoring window when that event is already used by a different GT mark.
    This is not proof that the AI failed to detect the vehicle, or that
    the mark and the nearby event depict the same physical object.

    Audit is read-only: pair assignments, classes, directions, tolerance,
    and scores are never changed.
    """
    by_gt = {gt_index: ai_index for gt_index, ai_index in pairs}
    by_ai = {ai_index: gt_index for gt_index, ai_index in pairs}
    gt_index_by_id = {item.id: index for index, item in enumerate(gt)}
    ai_index_by_id = {item.id: index for index, item in enumerate(ai)}
    misses_with_competition = 0
    misses_without_nearby_ai = 0
    misses_with_unassigned_ai = 0
    false_positives_near_assigned_gt = 0

    for miss in missed_items:
        index = gt_index_by_id[int(miss["ground_truth_id"])]
        mark = gt[index]
        eligible = [
            (abs(event.source_time_seconds - mark.source_time_seconds), event.id, ai_index)
            for ai_index, event in enumerate(ai)
            if abs(event.source_time_seconds - mark.source_time_seconds) <= tolerance
        ]
        eligible.sort()
        records = []
        for _, _, ai_index in eligible[:4]:
            event = ai[ai_index]
            assigned_gt_index = by_ai.get(ai_index)
            records.append({
                "ai_event_id": int(event.id),
                "delta_seconds": round(event.source_time_seconds - mark.source_time_seconds, 4),
                "direction_agrees": event.direction == mark.direction,
                "ai_direction": event.direction,
                "ai_vehicle_type": event.vehicle_type,
                "assigned_ground_truth_id": (
                    int(gt[assigned_gt_index].id) if assigned_gt_index is not None else None
                ),
                "assignment": "assigned_other_gt" if assigned_gt_index is not None else "unassigned",
            })
        claimed = any(record["assignment"] == "assigned_other_gt" for record in records)
        available = any(record["assignment"] == "unassigned" for record in records)
        if claimed:
            misses_with_competition += 1
            status = "persisted_event_claimed_by_other_gt"
        elif available:
            misses_with_unassigned_ai += 1
            status = "unassigned_event_in_window"
        else:
            misses_without_nearby_ai += 1
            status = "no_persisted_event_in_window"
        if eligible:
            miss["temporal_evidence"] = {
                "status": status,
                "nearby_persisted_events": records,
                "candidate_count": len(eligible),
                "truncated": len(eligible) > 4,
                "identity_proven": False,
            }

    for fp in false_positive_items:
        index = ai_index_by_id[int(fp["ai_event_id"])]
        event = ai[index]
        eligible = [
            (abs(mark.source_time_seconds - event.source_time_seconds), mark.id, gt_index)
            for gt_index, mark in enumerate(gt)
            if abs(mark.source_time_seconds - event.source_time_seconds) <= tolerance
        ]
        eligible.sort()
        candidates = []
        for _, _, gt_index in eligible[:4]:
            mark = gt[gt_index]
            assigned_ai_index = by_gt.get(gt_index)
            candidates.append({
                "ground_truth_id": int(mark.id),
                "delta_seconds": round(event.source_time_seconds - mark.source_time_seconds, 4),
                "direction_agrees": mark.direction == event.direction,
                "assigned_ai_event_id": (
                    int(ai[assigned_ai_index].id) if assigned_ai_index is not None else None
                ),
            })
        if any(record["assigned_ai_event_id"] is not None for record in candidates):
            false_positives_near_assigned_gt += 1
        if eligible:
            fp["temporal_evidence"] = {
                "nearby_ground_truth": candidates,
                "candidate_count": len(eligible),
                "truncated": len(eligible) > 4,
                "identity_proven": False,
            }

    return {
        "scope": "timestamp_only_one_to_one",
        "identity_proven": False,
        "scoring_unchanged": True,
        "count_totals_equal": len(gt) == len(ai),
        "paired_within_tolerance": len(pairs),
        "missed_with_claimed_persisted_event": misses_with_competition,
        "missed_with_available_persisted_event": misses_with_unassigned_ai,
        "missed_without_persisted_event_in_window": misses_without_nearby_ai,
        "false_positives_near_assigned_ground_truth": false_positives_near_assigned_gt,
    }


def _empty_ground_truth_report(ai: list[TimedCrossing], tolerance: float) -> dict:
    """Retain AI observations without scoring an unannotated benchmark.

    An empty mark list cannot distinguish a verified empty clip from a newly
    created benchmark. Until marks exist, neither a perfect empty score nor an
    over-count diagnosis is justified by the evidence available to this API.
    """
    class_counts = Counter(event.vehicle_type for event in ai)
    direction_counts = Counter(event.direction for event in ai)
    return {
        "report_readiness": {
            "status": "needs_ground_truth", "scoring_available": False,
            "reason": "no_ground_truth",
        },
        "tolerance_seconds": tolerance,
        "ground_truth_total": 0,
        "ai_total": len(ai),
        "matched": None,
        "missed": None,
        "false_positives": None,
        "count_error": None,
        "absolute_count_error": None,
        "counting_precision": None,
        "counting_recall": None,
        "counting_f1": None,
        "direction_accuracy": None,
        "class_accuracy": None,
        "class_mismatches": None,
        "class_mismatch_items": [],
        "matched_items": [],
        "missed_items": [],
        "false_positive_items": [],
        "false_positive_reason_counts": {},
        "dominant_false_positive_reason": None,
        "unmatched_review_links": None,
        "temporal_assignment_audit": None,
        "per_class": {
            name: {"ground_truth": 0, "ai": count, "difference": None, "correct_matches": None}
            for name, count in sorted(class_counts.items())
        },
        "per_direction": {
            name: {"ground_truth": 0, "ai": direction_counts[name], "difference": None}
            for name in ("in", "out", "unknown") if direction_counts[name]
        },
    }


def match_crossings(ground_truth: Iterable[Any], ai_events: Iterable[Any], tolerance_seconds: float = 0.75) -> dict:
    """Global one-to-one temporal matching for counting benchmarks.

    Matching maximizes valid timestamp pairs and minimizes total time error.
    Direction and vehicle class are scored separately, never used to manufacture
    a better class score.
    """

    tolerance = max(0.05, float(tolerance_seconds))
    # Exact timestamps may belong to different lanes or directions. Canonical
    # IDs break those ties without using class/direction to improve the score;
    # an equivalent query/input order must produce the same report.
    gt = sorted((_timed(item) for item in ground_truth), key=lambda x: (x.source_time_seconds, x.id))
    ai = sorted((_timed(item) for item in ai_events), key=lambda x: (x.source_time_seconds, x.id))
    if not gt:
        return _empty_ground_truth_report(ai, tolerance)
    pairs = _global_temporal_pairs(gt, ai, tolerance)
    matched_ai = {ai_index for _, ai_index in pairs}
    matched_gt = {gt_index for gt_index, _ in pairs}
    matched: list[dict] = []
    missed: list[dict] = []

    for gt_index, ai_index in pairs:
        mark = gt[gt_index]
        event = ai[ai_index]
        matched.append({
            "ground_truth_id": mark.id,
            "ai_event_id": event.id,
            "ground_truth_time": round(mark.source_time_seconds, 3),
            "ai_time": round(event.source_time_seconds, 3),
            "delta_seconds": round(event.source_time_seconds - mark.source_time_seconds, 3),
            "ground_truth_direction": mark.direction,
            "ai_direction": event.direction,
            "direction_correct": event.direction == mark.direction,
            "ground_truth_vehicle_type": mark.vehicle_type,
            "ai_vehicle_type": event.vehicle_type,
            "class_correct": event.vehicle_type == mark.vehicle_type,
            "tracking_id": event.tracking_id,
            "crossing_method": event.crossing_method,
        })

    for gt_index, mark in enumerate(gt):
        if gt_index in matched_gt:
            continue
        miss = {
            "ground_truth_id": mark.id,
            "time": round(mark.source_time_seconds, 3),
            "direction": mark.direction,
            "vehicle_type": mark.vehicle_type,
        }
        matching_audit = _missed_matching_audit(mark, gt, ai, pairs, tolerance)
        if matching_audit is not None:
            miss["matching_audit"] = matching_audit
        missed.append(miss)

    unmatched_ai = set(range(len(ai))) - matched_ai
    false_positive_events = [ai[index] for index in sorted(unmatched_ai, key=lambda i: (ai[i].source_time_seconds, ai[i].id))]
    false_positive_items, false_positive_reason_counts, dominant_false_positive_reason = _false_positive_diagnostics(
        false_positive_events, ai, matched, tolerance
    )
    unmatched_review_links = _attach_unmatched_review_candidates(
        missed, false_positive_events, false_positive_items, tolerance
    )
    temporal_audit = _attach_temporal_assignment_evidence(
        gt, ai, pairs, missed, false_positive_items, tolerance
    )

    gt_total = len(gt)
    ai_total = len(ai)
    matched_total = len(matched)
    precision = matched_total / ai_total if ai_total else (1.0 if gt_total == 0 else 0.0)
    recall = matched_total / gt_total if gt_total else (1.0 if ai_total == 0 else 0.0)
    f1 = (2.0 * precision * recall / (precision + recall)) if precision + recall else 0.0
    direction_correct = sum(1 for item in matched if item["direction_correct"])
    class_correct = sum(1 for item in matched if item["class_correct"])
    class_mismatch_items = [
        {
            "ground_truth_id": item["ground_truth_id"],
            "ai_event_id": item["ai_event_id"],
            "time": item["ground_truth_time"],
            "ai_time": item["ai_time"],
            "direction": item["ground_truth_direction"],
            "ground_truth_vehicle_type": item["ground_truth_vehicle_type"],
            "ai_vehicle_type": item["ai_vehicle_type"],
            "tracking_id": item.get("tracking_id"),
        }
        for item in matched
        if not item["class_correct"]
    ]

    class_names = sorted({item.vehicle_type for item in gt} | {item.vehicle_type for item in ai})
    per_class = {}
    for name in class_names:
        gt_count = sum(1 for item in gt if item.vehicle_type == name)
        ai_count = sum(1 for item in ai if item.vehicle_type == name)
        correct = sum(
            1 for item in matched
            if item["ground_truth_vehicle_type"] == name and item["ai_vehicle_type"] == name
        )
        per_class[name] = {
            "ground_truth": gt_count,
            "ai": ai_count,
            "difference": ai_count - gt_count,
            "correct_matches": correct,
        }

    per_direction = {}
    for name in ("in", "out", "unknown"):
        gt_count = sum(1 for item in gt if item.direction == name)
        ai_count = sum(1 for item in ai if item.direction == name)
        if gt_count or ai_count:
            per_direction[name] = {
                "ground_truth": gt_count,
                "ai": ai_count,
                "difference": ai_count - gt_count,
            }

    return {
        "report_readiness": {"status": "ready", "scoring_available": True, "reason": None},
        "tolerance_seconds": tolerance,
        "ground_truth_total": gt_total,
        "ai_total": ai_total,
        "matched": matched_total,
        "missed": len(missed),
        "false_positives": len(false_positive_items),
        "count_error": ai_total - gt_total,
        "absolute_count_error": abs(ai_total - gt_total),
        "counting_precision": round(precision, 6),
        "counting_recall": round(recall, 6),
        "counting_f1": round(f1, 6),
        "direction_accuracy": round(direction_correct / matched_total, 6) if matched_total else None,
        "class_accuracy": round(class_correct / matched_total, 6) if matched_total else None,
        "class_mismatches": len(class_mismatch_items),
        "class_mismatch_items": class_mismatch_items,
        "matched_items": matched,
        "missed_items": missed,
        "false_positive_items": false_positive_items,
        "false_positive_reason_counts": false_positive_reason_counts,
        "dominant_false_positive_reason": dominant_false_positive_reason,
        "unmatched_review_links": unmatched_review_links,
        "temporal_assignment_audit": temporal_audit,
        "per_class": per_class,
        "per_direction": per_direction,
    }
