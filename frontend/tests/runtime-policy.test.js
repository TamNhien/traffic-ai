import {test} from 'node:test'
import assert from 'node:assert/strict'
import {filterPolicyRows, policyFlagLabel, runtimePolicyView} from '../src/runtime-policy.js'

function response() {
  return {available:true,session_id:213,status:'available',metadata_verification:'prefix_only',
    runtime:{ai_runtime_version:'0.5.118',worker_source_sha256:'a'.repeat(64)},
    policy:{schema_version:1,digest_scope:'allowlisted_effective_algorithm_parameters',capture_status:'complete',
      configuration:{worker:{_endpoint_precision_guard_enabled:true,_endpoint_rescue_guard_enabled:false,detection_roi_mode:'full'},
        resolver:{max_gap_frames:30},primary:{history_gap_frames:45},detector:{confidence_threshold:.17}},
      component_presence:{worker:'present',resolver:'present',primary:'present',anchor_span:'absent',heavy_center:'absent',two_wheel_center:'absent',human_guard:'absent',detector:'present'},
      missing_fields:[],invalid_fields:[],unreadable_fields:[],configuration_sha256:'b'.repeat(64)}}
}

test('historical version, false flags and scoped parameters retain their recorded values',()=>{
  const view = runtimePolicyView(response(),213)
  assert.equal(view.available,true)
  assert.equal(view.runtimeVersion,'0.5.118')
  assert.equal(view.endpointGuard,'Bật')
  assert.equal(view.rescueGuard,'Tắt')
  assert.equal(view.rows.length,6)
  assert.equal(view.captureStatus,'complete')
  assert.equal(view.absentCount,4)
  assert.equal(view.configurationDigest,'b'.repeat(64))
})

test('missing historical flags remain unknown rather than disabled',()=>{
  const data=response()
  delete data.policy.configuration.worker._endpoint_rescue_guard_enabled
  data.policy.capture_status='partial'
  data.policy.missing_fields=['worker._endpoint_rescue_guard_enabled']
  const view=runtimePolicyView(data,213)
  assert.equal(view.rescueGuard,'Chưa ghi')
  assert.equal(view.missingCount,1)
  assert.equal(view.captureStatus,'partial')
  assert.equal(policyFlagLabel('false'),'Chưa ghi')
  assert.equal(policyFlagLabel(0),'Chưa ghi')
})

test('legacy and unavailable states never expose or substitute payload configuration',()=>{
  for(const status of ['not_recorded','invalid','unavailable']) {
    const data={...response(),available:false,status}
    const view=runtimePolicyView(data,213)
    assert.equal(view.state,status)
    assert.equal(view.available,false)
    assert.equal(view.runtimeVersion,null)
    assert.deepEqual(view.rows,[])
    assert.equal(view.rescueGuard,'Chưa ghi')
  }
})

test('a stale response from another session cannot become the current policy',()=>{
  assert.equal(runtimePolicyView(response(),214).state,'invalid')
  assert.equal(runtimePolicyView(response(),null).state,'invalid')
  assert.equal(runtimePolicyView({...response(),session_id:'213'},213).state,'invalid')
})

test('malformed or ambiguous metadata cannot appear as a verified scoped capture',()=>{
  const mutations=[
    data=>{data.metadata_verification='full_trace'},
    data=>{data.policy.configuration_sha256='wrong'},
    data=>{data.policy.schema_version=2},
    data=>{data.policy.digest_scope='complete_run'},
    data=>{data.policy.capture_status='unavailable'},
    data=>{data.policy.configuration.worker.confidence=Infinity},
    data=>{data.policy.configuration.worker.api_key='private-token'},
    data=>{data.policy.configuration.worker.detection_roi_mode='private-value'},
    data=>{data.policy.configuration.extra={secret:true}},
    data=>{data.policy.configuration.worker={nested:{secret:7}}},
    data=>{data.policy.component_presence.worker='absent'},
    data=>{data.policy.missing_fields=['/private/url']},
    data=>{data.policy.missing_fields=['worker.iou']},
    data=>{data.policy.component_presence.detector='absent';delete data.policy.configuration.detector},
    data=>{data.runtime.ai_runtime_version='/private/path'},
    data=>{data.runtime.worker_source_sha256='secret'},
  ]
  for(const mutation of mutations){const data=response();mutation(data);assert.equal(runtimePolicyView(data,213).state,'invalid')}
})

test('present components and absent components must have unambiguous structure',()=>{
  const data=response()
  delete data.policy.configuration.primary
  assert.equal(runtimePolicyView(data,213).state,'invalid')
  const missingPresence=response()
  delete missingPresence.policy.component_presence.primary
  assert.equal(runtimePolicyView(missingPresence,213).state,'invalid')
})

test('partial capture counts diagnostic fields and does not mutate API data',()=>{
  const data=response()
  data.policy.capture_status='partial'
  data.policy.invalid_fields=['worker.iou']
  data.policy.unreadable_fields=['primary.segment_margin']
  const before=structuredClone(data)
  const view=runtimePolicyView(data,213)
  assert.equal(view.missingCount,2)
  assert.deepEqual(data,before)
})

test('parameter lookup searches group, field and displayed value without changing rows',()=>{
  const rows=runtimePolicyView(response(),213).rows
  assert.equal(filterPolicyRows(rows,'  RESCUE ')[0].name,'_endpoint_rescue_guard_enabled')
  assert.equal(filterPolicyRows(rows,'Vạch đếm')[0].name,'history_gap_frames')
  assert.equal(filterPolicyRows(rows,'45').length,1)
  assert.equal(filterPolicyRows(rows,'không có').length,0)
  assert.equal(filterPolicyRows(rows,'').length,rows.length)
  assert.equal(rows.length,6)
})
