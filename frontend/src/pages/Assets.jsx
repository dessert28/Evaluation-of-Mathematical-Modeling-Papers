import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useRemote } from '../hooks'
import { dateTime, safeError } from '../utils'
import { Drawer, EmptyState, ErrorNotice, Loading, PageHeader, Panel, StatusBadge } from '../components/ui'

const accepted = ['.pdf', '.docx', '.md', '.markdown']
const supports = file => accepted.some(ext => file.name.toLowerCase().endsWith(ext))

export default function Assets() {
  const loadAssets = useCallback(() => api.assets(), [])
  const { data, loading, error, reload } = useRemote(loadAssets)
  const [queue, setQueue] = useState([])
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [blocks, setBlocks] = useState([])
  const [detailError, setDetailError] = useState('')
  const [busy, setBusy] = useState(false)
  const input = useRef(null)
  const selectionRequest = useRef(0)
  useEffect(() => () => { selectionRequest.current++ }, [])
  const assets = Array.isArray(data) ? data : []

  const inspect = async item => {
    const request = ++selectionRequest.current
    setSelected(item); setDetail(null); setBlocks([]); setDetailError('')
    try {
      const [asset, content] = await Promise.all([api.asset(item.id), api.blocks(item.id)])
      if (request !== selectionRequest.current) return
      setDetail(asset); setBlocks(Array.isArray(content) ? content : [])
    } catch (err) { if (request === selectionRequest.current) setDetailError(safeError(err)) }
  }
  const upload = async files => {
    if (busy) return
    const list = Array.from(files)
    if (!list.length) return
    const prepared = list.map((file, index) => ({ key: `${Date.now()}-${index}-${file.name}`, name: file.name, status: supports(file) ? '等待上传' : '不支持', error: supports(file) ? '' : '仅支持 PDF、DOCX、Markdown 文件' }))
    setQueue(current => [...prepared, ...current])
    setBusy(true)
    for (let index = 0; index < list.length; index += 1) {
      const file = list[index], row = prepared[index]
      if (!supports(file)) continue
      setQueue(current => current.map(item => item.key === row.key ? { ...item, status: '上传中' } : item))
      try {
        await api.uploadAsset(file)
        setQueue(current => current.map(item => item.key === row.key ? { ...item, status: '已解析', error: '' } : item))
      } catch (err) {
        setQueue(current => current.map(item => item.key === row.key ? { ...item, status: '失败', error: safeError(err) } : item))
      }
    }
    await reload(); setBusy(false)
  }
  const onDrop = event => { event.preventDefault(); upload(event.dataTransfer.files) }

  return <div className="space-y-6">
    <PageHeader title="论文资产" description="管理已登记论文与来源文件。解析失败会保留在队列和资产记录中，便于定位原因。" actions={<button className="btn btn-primary" onClick={() => input.current?.click()} disabled={busy}>选择文件</button>} />
    <input ref={input} className="hidden" type="file" multiple accept={accepted.join(',')} onChange={event => { upload(event.target.files); event.target.value = '' }} />
    <div onDragOver={event => event.preventDefault()} onDrop={onDrop} className="rounded-2xl border border-dashed border-sky-400/40 bg-sky-400/[0.04] p-8 text-center">
      <div className="text-sky-300 text-lg font-semibold">拖放文件到此处上传</div><p className="text-sm text-slate-400 mt-2">支持 PDF、DOCX、MD，单文件逐项上传与解析</p>
    </div>
    {queue.length > 0 && <Panel title="上传队列" description="每个文件独立显示结果；失败项目不会隐藏。">
      <div className="space-y-2">{queue.map(row => <div key={row.key} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-900/60 px-4 py-3 text-sm"><span className="truncate">{row.name}</span><span className={row.status === '失败' || row.status === '不支持' ? 'text-rose-300' : 'text-slate-300'}>{row.status}{row.error ? ` · ${row.error}` : ''}</span></div>)}</div>
    </Panel>}
    <Panel title="资产库" description={`${assets.length} 项 · 内容以安全文本方式呈现`}>
      {loading ? <Loading /> : error ? <ErrorNotice error={error} onRetry={reload} /> : assets.length === 0 ? <EmptyState title="暂无论文资产" description="上传 PDF、DOCX 或 Markdown 文件后，解析状态与文档块会显示在这里。" action={<button className="btn btn-primary btn-sm" onClick={() => input.current?.click()}>上传文件</button>} /> :
        <div className="overflow-x-auto"><table className="table table-sm"><thead><tr><th>文件</th><th>解析状态</th><th>大小</th><th>文档块</th><th>SHA-256</th><th>创建时间</th><th></th></tr></thead><tbody>{assets.map(item => <tr key={item.id}>
          <td className="font-medium text-slate-100">{item.filename}</td><td><StatusBadge value={item.status} /></td><td>{(item.size_bytes / 1024).toFixed(1)} KB</td><td>{item.blocks?.length ?? '—'}</td><td className="font-mono text-xs">{item.sha256?.slice(0, 14) || '—'}…</td><td>{dateTime(item.created_at)}</td><td><button className="btn btn-ghost btn-xs" onClick={() => inspect(item)}>查看块</button></td>
        </tr>)}</tbody></table></div>}
    </Panel>
    {selected && <Drawer title={selected.filename} onClose={() => { selectionRequest.current++; setSelected(null) }}>
      {detailError ? <ErrorNotice error={detailError} onRetry={() => inspect(selected)} /> : !detail ? <Loading /> : <div className="space-y-5">
        <div className="grid grid-cols-2 gap-3 text-sm"><div><span className="text-slate-500">状态</span><div><StatusBadge value={detail.status} /></div></div><div><span className="text-slate-500">SHA-256</span><div className="font-mono break-all">{detail.sha256}</div></div></div>
        {detail.parse_error && <div className="alert alert-error text-sm">{detail.parse_error}</div>}
        {detail.warnings?.length > 0 && <div className="alert alert-warning text-sm">{detail.warnings.join('；')}</div>}
        <h3 className="font-semibold">文档块 · {blocks.length}</h3>
        {blocks.length ? blocks.map(block => <article key={block.block_id} className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
          <div className="flex flex-wrap justify-between gap-2 text-xs text-sky-300"><span>{block.block_type} · {block.block_id}</span><span>{block.page ? `第 ${block.page} 页` : ''}{block.paragraph ? ` · 段落 ${block.paragraph}` : ''}{block.line_start ? ` · 行 ${block.line_start}${block.line_end && block.line_end !== block.line_start ? `–${block.line_end}` : ''}` : ''}</span></div>
          <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6 text-slate-200 mt-3">{block.text}</pre>
        </article>) : <EmptyState title="没有可展示的文档块" description={detail.status === 'failed' ? '解析失败资产仍保留供审计。' : '此资产没有提取到文本内容。'} />}
      </div>}
    </Drawer>}
  </div>
}
