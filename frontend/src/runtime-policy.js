const componentLabels = {
  worker: 'Xử lý AI', resolver: 'Nối ID', primary: 'Vạch đếm',
  anchor_span: 'Quỹ đạo anchor', heavy_center: 'Tâm xe lớn',
  two_wheel_center: 'Tâm xe hai bánh', human_guard: 'Xác nhận người/xe',
  detector: 'Detector',
}
const statuses = new Set(['not_recorded', 'invalid', 'unavailable'])
const fieldName = /^_?[A-Za-z][A-Za-z0-9_]{0,95}$/
const digestPattern = /^[0-9a-f]{64}$/
const versionPattern = /^\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?(?:\+[A-Za-z0-9.-]+)?$/
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value)

export function policyFlagLabel(value) {
  return value === true ? 'Bật' : value === false ? 'Tắt' : 'Chưa ghi'
}

function emptyView(state) {
  const messages = {
    not_recorded: 'Phiên này chưa ghi cấu hình thực tế. Không dùng cấu hình hiện tại để thay thế.',
    invalid: 'Thông tin cấu hình không khớp hoặc không hợp lệ. Chưa thể dùng để đối chiếu.',
    unavailable: 'Chưa đọc được cấu hình đã ghi của phiên. Bạn có thể thử tải lại.',
  }
  return {state, available: false, message: messages[state], rows: [], runtimeVersion: null,
    sourceDigest: null, configurationDigest: null, missingCount: 0, absentCount: 0,
    captureStatus: null, endpointGuard: 'Chưa ghi', rescueGuard: 'Chưa ghi'}
}

function diagnosticFields(value) {
  return Array.isArray(value) && value.length <= 256 && value.every(item => {
    if (typeof item !== 'string' || item.length > 128) return false
    const parts = item.split('.')
    return parts.length === 2 && Object.hasOwn(componentLabels, parts[0]) && fieldName.test(parts[1])
  })
}

// Convert the historical API response into scalar display data only. The API
// verifies the recorded digest; the UI does not treat this as a whole-run proof.
export function runtimePolicyView(payload, expectedSessionId) {
  const expected = Number(expectedSessionId)
  if (!Number.isSafeInteger(expected) || expected <= 0 || !record(payload) ||
      payload.session_id !== expected || payload.metadata_verification !== 'prefix_only') return emptyView('invalid')
  if (payload.available === false) {
    return emptyView(statuses.has(payload.status) ? payload.status : 'invalid')
  }
  if (payload.available !== true || payload.status !== 'available') return emptyView('invalid')
  const policy = payload.policy
  if (!record(policy) || policy.schema_version !== 1 ||
      policy.digest_scope !== 'allowlisted_effective_algorithm_parameters' ||
      !['complete', 'partial'].includes(policy.capture_status) ||
      !record(policy.configuration) || !record(policy.component_presence) ||
      typeof policy.configuration_sha256 !== 'string' || !digestPattern.test(policy.configuration_sha256) ||
      !['missing_fields', 'invalid_fields', 'unreadable_fields'].every(key => diagnosticFields(policy[key]))) return emptyView('invalid')
  const presence = policy.component_presence
  if (Object.keys(presence).length !== Object.keys(componentLabels).length ||
      Object.keys(componentLabels).some(name => !['present', 'absent'].includes(presence[name]))) return emptyView('invalid')
  const rows = []
  for (const [component, fields] of Object.entries(policy.configuration)) {
    if (!Object.hasOwn(componentLabels, component) || presence[component] !== 'present' || !record(fields)) return emptyView('invalid')
    for (const [name, value] of Object.entries(fields)) {
      if (!fieldName.test(name)) return emptyView('invalid')
      const scalar = typeof value === 'boolean' || (typeof value === 'number' && Number.isFinite(value)) ||
        (name === 'detection_roi_mode' && ['full', 'road', 'gate'].includes(value))
      if (!scalar || rows.length >= 256) return emptyView('invalid')
      rows.push({component, group: componentLabels[component], name,
        value: typeof value === 'boolean' ? policyFlagLabel(value) : String(value)})
    }
  }
  if (Object.keys(componentLabels).some(name => presence[name] === 'present' && !Object.hasOwn(policy.configuration, name))) return emptyView('invalid')
  const runtime = payload.runtime
  if (runtime !== null && !record(runtime)) return emptyView('invalid')
  const version = runtime?.ai_runtime_version
  const sourceDigest = runtime?.worker_source_sha256
  if (version != null && (typeof version !== 'string' || version.length > 128 || !versionPattern.test(version))) return emptyView('invalid')
  if (sourceDigest != null && (typeof sourceDigest !== 'string' || !digestPattern.test(sourceDigest))) return emptyView('invalid')
  const missingCount = policy.missing_fields.length + policy.invalid_fields.length + policy.unreadable_fields.length
  const absentCount = Object.values(presence).filter(value => value === 'absent').length
  if (policy.capture_status === 'complete' && (missingCount > 0 ||
      ['worker', 'resolver', 'primary', 'detector'].some(name => presence[name] !== 'present'))) return emptyView('invalid')
  rows.sort((a, b) => a.component.localeCompare(b.component) || a.name.localeCompare(b.name))
  return {state: 'available', available: true, rows, runtimeVersion: version || null,
    sourceDigest: sourceDigest || null, configurationDigest: policy.configuration_sha256,
    captureStatus: policy.capture_status, missingCount, absentCount,
    message: policy.capture_status === 'complete' ? 'Đã ghi đủ các tham số trong danh sách.' : 'Một phần tham số chưa được ghi hoặc chưa đọc được.',
    endpointGuard: policyFlagLabel(policy.configuration.worker?._endpoint_precision_guard_enabled),
    rescueGuard: policyFlagLabel(policy.configuration.worker?._endpoint_rescue_guard_enabled)}
}

export function filterPolicyRows(rows, query) {
  const term = typeof query === 'string' ? query.trim().toLocaleLowerCase('vi') : ''
  return rows.filter(row => !term || `${row.group} ${row.name} ${row.value}`.toLocaleLowerCase('vi').includes(term))
}
