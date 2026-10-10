import React, {useCallback, useEffect, useState} from 'react'

let csrfToken = ''

export async function secureFetch(input, options={}) {
  const method = String(options?.method || 'GET').toUpperCase()
  const headers = new Headers(options.headers || {})
  if (['POST','PUT','PATCH','DELETE'].includes(method) && csrfToken) headers.set('X-CSRF-Token',csrfToken)
  const response = await window.fetch(input, {...options, headers, credentials:'same-origin'})
  if (response.status === 401 && !String(input).includes('/auth/login')) {
    window.dispatchEvent(new Event('traffic-ai-auth-expired'))
  }
  return response
}

async function errorOf(response) {
  const data = await response.json().catch(()=>({}))
  return data.detail || `HTTP ${response.status}`
}

export function AuthShell({children}) {
  const [state,setState] = useState({loading:true,user:null})
  const [username,setUsername] = useState('')
  const [password,setPassword] = useState('')
  const [message,setMessage] = useState('')
  const [busy,setBusy] = useState(false)
  useEffect(()=>{
    let active = true
    window.fetch('/api/auth/me',{credentials:'same-origin',cache:'no-store'}).then(async response=>{
      if (!active) return
      if (!response.ok) {csrfToken='';setState({loading:false,user:null});return}
      const data=await response.json()
      csrfToken=data.csrf_token
      setState({loading:false,user:data.user})
    }).catch(()=>{if(active)setState({loading:false,user:null})})
    const expired=()=>{csrfToken='';setState({loading:false,user:null})}
    window.addEventListener('traffic-ai-auth-expired',expired)
    return ()=>{active=false;window.removeEventListener('traffic-ai-auth-expired',expired)}
  },[])
  const login=async event=>{
    event.preventDefault();setMessage('');setBusy(true)
    try {
      const response=await window.fetch('/api/auth/login',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})})
      if(!response.ok)throw Error(await errorOf(response))
      const data=await response.json();csrfToken=data.csrf_token
      setPassword('');setState({loading:false,user:data.user})
    }catch(err){setMessage(err.message)}finally{setBusy(false)}
  }
  const logout=async()=>{
    try{await secureFetch('/api/auth/logout',{method:'POST'})}finally{csrfToken='';setState({loading:false,user:null})}
  }
  if(state.loading)return <div className="auth-page"><div className="auth-box">Đang kiểm tra phiên đăng nhập...</div></div>
  if(!state.user)return <div className="auth-page"><form className="auth-box" onSubmit={login}>
    <div className="panel-kicker">TRAFFIC AI · SECURE ACCESS</div>
    <h1>Đăng nhập hệ thống</h1>
    <p>Quản lý AI giao thông bằng tài khoản được cấp quyền. Mật khẩu được băm Argon2id.</p>
    <label>Tài khoản<input autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)} required maxLength={80}/></label>
    <label>Mật khẩu<input type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required/></label>
    {message&&<div className="error-banner">{message}</div>}
    <button className="primary" type="submit" disabled={busy}>{busy?'Đang xác thực...':'Đăng nhập'}</button>
    <small>Chưa có tài khoản Admin? Sau khi khởi động hệ thống, chạy <code>.\scripts\create-admin.ps1</code> trên máy quản trị. Không có mật khẩu mặc định.</small>
  </form></div>
  if (state.user.must_change_password) return <div className="auth-page"><div className="auth-box"><h2>Bắt buộc đổi mật khẩu</h2><AccountPanel user={state.user} onLogout={logout}/><button type="button" onClick={logout}>Đăng xuất</button></div></div>
  return children(state.user,logout)
}

