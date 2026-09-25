import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const APP_VERSION = '0.5.25'
const vehicleLabels = {
  motorcycle: 'Xe máy', bicycle: 'Xe đạp', car: 'Ô tô', bus: 'Xe buýt', truck: 'Xe tải', other: 'Khác'
}
const missReasonLabels = {
  detector_miss: 'Detector không thấy xe',
  tracker_miss: 'YOLO thấy nhưng ByteTrack mất ID',
  road_zone_reject: 'Track bị Road Zone loại',
  crossing_gate_miss: 'Track trong đường nhưng Crossing Gate không phát event',
  crossing_confirmation_reject: 'Crossing chưa đủ xác nhận phía sau vạch',
  crossing_cooldown_reject: 'Crossing bị cooldown chống đếm lặp',
  no_trace_window: 'Không có telemetry gần timecode',
}
const falsePositiveReasonLabels = {
  startup_artifact: 'Event giả lúc khởi tạo clip',
  direction_flip_jitter: 'Cùng track đảo IN/OUT quá nhanh',
  same_track_repeat: 'Cùng track phát event lặp',
  duplicate_near_gt: 'Event dư nằm sát một GT đã khớp',
  rescued_gap_unmatched: 'Rescue qua gap nhưng GT không có',
  interpolated_unmatched: 'Nội suy qua vạch nhưng GT không có',
  direct_unmatched: 'Direct crossing nhưng GT không có',
  unmatched_ai_event: 'AI event chưa xác định nguyên nhân',
}

const clamp01 = value => Math.min(1, Math.max(0, Number(value)))

const roadZonePoints = zone => [
  [clamp01(zone?.road_x1 ?? 0.20), clamp01(zone?.road_y1 ?? 0.16)],
  [clamp01(zone?.road_x2 ?? 0.80), clamp01(zone?.road_y2 ?? 0.16)],
  [clamp01(zone?.road_x3 ?? 0.96), clamp01(zone?.road_y3 ?? 0.98)],
  [clamp01(zone?.road_x4 ?? 0.04), clamp01(zone?.road_y4 ?? 0.98)],
]

const pointOnSegment = (point, a, b, eps=1e-8) => {
  const cross=(point[0]-a[0])*(b[1]-a[1])-(point[1]-a[1])*(b[0]-a[0])
  if (Math.abs(cross)>eps) return false
  return point[0]>=Math.min(a[0],b[0])-eps && point[0]<=Math.max(a[0],b[0])+eps && point[1]>=Math.min(a[1],b[1])-eps && point[1]<=Math.max(a[1],b[1])+eps
}
const pointInPolygon = (point, polygon) => {
  let inside=false
  for (let i=0,j=polygon.length-1;i<polygon.length;j=i++) {
    const a=polygon[j], b=polygon[i]
    if (pointOnSegment(point,a,b)) return true
    if ((b[1]>point[1]) !== (a[1]>point[1])) {
      const x=(a[0]-b[0])*(point[1]-b[1])/(a[1]-b[1])+b[0]
      if (point[0]<x) inside=!inside
    }
  }
  return inside
}
const orientation = (a,b,c,eps=1e-8) => {
  const v=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
  return Math.abs(v)<=eps ? 0 : (v>0 ? 1 : -1)
}
const segmentsIntersect = (a,b,c,d) => {
  const o1=orientation(a,b,c), o2=orientation(a,b,d), o3=orientation(c,d,a), o4=orientation(c,d,b)
  if (o1!==o2 && o3!==o4) return true
  if (o1===0 && pointOnSegment(c,a,b)) return true
  if (o2===0 && pointOnSegment(d,a,b)) return true
  if (o3===0 && pointOnSegment(a,c,d)) return true
  if (o4===0 && pointOnSegment(b,c,d)) return true
  return false
}
const polygonArea = polygon => Math.abs(polygon.reduce((sum,p,i)=>{ const q=polygon[(i+1)%polygon.length]; return sum+p[0]*q[1]-q[0]*p[1] },0))/2
const validateCountingGeometry = geometry => {
  const zone=roadZonePoints(geometry)
  if (segmentsIntersect(zone[0],zone[1],zone[2],zone[3]) || segmentsIntersect(zone[1],zone[2],zone[3],zone[0])) return {valid:false,message:'Vùng lòng đường đang bị bắt chéo. Sắp 4 điểm xanh theo vòng quanh mặt đường.'}
  if (polygonArea(zone)<0.02) return {valid:false,message:'Vùng lòng đường quá nhỏ. Kéo 4 điểm xanh bao đủ phần mặt đường cần đếm.'}
  const a=[clamp01(geometry.line_x1),clamp01(geometry.line_y1)], b=[clamp01(geometry.line_x2),clamp01(geometry.line_y2)]
  if (Math.hypot(b[0]-a[0],b[1]-a[1])<0.05) return {valid:false,message:'Vạch đếm quá ngắn.'}
  if (!pointInPolygon(a,zone) || !pointInPolygon(b,zone)) return {valid:false,message:'Hai đầu vạch vàng phải nằm trong vùng LÒNG ĐƯỜNG; không kéo vạch ra lề/vỉa hè.'}
  return {valid:true,message:'Vạch đếm nằm hoàn toàn trong vùng lòng đường.'}
}

function RoadZoneOverlay({ zone }) {
  const points = roadZonePoints(zone).map(([x,y])=>`${x*100},${y*100}`).join(' ')
  return <svg className="road-overlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
    <polygon points={points} className="road-overlay-zone" />
    <text x="4" y="9" className="road-overlay-label">LÒNG ĐƯỜNG</text>
  </svg>
}

function CountingLineOverlay({ line }) {
  if (!line) return null
  const x1 = clamp01(line.line_x1) * 100
  const y1 = clamp01(line.line_y1) * 100
  const x2 = clamp01(line.line_x2) * 100
  const y2 = clamp01(line.line_y2) * 100
  return <svg className="counting-overlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
    <line x1={x1} y1={y1} x2={x2} y2={y2} className="counting-overlay-line" />
    <circle cx={x1} cy={y1} r="1.2" className="counting-overlay-point" />
    <circle cx={x2} cy={y2} r="1.2" className="counting-overlay-point" />
  </svg>
}

const defaultCameraForm = () => ({
  name: 'Camera demo', code: 'CAM-001', source_type: 'video',
  source_url: '/data/videos/demo.mp4', location: 'Khu vực demo',
  confidence_threshold: 0.06, line_x1: 0.32, line_y1: 0.59, line_x2: 0.84, line_y2: 0.59,
  road_x1:0.20, road_y1:0.16, road_x2:0.80, road_y2:0.16, road_x3:0.96, road_y3:0.98, road_x4:0.04, road_y4:0.98
})

function StatCard({ title, value, note }) {
  return <article className="stat-card"><span>{title}</span><strong>{value}</strong><small>{note}</small></article>
}

function CountingLineEditor({ previewUrl, line, onChange, disabled }) {
  const boxRef = useRef(null)
  const dragRef = useRef(null)

  const pointFromEvent = event => {
    const rect = boxRef.current.getBoundingClientRect()
    return { x: clamp01((event.clientX - rect.left) / rect.width), y: clamp01((event.clientY - rect.top) / rect.height) }
  }

  const beginDrag = (kind, event) => {
    if (disabled) return
    event.preventDefault()
    event.currentTarget.setPointerCapture?.(event.pointerId)
    dragRef.current = { kind, start: pointFromEvent(event), original: { ...line } }
  }

  const moveDrag = event => {
    const drag = dragRef.current
    if (!drag || disabled) return
    const point = pointFromEvent(event)
    if (drag.kind === 'p1') {
      onChange({ ...line, line_x1: point.x, line_y1: point.y })
      return
    }
    if (drag.kind === 'p2') {
      onChange({ ...line, line_x2: point.x, line_y2: point.y })
      return
    }
    if (drag.kind.startsWith('road')) {
      const index = Number(drag.kind.slice(4)) + 1
      onChange({ ...line, [`road_x${index}`]: point.x, [`road_y${index}`]: point.y })
      return
    }
    const dx = point.x - drag.start.x
    const dy = point.y - drag.start.y
    const o = drag.original
    const minDx = -Math.min(o.line_x1, o.line_x2)
    const maxDx = 1 - Math.max(o.line_x1, o.line_x2)
    const minDy = -Math.min(o.line_y1, o.line_y2)
    const maxDy = 1 - Math.max(o.line_y1, o.line_y2)
    const safeDx = Math.min(maxDx, Math.max(minDx, dx))
    const safeDy = Math.min(maxDy, Math.max(minDy, dy))
    onChange({ ...line, line_x1:o.line_x1+safeDx, line_y1:o.line_y1+safeDy, line_x2:o.line_x2+safeDx, line_y2:o.line_y2+safeDy })
  }

  const endDrag = () => { dragRef.current = null }
  const x1 = Number(line.line_x1), y1 = Number(line.line_y1), x2 = Number(line.line_x2), y2 = Number(line.line_y2)
  const mx = (x1 + x2) / 2, my = (y1 + y2) / 2
  const dx = x2 - x1, dy = y2 - y1
  const length = Math.max(Math.hypot(dx, dy), 0.001)
  const nx = -dy / length, ny = dx / length
  const zonePoints = roadZonePoints(line)
  const zoneSvg = zonePoints.map(([x,y])=>`${x},${y}`).join(' ')

  return <div className={`line-editor ${disabled ? 'locked' : ''}`} ref={boxRef} onPointerMove={moveDrag} onPointerUp={endDrag} onPointerCancel={endDrag}>
    {previewUrl ? <img src={previewUrl} alt="Khung hình dùng để đặt vạch đếm" /> : <div className="camera-placeholder"><strong>Chưa có ảnh xem trước</strong><span>Kiểm tra nguồn camera/video trước khi đặt vạch.</span></div>}
    <svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-label="Vạch đếm và vùng lòng đường tương tác">
      <polygon className="road-zone-editor" points={zoneSvg} />
      {zonePoints.map(([x,y],index)=><g key={`road-${index}`}><circle className="road-zone-handle" cx={x} cy={y} r="0.014" onPointerDown={e=>beginDrag(`road${index}`,e)} /><text className="road-zone-handle-label" fontSize="0.026" x={clamp01(x+0.012)} y={clamp01(y-0.012)}>{index+1}</text></g>)}
      <text className="road-zone-title" fontSize="0.030" x={zonePoints[0][0]} y={clamp01(zonePoints[0][1]+0.045)}>LÒNG ĐƯỜNG</text>
      <line className="gate-hit" x1={x1} y1={y1} x2={x2} y2={y2} onPointerDown={e=>beginDrag('line',e)} />
      <line className="gate-line" x1={x1} y1={y1} x2={x2} y2={y2} />
      <circle className="gate-handle" cx={x1} cy={y1} r="0.014" onPointerDown={e=>beginDrag('p1',e)} />
      <circle className="gate-handle" cx={x2} cy={y2} r="0.014" onPointerDown={e=>beginDrag('p2',e)} />
      <text className="gate-label in" fontSize="0.035" x={clamp01(mx + nx*0.055)} y={clamp01(my + ny*0.055)}>IN</text>
      <text className="gate-label out" fontSize="0.035" x={clamp01(mx - nx*0.055)} y={clamp01(my - ny*0.055)}>OUT</text>
    </svg>
  </div>
}

const annotationClasses = ['Xe máy', 'Xe đạp', 'Ô tô', 'Xe buýt', 'Xe tải']

