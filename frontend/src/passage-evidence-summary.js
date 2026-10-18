/** V0.5.99. Explain matcher contention without inventing vehicle identity. */
const count = value => Number.isSafeInteger(value) && value >= 0 ? value : null

export function verifiedPassageSummary(report, scored) {
  if (!scored || !report || !Array.isArray(report.missed_items)) return null
  const misses = count(report.missed)
  const audit = report.temporal_assignment_audit
  if (misses === null || misses !== report.missed_items.length || !audit ||
      audit.identity_proven !== false || audit.scope !== 'timestamp_only_one_to_one') return null
  const claimed = count(audit.missed_with_claimed_persisted_event)
  const unclaimed = count(audit.missed_without_persisted_event_in_window)
  if (claimed === null || unclaimed === null || claimed + unclaimed !== misses) return null
  return {
    claimed,
    withoutEvent: unclaimed,
    totalMissed: misses,
    identityProven: false,
    detail: `${claimed} GT gần sự kiện DB đã được ghép GT khác; ${unclaimed} GT chưa có event trong cửa sổ chấm. Đây là trạng thái ghép timecode, không xác nhận cùng xe hoặc detector bỏ sót.`,
  }
}
