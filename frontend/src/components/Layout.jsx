import { useState } from 'react'
import { Drawer } from './ui'

const navigation = [
  { group: '工作区', items: [
    ['/overview', '工作台概览', '⌂'], ['/assets', '论文资产', '▤'], ['/rubrics', '官方评分标准', '▦'],
  ] },
  { group: '评审流程', items: [
    ['/models', '模型配置', '⚙'], ['/create', '创建评审', '+'], ['/tasks', '评审任务', '◷'], ['/history', '历史与审计', '≡'],
  ] },
]

function NavLinks({ path, onNavigate }) {
  return <nav aria-label="主导航" className="space-y-6">
    {navigation.map(group => <div key={group.group}>
      <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-[.16em] text-slate-500">{group.group}</p>
      <div className="space-y-1">{group.items.map(([href, label, icon]) => {
        const active = path === href || (href === '/tasks' && path.startsWith('/reviews/'))
        return <a key={href} href={`#${href}`} onClick={onNavigate} aria-current={active ? 'page' : undefined} className={`group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${active ? 'bg-blue-500/15 font-medium text-blue-200 ring-1 ring-inset ring-blue-400/20' : 'text-slate-400 hover:bg-slate-800/70 hover:text-slate-100'}`}>
          <span aria-hidden="true" className={`grid h-5 w-5 place-items-center text-base ${active ? 'text-blue-300' : 'text-slate-500 group-hover:text-slate-300'}`}>{icon}</span>{label}
        </a>
      })}</div>
    </div>)}
  </nav>
}

export default function Layout({ children, path }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const closeMenu = () => setMobileOpen(false)
  return <div data-theme="nightwork" className="workbench min-h-screen text-slate-100">
    <aside className="sidebar fixed inset-y-0 left-0 z-30 hidden w-[250px] flex-col px-4 py-5 md:flex">
      <Brand />
      <div className="mt-9 flex-1"><NavLinks path={path} /></div>
      <div className="border-t border-soft pt-4"><p className="text-xs text-slate-500">本地评审工作区</p><p className="mt-1 text-xs text-slate-600">数学建模论文评审智能体</p></div>
    </aside>
    {mobileOpen && <Drawer title="工作区导航" onClose={closeMenu}>
      <Brand /><div className="mt-6"><NavLinks path={path} onNavigate={closeMenu} /></div>
    </Drawer>}
    <div className="min-h-screen md:pl-[250px]">
      <header className="sticky top-0 z-20 flex h-[68px] items-center justify-between border-b border-soft bg-[#0b1424]/90 px-4 backdrop-blur-xl sm:px-6 lg:px-8">
        <div className="flex items-center gap-3"><button className="btn btn-sm btn-ghost md:hidden" onClick={() => setMobileOpen(true)} aria-label="打开导航">☰</button><div className="hidden text-xs text-slate-500 sm:block">评审工作区 <span className="px-1.5 text-slate-700">/</span> <span className="text-slate-300">{navigation.flatMap(g => g.items).find(([href]) => href === path)?.[1] || (path.startsWith('/reviews/') ? '评审详情' : '工作台概览')}</span></div></div>
        <div className="flex items-center gap-3"><span className="hidden rounded-full border border-soft px-3 py-1.5 text-xs text-slate-400 sm:inline-flex">本地优先</span><span className="grid h-8 w-8 place-items-center rounded-full border border-blue-400/25 bg-blue-500/10 text-xs font-semibold text-blue-200" aria-label="数学建模评审">数</span></div>
      </header>
      <main className="workbench-main subtle-grid min-h-[calc(100vh-68px)] p-5 sm:p-7 lg:p-9">{children}</main>
      <footer className="border-t border-soft px-5 py-4 text-center text-xs text-slate-600 md:ml-0">数学建模论文评审智能体</footer>
    </div>
  </div>
}

function Brand() {
  return <a href="#/overview" className="flex min-w-0 items-center gap-3" aria-label="返回工作台概览">
    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-blue-300/20 bg-gradient-to-br from-blue-500/25 to-cyan-500/10 text-sm font-bold text-blue-200">M</span>
    <span className="min-w-0"><span className="block truncate text-sm font-semibold tracking-wide text-slate-100">数学建模论文</span><span className="mt-0.5 block truncate text-xs text-slate-500">评审智能体</span></span>
  </a>
}
