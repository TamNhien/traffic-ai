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


def point_in_rect(point: tuple[float, float], rect: Rect) -> bool:
    x, y = point
    x1, y1, x2, y2 = rect
    return x1 <= x <= x2 and y1 <= y <= y2


def expand_rider_envelope(target: Rect, frame_width: float, frame_height: float) -> Rect:
    """Area where the physical bike is expected relative to a rider/person box.

    A rider PERSON box often covers torso/head while the motorcycle detection is
    lower and only partly overlaps the target MOTORCYCLE box. V0.5.23 ignored
    such evidence because it required direct overlap with the target. The
    envelope deliberately grows more below than above the candidate.
    """
    x1, y1, x2, y2 = target
    width = max(1.0, x2 - x1)
    height = max(1.0, y2 - y1)
    return (
        max(0.0, x1 - width * 0.70),
        max(0.0, y1 - height * 0.18),
        min(float(frame_width), x2 + width * 0.70),
        min(float(frame_height), y2 + height * 0.95),
    )


def nearby_two_wheel_support(target: Rect, evidence: Rect, frame_width: float, frame_height: float) -> bool:
    """True for a two-wheel detection in the rider's lower/nearby envelope.

    This is intentionally stricter than merely being in the expanded crop so a
    pedestrian standing beside a parked motorcycle is not automatically treated
    as a rider. The two-wheel center must be horizontally close and its body
    must extend into/below the lower half of the target.
    """
    tx1, ty1, tx2, ty2 = target
    ex1, ey1, ex2, ey2 = evidence
    tw = max(1.0, tx2 - tx1)
    th = max(1.0, ty2 - ty1)
    tcx = (tx1 + tx2) / 2.0
    tcy = (ty1 + ty2) / 2.0
    ecx = (ex1 + ex2) / 2.0
    ecy = (ey1 + ey2) / 2.0
    envelope = expand_rider_envelope(target, frame_width, frame_height)
    if not point_in_rect((ecx, ecy), envelope):
        return False
    if abs(ecx - tcx) > tw * 0.95:
        return False
    # The bike should be at roughly the rider's waist/lower body or below.
    if ey2 < tcy + th * 0.05:
        return False
    # If it barely touches the envelope and is entirely far above, reject it.
    if ecy < ty1 - th * 0.05:
        return False
    return True


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
    nearby_vehicle_confidence: float = 0.0
    overlap_iou: float = 0.0
    target_coverage: float = 0.0
    rider_supported: bool = False
    hard_reject: bool = False


def human_dominates_two_wheel_candidate(
    target_rect: Rect,
    target_label: str,
    target_confidence: float,
    person_rect: Rect | None,
    person_confidence: float,
    vehicle_evidence_confidence: float = 0.0,
    nearby_vehicle_evidence_confidence: float = 0.0,
    speed_ratio: float = 0.0,
    *,
    min_person_confidence: float = 0.28,
    min_iou: float = 0.48,
    min_target_coverage: float = 0.72,
    min_width_ratio: float = 0.66,
    min_height_ratio: float = 0.70,
    min_person_like_aspect: float = 1.18,
    confidence_margin: float = 0.06,
    min_nearby_rider_confidence: float = 0.14,
    min_motion_rider_confidence: float = 0.10,
    min_rider_speed_ratio: float = 0.0018,
) -> HumanGuardDecision:
    """Decide whether a two-wheel track is actually a pedestrian.

    V0.5.24 is rider-aware. A real rider can have a tall MOTORCYCLE box almost
    identical to a PERSON box while the physical motorcycle is detected lower
    in the crop and overlaps only weakly with the target. Nearby lower two-wheel
    evidence and coherent vehicle-like motion therefore *protect* the track.

    A standalone pedestrian is rejected only when PERSON dominates and there is
    no convincing direct/nearby two-wheel evidence. The worker adds temporal
    confirmation so one ambiguous frame cannot permanently kill a rider track.
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
    direct_vehicle_conf = float(vehicle_evidence_confidence)
    nearby_vehicle_conf = float(nearby_vehicle_evidence_confidence)
    target_conf = float(target_confidence)
    motion_ratio = max(0.0, float(speed_ratio))

    direct_competitive = direct_vehicle_conf >= max(0.20, person_conf - float(confidence_margin) - 0.03)
    nearby_competitive = nearby_vehicle_conf >= max(float(min_nearby_rider_confidence), person_conf - 0.34)
    motion_supported = (
        motion_ratio >= float(min_rider_speed_ratio)
        and max(direct_vehicle_conf, nearby_vehicle_conf) >= float(min_motion_rider_confidence)
    )
    rider_supported = direct_competitive or nearby_competitive or motion_supported

    person_strong = person_conf >= max(float(min_person_confidence), target_conf * 0.78)
    hard_person = (
        person_conf >= 0.74
        and iou >= 0.62
        and coverage >= 0.82
        and max(direct_vehicle_conf, nearby_vehicle_conf) < 0.07
        and motion_ratio < float(min_rider_speed_ratio) * 0.80
    )
    reject = person_strong and not rider_supported
    reason = "person_dominates_two_wheel" if reject else ("rider_evidence" if rider_supported else "")
    return HumanGuardDecision(
        reject,
        reason,
        person_confidence=person_conf,
        vehicle_confidence=direct_vehicle_conf,
        nearby_vehicle_confidence=nearby_vehicle_conf,
        overlap_iou=iou,
        target_coverage=coverage,
        rider_supported=rider_supported,
        hard_reject=hard_person and reject,
    )


class HumanGuardTrackPolicy:
    """Temporal confirmation for pedestrian rejection and rider recovery."""

    def __init__(self, required_strikes: int = 2) -> None:
        self.required_strikes = max(1, int(required_strikes))
        self.strikes: dict[int, int] = {}
        self.rejected: set[int] = set()
        self.riders: set[int] = set()

    def is_rejected(self, track_id: int) -> bool:
        return int(track_id) in self.rejected

    def is_rider(self, track_id: int) -> bool:
        return int(track_id) in self.riders

    def observe(self, track_id: int, decision: HumanGuardDecision | None) -> str:
        tid = int(track_id)
        if decision is None:
            return "rejected" if tid in self.rejected else ("rider" if tid in self.riders else "keep")
        if decision.rider_supported:
            was_rejected = tid in self.rejected
            self.rejected.discard(tid)
            self.strikes.pop(tid, None)
            self.riders.add(tid)
            return "released" if was_rejected else "rider"
        if decision.reject:
            self.riders.discard(tid)
            count = self.strikes.get(tid, 0) + 1
            self.strikes[tid] = count
            if decision.hard_reject or count >= self.required_strikes:
                self.rejected.add(tid)
                return "rejected"
            return "pending"
        self.strikes.pop(tid, None)
        return "keep"


def normalized_distance(a: tuple[float, float], b: tuple[float, float], width: int, height: int) -> float:
    diagonal = max(hypot(width, height), 1.0)
    return hypot(a[0] - b[0], a[1] - b[1]) / diagonal
