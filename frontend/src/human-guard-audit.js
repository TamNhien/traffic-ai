const contexts = new Set(['fresh', 'same_frame_cache', 'interval_cache', 'out_of_order', 'not_requested', 'guard_unavailable', 'no_decision'])
const statuses = new Set(['keep', 'pending', 'rejected', 'rider'])
const frame = value => Number.isSafeInteger(value) && value >= 0 ? value : null
const score = value => typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1 ? value : null

export function buildHumanGuardAuditView(item) {
  const audit = item?.diagnosis?.human_guard_audit
  if (!audit || !['matched_track', 'nearby_time_window'].includes(audit.scope) || !Array.isArray(audit.records)) return null
  const matched = audit.scope === 'matched_track'
  const records = audit.records.filter(record => record && Number.isSafeInteger(record.track_id)
    && frame(record.frame_index) !== null && contexts.has(record.context) && statuses.has(record.policy_status)
    && (!matched || Number.isSafeInteger(item.ai_tracking_id) && record.track_id === item.ai_tracking_id)
  ).slice(-8).map(record => {
    const decisionFrame = frame(record.decision_frame_index)
    const decision = record.decision && typeof record.decision === 'object' ? {
      person: score(record.decision.person_confidence), direct: score(record.decision.vehicle_confidence),
      nearby: score(record.decision.nearby_vehicle_confidence), iou: score(record.decision.overlap_iou),
      coverage: score(record.decision.target_coverage), rider: record.decision.rider_supported === true,
      reject: record.decision.reject === true, hard: record.decision.hard_reject === true,
    } : null
    return {
      trackId: record.track_id, frameIndex: record.frame_index, context: record.context,
      status: record.policy_status, strikes: frame(record.strikes), requiredStrikes: frame(record.required_strikes),
      decisionFrame, age: decision && decisionFrame !== null && record.frame_index >= decisionFrame ? record.frame_index - decisionFrame : null,
      decision,
    }
  })
  return records.length ? { matched, records, truncated: audit.truncated === true || audit.records.length > 8 } : null
}
