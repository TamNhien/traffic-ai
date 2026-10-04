from __future__ import annotations

from collections import deque
import os
from dataclasses import dataclass, field
from math import hypot, isfinite

Point = tuple[float, float]


@dataclass(slots=True)
class CountingLine:
    x1: float = 0.1
    y1: float = 0.5
    x2: float = 0.9
    y2: float = 0.5

    def __post_init__(self) -> None:
        # Image coordinates grow downward. Canonicalizing the gate left-to-right
        # makes signed_side() positive below the gate, so negative -> positive is
        # always top -> bottom = IN and the reverse is OUT. This also prevents
        # endpoint dragging/order changes from silently flipping direction labels.
        if self.x2 < self.x1:
            self.x1, self.y1, self.x2, self.y2 = self.x2, self.y2, self.x1, self.y1

    def denormalize(self, width: int, height: int) -> tuple[Point, Point]:
        return (self.x1 * width, self.y1 * height), (self.x2 * width, self.y2 * height)


@dataclass(slots=True)
class RoadZone:
    """Normalized clockwise quadrilateral containing only drivable roadway."""

    x1: float = 0.20
    y1: float = 0.16
    x2: float = 0.80
    y2: float = 0.16
    x3: float = 0.96
    y3: float = 0.98
    x4: float = 0.04
    y4: float = 0.98

    def normalized_points(self) -> list[Point]:
        return [
            (self.x1, self.y1),
            (self.x2, self.y2),
            (self.x3, self.y3),
            (self.x4, self.y4),
        ]

    def denormalize(self, width: int, height: int) -> list[Point]:
        return [(x * width, y * height) for x, y in self.normalized_points()]

    def contains(self, point: Point, width: int, height: int) -> bool:
        return point_in_polygon(point, self.denormalize(width, height))

    def contains_with_margin(self, point: Point, width: int, height: int, margin_ratio: float = 0.0) -> bool:
        """Accept a tiny tracking-anchor error around the polygon boundary.

        Crossing/probe points remain strict. V0.5.21 uses this only for the two
        observed anchors so a bounding-box leading edge a few pixels outside the
        green road polygon does not create a false Road Zone miss.
        """
        polygon = self.denormalize(width, height)
        if point_in_polygon(point, polygon):
            return True
        margin_px = max(0.0, float(margin_ratio)) * max(1.0, min(width, height))
        if margin_px <= 0:
            return False
        return min(
            point_segment_distance(point, polygon[index], polygon[(index + 1) % len(polygon)])
            for index in range(len(polygon))
        ) <= margin_px

    @property
    def area_ratio(self) -> float:
        points = self.normalized_points()
        twice = 0.0
        for index, point in enumerate(points):
            nxt = points[(index + 1) % len(points)]
            twice += point[0] * nxt[1] - nxt[0] * point[1]
        return abs(twice) * 0.5

    @property
    def is_simple(self) -> bool:
        points = self.normalized_points()
        return not (
            segments_intersect(points[0], points[1], points[2], points[3])
            or segments_intersect(points[1], points[2], points[3], points[0])
        )

    def validate(self, min_area_ratio: float = 0.02) -> None:
        if not self.is_simple:
            raise ValueError("Road zone polygon is self-intersecting")
        if self.area_ratio < min_area_ratio:
            raise ValueError("Road zone is too small")


def _point_on_segment(point: Point, a: Point, b: Point, eps: float = 1e-6) -> bool:
    ax, ay = a
    bx, by = b
    px, py = point
    cross = abs((px - ax) * (by - ay) - (py - ay) * (bx - ax))
    if cross > eps * max(1.0, hypot(bx - ax, by - ay)):
        return False
    return min(ax, bx) - eps <= px <= max(ax, bx) + eps and min(ay, by) - eps <= py <= max(ay, by) + eps


def point_segment_distance(point: Point, a: Point, b: Point) -> float:
    px, py = point
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-12:
        return hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    qx, qy = ax + t * dx, ay + t * dy
    return hypot(px - qx, py - qy)


def point_in_polygon(point: Point, polygon: list[Point]) -> bool:
    """Boundary-inclusive ray casting for the editable road polygon."""
    if len(polygon) < 3:
        return False
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        a, b = polygon[j], polygon[i]
        if _point_on_segment(point, a, b):
            return True
        xi, yi = b
        xj, yj = a
        if (yi > y) != (yj > y):
            denom = yj - yi
            if abs(denom) > 1e-12:
                x_at_y = (xj - xi) * (y - yi) / denom + xi
                if x < x_at_y:
                    inside = not inside
        j = i
    return inside


def signed_side(point: Point, a: Point, b: Point) -> float:
    return (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])


def signed_distance(point: Point, a: Point, b: Point) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length = max((dx * dx + dy * dy) ** 0.5, 1e-9)
    return signed_side(point, a, b) / length


def _cross(v1: Point, v2: Point) -> float:
    return v1[0] * v2[1] - v1[1] * v2[0]


def segment_crossing_point(
    p0: Point,
    p1: Point,
    a: Point,
    b: Point,
    segment_margin: float = 0.0,
    eps: float = 1e-7,
) -> Point | None:
    """Return the finite-gate intersection for a trajectory segment.

    `segment_margin` is expressed as a fraction of the visible counting-line
    length. V0.5.8 uses zero margin by default, so a vehicle is never counted
    merely because its trajectory crosses an imaginary extension beyond either
    endpoint of the line.
    """

    r = (p1[0] - p0[0], p1[1] - p0[1])
    s = (b[0] - a[0], b[1] - a[1])
    denominator = _cross(r, s)
    if abs(denominator) <= eps:
        return None

    q_minus_p = (a[0] - p0[0], a[1] - p0[1])
    t = _cross(q_minus_p, s) / denominator
    u = _cross(q_minus_p, r) / denominator
    margin = max(0.0, float(segment_margin))
    if t < -eps or t > 1.0 + eps:
        return None
    if u < -margin - eps or u > 1.0 + margin + eps:
        return None
    return (p0[0] + t * r[0], p0[1] + t * r[1])


def segments_intersect(a: Point, b: Point, c: Point, d: Point, eps: float = 1e-6) -> bool:
    return segment_crossing_point(a, b, c, d, segment_margin=0.0, eps=eps) is not None


def crossing_frame_between(start: "_GateSample", end: "_GateSample", crossing: Point) -> float:
    """Estimate the source-frame position where a tracked segment hits the gate.

    Event persistence used to stamp the *confirmation* frame. For rescued/interpolated
    tracks that can be many frames after the physical line intersection, which turns one
    real crossing into a benchmark miss + false-positive pair. Project the gate
    intersection onto the observed motion segment and interpolate the frame index.
    """
    dx = float(end.point[0] - start.point[0])
    dy = float(end.point[1] - start.point[1])
    denom = dx * dx + dy * dy
    if denom <= 1e-9 or end.frame_index <= start.frame_index:
        return float(end.frame_index)
    ux = float(crossing[0] - start.point[0])
    uy = float(crossing[1] - start.point[1])
    alpha = max(0.0, min(1.0, (ux * dx + uy * dy) / denom))
    return float(start.frame_index) + alpha * float(end.frame_index - start.frame_index)


def select_event_crossing_frame(
    observed_frame: int | float,
    geometric_frame: float | None,
    crossing_mode: str | None,
    *,
    max_interpolated_shift_frames: float = 6.0,
    max_rescued_shift_frames: float = 18.0,
) -> tuple[float, bool, bool]:
    """Choose a trustworthy source frame for event persistence.

    V0.5.31 applied geometric interpolation to nearly every event.  The supplied
    benchmark showed that this is too aggressive: direct crossings do not need a
    synthetic timestamp, while long rescue gaps assume constant image-plane speed
    across perspective changes.  V0.5.32 therefore keeps direct events on their
    observed frame, applies bounded interpolation to short/dead-band events, and
    clamps long-gap rescue back-shifts instead of trusting an arbitrarily old
    extrapolated instant.

    Returns ``(selected_frame, corrected, clamped)``.
    """
    observed = max(1.0, float(observed_frame))
    if geometric_frame is None:
        return observed, False, False
    try:
        geometric = float(geometric_frame)
    except (TypeError, ValueError):
        return observed, False, False
    if geometric < 1.0 or geometric > observed + 0.25:
        return observed, False, False

    shift = observed - geometric
    # Sub-frame correction is benchmark-noise, not useful event semantics.
    if shift < 0.50:
        return observed, False, False

    mode = str(crossing_mode or "").strip().lower()
    if mode == "direct":
        return observed, False, False
    if mode == "interpolated":
        limit = max(0.5, float(max_interpolated_shift_frames))
    elif mode == "rescued":
        limit = max(0.5, float(max_rescued_shift_frames))
    else:
        return observed, False, False

    if shift <= limit:
        return geometric, True, False
    return observed - limit, True, True


@dataclass(slots=True)
class _GateSample:
    frame_index: int
    point: Point
    distance: float
    side: int


def observed_gate_crossing(
    history: list[_GateSample], start: _GateSample, end: _GateSample,
    a: Point, b: Point, *, segment_margin: float = 0.0,
) -> tuple[_GateSample, _GateSample, Point] | None:
    """Use the observed bracket, including neutral samples, for finite geometry.

    A stable-side endpoint chord can cut the gate even when intervening observed
    anchors went around its endpoint. Conversely, the chord can miss a real
    crossing visible in those neutral samples. Sparse trajectories still have a
    valid two-observation bracket; they need no invented replacement chord.
    """
    window = [start] + [
        item for item in history if start.frame_index < item.frame_index < end.frame_index
    ] + [end]
    bracket = None
    last_nonzero = start
    for left, right in zip(window, window[1:]):
        if right.distance == 0.0:
            continue
        # A return to the line followed by motion back to the same side is a
        # touch, not a later crossing. In particular, a post-side zero-distance
        # box sample outside an endpoint must not erase the genuine interior
        # bracket or change its source time.
        if last_nonzero.distance * right.distance < 0.0:
            bracket = left, right
        last_nonzero = right
    if bracket is None:
        return None
    left, right = bracket
    crossing = segment_crossing_point(left.point, right.point, a, b, segment_margin=segment_margin)
    return (left, right, crossing) if crossing is not None else None


def observed_road_path_ok(
    road_zone: RoadZone, history: list[_GateSample], start: _GateSample,
    end: _GateSample, width: int, height: int, margin_ratio: float,
) -> bool:
    """Validate every measured anchor in the geometry's source-frame window."""
    return all(
        road_zone.contains_with_margin(item.point, width, height, margin_ratio)
        for item in history if start.frame_index <= item.frame_index <= end.frame_index
    )


def observed_path_length(
    history: list[_GateSample], start: _GateSample, end: _GateSample,
) -> float:
    """Measure the trajectory used by the crossing, including neutral samples.

    A short endpoint chord can hide a large lateral excursion. Motion and jump
    guards must measure the same observed window as finite-gate/road checks.
    With just two observations this is exactly the existing chord length.
    """
    window = [start] + [
        item for item in history if start.frame_index < item.frame_index < end.frame_index
    ] + [end]
    return sum(
        hypot(right.point[0] - left.point[0], right.point[1] - left.point[1])
        for left, right in zip(window, window[1:])
    )


@dataclass(slots=True)
class _TrackGateState:
    history: deque[_GateSample] = field(default_factory=lambda: deque(maxlen=48))
    origin_history: deque[_GateSample] = field(default_factory=lambda: deque(maxlen=20))
    armed: bool = True
    counted_directions: set[str] = field(default_factory=set)
    last_count_frame: int = -10_000
    last_nonzero_side: int = 0
    side_streak: int = 0
    first_frame: int | None = None
    total_samples: int = 0
    max_abs_distance_since_count: float = 0.0


@dataclass(slots=True)
class _PassageRollback:
    accepted_direction: str
    accepted_frame: int
    counted_directions: set[str]
    last_count_frame: int
    armed: bool
    max_abs_distance_since_count: float
    crossing_point: Point | None
    crossing_frame: float | None
    crossing_mode: str | None
    origin_rescue: bool
    same_direction_override: bool = False
    cooldown_override: bool = False




@dataclass(slots=True)
class _AnchorSpanPending:
    start: _GateSample
    end: _GateSample
    direction: str
    crossing: Point
    crossing_frame: float
    destination_side: int
    frame_width: int
    frame_height: int
    confirmations: int = 1
    opposite_observations: int = 0
    road_edge_rescue: bool = False
    normal_ratio: float = 0.0
    side_depth_ratio: float = 0.0
    same_direction_candidate: bool = False
    approach_span: bool = False
    reviewed_through_frame: int = -10_000


