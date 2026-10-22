import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { STAGES, dateTime, key, prepareReview, safeError } from '../utils'
import { Drawer, EmptyState, ErrorNotice, Loading, Modal, PageHeader, Panel, StatusBadge } from '../components/ui'
import EvidenceIndex from '../components/EvidenceIndex'

const activeStates = new Set(['QUEUED', 'RUNNING'])
const list = value => Array.isArray(value) ? value : []

export default function ReviewDetail({ id, reviewId }) {
  const reviewKey = id || reviewId
  const [job, setJob] = useState(null), [progress, setProgress] = useState(null), [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true), [error, setError] = useState(''), [resultError, setResultError] = useState('')
  const [evidence, setEvidence] = useState(null), [evidenceData, setEvidenceData] = useState(null), [evidenceError, setEvidenceError] = useState('')
  const [rerun, setRerun] = useState(null), [reason, setReason] = useState(''), [busy, setBusy] = useState(false), [actionError, setActionError] = useState('')
  const [edit, setEdit] = useState(null), [editForm, setEditForm] = useState({}), [audit, setAudit] = useState(null)
  const [pollEpoch, setPollEpoch] = useState(0)
  const [resumeOpen, setResumeOpen] = useState(false), [resumeReason, setResumeReason] = useState(''), [resumeConfirmed, setResumeConfirmed] = useState(false)
  const evidenceSequence = useRef(0)
  const [inputs, setInputs] = useState(null)
  useEffect(() => {
    if (!job) return
    let alive = true
    Promise.all([api.asset(job.asset_id), api.rubric(job.rubric_profile_id)])
      .then(([asset, rubric]) => { if (alive) setInputs({ asset, rubric }) })
      .catch(() => { if (alive) setInputs(null) })
    return () => { alive = false }
  }, [job?.asset_id, job?.rubric_profile_id])
  const refresh = useCallback(async () => {
    try { const [nextJob, nextProgress] = await Promise.all([api.review(reviewKey), api.progress(reviewKey)]); setJob(nextJob); setProgress(nextProgress); setError(''); return { nextJob, nextProgress } }
    catch (err) { setError(safeError(err)); return null }
  }, [reviewKey])
  const refreshResult = useCallback(async () => {
    try { const next = await api.result(reviewKey); setResult(next); setResultError(''); return next }
    catch (err) { setResult(null); setResultError(err.status === 404 ? '' : safeError(err)); return null }
  }, [reviewKey])
  useEffect(() => {
    let alive = true, previousStage = null, timer = null
    const tick = async () => {
      try {
        const [nextJob, nextProgress] = await Promise.all([api.review(reviewKey), api.progress(reviewKey)])
        if (!alive) return
        setJob(nextJob); setProgress(nextProgress); setError(''); setLoading(false)
        const stage = nextProgress.current_stage || nextJob.state
        const terminal = Boolean(nextProgress.run_status) && !activeStates.has(nextProgress.run_status)
        if (stage !== previousStage || terminal) { previousStage = stage; await api.result(reviewKey).then(value => { if (alive) { setResult(value); setResultError('') } }).catch(err => { if (alive) { setResult(null); setResultError(err.status === 404 ? '' : safeError(err)) } }) }
        if (alive && (!nextProgress.run_status || !terminal)) timer = window.setTimeout(tick, 3000)
      } catch (err) { if (alive) { setError(safeError(err)); setLoading(false); timer = window.setTimeout(tick, 3000) } }
    }
    tick()
    return () => { alive = false; window.clearTimeout(timer) }
  }, [reviewKey, pollEpoch])
  const run = progress || job?.state_snapshot?.run || {}
  const active = activeStates.has(run.run_status)
  const stages = list(STAGES)
  const findings = list(result?.findings)
  const [severity, setSeverity] = useState('')
  const visibleFindings = useMemo(() => findings.filter(item => !severity || item.severity === severity), [findings, severity])
  const evidenceById = useMemo(() => new Map(list(result?.evidence).map(item => [item.id, item])), [result])
  const recommendations = list(result?.recommendations)
  const snapshotStale = Boolean(job?.state_snapshot?.stale || list(job?.state_snapshot?.stale_dependencies).length || Object.values(job?.state_snapshot?.stage_stale || {}).some(Boolean))

  const openEvidence = async item => {
    const sequence = ++evidenceSequence.current
    setEvidence(item); setEvidenceData(null); setEvidenceError('')
    try { const detail = await api.evidence(reviewKey, item.id); let blocks = []
      if (detail.asset_id && detail.block_id) blocks = await api.blocks(detail.asset_id)
      const block = list(blocks).find(value => value.block_id === detail.block_id)
      if (sequence === evidenceSequence.current) setEvidenceData({ ...detail, document_block: detail.document_block || block || null })
    } catch (err) { if (sequence === evidenceSequence.current) setEvidenceError(safeError(err)) }
  }

  const startStageRerun = async () => {
    if (!rerun || reason.trim().length < 3) return
    setBusy(true); setActionError('')
    try { const started = await api.runStage(reviewKey, rerun.id, { reason: reason.trim(), idempotency_key: key() }); setProgress(started); setPollEpoch(value => value + 1); setRerun(null); setReason(''); await refresh(); await refreshResult() }
    catch (err) { setActionError(safeError(err)) } finally { setBusy(false) }
  }
  const continueRun = async () => {
    if (!resumeConfirmed || resumeReason.trim().length < 3) return
    setBusy(true); setActionError('')
    try {
      let current = job
      if (['CREATED', 'INGESTING', 'ASSETS_FROZEN', 'RUBRIC_CONFIRMATION'].includes(job.state)) current = await prepareReview(api, job, { confirmed: true, reason: resumeReason.trim() })
      const started = await api.runReview(current.id, { idempotency_key: key() }); setJob(current); setProgress(started); setPollEpoch(value => value + 1); setResumeOpen(false); setResumeConfirmed(false); setResumeReason(''); await refresh()
    } catch (err) { setActionError(safeError(err)) } finally { setBusy(false) }
  }
  const saveRecommendation = async () => {
    if (!edit || !editForm.action?.trim() || !editForm.acceptance?.trim() || !editForm.rationale?.trim()) return
    setBusy(true); setActionError('')
    try { const updated = await api.editRecommendation(reviewKey, edit.id, { ...editForm, decided_by: 'human' }); setAudit(updated); setEdit(null); await refreshResult() }
    catch (err) { setActionError(safeError(err)) } finally { setBusy(false) }
  }
  const download = async format => { try { await api.downloadReport(reviewKey, format) } catch (err) { setActionError(safeError(err)) } }

  if (loading) return <Loading label="正在加载评审任务…" />
  return <div className="space-y-6">
    <PageHeader title="评审任务详情" description={`${reviewKey} · 创建于 ${dateTime(job?.created_at)}`} actions={<><button className="btn btn-outline btn-sm" onClick={() => download('md')}>下载 Markdown</button><button className="btn btn-outline btn-sm" onClick={() => download('json')}>下载 JSON</button></>} />
    {error && <ErrorNotice error={error} onRetry={refresh} />}{actionError && <ErrorNotice error={actionError} onRetry={() => setActionError('')} />}
    {job && <div className="grid gap-6 xl:grid-cols-[.85fr_1.15fr]">
      <Panel title="任务状态" description="生命周期与异步运行状态分开显示。">
        <div className="flex flex-wrap items-center gap-3"><StatusBadge value={job.state} /><StatusBadge value={run.run_status || '未启动'} />{active && <span className="text-sm text-sky-300">每 3 秒同步进度</span>}</div>
        {job.state === 'EVIDENCE_AUDIT' && <div className="alert alert-info mt-4 text-sm">七阶段已完成，待证据审计</div>}
        {run.last_error && <div className="alert alert-error mt-4 text-sm">{run.last_error.message || '阶段运行失败'} · {list(run.failed_stages).join(', ')}</div>}
        {(job.state === 'CREATED' || job.state === 'INGESTING' || job.state === 'ASSETS_FROZEN' || job.state === 'RUBRIC_CONFIRMATION' || (['EVALUATING', 'DEGRADED'].includes(job.state) && !active)) && <button className="btn btn-primary mt-4" onClick={() => setResumeOpen(true)}>{['CREATED','INGESTING','ASSETS_FROZEN','RUBRIC_CONFIRMATION'].includes(job.state) ? '继续确认并启动' : '继续七阶段运行'}</button>}
        <dl className="mt-5 grid grid-cols-2 gap-4 text-sm"><div><dt className="text-muted">论文资产</dt><dd className="mt-1 break-all">{inputs?.asset.filename || job.asset_id}</dd></div><div><dt className="text-muted">量表</dt><dd className="mt-1 break-all">{inputs?.rubric ? `${inputs.rubric.name} · ${inputs.rubric.version}` : job.rubric_profile_id}</dd></div><div><dt className="text-muted">输入快照</dt><dd className="mt-1 break-all font-mono text-xs">{job.input_snapshot_hash}</dd></div><div><dt className="text-muted">已完成阶段</dt><dd className="mt-1">{list(run.completed_stages).length}/7</dd></div></dl>
      </Panel>
      <Panel title="七阶段进度" description="重跑会使该阶段及依赖结果标记 stale，并要求填写原因。">
        <div className="space-y-3">{stages.map(stage => {
          const done = list(run.completed_stages).includes(stage.id), failed = list(run.failed_stages).includes(stage.id), current = run.current_stage === stage.id
          const stageRun = run.stage_runs?.[stage.id] || {}, stale = job.state_snapshot?.stage_stale?.[stage.id]
          return <div key={stage.id} className="rounded-xl border border-soft p-3"><div className="flex flex-wrap items-center gap-2"><strong className="text-sm text-slate-100">{stage.label}</strong><span className="text-xs text-muted">{Math.round(stage.weight * 100)}%</span><div className="ml-auto flex items-center gap-2"><StatusBadge value={stale ? 'stale' : failed ? 'failed' : done ? 'completed' : current ? 'running' : '等待中'} /><button className="btn btn-ghost btn-xs" disabled={active} onClick={() => { setRerun(stage); setReason(''); setActionError('') }}>重跑</button></div></div><progress className="progress progress-info mt-2 h-1.5" value={done && !stale ? 100 : 0} max="100" /><div className="mt-1 text-xs text-muted">{stageRun.error?.message || stageRun.error_code || stageRun.status || ''}</div></div>
        })}</div>
      </Panel>
    </div>}
    {resultError && <ErrorNotice error={resultError} onRetry={refreshResult} />}
    {!result && !resultError && <Panel title="评审结果"><EmptyState title="结果尚未生成" description="任务启动后会逐阶段保存部分结果；等待阶段完成或稍后刷新。" /></Panel>}
    {result && <>
      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="通用诊断" description="七阶段诊断分轨展示。部分阶段未完成时不计算正式总分。">
          {list(result.diagnostic_scores).length ? <div className="space-y-4">{stages.map(stage => { const score = result.diagnostic_scores.find(item => item.criterion === stage.id); return <div key={stage.id}><div className="mb-1 flex justify-between text-sm"><span>{stage.label}</span><span>{score ? `${score.raw_score_0_10}/10` : '待评'} · {Math.round(stage.weight * 100)}%</span></div><div className="h-2 overflow-hidden rounded bg-slate-800"><div className="h-full rounded bg-sky-400" style={{ width: `${Math.max(0, Math.min(100, score?.raw_score_0_10 * 10 || 0))}%` }} /></div>{score?.score_rationale && <p className="mt-1 text-xs text-muted">{score.score_rationale}</p>}</div>})}
            {run.diagnostic_total_status === 'complete' && Number.isFinite(run.diagnostic_total) && !snapshotStale ? <div className="rounded-xl bg-sky-400/10 p-3 text-sm text-sky-100">七阶段总分：{run.diagnostic_total.toFixed(1)} / 100</div> : <div className="text-sm text-muted">{snapshotStale ? '存在 stale 输入或阶段依赖，不显示正式总分。' : '阶段尚未全部有效完成，不显示正式总分。'}</div>}</div> : <EmptyState title="暂无通用诊断评分" description="服务端尚未保存阶段评分。" />}
        </Panel>
        <Panel title="官方评分" description="严格按任务绑定的已发布量表显示，不与通用诊断合并。">
          {list(result.official_scores).length ? <div className="overflow-x-auto"><table className="table table-sm"><thead><tr><th>评分项</th><th>得分</th><th>权重</th><th>依据</th></tr></thead><tbody>{result.official_scores.map(score => <tr key={score.id}><td>{score.criterion}</td><td>{score.raw_score_0_10}</td><td>{score.weight}</td><td>{list(score.evidence_ids).map(id => <button key={id} className="btn btn-link btn-xs" onClick={() => evidenceById.has(id) && openEvidence(evidenceById.get(id))}>{id}</button>)}</td></tr>)}</tbody></table></div> : <EmptyState title="暂无官方评分" description="当前结果没有已保存的官方评分项。" />}
        </Panel>
      </div>
      <EvidenceIndex result={result} onEvidence={openEvidence} />
      <Panel title="问题与证据" description="选择问题可查看关联主张和证据；无法稳定定位的证据会显示待人工核实。" actions={<select className="select select-bordered select-sm bg-slate-950/60" value={severity} onChange={event => setSeverity(event.target.value)} aria-label="筛选问题严重度"><option value="">全部严重度</option><option value="fatal">fatal</option><option value="major">major</option><option value="minor">minor</option></select>}>
        {!visibleFindings.length ? <EmptyState title="暂无问题记录" description="没有真实 Finding 可展示。" /> : <div className="grid gap-3 lg:grid-cols-2">{visibleFindings.map(finding => {
          const claims = list(result.claims).filter(item => list(finding.claim_ids).includes(item.id))
          const refs = list(finding.evidence_ids).map(id => evidenceById.get(id)).filter(Boolean)
          return <article key={finding.id} className="rounded-xl border border-soft bg-slate-950/30 p-4"><div className="flex flex-wrap items-center gap-2"><span className="badge badge-outline">{finding.severity}</span><span className="text-xs text-muted">{finding.verdict}{finding.stale ? ' · stale' : ''}</span></div><h3 className="mt-2 font-semibold text-slate-100">{finding.title}</h3><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">{finding.detail || '（无补充说明）'}</p>
            {claims.map(claim => <div key={claim.id} className="mt-3 border-l-2 border-violet-400/60 pl-3 text-sm"><div className="text-xs text-violet-300">主张 · {claim.verdict}{claim.stale ? ' · stale' : ''}</div><p className="mt-1 text-slate-200">{claim.exact_text}</p>{claim.assumptions?.length > 0 && <p className="mt-1 text-xs text-muted">适用条件：{claim.assumptions.join('；')}</p>}{list(result.obligations).filter(value => list(claim.obligation_ids).includes(value.id)).map(obligation => <div key={obligation.id} className="mt-2 rounded-lg bg-slate-900/70 p-2 text-xs"><div className="text-slate-300">义务 · {obligation.text} · {obligation.fulfilled == null ? '待核验' : obligation.fulfilled ? '满足' : '未满足'}</div><div className="mt-1 flex flex-wrap gap-1">{list(obligation.evidence_ids).map(id => evidenceById.get(id)).filter(Boolean).map(item => <button key={item.id} className="btn btn-ghost btn-xs" onClick={() => openEvidence(item)}>证据 {item.id}</button>)}</div></div>)}</div>)}
            {!refs.length ? <div className="mt-3 text-sm text-amber-300">待人工核实 · 当前没有可定位证据</div> : <div className="mt-3 flex flex-wrap gap-2">{refs.map(item => <button key={item.id} className="btn btn-outline btn-xs" onClick={() => openEvidence(item)}>证据 {item.id} · {item.page ? `第${item.page}页` : item.paragraph ? `段落${item.paragraph}` : item.line_start ? `行${item.line_start}` : '查看'}</button>)}</div>}
          </article>
        })}</div>}
      </Panel>
      <Panel title="优化建议" description="修改会作为人工决定单独保存，保留原始模型建议与修改理由。">
        {!recommendations.length ? <EmptyState title="暂无优化建议" description="当前结果没有已保存的建议记录。" /> : <div className="grid gap-3 lg:grid-cols-2">{recommendations.map(item => {
          const change = result.metadata?.recommendation_overrides?.[item.id] || (audit?.metadata?.recommendation_overrides?.[item.id])
          return <article key={item.id} className="rounded-xl border border-soft p-4"><div className="flex items-center justify-between gap-3"><StatusBadge value={item.priority} /><button className="btn btn-outline btn-xs" onClick={() => { setEdit(item); setEditForm({ action: item.action, acceptance: item.acceptance, priority: item.priority, owner: item.owner || '', rationale: '' }); setActionError('') }}>编辑建议</button></div><p className="mt-3 text-sm leading-6 text-slate-200">{item.action}</p><div className="mt-2 text-xs text-muted">验收条件：{item.acceptance}</div><div className="mt-1 text-xs text-muted">负责人：{item.owner || '未指定'}</div>
            {change && <div className="mt-3 rounded-lg bg-emerald-400/10 p-3 text-xs text-emerald-100">人工修改 · {change.decided_by || 'human'} · {dateTime(change.decided_at)}<div className="mt-1">理由：{change.rationale || '—'}</div></div>}
            {result.metadata?.recommendation_originals?.[item.id] && <details className="mt-3 text-xs text-muted"><summary className="cursor-pointer">查看原始建议与修改历史</summary><p className="mt-2">原始动作：{result.metadata.recommendation_originals[item.id].action}</p>{list(result.metadata.recommendation_edit_history).filter(entry => entry.recommendation_id === item.id).map((entry, index) => <p className="mt-2" key={index}>{dateTime(entry.decided_at)} · {entry.after?.action} · {entry.rationale}</p>)}</details>}
          </article>
        })}</div>}
      </Panel>
      {Object.keys(result.metadata?.recommendation_archive || {}).length > 0 && <Panel title="待重新核对的人工建议" description="重跑后原证据引用已变化；保留人工内容供核对，不作为当前有效建议。">{Object.values(result.metadata.recommendation_archive).map(item => <article className="mb-3 rounded-lg border border-amber-400/25 p-3 text-sm" key={item.id}><StatusBadge value="stale" /><p className="mt-2">{item.action}</p><p className="mt-1 text-muted">验收条件：{item.acceptance}</p></article>)}</Panel>}
      <Panel title="状态事件与输入记录" description="来自任务持久化快照的事件；当前服务未提供时显示为空。">
        {list(job.state_snapshot?.events).length ? <div className="space-y-2">{job.state_snapshot.events.map((event, index) => <div key={event.id || index} className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-slate-950/40 p-3 text-sm"><span>{event.from_state || '创建'} → {event.to_state || event.event_type} · {event.reason}</span><time className="text-xs text-muted">{dateTime(event.timestamp)}</time></div>)}</div> : list(job.state_snapshot?.state_machine?.events).length ? <div className="space-y-2">{job.state_snapshot.state_machine.events.map((event, index) => <div key={event.id || index} className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-slate-950/40 p-3 text-sm"><span>{event.from_state || '创建'} → {event.to_state || event.event_type} · {event.reason}</span><time className="text-xs text-muted">{dateTime(event.timestamp)}</time></div>)}</div> : <EmptyState title="暂无可展示的事件项" description="当前 API 快照没有返回状态事件列表。" />}
      </Panel>
    </>}
    {evidence && <Drawer title={`证据详情 · ${evidence.id}`} onClose={() => setEvidence(null)}>
      {evidenceError ? <ErrorNotice error={evidenceError} onRetry={() => openEvidence(evidence)} /> : !evidenceData ? <Loading /> : <div className="space-y-4 text-sm">
        <div className="grid grid-cols-2 gap-3"><div><span className="text-muted">资产</span><div className="break-all">{evidenceData.asset_id || '—'}</div></div><div><span className="text-muted">块</span><div>{evidenceData.block_id || '—'}</div></div><div><span className="text-muted">页码</span><div>{evidenceData.page ?? '—'}</div></div><div><span className="text-muted">段落</span><div>{evidenceData.paragraph ?? '—'}</div></div><div><span className="text-muted">行号</span><div>{evidenceData.line_start ?? '—'}{evidenceData.line_end ? `–${evidenceData.line_end}` : ''}</div></div><div><span className="text-muted">证据等级</span><div>{evidenceData.evidence_level || '—'}</div></div></div>
        {evidenceData.document_block ? <div className="rounded-xl border border-soft bg-slate-950/50 p-4"><div className="text-xs text-sky-300">原文块 · {evidenceData.document_block.block_id}</div><pre className="mt-3 whitespace-pre-wrap break-words font-sans leading-6 text-slate-200">{evidenceData.document_block.text || evidenceData.quote || '待人工核实'}</pre></div> : <div className="alert alert-warning">待人工核实 · 该证据没有可定位的原文块。</div>}
        {evidenceData.quote && <blockquote className="border-l-2 border-sky-400 pl-3 text-slate-300">{evidenceData.quote}</blockquote>}
      </div>}
    </Drawer>}
    {rerun && <Modal title={`重跑阶段：${rerun.label}`} onClose={() => !busy && setRerun(null)}>
      <p className="text-sm leading-6 text-slate-300">该阶段以及其后的依赖阶段会标记为 stale。已有结果仍可查看，但不能当作当前有效结论。请说明重跑原因。</p>
      <label className="form-control mt-4"><span className="label-text mb-2 text-slate-300">重跑原因</span><textarea className="textarea textarea-bordered min-h-24 bg-slate-950/60" value={reason} onChange={event => setReason(event.target.value)} placeholder="说明触发重跑的原因" /></label>
      {actionError && <div className="mt-4"><ErrorNotice error={actionError} /></div>}
      <div className="mt-6 flex justify-end gap-2"><button className="btn btn-ghost" disabled={busy} onClick={() => setRerun(null)}>取消</button><button className="btn btn-primary" disabled={busy || reason.trim().length < 3} onClick={startStageRerun}>{busy ? '正在提交…' : '确认重跑'}</button></div>
    </Modal>}
    {resumeOpen && <Modal title="继续评审任务" onClose={() => !busy && setResumeOpen(false)}>
      <p className="text-sm leading-6 text-slate-300">任务 {job.id} 已保留。继续之前请核对冻结输入，并填写这次操作的理由。人工确认只在你勾选并提交后记录。</p>
      <div className="mt-4 rounded-xl border border-soft bg-slate-950/50 p-3 text-xs"><p className="mb-2 text-sm">{inputs?.asset.filename || "资产详情暂不可用"} · {inputs?.rubric.name || "量表详情暂不可用"}</p><div>资产 ID：<span className="font-mono">{job.asset_id}</span></div><div className="mt-1">量表 ID：<span className="font-mono">{job.rubric_profile_id}</span></div><div className="mt-1 break-all">输入哈希：<span className="font-mono">{job.input_snapshot_hash}</span></div></div>
      <label className="form-control mt-4"><span className="label-text mb-2 text-slate-300">继续理由</span><textarea className="textarea textarea-bordered min-h-24 bg-slate-950/60" value={resumeReason} onChange={event => setResumeReason(event.target.value)} placeholder="说明为何继续此评审任务" /></label>
      <label className="mt-4 flex items-start gap-3 text-sm text-slate-300"><input className="checkbox checkbox-primary checkbox-sm mt-0.5" type="checkbox" checked={resumeConfirmed} onChange={event => setResumeConfirmed(event.target.checked)} /><span>我已核对任务输入，并确认继续评审。</span></label>
      {actionError && <div className="mt-4"><ErrorNotice error={actionError} /></div>}
      <div className="mt-6 flex justify-end gap-2"><button className="btn btn-ghost" disabled={busy} onClick={() => setResumeOpen(false)}>取消</button><button className="btn btn-primary" disabled={busy || !resumeConfirmed || resumeReason.trim().length < 3} onClick={continueRun}>{busy ? '正在继续…' : '继续运行'}</button></div>
    </Modal>}
    {edit && <Modal title="编辑优化建议" onClose={() => !busy && setEdit(null)}>
      <div className="space-y-4"><label className="form-control"><span className="label-text mb-2 text-slate-300">修改动作</span><textarea className="textarea textarea-bordered min-h-20 bg-slate-950/60" value={editForm.action || ''} onChange={event => setEditForm(value => ({ ...value, action: event.target.value }))} /></label>
        <label className="form-control"><span className="label-text mb-2 text-slate-300">验收条件</span><textarea className="textarea textarea-bordered min-h-20 bg-slate-950/60" value={editForm.acceptance || ''} onChange={event => setEditForm(value => ({ ...value, acceptance: event.target.value }))} /></label>
        <div className="grid gap-4 sm:grid-cols-2"><label className="form-control"><span className="label-text mb-2 text-slate-300">优先级</span><select className="select select-bordered bg-slate-950/60" value={editForm.priority || 'minor'} onChange={event => setEditForm(value => ({ ...value, priority: event.target.value }))}><option value="fatal">fatal</option><option value="major">major</option><option value="minor">minor</option></select></label><label className="form-control"><span className="label-text mb-2 text-slate-300">负责人</span><input className="input input-bordered bg-slate-950/60" value={editForm.owner || ''} onChange={event => setEditForm(value => ({ ...value, owner: event.target.value }))} /></label></div>
        <label className="form-control"><span className="label-text mb-2 text-slate-300">修改理由</span><textarea className="textarea textarea-bordered min-h-20 bg-slate-950/60" value={editForm.rationale || ''} onChange={event => setEditForm(value => ({ ...value, rationale: event.target.value }))} /></label>
      </div>
      {actionError && <div className="mt-4"><ErrorNotice error={actionError} /></div>}
      <div className="mt-6 flex justify-end gap-2"><button className="btn btn-ghost" disabled={busy} onClick={() => setEdit(null)}>取消</button><button className="btn btn-primary" disabled={busy || !editForm.action?.trim() || !editForm.acceptance?.trim() || !editForm.rationale?.trim()} onClick={saveRecommendation}>{busy ? '正在保存…' : '保存人工修改'}</button></div>
    </Modal>}
  </div>
}
