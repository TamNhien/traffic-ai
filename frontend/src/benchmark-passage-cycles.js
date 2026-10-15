/** V0.5.92: read-only candidate passages with a reused canonical tracker ID.
 * Same canonical ID or opposite directions does NOT establish duplicate counts.
 * Actual raw-token witnesses require the verified trace ZIP CLI audit.
 */
export function buildPassageCycleReview(report, maxGapSeconds = 12) {
  if (!report || !Number.isFinite(maxGapSeconds) || maxGapSeconds <= 0 || maxGapSeconds > 30 ||
      !Array.isArray(report.matched_items) || !Array.isArray(report.false_positive_items)) return []
  const events = [
    ...report.matched_items.map(row => ({ id:row.ai_event_id, track:row.tracking_id,
      time:row.ai_time, direction:row.ai_direction, method:row.crossing_method, extra:false })),
    ...report.false_positive_items.map(row => ({ id:row.ai_event_id, track:row.tracking_id,
      time:row.time, direction:row.direction, method:row.crossing_method, extra:true })),
  ].filter(row => Number.isInteger(row.id) && Number.isInteger(row.track) &&
    typeof row.time === 'number' && Number.isFinite(row.time) && row.time >= 0)
  const groups = new Map()
  for (const e of events) {
    if (!groups.has(e.track)) groups.set(e.track, [])
    groups.get(e.track).push(e)
  }
  const out = []
  for (const [track, rows] of groups) {
    rows.sort((a,b)=>a.time-b.time || a.id-b.id)
    for (let j=0;j<rows.length;j++) {
      for (let i=j-1;i>=0;i--) {
        const diff = rows[j].time-rows[i].time
        if (diff > maxGapSeconds) break
        if (diff < 0 || rows[j].id === rows[i].id) continue
        out.push({ key:`${rows[i].id}-${rows[j].id}`, track,
          earlier:rows[i], later:rows[j], gap:diff,
          hasExtra: rows[i].extra || rows[j].extra,
          identityProven:false })
      }
    }
  }
  return out.sort((a,b)=>a.later.time-b.later.time || a.earlier.time-b.earlier.time)
}