@dataclass(slots=True)
class _AnchorSpanState:
    history: deque[_GateSample] = field(default_factory=lambda: deque(maxlen=64))
    pending: _AnchorSpanPending | None = None
    counted_directions: set[str] = field(default_factory=set)
    last_count_frame: int = -10_000


@dataclass(slots=True)
class _AnchorSpanProposal:
    pending: _AnchorSpanPending
    frame_index: int
    kind: str


class VerifiedAnchorSpanRescuer:
    """Precision-first secondary gate for benchmark-proven anchor spans.

    V0.5.41 never loosens :class:`LineCrossingCounter`.  This helper only runs
    after the primary gate returned no event.  A candidate must span both sides
    of the *finite* gate with bounded jump, strong gate-normal motion and the
    normal Road Zone corridor checks.  Very strong spans can close immediately;
    otherwise a second destination-side observation is required.  The latter is
    the Post-Confirm Closure path.
    """

    def __init__(
        self,
        line: CountingLine,
        road_zone: RoadZone | None = None,
        *,
        enabled: bool = True,
        history_gap_frames: int = 12,
        dead_band_ratio: float = 0.006,
        segment_margin: float = 0.0,
        min_normal_ratio: float = 0.40,
        immediate_min_normal_ratio: float = 0.68,
        max_jump_ratio: float = 0.12,
        min_side_distance_ratio: float = 0.006,
        immediate_min_side_distance_ratio: float = 0.012,
        road_margin_ratio: float = 0.010,
        road_corridor_margin_ratio: float = 0.006,
        post_confirm_samples: int = 2,
        post_confirm_max_gap_frames: int = 6,
        post_confirm_opposite_samples: int = 2,
        same_direction_min_frames: int = 16,
        lost_finalize_min_normal_ratio: float = 0.55,
        lost_finalize_min_side_distance_ratio: float = 0.014,
    ) -> None:
        self.line = line
        self.road_zone = road_zone
        self.enabled = bool(enabled)
        self.history_gap_frames = max(2, int(history_gap_frames))
        self.dead_band_ratio = max(0.0, float(dead_band_ratio))
        self.segment_margin = max(0.0, float(segment_margin))
        self.min_normal_ratio = max(0.0, min(1.0, float(min_normal_ratio)))
        self.immediate_min_normal_ratio = max(self.min_normal_ratio, min(1.0, float(immediate_min_normal_ratio)))
        self.max_jump_ratio = max(0.01, float(max_jump_ratio))
        self.min_side_distance_ratio = max(0.0, float(min_side_distance_ratio))
        self.immediate_min_side_distance_ratio = max(self.min_side_distance_ratio, float(immediate_min_side_distance_ratio))
        self.road_margin_ratio = max(0.0, float(road_margin_ratio))
        self.road_corridor_margin_ratio = max(0.0, float(road_corridor_margin_ratio))
        self.post_confirm_samples = max(1, int(post_confirm_samples))
        self.post_confirm_max_gap_frames = max(1, int(post_confirm_max_gap_frames))
        self.post_confirm_opposite_samples = max(1, int(post_confirm_opposite_samples))
        self.same_direction_min_frames = max(1, int(same_direction_min_frames))
        self.lost_finalize_min_normal_ratio = max(self.min_normal_ratio, min(1.0, float(lost_finalize_min_normal_ratio)))
        self.lost_finalize_min_side_distance_ratio = max(self.min_side_distance_ratio, float(lost_finalize_min_side_distance_ratio))
        self._tracks: dict[int, _AnchorSpanState] = {}
        self.verified_candidates = 0
        self.verified_anchor_span_rescues = 0
        self.post_confirm_closures = 0
        self.post_confirm_jitter_holds = 0
        self.road_edge_span_rescues = 0
        self.rejected_validation = 0
        self.same_direction_overrides = 0
        self.cooldown_overrides = 0
        self.lost_track_finalizations = 0
        self.immediate_override_qualifications = 0
        self.immediate_handoff_rejections = 0
        self.approach_span_candidates = 0
        self.approach_span_rescues = 0
        self._last_crossing_frame: dict[int, float] = {}
        self._override_qualified: set[int] = set()
        self._immediate_candidates: set[int] = set()
        self._span_proposals: dict[int, _AnchorSpanProposal] = {}
        self._committed_proposals: dict[int, _AnchorSpanProposal] = {}

    def _propose_span(
        self, track_id: int, pending: _AnchorSpanPending, frame_index: int, kind: str,
    ) -> tuple[str, Point]:
        self._span_proposals[track_id] = _AnchorSpanProposal(pending, int(frame_index), kind)
        self._immediate_candidates.discard(track_id)
        self._override_qualified.discard(track_id)
        if kind == "immediate":
            self._immediate_candidates.add(track_id)
        else:
            self._override_qualified.add(track_id)
        return pending.direction, pending.crossing

    def _account_span_proposal(self, proposal: _AnchorSpanProposal, delta: int) -> None:
        pending = proposal.pending
        self.verified_anchor_span_rescues = max(0, self.verified_anchor_span_rescues + delta)
        if proposal.kind == "post-confirm":
            self.post_confirm_closures = max(0, self.post_confirm_closures + delta)
        elif proposal.kind == "lost":
            self.lost_track_finalizations = max(0, self.lost_track_finalizations + delta)
        elif proposal.kind == "immediate":
            self.immediate_override_qualifications = max(0, self.immediate_override_qualifications + delta)
        if pending.road_edge_rescue:
            self.road_edge_span_rescues = max(0, self.road_edge_span_rescues + delta)
        if pending.same_direction_candidate:
            self.same_direction_overrides = max(0, self.same_direction_overrides + delta)
        if pending.approach_span:
            self.approach_span_rescues = max(0, self.approach_span_rescues + delta)

    def _review_pending_history(self, state: _AnchorSpanState) -> str:
        """Replay post-span observations after aliases merge their histories.

        The latest step alone cannot validate an earlier jump, road departure or
        sustained opposite return inserted by alias fusion. Rebuild confirmation
        from unique source frames; a cancelled lifecycle cannot revive because a
        later destination observation happens to be local.
        """
        pending = state.pending
        if pending is None:
            return "valid"
        previous = pending.end
        confirmations = 1
        opposite = 0
        for sample in state.history:
            if sample.frame_index <= pending.end.frame_index:
                continue
            jump = hypot(
                sample.point[0] - previous.point[0], sample.point[1] - previous.point[1],
            ) / max(hypot(pending.frame_width, pending.frame_height), 1.0)
            road_ok = self.road_zone is None or self.road_zone.contains_with_margin(
                sample.point, pending.frame_width, pending.frame_height, self.road_margin_ratio,
            )
            if jump > self.max_jump_ratio or not road_ok:
                self.rejected_validation += 1
                state.pending = None
                # A fresh span may start at this observation, but it cannot
                # replay the original span or the rejected incoming jump.
                state.history = deque([
                    item for item in state.history if item.frame_index >= sample.frame_index
                ], maxlen=64)
                return "invalid"
            if sample.side == -pending.destination_side:
                opposite += 1
                if opposite >= self.post_confirm_opposite_samples:
                    state.pending = None
                    state.history = deque([
                        item for item in state.history if item.frame_index >= sample.frame_index
                    ], maxlen=64)
                    return "opposite"
                if sample.frame_index > pending.reviewed_through_frame:
                    self.post_confirm_jitter_holds += 1
            elif sample.side == pending.destination_side:
                opposite = 0
                confirmations += 1
            previous = sample
        pending.confirmations = confirmations
        pending.opposite_observations = opposite
        pending.reviewed_through_frame = max(pending.reviewed_through_frame, previous.frame_index)
        return "valid"

    def _revalidate_merged_pending_span(self, state: _AnchorSpanState) -> bool:
        """Rebuild pending geometry from the canonical merged observations.

        A pending span may have been proven by a sparse pair before an alias
        supplied intervening samples or replaced an endpoint at the same frame.
        Post-side confirmation cannot preserve proof contradicted by that now
        observed route. Valid added observations also define the actual crossing
        point and clock instead of the original sparse chord.
        """
        pending = state.pending
        if pending is None:
            return True
        history = list(state.history)
        by_frame = {item.frame_index: item for item in history}
        start = by_frame.get(pending.start.frame_index)
        end = by_frame.get(pending.end.frame_index)
        proof = None
        if (
            start is not None and end is not None
            and start.side == -pending.destination_side
            and end.side == pending.destination_side
            and 0 < end.frame_index - start.frame_index <= self.history_gap_frames
        ):
            window = [item for item in history if start.frame_index <= item.frame_index <= end.frame_index]
            # Approach recovery additionally promised continuous normal
            # progress. Merged evidence must keep that same promise.
            monotonic = not pending.approach_span or all(
                (right.distance - left.distance) * end.side >= -1e-6
                for left, right in zip(window, window[1:])
            )
            a, b = self.line.denormalize(pending.frame_width, pending.frame_height)
            crossing = observed_gate_crossing(
                history, start, end, a, b, segment_margin=self.segment_margin,
            )
            if monotonic and crossing is not None:
                left, right, point = crossing
                path_length = max(observed_path_length(history, start, end), 1e-6)
                normal_ratio = abs(end.distance - start.distance) / path_length
                side_depth = min(abs(start.distance), abs(end.distance)) / max(
                    1.0, min(pending.frame_width, pending.frame_height),
                )
                road_ok, road_edge = self._road_ok(
                    start, end, point, pending.frame_width, pending.frame_height,
                    corridor_start=left, corridor_end=right,
                )
                if self.road_zone is not None:
                    road_ok = road_ok and observed_road_path_ok(
                        self.road_zone, history, start, end, pending.frame_width,
                        pending.frame_height, self.road_margin_ratio,
                    )
                if (
                    normal_ratio >= self.min_normal_ratio
                    and path_length / max(hypot(pending.frame_width, pending.frame_height), 1.0) <= self.max_jump_ratio
                    and side_depth >= self.min_side_distance_ratio
                    and road_ok
                ):
                    proof = start, end, point, crossing_frame_between(left, right, point), normal_ratio, side_depth, road_edge
        if proof is None:
            self.rejected_validation += 1
            state.pending = None
            # Keep the canonical end and later observations for a genuinely
            # new return; the rejected incoming span can never reopen.
            state.history = deque([
                item for item in history if item.frame_index >= pending.end.frame_index
            ], maxlen=64)
            return False
        (
            pending.start, pending.end, pending.crossing, pending.crossing_frame,
            pending.normal_ratio, pending.side_depth_ratio, pending.road_edge_rescue,
        ) = proof
        return True

    def _road_ok(
        self, start: _GateSample, end: _GateSample, crossing: Point, width: int, height: int,
        *, corridor_start: _GateSample | None = None, corridor_end: _GateSample | None = None,
    ) -> tuple[bool, bool]:
        if self.road_zone is None:
            return True, False
        # The finite intersection and the road probes describe the same actual
        # observed bracket. A stable endpoint chord may point outside the road
        # when a curved measured trajectory crosses inside, or hide the reverse.
        local_start = corridor_start if corridor_start is not None else start
        local_end = corridor_end if corridor_end is not None else end
        dx = local_end.point[0] - local_start.point[0]
        dy = local_end.point[1] - local_start.point[1]
        length = max(hypot(dx, dy), 1e-6)
        ux, uy = dx / length, dy / length
        probe = max(3.0, min(width, height) * 0.018)
        before = (crossing[0] - ux * probe, crossing[1] - uy * probe)
        after = (crossing[0] + ux * probe, crossing[1] + uy * probe)
        anchors_ok = (
            self.road_zone.contains_with_margin(start.point, width, height, self.road_margin_ratio)
            and self.road_zone.contains_with_margin(end.point, width, height, self.road_margin_ratio)
        )
        strict_corridor = (
            self.road_zone.contains(crossing, width, height)
            and self.road_zone.contains(before, width, height)
            and self.road_zone.contains(after, width, height)
        )
        if anchors_ok and strict_corridor:
            return True, False
        # V0.5.43: a verified finite-line span may survive a *tiny* Road Zone
        # calibration edge error.  This does not loosen the primary counter: all
        # three corridor probes still have to be inside the same small margin.
        margin = self.road_corridor_margin_ratio
        margin_corridor = margin > 0.0 and all(
            self.road_zone.contains_with_margin(point, width, height, margin)
            for point in (crossing, before, after)
        )
        return bool(anchors_ok and margin_corridor), bool(anchors_ok and margin_corridor and not strict_corridor)

    def _verified_approach_span(
        self, history: list[_GateSample], width: int, height: int,
    ) -> tuple[_GateSample, Point, float, float, float, bool] | None:
        """Audit a continuous approach when the nearest box sample is oblique.

        A recent lateral box wobble can make the last two observations fail the
        normal-motion guard even while the measured approach crossed the gate.
        An older chord alone is insufficient: every observed step must progress
        toward the destination, the *total path* must pass the existing jump and
        normal-motion limits, and an adjacent observed segment must intersect
        the finite gate. This path always waits for post-side confirmation.
        """
        end = history[-1]
        a, b = self.line.denormalize(width, height)
        scale = max(1.0, min(width, height))
        diagonal = max(hypot(width, height), 1.0)
        for index in range(len(history) - 3, -1, -1):
            start = history[index]
            gap = end.frame_index - start.frame_index
            if gap > self.history_gap_frames:
                break
            if start.side != -end.side or gap <= 0:
                continue
            window = history[index:]
            # Do not recover a prior crossing, a reversal, or alias samples from
            # the same source frame by selecting an older, more favorable chord.
            if any(
                right.frame_index <= left.frame_index
                or (right.distance - left.distance) * end.side < -1e-6
                for left, right in zip(window, window[1:])
            ):
                continue
            path_length = sum(
                hypot(right.point[0] - left.point[0], right.point[1] - left.point[1])
                for left, right in zip(window, window[1:])
            )
            normal_ratio = abs(end.distance - start.distance) / max(path_length, 1e-6)
            side_depth = min(abs(start.distance), abs(end.distance)) / scale
            if (
                normal_ratio < self.min_normal_ratio
                or path_length / diagonal > self.max_jump_ratio
                or side_depth < self.min_side_distance_ratio
            ):
                continue
            if self.road_zone is not None and not all(
                self.road_zone.contains_with_margin(item.point, width, height, self.road_margin_ratio)
                for item in window
            ):
                continue
            observed_crossing = observed_gate_crossing(
                window, start, end, a, b, segment_margin=self.segment_margin,
            )
            if observed_crossing is None:
                continue
            left, right, crossing = observed_crossing
            road_ok, road_edge = self._road_ok(
                start, end, crossing, width, height, corridor_start=left, corridor_end=right,
            )
            if not road_ok:
                continue
            return start, crossing, crossing_frame_between(left, right, crossing), normal_ratio, side_depth, road_edge
        return None

    def update(
        self, track_id: int, anchor: Point, width: int, height: int, frame_index: int,
        *, commit: bool = True,
    ) -> tuple[str, Point] | None:
        if not self.enabled:
            return None
        tid = int(track_id)
        a, b = self.line.denormalize(width, height)
        scale = max(1.0, min(width, height))
        distance = signed_distance(anchor, a, b)
        dead_band = max(2.0, scale * self.dead_band_ratio)
        side = 0 if abs(distance) <= dead_band else (1 if distance > 0 else -1)
        sample = _GateSample(int(frame_index), anchor, distance, side)
        state = self._tracks.setdefault(tid, _AnchorSpanState())
        if state.history and sample.frame_index <= state.history[-1].frame_index:
            # Canonical alias fusion can deliver the same source frame twice.
            # It supplies no distinct post-side evidence for an override.
            return None
        self._span_proposals.pop(tid, None)
        self._override_qualified.discard(tid)
        self._immediate_candidates.discard(tid)
        state.history.append(sample)

        pending = state.pending
        if pending is not None:
            age = sample.frame_index - pending.end.frame_index
            if age > self.post_confirm_max_gap_frames:
                state.pending = None
                # Expiry closes the original geometry window. Retaining its
                # pre-side samples would reopen the very same old crossing with
                # a newer end timestamp and bypass post_confirm_max_gap_frames.
                state.history = deque([
                    item for item in state.history if item.frame_index > pending.end.frame_index
                ], maxlen=64)
            elif self._review_pending_history(state) != "valid":
                return None
            elif side == -pending.destination_side:
                # V0.5.43 Post-Confirm Closure 8.6: one opposite-side sample can
                # be box jitter immediately after a proven span.  Require a
                # second distinct opposite observation before cancelling.  While
                # this pending lifecycle is active, do not let the same jitter
                # sample open a reverse crossing candidate in the code below.
                return None
            elif side == pending.destination_side:
                # Count only distinct later observations. A near-line sample is
                # enough here because the original span already proved geometry.
                if pending.confirmations >= self.post_confirm_samples:
                    if pending.direction not in state.counted_directions or pending.same_direction_candidate:
                        if not commit:
                            return self._propose_span(tid, pending, sample.frame_index, "post-confirm")
                        state.counted_directions = {pending.direction}
                        state.pending = None
                        self.verified_anchor_span_rescues += 1
                        self.post_confirm_closures += 1
                        if pending.road_edge_rescue:
                            self.road_edge_span_rescues += 1
                        state.last_count_frame = sample.frame_index
                        self._last_crossing_frame[tid] = pending.crossing_frame
                        self._override_qualified.add(tid)
                        if pending.same_direction_candidate:
                            self.same_direction_overrides += 1
                        if pending.approach_span:
                            self.approach_span_rescues += 1
                        return pending.direction, pending.crossing
                    state.pending = None
                return None
            else:
                # Neutral/dead-band observations neither confirm nor invalidate
                # a geometry-proven pending span. Keep waiting without opening a
                # second candidate from the same sample.
                return None

        if side == 0:
            return None
        previous = None
        for candidate in reversed(list(state.history)[:-1]):
            gap = sample.frame_index - candidate.frame_index
            if gap <= 0:
                continue
            if gap > self.history_gap_frames:
                break
            if candidate.side == -side:
                previous = candidate
                break
        if previous is None:
            return None
        direction = "in" if previous.side < 0 < side else "out"
        same_direction_candidate = direction in state.counted_directions
        if same_direction_candidate and sample.frame_index - state.last_count_frame < self.same_direction_min_frames:
            return None
        observed_crossing = observed_gate_crossing(
            list(state.history), previous, sample, a, b, segment_margin=self.segment_margin,
        )
        if observed_crossing is None:
            return None
        crossing_start, crossing_end, crossing = observed_crossing
        move_len = max(observed_path_length(list(state.history), previous, sample), 1e-6)
        normal_ratio = abs(sample.distance - previous.distance) / move_len
        jump_ratio = move_len / max(hypot(width, height), 1.0)
        side_depth_ratio = min(abs(sample.distance), abs(previous.distance)) / scale
        road_ok, road_edge_rescue = self._road_ok(
            previous, sample, crossing, width, height,
            corridor_start=crossing_start, corridor_end=crossing_end,
        )
        if self.road_zone is not None:
            road_ok = road_ok and observed_road_path_ok(
                self.road_zone, list(state.history), previous, sample, width, height,
                self.road_margin_ratio,
            )
        approach_span = False
        crossing_frame = crossing_frame_between(crossing_start, crossing_end, crossing)
        if (
            normal_ratio < self.min_normal_ratio
            or jump_ratio > self.max_jump_ratio
            or side_depth_ratio < self.min_side_distance_ratio
            or not road_ok
        ):
            recovered = self._verified_approach_span(list(state.history), width, height)
            if recovered is None:
                self.rejected_validation += 1
                return None
            previous, crossing, crossing_frame, normal_ratio, side_depth_ratio, road_edge_rescue = recovered
            approach_span = True
            self.approach_span_candidates += 1
        self.verified_candidates += 1

        # An exceptionally clear two-sided span is self-confirming. This is not
        # a global threshold reduction: it is a separate finite-segment audit
        # gate with stricter normal-motion/side-depth/jump/road constraints.
        if (
            not same_direction_candidate
            and not approach_span
            and normal_ratio >= self.immediate_min_normal_ratio
            and side_depth_ratio >= self.immediate_min_side_distance_ratio
            and (sample.frame_index - previous.frame_index) <= 2
        ):
            # V0.5.49 Precision Recovery Closure 9.5: immediate finite-span
            # evidence may ask the primary counter to register the event, but it
            # no longer commits this secondary state before that hand-off.  Keep
            # the proven span pending with one destination confirmation.  If the
            # primary gate accepts it, worker.mark_counted() commits and clears
            # the pending state.  If cooldown/same-direction rejects it, a later
            # destination-side observation can still earn the existing stronger
            # Post-Confirm override instead of turning the rollback into a miss.
            state.pending = _AnchorSpanPending(
                start=previous, end=sample, direction=direction, crossing=crossing,
                crossing_frame=crossing_frame, destination_side=side, confirmations=1,
                frame_width=width, frame_height=height,
                road_edge_rescue=road_edge_rescue, normal_ratio=normal_ratio,
                side_depth_ratio=side_depth_ratio, same_direction_candidate=False,
            )
            if not commit:
                return self._propose_span(tid, state.pending, sample.frame_index, "immediate")
            self._immediate_candidates.add(tid)
            # Keep legacy rescuer-level telemetry semantics: a returned immediate
            # candidate counts as a rescue at this layer. If the primary hand-off
            # rejects it, note_immediate_handoff_result() rolls these counters back
            # before the pending span waits for stronger confirmation.
            self.verified_anchor_span_rescues += 1
            if road_edge_rescue:
                self.road_edge_span_rescues += 1
            self._last_crossing_frame[tid] = crossing_frame
            return direction, crossing

        state.pending = _AnchorSpanPending(
            start=previous, end=sample, direction=direction, crossing=crossing,
            crossing_frame=crossing_frame, destination_side=side, confirmations=1,
            frame_width=width, frame_height=height,
            road_edge_rescue=road_edge_rescue,
            normal_ratio=normal_ratio,
            side_depth_ratio=side_depth_ratio,
            same_direction_candidate=same_direction_candidate,
            approach_span=approach_span,
        )
        return None

    def finalize_lost(
        self, track_id: int, frame_index: int, *, commit: bool = True,
    ) -> tuple[str, Point] | None:
        """Close only a geometry-proven span when the tracker disappears.

        V0.5.47 never invents a crossing from disappearance alone.  A pending
        transaction exists only after a finite counting-line intersection passed
        road, jump, normal-motion and side-depth validation.  Track-loss closure
        additionally requires strong destination depth/normal motion so it can
        safely stand in for the missing post-side sample.
        """
        tid = int(track_id)
        state = self._tracks.get(tid)
        pending = state.pending if state is not None else None
        if pending is None:
            return None
        age = int(frame_index) - pending.end.frame_index
        if age < 1 or age > self.post_confirm_max_gap_frames:
            return None
        if self._review_pending_history(state) != "valid":
            return None
        if pending.approach_span:
            # A measured approach can repair an oblique last box pair only with
            # a distinct later destination observation. Disappearance must not
            # substitute for that confirmation, even when aggregate geometry is
            # strong enough for the ordinary two-point lost-track closure.
            return None
        if pending.opposite_observations:
            # An opposite-side observation followed by disappearance cannot
            # replace the missing destination confirmation, even after a strong
            # original span. Wait for an actual return to the destination.
            return None
        if pending.normal_ratio < self.lost_finalize_min_normal_ratio:
            return None
        if pending.side_depth_ratio < self.lost_finalize_min_side_distance_ratio:
            return None
        if not commit:
            return self._propose_span(tid, pending, pending.end.frame_index, "lost")
        state.pending = None
        state.counted_directions = {pending.direction}
        state.last_count_frame = pending.end.frame_index
        self.verified_anchor_span_rescues += 1
        self.lost_track_finalizations += 1
        if pending.same_direction_candidate:
            self.same_direction_overrides += 1
        if pending.road_edge_rescue:
            self.road_edge_span_rescues += 1
        self._last_crossing_frame[tid] = pending.crossing_frame
        self._override_qualified.add(tid)
        return pending.direction, pending.crossing

    def override_qualified_for(self, track_id: int) -> bool:
        return int(track_id) in self._override_qualified

    def immediate_candidate_for(self, track_id: int) -> bool:
        return int(track_id) in self._immediate_candidates

    def note_immediate_handoff_result(self, track_id: int, accepted: bool) -> None:
        tid = int(track_id)
        if tid not in self._immediate_candidates:
            return
        self._immediate_candidates.discard(tid)
        if tid in self._span_proposals:
            # Proposed spans have not spent identity or rescue telemetry. A
            # rejected primary handoff keeps the geometry available for a later
            # observed confirmation. Accepted telemetry commits in mark_counted.
            if not accepted:
                self.immediate_handoff_rejections += 1
            return
        if accepted:
            # This is an ordinary primary-gate acceptance now, not an override.
            self.immediate_override_qualifications += 1
        else:
            self.immediate_handoff_rejections += 1
            # update() tentatively accounted the returned rescue to preserve the
            # long-standing rescuer telemetry contract. Roll it back when the
            # primary counter rejects the transaction; a later Post-Confirm can
            # add it back only after stronger destination-side evidence.
            if self.verified_anchor_span_rescues > 0:
                self.verified_anchor_span_rescues -= 1
            state = self._tracks.get(tid)
            if (
                state is not None and state.pending is not None
                and state.pending.road_edge_rescue and self.road_edge_span_rescues > 0
            ):
                self.road_edge_span_rescues -= 1

    def consume_override_qualification(self, track_id: int) -> None:
        self._override_qualified.discard(int(track_id))

    def note_cooldown_override(self) -> None:
        self.cooldown_overrides += 1

    def crossing_frame_for(self, track_id: int) -> float | None:
        tid = int(track_id)
        candidate = self._span_proposals.get(tid)
        return candidate.pending.crossing_frame if candidate is not None else self._last_crossing_frame.get(tid)

    def capture_passage_state(self, track_id: int) -> tuple[frozenset[str], int, float | None, _AnchorSpanProposal | None]:
        """Capture only accepted identity/clock for a downstream guard check."""
        tid = int(track_id)
        state = self._tracks.get(tid)
        if state is None:
            return frozenset(), -10_000, None, None
        return (
            frozenset(state.counted_directions), state.last_count_frame,
            self._last_crossing_frame.get(tid), self._committed_proposals.get(tid),
        )

    def restore_passage_state(
        self, track_id: int, snapshot: tuple[frozenset[str], int, float | None, _AnchorSpanProposal | None],
    ) -> None:
        """Roll back identity and discard geometry rejected by a semantic guard.

        Keeping the rejected pending span would let expiry or track-loss closure
        re-offer it. New samples must establish a fresh finite crossing instead.
        """
        tid = int(track_id)
        directions, last_count_frame, crossing_frame, prior_proposal = snapshot
        current_proposal = self._committed_proposals.pop(tid, None)
        if current_proposal is not None and current_proposal is not prior_proposal:
            self._account_span_proposal(current_proposal, -1)
        if prior_proposal is not None:
            self._committed_proposals[tid] = prior_proposal
        state = self._tracks.setdefault(tid, _AnchorSpanState())
        state.counted_directions = set(directions)
        state.last_count_frame = int(last_count_frame)
        state.pending = None
        state.history.clear()
        self._override_qualified.discard(tid)
        self._immediate_candidates.discard(tid)
        self._span_proposals.pop(tid, None)
        if crossing_frame is None:
            self._last_crossing_frame.pop(tid, None)
        else:
            self._last_crossing_frame[tid] = crossing_frame

    def mark_counted(
        self, track_id: int, direction: str, frame_index: int | None = None,
        *, commit_candidate: bool = True,
    ) -> None:
        tid = int(track_id)
        state = self._tracks.setdefault(tid, _AnchorSpanState())
        candidate = self._span_proposals.pop(tid, None)
        clock = state.last_count_frame if frame_index is None else int(frame_index)
        if commit_candidate and candidate is not None and candidate.pending.direction == direction:
            self._account_span_proposal(candidate, 1)
            self._last_crossing_frame[tid] = candidate.pending.crossing_frame
            self._committed_proposals[tid] = candidate
        elif clock != state.last_count_frame or state.counted_directions != {str(direction)}:
            self._committed_proposals.pop(tid, None)
        state.counted_directions = {str(direction)}
        state.pending = None
        if frame_index is not None:
            state.last_count_frame = max(state.last_count_frame, int(frame_index))
        self._override_qualified.discard(int(track_id))
        self._immediate_candidates.discard(int(track_id))
        # Accepted geometry belongs to the completed passage. Keeping the
        # opposite-side tail allows a new alias or a long configured history
        # window to re-propose the same physical span after its cooldown.
        if state.history and (
            frame_index is None or state.history[-1].frame_index >= int(frame_index)
        ):
            state.history = deque([state.history[-1]], maxlen=64)
        else:
            state.history.clear()

    def merge_track(self, source_track_id: int, target_track_id: int) -> None:
        source, target = int(source_track_id), int(target_track_id)
        if source == target:
            return
        src = self._tracks.pop(source, None)
        if src is None:
            return
        dst = self._tracks.get(target)
        source_is_latest = dst is None or src.last_count_frame > dst.last_count_frame
        if dst is None:
            self._tracks[target] = src
        else:
            # One observation per source frame prevents aliases from supplying
            # synthetic confirmation evidence. Prefer the established target
            # observation when both aliases saw the same frame.
            history = {item.frame_index: item for item in src.history}
            history.update({item.frame_index: item for item in dst.history})
            dst.history = deque(sorted(history.values(), key=lambda item: item.frame_index)[-64:], maxlen=64)
            # Follow the primary counter's latest-passage contract. Unioning IN
            # and OUT forever turns a real alternating traversal into a false
            # same-direction candidate and loses the source cooldown clock.
            if src.last_count_frame > dst.last_count_frame:
                dst.counted_directions = set(src.counted_directions)
            elif src.last_count_frame == dst.last_count_frame and not dst.counted_directions:
                dst.counted_directions = set(src.counted_directions)
            dst.last_count_frame = max(dst.last_count_frame, src.last_count_frame)
            valid_pending = [
                item for item in (dst.pending, src.pending)
                if item is not None and item.end.frame_index > dst.last_count_frame
            ]
            dst.pending = max(valid_pending, key=lambda item: item.end.frame_index, default=None)
            if self._revalidate_merged_pending_span(dst):
                self._review_pending_history(dst)
        # Qualification describes a particular candidate transaction; aliases
        # cannot inherit an already-issued override after their state is merged.
        self._override_qualified.discard(source)
        self._override_qualified.discard(target)
        self._immediate_candidates.discard(source)
        self._immediate_candidates.discard(target)
        self._span_proposals.pop(source, None)
        self._span_proposals.pop(target, None)
        source_proposal = self._committed_proposals.pop(source, None)
        if source_is_latest:
            self._committed_proposals.pop(target, None)
        if source_is_latest and source_proposal is not None:
            self._committed_proposals[target] = source_proposal
        source_crossing = self._last_crossing_frame.pop(source, None)
        if source_is_latest:
            if source_crossing is None:
                self._last_crossing_frame.pop(target, None)
            else:
                self._last_crossing_frame[target] = source_crossing


