import React, {useEffect, useMemo, useRef, useState} from 'react'
import {secureFetch} from './security.jsx'
import {readableApiDetail} from './account-utils.js'
import {REPORT_GROUPS, REPORT_VEHICLES, recordedDate, reportBucketLabel, reportChartGeometry, reportFilterProblem, reportQuery, reportUrl, validateTrafficReport} from './traffic-report-utils.js'
import './traffic-reports.css'

const number = value => new Intl.NumberFormat('vi-VN').format(value)
async function responseError(response) {
  const data = await response.json().catch(()=>({}))
  return readableApiDetail(data.detail,response.status)
}

function ReportChart({series, groupBy}) {
  const chart = useMemo(()=>reportChartGeometry(series),[series])
  const ticks = [...new Set([0,Math.ceil(chart.maximum/2),chart.maximum])]
  const labels = [...new Set([0,Math.floor((chart.points.length-1)/2),chart.points.length-1])].filter(index=>index>=0)
  if (!chart.points.length) return <p className="tr-empty">Không có mốc thời gian trong khoảng đã chọn.</p>
  return <>
    <svg className="tr-chart" viewBox={`0 0 ${chart.width} ${chart.height}`} role="img" aria-label={`Biểu đồ ${REPORT_GROUPS[groupBy]?.toLowerCase()} gồm ${series.length} mốc; tổng lượt màu xanh dương, IN màu xanh lá, OUT màu vàng. Số liệu chi tiết ở bảng bên dưới.`}>
      <title>Lượt qua vạch theo thời điểm ghi nhận (UTC+7)</title>
      {ticks.map(tick=><g key={tick}><line className="tr-grid-line" x1={chart.left} y1={chart.y(tick)} x2={chart.left+chart.plotWidth} y2={chart.y(tick)}/><text x={chart.left-8} y={chart.y(tick)+4} textAnchor="end">{number(tick)}</text></g>)}
      {['total','in','out'].map(key=><polyline key={key} className={`tr-${key}`} points={chart.paths[key]} strokeWidth={key==='total'?2.5:1.8} vectorEffect="non-scaling-stroke"/>)}
      {chart.points.length<=40 && chart.points.map(point=><circle className="tr-total" key={point.bucket} cx={point.x} cy={chart.y(point.total)} r="3"><title>{reportBucketLabel(point.bucket,groupBy)} · Tổng {point.total} · IN {point.in} · OUT {point.out} · Chưa rõ {point.unknown}</title></circle>)}
      {labels.map(index=><text key={index} x={chart.points[index].x} y={chart.height-8} textAnchor={index===0?'start':index===chart.points.length-1?'end':'middle'}>{reportBucketLabel(chart.points[index].bucket,groupBy)}</text>)}
    </svg>
    <div className="tr-legend"><span>Tổng lượt</span><span className="tr-legend-in">IN</span><span className="tr-legend-out">OUT</span></div>
  </>
}

function CountTable({title, rows, rowLabel, empty='Không có dữ liệu.'}) {
  return <div className="tr-table-wrap"><table><caption>{title}</caption><thead><tr><th scope="col">Nhóm</th><th scope="col">Tổng</th><th scope="col">IN</th><th scope="col">OUT</th><th scope="col">Chưa rõ</th></tr></thead><tbody>
    {rows.map((row,index)=><tr key={row.bucket??row.camera_id??row.vehicle_type??index}><th scope="row">{rowLabel(row)}</th><td>{number(row.total)}</td><td>{number(row.in)}</td><td>{number(row.out)}</td><td>{number(row.unknown)}</td></tr>)}
    {!rows.length&&<tr><td colSpan="5" className="tr-empty">{empty}</td></tr>}
  </tbody></table></div>
}

