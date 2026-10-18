import test from 'node:test'
import assert from 'node:assert/strict'
import { verifiedPassageSummary } from '../src/passage-evidence-summary.js'

const report = () => ({
  missed: 6,
  missed_items: Array.from({length: 6}, (_, i) => ({ground_truth_id: i + 1})),
  temporal_assignment_audit: {
    missed_with_claimed_persisted_event: 4,
    missed_without_persisted_event_in_window: 2,
    identity_proven: false, scope: 'timestamp_only_one_to_one',
  },
})

test('display 4 timecode assignment conflicts and 2 with no event, with caution', () => {
  const summary = verifiedPassageSummary(report(), true)
  assert.equal(summary.claimed, 4)
  assert.equal(summary.withoutEvent, 2)
  assert.equal(summary.identityProven, false)
  assert.match(summary.detail, /không xác nhận cùng xe/)
})
test('absent scoring or historical old report cannot invent provenance', () => {
  assert.equal(verifiedPassageSummary(report(), false), null)
  const old = report()
  delete old.temporal_assignment_audit
  assert.equal(verifiedPassageSummary(old, true), null)
})
test('inconsistent counts fail closed rather than display false certainty', () => {
  const bad = report()
  bad.temporal_assignment_audit.missed_without_persisted_event_in_window = 1
  assert.equal(verifiedPassageSummary(bad, true), null)
  bad.temporal_assignment_audit.missed_without_persisted_event_in_window = 2
  bad.temporal_assignment_audit.identity_proven = true
  assert.equal(verifiedPassageSummary(bad, true), null)
})
test('non-integer and missing values fail closed', () => {
  const bad = report()
  bad.temporal_assignment_audit.missed_with_claimed_persisted_event = '4'
  assert.equal(verifiedPassageSummary(bad, true), null)
  bad.temporal_assignment_audit.missed_with_claimed_persisted_event = 4
  bad.missed = 5
  assert.equal(verifiedPassageSummary(bad, true), null)
})