@dataclass(slots=True)
class _HeavyRescueState:
    history: deque[_GateSample] = field(default_factory=lambda: deque(maxlen=128))
    counted_directions: set[str] = field(default_factory=set)
    last_count_frame: int = -10_000


@dataclass(slots=True)
class _CenterCrossingCandidate:
    direction: str
    frame_index: int
    crossing_frame: float
    mode: str


class _CenterPassageRescuer:
    """Keep proposed center geometry separate from accepted passage identity."""

    def capture_passage_state(self, track_id: int) -> tuple[frozenset[str], int, float | None, str | None, bool]:
        tid = int(track_id)
        state = self._tracks.get(tid)
        return (
            frozenset(state.counted_directions) if state is not None else frozenset(),
            state.last_count_frame if state is not None else -10_000,
            self._last_crossing_frame.get(tid), self._last_crossing_mode.get(tid),
            tid in self._last_committed_rescue,
        )

    def restore_passage_state(
        self, track_id: int, snapshot: tuple[frozenset[str], int, float | None, str | None, bool],
    ) -> None:
        tid = int(track_id)
        directions, clock, crossing_frame, mode, was_rescue = snapshot
        state = self._tracks.get(tid)
        if state is not None:
            if state.last_count_frame != clock and tid in self._last_committed_rescue:
                self.rescues = max(0, self.rescues - 1)
            state.counted_directions = set(directions)
            state.last_count_frame = clock
            # A semantic rejection must not be replayed from the rejected chord.
            state.history.clear()
        self._crossing_candidates.pop(tid, None)
        for mapping, value in ((self._last_crossing_frame, crossing_frame), (self._last_crossing_mode, mode)):
            if value is None:
                mapping.pop(tid, None)
            else:
                mapping[tid] = value
        if was_rescue:
            self._last_committed_rescue.add(tid)
        else:
            self._last_committed_rescue.discard(tid)

    def mark_counted(
        self, track_id: int, direction: str, frame_index: int | None = None,
        *, commit_candidate: bool = True,
    ) -> None:
        tid = int(track_id)
        state = self._tracks.get(tid)
        if state is None:
            state = self._state_type()
            self._tracks[tid] = state
        candidate = self._crossing_candidates.pop(tid, None)
        clock = int(frame_index) if frame_index is not None else (
            candidate.frame_index if candidate is not None else state.last_count_frame
        )
        if candidate is None and clock == state.last_count_frame and state.counted_directions == {str(direction)}:
            return
        state.counted_directions = {str(direction)}
        state.last_count_frame = max(state.last_count_frame, clock)
        if commit_candidate and candidate is not None and candidate.direction == direction:
            self._last_crossing_frame[tid] = candidate.crossing_frame
            self._last_crossing_mode[tid] = candidate.mode
            self._last_committed_rescue.add(tid)
            self.rescues += 1
        else:
            self._last_crossing_frame.pop(tid, None)
            self._last_crossing_mode.pop(tid, None)
            self._last_committed_rescue.discard(tid)
        if state.history:
            state.history = deque([state.history[-1]], maxlen=self._history_maxlen)

    def crossing_frame_for(self, track_id: int) -> float | None:
        tid = int(track_id)
        candidate = self._crossing_candidates.get(tid)
        return candidate.crossing_frame if candidate is not None else self._last_crossing_frame.get(tid)

    def crossing_mode_for(self, track_id: int) -> str:
        tid = int(track_id)
        candidate = self._crossing_candidates.get(tid)
        return candidate.mode if candidate is not None else self._last_crossing_mode.get(tid, "rescued")

    def merge_track(self, source_track_id: int, target_track_id: int) -> None:
        source, target = int(source_track_id), int(target_track_id)
        if source == target:
            return
        src = self._tracks.pop(source, None)
        if src is None:
            return
        dst = self._tracks.get(target)
        source_is_latest = dst is None or src.last_count_frame > dst.last_count_frame
        if dst is None:
            self._tracks[target] = src
        else:
            history = {item.frame_index: item for item in src.history}
            history.update({item.frame_index: item for item in dst.history})
            dst.history = deque(sorted(history.values(), key=lambda item: item.frame_index)[-self._history_maxlen:], maxlen=self._history_maxlen)
            if source_is_latest:
                dst.counted_directions = set(src.counted_directions)
            elif src.last_count_frame == dst.last_count_frame and not dst.counted_directions:
                dst.counted_directions = set(src.counted_directions)
            dst.last_count_frame = max(dst.last_count_frame, src.last_count_frame)
        self._crossing_candidates.pop(source, None)
        self._crossing_candidates.pop(target, None)
        for mapping in (self._last_crossing_frame, self._last_crossing_mode):
            value = mapping.pop(source, None)
            if source_is_latest:
                if value is None:
                    mapping.pop(target, None)
                else:
                    mapping[target] = value
        if source_is_latest:
            if source in self._last_committed_rescue:
                self._last_committed_rescue.add(target)
            else:
                self._last_committed_rescue.discard(target)
        self._last_committed_rescue.discard(source)


