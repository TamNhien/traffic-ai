import { buildObservedTrackAuditView } from './observed-track-audit.js'

const integer = value => Number.isSafeInteger(value) ? value : null
const count = value => integer(value) !== null && value >= 0 ? value : null
const number = value => typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= 1_000_000
const time = value => number(value) && value >= 0
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value)
const vector = value => Array.isArray(value) && value.length === 2 && value.every(number) ? [...value] : null

function cosine(left, right) {
  if (!left || !right) return null
  const length = Math.hypot(...left) * Math.hypot(...right)
  if (!Number.isFinite(length) || length <= 1e-9) return null
  return Math.max(-1, Math.min(1, (left[0] * right[0] + left[1] * right[1]) / length))
}

function segmentView(value) {
  if (!record(value) || integer(value.raw_track_id) === null ||
      integer(value.first_frame) === null || value.first_frame < 1 ||
      integer(value.last_frame) === null || value.last_frame <= value.first_frame ||
      !time(value.first_time) || !time(value.last_time) || value.last_time <= value.first_time ||
      count(value.sample_count) === null || value.sample_count < 2 || value.sample_count > 256 ||
      value.sample_count !== value.last_frame - value.first_frame + 1) return null
  const motion = value.rect_motion
  const observedVelocity = vector(motion?.pixels_per_frame)
  if (!record(motion) || !number(motion.dx) || !number(motion.dy) ||
      integer(motion.gap_frames) === null || motion.gap_frames !== value.last_frame - value.first_frame ||
      !observedVelocity || Math.abs(observedVelocity[0] - motion.dx / motion.gap_frames) > 1.1e-6 ||
      Math.abs(observedVelocity[1] - motion.dy / motion.gap_frames) > 1.1e-6) return null
  const filteredVelocity = value.filtered_velocity === null ? null : vector(value.filtered_velocity)
  if (value.filtered_velocity !== null && !filteredVelocity) return null
  return {rawId: value.raw_track_id, firstFrame: value.first_frame, lastFrame: value.last_frame,
    firstTime: value.first_time, lastTime: value.last_time, sampleCount: value.sample_count,
    displacement: [motion.dx, motion.dy], observedVelocity, filteredVelocity,
    handoff: null, handoffMotionCosine: null}
}

// Review only: every motion segment uses consecutive observations of one raw
// token. A canonical handoff jump is shown separately and never becomes raw
// movement, a vehicle identity conclusion, or a replacement counting direction.
export function buildRawMotionAuditView(item) {
  const targetId = item?.ai_tracking_id == null ? integer(item?.tracking_id) : integer(item.ai_tracking_id)
  const audit = item?.diagnosis?.raw_motion_audit
  if (targetId === null || !record(audit) || audit.schema_version !== 1 ||
      audit.scope !== 'same_raw_contiguous_observations' || audit.identity_proven !== false ||
      audit.status !== 'observed' || integer(audit.tracking_id) !== targetId ||
      audit.records_limit !== 8 || typeof audit.truncated !== 'boolean' ||
      count(audit.conflicting_frames) === null || audit.conflicting_frames !== 0 ||
      count(audit.out_of_order_frames) === null || audit.out_of_order_frames !== 0 ||
      !Array.isArray(audit.segments) || audit.segments.length < 1 || audit.segments.length > 8) return null
  const segments = audit.segments.map(segmentView)
  if (segments.some(segment => segment === null) ||
      segments.reduce((sum, segment) => sum + segment.sampleCount, 0) > 256) return null
  for (let index = 1; index < segments.length; index += 1) {
    if (segments[index].firstFrame <= segments[index - 1].lastFrame ||
        segments[index].firstTime <= segments[index - 1].lastTime) return null
  }
  const handoffs = buildObservedTrackAuditView(item)?.handoffs || []
  for (const segment of segments) {
    const matches = handoffs.filter(handoff => handoff.toRawId === segment.rawId &&
      handoff.toFrame === segment.firstFrame && Math.abs(handoff.toTime - segment.firstTime) <= 1e-6 &&
      handoff.displacement !== null)
    if (matches.length !== 1) continue
    const handoff = matches[0]
    segment.handoff = {...handoff, displacement: [...handoff.displacement]}
    segment.handoffMotionCosine = cosine(handoff.displacement, segment.displacement)
  }
  return {trackId: targetId, segments, truncated: audit.truncated}
}
