function releaseVersion(value) {
  if (typeof value !== 'string') return null
  const version = value.trim()
  if (version.length > 128 || !/^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/.test(version)) return null
  return version
}

function record(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

// Keep the loaded UI build distinct from the currently responding AI service.
// Missing, unavailable or malformed health responses are unknown, not drift.
export function runtimeReleaseStatus(uiVersion, systemStatus) {
  const ui = releaseVersion(uiVersion)
  const ai = record(systemStatus) && record(systemStatus.ai) ? systemStatus.ai : null
  const aiReady = systemStatus?.ai_service === 'ready' && ai?.status === 'ready' && ai?.service === 'ai-service'
  const aiVersion = aiReady ? releaseVersion(ai.version) : null
  return {
    uiVersion: ui,
    aiVersion,
    aiReady,
    state: ui && aiVersion ? (ui === aiVersion ? 'matching' : 'mismatch') : 'unknown',
  }
}