class HeavyVehicleCrossingRescuer(_CenterPassageRescuer):
    """Secondary center-trajectory gate for large four-wheel vehicles.

    Large vans/trucks can keep a valid track while the motion-leading anchor is
    clipped, jumps at the road-zone boundary, or is briefly lost when the box
    expands near the camera.  This rescuer never replaces the strict primary
    gate.  It only runs for four-wheel tracks after the primary gate returns no
    crossing, and it requires a finite-line center trajectory, road-zone
    corridor, bounded observation gap and strong normal motion.
    """

    def __init__(
        self,
        line: CountingLine,
        road_zone: RoadZone | None = None,
        *,
        history_gap_frames: int = 90,
        dead_band_ratio: float = 0.006,
        segment_margin: float = 0.0,
        min_normal_ratio: float = 0.20,
        min_motion_ratio: float = 0.004,
        road_margin_ratio: float = 0.020,
    ) -> None:
        self.line = line
        self.road_zone = road_zone
        self.history_gap_frames = max(2, int(history_gap_frames))
        self.dead_band_ratio = max(0.0, float(dead_band_ratio))
        self.segment_margin = max(0.0, float(segment_margin))
        self.min_normal_ratio = max(0.0, min(1.0, float(min_normal_ratio)))
        self.min_motion_ratio = max(0.0, float(min_motion_ratio))
        self.road_margin_ratio = max(0.0, float(road_margin_ratio))
        self._tracks: dict[int, _HeavyRescueState] = {}
        self.rescues = 0
        self.rejected_road = 0
        self.rejected_motion = 0
        self.rejected_segment = 0
        self._last_crossing_frame: dict[int, float] = {}
        self._last_crossing_mode: dict[int, str] = {}
        self._crossing_candidates: dict[int, _CenterCrossingCandidate] = {}
        self._last_committed_rescue: set[int] = set()
        self._state_type = _HeavyRescueState
        self._history_maxlen = 128

    def update(
        self,
        track_id: int,
        center: Point,
        frame_width: int,
        frame_height: int,
        frame_index: int,
        *, commit: bool = True,
    ) -> tuple[str, Point] | None:
        a, b = self.line.denormalize(frame_width, frame_height)
        scale = max(1.0, min(frame_width, frame_height))
        dead_band = max(2.0, scale * self.dead_band_ratio)
        distance = signed_distance(center, a, b)
        side = 0 if abs(distance) <= dead_band else (1 if distance > 0 else -1)
        sample = _GateSample(int(frame_index), center, distance, side)
        state = self._tracks.setdefault(int(track_id), _HeavyRescueState())
        if state.history and sample.frame_index <= state.history[-1].frame_index:
            return None
        self._crossing_candidates.pop(int(track_id), None)
        state.history.append(sample)
        if side == 0:
            return None

        previous: _GateSample | None = None
        for candidate in reversed(list(state.history)[:-1]):
            gap = sample.frame_index - candidate.frame_index
            if gap <= 0:
                continue
            if gap > self.history_gap_frames:
                break
            if candidate.side == -side:
                previous = candidate
                break
        if previous is None:
            return None

        direction = "in" if previous.side < 0 < side else "out"
        if direction in state.counted_directions:
            return None

        observed_crossing = observed_gate_crossing(
            list(state.history), previous, sample, a, b, segment_margin=self.segment_margin,
        )
        if observed_crossing is None:
            self.rejected_segment += 1
            return None
        crossing_start, crossing_end, crossing = observed_crossing

        move_len = max(observed_path_length(list(state.history), previous, sample), 1e-6)
        perpendicular = abs(distance - previous.distance)
        if perpendicular < max(2.0, scale * self.min_motion_ratio) or perpendicular / move_len < self.min_normal_ratio:
            self.rejected_motion += 1
            return None

        if self.road_zone is not None:
            local_dx = crossing_end.point[0] - crossing_start.point[0]
            local_dy = crossing_end.point[1] - crossing_start.point[1]
            local_len = max(hypot(local_dx, local_dy), 1e-6)
            ux, uy = local_dx / local_len, local_dy / local_len
            probe = max(3.0, scale * 0.018)
            before = (crossing[0] - ux * probe, crossing[1] - uy * probe)
            after = (crossing[0] + ux * probe, crossing[1] + uy * probe)
            centers_ok = (
                self.road_zone.contains_with_margin(previous.point, frame_width, frame_height, self.road_margin_ratio)
                and self.road_zone.contains_with_margin(center, frame_width, frame_height, self.road_margin_ratio)
                and observed_road_path_ok(
                    self.road_zone, list(state.history), previous, sample, frame_width, frame_height,
                    self.road_margin_ratio,
                )
            )
            corridor_ok = (
                self.road_zone.contains(crossing, frame_width, frame_height)
                and self.road_zone.contains(before, frame_width, frame_height)
                and self.road_zone.contains(after, frame_width, frame_height)
            )
            if not (centers_ok and corridor_ok):
                self.rejected_road += 1
                return None

        self._crossing_candidates[int(track_id)] = _CenterCrossingCandidate(
            direction, sample.frame_index, crossing_frame_between(crossing_start, crossing_end, crossing), "rescued",
        )
        if commit:
            self.mark_counted(track_id, direction, frame_index)
        return direction, crossing


