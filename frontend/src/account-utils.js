// Keep frontend validation aligned with backend/app/usernames.py.
export function usernameProblem(raw) {
  const username = String(raw || '').trim().normalize('NFC')
  if (!username) return 'Hãy nhập tên đăng nhập.'
  const key = username.toLocaleLowerCase('und')
  if ([...username].length < 3 || [...username].length > 80 || [...key].length > 80)
    return 'Tên đăng nhập phải từ 3 đến 80 ký tự.'
  if (/^[_.-]|[_.-]$/.test(username)) return 'Tên đăng nhập phải bắt đầu và kết thúc bằng chữ hoặc số.'
  // Every combining mark must follow a letter/mark. NFC covers common Vietnamese.
  if (!/^[\p{L}\p{N}_.-][\p{L}\p{N}\p{M}_.-]*$/u.test(username))
    return 'Chỉ dùng chữ tiếng Việt, số, dấu chấm, gạch nối và gạch dưới; không có khoảng trắng.'
  for (let i=0; i<username.length; i++) {
    if (/\p{M}/u.test(username[i]) && (i===0 || !/[\p{L}\p{M}]/u.test(username[i-1])))
      return 'Dấu tiếng Việt phải đi cùng chữ cái.'
  }
  return ''
}

const fieldLabels = {username: 'Tên đăng nhập',full_name: 'Họ tên',role: 'Vai trò',password: 'Mật khẩu',new_password:'Mật khẩu mới',current_password:'Mật khẩu hiện tại',is_active:'Trạng thái tài khoản'}
export function readableApiDetail(detail, status) {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const messages = detail.filter(item => item && typeof item === 'object').map(item => {
      const field = Array.isArray(item.loc) ? item.loc[item.loc.length-1] : ''
      const label = fieldLabels[field] || 'Dữ liệu'
      const msg = typeof item.msg === 'string' ? item.msg.replace(/^Value error,\s*/i,'') : 'không hợp lệ'
      if (field === 'username' && (item.type === 'string_pattern_mismatch' || item.type === 'value_error'))
        return `Tên đăng nhập: ${msg}`
      return `${label}: ${msg}`
    })
    if (messages.length) return messages.join(' · ')
  }
  if (detail && typeof detail === 'object') return 'Yêu cầu không hợp lệ. Vui lòng kiểm tra thông tin nhập.'
  if (status === 409) return 'Tên đăng nhập đã tồn tại.'
  if (status === 403) return 'Không đủ quyền thực hiện thao tác này.'
  if (status === 401) return 'Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại.'
  return `Không thể thực hiện yêu cầu (HTTP ${status}).`
}
