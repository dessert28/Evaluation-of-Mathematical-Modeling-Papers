import { useCallback, useMemo, useState } from 'react'
import { api } from '../api'
import { useRemote } from '../hooks'
import { dateTime, key, navigate, prepareReview, safeError } from '../utils'
import { EmptyState, ErrorNotice, Loading, Modal, PageHeader, Panel, StatusBadge } from '../components/ui'

export default function CreateReview() {
  const load = useCallback(async () => Promise.all([api.assets(), api.rubrics()]).then(([assets, rubrics]) => ({ assets, rubrics })), [])
  const { data, loading, error, reload } = useRemote(load)
  const [assetId, setAssetId] = useState(''), [rubricId, setRubricId] = useState('')
  const [job, setJob] = useState(null), [dialog, setDialog] = useState(false), [rationale, setRationale] = useState('')
  const [confirmed, setConfirmed] = useState(false), [busy, setBusy] = useState(false), [actionError, setActionError] = useState('')
  const sourceIds = new Set((data?.rubrics || []).map(item => item.source_asset_id))
  const assets = (data?.assets || []).filter(item => item.status === 'parsed' && /\.(pdf|docx|md|markdown)$/i.test(item.filename) && !sourceIds.has(item.id))
  const rubrics = (data?.rubrics || []).filter(item => item.status === 'published')
  const asset = assets.find(item => item.id === assetId), rubric = rubrics.find(item => item.id === rubricId)
  const canCreate = Boolean(asset && rubric)

  const launch = async () => {
    if (!confirmed || rationale.trim().length < 3 || !canCreate) return
    setBusy(true); setActionError('')
    try {
      let current = job
      if (!current) {
        current = await api.createReview({ asset_id: assetId, rubric_profile_id: rubricId, options: {} })
        setJob(current)
      }
      const prepared = await prepareReview(api, current, { confirmed: true, reason: rationale.trim() })
      setJob(prepared)
      await api.runReview(prepared.id, { idempotency_key: key() })
      setDialog(false); navigate(`/reviews/${prepared.id}`)
    } catch (err) { setActionError(safeError(err)) }
    finally { setBusy(false) }
  }
  const inputHash = useMemo(() => asset && rubric ? `${asset.sha256} · ${rubric.source_hash || rubric.source_sha256 || '来源哈希已绑定'}` : '选择论文与量表以查看输入摘要', [asset, rubric])
  return <div className="space-y-6">
    <PageHeader title="创建评审" description="选择已解析论文和已发布官方量表。输入冻结后，需由你明确确认才会进入评审阶段。" />
    {loading && <Loading />}{error && <ErrorNotice error={safeError(error)} onRetry={reload} />}
    {data && <div className="grid gap-6 xl:grid-cols-[1fr_.8fr]">
      <Panel title="评审输入" description="仅显示当前可用于新任务的真实资产和已发布量表。">
        {!assets.length || !rubrics.length ? <EmptyState title="创建条件尚未满足" description={!assets.length ? '请先上传并解析一篇论文。' : '请先导入、确认并发布一份官方量表。'} /> : <div className="space-y-5">
          <label className="form-control w-full"><span className="label-text mb-2 text-slate-300">论文资产</span><select disabled={Boolean(job)} className="select select-bordered bg-slate-950/60" value={assetId} onChange={event => setAssetId(event.target.value)}><option value="">选择已解析论文</option>{assets.map(item => <option key={item.id} value={item.id}>{item.filename}</option>)}</select></label>
          <label className="form-control w-full"><span className="label-text mb-2 text-slate-300">官方评分标准</span><select disabled={Boolean(job)} className="select select-bordered bg-slate-950/60" value={rubricId} onChange={event => setRubricId(event.target.value)}><option value="">选择已发布量表</option>{rubrics.map(item => <option key={item.id} value={item.id}>{item.name} · {item.version}</option>)}</select></label>
          {asset && <div className="rounded-xl border border-soft bg-slate-950/40 p-4 text-sm"><div className="flex justify-between gap-3"><b className="truncate">{asset.filename}</b><StatusBadge value={asset.status} /></div><div className="mt-2 text-xs text-muted">{asset.blocks?.length ?? '—'} 个文档块 · {dateTime(asset.created_at)}</div><div className="mt-3 break-all font-mono text-xs text-sky-200">{asset.sha256}</div></div>}
          {rubric && <div className="rounded-xl border border-soft bg-slate-950/40 p-4 text-sm"><div className="flex justify-between gap-3"><b>{rubric.name} · {rubric.version}</b><StatusBadge value={rubric.status} /></div><div className="mt-2 text-xs text-muted">评分项 {rubric.criteria?.length ?? 0} · 来源 {rubric.source_asset_id || '已绑定'}</div></div>}
        </div>}
      </Panel>
      <Panel title="输入快照" description="创建后会冻结资产与量表标识及哈希。">
        <dl className="space-y-4 text-sm"><div><dt className="text-muted">论文</dt><dd className="mt-1 break-all text-slate-100">{asset?.filename || '尚未选择'}</dd></div><div><dt className="text-muted">量表</dt><dd className="mt-1 text-slate-100">{rubric ? `${rubric.name} · ${rubric.version}` : '尚未选择'}</dd></div><div><dt className="text-muted">输入哈希摘要</dt><dd className="mt-1 break-all font-mono text-xs text-sky-200">{inputHash}</dd></div></dl>
        {job && <div className="alert alert-warning mt-5 text-sm">任务 {job.id} 已创建；流程未完成，可继续人工确认或保留任务。</div>}
        {actionError && <div className="mt-4"><ErrorNotice error={actionError} onRetry={() => { setDialog(true); setActionError('') }} /></div>}
        <button className="btn btn-primary mt-6 w-full" disabled={!canCreate || busy} onClick={() => setDialog(true)}>{job ? '继续确认并启动' : '创建并确认启动'}</button>
      </Panel>
    </div>}
    {dialog && <Modal title="确认评审输入并启动" onClose={() => !busy && setDialog(false)}>
      <p className="text-sm leading-6 text-slate-300">请核对论文、量表及输入哈希。确认后将记录本次人工决定，并依次推进任务状态。每次状态推进失败都会保留已创建任务，之后可继续。</p>
      <label className="form-control mt-4"><span className="label-text mb-2 text-slate-300">确认理由</span><textarea className="textarea textarea-bordered min-h-24 bg-slate-950/60" value={rationale} onChange={event => setRationale(event.target.value)} placeholder="例如：已核对论文文件与本次官方评分标准。" /></label>
      <label className="mt-4 flex items-start gap-3 text-sm text-slate-300"><input className="checkbox checkbox-primary checkbox-sm mt-0.5" type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /><span>我已核对以上输入，并确认启动本次七阶段评审。</span></label>
      {actionError && <div className="mt-4"><ErrorNotice error={actionError} /></div>}
      <div className="mt-6 flex justify-end gap-2"><button className="btn btn-ghost" disabled={busy} onClick={() => setDialog(false)}>取消</button><button className="btn btn-primary" disabled={busy || !confirmed || rationale.trim().length < 3} onClick={launch}>{busy ? '正在推进…' : '确认并启动'}</button></div>
    </Modal>}
  </div>
}
