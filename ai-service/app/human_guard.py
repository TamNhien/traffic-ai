from __future__ import annotations

from dataclasses import dataclass
from math import hypot

Rect = tuple[float, float, float, float]

TWO_WHEEL_LABELS = {"motorcycle", "bicycle"}


def _area(rect: Rect) -> float:
    x1, y1, x2, y2 = rect
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def intersection_area(a: Rect, b: Rect) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))


def box_iou(a: Rect, b: Rect) -> float:
    inter = intersection_area(a, b)
    if inter <= 0.0:
        return 0.0
    union = _area(a) + _area(b) - inter
    return inter / union if union > 0.0 else 0.0


def coverage_of_target(target: Rect, evidence: Rect) -> float:
    area = _area(target)
    return intersection_area(target, evidence) / area if area > 0.0 else 0.0


def is_person_like_two_wheel_box(rect: Rect, min_aspect: float = 1.18) -> bool:
    x1, y1, x2, y2 = rect
    width = max(1.0, x2 - x1)
    height = max(1.0, y2 - y1)
    return height / width >= max(0.5, float(min_aspect))


@dataclass(slots=True)
class HumanGuardDecision:
    reject: bool
    reason: str = ""
    person_confidence: float = 0.0
    vehicle_confidence: float = 0.0
    overlap_iou: float = 0.0
    target_coverage: float = 0.0


def human_dominates_two_wheel_candidate(
    target_rect: Rect,
    target_label: str,
    target_confidence: float,
    person_rect: Rect | None,
    person_confidence: float,
    vehicle_evidence_confidence: float = 0.0,
    *,
    min_person_confidence: float = 0.28,
    min_iou: float = 0.48,
    min_target_coverage: float = 0.72,
    min_width_ratio: float = 0.66,
    min_height_ratio: float = 0.70,
    min_person_like_aspect: float = 1.18,
    confidence_margin: float = 0.06,
) -> HumanGuardDecision:
    """Reject a two-wheel candidate only when a person detection dominates it.

    This guard is deliberately conservative. A rider usually produces a person
    box that is narrower than the whole motorcycle/rider box and the verifier
    still sees two-wheel evidence. A pedestrian misdetected as motorcycle tends
    to produce almost the same tall/narrow box for PERSON and MOTORCYCLE.
    """
    label = str(target_label)
    if label not in TWO_WHEEL_LABELS or person_rect is None:
        return HumanGuardDecision(False)
    if not is_person_like_two_wheel_box(target_rect, min_person_like_aspect):
        return HumanGuardDecision(False)

    tx1, ty1, tx2, ty2 = target_rect
    px1, py1, px2, py2 = person_rect
    tw = max(1.0, tx2 - tx1)
    th = max(1.0, ty2 - ty1)
    pw = max(1.0, px2 - px1)
    ph = max(1.0, py2 - py1)
    iou = box_iou(target_rect, person_rect)
    coverage = coverage_of_target(target_rect, person_rect)
    geometry_dominates = (
        iou >= float(min_iou)
        or (
            coverage >= float(min_target_coverage)
            and pw / tw >= float(min_width_ratio)
            and ph / th >= float(min_height_ratio)
        )
    )
    if not geometry_dominates:
        return HumanGuardDecision(False, overlap_iou=iou, target_coverage=coverage)

    person_conf = float(person_confidence)
    vehicle_conf = float(vehicle_evidence_confidence)
    target_conf = float(target_confidence)
    # A real rider can create both a person and motorcycle detection. Keep the
    # vehicle whenever the verifier still has competitive two-wheel evidence.
    competitive_vehicle = vehicle_conf >= max(0.22, person_conf - float(confidence_margin))
    person_strong = person_conf >= max(float(min_person_confidence), target_conf * 0.78)
    reject = person_strong and not competitive_vehicle
    reason = "person_dominates_two_wheel" if reject else ""
    return HumanGuardDecision(
        reject,
        reason,
        person_confidence=person_conf,
        vehicle_confidence=vehicle_conf,
        overlap_iou=iou,
        target_coverage=coverage,
    )


def normalized_distance(a: tuple[float, float], b: tuple[float, float], width: int, height: int) -> float:
    diagonal = max(hypot(width, height), 1.0)
    return hypot(a[0] - b[0], a[1] - b[1]) / diagonal