// The aggregate endpoint and export endpoint both enforce authentication/roles.
// Default to one counting session so video replays are never silently combined.
export function TrafficReports({cameras=[], selectedCameraId, canExport=false}) {
  const today = recordedDate()
  const [filters,setFilters] = useState(()=>({start:today,endInclusive:today,groupBy:'hour',cameraId:selectedCameraId?String(selectedCameraId):'',vehicleType:'',sessionId:'',scope:'session'}))
  const [sessionData,setSessionData] = useState({items:[],total:0,truncated:false})
  const [sessionsLoading,setSessionsLoading] = useState(false)
  const [sessionsError,setSessionsError] = useState('')
  const [sessionRefresh,setSessionRefresh] = useState(0)
  const [result,setResult] = useState(null)
  const [busy,setBusy] = useState(false)
  const [exportBusy,setExportBusy] = useState(false)
  const [error,setError] = useState('')
  const [notice,setNotice] = useState('')
  const requestId = useRef(0)
  const downloadId = useRef(0)
  const reportController = useRef(null)
  const exportController = useRef(null)
  const mounted = useRef(true)
  const queryRef = useRef('')
  const effective = {...filters,sessionId:filters.scope==='session'?filters.sessionId:''}
  const problem = reportFilterProblem(effective) || (filters.scope==='session'&&!filters.sessionId?'Chọn một phiên đếm để xem báo cáo.':'')
  const query = problem?'':reportQuery(effective)
  queryRef.current=query
  const current = result?.query===query && query ? result.data : null
  const selectedSession = sessionData.items.find(item=>String(item.id)===filters.sessionId)

  const sessionDates = session => {
    const start=recordedDate(session.started_at), end=recordedDate(session.ended_at || new Date())
    return start?{start,endInclusive:end&&end>=start?end:start}:{}
  }
  const chooseSession = (id, next={}) => {
    const item=sessionData.items.find(session=>String(session.id)===String(id))
    setFilters(previous=>({...previous,...next,sessionId:String(id),...(item?sessionDates(item):{})}))
  }
  const change = (name,value) => {
    setError('');setNotice('')
    setFilters(previous=>({...previous,[name]:value,...(name==='cameraId'?{sessionId:''}:{})}))
  }

  useEffect(()=>{
    mounted.current=true
    return ()=>{mounted.current=false;requestId.current++;downloadId.current++;reportController.current?.abort();exportController.current?.abort()}
  },[])
  useEffect(()=>{
    setFilters(previous=>({...previous,cameraId:selectedCameraId?String(selectedCameraId):'',sessionId:''}))
  },[selectedCameraId])
  useEffect(()=>{
    const controller=new AbortController()
    let alive=true
    setSessionsLoading(true);setSessionsError('');setSessionData({items:[],total:0,truncated:false})
    const params=new URLSearchParams({limit:'100'})
    if(filters.cameraId)params.set('camera_id',filters.cameraId)
    secureFetch(`/api/reports/sessions?${params}`,{cache:'no-store',signal:controller.signal}).then(async response=>{
      if(!response.ok)throw Error(await responseError(response))
      const data=await response.json()
      if(!Array.isArray(data.items))throw Error('Danh sách phiên đếm không hợp lệ.')
      if(!alive)return
      setSessionData(data)
      setFilters(previous=>{
        if(previous.cameraId!==filters.cameraId)return previous
        const chosen=data.items.find(item=>String(item.id)===previous.sessionId)||data.items[0]
        return {...previous,sessionId:chosen?String(chosen.id):'',...(chosen&&previous.scope==='session'?sessionDates(chosen):{})}
      })
    }).catch(err=>{if(alive&&err.name!=='AbortError')setSessionsError(err.message)}).finally(()=>{if(alive)setSessionsLoading(false)})
    return ()=>{alive=false;controller.abort()}
  },[filters.cameraId,sessionRefresh])
  useEffect(()=>{
    requestId.current++;downloadId.current++
    reportController.current?.abort();exportController.current?.abort()
    setBusy(false);setExportBusy(false);setError('');setNotice('')
  },[query])

  const loadReport = async event => {
    event?.preventDefault()
    if(problem){setError(problem);return}
    const snapshot=query, token=++requestId.current
    reportController.current?.abort()
    const controller=new AbortController();reportController.current=controller
    setBusy(true);setError('');setNotice('')
    try {
      const response=await secureFetch(reportUrl(snapshot),{cache:'no-store',signal:controller.signal})
      if(!response.ok)throw Error(await responseError(response))
      const data=validateTrafficReport(await response.json())
      if(!mounted.current||token!==requestId.current||queryRef.current!==snapshot)return
      setResult({query:snapshot,data});setNotice('Đã cập nhật báo cáo từ các lượt đếm đã lưu trong cơ sở dữ liệu.')
    }catch(err){if(mounted.current&&token===requestId.current&&queryRef.current===snapshot&&err.name!=='AbortError'){setResult(null);setError(err.message)}}
    finally{if(mounted.current&&token===requestId.current)setBusy(false)}
  }
  const exportReport = async format => {
    if(!canExport||!current||busy||exportBusy)return
    const snapshot=query, token=++downloadId.current
    const controller=new AbortController();exportController.current=controller
    setExportBusy(true);setError('');setNotice('')
    try {
      const response=await secureFetch(reportUrl(snapshot,format),{cache:'no-store',signal:controller.signal})
      if(!response.ok)throw Error(await responseError(response))
      const type=response.headers.get('content-type')||''
      const expected={xlsx:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',csv:'text/csv',pdf:'application/pdf'}[format]
      if(!type.toLowerCase().startsWith(expected))throw Error('Máy chủ chưa trả về đúng định dạng báo cáo. Hãy thử lại.')
      const blob=await response.blob()
      if(!mounted.current||token!==downloadId.current||queryRef.current!==snapshot)return
      if(!blob.size)throw Error('Tệp báo cáo rỗng. Hãy thử lại.')
      const url=URL.createObjectURL(blob)
      const anchor=document.createElement('a')
      try {
        anchor.href=url;anchor.download=`traffic-report-${filters.start}-${filters.endInclusive}.${format}`
        document.body.appendChild(anchor);anchor.click()
      }finally{anchor.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}
      setNotice(`Đã tải báo cáo ${format.toUpperCase()} theo bộ lọc đang hiển thị.`)
    }catch(err){if(mounted.current&&token===downloadId.current&&queryRef.current===snapshot&&err.name!=='AbortError')setError(err.message)}
    finally{if(mounted.current&&token===downloadId.current)setExportBusy(false)}
  }

  return <section className="panel traffic-reports" id="reports" aria-labelledby="traffic-report-title">
    <div className="panel-head"><div><span className="panel-kicker">TRAFFIC REPORTS · UTC+7</span><h2 id="traffic-report-title">Thống kê & báo cáo giao thông</h2></div></div>
    <p className="tr-subtitle">Tổng hợp lượt qua vạch theo giờ, ngày, tháng; lọc theo camera, loại xe và phiên đếm. Thời điểm ghi nhận dùng múi giờ Việt Nam (UTC+7).</p>
    <form onSubmit={loadReport}>
      <div className="tr-filters">
        <label>Phạm vi thống kê<select value={filters.scope} onChange={event=>{
          const scope=event.target.value
          if(scope==='session')chooseSession(filters.sessionId||sessionData.items[0]?.id||'',{scope})
          else change('scope',scope)
        }}><option value="session">Một phiên đếm</option><option value="range">Khoảng ngày · cộng các phiên</option></select></label>
        <label>Camera<select value={filters.cameraId} onChange={event=>change('cameraId',event.target.value)}><option value="">Tất cả camera</option>{cameras.map(camera=><option key={camera.id} value={String(camera.id)}>{camera.code} · {camera.name}</option>)}</select></label>
        <label>Loại phương tiện<select value={filters.vehicleType} onChange={event=>change('vehicleType',event.target.value)}><option value="">Tất cả loại xe</option>{Object.entries(REPORT_VEHICLES).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
        <label>Nhóm thời gian<select value={filters.groupBy} onChange={event=>change('groupBy',event.target.value)}>{Object.entries(REPORT_GROUPS).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
        <label>Từ ngày (UTC+7)<input type="date" required value={filters.start} onChange={event=>change('start',event.target.value)}/></label>
        <label>Đến hết ngày (UTC+7)<input type="date" required value={filters.endInclusive} onChange={event=>change('endInclusive',event.target.value)}/></label>
        <label className="tr-wide">Phiên đếm{filters.scope==='range'?' · không lọc phiên':''}<select disabled={filters.scope!=='session'||sessionsLoading} value={filters.sessionId} onChange={event=>chooseSession(event.target.value)}><option value="">{sessionsLoading?'Đang tải phiên...':'-- Chọn phiên đếm --'}</option>{sessionData.items.map(session=><option key={session.id} value={String(session.id)}>#{session.id} · Camera #{session.camera_id} · {recordedDate(session.started_at)} · {session.status} · {number(session.total_vehicles??0)} lượt</option>)}</select></label>
      </div>
      <div className="tr-actions"><button className="primary" type="submit" disabled={busy||!!problem}>{busy?'Đang tổng hợp...':'Xem báo cáo'}</button><button type="button" onClick={()=>setSessionRefresh(value=>value+1)} disabled={sessionsLoading}>Làm mới phiên</button>{canExport&&<>{['xlsx','csv','pdf'].map(format=><button type="button" key={format} onClick={()=>exportReport(format)} disabled={!current||busy||exportBusy}>{exportBusy?'Đang xuất...':`Tải ${format==='xlsx'?'Excel (.xlsx)':format.toUpperCase()}`}</button>)}</>}{!canExport&&<small>Quyền hiện tại cho phép xem báo cáo. Xuất tệp dành cho Admin / Operator.</small>}</div>
    </form>
    {problem&&<p className="hint">{problem}</p>}
    {sessionsError&&<div className="error-banner" role="alert">Không tải được danh sách phiên: {sessionsError}</div>}
    {sessionData.truncated&&<p className="hint">Đang liệt kê {sessionData.items.length} phiên mới nhất trong {number(sessionData.total)} phiên. Chọn camera để thu hẹp danh sách.</p>}
    {filters.scope==='range'&&<div className="tr-notice">Đang cộng các phiên trong khoảng ngày đã chọn. Mỗi lần phát lại video là một phiên riêng và được cộng thêm lượt; không dùng tổng này làm lưu lượng thực tế của một lần chạy.</div>}
    {filters.scope==='session'&&selectedSession&&<p className="hint">Phiên #{selectedSession.id}: báo cáo chỉ lấy các lượt thuộc phiên này trong khoảng ngày đang chọn. Với video, thời điểm ghi nhận là lúc xử lý video; không phải ngày quay hoặc timecode gốc.</p>}
    {error&&<div className="error-banner" role="alert">{error}</div>}
    {notice&&<div className="notice-banner" role="status">{notice}</div>}
    {!current&&<p className="tr-empty">{busy?'Đang đọc dữ liệu...':result?'Bộ lọc đã thay đổi. Nhấn Xem báo cáo để cập nhật trước khi xuất tệp.':'Chọn phạm vi và nhấn Xem báo cáo để xem số liệu.'}</p>}
    {current&&<>
      <div className="tr-stats">
        <div className="tr-stat"><span>Tổng lượt qua vạch</span><strong>{number(current.summary.total)}</strong><small>{number(current.summary.session_count)} phiên · {number(current.summary.camera_count)} camera</small></div>
        <div className="tr-stat"><span>Lượt IN</span><strong>{number(current.summary.in)}</strong><small>Đi theo hướng IN đã cấu hình</small></div>
        <div className="tr-stat"><span>Lượt OUT</span><strong>{number(current.summary.out)}</strong><small>Chưa rõ hướng: {number(current.summary.unknown)}</small></div>
        <div className="tr-stat"><span>Giờ ghi nhận cao nhất</span><strong>{current.summary.peak_hour?number(current.summary.peak_hour.total):'—'}</strong><small>{current.summary.peak_hour?`${reportBucketLabel(current.summary.peak_hour.bucket,'hour')} · UTC+7`:'Chưa có lượt ghi nhận'}</small></div>
      </div>
      <div className="tr-chart-panel"><h3>Lượt qua vạch · {REPORT_GROUPS[filters.groupBy].toLowerCase()}</h3><p className="hint">{filters.start} đến hết {filters.endInclusive} · UTC+7 · {filters.scope==='session'?`Phiên #${filters.sessionId}`:'Cộng các phiên theo bộ lọc'}</p><ReportChart series={current.series} groupBy={filters.groupBy}/></div>
      {current.summary.total===0&&<p className="tr-notice">Không có lượt đếm đã lưu phù hợp bộ lọc. Kiểm tra camera, phiên và khoảng ngày ghi nhận; đây không phải kết quả đánh giá Recall/F1.</p>}
      <div className="tr-tables"><CountTable title="Theo loại phương tiện" rows={current.per_class} rowLabel={row=>REPORT_VEHICLES[row.vehicle_type]||'Khác'}/><CountTable title="Theo camera" rows={current.per_camera} rowLabel={row=>`${row.camera_name||'Camera'} · #${row.camera_id}`}/><CountTable title="Chi tiết theo thời gian (UTC+7)" rows={current.series} rowLabel={row=>reportBucketLabel(row.bucket,filters.groupBy)}/><CountTable title="5 giờ ghi nhận nhiều lượt nhất (UTC+7)" rows={current.peak_hours} rowLabel={row=>reportBucketLabel(row.bucket,'hour')}/></div>
      {(current.warnings||[]).filter(item=>typeof item==='string').map((warning,index)=><p className="tr-footnote" key={index}>{warning}</p>)}
    </>}
    <p className="tr-footnote">Đơn vị là lượt cắt vạch: cùng một xe quay lại cắt vạch được tính thêm lượt. Báo cáo dùng sự kiện AI đã lưu; độ chính xác, lọt và dư cần đối chiếu Ground Truth trong Benchmark.</p>
  </section>
}
