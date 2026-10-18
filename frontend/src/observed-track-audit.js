const integer = value => Number.isSafeInteger(value) ? value : null
const count = value => integer(value) !== null && value >= 0 ? value : null
const time = value => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null
const ratio = value => time(value) !== null && value <= 1 ? value : null
const vector = value => Array.isArray(value) && value.length === 2
  && value.every(part => typeof part === 'number' && Number.isFinite(part)) ? [...value] : null
const motionVector = value => vector(value?.pixels_per_frame)

function cosine(left, right) {
  if (!left || !right) return null
  const length = Math.hypot(...left) * Math.hypot(...right)
  if (length <= 1e-9 || !Number.isFinite(length)) return null
  return Math.max(-1, Math.min(1, (left[0] * right[0] + left[1] * right[1]) / length))
}

// Treat the server's geometry as review evidence. Never infer vehicle identity
// or update a benchmark score from overlap, a shared ID, or similar velocities.
export function buildObservedTrackAuditView(item) {
  const audit = item?.diagnosis?.observed_track_audit
  const targetId = integer(item?.ai_tracking_id) ?? integer(item?.tracking_id)
  if (!audit || audit.schema_version !== 1 || audit.scope !== 'canonical_track_window'
    || audit.status !== 'observed' || audit.identity_proven !== false || targetId === null
    || integer(audit.tracking_id) !== targetId || count(audit.target?.frames) === null
    || audit.target.frames === 0) return null
  const nearId = integer(item?.near_matched_tracking_id)
  const allPeers = Array.isArray(audit.peers) ? audit.peers : []
  const peers = allPeers.filter(peer => peer && integer(peer.tracking_id) !== null
    && peer.tracking_id !== targetId && peer.identity_proven === false
    && count(peer.co_visible_frames) !== null && peer.co_visible_frames >= 1
    && count(peer.nested_frames) !== null && peer.nested_frames >= 1
    && peer.nested_frames <= peer.co_visible_frames
    && count(peer.first_frame) !== null && count(peer.last_frame) !== null
    && peer.last_frame >= peer.first_frame && time(peer.first_time) !== null
    && time(peer.last_time) !== null && peer.last_time >= peer.first_time
  ).map(peer => ({
    trackId: peer.tracking_id, coVisibleFrames: peer.co_visible_frames,
    nestedFrames: peer.nested_frames, firstFrame: peer.first_frame, lastFrame: peer.last_frame,
    firstTime: peer.first_time, lastTime: peer.last_time,
    containmentMin: ratio(peer.containment_min), containmentMax: ratio(peer.containment_max),
    actualMotionCosine: cosine(motionVector(peer.target_rect_motion), motionVector(peer.peer_rect_motion)),
    filteredVelocityCosine: cosine(vector(peer.target_filtered_velocity), vector(peer.peer_filtered_velocity)),
    nearMatchedEvent: nearId !== null && peer.tracking_id === nearId,
  })).sort((a, b) => Number(b.nearMatchedEvent) - Number(a.nearMatchedEvent)
    || b.nestedFrames - a.nestedFrames || a.trackId - b.trackId).slice(0, 4)
  const rawHandoffs = Array.isArray(audit.raw_id_handoffs) ? audit.raw_id_handoffs : []
  const handoffs = rawHandoffs.filter(record => record
    && integer(record.from_raw_track_id) !== null && integer(record.to_raw_track_id) !== null
    && record.from_raw_track_id !== record.to_raw_track_id
    && count(record.from_frame) !== null && count(record.to_frame) !== null
    && record.to_frame > record.from_frame && count(record.gap_frames) !== null
    && record.gap_frames === record.to_frame - record.from_frame
    && time(record.from_time) !== null && time(record.to_time) !== null
    && record.to_time >= record.from_time
  ).slice(-8).map(record => ({
    fromRawId: record.from_raw_track_id, toRawId: record.to_raw_track_id,
    fromFrame: record.from_frame, toFrame: record.to_frame,
    fromTime: record.from_time, toTime: record.to_time, gapFrames: record.gap_frames,
    displacement: vector(record.rect_displacement),
  }))
  if (!peers.length && !handoffs.length) return null
  return { trackId: targetId, peers, handoffs,
    truncated: audit.truncated === true || allPeers.length > 4 || rawHandoffs.length > 8,
    conflictingFrames: count(audit.conflicting_frames) ?? 0,
  }
}
