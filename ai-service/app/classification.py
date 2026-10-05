from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from math import hypot, isfinite

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


def prioritize_bicycle_xframe_candidates(
    candidates: list[tuple[float, float, int, Rect]],
    max_per_frame: int,
) -> list[tuple[float, float, int, Rect]]:
    """Return the bounded X-frame scan queue in precision-first order.

    V0.5.43 keeps the existing GPU scan budget but removes ByteTrack iteration
    order from the decision: the weak motorcycle nearest the finite counting
    gate gets first chance to accumulate cross-frame bicycle evidence. Lower
    detector confidence is the deterministic tie-break because it is the more
    ambiguous motorcycle candidate; track id is the final stable tie-break.
    """
    budget = max(0, int(max_per_frame))
    if budget <= 0 or not candidates:
        return []
    return sorted(candidates, key=lambda item: (float(item[0]), float(item[1]), int(item[2])))[:budget]


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
        # Overlap with a large neighbor does not waive the caller's local
        # center bound. The crop may contain several real vehicles.
        if not center_ok or not geometry_ok:
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



def select_contextual_bicycle_refinement(
    target: Rect,
    candidates: list[RefineCandidate],
    *,
    min_confidence: float = 0.18,
    max_center_distance_ratio: float = 1.35,
) -> TargetRefineMatch | None:
    """Match a bicycle candidate to a partial two-wheel target at crossing time.

    V0.5.34 still used the ordinary target matcher for its wide context crop.
    That remains too strict when ByteTrack owns only the basket/front wheel while
    the refiner detects the whole bicycle+rider footprint. V0.5.35 first tries a
    relaxed ordinary match, then permits a candidate that substantially overlaps
    a bounded envelope around the tracked target. The envelope is deliberately
    local so a parked bicycle elsewhere in the wide crop cannot steal the event.
    """
    bicycles = [c for c in candidates if str(c.label) == "bicycle" and float(c.confidence) >= float(min_confidence)]
    if not bicycles:
        return None
    strict = select_target_refinement(
        target, bicycles, min_iou=0.02, min_target_coverage=0.06,
        min_evidence_coverage=0.12, max_center_distance_ratio=1.15,
        target_family="two-wheel",
    )
    # The relaxed target matcher can accept a large overlapping box even when
    # its center is far away. Context still has a hard local envelope: apply
    # the caller's bound to the strict path as well as the envelope fallback.
    if strict is not None and strict.center_distance_ratio <= float(max_center_distance_ratio):
        return strict

    tx1, ty1, tx2, ty2 = [float(v) for v in target]
    tw = max(1.0, tx2 - tx1)
    th = max(1.0, ty2 - ty1)
    tcx = (tx1 + tx2) / 2.0
    tcy = (ty1 + ty2) / 2.0
    tdiag = max(hypot(tw, th), 1.0)
    envelope = (tx1 - 0.80 * tw, ty1 - 0.60 * th, tx2 + 0.80 * tw, ty2 + 0.60 * th)

    best: TargetRefineMatch | None = None
    for candidate in bicycles:
        rect = tuple(float(v) for v in candidate.rect)
        ex1, ey1, ex2, ey2 = rect
        ecx = (ex1 + ex2) / 2.0
        ecy = (ey1 + ey2) / 2.0
        center_ratio = hypot(ecx - tcx, ecy - tcy) / tdiag
        if center_ratio > float(max_center_distance_ratio):
            continue
        envelope_cov = _evidence_coverage(envelope, rect)
        target_cov = _coverage(target, rect)
        if envelope_cov < 0.34 and target_cov < 0.05:
            continue
        iou = _iou(target, rect)
        evidence_cov = _evidence_coverage(target, rect)
        geometry = max(envelope_cov, target_cov, max(0.0, 1.0 - center_ratio / max(1.0, float(max_center_distance_ratio))))
        score = float(candidate.confidence) * (0.55 + 0.45 * min(1.0, geometry))
        match = TargetRefineMatch(
            label="bicycle", confidence=float(candidate.confidence), target_iou=iou,
            target_coverage=target_cov, evidence_coverage=evidence_cov,
            center_distance_ratio=center_ratio, score=score,
        )
        if best is None or (match.score, match.confidence) > (best.score, best.confidence):
            best = match
    return best


