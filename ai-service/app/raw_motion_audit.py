"""Bounded box-center motion of one raw token, never a crossing decision.

An ID handoff or missing source frame ends a segment. In particular, the jump
between two raw IDs is not evidence of either raw token's observed movement.
"""
from __future__ import annotations

from math import isfinite

RAW_MOTION_FRAME_LIMIT = 256
RAW_MOTION_TRACKS_PER_FRAME = 64
RAW_MOTION_RECORD_LIMIT = 8


def _integer(value):
    return type(value) is int and abs(value) <= 2**53 - 1


def _number(value):
    return type(value) in (int, float) and abs(value) <= 1_000_000 and isfinite(value)


def _vector(value, length):
    if (not isinstance(value, (list, tuple)) or len(value) != length
            or not all(_number(part) for part in value)):
        return None
    return list(map(float, value))


def _sample(item, frame, time):
    raw = item.get('raw_track_id')
    rect = _vector(item.get('rect'), 4)
    if (not _integer(raw) or rect is None or any(part < 0 for part in rect)
            or rect[2] - rect[0] < .001 or rect[3] - rect[1] < .001):
        return None
    return {
        'raw': raw, 'frame': frame, 'time': float(time),
        'center': [(rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2],
        'rect': rect, 'velocity': _vector(item.get('measured_velocity'), 2),
    }


def _record(first, last, count):
    gap = last['frame'] - first['frame']
    dx = last['center'][0] - first['center'][0]
    dy = last['center'][1] - first['center'][1]
    return {
        'raw_track_id': first['raw'],
        'first_frame': first['frame'], 'last_frame': last['frame'],
        'first_time': first['time'], 'last_time': last['time'],
        'sample_count': count,
        'rect_motion': {
            'dx': round(dx, 6), 'dy': round(dy, 6), 'gap_frames': gap,
            'pixels_per_frame': [round(dx / gap, 6), round(dy / gap, 6)],
        },
        'filtered_velocity': list(last['velocity']) if last['velocity'] is not None else None,
    }


class RawMotionAudit:
    """Keep consecutive observations of a requested canonical owner separate.

    The canonical ID scopes the query, not physical identity. Duplicate or
    out-of-order conflicting evidence makes the entire result unavailable.
    No source paths, model data, environment values or free text are retained.
    """

    def __init__(self, tracking_id):
        self.tracking_id = tracking_id
        self.frames = {}
        self.last_frame = self.last_time = None
        self.truncated = False
        self.conflicting_frames = 0
        self.out_of_order_frames = 0

    def observe(self, row):
        if (not _integer(self.tracking_id) or not isinstance(row, dict)
                or row.get('audit_only') or row.get('kind') is not None):
            return
        frame, time = row.get('frame_index'), row.get('source_time_seconds')
        tracks = row.get('gate_tracks')
        if (not _integer(frame) or frame < 1 or not _number(time) or time < 0
                or not isinstance(tracks, list)):
            return
        if len(tracks) > RAW_MOTION_TRACKS_PER_FRAME:
            self.truncated = True
        own = []
        for item in tracks[:RAW_MOTION_TRACKS_PER_FRAME]:
            if (isinstance(item, dict) and _integer(item.get('track_id'))
                    and item['track_id'] == self.tracking_id):
                own.append(_sample(item, frame, time))
        sample = own[0] if own else None
        if any(other != sample for other in own[1:]):
            self.conflicting_frames = min(RAW_MOTION_FRAME_LIMIT, self.conflicting_frames + 1)
            return
        signature = float(time), sample
        if frame in self.frames:
            if self.frames[frame] != signature:
                self.conflicting_frames = min(RAW_MOTION_FRAME_LIMIT, self.conflicting_frames + 1)
            return
        if self.last_frame is not None and (frame < self.last_frame or time <= self.last_time):
            self.out_of_order_frames = min(RAW_MOTION_FRAME_LIMIT, self.out_of_order_frames + 1)
            return
        if len(self.frames) >= RAW_MOTION_FRAME_LIMIT:
            self.truncated = True
            return
        self.frames[frame] = signature
        self.last_frame, self.last_time = frame, float(time)

    def finish(self):
        segments = []
        first = last = None
        count = 0
        truncated = self.truncated

        def close():
            nonlocal truncated
            if count < 2:
                return
            if len(segments) < RAW_MOTION_RECORD_LIMIT:
                segments.append(_record(first, last, count))
            else:
                truncated = True

        if not self.conflicting_frames and not self.out_of_order_frames:
            for _, sample in self.frames.values():
                consecutive = (sample is not None and last is not None
                               and sample['raw'] == last['raw']
                               and sample['frame'] == last['frame'] + 1
                               and sample['time'] > last['time'])
                if not consecutive:
                    close()
                    first = sample
                    count = 1 if sample is not None else 0
                else:
                    count += 1
                last = sample
            close()
        return {
            'schema_version': 1, 'scope': 'same_raw_contiguous_observations',
            'tracking_id': self.tracking_id, 'identity_proven': False,
            'status': 'observed' if segments else 'unavailable',
            'segments': segments, 'truncated': truncated,
            'conflicting_frames': self.conflicting_frames,
            'out_of_order_frames': self.out_of_order_frames,
            'records_limit': RAW_MOTION_RECORD_LIMIT,
        }
