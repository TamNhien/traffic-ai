from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, hypot, isfinite, nextafter, sin

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


@dataclass(slots=True)
class _StationaryOwnership:
    """Bounded evidence for one uninterrupted same-raw stationary episode."""

    raw_id: int
    origin: Point
    first_frame: int
    last_frame: int
    observations: int
    footprint: float
    max_drift: float = 0.0


class TrackContinuityResolver:
    """Bridge short ByteTrack ID switches using motion prediction."""

    def __init__(
        self,
        max_gap_frames: int = 30,
        max_distance_ratio: float = 0.14,
        heavy_max_gap_frames: int | None = None,
        heavy_max_distance_ratio: float | None = None,
        raw_reuse_jump_ratio: float = 0.18,
        short_gap_alias_guard: bool = True,
        two_wheel_heading_inertia: bool = True,
        stationary_alias_guard: bool = True,
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
        # V0.5.82: isolate a ByteTrack token that abruptly reappears at an
        # impossible location, rather than inheriting another vehicle's gate,
        # cooldown, class and crossing history. The guard is deliberately very
        # narrow: the same raw ID must jump in <=3 frames by >18% of the full
        # frame diagonal AND by >3 previous/current bounding-box diagonals.
        # A fast vehicle returning after a genuine longer gap is not split.
        self.raw_reuse_jump_ratio = max(0.0, float(raw_reuse_jump_ratio))
        self.raw_id_discontinuities = 0
        self.short_gap_alias_rejections = 0
        self.stationary_alias_rejections = 0
        self.short_gap_alias_guard = bool(short_gap_alias_guard)
        self.two_wheel_heading_inertia = bool(two_wheel_heading_inertia)
        self.stationary_alias_guard = bool(stationary_alias_guard)
        self._stationary_ownership: dict[int, _StationaryOwnership] = {}
        self._raw_to_canonical: dict[int, int] = {}
        # V0.5.84: raw-token observations are NOT interchangeable with the
        # canonical identity's latest position. A canonical may be updated by
        # another ByteTrack alias between two observations of this raw token.
        # Testing against the canonical state could then falsely classify the
        # returning raw token as a teleport and tear down a valid crossing.
        self._raw_observations: dict[int, _IdentityState] = {}
        self._states: dict[int, _IdentityState] = {}
        # V0.5.62: a raw tracker token can also be an occupied canonical ID.
        # Keep collision-only identities in a separate, decreasing namespace.
        # Never reset this counter on TTL cleanup: the worker's gate/class
        # histories may outlive a continuity state. Normally ByteTrack IDs are
        # nonnegative; remember caller-supplied negative tokens too, so a later
        # synthetic allocation cannot reuse one after its motion state expires.
        self._next_synthetic_canonical_id = -1
        self._reserved_negative_ids: set[int] = set()
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
        visible_raw_centers: dict[int, Point] | None = None,
    ) -> tuple[int, bool]:
        # Expire the previous identity before an arriving raw ID can refresh it.
        # Otherwise a reused ID after a long silence revives stale motion state.
        self._cleanup(frame_index)
        raw_id = int(raw_id)
        if raw_id < 0:
            self._reserved_negative_ids.add(raw_id)
        claimed = claimed_canonical_ids or set()
        canonical = self._raw_to_canonical.get(raw_id)
        detached_canonical: int | None = None
        if canonical is not None and canonical not in claimed:
            previous = self._states.get(canonical)
            # Dual-provenance guard. A canonical identity may have been updated
            # by another raw alias since this token was last observed. Check
            # BOTH trajectories to avoid two dangerous cases:
            # - the raw ID genuinely teleported but the other alias moved the
            #   canonical nearby, hiding a reuse from the old detector;
            # - the raw token stayed nearby while the canonical jumped far due
            #   to another alias. Keeping them merged would fabricate a crossing.
            own_previous = self._raw_observations.get(raw_id)
            if own_previous is None and previous is not None and previous.last_raw_id == raw_id:
                own_previous = previous
            own_jump = (
                own_previous is not None
                and self._raw_reuse_is_discontinuous(
                    own_previous, point, frame_index, frame_width, frame_height, rect
                )
            )
            alias_jump = (
                previous is not None and previous.last_raw_id != raw_id
                and self._raw_reuse_is_discontinuous(
                    previous, point, frame_index, frame_width, frame_height, rect
                )
            )
            if own_jump or alias_jump:
                # Do not merge a distant new object's observations with the old
                # identity. Retire only the raw mapping; the previous canonical
                # trajectory may still reappear under a different ByteTrack ID.
                detached_canonical = canonical
                self._raw_to_canonical.pop(raw_id, None)
                self._canonical_raw_ids.get(canonical, set()).discard(raw_id)
                self.raw_id_discontinuities += 1
                canonical = None
            else:
                self._canonical_raw_ids.setdefault(canonical, set()).add(raw_id)
                self._record_raw_observation(raw_id, point, label, frame_index, rect)
                self._update_state(canonical, raw_id, point, label, frame_index, rect)
                self._cleanup(frame_index)
                return canonical, False

        diagonal = max(hypot(frame_width, frame_height), 1.0)
        family = _vehicle_family(label)
        best: tuple[float, int] | None = None
        for candidate_id, state in self._states.items():
            # A just-retired raw ID cannot stitch straight back into the
            # identity from which it was detached, even for heavy vehicles.
            if candidate_id == detached_canonical:
                continue
            gap = frame_index - state.frame_index
            state_family = _vehicle_family(state.label)
            gap_limit = self.heavy_max_gap_frames if family == "four-wheel" and state_family == "four-wheel" else self.max_gap_frames
            if gap <= 0 or gap > gap_limit or candidate_id in claimed:
                continue
            if state_family != family:
                continue

            # V0.5.86: reserve the identity for a visibly returning incumbent
            # for up to twelve frames of two-wheel occlusion. V0.5.80 only
            # checked <=3 frames, leaving a 4-12-frame window where the batch
            # could stitch an unrelated newcomer first, then force the actual
            # returning raw ID onto a different canonical identity. Both raw
            # tokens must be visible in THIS frame; the incumbent must still
            # be spatially close and strictly closer than the newcomer.
            # Keep the old <=3-frame rule for four-wheel vehicles. This is
            # order-independent and can be rolled back with the existing
            # AI_SHORT_GAP_ALIAS_GUARD switch (for the extended window only).
            incumbent_window = (
                gap <= 3 or (
                    self.short_gap_alias_guard
                    and family == 'two-wheel'
                    and 4 <= gap <= 12
                )
            )
            if visible_raw_centers and incumbent_window:
                incumbent = int(state.last_raw_id)
                incumbent_point = visible_raw_centers.get(incumbent)
                if incumbent != raw_id and incumbent_point is not None:
                    incumbent_distance = hypot(
                        incumbent_point[0] - state.point[0],
                        incumbent_point[1] - state.point[1],
                    )
                    newcomer_distance = hypot(
                        point[0] - state.point[0], point[1] - state.point[1],
                    )
                    if (
                        incumbent_distance <= max(15.0, diagonal * 0.055)
                        and newcomer_distance > incumbent_distance + max(15.0, diagonal * 0.025)
                    ):
                        continue

            if self._opposite_two_wheel_stitch(state, point, rect, family, gap):
                continue

            if self._stationary_owner_contradiction(candidate_id, state, raw_id, point, rect, family, gap):
                self.stationary_alias_rejections += 1
                continue

            # V0.5.93: include one-to-three-frame token handoffs in the
            # existing footprint-and-prediction contradiction check. Session
            # #193 shows a one-frame foreground token jumping about 250 pixels into
            # a rider's identity, fabricating an early passage and suppressing
            # the rider's later real passage through the ordinary dedup guard.
            # A far jump alone still cannot reject coherent fast motion.
            # V0.5.85: when a new ByteTrack token appears after a short
            # occlusion, do not let it steal a different two-wheel identity
            # whose old measured trajectory AND bounding-box footprint both
            # contradict this arrival. Session #186, frames 15143 -> 15152,
            # shows a motorcycle at (1056, 502) being offered a raw token at
            # (1181, 256), while the incumbent raw returns two frames later.
            # The previous global frame-diagonal tolerance accepts that jump.
            # Keep fast riders: a long displacement alone is NEVER enough;
            # the velocity-predicted position must also be far away.
            if (
                self.short_gap_alias_guard
                and family == 'two-wheel'
                and 1 <= gap <= 12
                and state.last_raw_id != raw_id
                and state.rect is not None and rect is not None
            ):
                old_box = hypot(
                    max(0.0, state.rect[2] - state.rect[0]),
                    max(0.0, state.rect[3] - state.rect[1]),
                )
                new_box = hypot(
                    max(0.0, rect[2] - rect[0]),
                    max(0.0, rect[3] - rect[1]),
                )
                footprint = max(20.0, old_box, new_box)
                direct_jump = hypot(point[0] - state.point[0], point[1] - state.point[1])
                predicted_jump = hypot(
                    point[0] - state.point[0] - state.velocity[0] * gap,
                    point[1] - state.point[1] - state.velocity[1] * gap,
                )
                if direct_jump > 1.75 * footprint and predicted_jump > 1.50 * footprint:
                    self.short_gap_alias_rejections += 1
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
        canonical = best[1] if best is not None else self._fresh_canonical_id(raw_id, claimed)
        self._raw_to_canonical[raw_id] = canonical
        self._canonical_raw_ids.setdefault(canonical, set()).add(raw_id)
        self._record_raw_observation(raw_id, point, label, frame_index, rect)
        self._update_state(canonical, raw_id, point, label, frame_index, rect)
        if stitched:
            self.stitch_count += 1
            if family == "four-wheel":
                self.heavy_stitch_count += 1
        self._cleanup(frame_index)
        return canonical, stitched

    def _record_raw_observation(
        self, raw_id: int, point: Point, label: str, frame_index: int, rect: Rect | None,
    ) -> None:
        prior = self._raw_observations.get(raw_id)
        if prior is not None and frame_index <= prior.frame_index:
            return
        self._raw_observations[raw_id] = _IdentityState(
            point, int(frame_index), str(label), int(raw_id), rect=rect,
        )

    @staticmethod
    def _valid_footprint(point: Point, rect: Rect | None) -> float | None:
        if rect is None or not all(isfinite(value) for value in (*point, *rect)):
            return None
        width, height = rect[2] - rect[0], rect[3] - rect[1]
        if width <= 0.0 or height <= 0.0:
            return None
        return max(20.0, hypot(width, height))

    def _record_stationary_ownership(
        self, canonical: int, raw_id: int, point: Point, label: str,
        frame_index: int, rect: Rect | None,
    ) -> None:
        """Keep the full episode's drift, even with a dense source clock.

        A fixed sample ring can forget earlier motion or never cover twelve
        frames at high observation density. This constant-size certificate
        retains the episode origin and its worst drift instead. Invalid boxes,
        raw switches and long gaps start independent evidence.
        """
        footprint = self._valid_footprint(point, rect)
        if not self.stationary_alias_guard or _vehicle_family(label) != "two-wheel" or footprint is None:
            self._stationary_ownership.pop(canonical, None)
            return
        episode = self._stationary_ownership.get(canonical)
        if episode is not None and episode.raw_id == raw_id and 0 < frame_index - episode.last_frame <= self.max_gap_frames:
            minimum_footprint = min(episode.footprint, footprint)
            drift = max(episode.max_drift, hypot(point[0] - episode.origin[0], point[1] - episode.origin[1]))
            if drift <= .25 * minimum_footprint:
                episode.last_frame = int(frame_index)
                episode.observations = min(3, episode.observations + 1)
                episode.footprint = minimum_footprint
                episode.max_drift = drift
                return
        self._stationary_ownership[canonical] = _StationaryOwnership(
            int(raw_id), point, int(frame_index), int(frame_index), 1, footprint,
        )

    def _stationary_owner_contradiction(
        self, candidate_id: int, state: _IdentityState, raw_id: int,
        point: Point, rect: Rect | None, family: str, gap: int,
    ) -> bool:
        """Stop a distant newcomer borrowing a proven parked rider identity.

        Only the previously unprotected 13..normal-gap window is involved.
        The direct jump uses the OLD owner's size: a large foreground rider's
        box cannot enlarge a small parked rider's ownership radius. Prediction
        must independently contradict both footprints, preserving perspective
        growth and coherent fast motion. Established moving headings and all
        four-wheel continuity retain their existing rules.
        """
        if (
            not self.stationary_alias_guard or family != "two-wheel"
            or not 13 <= gap <= self.max_gap_frames or state.last_raw_id == raw_id
            or candidate_id in self._anchor_velocities
            or abs(state.velocity[0]) + abs(state.velocity[1]) > .5
        ):
            return False
        episode = self._stationary_ownership.get(candidate_id)
        current_footprint = self._valid_footprint(point, rect)
        if (
            episode is None or current_footprint is None
            or episode.raw_id != state.last_raw_id or episode.last_frame != state.frame_index
            or episode.observations < 3 or episode.last_frame - episode.first_frame < 12
            or episode.max_drift > .25 * episode.footprint
        ):
            return False
        direct_jump = hypot(point[0] - state.point[0], point[1] - state.point[1])
        predicted_jump = hypot(
            point[0] - state.point[0] - state.velocity[0] * gap,
            point[1] - state.point[1] - state.velocity[1] * gap,
        )
        return (
            direct_jump > 1.75 * episode.footprint
            and predicted_jump > 1.50 * max(episode.footprint, current_footprint)
        )

    def _raw_reuse_is_discontinuous(
        self, previous: _IdentityState, point: Point, frame_index: int,
        width: int, height: int, rect: Rect | None,
    ) -> bool:
        """Fail closed only on an *implausible* near-instant raw-ID teleport.

        This check is deliberately independent of benchmark Ground Truth and
        does not use a general travel-speed limit. It requires both a large
        full-frame displacement and a large displacement relative to BOTH
        bounding boxes; otherwise perspective changes and legitimate fast
        vehicles would trigger identity churn and more false crossings.
        """
        gap = int(frame_index) - previous.frame_index
        if not (0 < gap <= 3 and self.raw_reuse_jump_ratio > 0):
            return False
        if previous.rect is None or rect is None:
            return False
        distance = hypot(point[0] - previous.point[0], point[1] - previous.point[1])
        if distance <= max(1.0, hypot(width, height)) * self.raw_reuse_jump_ratio:
            return False
        def box_diagonal(box: Rect) -> float:
            return hypot(max(0.0, box[2] - box[0]), max(0.0, box[3] - box[1]))
        return distance > 3.0 * max(box_diagonal(previous.rect), box_diagonal(rect), 1.0)

    def _fresh_canonical_id(self, raw_id: int, claimed: set[int]) -> int:
        """Choose a fresh identity without overwriting a visible alias owner.

        When raw 44 aliases canonical 10, both 44 and the returning raw 10 may
        coexist in one frame. The second observation must not fall back to the
        already claimed 10. A fresh canonical starts with its own motion and
        lineage; no gate/class history is transferred by this resolver.
        """
        already_synthetic = self._next_synthetic_canonical_id < raw_id < 0
        if raw_id not in self._states and raw_id not in claimed and not already_synthetic:
            return raw_id
        mapped_ids = set(self._raw_to_canonical.values())
        candidate = self._next_synthetic_canonical_id
        while (
            candidate in self._reserved_negative_ids or candidate in self._states
            or candidate in claimed or candidate in mapped_ids
        ):
            candidate -= 1
        self._next_synthetic_canonical_id = candidate - 1
        return candidate

    def alias_raw_id(self, raw_id: int, canonical_id: int) -> int | None:
        """Bind a duplicate raw ID and report any displaced canonical ID.

        V0.5.30 lets the worker coalesce gate/classification state when a
        CAR/TRUCK/BUS duplicate was already alive under another canonical ID.
        """
        raw_id = int(raw_id)
        canonical_id = int(canonical_id)
        self._reserved_negative_ids.update(value for value in (raw_id, canonical_id) if value < 0)
        previous = self._raw_to_canonical.get(raw_id)
        self._raw_to_canonical[raw_id] = canonical_id
        # A fusion is not same-raw observation evidence. Neither owner may
        # inherit a stationary certificate assembled by a different identity.
        self._stationary_ownership.pop(canonical_id, None)
        self._canonical_raw_ids.setdefault(canonical_id, set()).add(raw_id)
        displaced = previous if previous is not None and previous != canonical_id else None
        if displaced is not None:
            self._stationary_ownership.pop(displaced, None)
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
        self._record_stationary_ownership(canonical, raw_id, point, label, frame_index, rect)
        speed = abs(velocity[0]) + abs(velocity[1])
        if speed >= 1.5:
            self._set_anchor_heading(canonical, frame_index, velocity, previous)
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
            self._set_anchor_heading(
                canonical, frame_index,
                (velocity[0] * full_speed / speed, velocity[1] * full_speed / speed), previous,
            )
            self._anchor_reversals.pop(canonical, None)

    def _set_anchor_heading(
        self, canonical: int, frame_index: int, velocity: Point,
        previous: _IdentityState | None,
    ) -> None:
        """Turn a two-wheel contact proxy in proportion to observed travel.

        V0.5.94: a few pixels of detector-box jitter can exceed the 1.5-pixel
        full-heading boundary and swing a large box's anchor across the gate.
        Retain the actual velocity for prediction; only its contact heading has
        inertia. One observed half-box diagonal of travel permits a complete
        heading update. Smaller motion caps the shortest turn to travel/radius
        radians, so modest, supported curvature keeps its immediate response.
        The finite gate and road-zone checks remain unchanged.
        """
        heading = self._anchor_velocities.get(canonical)
        state = self._states[canonical]
        if (
            not self.two_wheel_heading_inertia or previous is None or heading is None
            or _vehicle_family(state.label) != "two-wheel"
            or previous.rect is None or state.rect is None
            or frame_index - previous.frame_index > self.max_gap_frames
        ):
            self._anchor_velocities[canonical] = (int(frame_index), velocity)
            return
        radius = max(
            hypot(max(0., box[2] - box[0]), max(0., box[3] - box[1])) * .5
            for box in (previous.rect, state.rect)
        )
        travel = hypot(state.point[0] - previous.point[0], state.point[1] - previous.point[1])
        weight = min(1., travel / max(1.5, radius))
        if weight >= 1.:
            self._anchor_velocities[canonical] = (int(frame_index), velocity)
            return
        old = heading[1]
        # atan2 also defines the exact antiparallel case. Interpolating angles
        # avoids a zero vector at a half turn and its stationary-bottom fallback.
        turn = atan2(old[0] * velocity[1] - old[1] * velocity[0],
                     old[0] * velocity[0] + old[1] * velocity[1])
        if abs(turn) <= weight:
            self._anchor_velocities[canonical] = (int(frame_index), velocity)
            return
        angle = atan2(old[1], old[0]) + max(-weight, min(weight, turn))
        unit = (cos(angle), sin(angle))
        full_speed = nextafter(1.5, float("inf"))
        scale = full_speed / (abs(unit[0]) + abs(unit[1]))
        self._anchor_velocities[canonical] = (int(frame_index), (unit[0] * scale, unit[1] * scale))

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
            self._stationary_ownership.pop(cid, None)
        for raw_id, cid in list(self._raw_to_canonical.items()):
            if cid in stale:
                self._raw_to_canonical.pop(raw_id, None)
                self._raw_observations.pop(raw_id, None)
