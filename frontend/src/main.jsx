import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const vehicleLabels = {
  motorcycle: 'Xe m\u00e1y',
  bicycle: 'Xe \u0111\u1ea1p',
  car: '\u00d4 t\u00f4',
  bus: 'Xe bu\u00fdt',
  truck: 'Xe t\u1ea3i',
  other: 'Kh\u00e1c'
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
    source_url: '/data/videos/demo.mp4', location: 'Khu v\u1ef1c demo',
    confidence_threshold: 0.35, line_x1: 0.1, line_y1: 0.5, line_x2: 0.9, line_y2: 0.5
  })

  const load = async () => {
    try {
      setError('')
      const [summaryRes, healthRes, systemStatusRes, camerasRes, eventsRes, pipelinesRes] = await Promise.all([
        fetch('/api/dashboard/summary'), fetch('/api/health'), fetch('/api/system/status'), fetch('/api/cameras'),
        fetch('/api/events?limit=20'), fetch('/api/pipelines')
      ])
      if (![summaryRes, healthRes, camerasRes, eventsRes].every(r => r.ok)) throw new Error('API ch\u01b0a s\u1eb5n s\u00e0ng')
      setSummary(await summaryRes.json())
      setHealth(await healthRes.json())
      setSystemStatus(systemStatusRes.ok ? await systemStatusRes.json() : null)
      const cameraData = await camerasRes.json()
      setCameras(cameraData)
      setEvents(await eventsRes.json())
      setPipelines(pipelinesRes.ok ? await pipelinesRes.json() : [])
      if (!selectedId && cameraData.length) setSelectedId(cameraData[0].id)
    } catch (err) {
      setError(err.message || 'Kh\u00f4ng th\u1ec3 t\u1ea3i d\u1eef li\u1ec7u')
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
      if (!response.ok) throw new Error((await response.json()).detail || 'Kh\u00f4ng t\u1ea1o \u0111\u01b0\u1ee3c camera')
      const camera = await response.json(); setSelectedId(camera.id); await load()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const togglePipeline = async () => {
    if (!selected) return
    setBusy(true); setError('')
    try {
      const action = activePipeline ? 'stop' : 'start'
      const response = await fetch(`/api/cameras/${selected.id}/${action}`, { method: 'POST' })
      if (!response.ok) throw new Error((await response.json()).detail || 'Kh\u00f4ng th\u1ec3 thay \u0111\u1ed5i pipeline')
      await load()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark">AI</div><div><strong>Traffic AI</strong><span>YOLO26 + ByteTrack</span></div></div>
        <nav><a className="active" href="#overview">T\u1ed5ng quan</a><a href="#live">Gi\u00e1m s\u00e1t</a><a href="#cameras">Camera</a><a href="#events">S\u1ef1 ki\u1ec7n</a></nav>
        <div className="sidebar-footer">V0.2.3 \u00b7 YOLO26n + ByteTrack</div>
      </aside>
      <main>
        <header className="topbar"><div><p className="eyebrow">\u0110\u1ed2 \u00c1N TR\u00cd TU\u1ec6 NH\u00c2N T\u1ea0O</p><h1>Ph\u00e1t hi\u1ec7n, theo d\u00f5i v\u00e0 \u0111\u1ebfm ph\u01b0\u01a1ng ti\u1ec7n</h1></div><div className={`health ${health?.status === 'ok' ? 'online' : ''}`}><span className="dot" />{health?.status === 'ok' ? 'H\u1ec7 th\u1ed1ng ho\u1ea1t \u0111\u1ed9ng' : '\u0110ang k\u1ebft n\u1ed1i'}</div></header>
        {error && <div className="error-banner">{error}</div>}
        <section className="stats-grid" id="overview">
          <StatCard title="Camera" value={summary?.total_cameras ?? '\u2014'} note={`${summary?.active_cameras ?? 0} \u0111ang ch\u1ea1y`} />
          <StatCard title="Ph\u01b0\u01a1ng ti\u1ec7n" value={summary?.total_events ?? '\u2014'} note="\u0110\u00e3 c\u1eaft counting line" />
          <StatCard title="Phi\u00ean \u0111\u1ebfm" value={summary?.running_sessions ?? '\u2014'} note="\u0110ang ho\u1ea1t \u0111\u1ed9ng" />
          <StatCard title="GPU" value={systemStatus?.ai?.gpu?.available ? 'CUDA' : (systemStatus?.ai_service === 'ready' ? 'CPU' : '—')} note={systemStatus?.ai?.gpu?.name || systemStatus?.ai?.model || (systemStatus?.ai_service === 'ready' ? 'AI service' : 'AI service đang khởi động')} />
        </section>
        <section className="content-grid" id="live">
          <article className="panel camera-panel">
            <div className="panel-head"><div><span className="panel-kicker">LIVE AI</span><h2>Camera Preview</h2></div><button className={activePipeline ? 'danger' : ''} disabled={!selected || busy} onClick={togglePipeline}>{activePipeline ? 'D\u1eebng AI' : 'Ch\u1ea1y AI'}</button></div>
            <div className="camera-stage">
              {activePipeline ? <img src={`/ai/streams/${selected.id}.mjpg`} alt="Live AI stream" /> : <div className="camera-placeholder"><strong>Ch\u1ecdn camera v\u00e0 b\u1ea5m Ch\u1ea1y AI</strong><span>YOLO26 ph\u00e1t hi\u1ec7n \u00b7 ByteTrack g\u00e1n ID \u00b7 counting line \u0111\u1ebfm IN/OUT</span></div>}
            </div>
            <div className="camera-select"><label>Camera</label><select value={selectedId || ''} onChange={e => setSelectedId(Number(e.target.value))}><option value="">-- Ch\u1ecdn camera --</option>{cameras.map(c => <option key={c.id} value={c.id}>{c.code} \u00b7 {c.name}</option>)}</select><span>{activePipeline ? `FPS ${activePipeline.fps} \u00b7 Count ${activePipeline.total_count}` : selected?.source_url || 'Ch\u01b0a c\u00f3 camera'}</span></div>
          </article>
          <article className="panel"><div className="panel-head"><div><span className="panel-kicker">VEHICLE COUNT</span><h2>Theo lo\u1ea1i ph\u01b0\u01a1ng ti\u1ec7n</h2></div></div><div className="vehicle-list">{vehicleRows.map(row => <div className="vehicle-row" key={row.label}><span>{row.label}</span><strong>{row.value}</strong></div>)}</div></article>
        </section>
        <section className="content-grid lower-grid">
          <article className="panel" id="cameras"><div className="panel-head"><div><span className="panel-kicker">CAMERA SOURCE</span><h2>Th\u00eam camera / video</h2></div></div><form className="camera-form" onSubmit={createCamera}>
            <input value={form.name} onChange={e => setForm({...form, name:e.target.value})} placeholder="T\u00ean camera" />
            <input value={form.code} onChange={e => setForm({...form, code:e.target.value})} placeholder="M\u00e3 camera" />
            <select value={form.source_type} onChange={e => setForm({...form, source_type:e.target.value})}><option value="video">Video MP4</option><option value="rtsp">RTSP</option><option value="webcam">Webcam Linux</option></select>
            <input className="wide" value={form.source_url} onChange={e => setForm({...form, source_url:e.target.value})} placeholder="/data/videos/demo.mp4 ho\u1eb7c rtsp://..." />
            <button disabled={busy}>T\u1ea1o camera</button>
          </form><p className="hint">Video local: ch\u00e9p file v\u00e0o th\u01b0 m\u1ee5c <code>videos</code>, sau \u0111\u00f3 d\u00f9ng <code>/data/videos/ten-file.mp4</code>.</p></article>
          <article className="panel" id="events"><div className="panel-head"><div><span className="panel-kicker">RECENT EVENTS</span><h2>L\u1ecbch s\u1eed \u0111\u1ebfm g\u1ea7n nh\u1ea5t</h2></div></div><div className="event-list">{events.length ? events.map(e => <div className="event-row" key={e.id}><span>#{e.tracking_id ?? '-'} \u00b7 {vehicleLabels[e.vehicle_type] || e.vehicle_type}</span><strong>{String(e.direction).toUpperCase()}</strong><small>{new Date(e.detected_at).toLocaleString()}</small></div>) : <div className="empty">Ch\u01b0a c\u00f3 s\u1ef1 ki\u1ec7n.</div>}</div></article>
        </section>
      </main>
    </div>
  )
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>)
