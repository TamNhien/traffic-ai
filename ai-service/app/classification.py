from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from math import hypot

Rect = tuple[float, float, float, float]
VEHICLE_CLASSES = {"bicycle", "car", "motorcycle", "bus", "truck"}
TWO_WHEEL_CLASSES = {"bicycle", "motorcycle"}
HEAVY_CLASSES = {"car", "bus", "truck"}


def vehicle_family(label: str) -> str:
    value = str(label)
    if value in TWO_WHEEL_CLASSES:
        return "two-wheel"
    if value in HEAVY_CLASSES:
        return "four-wheel"
    return value


def _area(rect: Rect) -> float:
    x1, y1, x2, y2 = rect
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def _intersection(a: Rect, b: Rect) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))


def _iou(a: Rect, b: Rect) -> float:
    inter = _intersection(a, b)
    if inter <= 0.0:
        return 0.0
    union = _area(a) + _area(b) - inter
    return inter / union if union > 0.0 else 0.0


def _coverage(target: Rect, evidence: Rect) -> float:
    area = _area(target)
    return _intersection(target, evidence) / area if area > 0.0 else 0.0


def _evidence_coverage(target: Rect, evidence: Rect) -> float:
    area = _area(evidence)
    return _intersection(target, evidence) / area if area > 0.0 else 0.0


@dataclass(frozen=True, slots=True)
class RefineCandidate:
    label: str
    confidence: float
    rect: Rect


@dataclass(frozen=True, slots=True)
class TargetRefineMatch:
    label: str
    confidence: float
    target_iou: float
    target_coverage: float
    evidence_coverage: float
    center_distance_ratio: float
    score: float


def select_target_refinement(
    target: Rect,
    candidates: list[RefineCandidate],
    *,
    min_iou: float = 0.08,
    min_target_coverage: float = 0.16,
    min_evidence_coverage: float = 0.50,
    max_center_distance_ratio: float = 0.58,
    target_family: str | None = None,
) -> TargetRefineMatch | None:
    """Choose the refiner detection that belongs to the tracked target.

    Older crossing refinement simply picked the highest-confidence object inside
    an expanded crop. In dense Vietnamese traffic that can be a *different*
    motorcycle parked beside the actual bicycle/truck candidate. V0.5.26 scores
    every refiner box against the original target box and refuses unrelated
    neighbors. This makes the custom best.pt a target classifier instead of a
    generic crop detector.
    """

    tx1, ty1, tx2, ty2 = [float(v) for v in target]
    tw = max(1.0, tx2 - tx1)
    th = max(1.0, ty2 - ty1)
    tcx = (tx1 + tx2) / 2.0
    tcy = (ty1 + ty2) / 2.0
    tdiag = max(hypot(tw, th), 1.0)

    best: TargetRefineMatch | None = None
    for candidate in candidates:
        label = str(candidate.label)
        if label not in VEHICLE_CLASSES:
            continue
        if target_family is not None and vehicle_family(label) != str(target_family):
            continue
        rect = tuple(float(v) for v in candidate.rect)
        ex1, ey1, ex2, ey2 = rect
        ecx = (ex1 + ex2) / 2.0
        ecy = (ey1 + ey2) / 2.0
        iou = _iou(target, rect)
        target_cov = _coverage(target, rect)
        evidence_cov = _evidence_coverage(target, rect)
        center_ratio = hypot(ecx - tcx, ecy - tcy) / tdiag
        center_ok = center_ratio <= float(max_center_distance_ratio)
        geometry_ok = (
            iou >= float(min_iou)
            or target_cov >= float(min_target_coverage)
            or evidence_cov >= float(min_evidence_coverage)
            or (center_ok and evidence_cov >= 0.30)
        )
        if not geometry_ok:
            continue

        # Confidence still matters most, but target geometry prevents a nearby
        # parked motorcycle from winning only because it has a larger score.
        geometry = max(
            min(1.0, iou * 2.2),
            min(1.0, target_cov * 1.6),
            min(1.0, evidence_cov),
            max(0.0, 1.0 - center_ratio),
        )
        score = max(0.0, float(candidate.confidence)) * (0.58 + 0.42 * geometry)
        match = TargetRefineMatch(
            label=label,
            confidence=float(candidate.confidence),
            target_iou=iou,
            target_coverage=target_cov,
            evidence_coverage=evidence_cov,
            center_distance_ratio=center_ratio,
            score=score,
        )
        if best is None or (match.score, match.confidence) > (best.score, best.confidence):
            best = match
    return best


