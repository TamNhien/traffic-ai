from __future__ import annotations

Rect = tuple[float, float, float, float]

HEAVY_CONFLICTS = {"bus", "truck"}


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
    """Plan a narrow BUS/TRUCK de-duplication pass.

    COCO-style detectors can emit highly-overlapping BUS and TRUCK boxes for the
    same physical heavy vehicle because normal NMS is class-aware. If both boxes
    reach ByteTrack they can become two raw IDs and independently cross the gate.

    The stronger box is kept. The weaker raw-track index is returned as an alias
    of the winner so the continuity resolver can bind both ByteTrack IDs to one
    canonical vehicle identity. The guard intentionally targets only the
    BUS/TRUCK conflict and leaves dense mixed traffic untouched.
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
        if winner_label not in HEAVY_CONFLICTS:
            continue
        for candidate in ranked[pos + 1 :]:
            if candidate in suppressed:
                continue
            candidate_label = str(labels[candidate])
            if candidate_label not in HEAVY_CONFLICTS or candidate_label == winner_label:
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
