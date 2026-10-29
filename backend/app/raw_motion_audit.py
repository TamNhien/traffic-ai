"""Project bounded same-raw motion evidence without changing count decisions."""
from __future__ import annotations

from math import isfinite


RECORDS_LIMIT = 8
FRAME_LIMIT = 256
SAFE_INTEGER = 2**53 - 1


def _integer(value, *, minimum=-SAFE_INTEGER, maximum=SAFE_INTEGER):
    return type(value) is int and minimum <= value <= maximum


def _number(value, *, minimum=-1_000_000, maximum=1_000_000):
    return type(value) in (int, float) and minimum <= value <= maximum and isfinite(value)


def _vector(value):
    if type(value) is not list or len(value) != 2 or not all(_number(item) for item in value):
        return None
    return list(value)


def scope_raw_motion_audit(audit, tracking_id):
    """Return detached, validated evidence only for the requested canonical ID.

    Motion belongs to consecutive samples of one raw ID. No displacement at a
    raw-ID handoff is allowed to masquerade as an observed motion segment, and
    this audit never proves identity, a gate crossing or a direction correction.
    """
    if (not _integer(tracking_id) or type(audit) is not dict
            or type(audit.get('schema_version')) is not int or audit['schema_version'] != 1
            or audit.get('scope') != 'same_raw_contiguous_observations'
            or not _integer(audit.get('tracking_id')) or audit['tracking_id'] != tracking_id
            or audit.get('identity_proven') is not False
            or type(audit.get('status')) is not str or audit['status'] not in {'observed', 'unavailable'}
            or type(audit.get('records_limit')) is not int or audit['records_limit'] != RECORDS_LIMIT
            or type(audit.get('truncated')) is not bool
            or not all(_integer(audit.get(key), minimum=0, maximum=FRAME_LIMIT)
                       for key in ('conflicting_frames', 'out_of_order_frames'))):
        return None
    segments = audit.get('segments')
    if type(segments) is not list or len(segments) > RECORDS_LIMIT:
        return None
    observed = audit['status'] == 'observed'
    if observed != bool(segments) or (observed and (audit['conflicting_frames'] or audit['out_of_order_frames'])):
        return None
    result = {key: audit[key] for key in (
        'schema_version', 'scope', 'tracking_id', 'identity_proven', 'status',
        'records_limit', 'truncated', 'conflicting_frames', 'out_of_order_frames',
    )}
    result['segments'] = []
    previous_frame = previous_time = None
    samples = 0
    for segment in segments:
        if type(segment) is not dict or not _integer(segment.get('raw_track_id')):
            return None
        first, last = segment.get('first_frame'), segment.get('last_frame')
        start, end = segment.get('first_time'), segment.get('last_time')
        count = segment.get('sample_count')
        if (not _integer(first, minimum=1) or not _integer(last, minimum=1) or last <= first
                or not _integer(count, minimum=2, maximum=FRAME_LIMIT) or count != last - first + 1
                or not _number(start, minimum=0) or not _number(end, minimum=0) or end <= start
                or previous_frame is not None and (first <= previous_frame or start <= previous_time)):
            return None
        samples += count
        if samples > FRAME_LIMIT:
            return None
        motion = segment.get('rect_motion')
        gap = last - first
        if (type(motion) is not dict or not _number(motion.get('dx')) or not _number(motion.get('dy'))
                or not _integer(motion.get('gap_frames'), minimum=1) or motion['gap_frames'] != gap):
            return None
        velocity = _vector(motion.get('pixels_per_frame'))
        # The producer rounds displacement and per-frame motion to six decimal
        # places. This tolerance covers only their independent serialization.
        if velocity is None or any(abs(value - motion[axis] / gap) > 0.0000011
                                   for value, axis in zip(velocity, ('dx', 'dy'))):
            return None
        filtered = segment.get('filtered_velocity')
        if filtered is not None:
            filtered = _vector(filtered)
            if filtered is None:
                return None
        result['segments'].append({
            'raw_track_id': segment['raw_track_id'], 'first_frame': first, 'last_frame': last,
            'first_time': start, 'last_time': end, 'sample_count': count,
            'rect_motion': {'dx': motion['dx'], 'dy': motion['dy'], 'gap_frames': gap,
                            'pixels_per_frame': velocity},
            'filtered_velocity': filtered,
        })
        previous_frame, previous_time = last, end
    return result