@dataclass(slots=True)
class _TwoWheelRescueState:
    history: deque[_GateSample] = field(default_factory=lambda: deque(maxlen=64))
    counted_directions: set[str] = field(default_factory=set)
    last_count_frame: int = -10_000


class TwoWheelCenterCrossingRescuer(_CenterPassageRescuer):
    """Conservative center-trajectory rescue for fragmented two-wheel tracks.

    V0.5.34 keeps the strict motion-leading-anchor gate as the primary source of
    truth.  This secondary gate is evaluated only for established bicycle /
    motorcycle tracks after the primary gate returns no crossing.  It targets a
    failure mode visible in the GT-149 benchmark: a narrow front-wheel box or a
    one-frame rider/vehicle box change can keep the leading anchor on one side of
    the line even though the *vehicle centre trajectory* cleanly crosses it.

    The rescue is deliberately much stricter than the heavy-vehicle center gate:
    short history, finite-segment edge margin, strong normal motion, bounded jump,
    road-corridor validation and minimum depth on both sides.  It therefore does
    not turn ordinary line-adjacent jitter into a crossing.
    """

    def __init__(
        self,
        line: CountingLine,
        road_zone: RoadZone | None = None,
        *,
        history_gap_frames: int = 12,
        interpolation_gap_frames: int = 3,
        dead_band_ratio: float = 0.006,
        segment_margin: float = 0.0,
        segment_edge_ratio: float = 0.04,
        min_normal_ratio: float = 0.42,
        min_motion_ratio: float = 0.005,
        max_jump_ratio: float = 0.10,
        min_side_distance_ratio: float = 0.006,
        road_margin_ratio: float = 0.008,
    ) -> None:
        self.line = line
        self.road_zone = road_zone
        self.history_gap_frames = max(2, int(history_gap_frames))
        self.interpolation_gap_frames = max(1, min(self.history_gap_frames, int(interpolation_gap_frames)))
        self.dead_band_ratio = max(0.0, float(dead_band_ratio))
        self.segment_margin = max(0.0, float(segment_margin))
        self.segment_edge_ratio = max(0.0, min(0.30, float(segment_edge_ratio)))
        self.min_normal_ratio = max(0.0, min(1.0, float(min_normal_ratio)))
        self.min_motion_ratio = max(0.0, float(min_motion_ratio))
        self.max_jump_ratio = max(0.0, float(max_jump_ratio))
        self.min_side_distance_ratio = max(0.0, float(min_side_distance_ratio))
        self.road_margin_ratio = max(0.0, float(road_margin_ratio))
        self._tracks: dict[int, _TwoWheelRescueState] = {}
        self.rescues = 0
        self.rejected_segment = 0
        self.rejected_motion = 0
        self.rejected_jump = 0
        self.rejected_road = 0
        self._last_crossing_frame: dict[int, float] = {}
        self._last_crossing_mode: dict[int, str] = {}
        self._crossing_candidates: dict[int, _CenterCrossingCandidate] = {}
        self._last_committed_rescue: set[int] = set()
        self._state_type = _TwoWheelRescueState
        self._history_maxlen = 64

    @staticmethod
    def _segment_fraction(point: Point, a: Point, b: Point) -> float:
        abx = b[0] - a[0]
        aby = b[1] - a[1]
        denom = abx * abx + aby * aby
        if denom <= 1e-9:
            return 0.5
        return ((point[0] - a[0]) * abx + (point[1] - a[1]) * aby) / denom

    def update(
        self,
        track_id: int,
        center: Point,
        frame_width: int,
        frame_height: int,
        frame_index: int,
        *, commit: bool = True,
    ) -> tuple[str, Point] | None:
        a, b = self.line.denormalize(frame_width, frame_height)
        scale = max(1.0, min(frame_width, frame_height))
        diagonal = max(hypot(frame_width, frame_height), 1.0)
        dead_band = max(2.0, scale * self.dead_band_ratio)
        distance = signed_distance(center, a, b)
        side = 0 if abs(distance) <= dead_band else (1 if distance > 0 else -1)
        sample = _GateSample(int(frame_index), center, distance, side)
        state = self._tracks.setdefault(int(track_id), _TwoWheelRescueState())
        if state.history and sample.frame_index <= state.history[-1].frame_index:
            return None
        self._crossing_candidates.pop(int(track_id), None)
        state.history.append(sample)
        if side == 0:
            return None

        previous: _GateSample | None = None
        for candidate in reversed(list(state.history)[:-1]):
            gap = sample.frame_index - candidate.frame_index
            if gap <= 0:
                continue
            if gap > self.history_gap_frames:
                break
            if candidate.side == -side:
                previous = candidate
                break
        if previous is None:
            return None

        direction = "in" if previous.side < 0 < side else "out"
        if direction in state.counted_directions:
            return None

        observed_crossing = observed_gate_crossing(
            list(state.history), previous, sample, a, b, segment_margin=self.segment_margin,
        )
        if observed_crossing is None:
            self.rejected_segment += 1
            return None
        crossing_start, crossing_end, crossing = observed_crossing
        fraction = self._segment_fraction(crossing, a, b)
        if fraction < self.segment_edge_ratio or fraction > 1.0 - self.segment_edge_ratio:
            self.rejected_segment += 1
            return None

        move_len = max(observed_path_length(list(state.history), previous, sample), 1e-6)
        perpendicular = abs(distance - previous.distance)
        normal_ratio = perpendicular / move_len
        jump_ratio = move_len / diagonal
        side_depth_ratio = min(abs(distance), abs(previous.distance)) / scale
        if jump_ratio > self.max_jump_ratio > 0.0:
            self.rejected_jump += 1
            return None
        if (
            perpendicular < max(2.0, scale * self.min_motion_ratio)
            or normal_ratio < self.min_normal_ratio
            or side_depth_ratio < self.min_side_distance_ratio
        ):
            self.rejected_motion += 1
            return None

        if self.road_zone is not None:
            local_dx = crossing_end.point[0] - crossing_start.point[0]
            local_dy = crossing_end.point[1] - crossing_start.point[1]
            local_len = max(hypot(local_dx, local_dy), 1e-6)
            ux, uy = local_dx / local_len, local_dy / local_len
            probe = max(3.0, scale * 0.015)
            before = (crossing[0] - ux * probe, crossing[1] - uy * probe)
            after = (crossing[0] + ux * probe, crossing[1] + uy * probe)
            centers_ok = (
                self.road_zone.contains_with_margin(previous.point, frame_width, frame_height, self.road_margin_ratio)
                and self.road_zone.contains_with_margin(center, frame_width, frame_height, self.road_margin_ratio)
                and observed_road_path_ok(
                    self.road_zone, list(state.history), previous, sample, frame_width, frame_height,
                    self.road_margin_ratio,
                )
            )
            corridor_ok = (
                self.road_zone.contains(crossing, frame_width, frame_height)
                and self.road_zone.contains(before, frame_width, frame_height)
                and self.road_zone.contains(after, frame_width, frame_height)
            )
            if not (centers_ok and corridor_ok):
                self.rejected_road += 1
                return None

        gap = sample.frame_index - previous.frame_index
        mode = "interpolated" if gap <= self.interpolation_gap_frames else "rescued"
        self._crossing_candidates[int(track_id)] = _CenterCrossingCandidate(
            direction, sample.frame_index, crossing_frame_between(crossing_start, crossing_end, crossing), mode,
        )
        if commit:
            self.mark_counted(track_id, direction, frame_index)
        return direction, crossing


