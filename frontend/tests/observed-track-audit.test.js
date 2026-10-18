import test from 'node:test'
import assert from 'node:assert/strict'
import { buildObservedTrackAuditView } from '../src/observed-track-audit.js'

const peer = (id = 182056) => ({
  tracking_id: id, identity_proven: false, co_visible_frames: 5, nested_frames: 5,
  first_frame: 12305, last_frame: 12318, first_time: 492.16, last_time: 492.68,
  containment_min: 0.937, containment_max: 1,
  target_rect_motion: { pixels_per_frame: [-4.4705, -1.986] },
  peer_rect_motion: { pixels_per_frame: [-3.938, -9.7995] },
  target_filtered_velocity: [-5.883145, -9.979731],
  peer_filtered_velocity: [-2.165977, -5.389825],
})
const item = () => ({ ai_tracking_id: 181574, near_matched_tracking_id: 182056,
  diagnosis: { observed_track_audit: { schema_version: 1, scope: 'canonical_track_window',
    tracking_id: 181574, identity_proven: false, status: 'observed', target: { frames: 16 },
    peers: [peer()], raw_id_handoffs: [], conflicting_frames: 0, truncated: false } } })

test('old and missing trace evidence is hidden', () => {
  for (const value of [null, {}, { diagnosis: {} }]) assert.equal(buildObservedTrackAuditView(value), null)
})
test('measured motion and filtered velocity remain distinct', () => {
  const result = buildObservedTrackAuditView(item())
  assert.ok(result.peers[0].actualMotionCosine < 0.8)
  assert.ok(result.peers[0].filteredVelocityCosine > 0.98)
  assert.equal(result.peers[0].nearMatchedEvent, true)
})
test('audit must refer to the actual event canonical track', () => {
  const input = item()
  input.ai_tracking_id = 999
  assert.equal(buildObservedTrackAuditView(input), null)
})
test('unsupported identity claims and schemas are rejected', () => {
  for (const [key, value] of [['identity_proven', true], ['schema_version', 2], ['scope', 'nearby_tracks']]) {
    const input = item()
    input.diagnosis.observed_track_audit[key] = value
    assert.equal(buildObservedTrackAuditView(input), null)
  }
})
test('near matched peer is preferred without changing the input or scores', () => {
  const input = item()
  input.matched = 143
  input.diagnosis.observed_track_audit.peers = [peer(999), peer(182056)]
  const original = structuredClone(input)
  const result = buildObservedTrackAuditView(input)
  assert.equal(result.peers[0].trackId, 182056)
  assert.deepEqual(input, original)
})
test('malformed peer time, identity and sample counts are ignored', () => {
  const variants = [{ first_time: '492.16' }, { last_time: 490 }, { nested_frames: 6 },
    { identity_proven: true }, { tracking_id: 181574 }, { co_visible_frames: true }]
  for (const patch of variants) {
    const input = item()
    Object.assign(input.diagnosis.observed_track_audit.peers[0], patch)
    assert.equal(buildObservedTrackAuditView(input), null)
  }
})
test('nonfinite vectors and missing geometry cannot become zero or agreement', () => {
  const input = item()
  const data = input.diagnosis.observed_track_audit.peers[0]
  data.containment_min = null
  data.target_filtered_velocity = [NaN, 0]
  data.target_rect_motion = { pixels_per_frame: [0, 0] }
  const result = buildObservedTrackAuditView(input).peers[0]
  assert.equal(result.containmentMin, null)
  assert.equal(result.actualMotionCosine, null)
  assert.equal(result.filteredVelocityCosine, null)
})
test('handoff exposes the measured gap but does not identify a new vehicle', () => {
  const input = item()
  input.diagnosis.observed_track_audit.peers = []
  input.diagnosis.observed_track_audit.raw_id_handoffs = [{
    from_raw_track_id: 312739, to_raw_track_id: 331821, from_frame: 18842,
    to_frame: 18860, from_time: 753.64, to_time: 754.36, gap_frames: 18,
    rect_displacement: [-56.76, 229.647],
  }]
  const result = buildObservedTrackAuditView(input)
  assert.equal(result.handoffs[0].gapFrames, 18)
  assert.deepEqual(result.handoffs[0].displacement, [-56.76, 229.647])
})
test('duplicate, reverse clock and inconsistent handoffs are hidden', () => {
  const input = item()
  input.diagnosis.observed_track_audit.peers = []
  input.diagnosis.observed_track_audit.raw_id_handoffs = [{
    from_raw_track_id: 4, to_raw_track_id: 4, from_frame: 10, to_frame: 12,
    from_time: 0.4, to_time: 0.48, gap_frames: 5,
  }]
  assert.equal(buildObservedTrackAuditView(input), null)
})
test('peer output is bounded and marks truncation', () => {
  const input = item()
  input.diagnosis.observed_track_audit.peers = Array.from({ length: 10 }, (_, index) => peer(index))
  const result = buildObservedTrackAuditView(input)
  assert.equal(result.peers.length, 4)
  assert.equal(result.truncated, true)
})