def select_contextual_two_wheel_refinement(
    target: Rect,
    candidates: list[RefineCandidate],
    *,
    label: str,
    min_confidence: float = 0.10,
    max_center_distance_ratio: float = 1.35,
) -> TargetRefineMatch | None:
    """V0.5.37 target-matched context evidence for one two-wheel label.

    Bicycle and motorcycle must be compared against the *same* local geometry.
    This prevents a weak bicycle score from being judged in isolation while a
    stronger motorcycle score on the exact same target is ignored.
    """
    wanted = str(label)
    filtered = [
        c for c in candidates
        if str(c.label) == wanted and float(c.confidence) >= float(min_confidence)
    ]
    if not filtered:
        return None
    if wanted == "bicycle":
        return select_contextual_bicycle_refinement(
            target, filtered, min_confidence=min_confidence,
            max_center_distance_ratio=max_center_distance_ratio,
        )

    strict = select_target_refinement(
        target, filtered, min_iou=0.02, min_target_coverage=0.06,
        min_evidence_coverage=0.12, max_center_distance_ratio=1.15,
        target_family="two-wheel",
    )
    if strict is not None and strict.center_distance_ratio <= float(max_center_distance_ratio):
        return strict

    tx1, ty1, tx2, ty2 = [float(v) for v in target]
    tw = max(1.0, tx2 - tx1)
    th = max(1.0, ty2 - ty1)
    tcx = (tx1 + tx2) / 2.0
    tcy = (ty1 + ty2) / 2.0
    tdiag = max(hypot(tw, th), 1.0)
    envelope = (tx1 - 0.80 * tw, ty1 - 0.60 * th, tx2 + 0.80 * tw, ty2 + 0.60 * th)
    best: TargetRefineMatch | None = None
    for candidate in filtered:
        rect = tuple(float(v) for v in candidate.rect)
        ex1, ey1, ex2, ey2 = rect
        ecx = (ex1 + ex2) / 2.0
        ecy = (ey1 + ey2) / 2.0
        center_ratio = hypot(ecx - tcx, ecy - tcy) / tdiag
        if center_ratio > float(max_center_distance_ratio):
            continue
        envelope_cov = _evidence_coverage(envelope, rect)
        target_cov = _coverage(target, rect)
        if envelope_cov < 0.34 and target_cov < 0.05:
            continue
        iou = _iou(target, rect)
        evidence_cov = _evidence_coverage(target, rect)
        geometry = max(
            envelope_cov, target_cov,
            max(0.0, 1.0 - center_ratio / max(1.0, float(max_center_distance_ratio))),
        )
        score = float(candidate.confidence) * (0.55 + 0.45 * min(1.0, geometry))
        match = TargetRefineMatch(
            label=wanted, confidence=float(candidate.confidence), target_iou=iou,
            target_coverage=target_cov, evidence_coverage=evidence_cov,
            center_distance_ratio=center_ratio, score=score,
        )
        if best is None or (match.score, match.confidence) > (best.score, best.confidence):
            best = match
    return best


def contextual_motorcycle_veto(
    observations: list[tuple[str, float, float]],
    *,
    motorcycle_veto: float = 0.10,
) -> bool:
    """Reject context rescue when any target-matched source favors motorcycle.

    A motor-only observation is evidence too. Filtering by bicycle confidence
    before this check, or choosing a source's most favorable bicycle frame,
    would discard the very contradiction that the veto is meant to protect.
    """
    margin = max(0.0, float(motorcycle_veto))
    for _source, bicycle_conf, motorcycle_conf in observations:
        bike = max(0.0, min(1.0, float(bicycle_conf)))
        moto = max(0.0, min(1.0, float(motorcycle_conf)))
        if moto - bike > margin:
            return True
    return False


def contextual_bicycle_competitive_decision(
    observations: list[tuple[str, float, float]],
    *,
    detector_confidence: float,
    max_motorcycle_confidence: float = 0.55,
    min_bicycle_confidence: float = 0.12,
    min_source_margin: float = 0.06,
    dual_fused_confidence: float = 0.34,
    fused_margin: float = 0.08,
    single_source_confidence: float = 0.55,
    temporal_hits: int = 0,
    temporal_fused: float = 0.0,
) -> tuple[str, float] | None:
    """Compare target-matched bicycle evidence against motorcycle evidence.

    V0.5.36 still required an absolute bicycle score. In the supplied 04:49
    frames the primary motorcycle itself is weak, so both context refiners can
    be weak in absolute terms while still preferring bicycle on the same box.
    Rescue is allowed only for a weak primary motorcycle and only when bicycle
    wins a target-matched competition; confident scooters remain untouched.
    """
    if float(detector_confidence) > float(max_motorcycle_confidence):
        return None
    best: dict[str, tuple[float, float]] = {}
    for source, bicycle_conf, motorcycle_conf in observations:
        bike = max(0.0, min(1.0, float(bicycle_conf)))
        moto = max(0.0, min(1.0, float(motorcycle_conf)))
        key = str(source)
        previous = best.get(key)
        if previous is None or bike > previous[0]:
            best[key] = (bike, moto)
    supportive = {
        source: values for source, values in best.items()
        if values[0] >= float(min_bicycle_confidence)
        and values[0] >= values[1] + float(min_source_margin)
    }
    if len(supportive) >= 2:
        bike_miss = 1.0
        moto_miss = 1.0
        for bike, moto in supportive.values():
            bike_miss *= max(0.0, 1.0 - bike)
            moto_miss *= max(0.0, 1.0 - moto)
        bike_fused = 1.0 - bike_miss
        moto_fused = 1.0 - moto_miss
        if bike_fused >= float(dual_fused_confidence) and bike_fused >= moto_fused + float(fused_margin):
            return "bicycle", bike_fused

    # Single-source rescue is deliberately much stricter and needs repeated
    # pre-crossing bicycle evidence from the ordinary target-aware refiner.
    if len(supportive) == 1 and int(temporal_hits) >= 2 and float(temporal_fused) >= 0.45:
        bike, moto = next(iter(supportive.values()))
        if bike >= float(single_source_confidence) and bike >= moto + max(0.12, float(min_source_margin)):
            return "bicycle", max(bike, float(temporal_fused))
    return None


