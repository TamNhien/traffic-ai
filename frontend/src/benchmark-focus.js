// V0.5.130: read-only priority navigation. Time matching never proves identity.
const rules = {
  clustered: ['Cụm xe sát nhau', 0],
  bicycle: ['Xe đạp chưa ghép', 1],
  rescue: ['Rescue qua gap', 2],
  interpolate: ['Cắt vạch nội suy', 3],
  duplicate: ['Nghi đếm trùng', 4],
  direction: ['Sai hướng', 5],
  class: ['Sai loại', 6],
  missed: ['Lọt chưa ghép', 7],
  extra: ['Dư chưa ghép', 8],
}
export function buildBenchmarkFocusQueue(report, scorable = true) {
  if (!scorable || !report || typeof report !== 'object') return []
  const result = []
  const add = (kind, value, type, key) => {
    const time = value?.time
    if (typeof time !== 'number' || !Number.isFinite(time) || time < 0) return
    let focus = type
    if (type === 'missed' && value?.temporal_evidence?.status === 'persisted_event_claimed_by_other_gt') focus = 'clustered'
    else if (type === 'missed' && value?.vehicle_type === 'bicycle') focus = 'bicycle'
    else if (type === 'extra' && value?.reason === 'rescued_gap_unmatched') focus = 'rescue'
    else if (type === 'extra' && value?.reason === 'interpolated_unmatched') focus = 'interpolate'
    else if (type === 'extra' && value?.reason === 'spatial_duplicate_near_gt') focus = 'duplicate'
    const [label, priority] = rules[focus]
    result.push({ key:`${kind}-${key}`, time, kind, label, priority, focus, identityProven:false })
  }
  for (const [name, kind, type] of [
    ['missed_items', 'missed', 'missed'],
    ['false_positive_items', 'extra', 'extra'],
    ['direction_mismatch_items', 'direction', 'direction'],
    ['class_mismatch_items', 'class', 'class']
  ]) {
    const items = Array.isArray(report[name]) ? report[name].slice(0, 500) : []
    items.forEach((entry, i) => add(kind,entry,type,i))
  }
  return result.sort((a,b)=>a.priority-b.priority||a.time-b.time).slice(0,50)
}
