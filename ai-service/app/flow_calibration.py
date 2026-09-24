from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from math import hypot
from typing import Iterable


def _clamp(value: float, lo: float = 0.02, hi: float = 0.98) -> float:
    return max(lo, min(hi, float(value)))


def _quantile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("No values")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = max(0.0, min(1.0, q)) * (len(ordered) - 1)
    lo = int(pos)
    hi = min(len(ordered) - 1, lo + 1)
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


@dataclass(slots=True)
class FlowSample:
    track_id: int
    x: float
    y: float
    frame_index: int


class FlowCalibrator:
    """Collect recent moving vehicle tracks and propose a Road Zone + count line.

    The calibrator deliberately ignores stationary detections by requiring a minimum
    end-to-end track displacement. The resulting quadrilateral follows the observed
    vehicle corridor and the proposed counting line is perpendicular to the dominant
    motion axis. All coordinates are normalized to [0, 1].
    """

    def __init__(self, history_frames: int = 1200, per_track_points: int = 180) -> None:
        self.history_frames = max(120, int(history_frames))
        self.per_track_points = max(12, int(per_track_points))
        self._tracks: dict[int, deque[FlowSample]] = defaultdict(lambda: deque(maxlen=self.per_track_points))
        self._latest_frame = 0

    def add(self, track_id: int, anchor: tuple[float, float], width: int, height: int, frame_index: int) -> None:
        if width <= 0 or height <= 0:
            return
        x = max(0.0, min(1.0, float(anchor[0]) / float(width)))
        y = max(0.0, min(1.0, float(anchor[1]) / float(height)))
        self._latest_frame = max(self._latest_frame, int(frame_index))
        samples = self._tracks[int(track_id)]
        if samples and samples[-1].frame_index == int(frame_index):
            samples[-1] = FlowSample(int(track_id), x, y, int(frame_index))
        else:
            samples.append(FlowSample(int(track_id), x, y, int(frame_index)))
        self._prune()

    def _prune(self) -> None:
        cutoff = self._latest_frame - self.history_frames
        stale: list[int] = []
        for track_id, samples in self._tracks.items():
            while samples and samples[0].frame_index < cutoff:
                samples.popleft()
            if not samples:
                stale.append(track_id)
        for track_id in stale:
            self._tracks.pop(track_id, None)

    def stats(self) -> dict:
        moving = self._moving_tracks()
        return {
            "sample_count": sum(len(samples) for samples in moving.values()),
            "track_count": len(self._tracks),
            "moving_track_count": len(moving),
            "ready": len(moving) >= 4 and sum(len(samples) for samples in moving.values()) >= 40,
        }

    def _moving_tracks(self, min_points: int = 4, min_displacement: float = 0.025) -> dict[int, list[FlowSample]]:
        result: dict[int, list[FlowSample]] = {}
        for track_id, samples_deque in self._tracks.items():
            samples = list(samples_deque)
            if len(samples) < min_points:
                continue
            dx = samples[-1].x - samples[0].x
            dy = samples[-1].y - samples[0].y
            if hypot(dx, dy) < min_displacement:
                continue
            result[track_id] = samples
        return result

    @staticmethod
    def _dominant_axis(tracks: dict[int, list[FlowSample]]) -> tuple[float, float, float]:
        vectors: list[tuple[float, float, float]] = []
        reference: tuple[float, float] | None = None
        for samples in tracks.values():
            dx = samples[-1].x - samples[0].x
            dy = samples[-1].y - samples[0].y
            mag = hypot(dx, dy)
            if mag <= 1e-6:
                continue
            ux, uy = dx / mag, dy / mag
            if reference is None:
                reference = (ux, uy)
            elif ux * reference[0] + uy * reference[1] < 0:
                ux, uy = -ux, -uy
            vectors.append((ux, uy, mag))
        if not vectors:
            raise ValueError("Chưa có đủ quỹ đạo chuyển động để học lòng đường.")
        sx = sum(ux * weight for ux, _, weight in vectors)
        sy = sum(uy * weight for _, uy, weight in vectors)
        norm = hypot(sx, sy)
        if norm <= 1e-6:
            raise ValueError("Luồng xe chưa có hướng chuyển động ổn định để đề xuất vạch.")
        dx, dy = sx / norm, sy / norm
        alignment = sum(abs(ux * dx + uy * dy) for ux, uy, _ in vectors) / len(vectors)
        return dx, dy, alignment

    def proposal(self) -> dict:
        tracks = self._moving_tracks()
        sample_count = sum(len(samples) for samples in tracks.values())
        if len(tracks) < 4 or sample_count < 40:
            raise ValueError(
                f"Chưa đủ dữ liệu luồng xe: cần ít nhất 4 track chuyển động và 40 điểm, hiện có {len(tracks)} track / {sample_count} điểm."
            )

        dx, dy, alignment = self._dominant_axis(tracks)
        nx, ny = -dy, dx
        samples = [sample for values in tracks.values() for sample in values]
        projected = [(sample.x * dx + sample.y * dy, sample.x * nx + sample.y * ny, sample) for sample in samples]
        t_values = [item[0] for item in projected]
        t_core_lo = _quantile(t_values, 0.06)
        t_core_hi = _quantile(t_values, 0.94)
        if t_core_hi - t_core_lo < 0.18:
            raise ValueError("Quỹ đạo xe quan sát được còn quá ngắn; hãy để AI chạy thêm một lúc rồi đề xuất lại.")

        t_slice_lo = _quantile(t_values, 0.24)
        t_slice_hi = _quantile(t_values, 0.76)
        low_slice = [item for item in projected if item[0] <= t_slice_lo]
        high_slice = [item for item in projected if item[0] >= t_slice_hi]
        if len(low_slice) < 6 or len(high_slice) < 6:
            low_slice = sorted(projected, key=lambda item: item[0])[: max(6, len(projected) // 4)]
            high_slice = sorted(projected, key=lambda item: item[0])[-max(6, len(projected) // 4):]

        def side_bounds(items: Iterable[tuple[float, float, FlowSample]]) -> tuple[float, float]:
            values = [item[1] for item in items]
            lo = _quantile(values, 0.05) - 0.035
            hi = _quantile(values, 0.95) + 0.035
            if hi - lo < 0.18:
                mid = (hi + lo) / 2.0
                lo, hi = mid - 0.09, mid + 0.09
            return lo, hi

        s_low_lo, s_low_hi = side_bounds(low_slice)
        s_high_lo, s_high_hi = side_bounds(high_slice)
        t_lo = t_core_lo - 0.025
        t_hi = t_core_hi + 0.025

        def point(t: float, s: float) -> tuple[float, float]:
            return (_clamp(dx * t + nx * s), _clamp(dy * t + ny * s))

        # Ordered around the observed road corridor: low-left, low-right,
        # high-right, high-left. RoadZone accepts any image orientation.
        p1 = point(t_lo, s_low_lo)
        p2 = point(t_lo, s_low_hi)
        p3 = point(t_hi, s_high_hi)
        p4 = point(t_hi, s_high_lo)

        line_fraction = 0.58
        t_line = t_core_lo + (t_core_hi - t_core_lo) * line_fraction
        s_line_lo = s_low_lo + (s_high_lo - s_low_lo) * line_fraction
        s_line_hi = s_low_hi + (s_high_hi - s_low_hi) * line_fraction
        width_s = max(0.08, s_line_hi - s_line_lo)
        inset = min(0.035, width_s * 0.10)
        a = point(t_line, s_line_lo + inset)
        b = point(t_line, s_line_hi - inset)

        quality = max(0.0, min(1.0,
            alignment * min(1.0, len(tracks) / 10.0) * min(1.0, sample_count / 220.0)
        ))

        return {
            "geometry": {
                "road_x1": round(p1[0], 4), "road_y1": round(p1[1], 4),
                "road_x2": round(p2[0], 4), "road_y2": round(p2[1], 4),
                "road_x3": round(p3[0], 4), "road_y3": round(p3[1], 4),
                "road_x4": round(p4[0], 4), "road_y4": round(p4[1], 4),
                "line_x1": round(a[0], 4), "line_y1": round(a[1], 4),
                "line_x2": round(b[0], 4), "line_y2": round(b[1], 4),
            },
            "quality": round(quality, 3),
            "sample_count": sample_count,
            "moving_track_count": len(tracks),
            "direction_alignment": round(alignment, 3),
            "dominant_direction": {"x": round(dx, 4), "y": round(dy, 4)},
            "message": "Đề xuất được học từ các track đang chuyển động; xe đứng/đỗ không được dùng để khoanh lòng đường.",
        }
