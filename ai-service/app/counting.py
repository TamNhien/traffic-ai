from __future__ import annotations

from collections import deque
import os
from dataclasses import dataclass, field
from math import hypot

Point = tuple[float, float]


@dataclass(slots=True)
class CountingLine:
    x1: float = 0.1
    y1: float = 0.5
    x2: float = 0.9
    y2: float = 0.5

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


@dataclass(slots=True)
class _GateSample:
    frame_index: int
    point: Point
    distance: float
    side: int


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
class _HeavyRescueState:
    history: deque[_GateSample] = field(default_factory=lambda: deque(maxlen=128))
    counted_directions: set[str] = field(default_factory=set)


class HeavyVehicleCrossingRescuer:
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

    def update(
        self,
        track_id: int,
        center: Point,
        frame_width: int,
        frame_height: int,
        frame_index: int,
    ) -> tuple[str, Point] | None:
        a, b = self.line.denormalize(frame_width, frame_height)
        scale = max(1.0, min(frame_width, frame_height))
        dead_band = max(2.0, scale * self.dead_band_ratio)
        distance = signed_distance(center, a, b)
        side = 0 if abs(distance) <= dead_band else (1 if distance > 0 else -1)
        sample = _GateSample(int(frame_index), center, distance, side)
        state = self._tracks.setdefault(int(track_id), _HeavyRescueState())
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

        crossing = segment_crossing_point(
            previous.point, center, a, b, segment_margin=self.segment_margin
        )
        if crossing is None:
            self.rejected_segment += 1
            return None

        dx = center[0] - previous.point[0]
        dy = center[1] - previous.point[1]
        move_len = max(hypot(dx, dy), 1e-6)
        perpendicular = abs(distance - previous.distance)
        if perpendicular < max(2.0, scale * self.min_motion_ratio) or perpendicular / move_len < self.min_normal_ratio:
            self.rejected_motion += 1
            return None

        if self.road_zone is not None:
            ux, uy = dx / move_len, dy / move_len
            probe = max(3.0, scale * 0.018)
            before = (crossing[0] - ux * probe, crossing[1] - uy * probe)
            after = (crossing[0] + ux * probe, crossing[1] + uy * probe)
            centers_ok = (
                self.road_zone.contains_with_margin(previous.point, frame_width, frame_height, self.road_margin_ratio)
                and self.road_zone.contains_with_margin(center, frame_width, frame_height, self.road_margin_ratio)
            )
            corridor_ok = (
                self.road_zone.contains(crossing, frame_width, frame_height)
                and self.road_zone.contains(before, frame_width, frame_height)
                and self.road_zone.contains(after, frame_width, frame_height)
            )
            if not (centers_ok and corridor_ok):
                self.rejected_road += 1
                return None

        state.counted_directions.add(direction)
        self.rescues += 1
        state.history = deque([sample], maxlen=128)
        return direction, crossing

    def merge_track(self, source_track_id: int, target_track_id: int) -> None:
        source = int(source_track_id)
        target = int(target_track_id)
        if source == target:
            return
        src = self._tracks.pop(source, None)
        if src is None:
            return
        dst = self._tracks.get(target)
        if dst is None:
            self._tracks[target] = src
            return
        samples = list(dst.history) + list(src.history)
        samples.sort(key=lambda sample: sample.frame_index)
        dst.history = deque(samples[-128:], maxlen=128)
        dst.counted_directions.update(src.counted_directions)


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
        road_anchor_margin_ratio: float = 0.0,
        fast_confirm_distance_ratio: float = 0.0,
        adaptive_cooldown: bool = False,
        cooldown_release_ratio: float = 0.0,
        rescue_min_normal_ratio: float = 0.0,
        rescue_max_jump_ratio: float = 0.0,
        rescue_min_side_distance_ratio: float = 0.0,
        bracket_confirm: bool = False,
        bracket_confirm_min_normal_ratio: float = 0.55,
        bracket_confirm_max_gap_frames: int = 2,
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
        self.road_anchor_margin_ratio = max(0.0, float(road_anchor_margin_ratio))
        self.fast_confirm_distance_ratio = max(0.0, float(fast_confirm_distance_ratio))
        self.adaptive_cooldown = bool(adaptive_cooldown)
        self.cooldown_release_ratio = max(0.0, float(cooldown_release_ratio))
        self.rescue_min_normal_ratio = max(0.0, min(1.0, float(rescue_min_normal_ratio)))
        self.rescue_max_jump_ratio = max(0.0, float(rescue_max_jump_ratio))
        self.rescue_min_side_distance_ratio = max(0.0, float(rescue_min_side_distance_ratio))
        self.bracket_confirm = bool(bracket_confirm)
        self.bracket_confirm_min_normal_ratio = max(0.0, min(1.0, float(bracket_confirm_min_normal_ratio)))
        self.bracket_confirm_max_gap_frames = max(1, int(bracket_confirm_max_gap_frames))
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
        self.origin_rescues = 0
        self.rejected_rescue_validation = 0
        self.adaptive_cooldown_releases = 0
        self._last_crossing_point: dict[int, Point] = {}

    def update(
        self,
        track_id: int,
        anchor: Point,
        frame_width: int,
        frame_height: int,
        frame_index: int | None = None,
        origin_probe: Point | None = None,
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
                state.armed = True
                state.history = deque(list(state.history)[-5:], maxlen=48)
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
                move_len_origin = max(hypot(move_x_origin, move_y_origin), 1e-6)
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
            quick_dx = anchor[0] - previous.point[0]
            quick_dy = anchor[1] - previous.point[1]
            quick_len = max(hypot(quick_dx, quick_dy), 1e-6)
            quick_normal_ratio = abs(distance - previous.distance) / quick_len
            bracket_destination = (
                quick_crossing is not None
                and quick_normal_ratio >= self.bracket_confirm_min_normal_ratio
            )
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
                self.rejected_unconfirmed_side += 1
                return None
        if sample.frame_index - state.last_count_frame < self.crossing_cooldown_frames:
            release_distance = scale * self.cooldown_release_ratio
            can_release = (
                self.adaptive_cooldown
                and release_distance > 0.0
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
            for left, right in zip(history[previous_index:-1], history[previous_index + 1:]):
                if left.frame_index >= sample.frame_index:
                    break
                # Adjacent samples bracket/touch the infinite gate. The finite-gate
                # intersection below still decides whether the visible segment was
                # really crossed.
                if left.side == 0 or right.side == 0 or left.side * right.side < 0:
                    crossing_start, crossing_end = left, right

        crossing = segment_crossing_point(
            crossing_start.point,
            crossing_end.point,
            a,
            b,
            segment_margin=self.segment_margin,
        )
        if crossing is None:
            # Fallback to the stable opposite-side pair for sparse/fast tracks.
            crossing_start, crossing_end = previous, sample
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

        # Crossing Engine 7.1: long-gap rescues are useful for fast vehicles but
        # are also the riskiest source of over-count. Validate the jump before
        # accepting it. Defaults are disabled for backwards-compatible unit
        # tests; runtime enables conservative thresholds through environment.
        if observation_gap > self.interpolation_gap_frames:
            jump_x = anchor[0] - previous.point[0]
            jump_y = anchor[1] - previous.point[1]
            jump_len = max(hypot(jump_x, jump_y), 1e-6)
            diagonal = max(hypot(frame_width, frame_height), 1.0)
            normal_ratio = abs(distance - previous.distance) / jump_len
            jump_ratio = jump_len / diagonal
            side_depth_ratio = min(abs(distance), abs(previous.distance)) / scale
            rescue_invalid = (
                (self.rescue_min_normal_ratio > 0.0 and normal_ratio < self.rescue_min_normal_ratio)
                or (self.rescue_max_jump_ratio > 0.0 and jump_ratio > self.rescue_max_jump_ratio)
                or (self.rescue_min_side_distance_ratio > 0.0 and side_depth_ratio < self.rescue_min_side_distance_ratio)
            )
            if rescue_invalid:
                self.rejected_rescue_validation += 1
                return None

        if self.road_zone is not None:
            move_x_zone = anchor[0] - previous.point[0]
            move_y_zone = anchor[1] - previous.point[1]
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

        move_x = anchor[0] - previous.point[0]
        move_y = anchor[1] - previous.point[1]
        move_len = max(hypot(move_x, move_y), 1e-6)
        perpendicular = abs(distance - previous.distance)
        min_motion = max(2.0, scale * self.min_crossing_motion_ratio)
        if perpendicular < min_motion:
            return None
        if perpendicular / move_len < self.min_perpendicular_ratio:
            return None

        direction = "in" if previous.side < 0 < side else "out"
        if direction in state.counted_directions:
            return None

        state.counted_directions.add(direction)
        state.armed = False
        state.last_count_frame = sample.frame_index
        state.max_abs_distance_since_count = 0.0
        self._last_crossing_point[int(track_id)] = crossing

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
        if direction in state.counted_directions:
            return False
        if int(frame_index) - state.last_count_frame < self.crossing_cooldown_frames:
            return False
        state.counted_directions.add(direction)
        state.armed = False
        state.last_count_frame = int(frame_index)
        state.max_abs_distance_since_count = 0.0
        self._last_crossing_point[tid] = crossing_point
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


    def crossing_point_for(self, track_id: int) -> Point | None:
        return self._last_crossing_point.get(int(track_id))

    def revoke_last_crossing(self, track_id: int, direction: str) -> None:
        """Undo the most recent crossing when a downstream semantic guard rejects it.

        Human Guard runs only after geometry finds a real line crossing. If the
        object is then proven to be a pedestrian, the geometry counter must be
        rolled back so IN/OUT telemetry remains truthful.
        """
        track_id = int(track_id)
        state = self._tracks.get(track_id)
        mode = self._last_crossing_mode.pop(track_id, None)
        was_origin_rescue = track_id in self._last_origin_rescue
        self._last_origin_rescue.discard(track_id)
        self._last_crossing_point.pop(track_id, None)
        if state is not None:
            state.counted_directions.discard(str(direction))
            state.armed = False
            state.max_abs_distance_since_count = 0.0
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
        if dst is None:
            self._tracks[target] = src
        else:
            history = list(dst.history) + list(src.history)
            history.sort(key=lambda sample: sample.frame_index)
            dst.history = deque(history[-48:], maxlen=48)
            origin_history = list(dst.origin_history) + list(src.origin_history)
            origin_history.sort(key=lambda sample: sample.frame_index)
            dst.origin_history = deque(origin_history[-20:], maxlen=20)
            dst.counted_directions.update(src.counted_directions)
            dst.last_count_frame = max(dst.last_count_frame, src.last_count_frame)
            dst.armed = dst.armed and src.armed if dst.counted_directions else (dst.armed or src.armed)
            dst.first_frame = min([value for value in (dst.first_frame, src.first_frame) if value is not None], default=None)
            dst.total_samples += src.total_samples
            dst.max_abs_distance_since_count = max(dst.max_abs_distance_since_count, src.max_abs_distance_since_count)
            latest = max(dst.history, key=lambda sample: sample.frame_index, default=None)
            if latest is not None:
                dst.last_nonzero_side = latest.side if latest.side != 0 else dst.last_nonzero_side
        source_frame = src.last_count_frame
        target_state = self._tracks.get(target)
        if source in self._last_crossing_mode and (target not in self._last_crossing_mode or source_frame >= (target_state.last_count_frame if target_state else -10000)):
            self._last_crossing_mode[target] = self._last_crossing_mode[source]
        self._last_crossing_mode.pop(source, None)
        if source in self._last_crossing_point:
            self._last_crossing_point[target] = self._last_crossing_point[source]
        self._last_crossing_point.pop(source, None)
        if source in self._last_origin_rescue:
            self._last_origin_rescue.add(target)
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
