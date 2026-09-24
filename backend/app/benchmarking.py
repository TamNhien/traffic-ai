from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import inf
from typing import Iterable, Mapping, Any


@dataclass(slots=True)
class TimedCrossing:
    id: int
    source_time_seconds: float
    direction: str
    vehicle_type: str


def _value(item: Any, name: str, default=None):
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _timed(item: Any) -> TimedCrossing:
    return TimedCrossing(
        id=int(_value(item, "id", 0)),
        source_time_seconds=float(_value(item, "source_time_seconds", 0.0)),
        direction=_enum_value(_value(item, "direction", "unknown")),
        vehicle_type=_enum_value(_value(item, "vehicle_type", "other")),
    )


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
            # Nearest timestamp is primary. Prefer same direction/class only as
            # tie-breakers; those attributes are reported independently below.
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
        })

    false_positives = [
        {
            "ai_event_id": ai[index].id,
            "time": round(ai[index].source_time_seconds, 3),
            "direction": ai[index].direction,
            "vehicle_type": ai[index].vehicle_type,
        }
        for index in sorted(unmatched_ai, key=lambda i: ai[i].source_time_seconds)
    ]

    gt_total = len(gt)
    ai_total = len(ai)
    matched_total = len(matched)
    precision = matched_total / ai_total if ai_total else (1.0 if gt_total == 0 else 0.0)
    recall = matched_total / gt_total if gt_total else (1.0 if ai_total == 0 else 0.0)
    f1 = (2.0 * precision * recall / (precision + recall)) if precision + recall else 0.0
    direction_correct = sum(1 for item in matched if item["direction_correct"])
    class_correct = sum(1 for item in matched if item["class_correct"])

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
        "false_positives": len(false_positives),
        "count_error": ai_total - gt_total,
        "absolute_count_error": abs(ai_total - gt_total),
        "counting_precision": round(precision, 6),
        "counting_recall": round(recall, 6),
        "counting_f1": round(f1, 6),
        "direction_accuracy": round(direction_correct / matched_total, 6) if matched_total else None,
        "class_accuracy": round(class_correct / matched_total, 6) if matched_total else None,
        "matched_items": matched,
        "missed_items": missed,
        "false_positive_items": false_positives,
        "per_class": per_class,
        "per_direction": per_direction,
    }
