import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { useRemote } from '../hooks'
import { dateTime, navigate, safeError } from '../utils'
import { EmptyState, ErrorNotice, Loading, PageHeader, Panel, StatusBadge } from '../components/ui'

export default function ReviewTasks() {
  const load = useCallback(() => api.reviews(), [])
  const { data, loading, error, reload } = useRemote(load)
  const [query, setQuery] = useState(''), [status, setStatus] = useState('')
  useEffect(() => {
    const active = (data || []).some(job => ['QUEUED', 'RUNNING'].includes(job.state_snapshot?.run?.run_status))
    if (!active) return undefined
    let alive = true, timer
    const tick = async () => { await reload(); if (alive) timer = window.setTimeout(tick, 3000) }
    timer = window.setTimeout(tick, 3000)
    return () => { alive = false; window.clearTimeout(timer) }
  }, [data, reload])
  const rows = useMemo(() => (Array.isArray(data) ? data : []).filter(job =>
    (!status || job.state === status) && (!query || `${job.id} ${job.asset_id} ${job.rubric_profile_id}`.toLowerCase().includes(query.toLowerCase()))
  ).sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || '')), [data, query, status])
  return <div className="space-y-6">
    <PageHeader title="评审任务" description="查看生命周期状态、七阶段运行进度及可用的部分结果。运行中任务由服务端每次刷新返回最新快照。" actions={<button className="btn btn-primary" onClick={() => navigate('/create')}>创建评审</button>} />
    <Panel title="任务列表" description={`${rows.length} 项匹配任务`}>
      <div className="mb-4 flex flex-wrap gap-3"><input className="input input-bordered input-sm min-w-56 bg-slate-950/60" value={query} onChange={event => setQuery(event.target.value)} placeholder="按任务、资产或量表搜索" aria-label="搜索任务" /><select className="select select-bordered select-sm bg-slate-950/60" value={status} onChange={event => setStatus(event.target.value)} aria-label="按状态筛选"><option value="">全部状态</option>{['CREATED','INGESTING','ASSETS_FROZEN','RUBRIC_CONFIRMATION','EVALUATING','EVIDENCE_AUDIT','FAILED','BLOCKED','DEGRADED','REVIEWABLE','NEEDS_MAJOR_FIXES'].map(value => <option key={value}>{value}</option>)}</select><button className="btn btn-ghost btn-sm" onClick={reload}>刷新</button></div>
      {loading ? <Loading /> : error ? <ErrorNotice error={safeError(error)} onRetry={reload} /> : !rows.length ? <EmptyState title="没有匹配任务" description="创建任务后，列表会展示真实状态和进度。" /> : <div className="overflow-x-auto"><table className="table table-sm"><thead><tr><th>任务</th><th>状态</th><th>当前阶段</th><th>进度</th><th>失败阶段</th><th>更新时间</th><th></th></tr></thead><tbody>{rows.map(job => {
        const run = job.state_snapshot?.run || {}, completed = run.completed_stages || [], failed = run.failed_stages || []
        return <tr key={job.id}><td className="font-mono text-xs">{job.id}</td><td><StatusBadge value={job.state} /></td><td>{run.current_stage || '—'}</td><td>{completed.length}/7 · {Math.round((run.completed_weight || 0) * 100)}%</td><td>{failed.length ? failed.join(', ') : '—'}</td><td>{dateTime(job.updated_at)}</td><td><button className="btn btn-ghost btn-xs" onClick={() => navigate(`/reviews/${job.id}`)}>查看</button></td></tr>
      })}</tbody></table></div>}
    </Panel>
  </div>
}
