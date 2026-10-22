import { useCallback, useState } from 'react'
import { api } from '../api'
import { useRemote } from '../hooks'
import { dateTime, safeError } from '../utils'
import { EmptyState, ErrorNotice, Loading, Modal, PageHeader, Panel, StatusBadge } from '../components/ui'

const blank = () => ({ provider: 'openai', base_url: 'https://api.openai.com/v1', api_key: '', model: '', is_active: true })

export default function Models() {
  const loadConfigs = useCallback(() => api.configs(), [])
  const { data, loading, error, reload } = useRemote(loadConfigs)
  const configs = data?.items || []
  const presets = data?.presets || {}
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(null)
  const [busy, setBusy] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [notice, setNotice] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [testing, setTesting] = useState('')

  const openCreate = () => { setEditing(null); setForm(blank()); setErrorMessage('') }
  const openEdit = item => { setEditing(item); setForm({ provider: item.provider, base_url: item.base_url, api_key: '', model: item.model, is_active: item.is_active }); setErrorMessage('') }
  const save = async event => {
    event.preventDefault(); setBusy(true); setErrorMessage(''); setNotice('')
    const body = { provider: form.provider.trim(), base_url: form.base_url.trim(), api_key: form.api_key, model: form.model.trim(), is_active: form.is_active }
    try {
      await api.saveConfig(body, editing?.id)
      setForm(current => ({ ...current, api_key: '' }))
      await reload(); setEditing(null); setForm(null); setNotice('模型配置已安全保存。')
    } catch (err) { setErrorMessage(safeError(err)) } finally { setBusy(false) }
  }
  const test = async item => {
    setTesting(item.id); setErrorMessage(''); setNotice('')
    try { await api.testConfig(item.id); setNotice(`${item.provider} · ${item.model} 连接测试成功。`) }
    catch (err) { setErrorMessage(safeError(err)) } finally { setTesting('') }
  }
  const remove = async () => {
    if (!confirmDelete) return
    setBusy(true); setErrorMessage('')
    try { await api.deleteConfig(confirmDelete.id); await reload(); setConfirmDelete(null); setNotice('模型配置已删除。') }
    catch (err) { setErrorMessage(safeError(err)) } finally { setBusy(false) }
  }
  const chooseProvider = provider => setForm(current => ({ ...current, provider, base_url: presets[provider] || (current.provider === 'custom' ? current.base_url : '') }))

  return <div className="space-y-6">
    <PageHeader title="模型配置" description="管理 OpenAI-compatible 服务端点。密钥仅在保存表单中临时输入，接口只返回是否已配置。" actions={<button className="btn btn-primary" onClick={openCreate}>新增配置</button>} />
    {notice && <div role="status" className="alert alert-success text-sm">{notice}</div>}{errorMessage && <div role="alert" className="alert alert-error text-sm"><span>{errorMessage}</span><button className="btn btn-ghost btn-xs" onClick={() => setErrorMessage('')}>关闭</button></div>}
    <Panel title="已保存的配置" description="启用配置会将其设为评审运行时使用的模型。密钥明文不会在此列表中显示。">
      {loading ? <Loading /> : error ? <ErrorNotice error={error} onRetry={reload} /> : configs.length === 0 ? <EmptyState title="尚未配置模型" description="新增一个兼容服务端点，再测试连接并启用它。" action={<button className="btn btn-primary btn-sm" onClick={openCreate}>新增配置</button>} /> :
        <div className="overflow-x-auto"><table className="table"><thead><tr><th>提供商</th><th>模型</th><th>API 地址</th><th>密钥</th><th>状态</th><th>更新时间</th><th>操作</th></tr></thead><tbody>{configs.map(item => <tr key={item.id}>
          <td className="font-medium">{item.provider}</td><td>{item.model}</td><td className="max-w-64 truncate font-mono text-xs">{item.base_url}</td><td>{item.api_key_configured ? <span className="text-emerald-300">已配置 · 隐藏</span> : <span className="text-slate-500">未配置</span>}</td><td><StatusBadge value={item.is_active ? 'active' : 'inactive'} /></td><td>{dateTime(item.updated_at || item.created_at)}</td>
          <td><div className="flex flex-wrap gap-1"><button className="btn btn-ghost btn-xs" onClick={() => openEdit(item)}>编辑</button><button className="btn btn-ghost btn-xs" disabled={testing === item.id} onClick={() => test(item)}>{testing === item.id ? '测试中…' : '测试'}</button>{!item.is_active && <button className="btn btn-outline btn-xs" onClick={() => openEdit({ ...item, is_active: true })}>启用</button>}<button className="btn btn-ghost btn-xs text-rose-300" onClick={() => setConfirmDelete(item)}>删除</button></div></td>
        </tr>)}</tbody></table></div>}
    </Panel>
    <Panel title="密钥保护" description="API Key 只通过 TLS/本地 API 在提交时发送；保存后输入框清空，列表响应只含 api_key_configured。" />
    {editing !== null || form ? <Modal title={editing ? '编辑模型配置' : '新增模型配置'} onClose={() => { setEditing(null); setForm(null); setErrorMessage('') }}>
      <form onSubmit={save} className="space-y-4">
        <label className="form-control"><span className="label-text">提供商</span><select aria-label="提供商" className="select select-bordered" value={Object.hasOwn(presets, form?.provider) ? form.provider : 'custom'} onChange={event => chooseProvider(event.target.value)}>{Object.keys(presets).map(value => <option key={value} value={value}>{value === 'custom' ? '自定义' : value}</option>)}</select></label>
        {form && (form.provider === 'custom' || !Object.hasOwn(presets, form.provider)) && <label className="form-control"><span className="label-text">自定义提供商名称</span><input aria-label="自定义提供商名称" className="input input-bordered" required value={form.provider} onChange={event => setForm({ ...form, provider: event.target.value })} placeholder="如：团队模型网关" /></label>}
        <label className="form-control"><span className="label-text">API Base URL</span><input className="input input-bordered" type="url" required value={form?.base_url || ''} onChange={event => setForm({ ...form, base_url: event.target.value })} placeholder="https://api.example.com/v1" /></label>
        <label className="form-control"><span className="label-text">模型名称</span><input className="input input-bordered" required value={form?.model || ''} onChange={event => setForm({ ...form, model: event.target.value })} placeholder="服务商提供的模型 ID" /></label>
        <label className="form-control"><span className="label-text">API Key {editing && form?.api_key === '' ? '（留空保留已保存密钥）' : '（不会回显）'}</span><input className="input input-bordered font-mono" type="password" autoComplete="new-password" value={form?.api_key || ''} onChange={event => setForm({ ...form, api_key: event.target.value })} placeholder={editing?.api_key_configured ? '已配置；留空保持原值' : '在此临时输入密钥'} /></label>
        <label className="flex cursor-pointer items-center gap-3"><input type="checkbox" className="toggle toggle-primary" checked={Boolean(form?.is_active)} onChange={event => setForm({ ...form, is_active: event.target.checked })} /><span>保存后启用此配置</span></label>
        {errorMessage && <div role="alert" className="alert alert-error text-sm">{errorMessage}</div>}
        <div className="flex justify-end gap-2"><button type="button" className="btn btn-ghost" onClick={() => { setEditing(null); setForm(null) }}>取消</button><button className="btn btn-primary" disabled={busy}>{busy ? '保存中…' : '安全保存'}</button></div>
      </form>
    </Modal> : null}
    {confirmDelete && <Modal title="删除模型配置" onClose={() => setConfirmDelete(null)}>
      <div className="space-y-4"><p>将删除 <b>{confirmDelete.provider} · {confirmDelete.model}</b> 的加密密钥和端点配置。正在使用的配置也会立即从运行时列表移除。</p>{errorMessage && <div role="alert" className="alert alert-error text-sm">{errorMessage}</div>}<div className="flex justify-end gap-2"><button className="btn btn-ghost" onClick={() => setConfirmDelete(null)}>取消</button><button className="btn btn-error" disabled={busy} onClick={remove}>确认删除</button></div></div>
    </Modal>}
  </div>
}
