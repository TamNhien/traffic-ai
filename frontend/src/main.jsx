import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const vehicleLabels = {
  motorcycle: 'Xe máy',
  bicycle: 'Xe đạp',
  car: 'Ô tô',
  bus: 'Xe buýt',
  truck: 'Xe tải',
  other: 'Khác'
}

function StatCard({ title, value, note }) {
  return <article className="stat-card"><span>{title}</span><strong>{value}</strong><small>{note}</small></article>
}

function App() {
  const [summary, setSummary] = useState(null)
  const [health, setHealth] = useState(null)
  const [systemStatus, setSystemStatus] = useState(null)
  const [cameras, setCameras] = useState([])
  const [events, setEvents] = useState([])
  const [pipelines, setPipelines] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({
    name: 'Camera demo', code: 'CAM-001', source_type: 'video',
    source_url: '/data/videos/demo.mp4', location: 'Khu vực demo',
    confidence_threshold: 0.35, line_x1: 0.1, line_y1: 0.5, line_x2: 0.9, line_y2: 0.5
  })

  const load = async () => {
    try {
      setError('')
      const [summaryRes, healthRes, systemStatusRes, camerasRes, eventsRes, pipelinesRes] = await Promise.all([
        fetch('/api/dashboard/summary'), fetch('/api/health'), fetch('/api/system/status'), fetch('/api/cameras'),
        fetch('/api/events?limit=20'), fetch('/api/pipelines')
      ])
      if (![summaryRes, healthRes, camerasRes, eventsRes].every(r => r.ok)) throw new Error('API chưa sẵn sàng')
      setSummary(await summaryRes.json())
      setHealth(await healthRes.json())
      setSystemStatus(systemStatusRes.ok ? await systemStatusRes.json() : null)
      const cameraData = await camerasRes.json()
      setCameras(cameraData)
      setEvents(await eventsRes.json())
      setPipelines(pipelinesRes.ok ? await pipelinesRes.json() : [])
      if (!selectedId && cameraData.length) setSelectedId(cameraData[0].id)
    } catch (err) {
      setError(err.message || 'Không thể tải dữ liệu')
    }
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [])

  const selected = cameras.find(c => c.id === Number(selectedId))
  const activePipeline = pipelines.find(p => p.camera_id === Number(selectedId) && ['starting', 'running'].includes(p.status))
  const vehicleRows = useMemo(() => Object.entries(vehicleLabels).map(([key, label]) => ({ label, value: summary?.by_vehicle_type?.[key] || 0 })), [summary])

  const createCamera = async e => {
    e.preventDefault(); setBusy(true); setError('')
    try {
      const response = await fetch('/api/cameras', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form) })
      if (!response.ok) throw new Error((await response.json()).detail || 'Không tạo được camera')
      const camera = await response.json(); setSelectedId(camera.id); await load()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const togglePipeline = async () => {
    if (!selected) return
    setBusy(true); setError('')
    try {
      const action = activePipeline ? 'stop' : 'start'
      const response = await fetch(`/api/cameras/${selected.id}/${action}`, { method: 'POST' })
      if (!response.ok) throw new Error((await response.json()).detail || 'Không thể thay đổi pipeline')
      await load()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark">AI</div><div><strong>Traffic AI</strong><span>YOLO26 + ByteTrack</span></div></div>
        <nav><a className="active" href="#overview">Tổng quan</a><a href="#live">Giám sát</a><a href="#cameras">Camera</a><a href="#events">Sự kiện</a></nav>
        <div className="sidebar-footer">V0.2.5 · YOLO26n + ByteTrack</div>
      </aside>
      <main>
        <header className="topbar"><div><p className="eyebrow">ĐỒ ÁN TRÍ TUỆ NHÂN TẠO</p><h1>Phát hiện, theo dõi và đếm phương tiện</h1></div><div className={`health ${health?.status === 'ok' ? 'online' : ''}`}><span className="dot" />{health?.status === 'ok' ? 'Hệ thống hoạt động' : 'Đang kết nối'}</div></header>
        {error && <div className="error-banner">{error}</div>}
        <section className="stats-grid" id="overview">
          <StatCard title="Camera" value={summary?.total_cameras ?? '—'} note={`${summary?.active_cameras ?? 0} đang chạy`} />
          <StatCard title="Phương tiện" value={summary?.total_events ?? '—'} note="Đã cắt counting line" />
          <StatCard title="Phiên đếm" value={summary?.running_sessions ?? '—'} note="Đang hoạt động" />
          <StatCard title="GPU" value={systemStatus?.ai?.gpu?.available ? 'CUDA' : (systemStatus?.ai_service === 'ready' ? 'CPU' : '—')} note={systemStatus?.ai?.gpu?.name || systemStatus?.ai?.model || (systemStatus?.ai_service === 'ready' ? 'AI service' : 'AI service đang khởi động')} />
        </section>
        <section className="content-grid" id="live">
          <article className="panel camera-panel">
            <div className="panel-head"><div><span className="panel-kicker">LIVE AI</span><h2>Camera Preview</h2></div><button className={activePipeline ? 'danger' : ''} disabled={!selected || busy} onClick={togglePipeline}>{activePipeline ? 'Dừng AI' : 'Chạy AI'}</button></div>
            <div className="camera-stage">
              {activePipeline ? <img src={`/ai/streams/${selected.id}.mjpg`} alt="Live AI stream" /> : <div className="camera-placeholder"><strong>Chọn camera và bấm Chạy AI</strong><span>YOLO26 phát hiện · ByteTrack gán ID · counting line đếm IN/OUT</span></div>}
            </div>
            <div className="camera-select"><label>Camera</label><select value={selectedId || ''} onChange={e => setSelectedId(Number(e.target.value))}><option value="">-- Chọn camera --</option>{cameras.map(c => <option key={c.id} value={c.id}>{c.code} · {c.name}</option>)}</select><span>{activePipeline ? `FPS ${activePipeline.fps} · Count ${activePipeline.total_count}` : selected?.source_url || 'Chưa có camera'}</span></div>
          </article>
          <article className="panel"><div className="panel-head"><div><span className="panel-kicker">VEHICLE COUNT</span><h2>Theo loại phương tiện</h2></div></div><div className="vehicle-list">{vehicleRows.map(row => <div className="vehicle-row" key={row.label}><span>{row.label}</span><strong>{row.value}</strong></div>)}</div></article>
        </section>
        <section className="content-grid lower-grid">
          <article className="panel" id="cameras"><div className="panel-head"><div><span className="panel-kicker">CAMERA SOURCE</span><h2>Thêm camera / video</h2></div></div><form className="camera-form" onSubmit={createCamera}>
            <input value={form.name} onChange={e => setForm({...form, name:e.target.value})} placeholder="Tên camera" />
            <input value={form.code} onChange={e => setForm({...form, code:e.target.value})} placeholder="Mã camera" />
            <select value={form.source_type} onChange={e => setForm({...form, source_type:e.target.value})}><option value="video">Video MP4</option><option value="rtsp">RTSP</option><option value="webcam">Webcam Linux</option></select>
            <input className="wide" value={form.source_url} onChange={e => setForm({...form, source_url:e.target.value})} placeholder="/data/videos/demo.mp4 hoặc rtsp://..." />
            <button disabled={busy}>Tạo camera</button>
          </form><p className="hint">Video local: chép file vào thư mục <code>videos</code>, sau đó dùng <code>/data/videos/ten-file.mp4</code>.</p></article>
          <article className="panel" id="events"><div className="panel-head"><div><span className="panel-kicker">RECENT EVENTS</span><h2>Lịch sử đếm gần nhất</h2></div></div><div className="event-list">{events.length ? events.map(e => <div className="event-row" key={e.id}><span>#{e.tracking_id ?? '-'} · {vehicleLabels[e.vehicle_type] || e.vehicle_type}</span><strong>{String(e.direction).toUpperCase()}</strong><small>{new Date(e.detected_at).toLocaleString()}</small></div>) : <div className="empty">Chưa có sự kiện.</div>}</div></article>
        </section>
      </main>
    </div>
  )
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>)