function AnnotationEditor({ dataset, onChanged }) {
  const [indexData, setIndexData] = useState(null)
  const [currentName, setCurrentName] = useState('')
  const [annotation, setAnnotation] = useState(null)
  const [boxes, setBoxes] = useState([])
  const [selectedBox, setSelectedBox] = useState(-1)
  const [newClassId, setNewClassId] = useState(0)
  const [reviewMode, setReviewMode] = useState('priority')
  const [saving, setSaving] = useState(false)
  const [bulkBusy, setBulkBusy] = useState(false)
  const [message, setMessage] = useState('')
  const stageRef = useRef(null)
  const drawRef = useRef(null)

  const readBody = async response => {
    const text = await response.text()
    if (!text) return {}
    try { return JSON.parse(text) } catch { return { detail:text } }
  }

  const loadIndex = async preferred => {
    if (!dataset?.id) { setIndexData(null); setCurrentName(''); setAnnotation(null); setBoxes([]); return '' }
    const response = await fetch(`/api/datasets/${dataset.id}/annotations?limit=1000&review_mode=${encodeURIComponent(reviewMode)}`, {cache:'no-store'})
    const body = await readBody(response)
    if (!response.ok) throw new Error(body.detail || 'Không tải được danh sách annotation')
    setIndexData(body)
    const names = body.items || []
    const next = preferred && names.some(i=>i.image_name===preferred) ? preferred : (currentName && names.some(i=>i.image_name===currentName) ? currentName : names[0]?.image_name || '')
    setCurrentName(next)
    if (!next) { setAnnotation(null); setBoxes([]); setSelectedBox(-1) }
    return next
  }

  const loadAnnotation = async name => {
    if (!dataset?.id || !name) { setAnnotation(null); setBoxes([]); return }
    const response = await fetch(`/api/datasets/${dataset.id}/annotations/${encodeURIComponent(name)}`, {cache:'no-store'})
    const body = await readBody(response)
    if (!response.ok) throw new Error(body.detail || 'Không tải được annotation')
    setAnnotation(body); setBoxes(body.boxes || []); setSelectedBox(-1); setMessage('')
  }

  useEffect(() => {
    let cancelled = false
    ;(async()=>{
      try {
        const name = await loadIndex('')
        if (!cancelled && name) await loadAnnotation(name)
      } catch (err) { if (!cancelled) setMessage(err.message) }
    })()
    return ()=>{ cancelled = true }
  }, [dataset?.id, dataset?.updated_at, reviewMode])

  useEffect(() => {
    if (currentName) loadAnnotation(currentName).catch(err=>setMessage(err.message))
  }, [currentName])

  useEffect(() => {
    const onKey = event => {
      if (event.target?.matches?.('input,select,textarea')) return
      if (selectedBox >= 0 && /^[1-5]$/.test(event.key)) {
        const classId = Number(event.key) - 1
        setBoxes(prev=>prev.map((b,i)=>i===selectedBox ? {...b,class_id:classId,class_name:['motorcycle','bicycle','car','bus','truck'][classId]} : b))
        setNewClassId(classId)
        event.preventDefault()
      } else if (selectedBox >= 0 && (event.key === 'Delete' || event.key === 'Backspace')) {
        setBoxes(prev=>prev.filter((_,i)=>i!==selectedBox)); setSelectedBox(-1); event.preventDefault()
      }
    }
    window.addEventListener('keydown', onKey)
    return ()=>window.removeEventListener('keydown', onKey)
  }, [selectedBox])

  const pointFromEvent = event => {
    const rect = stageRef.current.getBoundingClientRect()
    return {x:clamp01((event.clientX-rect.left)/rect.width), y:clamp01((event.clientY-rect.top)/rect.height)}
  }
  const beginDraw = event => {
    if (!annotation) return
    setSelectedBox(-1)
    const point = pointFromEvent(event)
    drawRef.current = point
    event.currentTarget.setPointerCapture?.(event.pointerId)
  }
  const finishDraw = event => {
    if (!drawRef.current || !annotation) return
    const start = drawRef.current; drawRef.current = null
    const end = pointFromEvent(event)
    const w = Math.abs(end.x-start.x), h = Math.abs(end.y-start.y)
    if (w < 0.01 || h < 0.01) return
    const box = {class_id:newClassId,class_name:['motorcycle','bicycle','car','bus','truck'][newClassId],x:(start.x+end.x)/2,y:(start.y+end.y)/2,w,h}
    setBoxes(prev=>[...prev,box]); setSelectedBox(boxes.length)
  }
  const changeSelectedClass = classId => {
    setNewClassId(classId)
    if (selectedBox >= 0) setBoxes(prev=>prev.map((b,i)=>i===selectedBox?{...b,class_id:classId,class_name:['motorcycle','bicycle','car','bus','truck'][classId]}:b))
  }
  const save = async () => {
    if (!dataset?.id || !currentName || !annotation) return
    setSaving(true); setMessage('')
    try {
      const response = await fetch(`/api/datasets/${dataset.id}/annotations/${encodeURIComponent(currentName)}`, {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({boxes:boxes.map(({class_id,x,y,w,h})=>({class_id,x,y,w,h})),reviewed:annotation.reviewed,difficult:annotation.difficult})})
      const body = await readBody(response)
      if (!response.ok) throw new Error(body.detail || 'Không lưu được annotation')
      setAnnotation(body); setBoxes(body.boxes || []); setMessage('Đã lưu nhãn ground-truth cho ảnh này.')
      const next = await loadIndex(currentName)
      if (next && next !== currentName) await loadAnnotation(next)
      onChanged?.()
    } catch (err) { setMessage(err.message) } finally { setSaving(false) }
  }
  const acceptSafe = async () => {
    if (!dataset?.id || bulkBusy) return
    const count = Number(indexData?.safe_auto_accept_images || 0)
    if (!count) { setMessage('Không có ảnh đủ điều kiện duyệt nhanh an toàn.'); return }
    if (!window.confirm(`Đánh dấu ${count} ảnh auto-label độ tin cậy cao là đã duyệt? Xe máy/xe đạp và ảnh không có detection KHÔNG được tự duyệt.`)) return
    setBulkBusy(true); setMessage('')
    try {
      const response = await fetch(`/api/datasets/${dataset.id}/annotations/accept-safe`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({min_confidence:0.70})})
      const body = await readBody(response)
      if (!response.ok) throw new Error(body.detail || 'Không duyệt nhanh được annotation')
      setMessage(`Đã duyệt nhanh ${body.accepted_images || 0} ảnh tin cậy. Xe máy/xe đạp vẫn để lại cho bạn kiểm tra.`)
      await loadIndex(''); onChanged?.()
    } catch (err) { setMessage(err.message) } finally { setBulkBusy(false) }
  }
  const move = delta => {
    const items = indexData?.items || []
    const idx = items.findIndex(i=>i.image_name===currentName)
    if (idx < 0 || !items.length) return
    const next = items[Math.min(items.length-1,Math.max(0,idx+delta))]
    if (next) setCurrentName(next.image_name)
  }
  if (!dataset) return <section className="panel annotation-panel" id="annotation"><div className="empty">Chọn dataset để mở Annotation Studio.</div></section>
  const items = indexData?.items || []
  const currentIndex = Math.max(0, items.findIndex(i=>i.image_name===currentName))
  const imageUrl = currentName ? `/api/datasets/${dataset.id}/images/${encodeURIComponent(currentName)}?v=${encodeURIComponent(dataset.updated_at || '')}` : ''
  return <section className="panel annotation-panel" id="annotation">
    <div className="panel-head"><div><span className="panel-kicker">ANNOTATION STUDIO · SMART REVIEW</span><h2>3. Chỉ rà soát ảnh cần thiết trước khi train lại</h2></div><span className="lock-state">V0.5.25</span></div>
    <p className="hint"><strong>Không cần sửa tay cả 1.200 ảnh.</strong> Chế độ mặc định đưa ảnh xe máy/xe đạp, confidence thấp, ảnh đông xe hoặc ảnh không detection lên trước. Ảnh ô tô/bus/truck rõ và confidence cao có thể duyệt nhanh sau khi bạn spot-check.</p>
    <div className="annotation-summary"><span>Tổng ảnh: <strong>{indexData?.total ?? 0}</strong></span><span>Đang hiện: <strong>{indexData?.filtered_total ?? 0}</strong></span><span>Cần ưu tiên: <strong>{indexData?.priority_images ?? 0}</strong></span><span>Có thể duyệt nhanh: <strong>{indexData?.safe_auto_accept_images ?? 0}</strong></span><span>Đã duyệt: <strong>{indexData?.reviewed_images ?? dataset.reviewed_images ?? 0}</strong></span><span>Ảnh khó: <strong>{indexData?.difficult_images ?? dataset.difficult_images ?? 0}</strong></span><span>Mất cân bằng: <strong>{indexData?.imbalance_ratio ? `x${indexData.imbalance_ratio}` : '—'}</strong></span></div>
    <div className="smart-review-bar"><label>Lọc ảnh<select value={reviewMode} onChange={e=>setReviewMode(e.target.value)}><option value="priority">🔥 Ưu tiên cần kiểm tra</option><option value="unreviewed">Chưa duyệt</option><option value="difficult">Ảnh khó</option><option value="all">Tất cả ảnh</option></select></label><button className="secondary" disabled={bulkBusy || !(indexData?.safe_auto_accept_images>0)} onClick={acceptSafe}>{bulkBusy?'Đang duyệt...':'Duyệt nhanh ảnh tin cậy'}</button></div>
    <div className="annotation-workspace">
      <div className="annotation-list">
        <div className="annotation-nav"><button className="secondary" disabled={currentIndex<=0 || !items.length} onClick={()=>move(-1)}>← Trước</button><span>{items.length ? `${currentIndex+1}/${items.length}` : '0/0'}</span><button className="secondary" disabled={!items.length || currentIndex>=items.length-1} onClick={()=>move(1)}>Sau →</button></div>
        <div className="annotation-frame-list" role="listbox" aria-label="Danh sách frame cần rà soát">{items.map(item=><button type="button" role="option" aria-selected={currentName===item.image_name} className={`annotation-frame-item ${currentName===item.image_name?'active':''}`} onClick={()=>setCurrentName(item.image_name)} key={item.image_name}><span className="frame-status">{item.reviewed?'✓':item.difficult?'⚠':item.priority_score>=35?'🔥':'•'}</span><span className="frame-copy"><strong title={item.image_name}>{item.image_name}</strong><small>{item.box_count} box · ưu tiên P{item.priority_score}{item.reviewed?' · đã duyệt':''}{item.difficult?' · ảnh khó':''}</small></span><span className={`frame-priority ${item.priority_score>=35?'hot':''}`}>P{item.priority_score}</span></button>)}</div>
        {!items.length && <div className="empty">Không còn ảnh trong bộ lọc này. Có thể chuyển sang “Chưa duyệt” hoặc “Tất cả ảnh”.</div>}
        <div className="class-balance">{Object.entries(indexData?.per_class || {}).map(([name,count])=><span key={name}>{vehicleLabels[name] || name}: <strong>{count}</strong></span>)}</div>
      </div>
      <div className="annotation-editor-wrap">
        {annotation && <div className="review-reason"><strong>Ưu tiên P{annotation.priority_score ?? 0}</strong> · {(annotation.priority_reasons || []).join(' · ') || 'Không có cảnh báo'}{annotation.min_confidence!=null ? ` · conf thấp nhất ${Number(annotation.min_confidence).toFixed(2)}` : ''}</div>}
        <div className="annotation-stage" ref={stageRef} onPointerDown={beginDraw} onPointerUp={finishDraw}>
          {imageUrl ? <img src={imageUrl} alt={currentName} draggable="false" /> : <div className="empty">Không có ảnh trong bộ lọc hiện tại.</div>}
          <svg viewBox="0 0 1 1" preserveAspectRatio="none">{boxes.map((box,index)=><g key={`${index}-${box.x}-${box.y}`} onPointerDown={e=>{e.stopPropagation();setSelectedBox(index);setNewClassId(box.class_id);setMessage('')}}><rect className={`annotation-box ${selectedBox===index?'selected':''}`} x={box.x-box.w/2} y={box.y-box.h/2} width={box.w} height={box.h}/><text className="annotation-label" fontSize="0.025" x={Math.max(0.002,box.x-box.w/2)} y={Math.max(0.025,box.y-box.h/2)}>Box {index+1} · {annotationClasses[box.class_id]}</text></g>)}</svg>
        </div>
        <div className={`annotation-selection ${selectedBox>=0?'has-selection':''}`}>
          {selectedBox>=0
            ? <>Đang chọn: <strong>Box {selectedBox+1} · {annotationClasses[boxes[selectedBox]?.class_id] || 'Không xác định'}</strong>. Dropdown bên dưới sẽ đổi class của box này.</>
            : <>Chưa chọn box. <strong>Kéo chuột trên ảnh để tạo box mới</strong>; class của box mới được lấy từ dropdown bên dưới.</>}
        </div>
        <div className="annotation-toolbar"><label>{selectedBox>=0?'Đổi class box đã chọn':'Class cho box mới'}<select value={selectedBox>=0 ? boxes[selectedBox]?.class_id ?? newClassId : newClassId} onChange={e=>changeSelectedClass(Number(e.target.value))}>{annotationClasses.map((name,id)=><option value={id} key={name}>{name}</option>)}</select></label><button className="danger" disabled={selectedBox<0} onClick={()=>{setBoxes(prev=>prev.filter((_,i)=>i!==selectedBox));setSelectedBox(-1)}}>Xóa box đã chọn</button><label className="check"><input type="checkbox" checked={!!annotation?.reviewed} onChange={e=>setAnnotation({...annotation,reviewed:e.target.checked})}/> Đã rà soát</label><label className="check"><input type="checkbox" checked={!!annotation?.difficult} onChange={e=>setAnnotation({...annotation,difficult:e.target.checked})}/> Ảnh khó</label><button disabled={saving || !annotation} onClick={save}>{saving?'Đang lưu...':'Lưu nhãn'}</button></div>
        <p className="hint"><strong>Trên ảnh:</strong> “Box 1 · Xe đạp” nghĩa là box số 1 hiện đang mang class Xe đạp, không phải phím 1 = Xe đạp. <strong>Phím tắt:</strong> khi đã chọn box, nhấn 1 Xe máy, 2 Xe đạp, 3 Ô tô, 4 Xe buýt, 5 Xe tải; Delete để xóa.</p>
        {message && <div className={message.startsWith('Đã')?'annotation-message ok-text':'annotation-message bad-text'}>{message}</div>}
      </div>
    </div>
  </section>
}