def contextual_bicycle_near_margin_decision(
    observations: list[tuple[str, float, float]],
    *,
    detector_confidence: float,
    max_motorcycle_confidence: float = 0.50,
    min_bicycle_confidence: float = 0.10,
    min_source_win: float = 0.02,
    max_motorcycle_veto: float = 0.08,
    dual_fused_confidence: float = 0.28,
    fused_margin: float = 0.02,
) -> tuple[str, float] | None:
    """V0.5.38 precision-first fallback for a *near-margin* bicycle context.

    V0.5.37 required every supporting refiner to beat motorcycle by a fairly
    visible margin.  The supplied 04:49 frame still has a weak primary
    ``motorcycle`` (~0.49) while both wide-context refiners can see a bicycle,
    but one source may be almost tied with motorcycle.  This fallback only opens
    for an even weaker primary detector and still requires two independent
    target-matched bicycle observations.  A source with a material motorcycle
    lead vetoes the rescue, so an ordinary scooter cannot be flipped merely by
    lowering an absolute bicycle threshold.
    """
    if float(detector_confidence) > float(max_motorcycle_confidence):
        return None

    if contextual_motorcycle_veto(observations, motorcycle_veto=max_motorcycle_veto):
        return None

    best: dict[str, tuple[float, float]] = {}
    for source, bicycle_conf, motorcycle_conf in observations:
        bike = max(0.0, min(1.0, float(bicycle_conf)))
        moto = max(0.0, min(1.0, float(motorcycle_conf)))
        if bike < float(min_bicycle_confidence):
            continue
        key = str(source)
        previous = best.get(key)
        if previous is None or bike > previous[0]:
            best[key] = (bike, moto)

    if len(best) < 2:
        return None

    deltas = [bike - moto for bike, moto in best.values()]
    if max(deltas) < float(min_source_win):
        return None
    if any((-delta) > float(max_motorcycle_veto) for delta in deltas):
        return None

    bike_miss = 1.0
    moto_miss = 1.0
    for bike, moto in best.values():
        bike_miss *= max(0.0, 1.0 - bike)
        moto_miss *= max(0.0, 1.0 - moto)
    bike_fused = 1.0 - bike_miss
    moto_fused = 1.0 - moto_miss
    if bike_fused < float(dual_fused_confidence):
        return None
    if bike_fused < moto_fused + float(fused_margin):
        return None
    return "bicycle", bike_fused



def contextual_bicycle_cross_frame_decision(
    observations: list[tuple[int, str, float, float]],
    *,
    detector_confidence: float,
    max_motorcycle_confidence: float = 0.52,
    min_source_confidence: float = 0.08,
    min_frames: int = 2,
    min_sources: int = 2,
    min_source_win: float = 0.015,
    motorcycle_veto: float = 0.10,
    min_strongest: float = 0.14,
    dual_fused_confidence: float = 0.30,
    fused_margin: float = 0.015,
) -> tuple[tuple[str, float] | None, dict]:
    """V0.5.41 cross-frame bicycle decision with audit reason codes.

    Evidence may come from the two refiners on *different* pre-crossing frames.
    Both frame diversity and source diversity require bicycle-winning evidence;
    a losing extra frame cannot qualify otherwise same-frame evidence. Every
    target-matched motor lead remains eligible to veto before source selection.
    The function is deliberately pure so benchmark traces can explain why a
    decision was accepted/rejected without re-running either model.
    """
    audit = {
        "reason": "no_evidence", "accepted": False, "observations": len(observations),
        "frames": 0, "sources": 0, "bike_fused": 0.0, "moto_fused": 0.0,
    }
    if float(detector_confidence) > float(max_motorcycle_confidence):
        audit["reason"] = "primary_motorcycle_too_strong"
        return None, audit

    if contextual_motorcycle_veto(
        [(source, bike, moto) for _frame, source, bike, moto in observations],
        motorcycle_veto=motorcycle_veto,
    ):
        audit["reason"] = "motorcycle_source_veto"
        return None, audit

    usable = []
    for frame_index, source, bicycle_conf, motorcycle_conf in observations:
        bike = max(0.0, min(1.0, float(bicycle_conf)))
        moto = max(0.0, min(1.0, float(motorcycle_conf)))
        if bike >= float(min_source_confidence):
            usable.append((int(frame_index), str(source), bike, moto))
    frame_ids = {item[0] for item in usable}
    audit["frames"] = len(frame_ids)
    if len(frame_ids) < max(2, int(min_frames)):
        audit["reason"] = "insufficient_frames"
        return None, audit

    best: dict[str, tuple[int, float, float]] = {}
    for frame_index, source, bike, moto in usable:
        prior = best.get(source)
        # Prefer a larger bicycle-vs-motorcycle advantage, then stronger bike.
        if prior is None or (bike - moto, bike) > (prior[1] - prior[2], prior[1]):
            best[source] = (frame_index, bike, moto)
    audit["sources"] = len(best)
    audit["source_evidence"] = {
        source: {"frame": frame, "bicycle": round(bike, 4), "motorcycle": round(moto, 4)}
        for source, (frame, bike, moto) in sorted(best.items())
    }
    if len(best) < max(2, int(min_sources)):
        audit["reason"] = "insufficient_sources"
        return None, audit
    if any((moto - bike) > float(motorcycle_veto) for _frame, bike, moto in best.values()):
        audit["reason"] = "motorcycle_source_veto"
        return None, audit
    winners = [(frame, bike, moto) for frame, bike, moto in best.values() if bike >= moto + float(min_source_win)]
    if len(winners) < max(2, int(min_sources)):
        audit["reason"] = "source_win_missing"
        return None, audit
    winning_frames = {
        frame for frame, _source, bike, moto in usable
        if bike >= moto + float(min_source_win)
    }
    audit["usable_frames"] = audit["frames"]
    audit["frames"] = len(winning_frames)
    audit["winning_frames"] = sorted(winning_frames)
    if len(winning_frames) < max(2, int(min_frames)):
        audit["reason"] = "insufficient_frames"
        return None, audit
    strongest = max(bike for _frame, bike, _moto in winners)
    audit["strongest_bicycle"] = round(strongest, 4)
    if strongest < float(min_strongest):
        audit["reason"] = "bicycle_evidence_too_weak"
        return None, audit
    bike_miss = 1.0
    moto_miss = 1.0
    for _frame, bike, moto in winners:
        bike_miss *= max(0.0, 1.0 - bike)
        moto_miss *= max(0.0, 1.0 - moto)
    bike_fused = 1.0 - bike_miss
    moto_fused = 1.0 - moto_miss
    audit["bike_fused"] = round(bike_fused, 4)
    audit["moto_fused"] = round(moto_fused, 4)
    if bike_fused < float(dual_fused_confidence):
        audit["reason"] = "fused_bicycle_too_weak"
        return None, audit
    if bike_fused < moto_fused + float(fused_margin):
        audit["reason"] = "fused_margin_reject"
        return None, audit
    audit["reason"] = "accepted"
    audit["accepted"] = True
    return ("bicycle", bike_fused), audit

