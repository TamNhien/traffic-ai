from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import inf
from typing import Iterable, Mapping, Any


@dataclass(slots=True)
class TimedCrossing:
    id: int
    source_time_seconds: float
    direction: str
    vehicle_type: str
    tracking_id: int | None = None
    crossing_method: str | None = None
    confidence: float | None = None


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
            ]
            if near_matched:
                nearest = min(near_matched, key=lambda other: abs(other.source_time_seconds - event.source_time_seconds))
                reason = "duplicate_near_gt"
                detail = (
                    f"Có một AI event khác đã khớp GT chỉ cách {abs(nearest.source_time_seconds-event.source_time_seconds):.2f}s; "
                    "có khả năng ID switch/duplicate crossing."
                )
            elif event.crossing_method == "rescued":
                reason = "rescued_gap_unmatched"
                detail = "Event được Crossing Engine cứu qua gap dài nhưng không có GT tương ứng."
            elif event.crossing_method == "interpolated":
                reason = "interpolated_unmatched"
                detail = "Event nội suy qua vạch không có GT tương ứng; cần kiểm tra jitter/dead-band tại timecode này."
            elif event.crossing_method == "direct":
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
        })

    dominant = reason_counts.most_common(1)[0][0] if reason_counts else None
    return diagnostics, dict(reason_counts), dominant


def match_crossings(ground_truth: Iterable[Any], ai_events: Iterable[Any], tolerance_seconds: float = 0.75) -> dict:
    """Greedy one-to-one temporal matching for counting benchmarks.

    Crossing presence is matched by nearest source-video timestamp inside the
    tolerance window. Direction and vehicle class are scored separately so a
    correctly detected crossing with a wrong class is not misreported as a
    missed vehicle plus a false positive.
    """

    tolerance = max(0.05, float(tolerance_seconds))
    gt = sorted((_timed(item) for item in ground_truth), key=lambda x: x.source_time_seconds)
    ai = sorted((_timed(item) for item in ai_events), key=lambda x: x.source_time_seconds)
    unmatched_ai = set(range(len(ai)))
    matched: list[dict] = []
    missed: list[dict] = []

    for mark in gt:
        best_index = None
        best_score = (inf, inf, inf)
        for index in list(unmatched_ai):
            event = ai[index]
            delta = abs(event.source_time_seconds - mark.source_time_seconds)
            if delta > tolerance:
                continue
            score = (
                delta,
                0 if event.direction == mark.direction else 1,
                0 if event.vehicle_type == mark.vehicle_type else 1,
            )
            if score < best_score:
                best_score = score
                best_index = index
        if best_index is None:
            missed.append({
                "ground_truth_id": mark.id,
                "time": round(mark.source_time_seconds, 3),
                "direction": mark.direction,
                "vehicle_type": mark.vehicle_type,
            })
            continue
        event = ai[best_index]
        unmatched_ai.remove(best_index)
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

    false_positive_events = [ai[index] for index in sorted(unmatched_ai, key=lambda i: ai[i].source_time_seconds)]
    false_positive_items, false_positive_reason_counts, dominant_false_positive_reason = _false_positive_diagnostics(
        false_positive_events, ai, matched, tolerance
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
        "per_class": per_class,
        "per_direction": per_direction,
    }
