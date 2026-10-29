import test from 'node:test'
import assert from 'node:assert/strict'
import { buildRawMotionAuditView } from '../src/raw-motion-audit.js'

const segment = (patch = {}) => ({raw_track_id: 331821, first_frame: 18860, last_frame: 18862,
  first_time: 754.36, last_time: 754.44, sample_count: 3,
  rect_motion: {dx: -9.687, dy: -15.38, gap_frames: 2, pixels_per_frame: [-4.8435, -7.69]},
  filtered_velocity: [-2.1, 8.2], ...patch})
const item = () => ({ai_tracking_id: 296297, matched: 144, diagnosis: {raw_motion_audit: {
  schema_version: 1, scope: 'same_raw_contiguous_observations', tracking_id: 296297,
  identity_proven: false, status: 'observed', records_limit: 8,
  segments: [segment()], truncated: false, conflicting_frames: 0, out_of_order_frames: 0,
}, observed_track_audit: {schema_version: 1, scope: 'canonical_track_window', tracking_id: 296297,
  identity_proven: false, status: 'observed', target: {frames: 13}, peers: [], truncated: false,
  conflicting_frames: 0, raw_id_handoffs: [{from_raw_track_id: 312739, to_raw_track_id: 331821,
    from_frame: 18842, to_frame: 18860, from_time: 753.64, to_time: 754.36,
    gap_frames: 18, rect_displacement: [-56.76, 229.647]}],
}}})

test('legacy and unavailable audit remains hidden', () => {
  for (const value of [null, {}, {diagnosis: {}}]) assert.equal(buildRawMotionAuditView(value), null)
  const input = item()
  input.diagnosis.raw_motion_audit.status = 'unavailable'
  assert.equal(buildRawMotionAuditView(input), null)
})
test('raw motion stays separate from alias jump and filtered velocity', () => {
  const result = buildRawMotionAuditView(item()).segments[0]
  assert.deepEqual(result.displacement, [-9.687, -15.38])
  assert.deepEqual(result.filteredVelocity, [-2.1, 8.2])
  assert.deepEqual(result.handoff.displacement, [-56.76, 229.647])
  assert.ok(result.handoffMotionCosine < 0)
})
test('exact canonical owner and supported scope are required', () => {
  for (const patch of [{tracking_id: 1}, {schema_version: 2}, {identity_proven: true}, {scope: 'nearby'}]) {
    const input = item()
    Object.assign(input.diagnosis.raw_motion_audit, patch)
    assert.equal(buildRawMotionAuditView(input), null)
  }
  const input = item()
  input.tracking_id = 296297
  input.ai_tracking_id = '296297'
  assert.equal(buildRawMotionAuditView(input), null)
})
test('contiguous source observations cannot be invented across a missing frame', () => {
  for (const patch of [{sample_count: 2}, {last_frame: 18863}, {first_time: '754.36'},
    {last_time: 754.3}, {raw_track_id: true}, {sample_count: 1}]) {
    const input = item()
    input.diagnosis.raw_motion_audit.segments = [segment(patch)]
    assert.equal(buildRawMotionAuditView(input), null)
  }
})
test('motion displacement and per-frame averages must agree and remain finite', () => {
  for (const motion of [{dx: NaN, dy: 2, gap_frames: 2, pixels_per_frame: [0, 1]},
    {dx: 2, dy: 2, gap_frames: 3, pixels_per_frame: [1, 1]},
    {dx: 2, dy: 2, gap_frames: 2, pixels_per_frame: [1, 3]},
    {dx: 2, dy: 2, gap_frames: 2, pixels_per_frame: [1, Infinity]}]) {
    const input = item()
    input.diagnosis.raw_motion_audit.segments = [segment({rect_motion: motion})]
    assert.equal(buildRawMotionAuditView(input), null)
  }
})
test('handoff comparison requires exact raw token, start frame and source time', () => {
  for (const patch of [{to_raw_track_id: 1}, {to_frame: 18859, gap_frames: 17}, {to_time: 754.4}]) {
    const input = item()
    Object.assign(input.diagnosis.observed_track_audit.raw_id_handoffs[0], patch)
    const result = buildRawMotionAuditView(input).segments[0]
    assert.equal(result.handoff, null)
    assert.equal(result.handoffMotionCosine, null)
  }
})
test('missing or ambiguous handoffs do not remove independently observed raw movement', () => {
  const input = item()
  delete input.diagnosis.observed_track_audit
  assert.deepEqual(buildRawMotionAuditView(input).segments[0].displacement, [-9.687, -15.38])
  const duplicate = item()
  duplicate.diagnosis.observed_track_audit.raw_id_handoffs.push(
    structuredClone(duplicate.diagnosis.observed_track_audit.raw_id_handoffs[0]))
  assert.equal(buildRawMotionAuditView(duplicate).segments[0].handoff, null)
})
test('stationary raw segment does not imply agreement or an inferred direction', () => {
  const input = item()
  input.diagnosis.raw_motion_audit.segments = [segment({rect_motion: {dx: 0, dy: 0,
    gap_frames: 2, pixels_per_frame: [0, 0]}, filtered_velocity: null})]
  const result = buildRawMotionAuditView(input).segments[0]
  assert.equal(result.handoffMotionCosine, null)
  assert.equal(result.filteredVelocity, null)
  assert.equal(Object.hasOwn(result, 'direction'), false)
})
test('conflicting or unordered observations cannot appear as reliable motion', () => {
  for (const patch of [{conflicting_frames: 1}, {out_of_order_frames: 1}, {truncated: 'false'}, {records_limit: 100}]) {
    const input = item()
    Object.assign(input.diagnosis.raw_motion_audit, patch)
    assert.equal(buildRawMotionAuditView(input), null)
  }
})
test('separate raw segments retain gap boundaries without cross-segment velocity', () => {
  const input = item()
  input.diagnosis.raw_motion_audit.segments.push(segment({first_frame: 18865, last_frame: 18867,
    first_time: 754.56, last_time: 754.64, raw_track_id: 331822}))
  input.diagnosis.raw_motion_audit.truncated = true
  const result = buildRawMotionAuditView(input)
  assert.equal(result.segments.length, 2)
  assert.equal(result.segments[1].handoff, null)
  assert.equal(result.truncated, true)
  input.diagnosis.raw_motion_audit.segments[1].first_frame = 18861
  assert.equal(buildRawMotionAuditView(input), null)
})
test('output is bounded and does not mutate benchmark data or alias records', () => {
  const input = item()
  const before = structuredClone(input)
  const result = buildRawMotionAuditView(input)
  result.segments[0].displacement[0] = 999
  result.segments[0].handoff.displacement[0] = 999
  assert.deepEqual(input, before)
  input.diagnosis.raw_motion_audit.segments = Array.from({length: 9}, () => segment())
  assert.equal(buildRawMotionAuditView(input), null)
})
test('the combined segment observations obey the 256-frame window limit', () => {
  const input = item()
  const populate = samples => {
    input.diagnosis.raw_motion_audit.segments = Array.from({length: 8}, (_, index) => {
      const first = 100 + index * 40
      const gap = samples - 1
      return segment({raw_track_id: 900 + index, first_frame: first, last_frame: first + gap,
        first_time: (first - 1) / 25, last_time: (first + gap - 1) / 25, sample_count: samples,
        rect_motion: {dx: gap, dy: gap * 2, gap_frames: gap, pixels_per_frame: [1, 2]}})
    })
  }
  populate(32)
  assert.equal(buildRawMotionAuditView(input).segments.length, 8)
  populate(34)
  assert.equal(buildRawMotionAuditView(input), null)
})
