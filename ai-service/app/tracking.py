from __future__ import annotations

from dataclasses import dataclass
from math import hypot

Point = tuple[float, float]


def _vehicle_family(label: str) -> str:
    label = str(label)
    if label in {"bicycle", "motorcycle"}:
        return "two-wheel"
    if label in {"car", "bus", "truck"}:
        return "four-wheel"
    return label


@dataclass(slots=True)
class _IdentityState:
    point: Point
    frame_index: int
    label: str
    last_raw_id: int
    velocity: Point = (0.0, 0.0)


class TrackContinuityResolver:
    """Bridge short ByteTrack ID switches around the counting gate.

    The resolver predicts where a recently lost canonical track should be using
    its latest velocity, then lets a newly-created raw ByteTrack ID inherit that
    canonical identity only when the predicted position, time gap and vehicle
    family are compatible.  Two tracks visible in the same frame are never
    stitched to the same canonical ID.
    """

    def __init__(self, max_gap_frames: int = 18, max_distance_ratio: float = 0.085) -> None:
        self.max_gap_frames = max(2, int(max_gap_frames))
        self.max_distance_ratio = max(0.01, float(max_distance_ratio))
        self._raw_to_canonical: dict[int, int] = {}
        self._states: dict[int, _IdentityState] = {}
        self.stitch_count = 0

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
            if gap <= 0 or gap > self.max_gap_frames or candidate_id in claimed:
                continue
            if _vehicle_family(state.label) != family:
                continue

            predicted = (
                state.point[0] + state.velocity[0] * gap,
                state.point[1] + state.velocity[1] * gap,
            )
            predicted_distance = hypot(point[0] - predicted[0], point[1] - predicted[1]) / diagonal
            direct_distance = hypot(point[0] - state.point[0], point[1] - state.point[1]) / diagonal

            # With a good velocity estimate we compare to the predicted position.
            # If velocity is not known yet, permit a larger but still bounded
            # direct displacement for a short gap.
            has_motion = abs(state.velocity[0]) + abs(state.velocity[1]) > 0.5
            distance_ratio = predicted_distance if has_motion else direct_distance
            allowed = self.max_distance_ratio * (1.20 if has_motion else min(2.0, 1.0 + 0.12 * gap))
            if distance_ratio > allowed:
                continue
            score = distance_ratio + gap * 0.0015
            if best is None or score < best[0]:
                best = (score, candidate_id)

        stitched = best is not None
        canonical = best[1] if best is not None else raw_id
        self._raw_to_canonical[raw_id] = canonical
        self._update_state(canonical, raw_id, point, label, frame_index)
        if stitched:
            self.stitch_count += 1
        self._cleanup(frame_index)
        return canonical, stitched

    def _update_state(self, canonical: int, raw_id: int, point: Point, label: str, frame_index: int) -> None:
        previous = self._states.get(canonical)
        velocity = (0.0, 0.0)
        if previous is not None:
            gap = max(1, frame_index - previous.frame_index)
            observed = ((point[0] - previous.point[0]) / gap, (point[1] - previous.point[1]) / gap)
            # Smooth velocity so one noisy box does not produce a wild prediction.
            velocity = (
                previous.velocity[0] * 0.55 + observed[0] * 0.45,
                previous.velocity[1] * 0.55 + observed[1] * 0.45,
            )
        self._states[canonical] = _IdentityState(point, frame_index, str(label), raw_id, velocity)

    def _cleanup(self, frame_index: int) -> None:
        expiry = self.max_gap_frames * 8
        stale = {cid for cid, state in self._states.items() if frame_index - state.frame_index > expiry}
        if not stale:
            return
        for cid in stale:
            self._states.pop(cid, None)
        for raw_id, cid in list(self._raw_to_canonical.items()):
            if cid in stale:
                self._raw_to_canonical.pop(raw_id, None)
