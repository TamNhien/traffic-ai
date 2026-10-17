import test from 'node:test'
import assert from 'node:assert/strict'
import { buildHumanGuardAuditView } from '../src/human-guard-audit.js'

const record = (trackId = 7, frameIndex = 108) => ({
  track_id: trackId, frame_index: frameIndex, context: 'interval_cache', policy_status: 'pending',
  strikes: 1, required_strikes: 2, decision_frame_index: 100,
  decision: { person_confidence: .8, vehicle_confidence: .05, nearby_vehicle_confidence: .02,
    overlap_iou: .9, target_coverage: .95, reject: true, rider_supported: false, hard_reject: false },
})
const item = (records, scope = 'nearby_time_window') => ({ ai_tracking_id: 7, diagnosis: { human_guard_audit: { scope, records } } })

test('Human Guard audit preserves recorded source clock and separates nearby from matched identity', () => {
  const nearby = buildHumanGuardAuditView(item([record(8)]))
  assert.equal(nearby.matched, false)
  assert.equal(nearby.records[0].age, 8)
  const matched = buildHumanGuardAuditView(item([record(8), record(7)], 'matched_track'))
  assert.equal(matched.matched, true)
  assert.deepEqual(matched.records.map(row => row.trackId), [7])
  assert.equal(buildHumanGuardAuditView(item([record(8)], 'matched_track')), null)
})

test('Human Guard audit bounds records and neutralizes malformed scores without inventing missing opinions', () => {
  const rows = Array.from({ length: 20 }, (_, index) => record(7, 108 + index))
  rows[19].decision.person_confidence = Infinity
  rows[19].decision.vehicle_confidence = '0.9'
  rows[18].decision = null
  const view = buildHumanGuardAuditView(item(rows))
  assert.equal(view.records.length, 8)
  assert.equal(view.truncated, true)
  assert.equal(view.records.at(-1).decision.person, null)
  assert.equal(view.records.at(-1).decision.direct, null)
  assert.equal(view.records.at(-2).decision, null)
  assert.equal(view.records.at(-2).age, null)
})

test('Human Guard audit remains hidden for older traces and rejects invalid scopes or frame identities', () => {
  assert.equal(buildHumanGuardAuditView({ diagnosis: {} }), null)
  assert.equal(buildHumanGuardAuditView(item([record()], 'physical_identity_proven')), null)
  assert.equal(buildHumanGuardAuditView(item([{ ...record(), frame_index: NaN }])), null)
  assert.equal(buildHumanGuardAuditView(item([{ ...record(), context: 'private/model.pt' }])), null)
})
