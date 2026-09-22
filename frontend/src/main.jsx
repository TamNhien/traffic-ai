import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const APP_VERSION = '0.2.9'
const vehicleLabels = {
  motorcycle: 'Xe máy', bicycle: 'Xe đạp', car: 'Ô tô', bus: 'Xe buýt', truck: 'Xe tải', other: 'Khác'
}

const defaultCameraForm = () => ({
  name: 'Camera demo', code: 'CAM-001', source_type: 'video',
  source_url: '/data/videos/demo.mp4', location: 'Khu vực demo',
  confidence_threshold: 0.35, line_x1: 0.1, line_y1: 0.5, line_x2: 0.9, line_y2: 0.5
})

function StatCard({ title, value, note }) {
  return <article className="stat-card"><span>{title}</span><strong>{value}</strong><small>{note}</small></article>
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
  const [lineForm, setLineForm] = useState({confidence_threshold:0.35,line_x1:0.1,line_y1:0.5,line_x2:0.9,line_y2:0.5})

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
      if (!selectedId && cameraData.length) setSelectedId(cameraData[0].id)
    } catch (err) {
      setError(err.message || 'Không thể tải dữ liệu')
    }
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 2000)
    return () => clearInterval(id)
  }, [])

  const selected = cameras.find(c => c.id === Number(selectedId))
  const activePipeline = pipelines.find(p => p.camera_id === Number(selectedId) && ['starting', 'running'].includes(p.status))
  const latestPipeline = pipelines.find(p => p.camera_id === Number(selectedId))
  const vehicleRows = useMemo(() => Object.entries(vehicleLabels).map(([key, label]) => ({ label, value: summary?.by_vehicle_type?.[key] || 0 })), [summary])
  const videoPathSet = useMemo(() => new Set(videoSources.map(v => v.source_url)), [videoSources])
  const selectedVideoMissing = selected?.source_type === 'video' && sourceStatus?.valid === false
  const sourceAutoRepairAvailable = selectedVideoMissing && !!sourceStatus?.suggested_source_url

  useEffect(() => {
    if (!selected) return
    setEditingId(selected.id)
    setForm({
      name: selected.name,
      code: selected.code,
      source_type: selected.source_type,
      source_url: selected.source_url,
      location: selected.location || '',
      confidence_threshold: selected.confidence_threshold ?? 0.35,
      line_x1: selected.line_x1 ?? 0.1, line_y1: selected.line_y1 ?? 0.5,
      line_x2: selected.line_x2 ?? 0.9, line_y2: selected.line_y2 ?? 0.5
    })
    setLineForm({
      confidence_threshold: selected.confidence_threshold ?? 0.35,
      line_x1: selected.line_x1 ?? 0.1, line_y1: selected.line_y1 ?? 0.5,
      line_x2: selected.line_x2 ?? 0.9, line_y2: selected.line_y2 ?? 0.5
    })
  }, [selectedId, selected?.updated_at])

  useEffect(() => {
    let cancelled = false
    if (!selected) { setSourceStatus(null); return () => {} }
    fetch(`/api/cameras/${selected.id}/source-status`)
      .then(async r => {
        const data = await r.json()
        if (!r.ok) throw new Error(data.detail || 'Không kiểm tra được nguồn')
        if (!cancelled) setSourceStatus(data)
      })
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
      setSelectedId(body.id)
      setEditingId(body.id)
      setNotice(editingId ? `Đã cập nhật ${body.code}. Nguồn mới đã được lưu vào PostgreSQL.` : `Đã tạo ${body.code}.`)
      await load()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const beginNewCamera = () => {
    const nextNumber = Math.max(0, ...cameras.map(c => Number(String(c.code).match(/(\d+)$/)?.[1] || 0))) + 1
    setEditingId(null)
    setForm({...defaultCameraForm(), name:'Camera mới', code:`CAM-${String(nextNumber).padStart(3,'0')}`})
    setNotice('Đang tạo camera mới. Chọn nguồn video rồi bấm Tạo camera.')
    setError('')
  }

  const togglePipeline = async () => {
    if (!selected) return
    setBusy(true); setError(''); setNotice('')
    try {
      const action = activePipeline ? 'stop' : 'start'
      const response = await fetch(`/api/cameras/${selected.id}/${action}`, { method: 'POST' })
      const body = await response.json()
      if (!response.ok) throw new Error(body.detail || 'Không thể thay đổi pipeline')
      if (action === 'start' && body.source_repaired) {
        setNotice(`Đã tự sửa nguồn video cũ thành ${body.source_url}, lưu vào PostgreSQL và bắt đầu AI.`)
      } else {
        setNotice(action === 'start' ? 'AI đã xác thực nguồn và bắt đầu xử lý video.' : 'Đã dừng AI.')
      }
      await load()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const applyPreset = preset => {
    if (preset === 'horizontal') setLineForm({...lineForm, line_x1:0.08,line_y1:0.62,line_x2:0.92,line_y2:0.62})
    if (preset === 'vertical') setLineForm({...lineForm, line_x1:0.5,line_y1:0.08,line_x2:0.5,line_y2:0.92})
  }

  const saveCountingLine = async () => {
    if (!selected) return
    setBusy(true); setError(''); setNotice('')
    try {
      const body = Object.fromEntries(Object.entries(lineForm).map(([k,v]) => [k, Number(v)]))
      const response = await fetch(`/api/cameras/${selected.id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) })
      if (!response.ok) throw new Error((await response.json()).detail || 'Không cập nhật được counting line')
      setNotice('Đã lưu vùng đếm vào camera đã chọn.')
      await load()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const applySuggestedSource = () => {
    if (!selected || !sourceStatus?.suggested_source_url) return
    setEditingId(selected.id)
    setForm(prev => ({...prev, source_type:'video', source_url:sourceStatus.suggested_source_url}))
    setNotice('Đã chọn nguồn gợi ý. Bấm Cập nhật camera để lưu đường dẫn mới vào PostgreSQL.')
  }

  const lineField = (name, label) => <label className="line-field"><span>{label}</span><input type="number" min="0" max="1" step="0.01" value={lineForm[name]} onChange={e=>setLineForm({...lineForm,[name]:e.target.value})}/></label>

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><img className="brand-logo" src={`/logo.svg?v=${APP_VERSION}`} alt="Traffic AI" /><div><strong>Traffic AI</strong><span>YOLO26 + ByteTrack</span></div></div>
        <nav><a className="active" href="#overview">Tổng quan</a><a href="#live">Giám sát</a><a href="#cameras">Camera</a><a href="#events">Sự kiện</a></nav>
        <div className="sidebar-footer">V{APP_VERSION} · YOLO26n + ByteTrack</div>
      </aside>
      <main>
        <header className="topbar"><div><p className="eyebrow">ĐỒ ÁN TRÍ TUỆ NHÂN TẠO</p><h1>Phát hiện, theo dõi và đếm phương tiện</h1></div><div className={`health ${health?.status === 'ok' ? 'online' : ''}`}><span className="dot" />{health?.status === 'ok' ? 'Hệ thống hoạt động' : 'Đang kết nối'}</div></header>
        {error && <div className="error-banner">{error}</div>}
        {notice && <div className="notice-banner">{notice}</div>}
        <section className="stats-grid" id="overview">
          <StatCard title="Camera" value={summary?.total_cameras ?? '—'} note={`${summary?.active_cameras ?? 0} đang chạy`} />
          <StatCard title="Phương tiện" value={summary?.total_events ?? '—'} note="Đã lưu vào PostgreSQL" />
          <StatCard title="Phiên đếm" value={summary?.running_sessions ?? '—'} note="Đang hoạt động" />
          <StatCard title="GPU" value={systemStatus?.ai?.gpu?.available ? 'CUDA' : (systemStatus?.ai_service === 'ready' ? 'CPU' : '—')} note={systemStatus?.ai?.gpu?.name || systemStatus?.ai?.model || 'AI service'} />
        </section>

        <section className="content-grid" id="live">
          <article className="panel camera-panel">
            <div className="panel-head"><div><span className="panel-kicker">LIVE AI</span><h2>Camera Preview</h2></div><button className={activePipeline ? 'danger' : ''} disabled={!selected || busy || (!activePipeline && selectedVideoMissing && !sourceAutoRepairAvailable)} onClick={togglePipeline}>{activePipeline ? 'Dừng AI' : 'Chạy AI'}</button></div>
            <div className="camera-stage">
              {activePipeline ? <img src={`/ai/streams/${selected.id}.mjpg?session=${activePipeline.session_id}`} alt="Live AI stream" /> : <div className="camera-placeholder"><strong>Chọn camera và bấm Chạy AI</strong><span>YOLO26 phát hiện · ByteTrack gán ID · xe cắt counting line sẽ được lưu PostgreSQL</span></div>}
            </div>
            <div className="camera-select"><label>Camera</label><select value={selectedId || ''} onChange={e => setSelectedId(Number(e.target.value))}><option value="">-- Chọn camera --</option>{cameras.map(c => <option key={c.id} value={c.id}>{c.code} · {c.name}</option>)}</select><span>{activePipeline ? `FPS ${activePipeline.fps} · Tổng ${activePipeline.total_count} · IN ${activePipeline.in_count ?? 0} · OUT ${activePipeline.out_count ?? 0}` : selected?.source_url || 'Chưa có camera'}</span></div>
            {selected && !activePipeline && <div className={`source-status ${sourceStatus?.valid ? 'ok' : 'bad'}`}><strong>{sourceStatus?.valid ? '✓ Nguồn sẵn sàng' : '⚠ Nguồn chưa sẵn sàng'}</strong><span>{sourceStatus?.message || 'Đang kiểm tra nguồn...'}</span>{sourceStatus?.suggested_source_url && <><small>Gợi ý: {sourceStatus.suggested_source_url}</small><button type="button" className="inline-action" onClick={applySuggestedSource}>Dùng nguồn gợi ý</button></>}</div>}
            {latestPipeline && !activePipeline && <div className="pipeline-result">Lần chạy gần nhất: <strong>{latestPipeline.status}</strong> · {latestPipeline.processed_frames} frame · {latestPipeline.total_count} xe · đã ghi {latestPipeline.delivered_events ?? 0} sự kiện{latestPipeline.last_error ? ` · ${latestPipeline.last_error}` : ''}</div>}
          </article>
          <article className="panel"><div className="panel-head"><div><span className="panel-kicker">VEHICLE COUNT</span><h2>Theo loại phương tiện</h2></div></div><div className="vehicle-list">{vehicleRows.map(row => <div className="vehicle-row" key={row.label}><span>{row.label}</span><strong>{row.value}</strong></div>)}</div></article>
        </section>

        <section className="content-grid lower-grid">
          <article className="panel" id="cameras"><div className="panel-head"><div><span className="panel-kicker">COUNTING LINE</span><h2>Cấu hình vùng đếm</h2></div></div>
            <p className="hint">Xe chỉ được đếm khi điểm đáy giữa của bounding box cắt đường màu vàng. Nếu xe đi dọc khung hình, dùng đường ngang; nếu xe đi ngang khung hình, dùng đường dọc.</p>
            <div className="preset-row"><button type="button" disabled={busy || !!activePipeline} onClick={()=>applyPreset('horizontal')}>Đường ngang</button><button type="button" disabled={busy || !!activePipeline} onClick={()=>applyPreset('vertical')}>Đường dọc</button></div>
            <div className="line-grid">{lineField('line_x1','X1')}{lineField('line_y1','Y1')}{lineField('line_x2','X2')}{lineField('line_y2','Y2')}{lineField('confidence_threshold','Confidence')}</div>
            <button disabled={!selected || busy || !!activePipeline} onClick={saveCountingLine}>Lưu cấu hình đếm</button>
          </article>

          <article className="panel"><div className="panel-head"><div><span className="panel-kicker">CAMERA SOURCE</span><h2>{editingId ? `Sửa Camera #${editingId}` : 'Tạo camera mới'}</h2></div><button className="secondary" type="button" disabled={busy || !!activePipeline} onClick={beginNewCamera}>Camera mới</button></div><form className="camera-form" onSubmit={saveCamera}>
            <input value={form.name} onChange={e => setForm({...form, name:e.target.value})} placeholder="Tên camera" required />
            <input value={form.code} onChange={e => setForm({...form, code:e.target.value})} placeholder="Mã camera" required />
            <select value={form.source_type} onChange={e => setForm({...form, source_type:e.target.value})}><option value="video">Video local</option><option value="rtsp">RTSP</option><option value="webcam">Webcam Linux</option></select>
            {form.source_type === 'video' ? <select className="wide" value={form.source_url} onChange={e=>setForm({...form, source_url:e.target.value})}>
              {!videoPathSet.has(form.source_url) && form.source_url && <option value={form.source_url}>⚠ {form.source_url} (không tồn tại)</option>}
              <option value="">-- Chọn video trong thư mục videos --</option>
              {videoSources.map(v => <option value={v.source_url} key={v.source_url}>{v.name}</option>)}
            </select> : <input className="wide" value={form.source_url} onChange={e => setForm({...form, source_url:e.target.value})} placeholder={form.source_type === 'rtsp' ? 'rtsp://user:pass@ip/stream' : '0'} required />}
            <input className="wide" value={form.location || ''} onChange={e => setForm({...form, location:e.target.value})} placeholder="Vị trí / mô tả ngắn" />
            <div className="camera-actions"><button disabled={busy || !!activePipeline}>{editingId ? 'Cập nhật camera' : 'Tạo camera'}</button>{editingId && <span className={form.source_type === 'video' && !videoPathSet.has(form.source_url) ? 'bad-text' : 'ok-text'}>{form.source_type === 'video' ? (videoPathSet.has(form.source_url) ? 'File video đang tồn tại.' : 'Hãy chọn lại file video rồi cập nhật camera.') : 'Nguồn sẽ được kiểm tra trước khi chạy AI.'}</span>}</div>
          </form><p className="hint">Video local được đọc từ <code>D:\LienThongDH\DoAn\traffic-ai\videos</code>. Khi đổi tên file, hãy chọn tên mới ở đây và bấm <strong>Cập nhật camera</strong>; đường dẫn lưu trong PostgreSQL sẽ được thay đổi.</p></article>
        </section>

        <section className="content-grid lower-grid" id="events">
          <article className="panel"><div className="panel-head"><div><span className="panel-kicker">RECENT EVENTS</span><h2>Lịch sử đếm gần nhất</h2></div></div><div className="event-list">{events.length ? events.map(e => <div className="event-row" key={e.id}><span>#{e.tracking_id ?? '-'} · {vehicleLabels[e.vehicle_type] || e.vehicle_type}</span><strong>{String(e.direction).toUpperCase()}</strong><small>{new Date(e.detected_at).toLocaleString()}</small></div>) : <div className="empty">Chưa có sự kiện cắt counting line.</div>}</div></article>
          <article className="panel"><div className="panel-head"><div><span className="panel-kicker">COUNTING SESSIONS</span><h2>Lịch sử phiên chạy</h2></div></div><div className="event-list">{sessions.length ? sessions.map(s => <div className="event-row" key={s.id}><span>Session #{s.id} · Camera #{s.camera_id}</span><strong>{String(s.status).toUpperCase()}</strong><small>{s.total_vehicles} xe · FPS {s.average_fps ?? '-'} · {new Date(s.started_at).toLocaleString()}</small></div>) : <div className="empty">Chưa có phiên chạy.</div>}</div></article>
        </section>
      </main>
    </div>
  )
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>)
