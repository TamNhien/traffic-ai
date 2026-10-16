// Report dates use the server's recorded clock, Asia/Ho_Chi_Minh (UTC+7).
export const REPORT_VEHICLES = Object.freeze({motorcycle:'Xe máy',bicycle:'Xe đạp',car:'Ô tô',bus:'Xe buýt',truck:'Xe tải',other:'Khác'})
export const REPORT_GROUPS = Object.freeze({hour:'Theo giờ',day:'Theo ngày',month:'Theo tháng'})

function dateValue(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value))) return null
  const date = new Date(`${value}T00:00:00Z`)
  return Number.isFinite(date.getTime()) && date.getUTCFullYear() >= 1 && date.toISOString().slice(0,10) === value ? date : null
}

export function shiftReportDate(value, days) {
  const date = dateValue(value)
  if (!date || !Number.isInteger(days)) throw Error('Ngày báo cáo không hợp lệ.')
  date.setUTCDate(date.getUTCDate()+days)
  const result = date.toISOString().slice(0,10)
  if (!dateValue(result)) throw Error('Ngày báo cáo ngoài phạm vi hỗ trợ.')
  return result
}

export function recordedDate(value = new Date()) {
  if (value == null || value === '') return ''
  // Database timestamps without an offset follow the backend's UTC convention.
  const raw = typeof value === 'string' && /^\d{4}-\d\d-\d\dT/.test(value) && !/(Z|[+-]\d\d:\d\d)$/.test(value) ? `${value}Z` : value
  const date = new Date(raw)
  if (!Number.isFinite(date.getTime())) return ''
  const parts = new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Ho_Chi_Minh',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(date)
  const get = name => parts.find(part=>part.type===name)?.value
  return `${get('year')}-${get('month')}-${get('day')}`
}

export function reportFilterProblem(filters) {
  const first = dateValue(filters?.start), last = dateValue(filters?.endInclusive)
  if (!first || !last) return 'Chọn ngày bắt đầu và ngày kết thúc hợp lệ.'
  if (filters.start === '0001-01-01' || filters.endInclusive === '9999-12-31') return 'Ngày báo cáo ngoài phạm vi hỗ trợ.'
  const days = Math.round((last-first)/86400000)+1
  if (days <= 0) return 'Ngày kết thúc phải từ ngày bắt đầu trở đi.'
  if (days > 366) return 'Mỗi báo cáo tối đa 366 ngày. Hãy thu hẹp khoảng ngày.'
  if (!Object.hasOwn(REPORT_GROUPS, filters?.groupBy)) return 'Chọn nhóm theo giờ, ngày hoặc tháng.'
  if (filters.groupBy === 'hour' && days > 31) return 'Báo cáo theo giờ tối đa 31 ngày; chọn theo ngày/tháng hoặc thu hẹp khoảng ngày.'
  if (filters.vehicleType && !Object.hasOwn(REPORT_VEHICLES,filters.vehicleType)) return 'Loại xe không hợp lệ.'
  for (const name of ['cameraId','sessionId']) if (filters[name] !== '' && filters[name] != null && (!/^\d+$/.test(String(filters[name])) || !Number.isSafeInteger(Number(filters[name])) || Number(filters[name]) <= 0 || Number(filters[name]) > 2147483647)) return 'Camera hoặc phiên đếm không hợp lệ.'
  return ''
}

export function reportQuery(filters) {
  const problem = reportFilterProblem(filters)
  if (problem) throw Error(problem)
  const query = new URLSearchParams({start:filters.start,end:shiftReportDate(filters.endInclusive,1),group_by:filters.groupBy})
  if (filters.cameraId) query.set('camera_id',String(Number(filters.cameraId)))
  if (filters.vehicleType) query.set('vehicle_type',filters.vehicleType)
  if (filters.sessionId) query.set('session_id',String(Number(filters.sessionId)))
  return query.toString()
}

export function reportUrl(query, format) {
  if (!format) return `/api/reports/traffic?${query}`
  if (!['xlsx','csv','pdf'].includes(format)) throw Error('Định dạng xuất báo cáo không hợp lệ.')
  return `/api/reports/traffic/export?${query}&format=${format}`
}

const finiteCount = value => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
export function validateTrafficReport(report) {
  const rowOk = row => row && ['total','in','out','unknown'].every(key=>finiteCount(row[key])) && row.total === row.in+row.out+row.unknown
  if (!rowOk(report?.summary) || !['session_count','camera_count'].every(key=>finiteCount(report.summary[key])) || !['series','per_camera','per_class','peak_hours'].every(key=>Array.isArray(report?.[key]) && report[key].every(rowOk))) throw Error('Dữ liệu báo cáo không hợp lệ. Hãy tải lại báo cáo.')
  if (report.series.some(row=>typeof row.bucket !== 'string') || report.peak_hours.some(row=>typeof row.bucket !== 'string')) throw Error('Mốc thời gian báo cáo không hợp lệ.')
  if (report.filters?.clock !== 'recorded' || report.filters?.timezone !== 'Asia/Ho_Chi_Minh') throw Error('Báo cáo chưa xác nhận thời điểm ghi nhận UTC+7.')
  if (report.summary.peak_hour !== null && (!rowOk(report.summary.peak_hour) || typeof report.summary.peak_hour.bucket !== 'string')) throw Error('Dữ liệu giờ cao nhất không hợp lệ.')
  if (report.series.reduce((sum,row)=>sum+row.total,0) !== report.summary.total) throw Error('Tổng lượt và chuỗi thời gian chưa đồng nhất. Hãy tải lại báo cáo.')
  return report
}

export function reportBucketLabel(bucket, groupBy = 'hour') {
  const value = String(bucket || '')
  if (groupBy === 'month' && /^\d{4}-\d{2}$/.test(value)) return `${value.slice(5,7)}/${value.slice(0,4)}`
  if (groupBy === 'day' && /^\d{4}-\d{2}-\d{2}$/.test(value)) return `${value.slice(8,10)}/${value.slice(5,7)}/${value.slice(0,4)}`
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:/.test(value)) return `${value.slice(8,10)}/${value.slice(5,7)} ${value.slice(11,13)}h`
  return '—'
}

export function reportChartGeometry(series, width = 880, height = 220) {
  const rows = Array.isArray(series) ? series : []
  const safe = value => finiteCount(value) ? value : 0
  const maximum = Math.max(1,...rows.map(row=>safe(row.total)))
  const left=48, top=14, right=18, bottom=34
  const plotWidth=Math.max(1,width-left-right), plotHeight=Math.max(1,height-top-bottom)
  const points=rows.map((row,index)=>({
    bucket:String(row.bucket || ''), x:left+(rows.length===1?plotWidth/2:index*plotWidth/Math.max(1,rows.length-1)),
    total:safe(row.total), in:safe(row.in), out:safe(row.out), unknown:safe(row.unknown),
  }))
  const y=value=>top+plotHeight*(1-safe(value)/maximum)
  return {width,height,left,top,plotWidth,plotHeight,maximum,points,y,
    paths:Object.fromEntries(['total','in','out'].map(key=>[key,points.map(point=>`${point.x.toFixed(2)},${y(point[key]).toFixed(2)}`).join(' ')]))}
}