def contextual_bicycle_temporal_decision(
    observations: list[tuple[str, float]],
    *,
    temporal_hits: int,
    temporal_fused: float,
    temporal_strongest: float,
    temporal_sources: int,
    min_hits: int = 2,
    min_temporal_fused: float = 0.50,
    min_temporal_strongest: float = 0.26,
    min_combined: float = 0.72,
) -> tuple[str, float] | None:
    """Crossing-only fallback combining context and earlier target evidence.

    A single weak context guess is never enough. At least one context observation
    must agree with repeated pre-crossing bicycle evidence. Two refiner sources
    are preferred; one source is accepted only after three temporal hits with a
    materially strong observation.
    """
    context = [max(0.0, min(1.0, float(conf))) for _source, conf in observations if float(conf) >= 0.18]
    if not context:
        return None
    if int(temporal_hits) < max(2, int(min_hits)):
        return None
    if float(temporal_fused) < float(min_temporal_fused) or float(temporal_strongest) < float(min_temporal_strongest):
        return None
    if int(temporal_sources) < 2 and not (int(temporal_hits) >= 3 and float(temporal_strongest) >= 0.45):
        return None
    context_strongest = max(context)
    combined = 1.0 - (1.0 - context_strongest) * (1.0 - max(0.0, min(1.0, float(temporal_fused))))
    if combined < float(min_combined):
        return None
    return "bicycle", combined



def contextual_bicycle_weak_motor_decision(
    observations: list[tuple[str, float]],
    *,
    detector_confidence: float,
    max_motorcycle_confidence: float = 0.62,
    dual_source_confidence: float = 0.58,
    min_source_confidence: float = 0.18,
    min_strongest: float = 0.24,
) -> tuple[str, float] | None:
    """Precision-preserving rescue for a *weak* motorcycle crossing.

    V0.5.35 proved the context matcher is finding bicycle candidates (Bike ctx
    match > 0) but the generic context threshold can still be too strict for the
    partial front-wheel/basket box at 04:49.  This path only opens when the
    detector itself is weak and *both* independent context refiners support a
    bicycle.  A confident motorcycle or a single-source guess can never use this
    relaxed threshold.
    """
    if float(detector_confidence) > float(max_motorcycle_confidence):
        return None
    best_by_source: dict[str, float] = {}
    for source, confidence in observations:
        value = max(0.0, min(1.0, float(confidence)))
        if value < float(min_source_confidence):
            continue
        key = str(source)
        best_by_source[key] = max(best_by_source.get(key, 0.0), value)
    if len(best_by_source) < 2:
        return None
    strongest = max(best_by_source.values())
    if strongest < float(min_strongest):
        return None
    miss_probability = 1.0
    for confidence in best_by_source.values():
        miss_probability *= max(0.0, 1.0 - confidence)
    fused = 1.0 - miss_probability
    if fused < float(dual_source_confidence):
        return None
    return "bicycle", fused

def contextual_bicycle_decision(
    observations: list[tuple[str, float]],
    *,
    dual_source_confidence: float = 0.72,
    single_source_confidence: float = 0.90,
    min_source_confidence: float = 0.18,
    min_strongest: float = 0.34,
) -> tuple[str, float] | None:
    """Fuse one crossing-time *context* bicycle opinion per refiner source.

    V0.5.33 intentionally made normal bicycle promotion very strict to stop
    scooters flipping to bicycle.  The remaining GT-149 error is different: the
    recall tracker sometimes boxes only the bicycle front wheel/basket, so the
    normal target crop never shows enough of the rider + frame.  V0.5.34 uses a
    second, larger context crop only at an actual two-wheel crossing.

    To keep the V0.5.33 precision gains, context evidence cannot promote from one
    ordinary weak guess.  Two independent sources (domain best.pt + general
    verifier) must jointly exceed a fused threshold, or one source must be very
    strong on its own.
    """

    best_by_source: dict[str, float] = {}
    for source, confidence in observations:
        value = max(0.0, min(1.0, float(confidence)))
        if value < float(min_source_confidence):
            continue
        key = str(source)
        best_by_source[key] = max(best_by_source.get(key, 0.0), value)
    if not best_by_source:
        return None

    strongest = max(best_by_source.values())
    if strongest >= float(single_source_confidence):
        return "bicycle", strongest

    if len(best_by_source) < 2 or strongest < float(min_strongest):
        return None
    miss_probability = 1.0
    for confidence in best_by_source.values():
        miss_probability *= max(0.0, 1.0 - confidence)
    fused = 1.0 - miss_probability
    if fused >= float(dual_source_confidence):
        return "bicycle", fused
    return None


