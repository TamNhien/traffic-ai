import React, {useCallback, useEffect, useState} from 'react'
import {secureFetch} from './security.jsx'
import {readableApiDetail} from './account-utils.js'

async function ensureOk(response) {
  if (!response.ok) {
    const body=await response.json().catch(()=>({}))
    throw Error(readableApiDetail(body.detail,response.status))
  }
  return response.json()
}

const fmtBytes=n=>Number.isFinite(Number(n)) ? `${(Number(n)/(1024*1024)).toFixed(1)} MB` : '—'
const fmtDate=d=>d ? new Date(d).toLocaleString('vi-VN') : '—'
const labels={queued:'Đang chờ',running:'Đang xử lý',completed:'Hoàn thành',failed:'Thất bại'}

// Admin-only tab. Server enforces role + session + CSRF on every endpoint.
export function BackupPanel() {
  const [data,setData]=useState(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [file,setFile]=useState(null)
  const [schedule,setSchedule]=useState(null)
  const [selected,setSelected]=useState('')
  const [confirmation,setConfirmation]=useState('')
  const refresh=useCallback(async()=>{
    const response=await secureFetch('/api/admin/backups',{cache:'no-store'})
    const next=await ensureOk(response)
    setData(next)
    setSchedule(previous=>previous??next.settings)
    return next
  },[])
  useEffect(()=>{
    let alive=true
    refresh().catch(err=>{if(alive)setError(err.message)})
    const timer=setInterval(()=>refresh().catch(()=>{}),5000)
    return ()=>{alive=false;clearInterval(timer)}
  },[refresh])
  const act=async fn=>{
    setBusy(true);setError('');setNotice('')
    try {const message=await fn();setNotice(message||'Đã gửi yêu cầu.');await refresh()}
    catch(err){setError(err.message)}finally{setBusy(false)}
  }
  const create=()=>act(async()=>{
    await ensureOk(await secureFetch('/api/admin/backups',{method:'POST'}))
    return 'Đã xếp hàng sao lưu PostgreSQL. Trạng thái tự cập nhật sau mỗi 5 giây.'
  })
  const saveSchedule=()=>act(async()=>{
    await ensureOk(await secureFetch('/api/admin/backups/settings',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({automatic:schedule.automatic,hours:Number(schedule.hours),retention:Number(schedule.retention)})
    }))
    return 'Đã lưu lịch backup. Worker tự cập nhật trong tối đa 10 giây.'
  })
  const upload=()=>act(async()=>{
    if(!file)throw Error('Hãy chọn tệp .zip hoặc .dump')
    if(file.size > 1024*1024*1024)throw Error('Dung lượng tối đa 1 GB')
    const result=await ensureOk(await secureFetch('/api/admin/backups/import',{
      method:'POST',headers:{'Content-Type':file.name.toLowerCase().endsWith('.zip')?'application/zip':'application/octet-stream'},body:file
    }))
    setSelected(result.id);setFile(null)
    return `Đã kiểm tra và nhập ${fmtBytes(result.bytes)}. Chưa ghi đè dữ liệu đang chạy.`
  })
  const restore=()=>act(async()=>{
    if(!selected)throw Error('Chọn bản sao lưu cần khôi phục')
    const phrase=`KHOI PHUC ${data?.database||'traffic_ai_db'}`
    if(confirmation!==phrase)throw Error(`Phải nhập chính xác: ${phrase}`)
    if(!window.confirm('CẢNH BÁO: sẽ ngắt kết nối database đang dùng, chuyển sang dữ liệu backup và giữ lại DB cũ. Dừng mọi phiên AI trước khi tiếp tục. Xác nhận?'))return ''
    await ensureOk(await secureFetch('/api/admin/backups/restore',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({backup_id:selected,confirmation})
    }))
    setConfirmation('')
    return 'Đã yêu cầu kiểm tra và phục hồi sang database tạm; hệ thống chỉ chuyển database sau khi restore hoàn tất. Hãy khởi động lại backend/AI sau khi thành công.'
  })
  const jobs=data?.jobs||[]
  const pending=jobs.some(j=>['queued','running'].includes(j.status))
  return <section className="panel backup-panel" id="backups">
    <div className="panel-head"><div><span className="panel-kicker">ADMIN · DATA RECOVERY</span><h2>Sao lưu, khôi phục & chuyển máy</h2></div><button type="button" onClick={()=>refresh().catch(err=>setError(err.message))} disabled={busy}>Làm mới</button></div>
    <p className="hint">PostgreSQL 18 · Cơ sở dữ liệu <strong>{data?.database||'...'}</strong> · Backup tự động: <strong>{data?.settings?.automatic?'Bật':'Tắt'}</strong> · mỗi <strong>{data?.settings?.hours||'—'} giờ</strong> · giữ <strong>{data?.settings?.retention||'—'}</strong> bản tự động gần nhất.</p>
    <div className="backup-actions"><button className="primary" onClick={create} disabled={busy||pending}>+ Sao lưu ngay</button><label className="backup-upload">Chọn ZIP chuyển máy hoặc .dump<input type="file" accept=".zip,.dump,application/zip" onChange={e=>setFile(e.target.files?.[0]||null)} /></label><button onClick={upload} disabled={busy||pending||!file}>Nhập bản sao lưu</button></div>
    {error&&<div className="error-banner" role="alert">{error}</div>}
    {notice&&<div className="notice-banner" role="status">{notice}</div>}
    {schedule&&<div className="backup-schedule">
      <h3>Lịch sao lưu tự động</h3>
      <label><input type="checkbox" checked={schedule.automatic} onChange={e=>setSchedule({...schedule,automatic:e.target.checked})}/> Bật lịch sao lưu</label>
      <label>Chu kỳ (giờ)<input type="number" min="1" max="720" value={schedule.hours} onChange={e=>setSchedule({...schedule,hours:e.target.value})}/></label>
      <label>Giữ tối đa bản tự động<input type="number" min="1" max="365" value={schedule.retention} onChange={e=>setSchedule({...schedule,retention:e.target.value})}/></label>
      <button onClick={saveSchedule} disabled={busy||!Number.isInteger(Number(schedule.hours))||Number(schedule.hours)<1||Number(schedule.hours)>720||!Number.isInteger(Number(schedule.retention))||Number(schedule.retention)<1||Number(schedule.retention)>365}>Lưu lịch sao lưu</button>
    </div>}
    <h3>Các bản sao lưu ({data?.backups?.length||0})</h3>
    <div className="backup-list">{(data?.backups||[]).map(b=><div className="backup-row" key={b.id}>
      <div><strong>{fmtDate(b.created_at)}</strong><small>{b.automatic?'Tự động':b.imported?'Chuyển từ máy khác':'Thủ công'} · {fmtBytes(b.bytes)} · SHA-256 {b.sha256?.slice(0,16)}…</small></div>
      <a href={`/api/admin/backups/${b.id}/download`} download>Tải .dump</a>
      <a href={`/api/admin/backups/${b.id}/transfer`} download>Tải ZIP chuyển máy</a>
      <button className="secondary" onClick={()=>{setSelected(b.id);setConfirmation('')}}>Chọn phục hồi</button>
    </div>)}{!data?.backups?.length&&<p>Chưa có bản sao lưu. Nhấn Sao lưu ngay để tạo bản đầu tiên.</p>}</div>
    <div className="backup-restore"><h3>Khôi phục an toàn</h3>
      <p className="hint">Bản sao được phục hồi vào <strong>database tạm</strong> trước khi chuyển đổi. Database đang dùng được giữ lại dưới tên <code>traffic_old_...</code> để hoàn tác. Quá trình chuyển đổi sẽ ngắt các kết nối; hãy dừng AI, không sử dụng dữ liệu đang ghi và chủ động sao lưu hiện trạng trước khi khôi phục.</p>
      <label>Bản sao lưu đã chọn<select value={selected} onChange={e=>{setSelected(e.target.value);setConfirmation('')}}><option value="">-- Chọn bản sao --</option>{(data?.backups||[]).map(b=><option key={b.id} value={b.id}>{fmtDate(b.created_at)} · {fmtBytes(b.bytes)} · {b.id.slice(0,8)}</option>)}</select></label>
      <label>Nhập chính xác <strong>KHOI PHUC {data?.database||'traffic_ai_db'}</strong> để xác nhận<input value={confirmation} onChange={e=>setConfirmation(e.target.value)} placeholder={`KHOI PHUC ${data?.database||'traffic_ai_db'}`} autoComplete="off" /></label>
      <button className="danger" onClick={restore} disabled={busy||pending||!selected||confirmation!==`KHOI PHUC ${data?.database||'traffic_ai_db'}`}>Khôi phục từ bản đã chọn</button>
    </div>
    <h3>Nhật ký tác vụ</h3>
    <div className="backup-list">{jobs.slice(0,15).map(j=><div className="backup-row" key={j.id}><strong>{j.action==='restore'?'Khôi phục':'Sao lưu'} · {labels[j.status]||j.status}</strong><span>{fmtDate(j.created_at)}</span><small>{j.message}{j.result?.rollback_database?` · DB cũ: ${j.result.rollback_database}`:''}</small></div>)}</div>
    <p className="hint">Chuyển máy: tải ZIP chuyển máy ở đây, chuyển riêng <code>.env</code> và các thư mục <code>models/</code>, <code>videos/</code>, <code>datasets/</code> nếu cần. Trên máy đích vào trang này → Nhập bản sao lưu → Chọn phục hồi. Không đăng gói ZIP lên GitHub.</p>
  </section>
}
