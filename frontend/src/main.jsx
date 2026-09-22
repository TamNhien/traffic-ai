import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const labels = {
  motorcycle: 'Xe máy',
  bicycle: 'Xe đạp',
  car: 'Ô tô',
  bus: 'Xe buýt',
  truck: 'Xe tải',
  other: 'Khác'
}

function StatCard({ title, value, note }) {
  return (
    <article className="stat-card">
      <span className="stat-title">{title}</span>
      <strong className="stat-value">{value}</strong>
      <span className="stat-note">{note}</span>
    </article>
  )
}

function App() {
  const [summary, setSummary] = useState(null)
  const [health, setHealth] = useState(null)
  const [error, setError] = useState('')

  const load = async () => {
    try {
      setError('')
      const [summaryRes, healthRes] = await Promise.all([
        fetch('/api/dashboard/summary'),
        fetch('/api/health')
      ])
      if (!summaryRes.ok || !healthRes.ok) throw new Error('API chưa sẵn sàng')
      setSummary(await summaryRes.json())
      setHealth(await healthRes.json())
    } catch (err) {
      setError(err.message || 'Không thể tải dữ liệu')
    }
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 10000)
    return () => clearInterval(id)
  }, [])

  const vehicleRows = useMemo(() => {
    const data = summary?.by_vehicle_type || {}
    return Object.entries(labels).map(([key, label]) => ({ key, label, value: data[key] || 0 }))
  }, [summary])

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">AI</div>
          <div>
            <strong>Traffic AI</strong>
            <span>Vehicle Intelligence</span>
          </div>
        </div>
        <nav>
          <a className="active" href="#overview">Tổng quan</a>
          <a href="#cameras">Camera</a>
          <a href="#events">Lịch sử nhận diện</a>
          <a href="#statistics">Thống kê</a>
          <a href="#models">AI Models</a>
          <a href="#settings">Cấu hình</a>
        </nav>
        <div className="sidebar-footer">V0.1.3 · Infrastructure</div>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <p className="eyebrow">ĐỒ ÁN TRÍ TUỆ NHÂN TẠO</p>
            <h1>Giám sát và đếm phương tiện giao thông</h1>
          </div>
          <div className={`health ${health?.status === 'ok' ? 'online' : ''}`}>
            <span className="dot" />
            {health?.status === 'ok' ? 'Hệ thống hoạt động' : 'Đang kết nối'}
          </div>
        </header>

        {error && <div className="error-banner">{error}</div>}

        <section className="stats-grid" id="overview">
          <StatCard title="Camera" value={summary?.total_cameras ?? '—'} note={`${summary?.active_cameras ?? 0} đang hoạt động`} />
          <StatCard title="Phương tiện" value={summary?.total_events ?? '—'} note="Tổng lượt đã ghi nhận" />
          <StatCard title="Phiên đang chạy" value={summary?.running_sessions ?? '—'} note="Counting sessions" />
          <StatCard title="AI Service" value={health?.ai_service === 'ready' ? 'READY' : '—'} note="YOLO + ByteTrack ở V0.2" />
        </section>

        <section className="content-grid">
          <article className="panel camera-panel" id="cameras">
            <div className="panel-head">
              <div>
                <span className="panel-kicker">LIVE PIPELINE</span>
                <h2>Camera Preview</h2>
              </div>
              <span className="badge">V0.2</span>
            </div>
            <div className="camera-placeholder">
              <div className="scanline" />
              <div className="camera-icon">◎</div>
              <strong>AI video pipeline đang chờ tích hợp</strong>
              <span>V0.2 sẽ thêm YOLO, ByteTrack, line crossing và luồng video.</span>
            </div>
          </article>

          <article className="panel" id="statistics">
            <div className="panel-head">
              <div>
                <span className="panel-kicker">VEHICLE COUNT</span>
                <h2>Theo loại phương tiện</h2>
              </div>
            </div>
            <div className="vehicle-list">
              {vehicleRows.map(row => (
                <div className="vehicle-row" key={row.key}>
                  <span>{row.label}</span>
                  <strong>{row.value}</strong>
                </div>
              ))}
            </div>
          </article>
        </section>

        <section className="panel system-panel" id="models">
          <div className="panel-head">
            <div>
              <span className="panel-kicker">SYSTEM STATUS</span>
              <h2>Hạ tầng V0.1.3</h2>
            </div>
            <button onClick={load}>Làm mới</button>
          </div>
          <div className="system-grid">
            <div><span>HTTPS Gateway</span><strong>8443 / 8444</strong></div>
            <div><span>PostgreSQL</span><strong>18 · port 5445</strong></div>
            <div><span>Backend</span><strong>FastAPI</strong></div>
            <div><span>Database</span><strong>traffic_ai_db</strong></div>
          </div>
        </section>
      </main>
    </div>
  )
}

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
