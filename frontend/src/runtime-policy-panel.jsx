import React, { useEffect, useMemo, useState } from 'react'
import { secureFetch } from './security.jsx'
import { filterPolicyRows, runtimePolicyView } from './runtime-policy.js'

export function RuntimePolicyPanel({ benchmarkId, sessionId }) {
  const [opened, setOpened] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState({status: 'idle', view: null})
  const [query, setQuery] = useState('')

  useEffect(() => {
    if (!opened) return undefined
    const controller = new AbortController()
    let current = true
    setState({status: 'loading', view: null})
    setQuery('')
    const load = async () => {
      try {
        const response = await secureFetch(`/api/benchmarks/${benchmarkId}/runtime-policy`, {
          cache: 'no-store', signal: controller.signal,
        })
        if (!response.ok) throw new Error('policy_unavailable')
        const payload = await response.json()
        if (current) setState({status: 'loaded', view: runtimePolicyView(payload, sessionId)})
      } catch {
        if (current && !controller.signal.aborted) setState({status: 'error', view: null})
      }
    }
    load()
    return () => { current = false; controller.abort() }
  }, [benchmarkId, sessionId, opened, attempt])

  const view = state.view
  const rows = useMemo(() => filterPolicyRows(view?.rows || [], query), [view, query])
  return <details className="runtime-policy" onToggle={event => {
    if (event.target === event.currentTarget) setOpened(event.currentTarget.open)
  }}>
    <summary>Cấu hình thực tế của phiên <small>Thông tin đã ghi khi AI chạy phiên #{sessionId}</small></summary>
    <div className="runtime-policy-body">
      {state.status === 'loading' && <p role="status">Đang đọc cấu hình đã ghi…</p>}
      {state.status === 'error' && <p role="status">Không tải được cấu hình của phiên.</p>}
      {view && <p role="status">{view.message}</p>}
      {view?.available && <>
        <dl className="runtime-policy-summary">
          <div><dt>AI của phiên</dt><dd>{view.runtimeVersion || 'Chưa ghi'}</dd></div>
          <div><dt>Tham số đã ghi</dt><dd>{view.rows.length}</dd></div>
          <div><dt>Bộ lọc đầu vạch</dt><dd>{view.endpointGuard}</dd></div>
          <div><dt>Mở rộng sang rescue</dt><dd>{view.rescueGuard}</dd></div>
          <div><dt>Trường thiếu / chưa đọc được</dt><dd>{view.missingCount}</dd></div>
          <div><dt>Thành phần không có</dt><dd>{view.absentCount}</dd></div>
        </dl>
        <p className="runtime-policy-note">Chỉ gồm các tham số thuật toán trong danh sách ghi nhận, chưa đại diện cho toàn bộ model, video và hình học. Phần thông tin đầu trace đã được kiểm tra; chưa xác minh toàn bộ tệp.</p>
        <details className="runtime-policy-parameters">
          <summary>Tra cứu {view.rows.length} tham số và mã đối chiếu</summary>
          <p>Mã cấu hình <code>{view.configurationDigest}</code></p>
          {view.sourceDigest && <p>Mã nguồn AI <code>{view.sourceDigest}</code></p>}
          <label>Tìm tham số<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Tên nhóm, tham số hoặc giá trị" /></label>
          <div className="runtime-policy-table"><table><thead><tr><th scope="col">Nhóm</th><th scope="col">Tham số</th><th scope="col">Giá trị đã ghi</th></tr></thead><tbody>
            {rows.map(row => <tr key={`${row.component}.${row.name}`}><td>{row.group}</td><td>{row.name}</td><td>{row.value}</td></tr>)}
          </tbody></table></div>
          {!rows.length && <p>Không có tham số phù hợp.</p>}
        </details>
      </>}
      {state.status !== 'loading' && state.status !== 'idle' && <button type="button" className="secondary compact" onClick={() => setAttempt(value => value + 1)}>Tải lại cấu hình đã ghi</button>}
    </div>
  </details>
}
