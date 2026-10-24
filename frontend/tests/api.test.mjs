import test from 'node:test'
import assert from 'node:assert/strict'
import { api, modelPayload, recommendationPayload } from '../src/api.js'
import { dateKey, dateTime, prepareReview, STAGES } from '../src/utils.js'

test('configuration and recommendation payloads exclude UI-only fields', async () => {
  const model = modelPayload({ provider: 'custom', base_url: 'https://example.test/v1', api_key: 'test-key', model: 'm', is_active: true, custom_provider: 'extra' })
  assert.deepEqual(Object.keys(model), ['provider', 'base_url', 'api_key', 'model', 'is_active'])
  const body = recommendationPayload({ id: 'r1', finding_id: 'f1', evidence_ids: ['e1'], action: 'Act', acceptance: 'Verify', decided_by: 'human', rationale: 'Checked', priority: 'major', owner: 'Author' })
  assert.deepEqual(Object.keys(body), ['action', 'acceptance', 'priority', 'owner', 'decided_by', 'rationale'])
  assert.equal(body.priority, 'major')
})

test('requests send exact bodies and expose readable errors without response details', async () => {
  let captured
  const original = globalThis.fetch
  globalThis.fetch = async (path, options) => { captured = { path, options }; return new Response(JSON.stringify({ id: 'config1', api_key_configured: true }), { status: 201 }) }
  try {
    await api.saveConfig({ provider: 'custom', base_url: 'http://local/v1', model: 'm', is_active: true, custom_provider: 'should-drop' })
    assert.equal(captured.path, '/api/v1/model-config')
    assert.equal(JSON.parse(captured.options.body).custom_provider, undefined)
    globalThis.fetch = async () => new Response(JSON.stringify({ error: { code: 'parse_failed', message: '无法解析', details: { private_path: 'hidden' } } }), { status: 422 })
    await assert.rejects(api.assets(), error => error.status === 422 && error.code === 'parse_failed' && error.message === '无法解析' && !error.details)
  } finally { globalThis.fetch = original }
})

test('review preparation refuses missing human confirmation without calling API', async () => {
  const client = { review: () => { throw new Error('should not call') } }
  await assert.rejects(prepareReview(client, { id: 'r' }, { confirmed: false, reason: 'Checked' }), /确认/)
})

test('review preparation resumes from persisted state rather than recreating input', async () => {
  const transitions = []
  const client = {
    review: async () => ({ id: 'r1', state: 'ASSETS_FROZEN' }),
    transitionReview: async (id, body) => { transitions.push(body); return { id, state: body.target } }
  }
  const final = await prepareReview(client, { id: 'r1', state: 'CREATED' }, { confirmed: true, reason: 'Human checked' })
  assert.equal(final.state, 'EVALUATING')
  assert.deepEqual(transitions.map(item => item.target), ['RUBRIC_CONFIRMATION', 'EVALUATING'])
  assert.equal(transitions[1].human_confirmed, true)
  assert.equal(transitions[1].reason, 'Human checked')
  assert.equal(STAGES.length, 7)
  assert.ok(Math.abs(STAGES.reduce((total, stage) => total + stage.weight, 0) - 1) < 1e-9)
})

test('report downloads use Blob with explicit filename and clean up URL', async () => {
  const original = { fetch: globalThis.fetch, document: globalThis.document, create: URL.createObjectURL, revoke: URL.revokeObjectURL, timer: globalThis.setTimeout }
  const anchor = { click() { this.clicked = true }, remove() { this.removed = true } }
  let revoked
  globalThis.fetch = async () => new Response('# Report', { status: 200 })
  globalThis.document = { createElement: () => anchor, body: { appendChild() {} } }
  URL.createObjectURL = () => 'blob:test'
  URL.revokeObjectURL = value => { revoked = value }
  globalThis.setTimeout = callback => { callback() }
  try {
    await api.downloadReport('review-1', 'md')
    assert.equal(anchor.download, 'review-review-1.md')
    assert.equal(anchor.clicked, true); assert.equal(anchor.removed, true); assert.equal(revoked, 'blob:test')
  } finally { globalThis.fetch = original.fetch; globalThis.document = original.document; URL.createObjectURL = original.create; URL.revokeObjectURL = original.revoke; globalThis.setTimeout = original.timer }
})

test('debate snapshot and run endpoints send exact request shapes', async () => {
  const calls = []
  const original = globalThis.fetch
  globalThis.fetch = async (path, options) => {
    calls.push({ path, options })
    return path.endsWith('/debate/run')
      ? new Response(JSON.stringify({ review_id: 'review-1', debate_status: 'QUEUED', idempotency_key: 'debate-1' }), { status: 202 })
      : new Response(JSON.stringify({ review_id: 'review-1', status: 'RUNNING', rounds: [] }), { status: 200 })
  }
  try {
    const snapshot = await api.debate('review-1')
    assert.equal(calls[0].path, '/api/v1/reviews/review-1/debate')
    assert.equal(calls[0].options.method, undefined)
    assert.equal(snapshot.status, 'RUNNING')
    const ack = await api.runDebate('review-1', { idempotency_key: 'debate-1', max_rounds: 2 })
    assert.equal(calls[1].path, '/api/v1/reviews/review-1/debate/run')
    assert.equal(calls[1].options.method, 'POST')
    assert.deepEqual(JSON.parse(calls[1].options.body), { idempotency_key: 'debate-1', max_rounds: 2 })
    assert.equal(ack.debate_status, 'QUEUED')
  } finally { globalThis.fetch = original }
})

test('debate snapshot without record surfaces status 404 so callers can treat it as empty', async () => {
  const original = globalThis.fetch
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: '暫無辯論記錄' }), { status: 404 })
  try {
    await assert.rejects(api.debate('review-1'), error => error.status === 404)
  } finally { globalThis.fetch = original }
})

test('naive SQLite UTC timestamps use Shanghai dates consistently', () => {
  assert.equal(dateKey('2026-10-07T20:00:00'), '2026-10-08')
  assert.equal(dateTime('2026-10-07T20:00:00'), dateTime('2026-10-07T20:00:00Z'))
})