class LineCrossingCounter:
    """Strict finite-line, trajectory-based bidirectional virtual gate.

    The counter keeps a bounded trajectory history so fast vehicles can still be
    counted when detector/tracker observations are missing for several frames.
    A crossing is accepted only when the trajectory intersects the *visible*
    counting segment, not an infinite line, and when enough motion is normal to
    the gate. This suppresses roadside/sidewalk traffic and line-parallel jitter.
    """

    def __init__(
        self,
        line: CountingLine,
        road_zone: RoadZone | None = None,
        segment_margin: float = 0.0,
        dead_band_ratio: float = 0.006,
        rearm_distance_ratio: float = 0.028,
        history_gap_frames: int = 45,
        interpolation_gap_frames: int = 3,
        min_perpendicular_ratio: float = 0.10,
        min_crossing_motion_ratio: float = 0.004,
        startup_grace_frames: int = 0,
        side_confirm_samples: int = 1,
        crossing_cooldown_frames: int = 0,
        passage_rearm_min_frames: int = 8,
        road_anchor_margin_ratio: float = 0.0,
        fast_confirm_distance_ratio: float = 0.0,
        adaptive_cooldown: bool = False,
        cooldown_release_ratio: float = 0.0,
        rescue_min_normal_ratio: float = 0.0,
        rescue_max_jump_ratio: float = 0.0,
        rescue_min_side_distance_ratio: float = 0.0,
        rescue_strict_gap_frames: int = 0,
        rescue_strict_min_normal_ratio: float = 0.0,
        rescue_strict_max_jump_ratio: float = 0.0,
        rescue_strict_min_side_distance_ratio: float = 0.0,
        lineage_rescue_guard: bool = False,
        lineage_rescue_min_normal_ratio: float = 0.46,
        lineage_rescue_max_jump_ratio: float = 0.18,
        lineage_rescue_min_side_distance_ratio: float = 0.014,
        lineage_rescue_confirm_samples: int = 2,
        bracket_confirm: bool = False,
        bracket_confirm_min_normal_ratio: float = 0.55,
        bracket_confirm_max_gap_frames: int = 2,
        late_geometry_confirm: bool = False,
        late_geometry_confirm_min_normal_ratio: float = 0.48,
        late_geometry_confirm_max_jump_ratio: float = 0.08,
        late_geometry_confirm_min_side_distance_ratio: float = 0.008,
        late_geometry_confirm_max_gap_frames: int = 3,
        origin_rescue_frames: int = 0,
        origin_rescue_distance_ratio: float = 0.06,
        origin_rescue_min_normal_ratio: float = 0.32,
    ) -> None:
        self.line = line
        self.road_zone = road_zone
        if self.road_zone is not None:
            self.road_zone.validate()
        self.segment_margin = max(0.0, float(segment_margin))
        self.dead_band_ratio = max(0.0, float(dead_band_ratio))
        self.rearm_distance_ratio = max(self.dead_band_ratio, float(rearm_distance_ratio))
        self.history_gap_frames = max(2, int(history_gap_frames))
        self.interpolation_gap_frames = max(1, min(self.history_gap_frames, int(interpolation_gap_frames)))
        self.min_perpendicular_ratio = max(0.0, min(1.0, float(min_perpendicular_ratio)))
        self.min_crossing_motion_ratio = max(0.0, float(min_crossing_motion_ratio))
        self.startup_grace_frames = max(0, int(startup_grace_frames))
        self.side_confirm_samples = max(1, int(side_confirm_samples))
        self.crossing_cooldown_frames = max(0, int(crossing_cooldown_frames))
        self.passage_rearm_min_frames = max(1, int(passage_rearm_min_frames))
        self.road_anchor_margin_ratio = max(0.0, float(road_anchor_margin_ratio))
        self.fast_confirm_distance_ratio = max(0.0, float(fast_confirm_distance_ratio))
        self.adaptive_cooldown = bool(adaptive_cooldown)
        self.cooldown_release_ratio = max(0.0, float(cooldown_release_ratio))
        self.rescue_min_normal_ratio = max(0.0, min(1.0, float(rescue_min_normal_ratio)))
        self.rescue_max_jump_ratio = max(0.0, float(rescue_max_jump_ratio))
        self.rescue_min_side_distance_ratio = max(0.0, float(rescue_min_side_distance_ratio))
        self.rescue_strict_gap_frames = max(0, int(rescue_strict_gap_frames))
        self.rescue_strict_min_normal_ratio = max(0.0, min(1.0, float(rescue_strict_min_normal_ratio)))
        self.rescue_strict_max_jump_ratio = max(0.0, float(rescue_strict_max_jump_ratio))
        self.rescue_strict_min_side_distance_ratio = max(0.0, float(rescue_strict_min_side_distance_ratio))
        self.lineage_rescue_guard = bool(lineage_rescue_guard)
        self.lineage_rescue_min_normal_ratio = max(0.0, min(1.0, float(lineage_rescue_min_normal_ratio)))
        self.lineage_rescue_max_jump_ratio = max(0.0, float(lineage_rescue_max_jump_ratio))
        self.lineage_rescue_min_side_distance_ratio = max(0.0, float(lineage_rescue_min_side_distance_ratio))
        self.lineage_rescue_confirm_samples = max(1, int(lineage_rescue_confirm_samples))
        self.bracket_confirm = bool(bracket_confirm)
        self.bracket_confirm_min_normal_ratio = max(0.0, min(1.0, float(bracket_confirm_min_normal_ratio)))
        self.bracket_confirm_max_gap_frames = max(1, int(bracket_confirm_max_gap_frames))
        self.late_geometry_confirm = bool(late_geometry_confirm)
        self.late_geometry_confirm_min_normal_ratio = max(0.0, min(1.0, float(late_geometry_confirm_min_normal_ratio)))
        self.late_geometry_confirm_max_jump_ratio = max(0.0, float(late_geometry_confirm_max_jump_ratio))
        self.late_geometry_confirm_min_side_distance_ratio = max(0.0, float(late_geometry_confirm_min_side_distance_ratio))
        self.late_geometry_confirm_max_gap_frames = max(1, int(late_geometry_confirm_max_gap_frames))
        self.origin_rescue_frames = max(0, int(origin_rescue_frames))
        self.origin_rescue_distance_ratio = max(0.0, float(origin_rescue_distance_ratio))
        self.origin_rescue_min_normal_ratio = max(0.0, min(1.0, float(origin_rescue_min_normal_ratio)))
        self._tracks: dict[int, _TrackGateState] = {}
        self.in_count = 0
        self.out_count = 0
        self.direct_crossings = 0
        self.interpolated_crossings = 0
        self.rescued_crossings = 0
        self._last_crossing_mode: dict[int, str] = {}
        self._last_origin_rescue: set[int] = set()
        self.rejected_outside_segment = 0
        self.rejected_outside_road = 0
        self.rejected_unconfirmed_side = 0
        self.rejected_cooldown = 0
        self.road_edge_rescues = 0
        self.fast_confirm_rescues = 0
        self.bracket_confirm_rescues = 0
        self.late_geometry_confirms = 0
        self.origin_rescues = 0
        self.rejected_rescue_validation = 0
        self.rejected_long_gap_rescue = 0
        self.rejected_lineage_rescue = 0
        self.adaptive_cooldown_releases = 0
        self.passage_cycle_rearms = 0
        self.rejected_same_direction_cycle = 0
        self.verified_same_direction_overrides = 0
        self.verified_cooldown_overrides = 0
        self._last_crossing_point: dict[int, Point] = {}
        self._last_crossing_frame: dict[int, float] = {}
        self._last_external_reject_reason: dict[int, str] = {}
        self._passage_rollbacks: dict[int, _PassageRollback] = {}

    def _capture_passage_rollback(
        self, track_id: int, direction: str, frame_index: int, state: _TrackGateState,
        *, same_direction_override: bool = False, cooldown_override: bool = False,
    ) -> None:
        tid = int(track_id)
        self._passage_rollbacks[tid] = _PassageRollback(
            accepted_direction=direction,
            accepted_frame=int(frame_index),
            counted_directions=set(state.counted_directions),
            last_count_frame=state.last_count_frame,
            armed=state.armed,
            max_abs_distance_since_count=state.max_abs_distance_since_count,
            crossing_point=self._last_crossing_point.get(tid),
            crossing_frame=self._last_crossing_frame.get(tid),
            crossing_mode=self._last_crossing_mode.get(tid),
            origin_rescue=tid in self._last_origin_rescue,
            same_direction_override=same_direction_override,
            cooldown_override=cooldown_override,
        )

    def update(
        self,
        track_id: int,
        anchor: Point,
        frame_width: int,
        frame_height: int,
        frame_index: int | None = None,
        origin_probe: Point | None = None,
        lineage_size: int = 1,
    ) -> str | None:
        if frame_index is None:
            state_existing = self._tracks.get(track_id)
            frame_index = (state_existing.history[-1].frame_index + 1) if state_existing and state_existing.history else 1

        a, b = self.line.denormalize(frame_width, frame_height)
        distance = signed_distance(anchor, a, b)
        scale = max(1.0, min(frame_width, frame_height))
        dead_band = max(2.0, scale * self.dead_band_ratio)
        rearm_distance = max(dead_band * 2.0, scale * self.rearm_distance_ratio)
        side = 0 if abs(distance) <= dead_band else (1 if distance > 0 else -1)

        state = self._tracks.setdefault(int(track_id), _TrackGateState())
        sample = _GateSample(int(frame_index), anchor, distance, side)
        if state.history and sample.frame_index <= state.history[-1].frame_index:
            # Aliases observed in the same source frame cannot supply a second
            # destination observation or re-arm an accepted passage.
            return None
        if origin_probe is not None:
            origin_distance = signed_distance(origin_probe, a, b)
            origin_side = 0 if abs(origin_distance) <= dead_band else (1 if origin_distance > 0 else -1)
            state.origin_history.append(_GateSample(int(frame_index), origin_probe, origin_distance, origin_side))
        if state.first_frame is None:
            state.first_frame = sample.frame_index
        state.total_samples += 1
        if side != 0:
            if side == state.last_nonzero_side:
                state.side_streak += 1
            else:
                state.last_nonzero_side = side
                state.side_streak = 1

        if state.last_count_frame > -10_000:
            state.max_abs_distance_since_count = max(state.max_abs_distance_since_count, abs(distance))

        if not state.armed:
            state.history.append(sample)
            if abs(distance) >= rearm_distance:
                # V0.5.46 separates geometric re-arm from passage identity.
                # Geometry may watch for a return as soon as the vehicle has
                # clearly left the dead band, while counted_directions keeps the
                # last accepted direction until an opposite traversal is proven.
                # Cooldown/adaptive release below still decides whether that
                # opposite return is temporally plausible.
                state.armed = True
                self.passage_cycle_rearms += 1
                state.history = deque([sample], maxlen=48)
            return None

        state.history.append(sample)
        if sample.frame_index <= self.startup_grace_frames:
            # Never replay a crossing that happened during startup once the
            # grace window expires. Keep only the most recent side sample.
            state.history = deque([sample], maxlen=48)
            return None
        if side == 0:
            return None

        previous: _GateSample | None = None
        for candidate in reversed(list(state.history)[:-1]):
            gap = sample.frame_index - candidate.frame_index
            if gap <= 0:
                continue
            if gap > self.history_gap_frames:
                break
            if candidate.side == -side:
                previous = candidate
                break

        origin_candidate = False
        if previous is None and self.origin_rescue_frames > 0 and sample.frame_index <= self.origin_rescue_frames:
            origin_samples = list(state.origin_history)
            if len(origin_samples) >= 2:
                first_origin = origin_samples[0]
                current_origin = origin_samples[-1]
                origin_band = max(dead_band * 2.0, scale * self.origin_rescue_distance_ratio)
                move_x_origin = current_origin.point[0] - first_origin.point[0]
                move_y_origin = current_origin.point[1] - first_origin.point[1]
                move_len_origin = max(observed_path_length(origin_samples, first_origin, current_origin), 1e-6)
                delta_origin = current_origin.distance - first_origin.distance
                current_origin_side = current_origin.side
                moving_away = (
                    current_origin_side != 0
                    and delta_origin * current_origin_side > 0
                    and abs(current_origin.distance) >= abs(first_origin.distance) + dead_band * 0.35
                )
                normal_ratio_origin = abs(delta_origin) / move_len_origin
                if (
                    abs(first_origin.distance) <= origin_band
                    and moving_away
                    and normal_ratio_origin >= self.origin_rescue_min_normal_ratio
                ):
                    # The clip can begin while a vehicle already straddles the
                    # gate. Extrapolate the first centre point backward by the
                    # observed motion and require that the inferred point lands
                    # on the opposite side of the finite counting segment. This
                    # recovers a genuine frame-0 crossing without globally
                    # weakening the normal opposite-side history requirement.
                    required_shift = abs(first_origin.distance) + dead_band * 1.5
                    factor = max(1.0, min(3.0, required_shift / max(abs(delta_origin), 1e-6)))
                    predicted = (
                        first_origin.point[0] - move_x_origin * factor,
                        first_origin.point[1] - move_y_origin * factor,
                    )
                    predicted_distance = signed_distance(predicted, a, b)
                    predicted_side = 0 if abs(predicted_distance) <= dead_band else (1 if predicted_distance > 0 else -1)
                    inferred_crossing = segment_crossing_point(
                        predicted, current_origin.point, a, b, segment_margin=self.segment_margin
                    )
                    if predicted_side == -current_origin_side and inferred_crossing is not None:
                        previous = _GateSample(
                            max(0, current_origin.frame_index - 1), predicted, predicted_distance, predicted_side
                        )
                        sample = current_origin
                        anchor = current_origin.point
                        distance = current_origin.distance
                        side = current_origin.side
                        origin_candidate = True

        if previous is None:
            return None

        observation_gap = sample.frame_index - previous.frame_index
        # Crossing Engine 7.0: direct/interpolated crossings must be confirmed
        # by a second observation on the destination side. Sparse long-gap
        # rescues stay eligible so fast vehicles are not lost merely because the
        # detector skipped frames.
        strong_destination = (
            self.fast_confirm_distance_ratio > 0.0
            and abs(distance) >= max(dead_band * 2.2, scale * self.fast_confirm_distance_ratio)
        )
        # Crossing Engine 7.2: if two nearby observations themselves form a
        # strong finite-segment bracket, requiring yet another destination-side
        # sample can lose a real vehicle that disappears immediately after the
        # line. This rescue is deliberately narrow: short gap, visible-segment
        # intersection and strongly normal motion. Road-zone and motion guards
        # below still have to pass before the crossing is accepted.
        bracket_destination = False
        if (
            self.bracket_confirm
            and observation_gap <= self.bracket_confirm_max_gap_frames
            and observation_gap <= self.interpolation_gap_frames
        ):
            quick_crossing = segment_crossing_point(
                previous.point, anchor, a, b, segment_margin=self.segment_margin
            )
            quick_len = max(observed_path_length(list(state.history), previous, sample), 1e-6)
            quick_normal_ratio = abs(distance - previous.distance) / quick_len
            bracket_destination = (
                quick_crossing is not None
                and quick_normal_ratio >= self.bracket_confirm_min_normal_ratio
            )
        pending_confirmation_reject = False
        if (
            not origin_candidate
            and observation_gap <= self.interpolation_gap_frames
            and state.side_streak < self.side_confirm_samples
        ):
            if strong_destination:
                self.fast_confirm_rescues += 1
            elif bracket_destination:
                self.bracket_confirm_rescues += 1
            else:
                # V0.5.50 Geometry-Backed Late Confirm 9.6: do not reject the
                # one-sample destination span before the finite segment, road
                # corridor and motion geometry have been checked.  Most weak
                # jitter still fails below; only a short, bounded, two-sided
                # trajectory can earn a late confirmation.
                pending_confirmation_reject = True
        if sample.frame_index - state.last_count_frame < self.crossing_cooldown_frames:
            elapsed_since_count = sample.frame_index - state.last_count_frame
            release_distance = scale * self.cooldown_release_ratio
            can_release = (
                self.adaptive_cooldown
                and release_distance > 0.0
                and elapsed_since_count >= self.passage_rearm_min_frames
                and state.max_abs_distance_since_count >= release_distance
            )
            if can_release:
                self.adaptive_cooldown_releases += 1
            else:
                self.rejected_cooldown += 1
                return None

        # Crossing Engine 6.0: use the most local pair of observations that
        # actually brackets the line. Older builds intersected the last stable
        # opposite-side sample directly with the current point, so normal
        # dead-band samples near the line looked like a long "rescue" jump.
        history = list(state.history)
        previous_index = max(0, len(history) - 2)
        for index in range(len(history) - 2, -1, -1):
            if history[index] is previous:
                previous_index = index
                break

        crossing_start = previous
        crossing_end = sample
        if not origin_candidate:
            observed_crossing = observed_gate_crossing(
                history, previous, sample, a, b, segment_margin=self.segment_margin,
            )
            if observed_crossing is None:
                self.rejected_outside_segment += 1
                return None
            crossing_start, crossing_end, crossing = observed_crossing
        else:
            crossing = segment_crossing_point(
                previous.point,
                anchor,
                a,
                b,
                segment_margin=self.segment_margin,
            )
        if crossing is None:
            self.rejected_outside_segment += 1
            return None

        # Origin rescue has a synthetic pre-side anchor. Its measured origin
        # trajectory was checked above; ordinary crossings use every observed
        # point in their own stable-side window.
        confirm_move_len = max(
            hypot(anchor[0] - previous.point[0], anchor[1] - previous.point[1])
            if origin_candidate else observed_path_length(history, previous, sample),
            1e-6,
        )
        confirm_diagonal = max(hypot(frame_width, frame_height), 1.0)
        confirm_normal_ratio = abs(distance - previous.distance) / confirm_move_len
        confirm_jump_ratio = confirm_move_len / confirm_diagonal
        confirm_side_depth_ratio = min(abs(distance), abs(previous.distance)) / scale

        # Crossing Engine 7.1: long-gap rescues are useful for fast vehicles but
        # are also the riskiest source of over-count. Validate the jump before
        # accepting it. Defaults are disabled for backwards-compatible unit
        # tests; runtime enables conservative thresholds through environment.
        if observation_gap > self.interpolation_gap_frames:
            normal_ratio = confirm_normal_ratio
            jump_ratio = confirm_jump_ratio
            side_depth_ratio = confirm_side_depth_ratio
            rescue_invalid = (
                (self.rescue_min_normal_ratio > 0.0 and normal_ratio < self.rescue_min_normal_ratio)
                or (self.rescue_max_jump_ratio > 0.0 and jump_ratio > self.rescue_max_jump_ratio)
                or (self.rescue_min_side_distance_ratio > 0.0 and side_depth_ratio < self.rescue_min_side_distance_ratio)
            )
            if rescue_invalid:
                self.rejected_rescue_validation += 1
                return None

            # V0.5.45 False Positive Closure 9.1: the longest history bridges
            # are disproportionately represented in unmatched benchmark events.
            # Keep ordinary rescue thresholds unchanged, but make only the far
            # tail prove stronger normal motion, bounded jump and side depth.
            # Defaults are disabled for unit compatibility; production runtime
            # enables the stricter tail through environment variables.
            if self.rescue_strict_gap_frames > 0 and observation_gap > self.rescue_strict_gap_frames:
                strict_invalid = (
                    (self.rescue_strict_min_normal_ratio > 0.0 and normal_ratio < self.rescue_strict_min_normal_ratio)
                    or (self.rescue_strict_max_jump_ratio > 0.0 and jump_ratio > self.rescue_strict_max_jump_ratio)
                    or (
                        self.rescue_strict_min_side_distance_ratio > 0.0
                        and side_depth_ratio < self.rescue_strict_min_side_distance_ratio
                    )
                )
                if strict_invalid:
                    self.rejected_long_gap_rescue += 1
                    self.rejected_rescue_validation += 1
                    return None

            # V0.5.49: when a long-gap secondary crossing also spans multiple
            # raw ByteTrack IDs, require either a second destination-side sample
            # or unusually strong two-sided geometry.  This targets rescue-tail
            # shadows caused by an ID switch without weakening DIRECT traffic or
            # ordinary single-ID gap rescue.  A first weak sample is held rather
            # than deleting history, so the next destination-side frame can still
            # confirm the real crossing.
            if self.lineage_rescue_guard and int(lineage_size) > 1:
                lineage_strong = (
                    normal_ratio >= self.lineage_rescue_min_normal_ratio
                    and (self.lineage_rescue_max_jump_ratio <= 0.0 or jump_ratio <= self.lineage_rescue_max_jump_ratio)
                    and side_depth_ratio >= self.lineage_rescue_min_side_distance_ratio
                )
                if state.side_streak < self.lineage_rescue_confirm_samples and not lineage_strong:
                    self.rejected_lineage_rescue += 1
                    self.rejected_rescue_validation += 1
                    return None

        if self.road_zone is not None:
            move_x_zone = crossing_end.point[0] - crossing_start.point[0]
            move_y_zone = crossing_end.point[1] - crossing_start.point[1]
            move_len_zone = max(hypot(move_x_zone, move_y_zone), 1e-6)
            ux, uy = move_x_zone / move_len_zone, move_y_zone / move_len_zone
            zone_probe_ratio = max(0.0, float(os.getenv("AI_ROAD_ZONE_PROBE_RATIO", "0.018")))
            zone_probe = max(3.0, min(frame_width, frame_height) * zone_probe_ratio)
            before = (crossing[0] - ux * zone_probe, crossing[1] - uy * zone_probe)
            after = (crossing[0] + ux * zone_probe, crossing[1] + uy * zone_probe)
            # V0.5.12 hard guard: both observed anchors must themselves be in the
            # drivable polygon. A long diagonal jump from sidewalk to sidewalk is
            # therefore never accepted merely because its segment passes through
            # the green polygon around the yellow gate.
            previous_strict = self.road_zone.contains(previous.point, frame_width, frame_height)
            anchor_strict = self.road_zone.contains(anchor, frame_width, frame_height)
            anchors_ok = (
                self.road_zone.contains_with_margin(previous.point, frame_width, frame_height, self.road_anchor_margin_ratio)
                and self.road_zone.contains_with_margin(anchor, frame_width, frame_height, self.road_anchor_margin_ratio)
                and (
                    origin_candidate or observed_road_path_ok(
                        self.road_zone, history, previous, sample, frame_width, frame_height,
                        self.road_anchor_margin_ratio,
                    )
                )
            )
            corridor_ok = (
                self.road_zone.contains(crossing, frame_width, frame_height)
                and self.road_zone.contains(before, frame_width, frame_height)
                and self.road_zone.contains(after, frame_width, frame_height)
            )
            if not (anchors_ok and corridor_ok):
                self.rejected_outside_road += 1
                return None
            if not (previous_strict and anchor_strict):
                self.road_edge_rescues += 1

        if pending_confirmation_reject:
            late_confirm_ok = (
                self.late_geometry_confirm
                and observation_gap <= self.late_geometry_confirm_max_gap_frames
                and confirm_normal_ratio >= self.late_geometry_confirm_min_normal_ratio
                and (
                    self.late_geometry_confirm_max_jump_ratio <= 0.0
                    or confirm_jump_ratio <= self.late_geometry_confirm_max_jump_ratio
                )
                and confirm_side_depth_ratio >= self.late_geometry_confirm_min_side_distance_ratio
            )
            if late_confirm_ok:
                self.late_geometry_confirms += 1
            else:
                self.rejected_unconfirmed_side += 1
                return None

        perpendicular = abs(distance - previous.distance)
        min_motion = max(2.0, scale * self.min_crossing_motion_ratio)
        if perpendicular < min_motion:
            return None
        if perpendicular / confirm_move_len < self.min_perpendicular_ratio:
            return None

        direction = "in" if previous.side < 0 < side else "out"
        if direction in state.counted_directions:
            self.rejected_same_direction_cycle += 1
            return None

        self._capture_passage_rollback(int(track_id), direction, sample.frame_index, state)

        # Keep only the most recently accepted direction.  The opposite
        # traversal is the proof that a later same-direction passage is a new
        # cycle, so alternating IN→OUT→IN remains countable without ever using
        # a lifetime unique tracking ID.
        state.counted_directions = {direction}
        state.armed = False
        state.last_count_frame = sample.frame_index
        state.max_abs_distance_since_count = 0.0
        self._last_crossing_point[int(track_id)] = crossing
        self._last_crossing_frame[int(track_id)] = crossing_frame_between(crossing_start, crossing_end, crossing)

        # Crossing quality is classified from actual observation continuity.
        # DIRECT      = consecutive observations bracket the gate.
        # INTERPOLATED= continuous/near-continuous track with dead-band samples
        #               or only a very small observation gap.
        # RESCUED     = a genuine longer detector/tracker gap bridged by history.
        crossing_window = history[previous_index:]
        frame_gaps = [
            right.frame_index - left.frame_index
            for left, right in zip(crossing_window, crossing_window[1:])
            if right.frame_index > left.frame_index
        ]
        max_observation_gap = max(frame_gaps, default=1)
        if origin_candidate:
            crossing_mode = "direct"
            self.direct_crossings += 1
            self.origin_rescues += 1
            self._last_origin_rescue.add(int(track_id))
        elif len(crossing_window) == 2 and max_observation_gap <= 1:
            self._last_origin_rescue.discard(int(track_id))
            crossing_mode = "direct"
            self.direct_crossings += 1
        elif max_observation_gap <= self.interpolation_gap_frames:
            self._last_origin_rescue.discard(int(track_id))
            crossing_mode = "interpolated"
            self.interpolated_crossings += 1
        else:
            self._last_origin_rescue.discard(int(track_id))
            crossing_mode = "rescued"
            self.rescued_crossings += 1
        self._last_crossing_mode[int(track_id)] = crossing_mode
        state.history = deque([sample], maxlen=48)

        if direction == "in":
            self.in_count += 1
        else:
            self.out_count += 1
        return direction


    def register_external_crossing(
        self,
        track_id: int,
        direction: str,
        frame_index: int,
        crossing_point: Point,
        *,
        mode: str = "rescued",
        crossing_frame: float | None = None,
        verified_anchor_span: bool = False,
    ) -> bool:
        """Register a crossing proven by a stricter secondary gate.

        V0.5.29 uses this only for the heavy-vehicle center rescue.  Updating the
        primary track state here is essential: the normal gate must know the
        direction was already counted so a later anchor recovery cannot create a
        duplicate event.
        """
        tid = int(track_id)
        direction = str(direction)
        if direction not in {"in", "out"}:
            return False
        state = self._tracks.setdefault(tid, _TrackGateState())
        same_direction_blocked = direction in state.counted_directions
        cooldown_blocked = int(frame_index) - state.last_count_frame < self.crossing_cooldown_frames
        self._last_external_reject_reason.pop(tid, None)
        if crossing_frame is not None:
            source_crossing = float(crossing_frame)
            prior_crossing = self._last_crossing_frame.get(tid)
            if (
                not isfinite(source_crossing) or source_crossing > int(frame_index)
                or (prior_crossing is not None and source_crossing <= prior_crossing)
            ):
                # Current emission time is not proof of a new source passage.
                # Delayed confirmation of older alias geometry cannot override
                # the clock of a newer accepted finite crossing.
                self._last_external_reject_reason[tid] = "stale-crossing-frame"
                return False
        if int(frame_index) <= state.last_count_frame:
            # Verified geometry can justify a later passage during cooldown;
            # it cannot turn an older alias/lost-track handoff into a new source
            # event or rewind the accepted passage clock.
            self._last_external_reject_reason[tid] = "stale-source-frame"
            return False
        if same_direction_blocked and not verified_anchor_span:
            self.rejected_same_direction_cycle += 1
            self._last_external_reject_reason[tid] = "same-direction"
            return False
        if cooldown_blocked and not verified_anchor_span:
            self._last_external_reject_reason[tid] = "cooldown"
            return False
        self._capture_passage_rollback(
            tid, direction, int(frame_index), state,
            same_direction_override=verified_anchor_span and same_direction_blocked,
            cooldown_override=verified_anchor_span and cooldown_blocked,
        )
        if verified_anchor_span and same_direction_blocked:
            self.verified_same_direction_overrides += 1
        if verified_anchor_span and cooldown_blocked:
            self.verified_cooldown_overrides += 1
        state.counted_directions = {direction}
        state.armed = False
        state.last_count_frame = int(frame_index)
        state.max_abs_distance_since_count = 0.0
        self._last_crossing_point[tid] = crossing_point
        self._last_crossing_frame[tid] = float(crossing_frame) if crossing_frame is not None else float(frame_index)
        resolved_mode = mode if mode in {"direct", "interpolated", "rescued"} else "rescued"
        self._last_crossing_mode[tid] = resolved_mode
        self._last_origin_rescue.discard(tid)
        if resolved_mode == "direct":
            self.direct_crossings += 1
        elif resolved_mode == "interpolated":
            self.interpolated_crossings += 1
        else:
            self.rescued_crossings += 1
        if direction == "in":
            self.in_count += 1
        else:
            self.out_count += 1
        return True


    def external_rejection_reason_for(self, track_id: int) -> str | None:
        return self._last_external_reject_reason.get(int(track_id))

    def crossing_point_for(self, track_id: int) -> Point | None:
        return self._last_crossing_point.get(int(track_id))

    def crossing_frame_for(self, track_id: int) -> float | None:
        return self._last_crossing_frame.get(int(track_id))

    def revoke_last_crossing(self, track_id: int, direction: str) -> bool:
        """Undo the most recent crossing when a downstream semantic guard rejects it.

        Human Guard runs only after geometry finds a real line crossing. If the
        object is then proven to be a pedestrian, the geometry counter must be
        rolled back so IN/OUT telemetry remains truthful.
        """
        track_id = int(track_id)
        state = self._tracks.get(track_id)
        rollback = self._passage_rollbacks.get(track_id)
        if (
            state is None or rollback is None
            or str(direction) != rollback.accepted_direction
            or state.last_count_frame != rollback.accepted_frame
        ):
            return False
        self._passage_rollbacks.pop(track_id)
        mode = self._last_crossing_mode.get(track_id)
        was_origin_rescue = track_id in self._last_origin_rescue
        self._last_origin_rescue.discard(track_id)
        state.counted_directions = set(rollback.counted_directions)
        state.last_count_frame = rollback.last_count_frame
        state.armed = rollback.armed
        state.max_abs_distance_since_count = rollback.max_abs_distance_since_count
        # The rejected geometry must not be replayed on the next sample or
        # mistaken for the opposite traversal that reopens the previous cycle.
        state.history.clear()
        state.origin_history.clear()
        for mapping, previous in (
            (self._last_crossing_point, rollback.crossing_point),
            (self._last_crossing_frame, rollback.crossing_frame),
            (self._last_crossing_mode, rollback.crossing_mode),
        ):
            if previous is None:
                mapping.pop(track_id, None)
            else:
                mapping[track_id] = previous
        if rollback.origin_rescue:
            self._last_origin_rescue.add(track_id)
        if rollback.same_direction_override:
            self.verified_same_direction_overrides = max(0, self.verified_same_direction_overrides - 1)
        if rollback.cooldown_override:
            self.verified_cooldown_overrides = max(0, self.verified_cooldown_overrides - 1)
        if direction == "in" and self.in_count > 0:
            self.in_count -= 1
        elif direction == "out" and self.out_count > 0:
            self.out_count -= 1
        if mode == "direct" and self.direct_crossings > 0:
            self.direct_crossings -= 1
            if was_origin_rescue and self.origin_rescues > 0:
                self.origin_rescues -= 1
        elif mode == "interpolated" and self.interpolated_crossings > 0:
            self.interpolated_crossings -= 1
        elif mode == "rescued" and self.rescued_crossings > 0:
            self.rescued_crossings -= 1
        return True

    def merge_track(self, source_track_id: int, target_track_id: int) -> None:
        """Coalesce gate history after cross-class canonical ID fusion.

        V0.5.30 canonical four-wheel fusion must merge more than ByteTrack IDs:
        the strict gate history is also transferred, otherwise one physical van
        can have the pre-line samples under CAR and post-line samples under
        TRUCK and never produce one complete trajectory.
        """
        source = int(source_track_id)
        target = int(target_track_id)
        if source == target:
            return
        src = self._tracks.pop(source, None)
        if src is None:
            return
        dst = self._tracks.get(target)
        source_is_latest = dst is None or src.last_count_frame > dst.last_count_frame
        source_rollback = self._passage_rollbacks.pop(source, None)
        target_rollback = self._passage_rollbacks.pop(target, None)
        rollback = source_rollback if source_is_latest else target_rollback
        other_state, other_tid = (dst, target) if source_is_latest else (src, source)
        if rollback is not None and other_state is not None and (
            rollback.last_count_frame < other_state.last_count_frame < rollback.accepted_frame
        ):
            # A provisional event on one alias may follow a committed passage
            # on the other. Its rollback must preserve that newer prior passage,
            # rather than restoring the source alias's initially empty clock.
            rollback.counted_directions = set(other_state.counted_directions)
            rollback.last_count_frame = other_state.last_count_frame
            rollback.armed = other_state.armed
            rollback.max_abs_distance_since_count = other_state.max_abs_distance_since_count
            rollback.crossing_point = self._last_crossing_point.get(other_tid)
            rollback.crossing_frame = self._last_crossing_frame.get(other_tid)
            rollback.crossing_mode = self._last_crossing_mode.get(other_tid)
            rollback.origin_rescue = other_tid in self._last_origin_rescue
        if rollback is not None:
            self._passage_rollbacks[target] = rollback
        if dst is None:
            self._tracks[target] = src
        else:
            history = {item.frame_index: item for item in src.history}
            history.update({item.frame_index: item for item in dst.history})
            dst.history = deque(sorted(history.values(), key=lambda item: item.frame_index)[-48:], maxlen=48)
            origin_history = {item.frame_index: item for item in src.origin_history}
            origin_history.update({item.frame_index: item for item in dst.origin_history})
            dst.origin_history = deque(sorted(origin_history.values(), key=lambda item: item.frame_index)[-20:], maxlen=20)
            # V0.5.46: counted_directions represents the latest accepted
            # passage direction, not a lifetime set.  Canonical fusion must keep
            # the newer passage state instead of unioning IN and OUT forever.
            if src.last_count_frame > dst.last_count_frame:
                dst.counted_directions = set(src.counted_directions)
                dst.armed = src.armed
                dst.max_abs_distance_since_count = src.max_abs_distance_since_count
            elif src.last_count_frame == dst.last_count_frame:
                if not dst.counted_directions:
                    dst.counted_directions = set(src.counted_directions)
                dst.armed = dst.armed and src.armed if dst.counted_directions else (dst.armed or src.armed)
                dst.max_abs_distance_since_count = max(dst.max_abs_distance_since_count, src.max_abs_distance_since_count)
            # Re-arm and cooldown excursion belong to the same latest accepted
            # passage as direction/clock. An older unarmed alias cannot disarm a
            # new rearmed traversal, or lend its old far-away travel to release
            # the new traversal's cooldown.
            dst.last_count_frame = max(dst.last_count_frame, src.last_count_frame)
            if dst.counted_directions:
                dst.history = deque([
                    item for item in dst.history if item.frame_index >= dst.last_count_frame
                ], maxlen=48)
                dst.origin_history = deque([
                    item for item in dst.origin_history if item.frame_index >= dst.last_count_frame
                ], maxlen=20)
            dst.first_frame = min([value for value in (dst.first_frame, src.first_frame) if value is not None], default=None)
            dst.total_samples += src.total_samples
            # Confirmation follows the merged observations, not whichever alias
            # happened to be the destination ID. Neutral observations preserve
            # the nonzero-side streak just as update() does.
            dst.last_nonzero_side = 0
            dst.side_streak = 0
            for item in dst.history:
                if item.side:
                    if item.side == dst.last_nonzero_side:
                        dst.side_streak += 1
                    else:
                        dst.last_nonzero_side = item.side
                        dst.side_streak = 1
        for mapping in (self._last_crossing_mode, self._last_crossing_point, self._last_crossing_frame):
            value = mapping.pop(source, None)
            if source_is_latest:
                if value is None:
                    mapping.pop(target, None)
                else:
                    mapping[target] = value
        if source_is_latest:
            if source in self._last_origin_rescue:
                self._last_origin_rescue.add(target)
            else:
                self._last_origin_rescue.discard(target)
        self._last_origin_rescue.discard(source)

    def crossing_mode_for(self, track_id: int) -> str | None:
        return self._last_crossing_mode.get(int(track_id))

    @property
    def crossing_breakdown(self) -> dict[str, int]:
        return {
            "direct": self.direct_crossings,
            "interpolated": self.interpolated_crossings,
            "rescued": self.rescued_crossings,
        }

    @property
    def counted_tracks(self) -> int:
        return sum(1 for state in self._tracks.values() if state.counted_directions)

    @property
    def total_crossings(self) -> int:
        return self.in_count + self.out_count
