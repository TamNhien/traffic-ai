from __future__ import annotations

from dataclasses import dataclass
from math import hypot, nextafter

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

    V0.5.56 follows the heading continuously around an inset ellipse. A tiny
    change between horizontal and vertical dominance must not move the anchor
    from the top to the side of the box and invent a crossing. Cardinal motion
    keeps the existing leading-edge points. Near the stationary cutoff, blend
    from the bottom-center fallback to avoid a second discontinuity.
    """
    x1, y1, x2, y2 = rect
    vx, vy = velocity
    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)
    inset = max(0.0, min(0.45, float(inset_ratio)))
    iy = height * inset
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    fallback = (cx, y2 - iy)
    speed = abs(vx) + abs(vy)
    if speed <= 0.75:
        return fallback
    heading_length = hypot(vx, vy)
    lead = (
        cx + width * (0.5 - inset) * vx / heading_length,
        cy + height * (0.5 - inset) * vy / heading_length,
    )
    heading_weight = min(1.0, (speed - 0.75) / 0.75)
    return (
        fallback[0] + heading_weight * (lead[0] - fallback[0]),
        fallback[1] + heading_weight * (lead[1] - fallback[1]),
    )


@dataclass(slots=True)
class _IdentityState:
    point: Point
    frame_index: int
    label: str
    last_raw_id: int
    velocity: Point = (0.0, 0.0)
    rect: Rect | None = None


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
        # A reliable heading belongs to the canonical identity, separately from
        # its measured velocity. Deceleration must not move a previously leading
        # contact point back through the box to the stationary bottom fallback.
        self._anchor_velocities: dict[int, tuple[int, Point]] = {}
        # A slow reversal needs two distinct, locally consecutive observations
        # beyond the existing .75 moving boundary. Keep the first center so a
        # velocity filter's residual cannot substitute for actual reverse travel.
        self._anchor_reversals: dict[int, tuple[int, int, Point]] = {}
        # V0.5.49 Precision Recovery Closure 9.5: remember every raw ByteTrack
        # ID that has contributed to one canonical identity.  The crossing gate
        # uses only the *size* of this lineage as a risk signal for long-gap
        # secondary rescues; direct crossings are unchanged.
        self._canonical_raw_ids: dict[int, set[int]] = {}
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
        *,
        rect: Rect | None = None,
    ) -> tuple[int, bool]:
        # Expire the previous identity before an arriving raw ID can refresh it.
        # Otherwise a reused ID after a long silence revives stale motion state.
        self._cleanup(frame_index)
        raw_id = int(raw_id)
        claimed = claimed_canonical_ids or set()
        canonical = self._raw_to_canonical.get(raw_id)
        if canonical is not None and canonical not in claimed:
            self._canonical_raw_ids.setdefault(canonical, set()).add(raw_id)
            self._update_state(canonical, raw_id, point, label, frame_index, rect)
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

            if self._opposite_two_wheel_stitch(state, point, rect, family, gap):
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
        self._canonical_raw_ids.setdefault(canonical, set()).add(raw_id)
        self._update_state(canonical, raw_id, point, label, frame_index, rect)
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
        self._canonical_raw_ids.setdefault(canonical_id, set()).add(raw_id)
        displaced = previous if previous is not None and previous != canonical_id else None
        if displaced is not None:
            displaced_raws = self._canonical_raw_ids.pop(displaced, set())
            self._canonical_raw_ids.setdefault(canonical_id, set()).update(displaced_raws)
            for candidate_raw, mapped in list(self._raw_to_canonical.items()):
                if mapped == displaced:
                    self._raw_to_canonical[candidate_raw] = canonical_id
                    self._canonical_raw_ids[canonical_id].add(candidate_raw)
            displaced_heading = self._anchor_velocities.pop(displaced, None)
            target_heading = self._anchor_velocities.get(canonical_id)
            if (
                canonical_id in self._states and displaced_heading is not None
                and (target_heading is None or displaced_heading[0] > target_heading[0])
            ):
                self._anchor_velocities[canonical_id] = displaced_heading
            self._states.pop(displaced, None)
            self._anchor_reversals.pop(displaced, None)
            # Unconfirmed direction evidence belongs to its observed trajectory;
            # alias fusion cannot combine two single-frame hints into a turn.
            self._anchor_reversals.pop(canonical_id, None)
        return displaced

    def lineage_size(self, canonical_id: int) -> int:
        """Return how many raw tracker IDs feed one canonical identity."""
        return max(1, len(self._canonical_raw_ids.get(int(canonical_id), set())))

    def has_lineage_switch(self, canonical_id: int) -> bool:
        return self.lineage_size(canonical_id) > 1

    def velocity_for(self, canonical_id: int) -> Point:
        state = self._states.get(int(canonical_id))
        return state.velocity if state is not None else (0.0, 0.0)

    def anchor_velocity_for(self, canonical_id: int) -> Point:
        """Keep an established leading heading when measured motion slows.

        The existing full-heading boundary is L1 speed 1.5. Motion below that
        boundary retains the latest reliable heading; an identity without one
        keeps the original stationary/startup blend. Stitch prediction and the
        Human Guard continue to use ``velocity_for`` and its actual velocity.
        A slow reversal can establish a new heading through two distinct local
        observations above .75, with at least 1.5 pixels of actual reverse travel.
        Its retained vector is normalized to the existing full-heading boundary,
        so stopping after that turn does not restart the stationary blend.
        """
        heading = self._anchor_velocities.get(int(canonical_id))
        return heading[1] if heading is not None else self.velocity_for(canonical_id)

    @staticmethod
    def _opposite_two_wheel_stitch(
        state: _IdentityState, point: Point, rect: Rect | None, family: str, gap: int,
    ) -> bool:
        """Reject a new rider identity that teleports behind a moving rider.

        V0.5.59 uses the established 1.5 full-heading boundary, rather than a
        looser global stitch radius. Detector boxes may expand or shrink between
        raw IDs, so allow backward center motion within either box's half
        diagonal and the expected travel over the gap. Only a larger opposing
        displacement contradicts that candidate. Existing raw-ID reversals and
        four-wheel perspective recovery keep their previous behavior. Callers
        without both rectangles keep the original center-only stitch contract.
        """
        velocity = state.velocity
        if (
            family != "two-wheel" or state.rect is None or rect is None
            or abs(velocity[0]) + abs(velocity[1]) < 1.5
        ):
            return False
        speed = hypot(*velocity)
        reverse_travel = -(
            (point[0] - state.point[0]) * velocity[0]
            + (point[1] - state.point[1]) * velocity[1]
        ) / speed
        box_radius = max(
            hypot(max(0.0, box[2] - box[0]), max(0.0, box[3] - box[1])) * .5
            for box in (state.rect, rect)
        )
        return reverse_travel > max(speed * gap, box_radius, 1.5 * gap)

    def _update_state(
        self, canonical: int, raw_id: int, point: Point, label: str,
        frame_index: int, rect: Rect | None = None,
    ) -> None:
        previous = self._states.get(canonical)
        if previous is not None and frame_index <= previous.frame_index:
            # A duplicated or stale source clock supplies no new motion evidence
            # and must not rewrite the center used by the next real observation.
            return
        velocity = (0.0, 0.0)
        if previous is not None:
            gap = max(1, frame_index - previous.frame_index)
            observed = ((point[0] - previous.point[0]) / gap, (point[1] - previous.point[1]) / gap)
            velocity = (
                previous.velocity[0] * 0.45 + observed[0] * 0.55,
                previous.velocity[1] * 0.45 + observed[1] * 0.55,
            )
        self._states[canonical] = _IdentityState(point, frame_index, str(label), raw_id, velocity, rect)
        speed = abs(velocity[0]) + abs(velocity[1])
        if speed >= 1.5:
            self._anchor_velocities[canonical] = (int(frame_index), velocity)
            self._anchor_reversals.pop(canonical, None)
            return

        heading = self._anchor_velocities.get(canonical)
        gap_limit = self.heavy_max_gap_frames if _vehicle_family(label) == "four-wheel" else self.max_gap_frames
        if (
            previous is None or heading is None or speed <= .75
            or frame_index - previous.frame_index > gap_limit
            or velocity[0] * heading[1][0] + velocity[1] * heading[1][1] >= 0.0
            or (point[0] - previous.point[0]) * heading[1][0]
               + (point[1] - previous.point[1]) * heading[1][1] >= 0.0
        ):
            self._anchor_reversals.pop(canonical, None)
            return
        pending = self._anchor_reversals.get(canonical)
        if pending is not None and 0 < frame_index - pending[0] <= gap_limit:
            observations, start = pending[1] + 1, pending[2]
        else:
            observations, start = 1, previous.point
        self._anchor_reversals[canonical] = (int(frame_index), observations, start)
        heading_length = hypot(*heading[1])
        reverse_travel = -(
            (point[0] - start[0]) * heading[1][0]
            + (point[1] - start[1]) * heading[1][1]
        ) / heading_length
        if observations >= 2 and reverse_travel >= 1.5:
            # Round upward by one float step so normalization cannot fall just
            # below 1.5 and leave a microscopic stationary-blend remainder.
            full_speed = nextafter(1.5, float("inf"))
            self._anchor_velocities[canonical] = (
                int(frame_index), (velocity[0] * full_speed / speed, velocity[1] * full_speed / speed),
            )
            self._anchor_reversals.pop(canonical, None)

    def _cleanup(self, frame_index: int) -> None:
        expiry = max(self.max_gap_frames, self.heavy_max_gap_frames) * 8
        stale = {cid for cid, state in self._states.items() if frame_index - state.frame_index > expiry}
        if not stale:
            return
        for cid in stale:
            self._states.pop(cid, None)
            self._canonical_raw_ids.pop(cid, None)
            self._anchor_velocities.pop(cid, None)
            self._anchor_reversals.pop(cid, None)
        for raw_id, cid in list(self._raw_to_canonical.items()):
            if cid in stale:
                self._raw_to_canonical.pop(raw_id, None)
