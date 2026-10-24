import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { safeError, stageLabel } from '../utils'
import { EmptyState, ErrorNotice, Loading, Panel } from './ui'

const activeDebateStates = new Set(['QUEUED', 'RUNNING'])
const list = value => Array.isArray(value) ? value : []

const debateStatusStyles = { QUEUED: 'badge-ghost', RUNNING: 'badge-info', COMPLETED: 'badge-success', DEGRADED: 'badge-warning', FAILED: 'badge-error', INTERRUPTED: 'badge-warning' }
const debateStatusLabels = { QUEUED: '排隊中', RUNNING: '辯論中', COMPLETED: '已完成', DEGRADED: '降級完成', FAILED: '失敗', INTERRUPTED: '已中斷' }
const severityStyles = { MINOR: 'badge-success', MODERATE: 'badge-warning', MAJOR: 'badge-error', FATAL: 'badge-error bg-red-900' }
const severityLabels = { MINOR: '輕微', MODERATE: '中等', MAJOR: '嚴重', FATAL: '致命' }
const stanceStyles = { AGREE: 'badge-success', QUALIFY: 'badge-warning', DISAGREE: 'badge-warning bg-orange-500', REFUTE: 'badge-error', WITHDRAW: 'badge-neutral' }
const stanceLabels = { AGREE: '同意', QUALIFY: '保留同意', DISAGREE: '反對', REFUTE: '駁斥', WITHDRAW: '撤回' }
const stopReasonLabels = { converged: '已收斂', max_rounds: '達到最大輪數', max_rounds_reached: '達到最大輪數', not_converged: '達到輪數上限仍未收斂', budget_exhausted: '調用預算耗盡', error: '因錯誤停止', interrupted: '已中斷' }

const label = value => value == null || value === '' ? '未知' : String(value)
const percentage = ratio => Math.max(0, Math.min(100, Math.round((Number(ratio) || 0) * 100)))
const confidence = value => Number.isFinite(Number(value)) ? `${Math.round(Number(value) * 100)}%` : '—'
const panelName = (panel, expertId) => list(panel).find(entry => entry.expert_id === expertId)?.lens || expertId

function EvidenceChips({ ids }) {
  if (!ids.length) return null
  return <details>
    <summary className="btn btn-ghost btn-xs cursor-pointer">證據 ×{ids.length}</summary>
    <div className="mt-2 flex flex-wrap gap-1">{ids.map(id => <span key={id} className="badge badge-outline badge-xs font-mono">{id}</span>)}</div>
  </details>
}

