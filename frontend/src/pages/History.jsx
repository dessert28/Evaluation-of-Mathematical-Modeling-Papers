import { useCallback, useMemo, useState } from 'react'
import { api } from '../api'
import { useRemote } from '../hooks'
import { dateKey, dateTime, navigate, safeError } from '../utils'
import { EmptyState, ErrorNotice, Loading, PageHeader, Panel, StatusBadge } from '../components/ui'

export default function History() {
  const load = useCallback(async () => Promise.all([api.reviews(), api.assets(), api.rubrics()]).then(([reviews, assets, rubrics]) => ({ reviews, assets, rubrics })), [])
  const { data, loading, error, reload } = useRemote(load)
  const [from, setFrom] = useState(''), [to, setTo] = useState(''), [assetId, setAssetId] = useState(''), [rubricId, setRubricId] = useState(''), [status, setStatus] = useState('')
  const rows = useMemo(() => (data?.reviews || []).filter(job => {
    const date = dateKey(job.created_at)
    return (!from || date >= from) && (!to || date <= to) && (!assetId || job.asset_id === assetId) && (!rubricId || job.rubric_profile_id === rubricId) && (!status || job.state === status)
  }).sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '')), [data, from, to, assetId, rubricId, status])
  const assets = new Map((data?.assets || []).map(item => [item.id, item.filename]))
  const rubrics = new Map((data?.rubrics || []).map(item => [item.id, `${item.name} · ${item.version}`]))
  return <div className="space-y-6">
    <PageHeader title="历史与审计" description="筛选当前存储的评审任务，查看输入快照、状态、历史结果和已保存的人工修改。" />
    <Panel title="筛选条件" description="筛选基于任务创建时间和任务快照中的真实关联字段。">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"><label className="form-control"><span className="label-text mb-1 text-xs text-muted">从</span><input className="input input-bordered input-sm bg-slate-950/60" type="date" value={from} onChange={event => setFrom(event.target.value)} /></label><label className="form-control"><span className="label-text mb-1 text-xs text-muted">至</span><input className="input input-bordered input-sm bg-slate-950/60" type="date" value={to} onChange={event => setTo(event.target.value)} /></label>
        <label className="form-control"><span className="label-text mb-1 text-xs text-muted">论文资产</span><select className="select select-bordered select-sm bg-slate-950/60" value={assetId} onChange={event => setAssetId(event.target.value)}><option value="">全部资产</option>{(data?.assets || []).map(item => <option key={item.id} value={item.id}>{item.filename}</option>)}</select></label>
        <label className="form-control"><span className="label-text mb-1 text-xs text-muted">官方量表</span><select className="select select-bordered select-sm bg-slate-950/60" value={rubricId} onChange={event => setRubricId(event.target.value)}><option value="">全部量表</option>{(data?.rubrics || []).map(item => <option key={item.id} value={item.id}>{item.name} · {item.version}</option>)}</select></label>
        <label className="form-control"><span className="label-text mb-1 text-xs text-muted">任务状态</span><select className="select select-bordered select-sm bg-slate-950/60" value={status} onChange={event => setStatus(event.target.value)}><option value="">全部状态</option>{['CREATED','EVALUATING','EVIDENCE_AUDIT','FAILED','BLOCKED','DEGRADED','REVIEWABLE','NEEDS_MAJOR_FIXES'].map(value => <option key={value}>{value}</option>)}</select></label></div>
    </Panel>
    <Panel title="历史任务" description={`${rows.length} 项匹配记录`}>
      {loading ? <Loading /> : error ? <ErrorNotice error={safeError(error)} onRetry={reload} /> : !rows.length ? <EmptyState title="没有匹配的历史记录" description="历史页面不会补充示例任务或人工修改。" /> : <div className="overflow-x-auto"><table className="table table-sm"><thead><tr><th>创建时间</th><th>论文</th><th>量表</th><th>状态</th><th>stale</th><th>输入哈希</th><th></th></tr></thead><tbody>{rows.map(job => {
        const stale = Boolean(job.state_snapshot?.stale || (job.state_snapshot?.stale_dependencies || []).length || Object.values(job.state_snapshot?.stage_stale || {}).some(Boolean))
        return <tr key={job.id}><td>{dateTime(job.created_at)}</td><td>{assets.get(job.asset_id) || job.asset_id}</td><td>{rubrics.get(job.rubric_profile_id) || job.rubric_profile_id}</td><td><StatusBadge value={job.state} /></td><td>{stale ? <StatusBadge value="stale" /> : '—'}</td><td className="max-w-44 truncate font-mono text-xs">{job.input_snapshot_hash}</td><td><button className="btn btn-ghost btn-xs" onClick={() => navigate(`/reviews/${job.id}`)}>查看结果与审计</button></td></tr>
      })}</tbody></table></div>}
    </Panel>
  </div>
}
