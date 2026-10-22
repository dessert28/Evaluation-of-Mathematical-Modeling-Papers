import { EmptyState, Panel, StatusBadge } from './ui'

export default function EvidenceIndex({ result, onEvidence }) {
  const evidence = result.evidence || []
  const byId = new Map(evidence.map(item => [item.id, item]))
  return <Panel title="主张与证据索引" description="展示全部已保存主张与证据，包括尚未关联问题的记录。">
    <div className="space-y-3">{(result.claims || []).map(claim => <details key={claim.id} className="rounded-xl border border-soft p-4">
      <summary className="cursor-pointer text-sm"><StatusBadge value={claim.verdict} /> <span className="ml-2">{claim.exact_text}</span>{claim.stale && <span className="ml-2 text-amber-300">stale</span>}</summary>
      {claim.scope && <p className="mt-3 text-sm text-muted">适用范围：{claim.scope}</p>}
      {claim.limitations?.length > 0 && <p className="mt-2 text-sm text-muted">限制：{claim.limitations.join('；')}</p>}
      {(result.obligations || []).filter(item => claim.obligation_ids?.includes(item.id)).map(item => <p key={item.id} className="mt-3 text-sm">义务：{item.text} · {item.fulfilled == null ? '待核验' : item.fulfilled ? '满足' : '未满足'}</p>)}
      <div className="mt-3 flex flex-wrap gap-2">{(claim.evidence_ids || []).map(id => byId.get(id)).filter(Boolean).map(item => <button key={item.id} className="btn btn-outline btn-xs" onClick={() => onEvidence(item)}>证据 {item.id}</button>)}</div>
      {!claim.evidence_ids?.length && <p className="mt-3 text-sm text-amber-300">待人工核实 · 缺少证据</p>}
    </details>)}</div>
    {!evidence.length ? <EmptyState title="暂无证据记录" description="尚未保存可以定位的证据。" /> : <div className="mt-4 overflow-x-auto"><table className="table table-sm"><thead><tr><th>证据</th><th>定位</th><th>等级</th><th></th></tr></thead><tbody>{evidence.map(item => <tr key={item.id}><td className="max-w-48 truncate font-mono text-xs">{item.id}</td><td>{item.page != null ? `第 ${item.page} 页` : item.paragraph != null ? `段落 ${item.paragraph}` : item.line_start != null ? `行 ${item.line_start}–${item.line_end || item.line_start}` : item.block_id ? '文档块' : '待人工核实'}</td><td className="text-xs">{item.evidence_level}</td><td><button className="btn btn-ghost btn-xs" onClick={() => onEvidence(item)}>查看原文</button></td></tr>)}</tbody></table></div>}
  </Panel>
}
