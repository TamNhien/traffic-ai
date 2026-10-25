import {test} from 'node:test'
import assert from 'node:assert/strict'
import {runtimeReleaseStatus} from '../src/runtime-release-status.js'

function status(version, extra={}) {
  return {ai_service:'ready', ai:{service:'ai-service',status:'ready',version,...extra}}
}

test('the loaded UI and a ready AI with equal versions match',()=>{
  assert.deepEqual(runtimeReleaseStatus('0.5.117',status('0.5.117')),{
    uiVersion:'0.5.117',aiVersion:'0.5.117',aiReady:true,state:'matching',
  })
})

test('a mismatched AI version never replaces the loaded UI build identity',()=>{
  assert.deepEqual(runtimeReleaseStatus('0.5.115',status('0.5.116')),{
    uiVersion:'0.5.115',aiVersion:'0.5.116',aiReady:true,state:'mismatch',
  })
  assert.equal(runtimeReleaseStatus('0.5.117',status('0.5.116')).state,'mismatch')
})

test('unavailable and absent AI responses remain unknown rather than mismatched',()=>{
  for (const payload of [null,undefined,{},[],{ai_service:'unavailable',ai:null},
    {ai_service:'unavailable',ai:{service:'ai-service',status:'ready',version:'0.5.116'}},
    status('0.5.116',{status:'error'}),status('0.5.116',{service:'backend'})]) {
    const result = runtimeReleaseStatus('0.5.117',payload)
    assert.equal(result.state,'unknown')
    assert.equal(result.aiVersion,null)
    assert.equal(result.aiReady,false)
  }
})

test('invalid or missing versions on a ready service do not trigger a mismatch',()=>{
  for (const version of [undefined,null,117,{},[],true,'','unknown','0.5','<script>1.2.3</script>','1.2.3'.repeat(40)]) {
    const result = runtimeReleaseStatus('0.5.117',status(version))
    assert.equal(result.aiReady,true)
    assert.equal(result.aiVersion,null)
    assert.equal(result.state,'unknown')
  }
  assert.equal(runtimeReleaseStatus(null,status('0.5.117')).state,'unknown')
})

test('normalization tolerates surrounding whitespace without altering the payload',()=>{
  const ai = Object.freeze({service:'ai-service',status:'ready',version:' 0.5.117 '})
  const payload = Object.freeze({ai_service:'ready',ai})
  assert.deepEqual(runtimeReleaseStatus(' 0.5.117 ',payload),{
    uiVersion:'0.5.117',aiVersion:'0.5.117',aiReady:true,state:'matching',
  })
  assert.equal(payload.ai.version,' 0.5.117 ')
})

test('valid prerelease and build metadata remain visible for comparison',()=>{
  assert.equal(runtimeReleaseStatus('0.5.117-rc.1',status('0.5.117')).state,'mismatch')
  assert.equal(runtimeReleaseStatus('0.5.117+build.2',status('0.5.117+build.2')).state,'matching')
})

test('malformed containers cannot masquerade as a ready AI health result',()=>{
  for (const ai of [null,undefined,[],false,117,'0.5.116']) {
    assert.equal(runtimeReleaseStatus('0.5.117',{ai_service:'ready',ai}).state,'unknown')
  }
})
