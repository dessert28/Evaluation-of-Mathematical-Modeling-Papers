import { useEffect, useRef } from 'react'

export function Panel({ title, description, actions, children, className = '' }) {
  return <section className={`workbench-panel min-w-0 ${className}`}>
    {(title || description || actions) && <header className="flex flex-wrap items-start justify-between gap-3 border-b border-soft px-5 py-4">
      <div className="min-w-0">{title && <h2 className="text-base font-semibold tracking-wide text-slate-100">{title}</h2>}{description && <p className="mt-1 text-sm text-muted">{description}</p>}</div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>}
    <div className="p-5">{children}</div>
  </section>
}

export function PageHeader({ title, description, actions }) {
  return <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
    <div><h1 className="text-2xl font-semibold tracking-tight text-white sm:text-[28px]">{title}</h1>{description && <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{description}</p>}</div>
    {actions && <div className="flex items-center gap-2">{actions}</div>}
  </div>
}

export function EmptyState({ title, description, action }) {
  return <div className="flex min-h-40 flex-col items-center justify-center rounded-xl border border-dashed border-soft px-5 py-8 text-center">
    <div className="mb-3 grid h-10 w-10 place-items-center rounded-full bg-slate-800 text-blue-300" aria-hidden="true">—</div>
    <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
    {description && <p className="mt-1 max-w-lg text-sm leading-6 text-muted">{description}</p>}
    {action && <div className="mt-4">{action}</div>}
  </div>
}

export function ErrorNotice({ error, onRetry }) {
  if (!error) return null
  const message = typeof error === 'string' ? error : error.message || '请求失败，请稍后重试。'
  return <div role="alert" className="alert border border-rose-400/25 bg-rose-950/40 text-rose-100">
    <span>{message}</span>{onRetry && <button type="button" className="btn btn-sm btn-outline border-rose-300/40" onClick={onRetry}>重试</button>}
  </div>
}

const statusStyles = {
  completed: 'badge-success', published: 'badge-success', parsed: 'badge-success', REVIEWABLE: 'badge-success',
  running: 'badge-info', EVALUATING: 'badge-info', queued: 'badge-info', draft: 'badge-warning',
  failed: 'badge-error', FAILED: 'badge-error', BLOCKED: 'badge-error', stale: 'badge-warning',
}
export function StatusBadge({ value }) {
  const label = value == null || value === '' ? '未知' : String(value)
  return <span className={`badge badge-sm capitalize ${statusStyles[label] || 'badge-ghost'}`}>{label.replaceAll('_', ' ')}</span>
}

export function Loading({ label = '正在加载…' }) {
  return <div className="flex items-center gap-3 py-8 text-sm text-muted" role="status"><span className="loading loading-spinner loading-sm text-blue-400" />{label}</div>
}

function useDialog(onClose, containerRef) {
  const closeRef = useRef(onClose)
  closeRef.current = onClose
  useEffect(() => {
    const previous = document.activeElement
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const focusables = () => containerRef.current?.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])') || []
    const first = focusables()[0]
    first?.focus()
    const keydown = event => {
      if (event.key === 'Escape') { event.stopPropagation(); closeRef.current?.(); return }
      if (event.key !== 'Tab') return
      const items = [...focusables()].filter(item => item.offsetParent !== null)
      if (!items.length) { event.preventDefault(); containerRef.current?.focus(); return }
      const firstItem = items[0], lastItem = items[items.length - 1]
      if (event.shiftKey && (document.activeElement === firstItem || !containerRef.current?.contains(document.activeElement))) { event.preventDefault(); lastItem.focus() }
      else if (!event.shiftKey && document.activeElement === lastItem) { event.preventDefault(); firstItem.focus() }
    }
    document.addEventListener('keydown', keydown)
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener('keydown', keydown); previous?.focus?.() }
  }, [containerRef])
}

export function Modal({ title, onClose, children }) {
  const ref = useRef(null)
  useDialog(onClose, ref)
  return <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/75 p-4 backdrop-blur-sm" onMouseDown={event => { if (event.target === event.currentTarget) onClose?.() }}>
    <section ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title} className="workbench-panel max-h-[min(88vh,900px)] w-full max-w-2xl overflow-auto shadow-2xl">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-soft bg-[#111d30] px-5 py-4"><h2 className="text-base font-semibold text-white">{title}</h2><button type="button" className="btn btn-sm btn-ghost" aria-label="关闭弹窗" onClick={onClose}>✕</button></header>
      <div className="p-5">{children}</div>
    </section>
  </div>
}

export function Drawer({ title, onClose, children }) {
  const ref = useRef(null)
  useDialog(onClose, ref)
  return <div className="fixed inset-0 z-50 bg-slate-950/65" onMouseDown={event => { if (event.target === event.currentTarget) onClose?.() }}>
    <section ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title} className="absolute inset-y-0 right-0 flex w-full max-w-2xl flex-col border-l border-soft bg-[#0d1829] shadow-2xl">
      <header className="flex items-center justify-between border-b border-soft px-5 py-4"><h2 className="text-base font-semibold text-white">{title}</h2><button type="button" className="btn btn-sm btn-ghost" aria-label="关闭详情" onClick={onClose}>✕</button></header>
      <div className="min-h-0 flex-1 overflow-y-auto p-5">{children}</div>
    </section>
  </div>
}