class RefineEvidenceAccumulator:
    """Fuse low-rate class-refiner observations across distinct source frames.

    V0.5.27 uses this as a *minority-class rescue* rather than a replacement
    tracker classifier. A single weak bicycle/truck guess is ignored, but
    repeated target-matched evidence from distinct frames can accumulate enough
    confidence to correct a stable motorcycle/car track. Multiple models on the
    same source frame never count as multiple hits.
    """

    def __init__(self, history_frames: int = 120, max_observations: int = 96) -> None:
        self.history_frames = max(8, int(history_frames))
        self.max_observations = max(16, int(max_observations))
        self._samples: dict[int, deque[tuple[int, str, float, str]]] = defaultdict(
            lambda: deque(maxlen=self.max_observations)
        )

    def update(self, track_id: int, frame_index: int, label: str, confidence: float, source: str = "refiner") -> None:
        if str(label) not in VEHICLE_CLASSES:
            return
        value = float(confidence)
        if not isfinite(value) or value <= 0.0:
            return
        tid = int(track_id)
        self._store_samples(tid, [
            *self._samples.get(tid, ()),
            (int(frame_index), str(label), min(1.0, value), str(source)),
        ])

    def _store_samples(self, track_id: int, samples: list[tuple[int, str, float, str]]) -> None:
        # A retry or track rebind must not fill the bounded history with copies
        # of one source-frame opinion and evict genuine temporal evidence.
        unique: dict[tuple[int, str, str], float] = {}
        for frame, label, confidence, source in samples:
            key = (int(frame), str(label), str(source))
            unique[key] = max(unique.get(key, 0.0), float(confidence))
        ordered = sorted(
            (frame, label, confidence, source)
            for (frame, label, source), confidence in unique.items()
        )
        self._samples[int(track_id)] = deque(ordered[-self.max_observations :], maxlen=self.max_observations)

    def support(self, track_id: int, frame_index: int, label: str) -> tuple[int, float, float]:
        """Return (distinct-frame hits, fused confidence, strongest single hit).

        Same-frame predictions from domain/general refiners are collapsed by
        taking the strongest confidence for the requested label. Confidence is
        then fused as ``1 - product(1 - p)`` with a mild recency decay.
        """

        current = int(frame_index)
        by_frame: dict[int, float] = {}
        for observed_frame, observed_label, confidence, _source in self._samples.get(int(track_id), ()):  # pragma: no branch
            age = current - int(observed_frame)
            if age < 0 or age > self.history_frames or observed_label != str(label):
                continue
            decayed = max(0.0, min(1.0, float(confidence))) * (0.992 ** age)
            by_frame[int(observed_frame)] = max(by_frame.get(int(observed_frame), 0.0), decayed)
        if not by_frame:
            return 0, 0.0, 0.0
        miss_probability = 1.0
        strongest = 0.0
        for confidence in by_frame.values():
            strongest = max(strongest, confidence)
            miss_probability *= max(0.0, 1.0 - confidence)
        return len(by_frame), 1.0 - miss_probability, strongest

    def source_count(self, track_id: int, frame_index: int, label: str) -> int:
        """Count independent refiner sources supporting ``label`` in history.

        Domain ``best.pt`` and the general YOLO verifier are intentionally
        treated as separate opinions. Repeated predictions from one model can
        still build temporal confidence, but V0.5.33 can require source
        diversity before promoting the rare ``bicycle`` class.
        """

        current = int(frame_index)
        sources: set[str] = set()
        for observed_frame, observed_label, _confidence, source in self._samples.get(int(track_id), ()):
            age = current - int(observed_frame)
            if age < 0 or age > self.history_frames or observed_label != str(label):
                continue
            sources.add(str(source))
        return len(sources)

    def competitive_support(
        self,
        track_id: int,
        frame_index: int,
        label: str,
        competing_label: str,
        *,
        min_source_win: float = 0.0,
        competing_veto: float | None = 0.10,
        include_current_frame: bool = True,
    ) -> tuple[int, float, float, int]:
        hits, fused, strongest, sources, _source_frame = self.competitive_support_snapshot(
            track_id, frame_index, label, competing_label,
            min_source_win=min_source_win, competing_veto=competing_veto,
            include_current_frame=include_current_frame,
        )
        return hits, fused, strongest, sources

    def competitive_support_snapshot(
        self,
        track_id: int,
        frame_index: int,
        label: str,
        competing_label: str,
        *,
        min_source_win: float = 0.0,
        competing_veto: float | None = 0.10,
        include_current_frame: bool = True,
    ) -> tuple[int, float, float, int, int | None]:
        """Return temporal support that wins its target's class competition.

        Ordinary refiner history can contain a bicycle from one model and a
        stronger motorcycle from another on the same source frame. Those
        frames cannot prove repeated bicycle agreement for context rescue.
        Apply the caller's motor veto before retaining winning frames, then
        fuse only one positive opinion per distinct frame with the same decay
        used by ``support``. Future and expired samples remain ineligible.
        Ordinary minority consensus passes no per-frame veto and keeps its
        existing aggregate motorcycle margin instead.
        """
        current = int(frame_index)
        by_frame: dict[int, dict[str, dict[str, float]]] = {}
        for observed_frame, observed_label, confidence, source in self._samples.get(int(track_id), ()):
            age = current - int(observed_frame)
            if age < 0 or age > self.history_frames or observed_label not in {str(label), str(competing_label)}:
                continue
            if age == 0 and not include_current_frame:
                continue
            frame = by_frame.setdefault(int(observed_frame), {})
            sources = frame.setdefault(str(observed_label), {})
            sources[str(source)] = max(sources.get(str(source), 0.0), float(confidence))

        margin = max(0.0, float(min_source_win))
        veto = None if competing_veto is None else max(0.0, float(competing_veto))
        winning: dict[int, float] = {}
        supporting_sources: set[str] = set()
        for observed_frame, frame in by_frame.items():
            sources = frame.get(str(label), {})
            confidence = max(sources.values(), default=0.0)
            competing_confidence = max(frame.get(str(competing_label), {}).values(), default=0.0)
            if veto is not None and competing_confidence - confidence > veto:
                return 0, 0.0, 0.0, 0, None
            if confidence <= 0.0 or confidence <= competing_confidence or confidence < competing_confidence + margin:
                continue
            winning[observed_frame] = confidence * (0.992 ** (current - observed_frame))
            supporting_sources.update(
                source for source, value in sources.items()
                if value > competing_confidence and value >= competing_confidence + margin
            )
        if not winning:
            return 0, 0.0, 0.0, 0, None
        miss_probability = 1.0
        for confidence in winning.values():
            miss_probability *= max(0.0, 1.0 - confidence)
        return len(winning), 1.0 - miss_probability, max(winning.values()), len(supporting_sources), max(winning)

    def minority_consensus_source_frame(
        self, track_id: int, frame_index: int, label: str,
    ) -> int | None:
        """Return the latest winning observation behind a minority decision."""
        if str(label) == "bicycle":
            return self.competitive_support_snapshot(
                track_id, frame_index, "bicycle", "motorcycle", competing_veto=None,
            )[4]
        if str(label) in HEAVY_CLASSES:
            return self.four_wheel_support_snapshot(track_id, frame_index, label)[3]
        return None

    def four_wheel_support(
        self, track_id: int, frame_index: int, label: str,
    ) -> tuple[int, float, float]:
        """Return repeated four-wheel evidence that beats its alternatives."""
        hits, fused, strongest, _source_frame = self.four_wheel_support_snapshot(
            track_id, frame_index, label,
        )
        return hits, fused, strongest

    def four_wheel_support_snapshot(
        self, track_id: int, frame_index: int, label: str,
    ) -> tuple[int, float, float, int | None]:
        """Return four-wheel support and its latest winning source frame.

        A target-matched truck opinion from one refiner can coexist with a
        stronger car or bus opinion from another. Count a source frame only
        when the requested label wins that frame, then require its fused
        support to beat each competing label's full eligible history. This
        keeps weak repeated winners useful without accumulating losing or
        tied opinions into a truck/bus correction or semantic lock.
        """
        selected_label = str(label)
        if selected_label not in HEAVY_CLASSES:
            return 0, 0.0, 0.0, None
        current = int(frame_index)
        by_frame: dict[int, dict[str, float]] = {}
        for observed_frame, observed_label, confidence, _source in self._samples.get(int(track_id), ()):
            age = current - int(observed_frame)
            if age < 0 or age > self.history_frames or observed_label not in HEAVY_CLASSES:
                continue
            frame = by_frame.setdefault(int(observed_frame), {})
            frame[observed_label] = max(frame.get(observed_label, 0.0), float(confidence))

        competing_labels = HEAVY_CLASSES - {selected_label}
        winning: dict[int, float] = {}
        for observed_frame, frame in by_frame.items():
            confidence = frame.get(selected_label, 0.0)
            competing_confidence = max((frame.get(other, 0.0) for other in competing_labels), default=0.0)
            if confidence > competing_confidence:
                winning[observed_frame] = confidence * (0.992 ** (current - observed_frame))
        if not winning:
            return 0, 0.0, 0.0, None
        miss_probability = 1.0
        for confidence in winning.values():
            miss_probability *= max(0.0, 1.0 - confidence)
        fused = 1.0 - miss_probability
        if any(fused <= self.support(track_id, current, other)[1] for other in competing_labels):
            return 0, 0.0, 0.0, None
        return len(winning), fused, max(winning.values()), max(winning)

    def consume_through(self, track_id: int, frame_index: int) -> None:
        """Consume completed-passage evidence while preserving newer samples."""
        tid = int(track_id)
        remaining = [sample for sample in self._samples.get(tid, ()) if sample[0] > int(frame_index)]
        if remaining:
            self._store_samples(tid, remaining)
        else:
            self._samples.pop(tid, None)

    def merge_track(self, source_track_id: int, target_track_id: int) -> None:
        source = int(source_track_id)
        target = int(target_track_id)
        if source == target:
            return
        source_samples = list(self._samples.pop(source, ()))
        if not source_samples:
            return
        self._store_samples(target, [*self._samples.get(target, ()), *source_samples])

    def minority_consensus(
        self,
        track_id: int,
        frame_index: int,
        base_label: str,
        *,
        min_hits: int = 2,
        bicycle_confidence: float = 0.60,
        truck_confidence: float = 0.52,
        bus_confidence: float = 0.62,
        bicycle_min_hits: int | None = None,
        bicycle_margin: float = 0.0,
        bicycle_min_strongest: float = 0.0,
        bicycle_min_sources: int = 1,
        bicycle_single_source_strong: float = 1.01,
    ) -> tuple[str, float] | None:
        """Return a conservative correction supported on distinct frames.

        The common class from the recall detector remains the default. Only
        minority classes that are important in this camera (bicycle/truck/bus)
        can be promoted by accumulated evidence.
        """

        base = str(base_label)
        hits_required = max(2, int(min_hits))
        if base in TWO_WHEEL_CLASSES:
            # Repeated bicycle agreement requires winning opinions. A tied or
            # losing frame cannot supply another hit, and a losing model cannot
            # borrow a stronger model's vote to qualify source diversity.
            hits, fused, strongest, source_count = self.competitive_support(
                track_id, frame_index, "bicycle", "motorcycle", competing_veto=None,
            )
            base_hits, base_fused, _ = self.support(track_id, frame_index, "motorcycle")
            bike_hits_required = max(hits_required, int(bicycle_min_hits) if bicycle_min_hits is not None else hits_required)
            contrast_ok = base_hits == 0 or fused >= base_fused + max(0.0, float(bicycle_margin))
            strongest_ok = strongest >= max(0.0, float(bicycle_min_strongest))
            source_ok = source_count >= max(1, int(bicycle_min_sources))
            # Escape hatch for a genuinely clear bicycle seen repeatedly by one
            # refiner: source diversity is preferred, not an absolute blocker.
            if not source_ok and hits >= bike_hits_required + 1:
                source_ok = strongest >= max(0.0, float(bicycle_single_source_strong))
            if (
                base != "bicycle"
                and hits >= bike_hits_required
                and fused >= float(bicycle_confidence)
                and contrast_ok
                and strongest_ok
                and source_ok
            ):
                return "bicycle", fused
            return None

        if base in HEAVY_CLASSES:
            truck_hits, truck_fused, _ = self.four_wheel_support(track_id, frame_index, "truck")
            if base != "truck" and truck_hits >= hits_required and truck_fused >= float(truck_confidence):
                return "truck", truck_fused
            bus_hits, bus_fused, _ = self.four_wheel_support(track_id, frame_index, "bus")
            if base != "bus" and bus_hits >= hits_required and bus_fused >= float(bus_confidence):
                return "bus", bus_fused
        return None