export function AccountPanel({user,onLogout}) {
  const [oldPassword,setOldPassword]=useState('')
  const [newPassword,setNewPassword]=useState('')
  const [message,setMessage]=useState('')
  const [busy,setBusy]=useState(false)
  const submit=async e=>{
    e.preventDefault();setMessage('');setBusy(true)
    try{
      const response=await secureFetch('/api/auth/change-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({current_password:oldPassword,new_password:newPassword})})
      if(!response.ok)throw Error(await errorOf(response))
      setOldPassword('');setNewPassword('');await onLogout()
    }catch(err){setMessage(err.message)}finally{setBusy(false)}
  }
  const logoutAll=async()=>{
    if(!window.confirm('Đăng xuất khỏi tất cả thiết bị và thu hồi toàn bộ phiên?'))return
    try {const result=await secureFetch('/api/auth/logout-all',{method:'POST'});if(!result.ok)throw Error(await errorOf(result));}
    catch(err){setMessage(err.message);return}
    await onLogout()
  }
  return <section className="panel account-panel" id="account">
    <div className="panel-head"><div><span className="panel-kicker">ACCOUNT SECURITY</span><h2>Tài khoản của tôi</h2></div></div>
    <p>{user.full_name || user.username} · {user.role.toUpperCase()}</p>
    {user.must_change_password&&<div className="error-banner">Bạn cần đổi mật khẩu tạm trước khi sử dụng hệ thống.</div>}
    <form className="user-form" onSubmit={submit}>
      <label>Mật khẩu hiện tại<input type="password" autoComplete="current-password" value={oldPassword} required onChange={e=>setOldPassword(e.target.value)}/></label>
      <label>Mật khẩu mới (ít nhất 12 ký tự, chữ và số)<input type="password" minLength={12} maxLength={128} autoComplete="new-password" value={newPassword} required onChange={e=>setNewPassword(e.target.value)}/></label>
      <button className="primary" disabled={busy}>{busy?'Đang xử lý...':'Đổi mật khẩu'}</button>
      {message&&<div className="error-banner">{message}</div>}
    </form>
    <button type="button" className="secondary" onClick={logoutAll}>Đăng xuất khỏi tất cả thiết bị</button>
  </section>
}

export function AdminPanel({user}) {
  const [users,setUsers]=useState([])
  const [search,setSearch]=useState('')
  const [audit,setAudit]=useState([])
  const [form,setForm]=useState({username:'',full_name:'',role:'viewer',password:''})
  const [message,setMessage]=useState('')
  const [busy,setBusy]=useState(false)
  const refresh=useCallback(async()=>{
    try{
      const [u,a]=await Promise.all([secureFetch('/api/admin/users'),secureFetch('/api/admin/audit?limit=80')])
      if(!u.ok)throw Error(await errorOf(u))
      setUsers(await u.json());if(a.ok)setAudit(await a.json())
    }catch(err){setMessage(err.message)}
  },[])
  useEffect(()=>{refresh()},[refresh])
  const create=async e=>{
    e.preventDefault();setBusy(true);setMessage('')
    try{
      const res=await secureFetch('/api/admin/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(form)})
      if(!res.ok)throw Error(await errorOf(res))
      setForm({username:'',full_name:'',role:'viewer',password:''});setMessage('Đã tạo tài khoản. Yêu cầu đổi mật khẩu khi đăng nhập lần đầu.');await refresh()
    }catch(err){setMessage(err.message)}finally{setBusy(false)}
  }
  const edit=async(target,patch)=>{
    setBusy(true);setMessage('')
    try{
      const res=await secureFetch(`/api/admin/users/${target.id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(patch)})
      if(!res.ok)throw Error(await errorOf(res));await refresh()
    }catch(err){setMessage(err.message)}finally{setBusy(false)}
  }
  const editName=async target=>{
    const name=window.prompt(`Sửa họ tên của ${target.username}:`,target.full_name||'')
    if(name!==null && name.trim())await edit(target,{full_name:name.trim()})
  }
  const revoke=async target=>{
    if(!window.confirm(`Thu hồi tất cả phiên của ${target.username}?`))return
    setBusy(true);setMessage('')
    try{
      const res=await secureFetch(`/api/admin/users/${target.id}/revoke-sessions`,{method:'POST'})
      if(!res.ok)throw Error(await errorOf(res))
      setMessage(`Đã thu hồi các phiên của ${target.username}.`)
      await refresh()
    }catch(err){setMessage(err.message)}finally{setBusy(false)}
  }
  const reset=async target=>{
    const password=window.prompt(`Đặt mật khẩu tạm mới cho ${target.username} (12+ ký tự, chữ + số):`)
    if(password===null)return
    if(!window.confirm(`Thu hồi mọi phiên của ${target.username} và đặt mật khẩu tạm mới?`))return
    setBusy(true);setMessage('')
    try{
      const res=await secureFetch(`/api/admin/users/${target.id}/reset-password`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({new_password:password})})
      if(!res.ok)throw Error(await errorOf(res));setMessage('Đã đặt lại mật khẩu và thu hồi mọi phiên của tài khoản.');await refresh()
    }catch(err){setMessage(err.message)}finally{setBusy(false)}
  }
  return <section className="panel admin-panel" id="users">
    <div className="panel-head"><div><span className="panel-kicker">ADMIN ONLY</span><h2>Quản lý người dùng & phân quyền</h2></div><button onClick={refresh}>Làm mới</button></div>
    <div className="user-role-help">Admin: toàn quyền · Operator: camera, AI, benchmark, huấn luyện · Viewer: chỉ xem</div>
    <form className="user-form" onSubmit={create}>
      <label>Tên đăng nhập<input value={form.username} minLength={3} maxLength={80} required onChange={e=>setForm({...form,username:e.target.value})}/></label>
      <label>Họ tên<input value={form.full_name} maxLength={160} required onChange={e=>setForm({...form,full_name:e.target.value})}/></label>
      <label>Vai trò<select value={form.role} onChange={e=>setForm({...form,role:e.target.value})}><option value="viewer">Viewer</option><option value="operator">Operator</option><option value="admin">Admin</option></select></label>
      <label>Mật khẩu tạm<input type="password" autoComplete="new-password" value={form.password} minLength={12} maxLength={128} required onChange={e=>setForm({...form,password:e.target.value})}/></label>
      <button className="primary" disabled={busy}>+ Tạo tài khoản</button>
    </form>
    {message&&<div className="notice-banner">{message}</div>}
    <input className="user-search" placeholder="Tìm theo tên hoặc tài khoản..." value={search} onChange={e=>setSearch(e.target.value)}/>
    <div className="user-list">
      {users.filter(u=>(`${u.username} ${u.full_name||''}`).toLocaleLowerCase().includes(search.toLocaleLowerCase())).map(u=><div className="user-row" key={u.id}>
        <div><strong>{u.full_name || u.username}</strong><small>@{u.username} · #{u.id} · {u.is_active?'Hoạt động':'Đã khóa'} {u.must_change_password?'· Chờ đổi mật khẩu':''}</small></div>
        <select aria-label={`Quyền của ${u.username}`} disabled={busy || u.id===user.id} value={u.role} onChange={e=>edit(u,{role:e.target.value})}><option value="viewer">Viewer</option><option value="operator">Operator</option><option value="admin">Admin</option></select>
        <button disabled={busy || u.id===user.id} onClick={()=>edit(u,{is_active:!u.is_active})}>{u.is_active?'Khóa':'Mở khóa'}</button>
        <button disabled={busy} onClick={()=>editName(u)}>Sửa tên</button>
        <button disabled={busy} onClick={()=>reset(u)}>Đặt lại mật khẩu</button>
        <button disabled={busy} onClick={()=>revoke(u)}>Thu hồi phiên</button>
      </div>)}
    </div>
    <h3>Nhật ký thao tác gần đây</h3>
    <div className="security-audit-list">{audit.map(row=><div className="event-row" key={row.id}><span>{row.username||'Không xác định'} · {row.action}</span><small>{row.resource} · {row.outcome} · {new Date(row.created_at).toLocaleString('vi-VN')}</small></div>)}</div>
  </section>
}
