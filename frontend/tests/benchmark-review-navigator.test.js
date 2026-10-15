import test from 'node:test'
import assert from 'node:assert/strict'
import { buildReviewQueue, filterReviewQueue, reviewSeekStart } from '../src/benchmark-review-navigator.js'

const report = () => ({
  tolerance_seconds: 0.75,
  missed_items: [
    {ground_truth_id: 4,time: 20.2,direction:'in',vehicle_type:'bicycle',diagnosis:{reason:'crossing_gate_miss'},temporal_evidence:{status:'no_persisted_event_in_window'}},
    {ground_truth_id: 2,time: 5.1,direction:'out',vehicle_type:'motorcycle',temporal_evidence:{status:'persisted_event_claimed_by_other_gt'}},
  ],
  false_positive_items: [
    {ai_event_id: 9,time: 5.5,direction:'out',vehicle_type:'motorcycle',reason:'rescued_gap_unmatched',crossing_method:'rescued'},
    {ai_event_id: 10,time: 10.0,direction:'in',vehicle_type:'truck',crossing_method:'direct'},
  ],
})
test('scored benchmark yields all unmatched cases sorted by time', () => {
  const rows = buildReviewQueue(report(), true)
  assert.deepEqual(rows.map(row=>row.key), ['gt-2','ai-9','ai-10','gt-4'])
  assert.equal(rows.length, 4)
})
test('a nearby extra is linked as a review candidate, not as confirmed duplicate', () => {
  const rows = buildReviewQueue(report(), true)
  assert.deepEqual(rows[0].near,['ai-9'])
  assert.deepEqual(rows[1].near,['gt-2'])
  assert.deepEqual(rows[2].near,[])
  assert.equal(rows[0].conflict,true)
})
test('GT-free benchmark never fabricates a review queue', () => {
  assert.deepEqual(buildReviewQueue(report(), false), [])
  assert.deepEqual(buildReviewQueue(null,true),[])
})
test('invalid timecode cannot enter review navigation', () => {
  const r=report()
  r.missed_items.push({time:'Infinity',ground_truth_id:5})
  r.false_positive_items.push({time:-2,ai_event_id:100})
  assert.equal(buildReviewQueue(r,true).length,4)
})
test('filter by missed, extra or cases requiring temporal review', () => {
  const rows=buildReviewQueue(report(),true)
  assert.equal(filterReviewQueue(rows,'missed').length,2)
  assert.equal(filterReviewQueue(rows,'extra').length,2)
  assert.deepEqual(filterReviewQueue(rows,'conflict').map(x=>x.key),['gt-2','ai-9'])
  assert.equal(filterReviewQueue(rows,'all').length,4)
})
test('seek start is frame-safe, bounded, and never negative', () => {
  assert.equal(reviewSeekStart(0.16),0)
  assert.ok(Math.abs(reviewSeekStart(5.5)-5.1)<1e-8)
  assert.equal(reviewSeekStart(-1),0)
  assert.equal(reviewSeekStart(7,100),5)
})
test('input report is unchanged by navigation data assembly', () => {
  const input=report()
  const before=JSON.stringify(input)
  buildReviewQueue(input,true)
  assert.equal(JSON.stringify(input),before)
})
