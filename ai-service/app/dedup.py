from __future__ import annotations

Rect = tuple[float, float, float, float]

FOUR_WHEEL_CONFLICTS = {"car", "bus", "truck"}
# Backward-compatible alias kept for the V0.5.17 semantic contract.
# V0.5.29 broadens the same guard from BUS/TRUCK to the whole four-wheel family.
HEAVY_CONFLICTS = FOUR_WHEEL_CONFLICTS


def box_iou(a: Rect, b: Rect) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0.0 else 0.0


def single_heavy_vehicle_plan(
    rects: list[Rect],
    labels: list[str],
    confidences: list[float],
    iou_threshold: float = 0.68,
) -> tuple[list[int], dict[int, list[int]], int]:
    """Plan a narrow cross-class four-wheel de-duplication pass.

    Frontal vans can oscillate between CAR/TRUCK/BUS in the same frame. Because
    normal NMS is class-aware, overlapping labels may reach ByteTrack as separate
    raw IDs and fragment one physical van into many canonical tracks. V0.5.29
    collapses only highly-overlapping *different* four-wheel labels and aliases
    the losing raw IDs to the strongest box. Same-class boxes and two-wheel
    traffic remain untouched.
    """
    count = min(len(rects), len(labels), len(confidences))
    if count <= 1:
        return list(range(count)), {}, 0

    threshold = max(0.1, min(0.99, float(iou_threshold)))
    ranked = sorted(range(count), key=lambda idx: float(confidences[idx]), reverse=True)
    suppressed: set[int] = set()
    aliases: dict[int, list[int]] = {}

    for pos, winner in enumerate(ranked):
        if winner in suppressed:
            continue
        winner_label = str(labels[winner])
        if winner_label not in FOUR_WHEEL_CONFLICTS:
            continue
        for candidate in ranked[pos + 1 :]:
            if candidate in suppressed:
                continue
            candidate_label = str(labels[candidate])
            if candidate_label not in FOUR_WHEEL_CONFLICTS or candidate_label == winner_label:
                continue
            if box_iou(rects[winner], rects[candidate]) >= threshold:
                suppressed.add(candidate)
                aliases.setdefault(winner, []).append(candidate)

    keep = [idx for idx in range(count) if idx not in suppressed]
    return keep, aliases, len(suppressed)


def keep_single_heavy_vehicle(
    rects: list[Rect],
    labels: list[str],
    confidences: list[float],
    iou_threshold: float = 0.68,
) -> tuple[list[int], int]:
    keep, _aliases, suppressed = single_heavy_vehicle_plan(rects, labels, confidences, iou_threshold)
    return keep, suppressed
