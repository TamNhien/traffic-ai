/** V0.5.91: read-only timecode navigation for unmatched benchmark crossings.
 * Never infer that two nearby crossings belong to the same physical vehicle.
 * No scoring, class, GT or backend event mutation is performed here.
 */
const validTime = value => typeof value === 'number' && Number.isFinite(value) && value >= 0

export function buildReviewQueue(report, scoringAvailable) {
  if (!scoringAvailable || !report || !Array.isArray(report.missed_items) ||
      !Array.isArray(report.false_positive_items)) return []
  const misses = report.missed_items.filter(row => validTime(row?.time)).map((row, index) => ({
    key: `gt-${row.ground_truth_id ?? index}`, kind: 'missed', time: row.time,
    vehicleType: row.vehicle_type, direction: row.direction,
    reason: row.diagnosis?.reason || 'review_video',
    conflict: row.temporal_evidence?.status === 'persisted_event_claimed_by_other_gt',
    id: row.ground_truth_id ?? null, near: [],
  }))
  const extras = report.false_positive_items.filter(row => validTime(row?.time)).map((row, index) => ({
    key: `ai-${row.ai_event_id ?? index}`, kind: 'extra', time: row.time,
    vehicleType: row.vehicle_type, direction: row.direction,
    reason: row.reason || 'review_video', method: row.crossing_method,
    conflict: row.near_matched_ai_event_id != null || row.near_matched_time_delta != null,
    id: row.ai_event_id ?? null, near: [],
  }))
  const window = Math.min(3, Math.max(0.05, Number(report.tolerance_seconds) || 0.75))
  // Temporal proximity merely suggests review candidates; no identity resolution.
  for (const row of [...misses, ...extras]) {
    const opposites = row.kind === 'missed' ? extras : misses
    row.near = opposites.filter(other => Math.abs(other.time - row.time) <= window)
      .sort((a,b) => Math.abs(a.time - row.time) - Math.abs(b.time - row.time) || a.key.localeCompare(b.key))
      .map(other => other.key)
  }
  return [...misses, ...extras].sort((a,b) => a.time - b.time || a.key.localeCompare(b.key))
}

export function filterReviewQueue(cases, filter) {
  if (filter === 'missed' || filter === 'extra') return cases.filter(row => row.kind === filter)
  if (filter === 'conflict') return cases.filter(row => row.conflict || row.near.length > 0)
  return cases
}

export function reviewSeekStart(time, leadSeconds = 0.4) {
  if (!validTime(time)) return 0
  return Math.max(0, time - Math.max(0, Math.min(2, Number(leadSeconds) || 0)))
}
