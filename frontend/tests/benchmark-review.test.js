import {test} from 'node:test'
import assert from 'node:assert/strict'
import {shouldShowTemporalCompetitionReview} from '../src/benchmark-review.js'

const report = (gt, ai, missed=0, extra=0) => ({
  ground_truth_total: gt,
  ai_total: ai,
  temporal_assignment_audit: {
    missed_with_claimed_persisted_event: missed,
    false_positives_near_assigned_ground_truth: extra,
  },
})

test('v0.5.88 review is shown for GT != AI when there is temporal competition', () => {
  // Benchmark #62: GT149, AI150, 4 GT and 2 AI require visual review.
  assert.equal(shouldShowTemporalCompetitionReview(report(149,150,4,2), true), true)
  assert.equal(shouldShowTemporalCompetitionReview(report(149,150,4,0), true), true)
  assert.equal(shouldShowTemporalCompetitionReview(report(149,150,0,2), true), true)
})

test('v0.5.88 review is shown for GT = AI when there is temporal competition', () => {
  assert.equal(shouldShowTemporalCompetitionReview(report(1,1,1,1), true), true)
})

test('v0.5.88 no evidence means no review, independent of totals', () => {
  assert.equal(shouldShowTemporalCompetitionReview(report(149,150,0,0), true), false)
  assert.equal(shouldShowTemporalCompetitionReview(report(149,149,0,0), true), false)
})

test('v0.5.88 GT not ready means no speculative temporal review', () => {
  assert.equal(shouldShowTemporalCompetitionReview(report(0,150,2,3), false), false)
  assert.equal(shouldShowTemporalCompetitionReview(null, false), false)
  assert.equal(shouldShowTemporalCompetitionReview({ground_truth_total:149,ai_total:150}, true), false)
})
