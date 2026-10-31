import test from 'node:test'
import assert from 'node:assert/strict'
import { buildBenchmarkFocusQueue } from '../src/benchmark-focus.js'
test('V0.5.130 focus queue prioritizes crowded GT and bicycle misses without changing counts', () => {
  const report = { missed_items:[{time:59.446,vehicle_type:'motorcycle',temporal_evidence:{status:'persisted_event_claimed_by_other_gt'}},{time:591.091,vehicle_type:'bicycle'}],false_positive_items:[{time:54.294,reason:'rescued_gap_unmatched'},{time:759.52,reason:'spatial_duplicate_near_gt'}],direction_mismatch_items:[{time:58.984}],class_mismatch_items:[{time:641.981}] }
  const snapshot=JSON.stringify(report)
  const q=buildBenchmarkFocusQueue(report)
  assert.equal(q.length,6)
  assert.deepEqual(q.map(x=>x.focus),['clustered','bicycle','rescue','duplicate','direction','class'])
  assert.ok(q.every(x=>x.identityProven===false))
  assert.equal(JSON.stringify(report),snapshot)
})
test('V0.5.130 focus queue is absent for unscored or malformed benchmark',()=>{
  assert.deepEqual(buildBenchmarkFocusQueue({missed_items:[{time:12}]},false),[])
  assert.deepEqual(buildBenchmarkFocusQueue({missed_items:[{time:'12'},{time:NaN},{time:-1}]},true),[])
  assert.deepEqual(buildBenchmarkFocusQueue(null),[])
})