class TruckSemanticLock:
    """Sticky-but-bounded truck identity for one canonical four-wheel track.

    A delivery van can be confidently TRUCK while far from the gate, then flip
    back to COCO ``car`` as the box grows near the camera.  V0.5.30 keeps a
    truck decision only after repeated refiner evidence or strong temporal
    primary evidence, and holds that semantic identity long enough to survive
    the final approach to the counting line.  The lock is family-scoped and
    expires automatically, so it cannot convert two-wheel traffic or persist
    forever.
    """

    def __init__(
        self,
        *,
        ttl_frames: int = 450,
        min_refiner_hits: int = 2,
        min_refiner_confidence: float = 0.62,
        primary_hits: int = 3,
        primary_certainty: float = 0.80,
    ) -> None:
        self.ttl_frames = max(30, int(ttl_frames))
        self.min_refiner_hits = max(2, int(min_refiner_hits))
        self.min_refiner_confidence = max(0.0, min(1.0, float(min_refiner_confidence)))
        self.primary_hits = max(2, int(primary_hits))
        self.primary_certainty = max(0.0, min(1.0, float(primary_certainty)))
        self._locks: dict[int, tuple[float, int]] = {}

    def observe(
        self,
        track_id: int,
        frame_index: int,
        *,
        stable_label: str,
        certainty: float,
        hits: int,
        primary_frame_index: int | None = None,
        refiner_hits: int = 0,
        refiner_confidence: float = 0.0,
        refiner_frame_index: int | None = None,
    ) -> tuple[str, float] | None:
        # The caller can refresh all tracked classes. A cached truck identity
        # must never escape its four-wheel family merely because observe used
        # a literal "truck" label for the final resolution.
        if vehicle_family(stable_label) != "four-wheel":
            return None
        previous = self._locks.get(int(track_id))
        if previous is not None and int(frame_index) < previous[1]:
            return None
        primary_source_frame = int(frame_index) if primary_frame_index is None else int(primary_frame_index)
        strong_primary = (
            str(stable_label) == "truck"
            and int(hits) >= self.primary_hits
            and float(certainty) >= self.primary_certainty
            and 0 <= int(frame_index) - primary_source_frame <= self.ttl_frames
        )
        refiner_source_frame = int(frame_index) if refiner_frame_index is None else int(refiner_frame_index)
        strong_refiner = (
            int(refiner_hits) >= self.min_refiner_hits
            and float(refiner_confidence) >= self.min_refiner_confidence
            and 0 <= int(frame_index) - refiner_source_frame <= self.ttl_frames
        )
        if strong_primary or strong_refiner:
            # A stable primary label may still be supported by old truck pixels
            # while the current detector sees car. Both evidence paths retain
            # their actual source clocks; the newest qualified path owns TTL.
            qualified_clocks = []
            if strong_primary:
                qualified_clocks.append(primary_source_frame)
            if strong_refiner:
                qualified_clocks.append(refiner_source_frame)
            observed_frame = max(qualified_clocks)
            if previous is None or observed_frame >= previous[1]:
                confidence = max(
                    float(certainty) if strong_primary else 0.0,
                    float(refiner_confidence) if strong_refiner else 0.0,
                )
                if previous is not None and int(frame_index) - previous[1] <= self.ttl_frames:
                    confidence = max(confidence, previous[0])
                self._locks[int(track_id)] = (confidence, observed_frame)
        return self.resolve(track_id, frame_index, stable_label)

    def resolve(self, track_id: int, frame_index: int, primary_label: str) -> tuple[str, float] | None:
        if vehicle_family(primary_label) != "four-wheel":
            return None
        entry = self._locks.get(int(track_id))
        if entry is None:
            return None
        confidence, observed_frame = entry
        if int(frame_index) < int(observed_frame):
            return None
        if int(frame_index) - int(observed_frame) > self.ttl_frames:
            self._locks.pop(int(track_id), None)
            return None
        return "truck", float(confidence)

    def snapshot_for(self, track_id: int, frame_index: int, primary_label: str) -> dict | None:
        """Read an eligible lock and its source clock without changing state."""
        if vehicle_family(primary_label) != "four-wheel":
            return None
        entry = self._locks.get(int(track_id))
        if entry is None:
            return None
        confidence, observed_frame = entry
        if not isfinite(float(confidence)) or not 0 <= int(frame_index) - int(observed_frame) <= self.ttl_frames:
            return None
        return {
            "label": "truck", "confidence": float(confidence),
            "source_frame_index": int(observed_frame),
            "expires_after_frame_index": int(observed_frame) + self.ttl_frames,
        }

    def rebind(self, source_track_id: int, target_track_id: int) -> None:
        source = int(source_track_id)
        target = int(target_track_id)
        if source == target:
            return
        src = self._locks.pop(source, None)
        if src is None:
            return
        dst = self._locks.get(target)
        if dst is None or (src[1], src[0]) > (dst[1], dst[0]):
            self._locks[target] = src

    def active_count(self, frame_index: int) -> int:
        current = int(frame_index)
        stale = [tid for tid, (_conf, observed) in self._locks.items() if current - int(observed) > self.ttl_frames]
        for tid in stale:
            self._locks.pop(tid, None)
        return len(self._locks)


