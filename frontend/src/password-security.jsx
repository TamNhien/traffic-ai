import React, {useId, useState} from 'react'

// UI feedback only. The backend must independently enforce the same policy.
export function passwordChecks(value) {
  const length = Array.from(value).length
  const bytes = new TextEncoder().encode(value).length
  const checks = [
    {name: 'Từ 12 đến 128 ký tự', valid: length >= 12 && length <= 128},
    {name: 'Có chữ hoa (A–Z)', valid: /\p{Lu}/u.test(value)},
    {name: 'Có chữ thường (a–z)', valid: /\p{Ll}/u.test(value)},
    {name: 'Có chữ số (0–9)', valid: /\p{Nd}/u.test(value)},
    {name: 'Có ký tự đặc biệt (!, @, #, …)', valid: /[\p{P}\p{S}]/u.test(value)},
  ]
  const valid = checks.every(check => check.valid) && bytes <= 512
  // An approximate, deliberately conservative UI indicator, not an entropy guarantee.
  const passed = checks.filter(check => check.valid).length
  const strength = !value ? 0 : !valid ? 1 : length >= 16 ? 3 : 2
  return {valid, checks, strength, bytesValid: bytes <= 512, passed}
}

export function PasswordPolicy({value}) {
  const {valid, checks, strength, bytesValid} = passwordChecks(value)
  const labels = ['Chưa nhập', 'Yếu', 'Trung bình', 'Mạnh']
  return <div className="password-policy" aria-live="polite">
    <div className="password-meter-head"><span>Độ mạnh mật khẩu (ước tính)</span><strong className={`strength-${strength}`}>{labels[strength]}</strong></div>
    <div className={`password-meter strength-${strength}`} role="progressbar" aria-label="Độ mạnh mật khẩu" aria-valuemin={0} aria-valuemax={3} aria-valuenow={strength}>
      <span style={{width: `${strength * 100 / 3}%`}} />
    </div>
    <div className="password-requirements" aria-label="Điều kiện mật khẩu">
      {checks.map(check => <div key={check.name} className={check.valid?'requirement-ok':'requirement-pending'}>
        <span aria-hidden="true">{check.valid?'✓':'○'}</span>{check.name}
      </div>)}
      {!bytesValid && <div className="requirement-pending">○ Tối đa 512 byte UTF-8</div>}
    </div>
    {value && valid && <small className="password-policy-ok">✓ Đáp ứng đầy đủ yêu cầu mật khẩu.</small>}
  </div>
}

export function PasswordField({label, value, onChange, autoComplete='new-password', showPolicy=false, required=true, minLength, maxLength, disabled=false}) {
  const id = useId()
  const [visible, setVisible] = useState(false)
  return <div className="password-field">
    <label htmlFor={id}>{label}</label>
    <div className="password-input-wrap">
      <input id={id} type={visible?'text':'password'} value={value} onChange={onChange}
        autoComplete={autoComplete} autoCapitalize="off" spellCheck={false}
        required={required} minLength={minLength} maxLength={maxLength} disabled={disabled} />
      <button type="button" className="password-visibility" onClick={()=>setVisible(current=>!current)}
        aria-label={`${visible?'Ẩn':'Hiện'} ${label.toLocaleLowerCase('vi-VN')}`}
        title={visible?'Ẩn mật khẩu':'Hiện mật khẩu'} aria-pressed={visible} disabled={disabled}>
        {visible ? <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 3l18 18M10.6 10.7a2 2 0 002.7 2.7"/><path d="M9.9 5.3A10.6 10.6 0 0112 5c5.1 0 8.5 4.1 9.5 7-.4 1.1-1.3 2.3-2.4 3.4M6.3 6.4C4.4 7.8 3 9.8 2.5 12c1 2.9 4.4 7 9.5 7a10 10 0 004.1-.8"/></svg>
          : <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M2.5 12S6 5 12 5s9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7Z"/><circle cx="12" cy="12" r="3"/></svg>}
      </button>
    </div>
    {showPolicy && <PasswordPolicy value={value}/>}
  </div>
}