const formatVideoTime = value => {
  const seconds = Math.max(0, Number(value || 0))
  const minutes = Math.floor(seconds / 60)
  const rest = seconds - minutes * 60
  return `${String(minutes).padStart(2,'0')}:${rest.toFixed(3).padStart(6,'0')}`
}

function BenchmarkGateOverlay({ geometry }) {
  if (!geometry) return null
  const scale = 1000
  const x1 = Number(geometry.line_x1) * scale
  const y1 = Number(geometry.line_y1) * scale
  const x2 = Number(geometry.line_x2) * scale
  const y2 = Number(geometry.line_y2) * scale
  const road = [1,2,3,4].map(index => `${Number(geometry[`road_x${index}`]) * scale},${Number(geometry[`road_y${index}`]) * scale}`).join(' ')
  const dx = x2 - x1
  const dy = y2 - y1
  const length = Math.max(Math.hypot(dx, dy), 1)
  // signed_side() in the counting engine is positive in the (-dy, +dx) normal.
  // IN moves negative -> positive; OUT is the opposite direction.
  const nx = (-dy / length) * 92
  const ny = (dx / length) * 92
  const tx = (dx / length) * 58
  const ty = (dy / length) * 58
  const mx = (x1 + x2) / 2
  const my = (y1 + y2) / 2
  // Put IN and OUT arrows side-by-side along the gate tangent so they never overlap.
  const inCenter = {x:mx+tx, y:my+ty}
  const outCenter = {x:mx-tx, y:my-ty}
  const inStart = {x:inCenter.x-nx, y:inCenter.y-ny}
  const inEnd = {x:inCenter.x+nx, y:inCenter.y+ny}
  const outStart = {x:outCenter.x+nx, y:outCenter.y+ny}
  const outEnd = {x:outCenter.x-nx, y:outCenter.y-ny}
  return <svg className="benchmark-gate-overlay" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Vạch đếm và hướng IN OUT của benchmark">
    <defs>
      <marker id="benchmarkArrowIn" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" /></marker>
      <marker id="benchmarkArrowOut" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" /></marker>
    </defs>
    <polygon className="benchmark-road-zone" points={road} />
    <line className="benchmark-count-line-shadow" x1={x1} y1={y1} x2={x2} y2={y2} />
    <line className="benchmark-count-line" x1={x1} y1={y1} x2={x2} y2={y2} />
    <circle className="benchmark-line-handle" cx={x1} cy={y1} r="10" /><circle className="benchmark-line-handle" cx={x2} cy={y2} r="10" />
    <line className="benchmark-direction benchmark-direction-in" x1={inStart.x} y1={inStart.y} x2={inEnd.x} y2={inEnd.y} markerEnd="url(#benchmarkArrowIn)" />
    <line className="benchmark-direction benchmark-direction-out" x1={outStart.x} y1={outStart.y} x2={outEnd.x} y2={outEnd.y} markerEnd="url(#benchmarkArrowOut)" />
    <text className="benchmark-direction-label benchmark-in-label" x={inCenter.x+nx*1.22} y={inCenter.y+ny*1.22}>IN</text>
    <text className="benchmark-direction-label benchmark-out-label" x={outCenter.x-nx*1.22} y={outCenter.y-ny*1.22}>OUT</text>
    <text className="benchmark-line-label" x={mx} y={my-18}>VẠCH ĐẾM</text>
  </svg>
}