class TrackLabelSmoother:
    def __init__(self, history: int = 24) -> None:
        self.history = max(3, history)
        self._samples: dict[int, deque[tuple[str, float]]] = defaultdict(lambda: deque(maxlen=self.history))
        self._source_frames: dict[int, deque[int | None]] = defaultdict(lambda: deque(maxlen=self.history))

    def _store_timed_samples(
        self, track_id: int, samples: list[tuple[int | None, str, float]],
    ) -> None:
        if all(frame is not None for frame, _label, _confidence in samples):
            by_frame: dict[int, tuple[str, float]] = {}
            for frame, label, confidence in samples:
                previous = by_frame.get(int(frame))
                if previous is None or float(confidence) > previous[1]:
                    by_frame[int(frame)] = (str(label), float(confidence))
            samples = [(frame, *opinion) for frame, opinion in sorted(by_frame.items())]
        # Clockless callers retain the legacy append order and two-tuple ABI.
        retained = samples[-self.history :]
        self._samples[int(track_id)] = deque(
            ((label, confidence) for _frame, label, confidence in retained), maxlen=self.history,
        )
        self._source_frames[int(track_id)] = deque(
            (frame for frame, _label, _confidence in retained), maxlen=self.history,
        )

    def update(
        self, track_id: int, label: str, confidence: float, frame_index: int | None = None,
    ) -> None:
        tid = int(track_id)
        frames = list(self._source_frames.get(tid, ()))
        samples = list(self._samples.get(tid, ()))
        if len(frames) != len(samples):
            frames = [None] * len(samples)
        self._store_timed_samples(tid, [
            *((frame, *opinion) for frame, opinion in zip(frames, samples)),
            (None if frame_index is None else int(frame_index), str(label), float(confidence)),
        ])

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

    def source_frame_for(self, track_id: int, label: str) -> int | None:
        """Return the last retained detector observation of one actual label.

        Read-only lookup never turns smoothing into a new observation. Fully
        clocked production histories retain source order through canonical
        merges. Legacy or mixed clockless callers keep their existing ABI.
        """
        tid = int(track_id)
        samples = list(self._samples.get(tid, ()))
        frames = list(self._source_frames.get(tid, ()))
        if len(frames) != len(samples) or any(frame is None for frame in frames):
            return None
        return max(
            (int(frame) for frame, opinion in zip(frames, samples) if opinion[0] == str(label)),
            default=None,
        )

    def merge_track(self, source_track_id: int, target_track_id: int) -> None:
        source = int(source_track_id)
        target = int(target_track_id)
        if source == target:
            return
        source_samples = list(self._samples.pop(source, ()))
        source_frames = list(self._source_frames.pop(source, ()))
        if not source_samples:
            return
        target_samples = list(self._samples.get(target, ()))
        target_frames = list(self._source_frames.get(target, ()))
        if len(source_frames) != len(source_samples):
            source_frames = [None] * len(source_samples)
        if len(target_frames) != len(target_samples):
            target_frames = [None] * len(target_samples)
        self._store_timed_samples(target, [
            *((frame, *opinion) for frame, opinion in zip(target_frames, target_samples)),
            *((frame, *opinion) for frame, opinion in zip(source_frames, source_samples)),
        ])


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