export default function DebateTimeline({ reviewId, runStatus }) {
  const [snapshot, setSnapshot] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState('')
  const [awaiting, setAwaiting] = useState(false)
  const [activeRound, setActiveRound] = useState(0)
  const sequence = useRef(0)
  const debatable = Boolean(runStatus) && !activeDebateStates.has(runStatus)

  const load = useCallback(async () => {
    const current = ++sequence.current
    setLoading(true)
    try {
      const value = await api.debate(reviewId)
      if (sequence.current === current) { setSnapshot(value); setAwaiting(false); setError('') }
    } catch (issue) {
      if (sequence.current !== current) return
      if (issue.status === 404) { setSnapshot(null); setError('') }
      else { setSnapshot(null); setError(safeError(issue)) }
    } finally { if (sequence.current === current) setLoading(false) }
  }, [reviewId])

  useEffect(() => { load(); setActiveRound(0) }, [load, runStatus])

  const active = awaiting || Boolean(snapshot && activeDebateStates.has(snapshot.status))
  useEffect(() => {
    if (!active) return
    const timer = window.setInterval(load, 3000)
    return () => window.clearInterval(timer)
  }, [active, load])

  const startDebate = async () => {
    setStarting(true); setStartError('')
    try {
      await api.runDebate(reviewId, { idempotency_key: `debate-${Date.now()}` })
      setAwaiting(true); setSnapshot(null)
      await load()
    } catch (issue) { setStartError(safeError(issue)) } finally { setStarting(false) }
  }

  const rounds = list(snapshot?.rounds).slice().sort((left, right) => left.round_number - right.round_number)
  const currentRound = rounds.find(round => round.round_number === activeRound) || rounds[0] || null
  const outcome = snapshot?.outcome
  const conflictCount = list(outcome?.conflict_opinion_ids).length
  const voteEntries = outcome ? Object.entries(outcome.vote_tally || {}) : []

  const jumpToOpinion = opinionId => {
    const round = rounds.find(entry => list(entry.opinions).some(opinion => opinion.id === opinionId))
    if (!round) return
    setActiveRound(round.round_number)
    window.setTimeout(() => document.getElementById(`opinion-${opinionId}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 120)
  }

  return <Panel title="多智能體辯論評審" description="專家團逐輪提出意見、交鋒並投票，收斂後給出被接納與衝突的結論。" actions={<button className="btn btn-outline btn-sm" disabled={loading} onClick={() => load()}>刷新</button>}>
    {error && <ErrorNotice error={error} onRetry={load} />}
    {loading && !snapshot && !error && <Loading label="正在加載辯論快照…" />}
    {!error && !snapshot && !loading && (debatable ? <div className="flex min-h-40 flex-col items-center justify-center rounded-xl border border-dashed border-soft px-5 py-8 text-center">
      <h3 className="text-sm font-semibold text-slate-200">暫無辯論記錄</h3>
      <p className="mt-1 max-w-lg text-sm leading-6 text-muted">評審運行已結束，可以召集專家團對本論文進行多智能體辯論評審。</p>
      <button className="btn btn-primary btn-sm mt-4" disabled={starting} onClick={startDebate}>{starting ? '正在啟動…' : '運行辯論'}</button>
      {startError && <div className="mt-3 w-full"><ErrorNotice error={startError} /></div>}
    </div> : <EmptyState title="暫無辯論" description="評審運行完成後，可以在這裡發起多智能體辯論評審。" />)}
    {snapshot && <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <span className={`badge badge-sm ${debateStatusStyles[label(snapshot.status)] || 'badge-ghost'}`}>{debateStatusLabels[label(snapshot.status)] || label(snapshot.status).replaceAll('_', ' ')}</span>
        {active && <span className="text-sm text-sky-300">辯論進行中，每 3 秒自動同步</span>}
        <span className="ml-auto flex items-center gap-2 text-sm text-muted"><span>調用預算</span><span className="font-mono text-slate-200">{snapshot.call_budget?.used ?? 0}/{snapshot.call_budget?.max ?? '—'}</span></span>
      </div>
      {outcome && <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <div className="mb-1 flex justify-between text-sm"><span className="text-muted">收斂一致性</span><span>{outcome.agreement_ratio != null ? `${percentage(outcome.agreement_ratio)}%` : '—'}</span></div>
          <progress className="progress progress-info h-2 w-full" value={percentage(outcome.agreement_ratio)} max="100" />
        </div>
        <div><span className="text-muted">衝突意見</span><div className="mt-1 text-sm">{conflictCount} 條</div></div>
        <div><span className="text-muted">運行輪數</span><div className="mt-1 text-sm">{outcome.rounds_run ?? list(rounds).length} 輪 · 收斂：{outcome.converged ? '是' : '否'}</div></div>
      </div>}
      {snapshot.stale && <div className="alert alert-warning text-sm">階段已重跑，辯論結果已過期，僅供參考。</div>}
      {snapshot.last_error && <div className="alert alert-error text-sm">{snapshot.last_error.message || '辯論運行出錯'} · <span className="font-mono text-xs">{snapshot.last_error.code || 'unknown'}</span></div>}
      {rounds.length ? <>
        <div role="tablist" className="tabs tabs-bordered">
          {rounds.map(round => <button key={round.round_number} role="tab" type="button" aria-selected={currentRound?.round_number === round.round_number} className={`tab ${currentRound?.round_number === round.round_number ? 'tab-active' : ''}`} onClick={() => setActiveRound(round.round_number)}>{round.round_number === 0 ? '第 0 輪 · 獨立意見' : `第 ${round.round_number} 輪 · 交鋒`}</button>)}
        </div>
        {currentRound && (() => {
          const opinions = list(currentRound.opinions), messages = list(currentRound.messages), rejected = list(currentRound.rejected)
          return <div role="tabpanel" className="space-y-3">
            {list(currentRound.speaker_order).length > 0 && <p className="text-xs text-muted">本輪發言順序：{currentRound.speaker_order.map(expertId => panelName(snapshot.panel, expertId)).join(' → ')}</p>}
            {currentRound.round_number === 0
              ? (opinions.length ? opinions.map(opinion =>
                <article id={`opinion-${opinion.id}`} key={opinion.id} className="rounded-xl border border-soft bg-slate-950/30 p-4">
                  <div className="flex flex-wrap items-center gap-2"><span className="badge badge-outline">{panelName(snapshot.panel, opinion.expert_id) || opinion.lens}</span><span className={`badge badge-sm ${severityStyles[opinion.severity] || 'badge-ghost'}`}>{severityLabels[opinion.severity] || label(opinion.severity)}</span><span className="ml-auto text-xs text-muted">置信度 {confidence(opinion.confidence)}</span></div>
                  <h3 className="mt-2 font-semibold text-slate-100">{opinion.title}</h3>
                  <p className="mt-1 text-xs text-muted">階段：{stageLabel(opinion.stage_id)} · 編號 <span className="font-mono">{opinion.id}</span></p>
                  {opinion.detail && <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">{opinion.detail}</p>}
                  <div className="mt-2"><EvidenceChips ids={list(opinion.evidence_ids)} /></div>
                </article>) : <EmptyState title="本輪沒有保留意見" description="專家團在本輪未產出可展示意見。" />)
              : (messages.length ? messages.map(message =>
                <article key={message.id} className="rounded-xl border border-soft bg-slate-950/30 p-4">
                  <div className="flex flex-wrap items-center gap-2"><span className="badge badge-outline">{panelName(snapshot.panel, message.expert_id)}</span><span className={`badge badge-sm ${stanceStyles[message.stance] || 'badge-ghost'}`}>{stanceLabels[message.stance] || label(message.stance)}</span><span className="text-xs text-muted">指向 <button className="btn btn-link btn-xs" onClick={() => jumpToOpinion(message.target_opinion_id)}>{message.target_opinion_id || '—'}</button></span><span className="ml-auto text-xs text-muted">置信度 {confidence(message.confidence)}</span></div>
                  {message.revised_title && <h3 className="mt-2 font-semibold text-slate-100">{message.revised_title}</h3>}
                  {message.rationale && <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">{message.rationale}</p>}
                  {list(message.evidence_ids).length > 0 && <p className="mt-2 text-xs text-muted">證據：{message.evidence_ids.join('、')}</p>}
                </article>) : <EmptyState title="本輪沒有保留發言" description="專家團在本輪未產出可展示發言。" />)}
            {rejected.length > 0 && <details className="rounded-xl border border-dashed border-soft p-3">
              <summary className="cursor-pointer text-xs text-muted">被拒發言（{rejected.length}）</summary>
              {rejected.map((entry, index) => <p key={entry.id || index} className="mt-2 text-xs text-rose-300/80">{panelName(snapshot.panel, entry.expert_id)} · <span className="font-mono">{entry.code || 'unknown'}</span> · {entry.message}</p>)}
            </details>}
          </div>
        })()}
      </> : <EmptyState title="辯論尚未產生輪次" description={active ? '辯論進行中，稍後會自動同步。' : '當前快照沒有可用的輪次記錄。'} />}
      {outcome && <div className="rounded-xl border border-soft bg-slate-950/30 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-semibold text-slate-100">辯論結論</h3><span className="badge badge-outline">{stopReasonLabels[outcome.stop_reason] || outcome.stop_reason || '—'}</span></div>
        <div className="mt-3 grid gap-4 lg:grid-cols-2">
          <div><span className="text-xs text-muted">被接納意見（{list(outcome.accepted_opinion_ids).length}）</span><ul className="mt-2 space-y-1">{list(outcome.accepted_opinion_ids).map(id => <li key={id} className="font-mono text-xs text-emerald-300">{id}</li>)}{!list(outcome.accepted_opinion_ids).length && <li className="text-xs text-muted">無</li>}</ul></div>
          <div><span className="text-xs text-muted">衝突意見（{conflictCount}）</span><ul className="mt-2 space-y-1">{list(outcome.conflict_opinion_ids).map(id => <li key={id} className="font-mono text-xs text-rose-300">{id}</li>)}{!conflictCount && <li className="text-xs text-muted">無</li>}</ul></div>
        </div>
        {voteEntries.length > 0 && <div className="mt-3"><span className="text-xs text-muted">投票權重（vote_tally）</span><div className="mt-2 flex flex-wrap gap-2">{voteEntries.map(([opinionId, weight]) => <span key={opinionId} className="badge badge-outline badge-sm font-mono">{opinionId} · {weight}</span>)}</div></div>}
      </div>}
    </div>}
  </Panel>
}