function GroundTruthBenchmark({ selectedCameraId, sessions }) {
  const [benchmarks, setBenchmarks] = useState([])
  const [selectedBenchmarkId, setSelectedBenchmarkId] = useState(null)
  const [selectedSessionId, setSelectedSessionId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [report, setReport] = useState(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [markDirection, setMarkDirection] = useState('in')
  const [markVehicle, setMarkVehicle] = useState('motorcycle')
  const [tolerance, setTolerance] = useState(0.75)
  const [playbackRate, setPlaybackRate] = useState(0.5)
  const [busy, setBusy] = useState(false)
  const [reconciling, setReconciling] = useState(false)
  const [reconcileStatus, setReconcileStatus] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const videoRef = useRef(null)

  const cameraSessions = useMemo(
    () => sessions.filter(item => Number(item.camera_id) === Number(selectedCameraId) && ['completed','stopped'].includes(String(item.status))),
    [sessions, selectedCameraId]
  )

  const readBody = async response => {
    const text = await response.text()
    if (!text) return {}
    try { return JSON.parse(text) } catch { return {detail:text} }
  }

  const loadBenchmarks = async () => {
    if (!selectedCameraId) { setBenchmarks([]); setSelectedBenchmarkId(null); return }
    try {
      const response = await fetch(`/api/benchmarks?camera_id=${selectedCameraId}&limit=50`, {cache:'no-store'})
      if (!response.ok) throw new Error('Không tải được benchmark')
      const rows = await response.json()
      setBenchmarks(rows)
      setSelectedBenchmarkId(prev => rows.some(row => row.id === Number(prev)) ? prev : (rows[0]?.id || null))
    } catch (err) { setError(err.message) }
  }

  const loadDetail = async benchmarkId => {
    if (!benchmarkId) { setDetail(null); setReport(null); return }
    try {
      const [detailRes, reportRes] = await Promise.all([
        fetch(`/api/benchmarks/${benchmarkId}`, {cache:'no-store'}),
        fetch(`/api/benchmarks/${benchmarkId}/report`, {cache:'no-store'}),
      ])
      if (!detailRes.ok) throw new Error('Không tải được ground truth')
      const data = await detailRes.json()
      setDetail(data)
      setTolerance(Number(data.tolerance_seconds || 0.75))
      setReport(reportRes.ok ? await reportRes.json() : null)
    } catch (err) { setError(err.message) }
  }

  useEffect(() => {
    setMessage(''); setError(''); setDetail(null); setReport(null)
    const latest = cameraSessions[0]?.id || null
    setSelectedSessionId(latest)
    loadBenchmarks()
  }, [selectedCameraId, cameraSessions[0]?.id])

  useEffect(() => { setReconcileStatus(''); loadDetail(selectedBenchmarkId) }, [selectedBenchmarkId])

  const compatibleCloneSource = (() => {
    if (!detail || (detail.marks?.length || 0) > 0) return null
    const g = detail.geometry || {}
    const sameLine = item => {
      const other = item.geometry || {}
      if (!item.source_url || item.source_url !== detail.source_url) return false
      const values = ['line_x1','line_y1','line_x2','line_y2']
      return Math.max(...values.map(key=>Math.abs(Number(other[key] ?? 99)-Number(g[key] ?? -99)))) <= 0.002
    }
    return benchmarks.find(item => Number(item.id) !== Number(detail.id) && Number(item.mark_count || 0) > 0 && sameLine(item)) || null
  })()

  const cloneGroundTruthIntoCurrent = async () => {
    if (!detail || !compatibleCloneSource) return
    setBusy(true); setError(''); setMessage('')
    try {
      const response = await fetch(`/api/benchmarks/${detail.id}/clone-marks`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({source_benchmark_id:Number(compatibleCloneSource.id)})
      })
      const body = await readBody(response)
      if (!response.ok) throw new Error(body.detail || 'Không sao chép được Ground Truth')
      setMessage(`Đã sao chép ${body.cloned_marks} GT từ Benchmark #${body.source_benchmark_id} sang Benchmark #${detail.id}. Không cần đánh lại clip.`)
      await loadDetail(detail.id)
      await loadBenchmarks()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const createBenchmark = async (cloneSourceBenchmarkId=null) => {
    if (!selectedSessionId) return
    setBusy(true); setError(''); setMessage('')
    try {
      const response = await fetch('/api/benchmarks', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          session_id:Number(selectedSessionId),
          tolerance_seconds:Number(tolerance || 0.75),
          clone_marks_from_benchmark_id: cloneSourceBenchmarkId ? Number(cloneSourceBenchmarkId) : null,
        })
      })
      const body = await readBody(response)
      if (!response.ok) throw new Error(body.detail || 'Không tạo được benchmark')
      await loadBenchmarks()
      setSelectedBenchmarkId(body.id)
      setMessage(body.cloned_marks
        ? `Đã tạo Benchmark #${body.id} và sao chép ${body.cloned_marks} Ground Truth. Bây giờ chỉ cần đối chiếu session AI mới.`
        : `Đã tạo Benchmark #${body.id}. Mở video và đánh dấu từng xe thật sự cắt vạch.`)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const addMark = async (directionOverride=null) => {
    if (!detail || !videoRef.current) return
    setBusy(true); setError(''); setMessage('')
    try {
      const at = Number(videoRef.current.currentTime || 0)
      const response = await fetch(`/api/benchmarks/${detail.id}/marks`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({source_time_seconds:at, direction:directionOverride || markDirection, vehicle_type:markVehicle})
      })
      const body = await readBody(response)
      if (!response.ok) throw new Error(body.detail || 'Không lưu được ground truth')
      const savedDirection = directionOverride || markDirection
      setMessage(`Đã đánh dấu ${vehicleLabels[markVehicle] || markVehicle} ${savedDirection.toUpperCase()} tại ${formatVideoTime(at)}.`)
      await loadDetail(detail.id)
      await loadBenchmarks()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const deleteMark = async markId => {
    if (!detail) return
    setBusy(true); setError(''); setMessage('')
    try {
      const response = await fetch(`/api/benchmarks/${detail.id}/marks/${markId}`, {method:'DELETE'})
      const body = await readBody(response)
      if (!response.ok) throw new Error(body.detail || 'Không xóa được mốc')
      await loadDetail(detail.id); await loadBenchmarks()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const saveTolerance = async () => {
    if (!detail) return
    setBusy(true); setError(''); setMessage('')
    try {
      const response = await fetch(`/api/benchmarks/${detail.id}`, {
        method:'PATCH', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({tolerance_seconds:Number(tolerance)})
      })
      const body = await readBody(response)
      if (!response.ok) throw new Error(body.detail || 'Không lưu được tolerance')
      setMessage(`Đã đặt cửa sổ ghép GT↔AI = ±${Number(body.tolerance_seconds).toFixed(2)} giây.`)
      await loadDetail(detail.id); await loadBenchmarks()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const reconcileBenchmark = async () => {
    if (!detail || reconciling) return
    const before = report ? `${report.matched}/${report.missed}/${report.false_positives}` : ''
    setReconciling(true); setError(''); setReconcileStatus('Đang đối chiếu lại GT ↔ AI từ dữ liệu gốc...')
    try {
      const response = await fetch(`/api/benchmarks/${detail.id}/reconcile`, {method:'POST', cache:'no-store'})
      const body = await readBody(response)
      if (!response.ok) throw new Error(body.detail || 'Không đối chiếu lại được benchmark')
      setReport(body)
      const after = `${body.matched}/${body.missed}/${body.false_positives}`
      const stamp = new Date(body.reconciled_at || Date.now()).toLocaleTimeString('vi-VN')
      setReconcileStatus(before === after
        ? `Đã đối chiếu lại lúc ${stamp}. Kết quả không đổi: khớp ${body.matched}, lọt ${body.missed}, dư ${body.false_positives}.`
        : `Đã đối chiếu lại lúc ${stamp}. Kết quả mới: khớp ${body.matched}, lọt ${body.missed}, dư ${body.false_positives}.`)
    } catch (err) { setError(err.message); setReconcileStatus('') } finally { setReconciling(false) }
  }

  useEffect(() => {
    if (!detail) return () => {}
    const handler = event => {
      const tag = String(event.target?.tagName || '').toLowerCase()
      if (['input','select','textarea'].includes(tag)) return
      const key = event.key.toLowerCase()
      if (key === 'i') { event.preventDefault(); addMark('in') }
      else if (key === 'o') { event.preventDefault(); addMark('out') }
      else if (key === '[') { event.preventDefault(); step(-1 / Math.max(1, Number(detail?.source_fps || 25))) }
      else if (key === ']') { event.preventDefault(); step(1 / Math.max(1, Number(detail?.source_fps || 25))) }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [detail?.id, markVehicle, markDirection, busy])

  const seekTo = seconds => {
    if (!videoRef.current) return
    const duration = Number(videoRef.current.duration || detail?.source_duration_seconds || 0)
    const target = Math.max(0, duration > 0 ? Math.min(Number(seconds), duration) : Number(seconds))
    videoRef.current.currentTime = target
    setCurrentTime(target)
  }
  const step = delta => seekTo((videoRef.current?.currentTime || 0) + delta)
  const fps = Number(detail?.source_fps || 25)
  const benchmarkVideoUrl = detail?.source_url ? `/ai/media/video?source_url=${encodeURIComponent(detail.source_url)}&benchmark=${detail.id}` : ''

  return <section className="benchmark-layout" id="benchmark">
    <article className="panel benchmark-panel">
      <div className="panel-head"><div><span className="panel-kicker">GROUND-TRUTH COUNTING BENCHMARK</span><h2>Đánh dấu xe thật cắt vạch trên chính clip</h2></div><span className="lock-state">V0.5.25</span></div>
      <p className="hint">Benchmark không đoán tổng xe. Bạn xem lại clip, dừng đúng lúc mỗi xe <strong>thực sự cắt vạch</strong> rồi bấm đánh dấu IN/OUT. Traffic AI lưu timecode video cho từng event và tự ghép GT ↔ AI để chỉ ra chính xác <strong>xe bị lọt</strong> và <strong>xe đếm dư</strong>.</p>
      <div className="benchmark-create-row">
        <label>Phiên AI<select value={selectedSessionId || ''} onChange={e=>setSelectedSessionId(Number(e.target.value))}><option value="">-- Chọn phiên đã chạy clip --</option>{cameraSessions.map(item=><option key={item.id} value={item.id}>Session #{item.id} · {String(item.status).toUpperCase()} · AI {item.total_vehicles} lượt</option>)}</select></label>
        <button disabled={!selectedSessionId || busy} onClick={()=>createBenchmark()}>Tạo benchmark cho phiên này</button>
        <label>Benchmark<select value={selectedBenchmarkId || ''} onChange={e=>setSelectedBenchmarkId(Number(e.target.value))}><option value="">-- Chọn benchmark --</option>{benchmarks.map(item=><option key={item.id} value={item.id}>#{item.id} · Session #{item.session_id} · GT {item.mark_count}</option>)}</select></label>
      </div>
      {compatibleCloneSource && <button className="secondary benchmark-clone-gt" disabled={busy} onClick={cloneGroundTruthIntoCurrent}>Sao chép {compatibleCloneSource.mark_count} GT từ Benchmark #{compatibleCloneSource.id} sang Benchmark #{detail.id}</button>}
      {detail?.marks?.length > 0 && selectedSessionId && Number(selectedSessionId) !== Number(detail.session_id) && <button className="secondary benchmark-clone-gt benchmark-clone-create" disabled={busy} onClick={()=>createBenchmark(detail.id)}>Tạo benchmark mới + sao chép {detail.marks.length} GT sang Session #{selectedSessionId}</button>}
      {error && <div className="source-status bad"><strong>⚠ Benchmark</strong><span>{error}</span></div>}
      {message && <div className="source-status ok"><strong>✓ Benchmark</strong><span>{message}</span></div>}
      {detail ? <>
        <div className="benchmark-video-wrap">
          <video ref={videoRef} key={detail.id} src={benchmarkVideoUrl} controls preload="metadata" onLoadedMetadata={e=>{e.currentTarget.playbackRate=playbackRate}} onTimeUpdate={e=>setCurrentTime(e.currentTarget.currentTime)} />
          <BenchmarkGateOverlay geometry={detail.geometry} />
          <div className="benchmark-clock"><strong>{formatVideoTime(currentTime)}</strong><span>{fps ? `${fps.toFixed(2)} FPS` : 'FPS —'} · Session #{detail.session_id}</span></div>
          <div className="benchmark-overlay-legend"><strong>Vạch benchmark</strong><span>↓/↑ theo mũi tên IN/OUT trên hình</span></div>
        </div>
        <div className="benchmark-step-row"><button className="secondary" onClick={()=>step(-1/fps)}>← 1 frame</button><button className="secondary" onClick={()=>step(-0.5)}>−0,5s</button><label className="benchmark-speed">Tốc độ<select value={playbackRate} onChange={e=>{const rate=Number(e.target.value);setPlaybackRate(rate);if(videoRef.current)videoRef.current.playbackRate=rate}}><option value="0.25">0.25×</option><option value="0.5">0.5×</option><option value="0.75">0.75×</option><option value="1">1×</option></select></label><button className="secondary" onClick={()=>step(0.5)}>+0,5s</button><button className="secondary" onClick={()=>step(1/fps)}>1 frame →</button></div><p className="benchmark-hotkeys">Phím nhanh: <strong>I</strong> = đánh dấu IN · <strong>O</strong> = OUT · <strong>[</strong>/<strong>]</strong> = lùi/tiến 1 frame. Mặc định 0.5×. Chỉ bấm I/O khi tâm/quỹ đạo xe thật sự cắt đúng vạch vàng đang hiển thị trên video.</p>
        <div className="benchmark-mark-row">
          <label>Hướng<select value={markDirection} onChange={e=>setMarkDirection(e.target.value)}><option value="in">IN</option><option value="out">OUT</option><option value="unknown">Chưa rõ</option></select></label>
          <label>Loại xe<select value={markVehicle} onChange={e=>setMarkVehicle(e.target.value)}>{Object.entries(vehicleLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
          <button disabled={busy} onClick={()=>addMark()}>+ Đánh dấu GT tại {formatVideoTime(currentTime)}</button>
        </div>
        <div className="benchmark-mark-list">{detail.marks?.length ? detail.marks.map(mark=><div className="benchmark-mark" key={mark.id}><button className="time-link" onClick={()=>seekTo(mark.source_time_seconds)}>{formatVideoTime(mark.source_time_seconds)}</button><span>{String(mark.direction).toUpperCase()} · {vehicleLabels[mark.vehicle_type] || mark.vehicle_type}</span><button className="danger compact" disabled={busy} onClick={()=>deleteMark(mark.id)}>Xóa</button></div>) : <div className="empty">Chưa có ground-truth mark. Phát clip, dừng khi xe cắt vạch rồi đánh dấu.</div>}</div>
      </> : <div className="empty">Chọn một phiên đã chạy clip rồi tạo benchmark.</div>}
    </article>

    <article className="panel benchmark-report-panel">
      <div className="panel-head"><div><span className="panel-kicker">BENCHMARK REPORT</span><h2>Xe lọt / đếm dư theo timecode</h2></div></div>
      {detail && <><div className="tolerance-row"><label>Cửa sổ ghép ± giây<input type="number" min="0.05" max="3" step="0.05" value={tolerance} onChange={e=>setTolerance(e.target.value)} /></label><button className="secondary" disabled={busy || reconciling} onClick={saveTolerance}>Áp dụng</button><button disabled={busy || reconciling} onClick={reconcileBenchmark}>{reconciling ? 'Đang đối chiếu…' : 'Đối chiếu lại'}</button></div>{reconcileStatus && <div className="benchmark-reconcile-status">{reconcileStatus}</div>}</>}
      {report ? <>
        <div className="benchmark-metrics"><div><span>Ground truth</span><strong>{report.ground_truth_total}</strong></div><div><span>AI đếm</span><strong>{report.ai_total}</strong></div><div><span>Khớp</span><strong>{report.matched}</strong></div><div className={report.missed ? 'metric-bad' : ''}><span>Lọt không đếm</span><strong>{report.missed}</strong></div><div className={report.false_positives ? 'metric-warn' : ''}><span>Đếm dư</span><strong>{report.false_positives}</strong></div><div><span>Sai số tổng</span><strong>{report.count_error > 0 ? '+' : ''}{report.count_error}</strong></div></div>
        <div className="benchmark-scores"><span>Counting Recall <strong>{(Number(report.counting_recall || 0)*100).toFixed(1)}%</strong></span><span>Precision <strong>{(Number(report.counting_precision || 0)*100).toFixed(1)}%</strong></span><span>F1 <strong>{(Number(report.counting_f1 || 0)*100).toFixed(1)}%</strong></span><span>Class đúng <strong>{report.class_accuracy == null ? '—' : `${(report.class_accuracy*100).toFixed(1)}%`}</strong></span></div>
        {report.integrity && <div className={`source-status ${report.integrity.ok ? 'ok' : 'warn'}`}><strong>{report.integrity.ok ? '✓ Benchmark Integrity OK' : '⚠ Benchmark Integrity cần chú ý'}</strong><span>Worker đề xuất {report.integrity.worker_total} · DB lưu {report.integrity.persisted_events} · event có timecode {report.integrity.timed_events} · backend gộp {report.integrity.dedup_suppressed_events} · Human Guard loại {report.integrity.human_guard_rejections}{report.integrity.missing_timecode ? ` · thiếu timecode ${report.integrity.missing_timecode}` : ''}.</span></div>}
        {report.dominant_miss_reason && <div className="source-status bad"><strong>Nguyên nhân lọt nổi bật: {missReasonLabels[report.dominant_miss_reason] || report.dominant_miss_reason}</strong><span>{Object.entries(report.miss_reason_counts || {}).map(([reason,count])=>`${missReasonLabels[reason] || reason}: ${count}`).join(' · ')}</span></div>}
        {report.dominant_false_positive_reason && <div className="source-status warn"><strong>Nguyên nhân đếm dư nghi ngờ: {falsePositiveReasonLabels[report.dominant_false_positive_reason] || report.dominant_false_positive_reason}</strong><span>{Object.entries(report.false_positive_reason_counts || {}).map(([reason,count])=>`${falsePositiveReasonLabels[reason] || reason}: ${count}`).join(' · ')}</span></div>}
        {report.legacy_ai_events_without_source_time > 0 && <div className="source-status bad"><strong>⚠ Phiên cũ thiếu timecode</strong><span>{report.legacy_ai_events_without_source_time} event được tạo trước V0.5.19 nên không thể ghép chính xác. Hãy chạy lại clip một lần trên V0.5.19 rồi benchmark session mới.</span></div>}
        <h3 className="benchmark-subhead">Lọt không đếm ({report.missed_items?.length || 0})</h3>
        <div className="benchmark-diff-list">{report.missed_items?.length ? report.missed_items.map(item=><button key={`m-${item.ground_truth_id}`} className="diff-row missed" onClick={()=>seekTo(item.time)}><strong>{formatVideoTime(item.time)}</strong><span>{String(item.direction).toUpperCase()} · {vehicleLabels[item.vehicle_type] || item.vehicle_type}</span><em>{item.diagnosis?.reason ? (missReasonLabels[item.diagnosis.reason] || item.diagnosis.reason) : 'GT có · AI không có'}</em></button>) : <div className="empty">Chưa có xe lọt trong cửa sổ ghép hiện tại.</div>}</div>
        <h3 className="benchmark-subhead">AI đếm dư ({report.false_positive_items?.length || 0})</h3>
        <div className="benchmark-diff-list">{report.false_positive_items?.length ? report.false_positive_items.map(item=><button key={`f-${item.ai_event_id}`} className="diff-row false-positive" onClick={()=>seekTo(item.time)}><strong>{formatVideoTime(item.time)}</strong><span>{String(item.direction).toUpperCase()} · {vehicleLabels[item.vehicle_type] || item.vehicle_type}</span><em>{item.reason ? (falsePositiveReasonLabels[item.reason] || item.reason) : 'AI có · GT không có'}</em></button>) : <div className="empty">Chưa có lượt đếm dư trong cửa sổ ghép hiện tại.</div>}</div>
        <h3 className="benchmark-subhead">Theo loại phương tiện</h3>
        <div className="benchmark-class-grid">{Object.entries(report.per_class || {}).map(([name,item])=><div key={name}><span>{vehicleLabels[name] || name}</span><strong>GT {item.ground_truth} · AI {item.ai}</strong><small>Δ {item.difference > 0 ? '+' : ''}{item.difference}</small></div>)}</div>
      </> : <div className="empty">Tạo/chọn benchmark để xem Recall, Precision, xe lọt và xe đếm dư theo từng timecode.</div>}
    </article>
  </section>
}

function App() {
  const [previewMode, setPreviewMode] = useState('smooth')
  const [overlayReady, setOverlayReady] = useState(false)
  const [summary, setSummary] = useState(null)
  const [health, setHealth] = useState(null)
  const [systemStatus, setSystemStatus] = useState(null)
  const [cameras, setCameras] = useState([])
  const [events, setEvents] = useState([])
  const [sessions, setSessions] = useState([])
  const [pipelines, setPipelines] = useState([])
  const [videoSources, setVideoSources] = useState([])
  const [sourceStatus, setSourceStatus] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState(defaultCameraForm())
  const [lineForm, setLineForm] = useState({confidence_threshold:0.06,line_x1:0.32,line_y1:0.59,line_x2:0.84,line_y2:0.59,road_x1:0.20,road_y1:0.16,road_x2:0.80,road_y2:0.16,road_x3:0.96,road_y3:0.98,road_x4:0.04,road_y4:0.98})
  const [roadProposal, setRoadProposal] = useState(null)
  const [datasets, setDatasets] = useState([])
  const [trainingRuns, setTrainingRuns] = useState([])
  const [datasetForm, setDatasetForm] = useState({name:'Dataset giao thông Việt Nam', every_n_frames:15, max_images:600, smart_dedupe:true, min_change_ratio:0.008})
  const [selectedDatasetId, setSelectedDatasetId] = useState(null)
  const [trainingForm, setTrainingForm] = useState({epochs:80, imgsz:640, batch:8, base_model:'yolo26s.pt'})
  const countingGeometryState = useMemo(() => validateCountingGeometry(lineForm), [lineForm])

  const readApiBody = async (response) => {
    const text = await response.text()
    if (!text) return {}
    const type = response.headers.get('content-type') || ''
    if (type.includes('application/json')) {
      try { return JSON.parse(text) } catch {}
    }
    try { return JSON.parse(text) } catch {
      return { detail: text, raw: text }
    }
  }

  const load = async () => {
    try {
      const [summaryRes, healthRes, systemStatusRes, camerasRes, eventsRes, pipelinesRes, sessionsRes, videosRes, datasetsRes, trainingRes] = await Promise.all([
        fetch('/api/dashboard/summary'), fetch('/api/health'), fetch('/api/system/status'), fetch('/api/cameras'),
        fetch('/api/events?limit=20'), fetch('/api/pipelines'), fetch('/api/sessions?limit=50'), fetch('/api/sources/videos'),
        fetch('/api/datasets'), fetch('/api/training/runs')
      ])
      if (![summaryRes, healthRes, camerasRes, eventsRes, sessionsRes].every(r => r.ok)) throw new Error('API chưa sẵn sàng')
      setSummary(await summaryRes.json())
      setHealth(await healthRes.json())
      setSystemStatus(systemStatusRes.ok ? await systemStatusRes.json() : null)
      const cameraData = await camerasRes.json()
      setCameras(cameraData)
      setEvents(await eventsRes.json())
      setPipelines(pipelinesRes.ok ? await pipelinesRes.json() : [])
      setSessions(await sessionsRes.json())
      setVideoSources(videosRes.ok ? await videosRes.json() : [])
      const datasetData = datasetsRes.ok ? await datasetsRes.json() : []
      setDatasets(datasetData)
      setTrainingRuns(trainingRes.ok ? await trainingRes.json() : [])
      if (cameraData.length) setSelectedId(prev => prev || cameraData[0].id)
      if (datasetData.length) setSelectedDatasetId(prev => datasetData.some(d=>d.id===Number(prev)) ? prev : datasetData[0].id)
      else setSelectedDatasetId(null)
    } catch (err) {
      setError(err.message || 'Không thể tải dữ liệu')
    }
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 1800)
    return () => clearInterval(id)
  }, [])

  // Runtime counters are lightweight and need to feel live. Poll only the AI
  // registry more frequently instead of refreshing every dashboard API at 10 Hz.
  useEffect(() => {
    let cancelled = false
    const refreshPipelines = async () => {
      try {
        const response = await fetch('/api/pipelines', { cache: 'no-store' })
        if (response.ok && !cancelled) setPipelines(await response.json())
      } catch {}
    }
    const id = setInterval(refreshPipelines, 400)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  const selected = cameras.find(c => c.id === Number(selectedId))
  const selectedDataset = datasets.find(d => d.id === Number(selectedDatasetId))
  const latestTraining = trainingRuns.find(r => r.dataset_id === Number(selectedDatasetId))
  const activePipeline = pipelines.find(p => p.camera_id === Number(selectedId) && ['starting', 'warming', 'running'].includes(p.status))
  const latestPipeline = pipelines.find(p => p.camera_id === Number(selectedId))
  const sessionPipeline = activePipeline || latestPipeline
  const sessionCounts = sessionPipeline?.counts_by_type || {}
  const vehicleRows = useMemo(() => Object.entries(vehicleLabels).map(([key, label]) => ({ label, value: sessionCounts?.[key] || 0 })), [sessionCounts])
  const sessionTotal = sessionPipeline?.total_count ?? 0
  const videoPathSet = useMemo(() => new Set(videoSources.map(v => v.source_url)), [videoSources])
  const selectedVideoMissing = selected?.source_type === 'video' && sourceStatus?.valid === false
  const sourceAutoRepairAvailable = selectedVideoMissing && !!sourceStatus?.suggested_source_url
  const previewUrl = selected ? `/api/cameras/${selected.id}/preview.jpg?rev=${encodeURIComponent(selected.updated_at || '')}` : ''
  const nativeVideoUrl = selected?.source_type === 'video' ? `/ai/media/video?source_url=${encodeURIComponent(selected.source_url)}&v=${activePipeline?.session_id || 0}` : ''
  const smoothNativePlayback = !!activePipeline && selected?.source_type === 'video' && previewMode === 'smooth'
  const overlayStreamUrl = activePipeline ? `/ai/streams/${selected?.id}.mjpg?session=${activePipeline.session_id}` : ''

  useEffect(() => {
    setOverlayReady(false)
    setRoadProposal(null)
  }, [selectedId, activePipeline?.session_id])

  useEffect(() => {
    if (!selected) return
    setEditingId(selected.id)
    setForm({
      name: selected.name, code: selected.code, source_type: selected.source_type, source_url: selected.source_url,
      location: selected.location || '', confidence_threshold: selected.confidence_threshold ?? 0.06,
      line_x1: selected.line_x1 ?? 0.32, line_y1: selected.line_y1 ?? 0.59,
      line_x2: selected.line_x2 ?? 0.84, line_y2: selected.line_y2 ?? 0.59,
      road_x1:selected.road_x1 ?? 0.20, road_y1:selected.road_y1 ?? 0.16, road_x2:selected.road_x2 ?? 0.80, road_y2:selected.road_y2 ?? 0.16,
      road_x3:selected.road_x3 ?? 0.96, road_y3:selected.road_y3 ?? 0.98, road_x4:selected.road_x4 ?? 0.04, road_y4:selected.road_y4 ?? 0.98
    })
    setLineForm({
      confidence_threshold: selected.confidence_threshold ?? 0.06,
      line_x1: selected.line_x1 ?? 0.32, line_y1: selected.line_y1 ?? 0.59,
      line_x2: selected.line_x2 ?? 0.84, line_y2: selected.line_y2 ?? 0.59,
      road_x1:selected.road_x1 ?? 0.20, road_y1:selected.road_y1 ?? 0.16, road_x2:selected.road_x2 ?? 0.80, road_y2:selected.road_y2 ?? 0.16,
      road_x3:selected.road_x3 ?? 0.96, road_y3:selected.road_y3 ?? 0.98, road_x4:selected.road_x4 ?? 0.04, road_y4:selected.road_y4 ?? 0.98
    })
  }, [selectedId, selected?.updated_at])

  useEffect(() => {
    let cancelled = false
    if (!selected) { setSourceStatus(null); return () => {} }
    fetch(`/api/cameras/${selected.id}/source-status`)
      .then(async r => { const data = await r.json(); if (!r.ok) throw new Error(data.detail || 'Không kiểm tra được nguồn'); if (!cancelled) setSourceStatus(data) })
      .catch(err => { if (!cancelled) setSourceStatus({ valid:false, message:err.message }) })
    return () => { cancelled = true }
  }, [selectedId, selected?.source_url, selected?.source_type])

  const saveCamera = async e => {
    e.preventDefault(); setBusy(true); setError(''); setNotice('')
    try {
      const endpoint = editingId ? `/api/cameras/${editingId}` : '/api/cameras'
      const method = editingId ? 'PATCH' : 'POST'
      const response = await fetch(endpoint, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form) })
      const body = await readApiBody(response)
      if (!response.ok) throw new Error(body.detail || (editingId ? 'Không cập nhật được camera' : 'Không tạo được camera'))
      setSelectedId(body.id); setEditingId(body.id)
      setNotice(editingId ? `Đã cập nhật ${body.code}.` : `Đã tạo ${body.code}.`)
      await load()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const beginNewCamera = () => {
    const nextNumber = Math.max(0, ...cameras.map(c => Number(String(c.code).match(/(\d+)$/)?.[1] || 0))) + 1
    setEditingId(null)
    setForm({...defaultCameraForm(), name:'Camera mới', code:`CAM-${String(nextNumber).padStart(3,'0')}`})
    setNotice('Đang tạo camera mới. Chọn nguồn video rồi bấm Tạo camera.'); setError('')
  }

  const togglePipeline = async () => {
    if (!selected) return
    setBusy(true); setError(''); setNotice('')
    try {
      const action = activePipeline ? 'stop' : 'start'
      const response = await fetch(`/api/cameras/${selected.id}/${action}`, { method: 'POST' })
      const body = await readApiBody(response)
      if (!response.ok) throw new Error(body.detail || 'Không thể thay đổi pipeline')
      if (action === 'start') {
        const fresh = body.pipeline || {camera_id:selected.id, session_id:body.session_id, status:'starting', total_count:0, in_count:0, out_count:0, counts_by_type:{}}
        setPipelines(prev => [fresh, ...prev.filter(p => p.camera_id !== selected.id)])
      }
      if (action === 'start' && body.source_repaired) setNotice(`Đã tự sửa nguồn thành ${body.source_url} và bắt đầu AI. Bộ đếm phiên mới đã reset về 0.`)
      else setNotice(action === 'start' ? 'AI đã bắt đầu. Bộ đếm phiên mới đã reset về 0; lịch sử PostgreSQL vẫn được giữ.' : 'Đã dừng AI. Bây giờ có thể chỉnh vạch đếm.')
      await load()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const applyPreset = preset => {
    if (activePipeline) return
    if (preset === 'road-horizontal') setLineForm({...lineForm, line_x1:0.32,line_y1:0.59,line_x2:0.84,line_y2:0.59})
    if (preset === 'horizontal') setLineForm({...lineForm, line_x1:0.16,line_y1:0.55,line_x2:0.84,line_y2:0.55})
    if (preset === 'vertical') setLineForm({...lineForm, line_x1:0.52,line_y1:0.22,line_x2:0.52,line_y2:0.90})
  }

  const applyRoadZonePreset = preset => {
    if (activePipeline) return
    if (preset === 'roadway') setLineForm({...lineForm,road_x1:0.20,road_y1:0.16,road_x2:0.80,road_y2:0.16,road_x3:0.96,road_y3:0.98,road_x4:0.04,road_y4:0.98})
    if (preset === 'narrow') setLineForm({...lineForm,road_x1:0.30,road_y1:0.18,road_x2:0.70,road_y2:0.18,road_x3:0.86,road_y3:0.98,road_x4:0.14,road_y4:0.98})
    if (preset === 'full') setLineForm({...lineForm,road_x1:0,road_y1:0,road_x2:1,road_y2:0,road_x3:1,road_y3:1,road_x4:0,road_y4:1})
  }

  const moveLine = (dx, dy) => {
    if (activePipeline) return
    const x1=Number(lineForm.line_x1), y1=Number(lineForm.line_y1), x2=Number(lineForm.line_x2), y2=Number(lineForm.line_y2)
    const safeDx=Math.min(1-Math.max(x1,x2),Math.max(-Math.min(x1,x2),dx))
    const safeDy=Math.min(1-Math.max(y1,y2),Math.max(-Math.min(y1,y2),dy))
    setLineForm({...lineForm,line_x1:x1+safeDx,line_y1:y1+safeDy,line_x2:x2+safeDx,line_y2:y2+safeDy})
  }

  const resizeLine = factor => {
    if (activePipeline) return
    const x1=Number(lineForm.line_x1), y1=Number(lineForm.line_y1), x2=Number(lineForm.line_x2), y2=Number(lineForm.line_y2)
    const mx=(x1+x2)/2,my=(y1+y2)/2
    setLineForm({...lineForm,line_x1:clamp01(mx+(x1-mx)*factor),line_y1:clamp01(my+(y1-my)*factor),line_x2:clamp01(mx+(x2-mx)*factor),line_y2:clamp01(my+(y2-my)*factor)})
  }

  const saveCountingLine = async () => {
    if (!selected || activePipeline) return
    if (!countingGeometryState.valid) { setError(countingGeometryState.message); return }
    setBusy(true); setError(''); setNotice('')
    try {
      const body = Object.fromEntries(Object.entries(lineForm).map(([k,v]) => [k, Number(v)]))
      const response = await fetch(`/api/cameras/${selected.id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) })
      const result = await readApiBody(response)
      if (!response.ok) throw new Error(result.detail || 'Không cập nhật được counting line')
      setNotice('Đã lưu vạch + vùng lòng đường. Chỉ xe cắt vạch vàng bên trong vùng xanh mới được tính IN/OUT.')
      await load()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const requestRoadProposal = async () => {
    if (!selected || !sessionPipeline?.calibration_ready) return
    setBusy(true); setError(''); setNotice('')
    try {
      const response = await fetch(`/api/cameras/${selected.id}/road-proposal`, {cache:'no-store'})
      const body = await readApiBody(response)
      if (!response.ok) throw new Error(body.detail || 'Chưa tạo được đề xuất vùng lòng đường')
      const geometry = body.geometry || {}
      setRoadProposal(body)
      setLineForm(prev => ({...prev, ...geometry}))
      setNotice(`AI đã đề xuất vùng lòng đường từ ${body.moving_track_count} track / ${body.sample_count} điểm chuyển động · chất lượng ${Math.round((body.quality || 0)*100)}%. Xem vùng xanh/vạch vàng rồi bấm “Dừng AI + áp dụng đề xuất”.`)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const applyRoadProposal = async () => {
    if (!selected || !roadProposal?.geometry) return
    setBusy(true); setError(''); setNotice('')
    try {
      if (activePipeline) {
        const stopResponse = await fetch(`/api/cameras/${selected.id}/stop`, {method:'POST'})
        const stopBody = await readApiBody(stopResponse)
        if (!stopResponse.ok) throw new Error(stopBody.detail || 'Không dừng được AI để áp dụng đề xuất')
      }
      const body = {...roadProposal.geometry, confidence_threshold:Number(lineForm.confidence_threshold)}
      const response = await fetch(`/api/cameras/${selected.id}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)})
      const result = await readApiBody(response)
      if (!response.ok) throw new Error(result.detail || 'Không lưu được đề xuất Road Zone')
      setRoadProposal(null)
      setNotice('Đã dừng AI và lưu đề xuất Road Zone + vạch đếm. Bấm Chạy AI để kiểm thử cấu hình mới.')
      await load()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const applySuggestedSource = () => {
    if (!selected || !sourceStatus?.suggested_source_url) return
    setEditingId(selected.id); setForm(prev => ({...prev, source_type:'video', source_url:sourceStatus.suggested_source_url}))
    setNotice('Đã chọn nguồn gợi ý. Bấm Cập nhật camera để lưu vào PostgreSQL.')
  }

  const lineField = (name, label) => <label className="line-field"><span>{label}</span><input disabled={!!activePipeline} type="number" min="0" max="1" step="0.01" value={Number(lineForm[name]).toFixed(2)} onChange={e=>setLineForm({...lineForm,[name]:Number(e.target.value)})}/></label>

const createDataset = async () => {
  if (!selected) return
  setBusy(true); setError(''); setNotice('')
  try {
    const response = await fetch('/api/datasets', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:datasetForm.name, camera_id:selected.id, every_n_frames:Number(datasetForm.every_n_frames), max_images:Number(datasetForm.max_images), smart_dedupe:!!datasetForm.smart_dedupe, min_change_ratio:Number(datasetForm.min_change_ratio)})})
    const body = await readApiBody(response); if (!response.ok) throw new Error(body.detail || `Không tạo được dataset (HTTP ${response.status})`)
    setSelectedDatasetId(body.id); setNotice(`Đã giữ ${body.image_count} frame đa dạng${body.skipped_similar!=null ? `, bỏ ${body.skipped_similar} frame gần trùng` : ''} trong dataset ${body.name}.`); await load()
  } catch (err) { setError(err.message) } finally { setBusy(false) }
}

const datasetAction = async action => {
  if (!selectedDataset) return
  setBusy(true); setError(''); setNotice('')
  try {
    const payload = action === 'autolabel' ? {confidence:0.25} : {train_ratio:0.70,val_ratio:0.20,seed:2026}
    const response = await fetch(`/api/datasets/${selectedDataset.id}/${action}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)})
    const body = await readApiBody(response); if (!response.ok) throw new Error(body.detail || `Không thực hiện được ${action} (HTTP ${response.status})`)
    if (action === 'autolabel') setNotice(`Auto-label xong: ${body.labeled_images}/${body.image_count} ảnh có phương tiện, ${body.box_count} bounding box. Đây là nhãn gợi ý, cần rà soát trước khi train.`)
    else setNotice(`Dataset ready: train ${body.train_count}, val ${body.val_count}, test ${body.test_count}.`)
    await load()
  } catch (err) { setError(err.message) } finally { setBusy(false) }
}

const resetDatasetLabels = async () => {
  if (!selectedDataset || busy) return
  if (!window.confirm(`Làm lại nhãn cho dataset “${selectedDataset.name}”? Ảnh gốc vẫn giữ, nhưng pseudo-label, trạng thái đã duyệt và train/val/test hiện tại sẽ bị xóa.`)) return
  setBusy(true); setError(''); setNotice('')
  try {
    const response = await fetch(`/api/datasets/${selectedDataset.id}/reset-labels`, {method:'POST'})
    const body = await readApiBody(response); if (!response.ok) throw new Error(body.detail || 'Không reset được nhãn dataset')
    setNotice(`Đã xóa nhãn cũ và giữ lại ${body.image_count || 0} ảnh gốc. Bây giờ chạy Auto-label lại.`); await load()
  } catch (err) { setError(err.message) } finally { setBusy(false) }
}

const deleteDataset = async () => {
  if (!selectedDataset || busy) return
  if (!window.confirm(`XÓA dataset “${selectedDataset.name}” cùng toàn bộ ảnh và thư mục training-runs liên quan? best.pt đã export trong thư mục models vẫn được giữ. Thao tác này không hoàn tác.`)) return
  setBusy(true); setError(''); setNotice('')
  try {
    const deletedName = selectedDataset.name
    const response = await fetch(`/api/datasets/${selectedDataset.id}`, {method:'DELETE'})
    const body = await readApiBody(response); if (!response.ok) throw new Error(body.detail || 'Không xóa được dataset')
    setSelectedDatasetId(null); setNotice(`Đã xóa dataset ${deletedName} và ảnh cũ. Model đã export trong models vẫn được giữ.`); await load()
  } catch (err) { setError(err.message) } finally { setBusy(false) }
}

const startTraining = async () => {
  if (!selectedDataset) return
  setBusy(true); setError(''); setNotice('')
  try {
    const response = await fetch('/api/training/runs', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({dataset_id:selectedDataset.id, base_model:trainingForm.base_model, epochs:Number(trainingForm.epochs), imgsz:Number(trainingForm.imgsz), batch:Number(trainingForm.batch), device:'auto'})})
    const body = await readApiBody(response); if (!response.ok) throw new Error(body.detail || `Không khởi động được training (HTTP ${response.status})`)
    setNotice(`Đã bắt đầu Training Run #${body.id} trên ${trainingForm.base_model}.`); await load()
  } catch (err) { setError(err.message) } finally { setBusy(false) }
}

const activateTraining = async run => {
  setBusy(true); setError(''); setNotice('')
  try {
    const response = await fetch(`/api/training/runs/${run.id}/activate`, {method:'POST'})
    const body = await readApiBody(response); if (!response.ok) throw new Error(body.detail || `Không kích hoạt được model (HTTP ${response.status})`)
    setNotice(body.already_active ? `${body.name} đã là model đang dùng.` : `Đã kích hoạt ${body.name}: ${body.model_path}. Phiên AI mới sẽ dùng model này.`); await load()
  } catch (err) { setError(err.message) } finally { setBusy(false) }
}

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><img className="brand-logo" src={`/logo.svg?v=${APP_VERSION}`} alt="Traffic AI" /><div><strong>Traffic AI</strong><span>YOLO26s + ByteTrack</span></div></div>
      <nav><a className="active" href="#overview">Tổng quan</a><a href="#live">Giám sát</a><a href="#benchmark">Benchmark</a><a href="#cameras">Camera</a><a href="#training">Dữ liệu & huấn luyện</a><a href="#annotation">Gán nhãn</a><a href="#events">Sự kiện</a></nav>
      <div className="sidebar-footer">V{APP_VERSION} · Strict Gate</div>
    </aside>
    <main>
      <header className="topbar"><div><p className="eyebrow">ĐỒ ÁN TRÍ TUỆ NHÂN TẠO</p><h1>Phát hiện, theo dõi và đếm phương tiện</h1></div><div className={`health ${health?.status === 'ok' ? 'online' : ''}`}><span className="dot" />{health?.status === 'ok' ? 'Hệ thống hoạt động' : 'Đang kết nối'}</div></header>
      {error && <div className="error-banner">{error}</div>}{notice && <div className="notice-banner">{notice}</div>}
      <section className="stats-grid" id="overview">
        <StatCard title="Camera" value={summary?.total_cameras ?? '—'} note={`${summary?.active_cameras ?? 0} đang chạy`} />
        <StatCard title="Phương tiện phiên" value={sessionTotal} note={`Lịch sử PostgreSQL: ${summary?.total_events ?? 0}`} />
        <StatCard title="Phiên đếm" value={summary?.running_sessions ?? '—'} note="Đang hoạt động" />
        <StatCard title="GPU" value={systemStatus?.ai?.gpu?.available ? 'CUDA' : (systemStatus?.ai_service === 'ready' ? 'CPU' : '—')} note={systemStatus?.ai?.gpu?.name || systemStatus?.ai?.model || 'AI service'} />
      </section>

      <section className="content-grid" id="live">
        <article className="panel camera-panel">
          <div className="panel-head"><div><span className="panel-kicker">LIVE AI</span><h2>Camera Preview</h2></div><div className="panel-actions">{activePipeline && selected?.source_type === 'video' && <div className="preview-switch" title="Phát mượt dùng trình phát video native; AI Overlay dùng MJPEG đã vẽ box."><button type="button" className={previewMode === 'smooth' ? 'active' : 'secondary'} onClick={()=>setPreviewMode('smooth')}>Phát mượt</button><button type="button" className={previewMode === 'overlay' ? 'active' : 'secondary'} onClick={()=>{setOverlayReady(false);setPreviewMode('overlay')}}>AI Overlay</button></div>}<button className={activePipeline ? 'danger' : ''} disabled={!selected || busy || (!activePipeline && selectedVideoMissing && !sourceAutoRepairAvailable)} onClick={togglePipeline}>{activePipeline ? 'Dừng AI' : 'Chạy AI'}</button></div></div>
          <div className={`camera-stage ${activePipeline && selected?.source_type === 'video' ? 'dual-preview-stage' : ''}`}>
            {activePipeline && selected?.source_type === 'video' ? <>
              <video key={`${selected.id}-${activePipeline.session_id}`} className={`preview-layer native-preview ${previewMode === 'smooth' || !overlayReady ? 'visible' : ''}`} src={nativeVideoUrl} autoPlay muted controls={previewMode === 'smooth'} playsInline preload="auto" />
              {previewMode === 'overlay' && <img className={`preview-layer overlay-preview ${overlayReady ? 'visible' : ''}`} src={overlayStreamUrl} alt="Live AI stream" onLoad={()=>setOverlayReady(true)} />}
              {(previewMode === 'smooth' || !overlayReady || roadProposal) && <><RoadZoneOverlay zone={lineForm} /><CountingLineOverlay line={lineForm} /></>}
              {previewMode === 'smooth' && <span className="smooth-badge">Phát mượt · AI xử lý nền</span>}
              {previewMode === 'overlay' && !overlayReady && <span className="overlay-loading-badge">Đang nối AI Overlay · video vẫn phát trong lúc chờ frame AI đầu tiên</span>}{roadProposal && <span className="proposal-badge">ĐỀ XUẤT AI · chưa áp dụng</span>}
            </> : activePipeline ? <img src={overlayStreamUrl} alt="Live AI stream" /> : <img src={previewUrl} alt="Preview camera" onLoad={e=>{e.currentTarget.style.visibility='visible'}} onError={e=>{e.currentTarget.style.visibility='hidden'}} />}
          </div>
          <div className="camera-select"><label>Camera</label><select value={selectedId || ''} onChange={e => setSelectedId(Number(e.target.value))}><option value="">-- Chọn camera --</option>{cameras.map(c => <option key={c.id} value={c.id}>{c.code} · {c.name}</option>)}</select><span>{activePipeline ? `INFERENCE · ${activePipeline.model_name || 'model đang kích hoạt'} · ${activePipeline.hybrid_mode ? `HYBRID detect ${activePipeline.detector_model_name || 'pretrained'} + refine best.pt` : `DIRECT ${activePipeline.detector_model_name || activePipeline.model_name || ''}`} · AI ${activePipeline.processing_progress ?? 0}% · FPS ${activePipeline.fps}/${activePipeline.source_fps || '-'} · RT x${activePipeline.realtime_factor ?? 0} · lag ${activePipeline.playback_lag_seconds ?? 0}s · ${activePipeline.inference_ms ?? 0} ms · ${String(activePipeline.device || '?').toUpperCase()} · DET ${activePipeline.detections_current_frame ?? 0} · chưa ID ${activePipeline.untracked_detections ?? 0} · track ${activePipeline.active_tracks ?? 0} · road ${activePipeline.road_tracks_current_frame ?? 0} · gộp bus/truck ${activePipeline.suppressed_class_duplicates_current_frame ?? 0} · Human Guard ${activePipeline.human_guard_rejections ?? 0} · Rider giữ ${activePipeline.rider_guard_rescues ?? 0} · Guard chờ ${activePipeline.human_guard_pending_crossings ?? 0} · Bracket+ ${activePipeline.bracket_confirm_rescues ?? 0} · DB ${activePipeline.persisted_events ?? 0} · dedup ${activePipeline.deduplicated_events ?? 0} · seen ${activePipeline.detected_tracks ?? 0} · calib ${activePipeline.calibration_moving_tracks ?? 0}T/${activePipeline.calibration_samples ?? 0}P · DETECT ${(activePipeline.detection_roi_mode || 'full').toUpperCase()} · Tổng ${activePipeline.total_count} · IN ${activePipeline.in_count ?? 0} · OUT ${activePipeline.out_count ?? 0} · trực tiếp ${activePipeline.direct_crossings ?? 0} · nội suy ${activePipeline.interpolated_crossings ?? 0} · cứu ${activePipeline.rescued_crossings ?? 0} · loại ngoài lòng đường ${activePipeline.rejected_outside_road ?? 0}` : selected?.source_url || 'Chưa có camera'}</span></div>
          {activePipeline && (activePipeline.detections_current_frame ?? 0) > 0 && (activePipeline.active_tracks ?? 0) === 0 && <div className="source-status bad"><strong>⚠ YOLO thấy xe nhưng ByteTrack chưa cấp ID</strong><span>V0.5.25 vẫn vẽ box DET màu vàng cho detection chưa có ID. Bộ đếm chỉ tăng khi track ổn định; profile ByteTrack high-recall sẽ cố bám các xe nhỏ/nhanh ở những frame tiếp theo.</span></div>}
          {activePipeline && (activePipeline.suppressed_class_duplicates_current_frame ?? 0) > 0 && <div className="source-status ok"><strong>✓ Đã gộp detection bus/truck trùng nhau</strong><span>Single-Object Guard loại detection BUS/TRUCK chồng lên cùng một xe trước khi đưa vào bộ đếm, tránh một xe tải bị cộng đồng thời vào Xe buýt và Xe tải.</span></div>}
          {activePipeline && (activePipeline.human_guard_rejections ?? 0) > 0 && <div className="source-status ok"><strong>✓ Human Guard đã loại người bị nhầm thành xe hai bánh</strong><span>{activePipeline.human_guard_rejections} track người đã được xác nhận chặn khỏi bộ đếm. Transactional Rider-aware Guard 2.1 không khóa rider thật chỉ vì một frame PERSON mạnh; xe máy/xe đạp có evidence thân xe phía dưới sẽ được giữ lại.</span></div>}
          {activePipeline && (activePipeline.rider_guard_rescues ?? 0) > 0 && <div className="source-status ok"><strong>✓ Rider Guard đang giữ xe hai bánh thật</strong><span>{activePipeline.rider_guard_rescues} track rider đã được giữ/cứu nhờ evidence thân xe phía dưới hoặc motion phù hợp, nên người đang ngồi/lái xe không bị loại như pedestrian.</span></div>}
          {activePipeline && (activePipeline.active_tracks ?? 0) > 0 && (activePipeline.road_tracks_current_frame ?? 0) === 0 && <div className="source-status bad"><strong>⚠ Có track nhưng Road Zone chưa phủ luồng xe</strong><span>Dừng AI rồi kéo vùng xanh bao phần lòng đường mà xe thực sự chạy; chỉ vùng xanh mới được phép đếm.</span></div>}
          {selected && !activePipeline && <div className={`source-status ${sourceStatus?.valid ? 'ok' : 'bad'}`}><strong>{sourceStatus?.valid ? '✓ Nguồn sẵn sàng' : '⚠ Nguồn chưa sẵn sàng'}</strong><span>{sourceStatus?.message || 'Đang kiểm tra nguồn...'}</span>{sourceStatus?.suggested_source_url && <><small>Gợi ý: {sourceStatus.suggested_source_url}</small><button type="button" className="inline-action" onClick={applySuggestedSource}>Dùng nguồn gợi ý</button></>}</div>}
          {latestPipeline && !activePipeline && <div className="pipeline-result">Lần chạy gần nhất: <strong>{latestPipeline.status}</strong> · {latestPipeline.processed_frames} frame · worker {latestPipeline.total_count} crossing · DB mới {latestPipeline.persisted_events ?? latestPipeline.delivered_events ?? 0} event · dedup {latestPipeline.deduplicated_events ?? 0} · Human Guard {latestPipeline.human_guard_rejections ?? 0} · Rider giữ {latestPipeline.rider_guard_rescues ?? 0} · Guard xác nhận {latestPipeline.human_guard_deferred_commits ?? 0} · Guard timeout {latestPipeline.human_guard_pending_drops ?? 0}{latestPipeline.last_error ? ` · ${latestPipeline.last_error}` : ''}</div>}
        </article>
        <article className="panel"><div className="panel-head"><div><span className="panel-kicker">VEHICLE COUNT</span><h2>Theo loại phương tiện · phiên hiện tại</h2></div></div><div className="counting-summary"><div><span>Tổng lượt cắt vạch</span><strong>{sessionPipeline?.total_count ?? 0}</strong></div><div><span>IN</span><strong>{sessionPipeline?.in_count ?? 0}</strong></div><div><span>OUT</span><strong>{sessionPipeline?.out_count ?? 0}</strong></div></div><div className="crossing-quality"><span>Trực tiếp <strong>{sessionPipeline?.direct_crossings ?? 0}</strong></span><span>Nội suy <strong>{sessionPipeline?.interpolated_crossings ?? 0}</strong></span><span>Cứu qua gap <strong>{sessionPipeline?.rescued_crossings ?? 0}</strong></span><span>Fast-confirm <strong>{sessionPipeline?.fast_confirm_rescues ?? 0}</strong></span><span>Bracket-confirm <strong>{sessionPipeline?.bracket_confirm_rescues ?? 0}</strong></span><span>Rescue bị loại <strong>{sessionPipeline?.rescue_validation_rejections ?? 0}</strong></span><span>Human Guard <strong>{sessionPipeline?.human_guard_rejections ?? 0}</strong></span><span>Rider giữ <strong>{sessionPipeline?.rider_guard_rescues ?? 0}</strong></span><span>Guard chờ <strong>{sessionPipeline?.human_guard_pending_crossings ?? 0}</strong></span><span>Guard xác nhận <strong>{sessionPipeline?.human_guard_deferred_commits ?? 0}</strong></span><span>Guard timeout <strong>{sessionPipeline?.human_guard_pending_drops ?? 0}</strong></span></div><div className="vehicle-list">{vehicleRows.map(row => <div className="vehicle-row" key={row.label}><span>{row.label}</span><strong>{row.value}</strong></div>)}</div><p className="hint"><strong>Crossing Engine 7.2</strong> thêm bracket-confirm cho track cắt hữu hạn rõ nhưng mất ngay sau vạch, giữ fast-confirm/adaptive cooldown/rescue validation, và Transactional Human Guard 2.1 chỉ phát event xe hai bánh sau khi trạng thái rider/pedestrian đã được xác nhận. Tổng xe vẫn là <strong>IN + OUT</strong>; telemetry không còn gọi mọi crossing có gap &gt; 1 frame là “cứu”. Chế độ Phát mượt dùng video native; AI vẫn detect/track/đếm ở nền.</p></article>
      </section>


      <GroundTruthBenchmark selectedCameraId={selectedId} sessions={sessions} />

      <section className="line-layout" id="cameras">
        <article className="panel line-panel"><div className="panel-head"><div><span className="panel-kicker">ROAD ZONE + COUNTING LINE</span><h2>Khoanh lòng đường và đặt vạch đếm</h2></div><span className={`lock-state ${activePipeline ? 'locked' : ''}`}>{activePipeline ? 'Đang khóa khi AI chạy' : 'Có thể chỉnh'}</span></div>
          <CountingLineEditor previewUrl={previewUrl} line={lineForm} onChange={setLineForm} disabled={!!activePipeline} />
          <div className="preset-row"><button disabled={busy || !!activePipeline} onClick={()=>applyPreset('road-horizontal')}>Gợi ý cho clip hiện tại</button><button disabled={busy || !!activePipeline} onClick={()=>applyPreset('horizontal')}>Đường ngang</button><button disabled={busy || !!activePipeline} onClick={()=>applyPreset('vertical')}>Đường dọc</button></div>
          <div className="road-zone-toolbar"><span>Vùng lòng đường:</span><button className="secondary" disabled={busy || !!activePipeline} onClick={()=>applyRoadZonePreset('roadway')}>Trapezoid đường</button><button className="secondary" disabled={busy || !!activePipeline} onClick={()=>applyRoadZonePreset('narrow')}>Hẹp hơn</button><button className="secondary" disabled={busy || !!activePipeline} onClick={()=>applyRoadZonePreset('full')}>Toàn khung</button></div>
          <div className="auto-road-toolbar"><button type="button" disabled={!sessionPipeline || busy || !sessionPipeline?.calibration_ready} onClick={requestRoadProposal}>{!sessionPipeline ? 'Chạy AI để học luồng xe' : sessionPipeline?.calibration_ready ? `✨ AI đề xuất theo luồng xe · ${sessionPipeline.calibration_moving_tracks ?? 0} track` : `Đang học luồng xe · ${sessionPipeline?.calibration_moving_tracks ?? 0} track / ${sessionPipeline?.calibration_samples ?? 0} điểm`}</button>{roadProposal && <button type="button" className="success" disabled={busy || !countingGeometryState.valid} onClick={applyRoadProposal}>{activePipeline ? '✓ Dừng AI + áp dụng đề xuất' : '✓ Áp dụng đề xuất'}</button>}</div>
          {roadProposal && <div className="proposal-status"><strong>✨ Auto Road-Zone · chất lượng {Math.round((roadProposal.quality || 0)*100)}%</strong><span>{roadProposal.moving_track_count} track chuyển động · {roadProposal.sample_count} điểm · xe đứng/đỗ đã bị bỏ khỏi dữ liệu học vùng đường.</span></div>}
          <div className="nudge-grid"><button disabled={!!activePipeline} onClick={()=>moveLine(0,-0.02)}>↑ Lên</button><button disabled={!!activePipeline} onClick={()=>moveLine(0,0.02)}>↓ Xuống</button><button disabled={!!activePipeline} onClick={()=>moveLine(-0.02,0)}>← Trái</button><button disabled={!!activePipeline} onClick={()=>moveLine(0.02,0)}>→ Phải</button><button disabled={!!activePipeline} onClick={()=>resizeLine(1.12)}>Dài hơn</button><button disabled={!!activePipeline} onClick={()=>resizeLine(0.88)}>Ngắn hơn</button></div>
          <div className="line-grid">{lineField('line_x1','X1')}{lineField('line_y1','Y1')}{lineField('line_x2','X2')}{lineField('line_y2','Y2')}{lineField('confidence_threshold','Confidence')}</div>
          <div className={`geometry-status ${countingGeometryState.valid ? 'ok' : 'bad'}`}><strong>{countingGeometryState.valid ? '✓ ROAD GUARD hợp lệ' : '⚠ Chưa thể lưu'}</strong><span>{countingGeometryState.message}</span></div>
          <button disabled={!selected || busy || !!activePipeline || !countingGeometryState.valid} onClick={saveCountingLine}>Lưu vạch + vùng lòng đường</button>
          <p className="hint"><strong>Vùng xanh = lòng đường được phép đếm.</strong> V0.5.25 giữ <strong>Hybrid Recall</strong> + <strong>Auto Road-Zone</strong>, <strong>Single-Object Guard</strong> và <strong>Transactional Human Guard 2.1</strong> để BUS/TRUCK chồng box chỉ được tính là một phương tiện: khi AI chạy đủ track chuyển động, bấm “AI đề xuất theo luồng xe” để hệ thống tự khoanh phần đường xe thật sự đi qua và đặt vạch gần vuông góc luồng xe. Hybrid Recall: YOLO26 pretrained quét toàn khung để tạo track ổn định, còn best.pt tùy biến kiểm tra lại class tại crossing. Detection chưa có ID vẫn hiện box vàng; chỉ track cắt vạch vàng hợp lệ trong vùng xanh mới được cộng IN/OUT.</p>
        </article>

        <article className="panel"><div className="panel-head"><div><span className="panel-kicker">CAMERA SOURCE</span><h2>{editingId ? `Sửa Camera #${editingId}` : 'Tạo camera mới'}</h2></div><button className="secondary" type="button" disabled={busy || !!activePipeline} onClick={beginNewCamera}>Camera mới</button></div><form className="camera-form" onSubmit={saveCamera}>
          <input value={form.name} onChange={e => setForm({...form, name:e.target.value})} placeholder="Tên camera" required /><input value={form.code} onChange={e => setForm({...form, code:e.target.value})} placeholder="Mã camera" required />
          <select value={form.source_type} onChange={e => setForm({...form, source_type:e.target.value})}><option value="video">Video local</option><option value="rtsp">RTSP</option><option value="webcam">Webcam Linux</option></select>
          {form.source_type === 'video' ? <select className="wide" value={form.source_url} onChange={e=>setForm({...form, source_url:e.target.value})}>{!videoPathSet.has(form.source_url) && form.source_url && <option value={form.source_url}>⚠ {form.source_url} (không tồn tại)</option>}<option value="">-- Chọn video trong thư mục videos --</option>{videoSources.map(v => <option value={v.source_url} key={v.source_url}>{v.name}</option>)}</select> : <input className="wide" value={form.source_url} onChange={e => setForm({...form, source_url:e.target.value})} placeholder={form.source_type === 'rtsp' ? 'rtsp://user:pass@ip/stream' : '0'} required />}
          <input className="wide" value={form.location || ''} onChange={e => setForm({...form, location:e.target.value})} placeholder="Vị trí / mô tả ngắn" />
          <div className="camera-actions"><button disabled={busy || !!activePipeline}>{editingId ? 'Cập nhật camera' : 'Tạo camera'}</button>{editingId && <span className={form.source_type === 'video' && !videoPathSet.has(form.source_url) ? 'bad-text' : 'ok-text'}>{form.source_type === 'video' ? (videoPathSet.has(form.source_url) ? 'File video đang tồn tại.' : 'Hãy chọn lại file video rồi cập nhật camera.') : 'Nguồn sẽ được kiểm tra trước khi chạy AI.'}</span>}</div>
        </form><p className="hint">Khi AI đang chạy, hệ thống khóa nguồn và vạch đếm để bảo đảm một phiên dùng đúng một cấu hình. Bấm <strong>Dừng AI</strong> trước khi chỉnh.</p></article>
      </section>

      <section className="training-layout" id="training">
        <article className="panel training-panel"><div className="panel-head"><div><span className="panel-kicker">DATASET STUDIO · CLEAN RETRAIN</span><h2>Dataset giao thông Việt Nam</h2></div><span className="lock-state">V0.5.25</span></div>
          <p className="hint"><strong>Train lại từ đầu</strong> nên tạo dataset mới sạch từ video gốc. V0.5.25 mặc định lấy mỗi 15 frame, tối đa 600 ảnh và tự loại frame gần trùng; vì vậy bạn không còn phải mặc định xử lý 1.200 ảnh gần giống nhau.</p>
          <div className="dataset-form">
            <label className="dataset-name-field">Tên dataset<input value={datasetForm.name} onChange={e=>setDatasetForm({...datasetForm,name:e.target.value})} placeholder="traffic-vietnam-clean-01" /></label>
            <label>Mỗi N frame<input type="number" min="1" value={datasetForm.every_n_frames} onChange={e=>setDatasetForm({...datasetForm,every_n_frames:e.target.value})}/></label>
            <label>Tối đa ảnh<input type="number" min="10" value={datasetForm.max_images} onChange={e=>setDatasetForm({...datasetForm,max_images:e.target.value})}/></label>
            <label className="dataset-threshold-field">Ngưỡng thay đổi<input type="number" min="0" max="1" step="0.001" value={datasetForm.min_change_ratio} onChange={e=>setDatasetForm({...datasetForm,min_change_ratio:e.target.value})}/><small>0.008 = cần ít nhất khoảng 0,8% điểm ảnh đại diện thay đổi để giữ frame.</small></label>
            <label className="check"><input type="checkbox" checked={!!datasetForm.smart_dedupe} onChange={e=>setDatasetForm({...datasetForm,smart_dedupe:e.target.checked})}/> Loại frame gần trùng</label>
            <button className="dataset-create-button" disabled={!selected || busy || selected?.source_type !== 'video'} onClick={createDataset}>1. Tạo dataset · Trích frame thông minh</button>
          </div>
          <p className="hint">Gợi ý video ~30 FPS: <strong>N=15</strong> ≈ 2 frame ứng viên/giây trước khi lọc; <strong>N=30</strong> ≈ 1 frame/giây. Với một góc camera cố định, thường nên bắt đầu khoảng <strong>400–800 ảnh đa dạng</strong>, không cần cố đủ 1.200 ảnh.</p>
          <div className="dataset-select"><label>Dataset</label><select value={selectedDatasetId || ''} onChange={e=>setSelectedDatasetId(Number(e.target.value))}><option value="">-- Chọn dataset --</option>{datasets.map(d=><option key={d.id} value={d.id}>#{d.id} · {d.name} · {d.status}</option>)}</select></div>
          {selectedDataset && <div className="dataset-stats"><div><span>Ảnh</span><strong>{selectedDataset.image_count}</strong></div><div><span>Ảnh có nhãn</span><strong>{selectedDataset.labeled_images}</strong></div><div><span>Boxes</span><strong>{selectedDataset.box_count}</strong></div><div><span>Đã rà soát</span><strong>{selectedDataset.reviewed_images ?? 0}</strong></div><div><span>Ảnh khó</span><strong>{selectedDataset.difficult_images ?? 0}</strong></div><div><span>Train/Val/Test</span><strong>{selectedDataset.train_count}/{selectedDataset.val_count}/{selectedDataset.test_count}</strong></div></div>}
          <div className="training-actions"><button disabled={!selectedDataset || busy} onClick={()=>datasetAction('autolabel')}>2. Auto-label YOLO26</button><button disabled={!selectedDataset || busy || !['pseudo_labeled','labeled','ready'].includes(selectedDataset?.status)} onClick={()=>datasetAction('prepare')}>4. Chia train/val/test</button><button className="secondary" disabled={!selectedDataset || busy} onClick={resetDatasetLabels}>Làm lại nhãn · giữ ảnh</button><button className="danger" disabled={!selectedDataset || busy} onClick={deleteDataset}>Xóa dataset + ảnh cũ</button></div>
          <p className="hint"><strong>Không sửa tay tất cả ảnh.</strong> Sau Auto-label, xuống Annotation Studio và để bộ lọc “🔥 Ưu tiên cần kiểm tra”: hệ thống đưa xe máy/xe đạp, confidence thấp, ảnh đông xe và ảnh không detection lên trước. Nút “Duyệt nhanh ảnh tin cậy” chỉ áp dụng cho ảnh rõ, không chứa motorcycle/bicycle và không phải ảnh rỗng.</p>
          <p className="hint">Nếu ảnh đã tốt nhưng nhãn sai, dùng <strong>Làm lại nhãn · giữ ảnh</strong>. Nếu muốn bắt đầu hoàn toàn sạch, dùng <strong>Xóa dataset + ảnh cũ</strong> rồi trích dataset mới. Xóa dataset không xóa file <code>best.pt</code> đã export trong <code>models/</code>.</p>
        </article>
        <article className="panel training-panel"><div className="panel-head"><div><span className="panel-kicker">FINE-TUNE</span><h2>Huấn luyện YOLO26 tùy biến</h2></div><span className="lock-state">Fresh run</span></div>
          <div className="train-form"><label>Base model<select value={trainingForm.base_model} onChange={e=>setTrainingForm({...trainingForm,base_model:e.target.value})}><option value="yolo26s.pt">YOLO26s</option><option value="yolo26m.pt">YOLO26m</option></select></label><label>Epochs<input type="number" min="1" value={trainingForm.epochs} onChange={e=>setTrainingForm({...trainingForm,epochs:e.target.value})}/></label><label>Image size<input type="number" min="320" step="32" value={trainingForm.imgsz} onChange={e=>setTrainingForm({...trainingForm,imgsz:e.target.value})}/></label><label>Batch<input type="number" min="1" value={trainingForm.batch} onChange={e=>setTrainingForm({...trainingForm,batch:e.target.value})}/></label></div>
          <p className="hint"><strong>Train mới từ đầu trong Traffic AI</strong> = tạo một Training Run mới từ base model pretrained bạn chọn (khuyến nghị YOLO26s), <strong>không tiếp tục học từ best.pt cũ</strong>. Đây là fine-tune mới, không phải random-weight training.</p><button disabled={!selectedDataset || selectedDataset?.status !== 'ready' || busy || trainingRuns.some(r=>r.status==='running')} onClick={startTraining}>5. Bắt đầu fine-tune mới RTX 3060</button>
          <div className="event-list training-runs">{trainingRuns.length ? trainingRuns.map(run=><div className="event-row training-row" key={run.id}><span>Run #{run.id} · Dataset #{run.dataset_id} · {run.base_model}</span><strong>{String(run.status).toUpperCase()} · {Number(run.progress || 0).toFixed(1)}%</strong><small>Epoch {run.current_epoch}/{run.epochs} · P {run.precision?.toFixed?.(3) ?? '-'} · R {run.recall?.toFixed?.(3) ?? '-'} · mAP50 {run.map50?.toFixed?.(3) ?? '-'} · mAP50-95 {run.map50_95?.toFixed?.(3) ?? '-'}</small>{run.status==='completed' && (run.is_active_model ? <span className="active-model-badge">✓ ĐANG DÙNG best.pt</span> : <button className="inline-action" disabled={busy} onClick={()=>activateTraining(run)}>6. Kích hoạt best.pt</button>)}{run.last_error && <small className="bad-text">{run.last_error}</small>}</div>) : <div className="empty">Chưa có training run.</div>}</div>
          <p className="hint">Sau khi kích hoạt <code>best.pt</code>, V0.5.25 dùng <strong>Hybrid Recall</strong>: YOLO26 pretrained đảm nhiệm detect/track để không bỏ xe vì recall thấp, còn <code>best.pt</code> tùy biến refine class tại crossing. Strict Gate/Road Guard vẫn quyết định đếm; Annotation Studio tiếp tục dùng để nâng chất lượng ground truth cho các lần train sau.</p>
        </article>
      </section>

      <AnnotationEditor dataset={selectedDataset} onChanged={load} />

      <section className="content-grid lower-grid" id="events">
        <article className="panel"><div className="panel-head"><div><span className="panel-kicker">RECENT EVENTS</span><h2>Lịch sử PostgreSQL · mọi phiên</h2></div></div><div className="event-list">{events.length ? events.map(e => <div className="event-row" key={e.id}><span>#{e.tracking_id ?? '-'} · {vehicleLabels[e.vehicle_type] || e.vehicle_type}</span><strong>{String(e.direction).toUpperCase()}</strong><small>{new Date(e.detected_at).toLocaleString()}</small></div>) : <div className="empty">Chưa có phương tiện cắt vạch đếm.</div>}</div></article>
        <article className="panel"><div className="panel-head"><div><span className="panel-kicker">COUNTING SESSIONS</span><h2>Lịch sử phiên chạy</h2></div></div><div className="event-list">{sessions.length ? sessions.map(s => <div className="event-row" key={s.id}><span>Session #{s.id} · Camera #{s.camera_id}</span><strong>{String(s.status).toUpperCase()}</strong><small>{s.total_vehicles} event DB · worker {s.worker_total_vehicles ?? s.total_vehicles} · dedup {s.dedup_suppressed_events ?? 0} · human {s.human_guard_rejections ?? 0} · FPS {s.average_fps ?? '-'} · {new Date(s.started_at).toLocaleString()}</small></div>) : <div className="empty">Chưa có phiên chạy.</div>}</div></article>
      </section>
    </main>
  </div>
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>)
