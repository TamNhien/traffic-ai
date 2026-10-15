import test from 'node:test'
import assert from 'node:assert/strict'
import { buildPassageCycleReview } from '../src/benchmark-passage-cycles.js'
const caseReport = () => ({ matched_items:[
 { ai_event_id:1, tracking_id:44, ai_time:5, ai_direction:'in', crossing_method:'direct'},
 { ai_event_id:2, tracking_id:55, ai_time:6, ai_direction:'in', crossing_method:'direct'},
 ], false_positive_items:[
 {ai_event_id:3,tracking_id:44,time:8,direction:'out',crossing_method:'rescued'},
 ]})
test('matching canonical IDs link a review pair, not a duplicate claim',()=>{
 const rows=buildPassageCycleReview(caseReport())
 assert.equal(rows.length,1)
 assert.equal(rows[0].track,44)
 assert.equal(rows[0].gap,3)
 assert.equal(rows[0].hasExtra,true)
 assert.equal(rows[0].identityProven,false)
})
test('unrelated tracks or long window are not paired',()=>{
 assert.equal(buildPassageCycleReview(caseReport(),2).length,0)
 assert.equal(buildPassageCycleReview(caseReport(),40).length,0)
})
test('a legitimate same-track return is not automatically rejected',()=>{
 const r=caseReport(); r.false_positive_items[0].time=9
 const before=JSON.stringify(r)
 const pairs=buildPassageCycleReview(r)
 assert.equal(pairs[0].later.direction,'out')
 assert.equal(JSON.stringify(r),before)
})
test('invalid/missing inputs fail closed',()=>{
 assert.deepEqual(buildPassageCycleReview(null),[])
 assert.deepEqual(buildPassageCycleReview({matched_items:[]}),[])
 const r=caseReport();r.matched_items[0].ai_time='NaN'
 assert.deepEqual(buildPassageCycleReview(r),[])
})
