import { useCallback, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { useRemote } from '../hooks'
import { safeError } from '../utils'
import { EmptyState, ErrorNotice, Loading, Modal, PageHeader, Panel, StatusBadge } from '../components/ui'

const criterion = () => ({ id: `criterion-${Date.now()}`, label: '', description: '', weight: 0, scale_min: 0, scale_max: 100, evidence_required: true })
const totalWeight = items => items.reduce((sum, item) => sum + Number(item.weight || 0), 0)

export default function Rubrics() {
  const loadRubrics = useCallback(() => api.rubrics(), [])
  const { data, loading, error, reload } = useRemote(loadRubrics)
  const rubrics = Array.isArray(data) ? data : []
  const fileInput = useRef(null)
  const [editing, setEditing] = useState(null)
  const [publishing, setPublishing] = useState(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [operationError, setOperationError] = useState('')

  const importFile = async file => {
    if (!file) return
    setBusy(true); setOperationError(''); setNotice('')
    try { await api.importRubricFile(file); await reload(); setNotice(`已导入 ${file.name}，请核对解析后的评分项与权重。`) }
    catch (err) { setOperationError(safeError(err)) } finally { setBusy(false) }
  }
  const openEdit = item => setEditing({ id: item.id, name: item.name, version: item.version, source_asset_id: item.source_asset_id, source_hash: item.source_hash, criteria: item.criteria.map(c => ({ ...c })) })
  const weight = useMemo(() => editing ? totalWeight(editing.criteria) : 0, [editing])
  const updateCriterion = (index, key, value) => setEditing(current => ({ ...current, criteria: current.criteria.map((item, i) => i === index ? { ...item, [key]: value } : item) }))
  const save = async event => {
    event.preventDefault(); setBusy(true); setOperationError('')
    const payload = { format: 'json', source_asset_id: editing.source_asset_id, source_hash: editing.source_hash, content: { name: editing.name, version: editing.version, criteria: editing.criteria } }
    try { await api.updateRubric(editing.id, payload); await reload(); setEditing(null); setNotice('量表草稿已保存。') }
    catch (err) { setOperationError(safeError(err)) } finally { setBusy(false) }
  }
  const publish = async event => {
    event.preventDefault(); setBusy(true); setOperationError('')
    const form = new FormData(event.currentTarget)
    try { await api.publishRubric(publishing.id, { confirmed_by: 'human', decision: 'publish', rationale: String(form.get('rationale') || '').trim() }); await reload(); setPublishing(null); setNotice('已按你的确认发布该量表版本。') }
    catch (err) { setOperationError(safeError(err)) } finally { setBusy(false) }
  }

  return <div className="space-y-6">
    <PageHeader title="官方评分标准" description="导入来源文件，逐项核对解析结果与权重，人工确认后发布不可变版本。" actions={<button className="btn btn-primary" onClick={() => fileInput.current?.click()} disabled={busy}>导入评分文件</button>} />
    <input ref={fileInput} className="hidden" type="file" accept=".json,.md,.markdown,.pdf,.docx" onChange={event => { importFile(event.target.files?.[0]); event.target.value = '' }} />
    <Panel title="从来源文件创建草稿" description="支持 JSON、Markdown、PDF、DOCX；导入失败会显示后端错误，源资产与哈希由接口绑定。">
      <div className="flex flex-wrap items-center gap-4"><button className="btn btn-outline btn-sm" onClick={() => fileInput.current?.click()} disabled={busy}>选择文件</button><span className="text-sm text-slate-400">{busy ? '正在处理…' : '请确保文件包含可识别的评分项和权重。'}</span></div>
    </Panel>
    {notice && <div role="status" className="alert alert-success text-sm">{notice}</div>}{operationError && <div role="alert" className="alert alert-error text-sm"><span>{operationError}</span><button className="btn btn-ghost btn-xs" onClick={() => setOperationError('')}>关闭</button></div>}
    <Panel title="量表版本" description="权重按 0–1 保存；发布要求所有权重大于 0 且合计为 1。">
      {loading ? <Loading /> : error ? <ErrorNotice error={error} onRetry={reload} /> : !rubrics.length ? <EmptyState title="暂无评分标准" description="导入官方评分文件后，草稿和已发布版本会显示在这里。" action={<button className="btn btn-primary btn-sm" onClick={() => fileInput.current?.click()}>导入评分文件</button>} /> :
        <div className="space-y-4">{rubrics.map(item => {
          const total = totalWeight(item.criteria || [])
          return <article key={item.id} className="rounded-2xl border border-slate-700 bg-slate-900/50 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold text-slate-100">{item.name} <span className="text-slate-400">· {item.version}</span></h3><p className="mt-1 text-xs text-slate-400">来源 {item.source_asset_id} · {item.criteria?.length || 0} 个评分项</p></div><StatusBadge value={item.status} /></div>
            <div className="mt-4 grid gap-3 sm:grid-cols-3 text-sm"><div className="rounded-xl bg-slate-950/60 p-3"><span className="text-slate-500">权重合计</span><p className={Math.abs(total - 1) <= 1e-6 ? 'text-emerald-300' : 'text-amber-300'}>{(total * 100).toFixed(2)}%</p></div><div className="rounded-xl bg-slate-950/60 p-3"><span className="text-slate-500">源文件哈希</span><p className="font-mono text-xs break-all">{item.source_hash}</p></div><div className="rounded-xl bg-slate-950/60 p-3"><span className="text-slate-500">发布决策</span><p>{item.decision_ledger_id || '尚未确认'}</p></div></div>
            {item.warnings?.length > 0 && <div className="alert alert-warning mt-3 text-sm">{item.warnings.join('；')}</div>}
            <div className="mt-4 overflow-x-auto"><table className="table table-xs"><thead><tr><th>ID</th><th>评分项</th><th>权重</th><th>分值范围</th><th>证据</th></tr></thead><tbody>{item.criteria?.map(row => <tr key={row.id}><td>{row.id}</td><td>{row.label}</td><td>{(row.weight * 100).toFixed(2)}%</td><td>{row.scale_min}–{row.scale_max}</td><td>{row.evidence_required ? '要求' : '可选'}</td></tr>)}</tbody></table></div>
            {item.status === 'draft' && <div className="mt-4 flex gap-2"><button className="btn btn-sm btn-outline" onClick={() => openEdit(item)}>编辑评分项</button><button className="btn btn-sm btn-primary" disabled={total <= 0 || Math.abs(total - 1) > 1e-6} onClick={() => { setPublishing(item); setOperationError('') }}>确认并发布</button></div>}
          </article>
        })}</div>}
    </Panel>
    {editing && <Modal title="编辑量表草稿" onClose={() => setEditing(null)}>
      <form onSubmit={save} className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2"><label className="form-control"><span className="label-text">名称</span><input className="input input-bordered" required value={editing.name} onChange={event => setEditing({ ...editing, name: event.target.value })} /></label><label className="form-control"><span className="label-text">版本</span><input className="input input-bordered" required value={editing.version} onChange={event => setEditing({ ...editing, version: event.target.value })} /></label></div>
        <div className="flex items-center justify-between"><h3 className="font-semibold">评分项表格</h3><button type="button" className="btn btn-xs btn-outline" onClick={() => setEditing(current => ({ ...current, criteria: [...current.criteria, criterion()] }))}>添加评分项</button></div>
        <div className="overflow-x-auto"><table className="table table-xs"><thead><tr><th>ID</th><th>名称</th><th>说明</th><th>权重 %</th><th>最低</th><th>最高</th><th>证据</th><th></th></tr></thead><tbody>{editing.criteria.map((row, index) => <tr key={`${row.id}-${index}`}>
          <td><input className="input input-bordered input-xs w-28" value={row.id} onChange={e => updateCriterion(index, 'id', e.target.value)} required /></td><td><input className="input input-bordered input-xs w-32" value={row.label} onChange={e => updateCriterion(index, 'label', e.target.value)} required /></td><td><input className="input input-bordered input-xs w-48" value={row.description} onChange={e => updateCriterion(index, 'description', e.target.value)} /></td><td><input type="number" min="0" max="100" step="0.01" className="input input-bordered input-xs w-20" value={(Number(row.weight) * 100).toFixed(2)} onChange={e => updateCriterion(index, 'weight', Number(e.target.value) / 100)} /></td><td><input type="number" className="input input-bordered input-xs w-16" value={row.scale_min} onChange={e => updateCriterion(index, 'scale_min', Number(e.target.value))} /></td><td><input type="number" className="input input-bordered input-xs w-16" value={row.scale_max} onChange={e => updateCriterion(index, 'scale_max', Number(e.target.value))} /></td><td><input type="checkbox" className="checkbox checkbox-xs" checked={row.evidence_required} onChange={e => updateCriterion(index, 'evidence_required', e.target.checked)} /></td><td><button type="button" className="btn btn-ghost btn-xs text-rose-300" onClick={() => setEditing(current => ({ ...current, criteria: current.criteria.filter((_, i) => i !== index) }))}>移除</button></td>
        </tr>)}</tbody></table></div>
        <p className={Math.abs(weight - 1) <= 1e-6 ? 'text-sm text-emerald-300' : 'text-sm text-amber-300'}>当前权重合计 {(weight * 100).toFixed(2)}%。导入器会按后端规则归一化非零权重；保存后请再次核对。</p>
        <div className="flex justify-end gap-2"><button type="button" className="btn btn-ghost" onClick={() => setEditing(null)}>取消</button><button className="btn btn-primary" disabled={busy || !editing.criteria.length}>保存草稿</button></div>
      </form>
    </Modal>}
    {publishing && <Modal title="确认发布量表" onClose={() => setPublishing(null)}>
      <form onSubmit={publish} className="space-y-4"><p>发布 <b>{publishing.name} · {publishing.version}</b> 后该版本将不可编辑。请确认权重和评分项已人工核对。</p><label className="form-control"><span className="label-text">人工确认理由</span><textarea name="rationale" required minLength="3" className="textarea textarea-bordered" placeholder="记录你核对了哪些内容" /></label><div className="flex justify-end gap-2"><button type="button" className="btn btn-ghost" onClick={() => setPublishing(null)}>取消</button><button className="btn btn-primary" disabled={busy}>我已核对，发布</button></div></form>
    </Modal>}
  </div>
}