class TrackLabelSmoother:
    def __init__(self, history: int = 24) -> None:
        self.history = max(3, history)
        self._samples: dict[int, deque[tuple[str, float]]] = defaultdict(lambda: deque(maxlen=self.history))

    def update(self, track_id: int, label: str, confidence: float) -> None:
        self._samples[int(track_id)].append((str(label), float(confidence)))

    def evidence(self, track_id: int) -> tuple[dict[str, float], dict[str, int]]:
        samples = self._samples.get(int(track_id))
        scores: dict[str, float] = defaultdict(float)
        hits: dict[str, int] = defaultdict(int)
        if not samples:
            return {}, {}
        for age, (label, confidence) in enumerate(reversed(samples)):
            recency = 0.965 ** age
            scores[label] += (max(confidence, 0.01) ** 2) * recency
            hits[label] += 1
        return dict(scores), dict(hits)

    def stable_label(self, track_id: int, fallback: str) -> tuple[str, float, int]:
        scores, hits = self.evidence(track_id)
        if not scores:
            return fallback, 0.0, 0
        label = max(scores, key=lambda item: (scores[item], hits.get(item, 0)))
        total = sum(scores.values()) or 1.0
        return label, scores[label] / total, hits.get(label, 0)


class VehicleClassPolicy:
    """Target-aware vehicle class policy for Vietnamese mixed traffic.

    V0.5.25 was intentionally motorcycle-biased: ambiguous bicycle tracks were
    forced to motorcycle unless the *primary* detector already produced many
    bicycle votes. That protected against false bicycles, but it also made a
    true bicycle impossible to recover when YOLO26s consistently called it a
    motorcycle. Likewise a small light truck that YOLO26s called `car` could not
    be corrected unless the one-shot refiner was unusually confident.

    V0.5.26 keeps temporal smoothing, but a target-matched custom refiner can
    override inside the same vehicle family with asymmetric safety thresholds.
    Demoting a truck/bus to car remains harder than promoting a car to truck.
    """

    def __init__(
        self,
        bicycle_certainty: float = 0.80,
        bicycle_hits: int = 5,
        strong_bicycle_certainty: float = 0.90,
        strong_bicycle_hits: int = 8,
        bicycle_refine_override_conf: float = 0.58,
        truck_refine_override_conf: float = 0.48,
        heavy_refine_override_conf: float = 0.54,
    ) -> None:
        self.bicycle_certainty = float(bicycle_certainty)
        self.bicycle_hits = int(bicycle_hits)
        self.strong_bicycle_certainty = float(strong_bicycle_certainty)
        self.strong_bicycle_hits = int(strong_bicycle_hits)
        self.bicycle_refine_override_conf = float(bicycle_refine_override_conf)
        self.truck_refine_override_conf = float(truck_refine_override_conf)
        self.heavy_refine_override_conf = float(heavy_refine_override_conf)

    def display_label(
        self,
        current_label: str,
        stable_label: str,
        certainty: float,
        hits: int,
        current_confidence: float,
    ) -> str:
        if stable_label in TWO_WHEEL_CLASSES or current_label in TWO_WHEEL_CLASSES:
            bicycle_ok = (
                stable_label == "bicycle"
                and current_label == "bicycle"
                and hits >= self.bicycle_hits
                and certainty >= self.bicycle_certainty
                and current_confidence >= 0.28
            )
            return "bicycle" if bicycle_ok else "motorcycle"
        return stable_label if hits >= 2 else current_label

    def _two_wheel_label(
        self,
        current_label: str,
        stable_label: str,
        certainty: float,
        hits: int,
        refined_label: str | None,
        refined_conf: float,
    ) -> tuple[str, float]:
        base_conf = float(certainty)

        # A target-matched domain refiner is allowed to rescue a true bicycle
        # even when the pretrained detector was motorcycle-biased for the whole
        # track. The threshold remains materially above low-confidence noise.
        if refined_label == "bicycle":
            required = max(self.bicycle_refine_override_conf, min(0.72, base_conf * 0.58))
            if refined_conf >= required:
                return "bicycle", max(base_conf, refined_conf)
        if refined_label == "motorcycle" and refined_conf >= 0.55:
            return "motorcycle", max(base_conf, refined_conf)

        strong_primary_bicycle = (
            stable_label == "bicycle"
            and hits >= self.strong_bicycle_hits
            and certainty >= self.strong_bicycle_certainty
        )
        refined_primary_bicycle = (
            stable_label == "bicycle"
            and hits >= self.bicycle_hits
            and certainty >= self.bicycle_certainty
            and refined_label == "bicycle"
            and refined_conf >= 0.52
        )
        if strong_primary_bicycle or refined_primary_bicycle:
            return "bicycle", max(base_conf, refined_conf)
        return "motorcycle", max(base_conf, refined_conf if refined_label == "motorcycle" else 0.0)

    def _heavy_label(
        self,
        current_label: str,
        stable_label: str,
        certainty: float,
        hits: int,
        refined_label: str | None,
        refined_conf: float,
    ) -> tuple[str, float]:
        base = stable_label if hits >= 2 and stable_label in HEAVY_CLASSES else current_label
        if base not in HEAVY_CLASSES:
            base = stable_label if stable_label in HEAVY_CLASSES else current_label
        base_conf = float(certainty)

        if refined_label not in HEAVY_CLASSES:
            return base, base_conf
        if refined_label == base:
            return base, max(base_conf, refined_conf)

        # Small delivery trucks are frequently COCO-car shaped from a frontal
        # high-angle camera. Promote CAR -> TRUCK at a lower threshold when the
        # target-matched domain refiner sees truck. The reverse correction needs
        # much stronger evidence so a real truck is not flattened back to car.
        if refined_label == "truck" and base in {"car", "bus"}:
            required = max(self.truck_refine_override_conf, min(0.62, base_conf * 0.48))
            if refined_conf >= required:
                return "truck", max(base_conf, refined_conf)
        elif refined_label == "bus" and base in {"car", "truck"}:
            required = max(self.heavy_refine_override_conf, min(0.68, base_conf * 0.55))
            if refined_conf >= required:
                return "bus", max(base_conf, refined_conf)
        elif refined_label == "car" and base in {"truck", "bus"}:
            # Demotion is deliberately conservative.
            if refined_conf >= max(0.70, base_conf * 0.72):
                return "car", max(base_conf, refined_conf)
        elif refined_conf >= max(self.heavy_refine_override_conf + 0.08, base_conf * 0.60):
            return refined_label, max(base_conf, refined_conf)

        return base, base_conf

    def final_label(
        self,
        current_label: str,
        stable_label: str,
        certainty: float,
        hits: int,
        refined: tuple[str, float] | None = None,
    ) -> tuple[str, float]:
        refined_label, refined_conf = refined if refined is not None else (None, 0.0)
        base_conf = float(certainty)

        if stable_label in TWO_WHEEL_CLASSES or current_label in TWO_WHEEL_CLASSES:
            return self._two_wheel_label(
                current_label, stable_label, certainty, hits, refined_label, float(refined_conf)
            )

        if stable_label in HEAVY_CLASSES or current_label in HEAVY_CLASSES:
            return self._heavy_label(
                current_label, stable_label, certainty, hits, refined_label, float(refined_conf)
            )

        return stable_label or current_label or "other", base_conf
