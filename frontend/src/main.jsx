import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const APP_VERSION = '0.3.3'
const vehicleLabels = {
  motorcycle: 'Xe máy', bicycle: 'Xe đạp', car: 'Ô tô', bus: 'Xe buýt', truck: 'Xe tải', other: 'Khác'
}
const clamp01 = value => Math.min(1, Math.max(0, Number(value)))

const defaultCameraForm = () => ({
  name: 'Camera demo', code: 'CAM-001', source_type: 'video',
  source_url: '/data/videos/demo.mp4', location: 'Khu vực demo',
  confidence_threshold: 0.20, line_x1: 0.32, line_y1: 0.59, line_x2: 0.84, line_y2: 0.59
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

  return <div className={`line-editor ${disabled ? 'locked' : ''}`} ref={boxRef} onPointerMove={moveDrag} onPointerUp={endDrag} onPointerCancel={endDrag}>
    {previewUrl ? <img src={previewUrl} alt="Khung hình dùng để đặt vạch đếm" /> : <div className="camera-placeholder"><strong>Chưa có ảnh xem trước</strong><span>Kiểm tra nguồn camera/video trước khi đặt vạch.</span></div>}
    <svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-label="Vạch đếm tương tác">
      <line className="gate-hit" x1={x1} y1={y1} x2={x2} y2={y2} onPointerDown={e=>beginDrag('line',e)} />
      <line className="gate-line" x1={x1} y1={y1} x2={x2} y2={y2} />
      <circle className="gate-handle" cx={x1} cy={y1} r="0.014" onPointerDown={e=>beginDrag('p1',e)} />
      <circle className="gate-handle" cx={x2} cy={y2} r="0.014" onPointerDown={e=>beginDrag('p2',e)} />
      <text className="gate-label in" fontSize="0.035" x={clamp01(mx + nx*0.055)} y={clamp01(my + ny*0.055)}>IN</text>
      <text className="gate-label out" fontSize="0.035" x={clamp01(mx - nx*0.055)} y={clamp01(my - ny*0.055)}>OUT</text>
    </svg>
    <div className="line-editor-help">{disabled ? '🔒 AI đang chạy — dừng AI để chỉnh vạch.' : 'Kéo đường vàng để di chuyển; kéo 2 đầu tròn để xoay hoặc thay đổi chiều dài.'}</div>
  </div>
}

function App() {
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
  const [lineForm, setLineForm] = useState({confidence_threshold:0.20,line_x1:0.32,line_y1:0.59,line_x2:0.84,line_y2:0.59})

  const load = async () => {
    try {
      const [summaryRes, healthRes, systemStatusRes, camerasRes, eventsRes, pipelinesRes, sessionsRes, videosRes] = await Promise.all([
        fetch('/api/dashboard/summary'), fetch('/api/health'), fetch('/api/system/status'), fetch('/api/cameras'),
        fetch('/api/events?limit=20'), fetch('/api/pipelines'), fetch('/api/sessions?limit=10'), fetch('/api/sources/videos')
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
      if (cameraData.length) setSelectedId(prev => prev || cameraData[0].id)
    } catch (err) {
      setError(err.message || 'Không thể tải dữ liệu')
    }
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 1500)
    return () => clearInterval(id)
  }, [])

  const selected = cameras.find(c => c.id === Number(selectedId))
  const activePipeline = pipelines.find(p => p.camera_id === Number(selectedId) && ['starting', 'running'].includes(p.status))
  const latestPipeline = pipelines.find(p => p.camera_id === Number(selectedId))
  const sessionPipeline = activePipeline || latestPipeline
  const sessionCounts = sessionPipeline?.counts_by_type || {}
  const vehicleRows = useMemo(() => Object.entries(vehicleLabels).map(([key, label]) => ({ label, value: sessionCounts?.[key] || 0 })), [sessionCounts])
  const sessionTotal = sessionPipeline?.total_count ?? 0
  const videoPathSet = useMemo(() => new Set(videoSources.map(v => v.source_url)), [videoSources])
  const selectedVideoMissing = selected?.source_type === 'video' && sourceStatus?.valid === false
  const sourceAutoRepairAvailable = selectedVideoMissing && !!sourceStatus?.suggested_source_url
  const previewUrl = selected ? `/api/cameras/${selected.id}/preview.jpg?rev=${encodeURIComponent(selected.updated_at || '')}` : ''

  useEffect(() => {
    if (!selected) return
    setEditingId(selected.id)
    setForm({
      name: selected.name, code: selected.code, source_type: selected.source_type, source_url: selected.source_url,
      location: selected.location || '', confidence_threshold: selected.confidence_threshold ?? 0.20,
      line_x1: selected.line_x1 ?? 0.32, line_y1: selected.line_y1 ?? 0.59,
      line_x2: selected.line_x2 ?? 0.84, line_y2: selected.line_y2 ?? 0.59
    })
    setLineForm({
      confidence_threshold: selected.confidence_threshold ?? 0.20,
      line_x1: selected.line_x1 ?? 0.32, line_y1: selected.line_y1 ?? 0.59,
      line_x2: selected.line_x2 ?? 0.84, line_y2: selected.line_y2 ?? 0.59
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
      const body = await response.json()
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
      const body = await response.json()
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
    if (preset === 'horizontal') setLineForm({...lineForm, line_x1:0.18,line_y1:0.55,line_x2:0.88,line_y2:0.55})
    if (preset === 'vertical') setLineForm({...lineForm, line_x1:0.52,line_y1:0.12,line_x2:0.52,line_y2:0.90})
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
    setBusy(true); setError(''); setNotice('')
    try {
      const body = Object.fromEntries(Object.entries(lineForm).map(([k,v]) => [k, Number(v)]))
      const response = await fetch(`/api/cameras/${selected.id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail || 'Không cập nhật được counting line')
      setNotice('Đã lưu vạch đếm. Vạch chỉ đếm khi tâm đáy phương tiện đi từ một phía sang phía kia.')
      await load()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const applySuggestedSource = () => {
    if (!selected || !sourceStatus?.suggested_source_url) return
    setEditingId(selected.id); setForm(prev => ({...prev, source_type:'video', source_url:sourceStatus.suggested_source_url}))
    setNotice('Đã chọn nguồn gợi ý. Bấm Cập nhật camera để lưu vào PostgreSQL.')
  }

  const lineField = (name, label) => <label className="line-field"><span>{label}</span><input disabled={!!activePipeline} type="number" min="0" max="1" step="0.01" value={Number(lineForm[name]).toFixed(2)} onChange={e=>setLineForm({...lineForm,[name]:Number(e.target.value)})}/></label>

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><img className="brand-logo" src={`/logo.svg?v=${APP_VERSION}`} alt="Traffic AI" /><div><strong>Traffic AI</strong><span>YOLO26 + ByteTrack</span></div></div>
      <nav><a className="active" href="#overview">Tổng quan</a><a href="#live">Giám sát</a><a href="#cameras">Camera</a><a href="#events">Sự kiện</a></nav>
      <div className="sidebar-footer">V{APP_VERSION} · Smart Gate 3.0</div>
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
          <div className="panel-head"><div><span className="panel-kicker">LIVE AI</span><h2>Camera Preview</h2></div><button className={activePipeline ? 'danger' : ''} disabled={!selected || busy || (!activePipeline && selectedVideoMissing && !sourceAutoRepairAvailable)} onClick={togglePipeline}>{activePipeline ? 'Dừng AI' : 'Chạy AI'}</button></div>
          <div className="camera-stage">{activePipeline ? <img src={`/ai/streams/${selected.id}.mjpg?session=${activePipeline.session_id}`} alt="Live AI stream" /> : <img src={previewUrl} alt="Preview camera" onLoad={e=>{e.currentTarget.style.visibility='visible'}} onError={e=>{e.currentTarget.style.visibility='hidden'}} />}</div>
          <div className="camera-select"><label>Camera</label><select value={selectedId || ''} onChange={e => setSelectedId(Number(e.target.value))}><option value="">-- Chọn camera --</option>{cameras.map(c => <option key={c.id} value={c.id}>{c.code} · {c.name}</option>)}</select><span>{activePipeline ? `FPS ${activePipeline.fps} · ${activePipeline.inference_ms ?? 0} ms · Tổng ${activePipeline.total_count} · IN ${activePipeline.in_count ?? 0} · OUT ${activePipeline.out_count ?? 0}` : selected?.source_url || 'Chưa có camera'}</span></div>
          {selected && !activePipeline && <div className={`source-status ${sourceStatus?.valid ? 'ok' : 'bad'}`}><strong>{sourceStatus?.valid ? '✓ Nguồn sẵn sàng' : '⚠ Nguồn chưa sẵn sàng'}</strong><span>{sourceStatus?.message || 'Đang kiểm tra nguồn...'}</span>{sourceStatus?.suggested_source_url && <><small>Gợi ý: {sourceStatus.suggested_source_url}</small><button type="button" className="inline-action" onClick={applySuggestedSource}>Dùng nguồn gợi ý</button></>}</div>}
          {latestPipeline && !activePipeline && <div className="pipeline-result">Lần chạy gần nhất: <strong>{latestPipeline.status}</strong> · {latestPipeline.processed_frames} frame · {latestPipeline.total_count} lượt cắt vạch · đã ghi {latestPipeline.delivered_events ?? 0} sự kiện{latestPipeline.last_error ? ` · ${latestPipeline.last_error}` : ''}</div>}
        </article>
        <article className="panel"><div className="panel-head"><div><span className="panel-kicker">VEHICLE COUNT</span><h2>Theo loại phương tiện · phiên hiện tại</h2></div></div><div className="vehicle-list">{vehicleRows.map(row => <div className="vehicle-row" key={row.label}><span>{row.label}</span><strong>{row.value}</strong></div>)}</div><p className="hint">Mỗi lần bấm Chạy AI là một phiên mới và bộ đếm này bắt đầu từ 0. Lịch sử cũ vẫn được giữ trong PostgreSQL. Track bị đổi ID ngắn hạn được nối lại; xe buýt/xe tải hoặc nhãn chưa chắc chắn được kiểm tra lại tại thời điểm cắt vạch.</p></article>
      </section>

      <section className="line-layout" id="cameras">
        <article className="panel line-panel"><div className="panel-head"><div><span className="panel-kicker">COUNTING LINE</span><h2>Đặt vạch đếm trực tiếp trên hình</h2></div><span className={`lock-state ${activePipeline ? 'locked' : ''}`}>{activePipeline ? 'Đang khóa khi AI chạy' : 'Có thể chỉnh'}</span></div>
          <p className="hint"><strong>Nguyên tắc:</strong> vạch vàng phải cắt ngang hướng xe chạy. Với video clip bạn gửi, đường xe chạy theo chiều trên ↔ dưới màn hình, nên dùng vạch gần ngang lòng đường. Chỉ xe thực sự đi từ một phía sang phía kia mới được đếm.</p>
          <CountingLineEditor previewUrl={previewUrl} line={lineForm} onChange={setLineForm} disabled={!!activePipeline} />
          <div className="preset-row"><button disabled={busy || !!activePipeline} onClick={()=>applyPreset('road-horizontal')}>Gợi ý cho clip hiện tại</button><button disabled={busy || !!activePipeline} onClick={()=>applyPreset('horizontal')}>Đường ngang</button><button disabled={busy || !!activePipeline} onClick={()=>applyPreset('vertical')}>Đường dọc</button></div>
          <div className="nudge-grid"><button disabled={!!activePipeline} onClick={()=>moveLine(0,-0.02)}>↑ Lên</button><button disabled={!!activePipeline} onClick={()=>moveLine(0,0.02)}>↓ Xuống</button><button disabled={!!activePipeline} onClick={()=>moveLine(-0.02,0)}>← Trái</button><button disabled={!!activePipeline} onClick={()=>moveLine(0.02,0)}>→ Phải</button><button disabled={!!activePipeline} onClick={()=>resizeLine(1.12)}>Dài hơn</button><button disabled={!!activePipeline} onClick={()=>resizeLine(0.88)}>Ngắn hơn</button></div>
          <div className="line-grid">{lineField('line_x1','X1')}{lineField('line_y1','Y1')}{lineField('line_x2','X2')}{lineField('line_y2','Y2')}{lineField('confidence_threshold','Confidence')}</div>
          <button disabled={!selected || busy || !!activePipeline} onClick={saveCountingLine}>Lưu vị trí vạch</button>
          <p className="hint">Confidence mặc định 0,20 để giảm bỏ sót xe nhỏ/xa. Không nên hạ quá thấp nếu cảnh có nhiều xe đỗ hai bên đường.</p>
        </article>

        <article className="panel"><div className="panel-head"><div><span className="panel-kicker">CAMERA SOURCE</span><h2>{editingId ? `Sửa Camera #${editingId}` : 'Tạo camera mới'}</h2></div><button className="secondary" type="button" disabled={busy || !!activePipeline} onClick={beginNewCamera}>Camera mới</button></div><form className="camera-form" onSubmit={saveCamera}>
          <input value={form.name} onChange={e => setForm({...form, name:e.target.value})} placeholder="Tên camera" required /><input value={form.code} onChange={e => setForm({...form, code:e.target.value})} placeholder="Mã camera" required />
          <select value={form.source_type} onChange={e => setForm({...form, source_type:e.target.value})}><option value="video">Video local</option><option value="rtsp">RTSP</option><option value="webcam">Webcam Linux</option></select>
          {form.source_type === 'video' ? <select className="wide" value={form.source_url} onChange={e=>setForm({...form, source_url:e.target.value})}>{!videoPathSet.has(form.source_url) && form.source_url && <option value={form.source_url}>⚠ {form.source_url} (không tồn tại)</option>}<option value="">-- Chọn video trong thư mục videos --</option>{videoSources.map(v => <option value={v.source_url} key={v.source_url}>{v.name}</option>)}</select> : <input className="wide" value={form.source_url} onChange={e => setForm({...form, source_url:e.target.value})} placeholder={form.source_type === 'rtsp' ? 'rtsp://user:pass@ip/stream' : '0'} required />}
          <input className="wide" value={form.location || ''} onChange={e => setForm({...form, location:e.target.value})} placeholder="Vị trí / mô tả ngắn" />
          <div className="camera-actions"><button disabled={busy || !!activePipeline}>{editingId ? 'Cập nhật camera' : 'Tạo camera'}</button>{editingId && <span className={form.source_type === 'video' && !videoPathSet.has(form.source_url) ? 'bad-text' : 'ok-text'}>{form.source_type === 'video' ? (videoPathSet.has(form.source_url) ? 'File video đang tồn tại.' : 'Hãy chọn lại file video rồi cập nhật camera.') : 'Nguồn sẽ được kiểm tra trước khi chạy AI.'}</span>}</div>
        </form><p className="hint">Khi AI đang chạy, hệ thống khóa nguồn và vạch đếm để bảo đảm một phiên dùng đúng một cấu hình. Bấm <strong>Dừng AI</strong> trước khi chỉnh.</p></article>
      </section>

      <section className="content-grid lower-grid" id="events">
        <article className="panel"><div className="panel-head"><div><span className="panel-kicker">RECENT EVENTS</span><h2>Lịch sử PostgreSQL · mọi phiên</h2></div></div><div className="event-list">{events.length ? events.map(e => <div className="event-row" key={e.id}><span>#{e.tracking_id ?? '-'} · {vehicleLabels[e.vehicle_type] || e.vehicle_type}</span><strong>{String(e.direction).toUpperCase()}</strong><small>{new Date(e.detected_at).toLocaleString()}</small></div>) : <div className="empty">Chưa có phương tiện cắt vạch đếm.</div>}</div></article>
        <article className="panel"><div className="panel-head"><div><span className="panel-kicker">COUNTING SESSIONS</span><h2>Lịch sử phiên chạy</h2></div></div><div className="event-list">{sessions.length ? sessions.map(s => <div className="event-row" key={s.id}><span>Session #{s.id} · Camera #{s.camera_id}</span><strong>{String(s.status).toUpperCase()}</strong><small>{s.total_vehicles} lượt cắt vạch · FPS {s.average_fps ?? '-'} · {new Date(s.started_at).toLocaleString()}</small></div>) : <div className="empty">Chưa có phiên chạy.</div>}</div></article>
      </section>
    </main>
  </div>
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>)
