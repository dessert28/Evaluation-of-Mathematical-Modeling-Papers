export class ApiError extends Error {
  constructor(message, status, code) { super(message); this.status = status; this.code = code }
}

function apiUrl(path) {
  const base = globalThis.__DESKTOP_API_BASE__
  return base ? `${base.replace(/\/$/, '')}${path}` : path
}

function apiHeaders(headers = {}) {
  const token = globalThis.__DESKTOP_SESSION_TOKEN__
  return token ? { ...headers, 'X-Desktop-Token': token } : headers
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(apiUrl(path), { ...options, headers: apiHeaders({ ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(options.headers || {}) }) })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError('无法连接本地服务，请检查后端是否运行。', 0, 'network_error')
  }
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const issue = payload.error || payload.detail?.error
    throw new ApiError(issue?.message || `请求失败（HTTP ${response.status}），请检查填写内容。`, response.status, issue?.code || 'request_failed')
  }
  return payload
}

const json = (method, body) => ({ method, body: JSON.stringify(body) })
const id = value => encodeURIComponent(value)
const reviewPath = value => `/api/v1/reviews/${id(value)}`

export function modelPayload(body) {
  return { provider: body.provider, base_url: body.base_url, api_key: body.api_key || '', model: body.model, is_active: Boolean(body.is_active) }
}
export function recommendationPayload(body) {
  return { action: body.action, acceptance: body.acceptance, priority: body.priority || 'minor', owner: body.owner || null, decided_by: body.decided_by, rationale: body.rationale }
}

export const api = {
  health: () => request('/health'),
  configs: () => request('/api/v1/model-config'),
  saveConfig: (body, configId) => request(configId ? `/api/v1/model-config/${id(configId)}` : '/api/v1/model-config', json(configId ? 'PUT' : 'POST', modelPayload(body))),
  testConfig: configId => request(`/api/v1/model-config/${id(configId)}/test`, { method: 'POST' }),
  deleteConfig: configId => request(`/api/v1/model-config/${id(configId)}`, { method: 'DELETE' }),
  assets: () => request('/api/v1/assets'),
  asset: assetId => request(`/api/v1/assets/${id(assetId)}`),
  blocks: assetId => request(`/api/v1/assets/${id(assetId)}/blocks`),
  uploadAsset: file => { const form = new FormData(); form.append('file', file); return request('/api/v1/assets', { method: 'POST', body: form }) },
  rubrics: () => request('/api/v1/rubrics'),
  rubric: rubricId => request(`/api/v1/rubrics/${id(rubricId)}`),
  importRubric: body => request('/api/v1/rubrics/import', json('POST', body)),
  importRubricFile: file => { const form = new FormData(); form.append('file', file); return request('/api/v1/rubrics/import', { method: 'POST', body: form }) },
  updateRubric: (rubricId, body) => request(`/api/v1/rubrics/${id(rubricId)}`, json('PUT', body)),
  publishRubric: (rubricId, body) => request(`/api/v1/rubrics/${id(rubricId)}/publish`, json('POST', body)),
  reviews: () => request('/api/v1/reviews'),
  review: reviewId => request(reviewPath(reviewId)),
  createReview: body => request('/api/v1/reviews', json('POST', body)),
  transitionReview: (reviewId, body) => request(`${reviewPath(reviewId)}/transition`, json('POST', body)),
  runReview: (reviewId, body) => request(`${reviewPath(reviewId)}/run`, json('POST', body)),
  runStage: (reviewId, stage, body) => request(`${reviewPath(reviewId)}/stages/${id(stage)}/run`, json('POST', body)),
  progress: reviewId => request(`${reviewPath(reviewId)}/progress`),
  result: reviewId => request(`${reviewPath(reviewId)}/result`),
  evidence: (reviewId, evidenceId) => request(`${reviewPath(reviewId)}/evidence/${id(evidenceId)}`),
  editRecommendation: (reviewId, recommendationId, body) => request(`${reviewPath(reviewId)}/recommendations/${id(recommendationId)}`, json('PUT', recommendationPayload(body))),
  downloadReport: async (reviewId, format) => {
    if (!['md', 'json'].includes(format)) throw new Error('不支持的报告格式')
    const response = await fetch(apiUrl(`${reviewPath(reviewId)}/report?format=${format}`), { headers: apiHeaders() })
    if (!response.ok) throw new ApiError('报告暂不可下载，请刷新结果后重试。', response.status, 'report_download_failed')
    const url = URL.createObjectURL(await response.blob())
    const anchor = document.createElement('a')
    anchor.href = url; anchor.download = `review-${reviewId}.${format}`
    document.body.appendChild(anchor); anchor.click(); anchor.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
}
