import { useCallback } from 'react'
import { api } from '../api'
import { useRemote } from '../hooks'
import { dateTime, navigate, safeError } from '../utils'
import { EmptyState, ErrorNotice, Loading, PageHeader, Panel, StatusBadge } from '../components/ui'

export default function Dashboard() {
  const load = useCallback(async () => {
    const [configs, assets, rubrics, reviews] = await Promise.all([api.configs(), api.assets(), api.rubrics(), api.reviews()])
    return { configs: configs.items || [], assets, rubrics, reviews }
  }, [])
  const { data, loading, error, reload } = useRemote(load)
  const stats = data ? [
    ['当前启用模型', data.configs.find(item => item.is_active)?.model || '未启用'],
    ['资产总数', data.assets.length],
    ['已发布量表', data.rubrics.filter(item => item.status === 'published').length],
    ['运行任务', data.reviews.filter(item => ['QUEUED', 'RUNNING'].includes(item.state_snapshot?.run?.run_status)).length],
  ] : []
  const latest = [...(data?.reviews || [])].sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || '')).slice(0, 5)
  return <div className="space-y-6">
    <PageHeader title="工作台概览" description="数学建模论文评审智能体 · 资产、量表与运行任务的当前状态。" actions={<button className="btn btn-primary" onClick={() => navigate('/create')}>创建评审</button>} />
    {loading && <Loading label="正在读取工作台状态…" />}
    {error && <ErrorNotice error={safeError(error)} onRetry={reload} />}
    {data && <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{stats.map(([label, value]) => <div key={label} className="workbench-panel p-5"><div className="text-sm text-muted">{label}</div><div className="mt-2 truncate text-xl font-semibold text-white" title={String(value)}>{value}</div></div>)}</div>
      <div className="grid gap-6 xl:grid-cols-[1.2fr_.8fr]">
        <Panel title="最近任务" description="展示最近更新的真实评审任务。" actions={<button className="btn btn-ghost btn-sm" onClick={() => navigate('/tasks')}>全部任务</button>}>
          {latest.length ? <div className="space-y-2">{latest.map(job => <button key={job.id} onClick={() => navigate(`/reviews/${job.id}`)} className="flex w-full flex-wrap items-center justify-between gap-3 rounded-xl border border-soft p-3 text-left hover:border-sky-400/50"><span className="min-w-0"><span className="block truncate font-medium text-slate-100">{job.id}</span><span className="text-xs text-muted">{dateTime(job.updated_at)}</span></span><StatusBadge value={job.state} /></button>)}</div> : <EmptyState title="暂无评审任务" description="准备好论文资产和已发布量表后，可以创建第一项评审。" />}
        </Panel>
        <Panel title="操作向导" description="按顺序准备输入，再启动人工确认后的七阶段评审。">
          <div className="space-y-3">{[['01','配置模型','/models'],['02','上传并解析论文','/assets'],['03','确认并发布官方量表','/rubrics'],['04','创建评审并查看结果','/create']].map(([n,label,path]) => <button key={n} onClick={() => navigate(path)} className="flex w-full items-center gap-3 rounded-xl bg-slate-900/60 p-3 text-left"><span className="grid h-8 w-8 place-items-center rounded-lg bg-blue-500/15 text-xs text-blue-300">{n}</span><span className="text-sm text-slate-200">{label}</span><span className="ml-auto text-muted">→</span></button>)}</div>
        </Panel>
      </div>
    </>}
  </div>
}
