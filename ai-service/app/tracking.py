from __future__ import annotations

from dataclasses import dataclass
from math import hypot

Point = tuple[float, float]
Rect = tuple[float, float, float, float]


def _vehicle_family(label: str) -> str:
    label = str(label)
    if label in {"bicycle", "motorcycle"}:
        return "two-wheel"
    if label in {"car", "bus", "truck"}:
        return "four-wheel"
    return label


def motion_leading_anchor(rect: Rect, velocity: Point, inset_ratio: float = 0.0) -> Point:
    """Pick a motion-leading road-contact proxy inside the detection box.

    Two-wheel traffic still uses the true leading edge by default. Large cars,
    vans, buses and trucks can pass a non-zero ``inset_ratio`` so a clipped or
    oversized detector box does not push the anchor outside the editable Road
    Zone exactly while the vehicle crosses the gate. The inset is directional:
    it moves the leading point toward the box interior without changing the
    travel axis or the IN/OUT semantics.
    """
    x1, y1, x2, y2 = rect
    vx, vy = velocity
    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)
    inset = max(0.0, min(0.45, float(inset_ratio)))
    ix = width * inset
    iy = height * inset
    if abs(vx) + abs(vy) < 0.75:
        return ((x1 + x2) / 2.0, y2 - iy)
    if abs(vx) > abs(vy):
        return ((x2 - ix) if vx > 0 else (x1 + ix), (y1 + y2) / 2.0)
    return ((x1 + x2) / 2.0, (y2 - iy) if vy > 0 else (y1 + iy))


@dataclass(slots=True)
class _IdentityState:
    point: Point
    frame_index: int
    label: str
    last_raw_id: int
    velocity: Point = (0.0, 0.0)


class TrackContinuityResolver:
    """Bridge short ByteTrack ID switches using motion prediction."""

    def __init__(
        self,
        max_gap_frames: int = 30,
        max_distance_ratio: float = 0.14,
        heavy_max_gap_frames: int | None = None,
        heavy_max_distance_ratio: float | None = None,
    ) -> None:
        self.max_gap_frames = max(2, int(max_gap_frames))
        self.max_distance_ratio = max(0.01, float(max_distance_ratio))
        self.heavy_max_gap_frames = max(
            self.max_gap_frames,
            int(heavy_max_gap_frames) if heavy_max_gap_frames is not None else self.max_gap_frames,
        )
        self.heavy_max_distance_ratio = max(
            self.max_distance_ratio,
            float(heavy_max_distance_ratio) if heavy_max_distance_ratio is not None else self.max_distance_ratio,
        )
        self._raw_to_canonical: dict[int, int] = {}
        self._states: dict[int, _IdentityState] = {}
        self.stitch_count = 0
        self.heavy_stitch_count = 0

    def resolve(
        self,
        raw_id: int,
        point: Point,
        label: str,
        frame_index: int,
        frame_width: int,
        frame_height: int,
        claimed_canonical_ids: set[int] | None = None,
    ) -> tuple[int, bool]:
        raw_id = int(raw_id)
        claimed = claimed_canonical_ids or set()
        canonical = self._raw_to_canonical.get(raw_id)
        if canonical is not None and canonical not in claimed:
            self._update_state(canonical, raw_id, point, label, frame_index)
            self._cleanup(frame_index)
            return canonical, False

        diagonal = max(hypot(frame_width, frame_height), 1.0)
        family = _vehicle_family(label)
        best: tuple[float, int] | None = None
        for candidate_id, state in self._states.items():
            gap = frame_index - state.frame_index
            state_family = _vehicle_family(state.label)
            gap_limit = self.heavy_max_gap_frames if family == "four-wheel" and state_family == "four-wheel" else self.max_gap_frames
            if gap <= 0 or gap > gap_limit or candidate_id in claimed:
                continue
            if state_family != family:
                continue

            predicted = (
                state.point[0] + state.velocity[0] * gap,
                state.point[1] + state.velocity[1] * gap,
            )
            predicted_distance = hypot(point[0] - predicted[0], point[1] - predicted[1]) / diagonal
            direct_distance = hypot(point[0] - state.point[0], point[1] - state.point[1]) / diagonal
            has_motion = abs(state.velocity[0]) + abs(state.velocity[1]) > 0.5
            distance_ratio = predicted_distance if has_motion else direct_distance
            if family == "four-wheel" and gap > self.max_gap_frames:
                # A close van grows rapidly in perspective, so velocity measured
                # while it is far away can wildly over-predict a long occlusion.
                # For the extended heavy-only stitch window, accept the safer of
                # direct and velocity-predicted distance instead of trusting a
                # stale velocity vector unconditionally.
                distance_ratio = min(predicted_distance, direct_distance)

            # Allow a little more uncertainty over longer gaps while staying
            # bounded; this is especially important for fast motorcycles.
            gap_factor = min(2.2, 1.0 + 0.055 * gap)
            base_distance = self.heavy_max_distance_ratio if family == "four-wheel" else self.max_distance_ratio
            allowed = base_distance * (1.25 if has_motion else gap_factor)
            if distance_ratio > allowed:
                continue
            score = distance_ratio + gap * 0.0012
            if best is None or score < best[0]:
                best = (score, candidate_id)

        stitched = best is not None
        canonical = best[1] if best is not None else raw_id
        self._raw_to_canonical[raw_id] = canonical
        self._update_state(canonical, raw_id, point, label, frame_index)
        if stitched:
            self.stitch_count += 1
            if family == "four-wheel":
                self.heavy_stitch_count += 1
        self._cleanup(frame_index)
        return canonical, stitched

    def alias_raw_id(self, raw_id: int, canonical_id: int) -> int | None:
        """Bind a duplicate raw ID and report any displaced canonical ID.

        V0.5.30 lets the worker coalesce gate/classification state when a
        CAR/TRUCK/BUS duplicate was already alive under another canonical ID.
        """
        raw_id = int(raw_id)
        canonical_id = int(canonical_id)
        previous = self._raw_to_canonical.get(raw_id)
        self._raw_to_canonical[raw_id] = canonical_id
        displaced = previous if previous is not None and previous != canonical_id else None
        if displaced is not None:
            for candidate_raw, mapped in list(self._raw_to_canonical.items()):
                if mapped == displaced:
                    self._raw_to_canonical[candidate_raw] = canonical_id
            self._states.pop(displaced, None)
        return displaced

    def velocity_for(self, canonical_id: int) -> Point:
        state = self._states.get(int(canonical_id))
        return state.velocity if state is not None else (0.0, 0.0)

    def _update_state(self, canonical: int, raw_id: int, point: Point, label: str, frame_index: int) -> None:
        previous = self._states.get(canonical)
        velocity = (0.0, 0.0)
        if previous is not None:
            gap = max(1, frame_index - previous.frame_index)
            observed = ((point[0] - previous.point[0]) / gap, (point[1] - previous.point[1]) / gap)
            velocity = (
                previous.velocity[0] * 0.45 + observed[0] * 0.55,
                previous.velocity[1] * 0.45 + observed[1] * 0.55,
            )
        self._states[canonical] = _IdentityState(point, frame_index, str(label), raw_id, velocity)

    def _cleanup(self, frame_index: int) -> None:
        expiry = max(self.max_gap_frames, self.heavy_max_gap_frames) * 8
        stale = {cid for cid, state in self._states.items() if frame_index - state.frame_index > expiry}
        if not stale:
            return
        for cid in stale:
            self._states.pop(cid, None)
        for raw_id, cid in list(self._raw_to_canonical.items()):
            if cid in stale:
                self._raw_to_canonical.pop(raw_id, None)
