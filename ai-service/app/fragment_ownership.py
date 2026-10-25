"""Causal, bounded evidence for an uncommitted newborn two-wheel fragment.

Geometry can corroborate a detector fragment; it is not appearance identity.
No GT, event matching or proximity in time alone participates in this policy.
The worker must validate and discard *all* uncommitted counting state before
activating a certificate. The original owner's state is never merged.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import hypot, isfinite

Rect = tuple[float, float, float, float]
Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class FragmentObservation:
    raw_id: int
    canonical_id: int | None
    rect: Rect
    label: str
    class_hits: int
    last_count_frame: int | None = None
    guard_pending: bool = False


def _center(rect: Rect) -> Point:
    return ((rect[0] + rect[2]) * .5, (rect[1] + rect[3]) * .5)


def _valid_geometry(item: FragmentObservation) -> bool:
    return (
        isinstance(item, FragmentObservation)
        and isinstance(item.raw_id, int) and not isinstance(item.raw_id, bool)
        and isinstance(item.rect, (tuple, list)) and len(item.rect) == 4
        and all(isinstance(v, (int, float)) and not isinstance(v, bool) and isfinite(v) for v in item.rect)
        and item.rect[2] > item.rect[0] and item.rect[3] > item.rect[1]
    )


def _valid(item: FragmentObservation) -> bool:
    return (
        _valid_geometry(item)
        and (item.canonical_id is None or (isinstance(item.canonical_id, int) and not isinstance(item.canonical_id, bool)))
        and isinstance(item.label, str) and item.label in {"bicycle", "motorcycle"}
        and isinstance(item.class_hits, int) and not isinstance(item.class_hits, bool) and item.class_hits >= 0
        and (item.last_count_frame is None or (isinstance(item.last_count_frame, int) and not isinstance(item.last_count_frame, bool)))
    )


def _nested(child: Rect, owner: Rect) -> bool:
    cw, ch = child[2] - child[0], child[3] - child[1]
    ow, oh = owner[2] - owner[0], owner[3] - owner[1]
    overlap = max(0., min(child[2], owner[2]) - max(child[0], owner[0])) * max(
        0., min(child[3], owner[3]) - max(child[1], owner[1]))
    return overlap >= .90 * cw * ch and cw * ch <= .60 * ow * oh and cw <= .80 * ow and ch <= .80 * oh


def _point_segment_distance(point: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    t = max(0., min(1., ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length2))
    return hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy)


def _point_rect_distance(point: Point, rect: Rect) -> float:
    return hypot(max(rect[0] - point[0], 0., point[0] - rect[2]),
                 max(rect[1] - point[1], 0., point[1] - rect[3]))


@dataclass(slots=True)
class _Quarantine:
    owner_raw_id: int
    last_seen: int
    clear_frames: int = 0
    last_clear_frame: int = -1


class TwoWheelFragmentOwnership:
    """Three distinct near-consecutive nested views, followed by safe rearm.

    Quarantine ends after an absence longer than 30 source frames, or three
    non-overlapping observations whose entire box is well away from the finite
    gate. Release never restores the retired canonical or its passage history.
    """

    def __init__(self) -> None:
        self._clock = -1
        self._first: dict[int, int] = {}
        self._history: dict[int, deque[tuple[int, Rect]]] = {}
        self._pairs: dict[tuple[int, int], deque[tuple[int, Point]]] = {}
        self._quarantine: dict[int, _Quarantine] = {}
        self.retirements = 0
        self.releases = 0

    def activate(self, raw_id: int, owner_raw_id: int, frame_index: int) -> None:
        """Called only after the worker's all-or-nothing uncommitted discard."""
        if raw_id not in self._quarantine:
            self._quarantine[raw_id] = _Quarantine(int(owner_raw_id), int(frame_index))
            self.retirements += 1

    def observe(
        self, frame_index: int, observations: list[FragmentObservation],
        line: tuple[Point, Point], frame_width: int, frame_height: int,
    ) -> tuple[set[int], list[dict], list[dict]]:
        """Return current filtered raws, proposed certificates and release audit."""
        if (not isinstance(frame_index, int) or isinstance(frame_index, bool) or frame_index < 0
                or frame_width <= 0 or frame_height <= 0):
            return set(), [], []
        if frame_index <= self._clock:
            return set(self._quarantine).intersection(item.raw_id for item in observations if isinstance(item, FragmentObservation)), [], []
        self._clock = frame_index
        items = [item for item in observations if _valid(item)]
        observed_raws = {item.raw_id for item in observations if isinstance(item, FragmentObservation)
                         and isinstance(item.raw_id, int) and not isinstance(item.raw_id, bool)}
        # Ambiguous duplicate raw rows cannot manufacture correspondence.
        raw_counts: dict[int, int] = {}
        for item in observations:
            if isinstance(item, FragmentObservation) and isinstance(item.raw_id, int) and not isinstance(item.raw_id, bool):
                raw_counts[item.raw_id] = raw_counts.get(item.raw_id, 0) + 1
        visible = {item.raw_id: item for item in items if raw_counts[item.raw_id] == 1}
        visible_geometry = {item.raw_id: item for item in observations
                            if _valid_geometry(item) and raw_counts[item.raw_id] == 1}
        releases = []
        for raw, quarantine in list(self._quarantine.items()):
            item = visible_geometry.get(raw)
            absent = frame_index - quarantine.last_seen > 30
            clear = False
            if item is not None and not absent:
                owner = visible_geometry.get(quarantine.owner_raw_id)
                separated = owner is None or not _rects_overlap(item.rect, owner.rect)
                a, b = line
                valid_line = all(isfinite(v) for p in line for v in p) and hypot(b[0] - a[0], b[1] - a[1]) > 0
                corners = ((item.rect[0], item.rect[1]), (item.rect[2], item.rect[1]),
                           (item.rect[0], item.rect[3]), (item.rect[2], item.rect[3]))
                # Same-side corners rule out a segment crossing the box even
                # when every corner individually lies far from the segment.
                sides = [(b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) for p in corners]
                clear = (valid_line and separated and (all(s > 0 for s in sides) or all(s < 0 for s in sides))
                         and min(*(_point_segment_distance(p, a, b) for p in corners),
                                 _point_rect_distance(a, item.rect), _point_rect_distance(b, item.rect))
                         >= .08 * min(frame_width, frame_height))
                if clear:
                    quarantine.clear_frames = quarantine.clear_frames + 1 if 0 < frame_index - quarantine.last_clear_frame <= 2 else 1
                    quarantine.last_clear_frame = frame_index
                else:
                    quarantine.clear_frames = 0
                quarantine.last_seen = frame_index
            elif raw in observed_raws and not absent:
                # Ambiguous/malformed rows still demonstrate presence. They
                # cannot earn clear-space evidence or masquerade as absence.
                quarantine.last_seen = frame_index
                quarantine.clear_frames = 0
            if absent or (clear and quarantine.clear_frames >= 3):
                self._quarantine.pop(raw)
                self._first.pop(raw, None)
                self._history.pop(raw, None)
                self.releases += 1
                releases.append({"raw_track_id": raw, "frame_index": frame_index,
                                 "reason": "absence_rearm" if absent else "independent_box_rearm"})
        for raw, history in list(self._history.items()):
            if frame_index - history[-1][0] > 90:
                self._history.pop(raw)
                self._first.pop(raw, None)
        for raw, item in visible.items():
            history = self._history.setdefault(raw, deque(maxlen=20))
            if history and frame_index - history[-1][0] > 30:
                history.clear()
                self._first.pop(raw, None)
            self._first.setdefault(raw, frame_index)
            history.append((frame_index, item.rect))
        proposed = []
        qualifying = set()
        for raw, child in visible.items():
            if (raw in self._quarantine or frame_index - self._first[raw] > 5
                    or child.class_hits > 6 or child.guard_pending or child.last_count_frame is not None):
                continue
            owners = []
            for owner_raw, owner in visible.items():
                if (owner_raw == raw or owner_raw in self._quarantine or owner.canonical_id is None
                        or owner.canonical_id == child.canonical_id or owner.class_hits < 8
                        or owner.guard_pending or owner.last_count_frame is None
                        or not 0 <= frame_index - owner.last_count_frame <= 75 or not _nested(child.rect, owner.rect)):
                    continue
                history = self._history[owner_raw]
                old = next((rect for clock, rect in reversed(history) if frame_index - clock >= 8), None)
                if len(history) < 3 or old is None:
                    continue
                oc, cc, before = _center(owner.rect), _center(child.rect), _center(old)
                motion = (oc[0] - before[0], oc[1] - before[1])
                ow, oh = owner.rect[2] - owner.rect[0], owner.rect[3] - owner.rect[1]
                if hypot(*motion) < .10 * hypot(ow, oh) or (cc[0] - oc[0]) * motion[0] + (cc[1] - oc[1]) * motion[1] >= 0:
                    continue
                owners.append((owner, ((cc[0] - oc[0]) / ow, (cc[1] - oc[1]) / oh)))
            if len(owners) != 1:
                continue
            owner, offset = owners[0]
            key = (raw, owner.raw_id)
            qualifying.add(key)
            trail = self._pairs.setdefault(key, deque(maxlen=3))
            if trail and frame_index - trail[-1][0] > 2:
                trail.clear()
            trail.append((frame_index, offset))
            drift = max((hypot(p[0] - q[0], p[1] - q[1]) for _c, p in trail for _d, q in trail), default=0.)
            if len(trail) >= 3 and drift <= .06:
                proposed.append({"raw_track_id": raw, "track_id": child.canonical_id,
                    "owner_raw_track_id": owner.raw_id, "owner_track_id": owner.canonical_id,
                    "frame_index": frame_index, "sample_frames": [clock for clock, _point in trail],
                    "normalized_offset_drift": drift, "reason": "nested_newborn_correspondence"})
        for key, trail in list(self._pairs.items()):
            if key not in qualifying or frame_index - trail[-1][0] > 2:
                self._pairs.pop(key)
        return set(self._quarantine).intersection(observed_raws), proposed, releases


def _rects_overlap(a: Rect, b: Rect) -> bool:
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])
