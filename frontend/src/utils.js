export const STAGES = [
  { id: 'problem_identification', label: '问题识别', weight: .15 },
  { id: 'problem_formulation', label: '问题表述', weight: .15 },
  { id: 'assumptions', label: '假设建立', weight: .15 },
  { id: 'model_construction', label: '模型构造', weight: .20 },
  { id: 'solving', label: '模型求解', weight: .10 },
  { id: 'code_implementation', label: '代码实现', weight: .15 },
  { id: 'results_analysis', label: '结果分析', weight: .10 },
]
export const stageLabel = value => STAGES.find(stage => stage.id === value)?.label || value || '尚未开始'
function parsedDate(value) {
  const text = String(value)
  // SQLite stores UTC timestamps without an offset for ReviewJob rows.
  return new Date(/^\d{4}-\d\d-\d\dT/.test(text) && !/(Z|[+-]\d\d:\d\d)$/i.test(text) ? text + 'Z' : text)
}
export function dateTime(value) {
  if (!value) return '—'
  const date = parsedDate(value)
  return Number.isNaN(date.valueOf()) ? '—' : date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
}
export function dateKey(value) {
  if (!value) return ''
  const date = parsedDate(value)
  return Number.isNaN(date.valueOf()) ? '' : date.toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' })
}
export const safeError = error => error?.message || (typeof error === 'string' ? error : '操作失败，请重试。')
export const navigate = path => { window.location.hash = path }
export const key = () => globalThis.crypto?.randomUUID?.() || `run-${Date.now()}-${Math.random().toString(36).slice(2)}`

export async function prepareReview(client, job, { confirmed, reason }) {
  if (!confirmed || !reason?.trim()) throw new Error('请先明确确认评审输入并填写确认理由。')
  let current = await client.review(job.id)
  const steps = { CREATED: 'INGESTING', INGESTING: 'ASSETS_FROZEN', ASSETS_FROZEN: 'RUBRIC_CONFIRMATION', RUBRIC_CONFIRMATION: 'EVALUATING' }
  while (steps[current.state]) {
    const target = steps[current.state]
    const body = { target, reason: reason.trim() }
    if (target === 'ASSETS_FROZEN') body.assets_frozen = true
    if (target === 'EVALUATING') { body.rubric_published = true; body.human_confirmed = confirmed }
    current = await client.transitionReview(current.id, body)
  }
  return current
}
