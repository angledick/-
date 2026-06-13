/**
 * 风险监控中心 — 完整版
 *
 * Tab 1  情报流     主动检索 + 历史情报 + LLM 分析展示
 * Tab 2  关键词     CRUD + 周期配置 + 执行历史
 * Tab 3  预警列表   AI 触发预警 + 传统预警 + 溯源
 * Tab 4  热力图     三域分布 + 趋势 + 市场排行
 * Tab 5  扫描监控   市场覆盖矩阵 + 手动触发 + 分析队列
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  riskIntelApi, riskAlertsApi,
  type RiskIntelItem, type RiskIntelKeyword, type RiskIntelRun,
  type RiskHeatmap, type RiskAlertItem, type LlmAnalysis,
} from '../api/config'
import { useWebSocketContext } from '../context/WebSocketContext'

const DOMAIN = {
  tariff:   { label: '关税',  icon: '🛃', color: '#D97706', bg: '#FEF3C7', ring: '#FDE68A' },
  conflict: { label: '冲突',  icon: '⚔️', color: '#DC2626', bg: '#FEF2F2', ring: '#FCA5A5' },
  financial:{ label: '金融',  icon: '📈', color: '#2563EB', bg: '#EFF6FF', ring: '#93C5FD' },
} as const

const SEV = {
  critical: { label: '极高', dot: 'bg-red-500',     chip: 'bg-red-50 text-red-600 ring-1 ring-red-200' },
  high:     { label: '高危', dot: 'bg-red-400',     chip: 'bg-red-50 text-red-500 ring-1 ring-red-100' },
  medium:   { label: '中危', dot: 'bg-amber-400',   chip: 'bg-amber-50 text-amber-600 ring-1 ring-amber-200' },
  low:      { label: '低危', dot: 'bg-emerald-400', chip: 'bg-emerald-50 text-emerald-600 ring-1 ring-emerald-200' },
} as const

const CRON_OPTIONS = [
  { label: '每 2 小时', value: '0 */2 * * *' },
  { label: '每 4 小时', value: '0 */4 * * *' },
  { label: '每 6 小时', value: '0 */6 * * *' },
  { label: '每 12 小时', value: '0 */12 * * *' },
  { label: '每天早 9 时', value: '0 9 * * *' },
]

function cx(...a: (string | false | null | undefined)[]) { return a.filter(Boolean).join(' ') }

function Spinner({ size = 'sm' }: { size?: 'xs' | 'sm' }) {
  return (
    <svg className={cx(size === 'xs' ? 'w-3 h-3' : 'w-4 h-4', 'animate-spin text-current')} viewBox="0 0 24 24" fill="none">
      <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
    </svg>
  )
}

function SevBadge({ severity }: { severity: string }) {
  const m = SEV[severity as keyof typeof SEV] ?? { label: severity, dot: 'bg-gray-300', chip: 'bg-gray-50 text-gray-500 ring-1 ring-gray-200' }
  return (
    <span className={cx('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold', m.chip)}>
      <span className={cx('w-1.5 h-1.5 rounded-full', m.dot)}/>{m.label}
    </span>
  )
}

function DomainTag({ domain, compact = false }: { domain?: string | null; compact?: boolean }) {
  if (!domain || !(domain in DOMAIN)) return null
  const m = DOMAIN[domain as keyof typeof DOMAIN]
  return (
    <span className={cx('inline-flex items-center rounded-full font-medium border', compact ? 'gap-0.5 px-1.5 py-0.5 text-[10px]' : 'gap-1 px-2 py-0.5 text-[11px]')}
      style={{ color: m.color, background: m.bg, borderColor: m.ring }}>
      {m.icon} {m.label}
    </span>
  )
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = score >= 0.8 ? '#EF4444' : score >= 0.6 ? '#F59E0B' : score >= 0.35 ? '#10B981' : '#9CA3AF'
  return (
    <span className="inline-flex items-center gap-1.5 shrink-0">
      <span className="w-14 h-1.5 rounded-full bg-gray-100 overflow-hidden block">
        <span className="h-full rounded-full block" style={{ width: `${pct}%`, background: color }}/>
      </span>
      <span className="text-[11px] font-mono tabular-nums w-6" style={{ color }}>{pct}</span>
    </span>
  )
}

function Ago({ iso }: { iso?: string | null }) {
  if (!iso) return <span className="text-[11px] text-gray-400">—</span>
  try {
    const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
    const t = m < 1 ? '刚刚' : m < 60 ? `${m}m` : m < 1440 ? `${Math.floor(m / 60)}h` : `${Math.floor(m / 1440)}d`
    return <span className="text-[11px] text-gray-400 tabular-nums">{t}</span>
  } catch { return <span className="text-[11px] text-gray-400">—</span> }
}

function EmptyTip({ icon, title, sub }: { icon: string; title: string; sub?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-14 gap-2 text-center">
      <span className="text-3xl">{icon}</span>
      <p className="text-sm font-medium text-gray-500">{title}</p>
      {sub && <p className="text-xs text-gray-400 max-w-xs">{sub}</p>}
    </div>
  )
}

// ── LLM 分析卡 ────────────────────────────────────────────────────────────────

function LlmCard({ analysis, pending = false }: { analysis?: LlmAnalysis | null; pending?: boolean }) {
  if (pending) return (
    <div className="mt-3 rounded-2xl border border-dashed border-violet-200 bg-violet-50/60 px-4 py-3 flex items-center gap-2.5">
      <span className="text-violet-500"><Spinner size="xs"/></span>
      <span className="text-xs text-violet-600 font-medium">AI 正在深度分析，结果将实时推送…</span>
    </div>
  )
  if (!analysis) return (
    <div className="mt-3 rounded-2xl border border-dashed border-gray-200 bg-gray-50 px-4 py-3 text-center">
      <p className="text-xs text-gray-400">尚未经过 AI 深度分析</p>
    </div>
  )
  return (
    <div className="mt-3 rounded-2xl border border-violet-100 bg-gradient-to-b from-violet-50/80 to-white overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-violet-100">
        <span className="text-[11px] text-violet-500">✦</span>
        <span className="text-[10px] font-bold tracking-widest text-violet-500 uppercase">AI 深度分析</span>
        {analysis.confidence != null && (
          <span className="ml-auto text-[10px] text-violet-400">置信度 {Math.round(analysis.confidence * 100)}%</span>
        )}
      </div>
      <div className="divide-y divide-violet-50 px-4">
        {analysis.summary && (
          <div className="py-2.5">
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-1">事件概述</p>
            <p className="text-sm leading-relaxed text-gray-700">{analysis.summary}</p>
          </div>
        )}
        {analysis.impact && (
          <div className="py-2.5">
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-1">跨境影响</p>
            <p className="text-sm leading-relaxed text-gray-600">{analysis.impact}</p>
          </div>
        )}
        {analysis.actions && analysis.actions.length > 0 && (
          <div className="py-2.5">
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-2">建议行动</p>
            <ol className="space-y-1.5">
              {analysis.actions.map((a, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-violet-100 text-[11px] font-bold text-violet-600">{i+1}</span>
                  <span className="text-sm text-gray-700">{a}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </div>
  )
}

// ── 情报行 ────────────────────────────────────────────────────────────────────

function IntelRow({ item: init }: { item: RiskIntelItem }) {
  const [open, setOpen] = useState(false)
  const [item, setItem] = useState(init)
  const [analyzing, setAnalyzing] = useState(false)

  useEffect(() => { setItem(init) }, [init])

  const analyzed = item.llm_analyzed === 1
  const llm = item.llm_analysis

  const handleAnalyze = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (analyzing || analyzed) return
    setAnalyzing(true)
    try { await riskIntelApi.analyzeItem(item.id) } catch { setAnalyzing(false) }
  }

  return (
    <div className="border-b border-gray-100 last:border-0">
      <button className="w-full text-left px-4 py-3.5 hover:bg-gray-50/70 transition-colors" onClick={() => setOpen(v => !v)}>
        <div className="flex items-start gap-3">
          <div className="shrink-0 pt-0.5 space-y-1.5 min-w-[80px]">
            <DomainTag domain={item.risk_domain} compact/>
            <SevBadge severity={item.severity}/>
          </div>
          <div className="flex-1 min-w-0">
            <p className={cx('text-[13.5px] font-medium text-gray-800 leading-snug', !open && 'line-clamp-2')}>
              {item.headline_summary || item.title}
            </p>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              {item.affected_markets.slice(0, 5).map(m => (
                <span key={m} className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">{m}</span>
              ))}
              {item.affected_hs_codes.slice(0, 3).map(h => (
                <span key={h} className="text-[10px] bg-blue-50 text-blue-500 px-1.5 py-0.5 rounded">HS {h}</span>
              ))}
              {item.jin10_important === 1 && <span className="text-[10px] bg-red-50 text-red-500 px-1.5 py-0.5 rounded font-medium">重要</span>}
              {item.alert_id && <span className="text-[10px] bg-amber-50 text-amber-600 px-1.5 py-0.5 rounded font-medium">⚡ 已预警</span>}
              {analyzed ? (
                <span className="text-[10px] bg-violet-50 text-violet-600 px-1.5 py-0.5 rounded font-semibold">✦ AI 已分析</span>
              ) : analyzing ? (
                <span className="text-[10px] text-violet-500 flex items-center gap-0.5"><Spinner size="xs"/> 分析中</span>
              ) : (
                <button onClick={handleAnalyze} className="text-[10px] text-gray-400 border border-dashed border-gray-300 px-1.5 py-0.5 rounded hover:border-violet-400 hover:text-violet-500 transition-colors">✦ AI 分析</button>
              )}
            </div>
            {open && (
              <div className="mt-3">
                {llm ? <LlmCard analysis={llm}/> : analyzing ? <LlmCard pending/> : (
                  item.summary && <p className="text-xs text-gray-500 leading-relaxed border-l-2 border-gray-200 pl-3">{item.summary}</p>
                )}
                <div className="mt-3 pt-3 border-t border-gray-100 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-gray-400">
                  <span>{item.source_name}</span>
                  {item.risk_category && <span>{item.risk_category}</span>}
                  {item.jin10_channel?.length ? <span>金十 ch{item.jin10_channel.join(',')}</span> : null}
                  {item.url && item.url !== 'https://www.jin10.com/' && (
                    <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline" onClick={e => e.stopPropagation()}>原文 ↗</a>
                  )}
                  {llm?.analyzed_at && <span className="ml-auto text-violet-400">AI 分析 <Ago iso={llm.analyzed_at}/></span>}
                </div>
              </div>
            )}
          </div>
          <div className="shrink-0 flex flex-col items-end gap-1.5 pt-0.5">
            <ScoreBar score={item.risk_score}/>
            <Ago iso={item.pub_time || item.collected_at}/>
          </div>
        </div>
      </button>
    </div>
  )
}

// ── Tab 1: 情报流 ─────────────────────────────────────────────────────────────

function FeedPanel() {
  const [items, setItems] = useState<RiskIntelItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [domain, setDomain] = useState('')
  const [sev, setSev] = useState('')
  const [hours, setHours] = useState(168)
  const [jin10, setJin10] = useState(false)
  const [imp, setImp] = useState(false)
  const [kw, setKw] = useState('')
  const [kwBusy, setKwBusy] = useState(false)
  const [kwMsg, setKwMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [analyzeStats, setAnalyzeStats] = useState<{ total: number; done: number; pending: number } | null>(null)
  const [triggering, setTriggering] = useState(false)
  const { on: wsOn } = useWebSocketContext()

  const load = useCallback(async (p = 1) => {
    setLoading(true)
    try {
      const [feed, stats] = await Promise.all([
        riskIntelApi.getFeed({ q: q || undefined, domain: domain || undefined, severity: sev || undefined, hours, jin10_only: jin10 || undefined, important_only: imp || undefined, page: p, size: 20 }),
        riskIntelApi.getAnalyzeStatus().catch(() => null),
      ])
      setItems(feed.items); setTotal(feed.total); setPage(p)
      if (stats) setAnalyzeStats(stats)
    } finally { setLoading(false) }
  }, [q, domain, sev, hours, jin10, imp])

  useEffect(() => { load(1) }, [load])

  useEffect(() => {
    const off = wsOn('intel_analyzed', (msg) => {
      const p = msg.payload as any
      setItems(prev => prev.map(i => i.id === p?.intel_id ? {
        ...i, llm_analyzed: 1,
        llm_analysis: p?.llm_analysis ?? i.llm_analysis,
        risk_score: p?.risk_score ?? i.risk_score,
        severity: p?.severity ?? i.severity,
        headline_summary: p?.headline_summary ?? i.headline_summary,
      } : i))
      riskIntelApi.getAnalyzeStatus().then(setAnalyzeStats).catch(() => {})
    })
    return off
  }, [wsOn])

  const handleSearch = async () => {
    if (!kw.trim()) return
    setKwBusy(true); setKwMsg(null)
    try {
      const r = await riskIntelApi.search(kw.trim(), domain || undefined)
      setKwMsg({ ok: true, text: `采集 ${r.total_found} 条 · 新增 ${r.items_new} 条 · 触发预警 ${r.alerts_triggered} 条` })
      await load(1)
    } catch { setKwMsg({ ok: false, text: '检索失败，请稍后重试' }) }
    finally { setKwBusy(false) }
  }

  const handleTriggerAnalyze = async () => {
    setTriggering(true)
    try {
      await riskIntelApi.triggerAnalyze(20, 0)
      setKwMsg({ ok: true, text: '已提交 AI 分析批次，结果将实时推送到列表' })
    } finally { setTriggering(false) }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50 to-white p-4 space-y-3">
        <p className="text-xs font-bold uppercase tracking-widest text-blue-400">主动检索 <span className="text-[10px] text-gray-400 font-normal ml-1">— 联网采集实时情报并触发 AI 分析</span></p>
        <div className="flex gap-2">
          <input value={kw} onChange={e => setKw(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="输入关键词，如「美国加征关税」「OFAC 制裁」「汽车出海」…"
            className="flex-1 h-10 px-3.5 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-400/30 focus:border-blue-400 transition"/>
          <button onClick={handleSearch} disabled={kwBusy || !kw.trim()}
            className="h-10 px-5 text-sm font-semibold rounded-xl bg-gray-900 text-white hover:bg-gray-700 disabled:opacity-40 transition flex items-center gap-2">
            {kwBusy ? <><Spinner/>检索中</> : '立即检索'}
          </button>
          <button onClick={handleTriggerAnalyze} disabled={triggering}
            className="h-10 px-4 text-sm font-medium rounded-xl border border-violet-200 bg-violet-50 text-violet-600 hover:bg-violet-100 disabled:opacity-40 transition flex items-center gap-1.5">
            {triggering ? <Spinner/> : '✦'} AI 分析
          </button>
        </div>
        {kwMsg && <p className={cx('text-xs font-medium', kwMsg.ok ? 'text-emerald-600' : 'text-red-500')}>{kwMsg.text}</p>}
      </div>

      {analyzeStats && analyzeStats.pending > 0 && (
        <div className="flex items-center gap-2.5 rounded-xl border border-violet-100 bg-violet-50 px-3.5 py-2.5 text-xs text-violet-700">
          <Spinner size="xs"/><span>AI 分析队列 · <strong>{analyzeStats.pending}</strong> 条等待 · <strong>{analyzeStats.done}</strong> 条完成 / {analyzeStats.total} 总计</span>
        </div>
      )}
      {analyzeStats && analyzeStats.pending === 0 && analyzeStats.done > 0 && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-100 bg-emerald-50 px-3.5 py-2.5 text-xs text-emerald-700">
          <span>✦</span><span>全部 <strong>{analyzeStats.done}</strong> 条情报已完成 AI 深度分析</span>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && load(1)}
          placeholder="全文搜索历史情报…"
          className="h-8 w-40 px-3 text-xs bg-white rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-400/20 transition"/>
        {(['', 'tariff', 'conflict', 'financial'] as const).map(d => (
          <button key={d} onClick={() => setDomain(d)}
            className={cx('h-8 px-3 text-xs font-medium rounded-lg border transition', domain === d ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-500 border-gray-200 hover:border-gray-400')}>
            {d === '' ? '全部' : DOMAIN[d].icon + ' ' + DOMAIN[d].label}
          </button>
        ))}
        <span className="w-px h-5 bg-gray-200"/>
        {(['', 'critical', 'high', 'medium'] as const).map(s => (
          <button key={s} onClick={() => setSev(s)}
            className={cx('h-8 px-3 text-xs font-medium rounded-lg border transition', sev === s ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-500 border-gray-200 hover:border-gray-400')}>
            {s === '' ? '全危' : SEV[s].label}
          </button>
        ))}
        <select value={hours} onChange={e => setHours(+e.target.value)} className="h-8 px-2 text-xs bg-white rounded-lg border border-gray-200 focus:outline-none text-gray-600">
          <option value={24}>24h</option><option value={72}>3天</option><option value={168}>7天</option><option value={720}>30天</option>
        </select>
        <label className="flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer"><input type="checkbox" checked={jin10} onChange={e => setJin10(e.target.checked)} className="accent-blue-500"/>仅金十</label>
        <label className="flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer"><input type="checkbox" checked={imp} onChange={e => setImp(e.target.checked)} className="accent-amber-500"/>仅重要</label>
        <button onClick={() => load(1)} className="ml-auto h-8 px-3 text-xs bg-white rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition">刷新</button>
      </div>

      <p className="text-xs text-gray-400">共 <strong className="text-gray-700">{total}</strong> 条情报</p>

      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-14 gap-2 text-gray-400"><Spinner/><span className="text-sm">加载中</span></div>
        ) : items.length === 0 ? (
          <EmptyTip icon="📭" title="暂无情报" sub="输入关键词点击「立即检索」开始采集"/>
        ) : (
          items.map(item => <IntelRow key={item.id} item={item}/>)
        )}
      </div>

      {total > 20 && (
        <div className="flex items-center justify-center gap-3">
          <button disabled={page <= 1} onClick={() => load(page - 1)} className="h-8 px-4 text-xs rounded-lg border border-gray-200 text-gray-500 disabled:opacity-40 hover:bg-gray-50 transition">← 上一页</button>
          <span className="text-xs text-gray-400">第 {page} / {Math.ceil(total / 20)} 页</span>
          <button disabled={page * 20 >= total} onClick={() => load(page + 1)} className="h-8 px-4 text-xs rounded-lg border border-gray-200 text-gray-500 disabled:opacity-40 hover:bg-gray-50 transition">下一页 →</button>
        </div>
      )}
    </div>
  )
}

// ── Tab 2: 关键词 ─────────────────────────────────────────────────────────────

function KeywordsPanel() {
  const [keywords, setKeywords] = useState<RiskIntelKeyword[]>([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [running, setRunning] = useState<Record<string, boolean>>({})
  const [runMsg, setRunMsg] = useState<Record<string, string>>({})
  const [historyId, setHistoryId] = useState<string | null>(null)
  const [history, setHistory] = useState<RiskIntelRun[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [suggestions, setSuggestions] = useState<{ keyword: string; domain: string }[]>([])
  const [form, setForm] = useState({ keyword: '', label: '', domain: 'all', periodic: false, cron: '0 */6 * * *', custom: false })
  const [saving, setSaving] = useState(false)
  const [formErr, setFormErr] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try { setKeywords(await riskIntelApi.listKeywords()) } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleAdd = async () => {
    if (!form.keyword.trim()) { setFormErr('关键词不能为空'); return }
    setSaving(true); setFormErr('')
    try {
      await riskIntelApi.addKeyword({ keyword: form.keyword.trim(), label: form.label || undefined, domain: form.domain, periodic_enabled: form.periodic, cron_expr: form.cron })
      setAdding(false); setForm({ keyword: '', label: '', domain: 'all', periodic: false, cron: '0 */6 * * *', custom: false })
      await load()
    } catch (e: any) { setFormErr(e.message || '添加失败') } finally { setSaving(false) }
  }

  const handleRun = async (kw: RiskIntelKeyword) => {
    setRunning(r => ({ ...r, [kw.id]: true })); setRunMsg(m => ({ ...m, [kw.id]: '触发中…' }))
    try {
      await riskIntelApi.runKeyword(kw.id)
      setRunMsg(m => ({ ...m, [kw.id]: '✓ 已触发' }))
    } catch { setRunMsg(m => ({ ...m, [kw.id]: '触发失败' })) }
    finally {
      setRunning(r => ({ ...r, [kw.id]: false }))
      setTimeout(() => setRunMsg(m => { const n = { ...m }; delete n[kw.id]; return n }), 4000)
    }
  }

  const handleToggle = async (kw: RiskIntelKeyword) => {
    await riskIntelApi.updateKeyword(kw.id, { periodic_enabled: kw.periodic_enabled ? 0 : 1 } as any)
    await load()
  }

  const showHistory = async (id: string) => {
    if (historyId === id) { setHistoryId(null); return }
    setHistoryId(id); setHistoryLoading(true)
    try { setHistory(await riskIntelApi.getRuns(id)) } finally { setHistoryLoading(false) }
  }

  const loadSuggestions = async () => {
    const r = await riskIntelApi.suggestKeywords(['US', 'EU', 'CN'], ['tariff', 'conflict', 'financial'])
    setSuggestions(r.suggestions.slice(0, 12))
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <button onClick={() => setAdding(a => !a)} className="h-9 px-4 text-sm font-semibold rounded-xl bg-gray-900 text-white hover:bg-gray-700 transition">+ 新增关键词</button>
        <button onClick={loadSuggestions} className="h-9 px-4 text-sm rounded-xl border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 transition">💡 系统推荐</button>
        <span className="ml-auto text-xs text-gray-400">{keywords.length} 个关键词</span>
      </div>

      {adding && (
        <div className="rounded-2xl border border-blue-100 bg-blue-50/40 p-4 space-y-3">
          <p className="text-sm font-semibold text-gray-700">新增监控关键词</p>
          <div className="grid grid-cols-2 gap-2">
            <input value={form.keyword} onChange={e => setForm(f => ({ ...f, keyword: e.target.value }))} placeholder="关键词（必填）"
              className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-400/30 transition"/>
            <input value={form.label} onChange={e => setForm(f => ({ ...f, label: e.target.value }))} placeholder="备注标签（可选）"
              className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-400/30 transition"/>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select value={form.domain} onChange={e => setForm(f => ({ ...f, domain: e.target.value }))} className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none">
              <option value="all">全部域</option><option value="tariff">🛃 关税</option><option value="conflict">⚔️ 冲突</option><option value="financial">📈 金融</option>
            </select>
            <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
              <span className={cx('relative flex w-9 h-5 rounded-full transition-colors cursor-pointer', form.periodic ? 'bg-emerald-500' : 'bg-gray-200')}
                onClick={() => setForm(f => ({ ...f, periodic: !f.periodic }))}>
                <span className={cx('absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform', form.periodic ? 'translate-x-4' : 'translate-x-0.5')}/>
              </span>
              周期检索
            </label>
            {form.periodic && (
              <>
                <select value={form.custom ? 'custom' : form.cron}
                  onChange={e => e.target.value === 'custom' ? setForm(f => ({ ...f, custom: true })) : setForm(f => ({ ...f, cron: e.target.value, custom: false }))}
                  className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none">
                  {CRON_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  <option value="custom">自定义…</option>
                </select>
                {form.custom && (
                  <input value={form.cron} onChange={e => setForm(f => ({ ...f, cron: e.target.value }))} placeholder="cron 表达式"
                    className="h-9 w-36 px-3 text-xs font-mono bg-white rounded-xl border border-gray-200 focus:outline-none"/>
                )}
              </>
            )}
          </div>
          {formErr && <p className="text-xs text-red-500">{formErr}</p>}
          <div className="flex gap-2">
            <button onClick={handleAdd} disabled={saving || !form.keyword.trim()}
              className="h-9 px-5 text-sm font-semibold rounded-xl bg-gray-900 text-white hover:bg-gray-700 disabled:opacity-40 transition flex items-center gap-1.5">
              {saving ? <><Spinner/>保存中</> : '保存'}
            </button>
            <button onClick={() => setAdding(false)} className="h-9 px-5 text-sm rounded-xl border border-gray-200 bg-white text-gray-500 hover:bg-gray-50 transition">取消</button>
          </div>
        </div>
      )}

      {suggestions.length > 0 && (
        <div className="rounded-2xl border border-gray-200 bg-white p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-bold text-gray-400 uppercase tracking-wide">系统推荐</p>
            <button onClick={() => setSuggestions([])} className="text-[10px] text-gray-400 hover:text-gray-600">关闭</button>
          </div>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s, i) => (
              <button key={i} onClick={async () => { await riskIntelApi.addKeyword({ keyword: s.keyword, domain: s.domain }); await load(); setSuggestions(p => p.filter((_, j) => j !== i)) }}
                className="inline-flex items-center gap-1 h-7 px-3 text-xs rounded-full border border-gray-200 bg-white text-gray-600 hover:border-blue-400 hover:text-blue-600 transition">
                <DomainTag domain={s.domain} compact/>{s.keyword}<span className="text-gray-300">+</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12 gap-2 text-gray-400"><Spinner/><span className="text-sm">加载中</span></div>
      ) : keywords.length === 0 ? (
        <EmptyTip icon="🔑" title="还没有关键词" sub="点击「新增关键词」或「系统推荐」开始监控"/>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden divide-y divide-gray-100">
          {keywords.map(kw => (
            <div key={kw.id}>
              <div className="px-4 py-3.5 flex items-center gap-3">
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-gray-800">{kw.keyword}</span>
                    {kw.label && <span className="text-xs text-gray-400">({kw.label})</span>}
                    {kw.domain !== 'all' && <DomainTag domain={kw.domain} compact/>}
                    {kw.auto_suggested === 1 && <span className="text-[10px] bg-purple-50 text-purple-500 px-1.5 py-0.5 rounded-full">推荐</span>}
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-xs text-gray-400">
                    {kw.periodic_enabled ? <span className="text-emerald-600 font-medium">⏱ {kw.cron_expr}</span> : <span>手动模式</span>}
                    <span>执行 <strong className="text-gray-600">{kw.total_runs}</strong></span>
                    <span>预警 <strong className="text-red-500">{kw.total_hits}</strong></span>
                    {kw.last_run_at && <span>上次 <Ago iso={kw.last_run_at}/></span>}
                    {runMsg[kw.id] && <span className="text-emerald-600 font-medium">{runMsg[kw.id]}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button onClick={() => showHistory(kw.id)}
                    className={cx('h-7 px-2.5 text-xs rounded-lg border transition', historyId === kw.id ? 'border-blue-400 bg-blue-50 text-blue-600' : 'border-gray-200 text-gray-400 hover:border-blue-300 hover:text-blue-500')}>
                    历史
                  </button>
                  <button onClick={() => handleToggle(kw)}
                    className={cx('relative flex w-9 h-5 rounded-full transition-colors', kw.periodic_enabled ? 'bg-emerald-500' : 'bg-gray-200')}>
                    <span className={cx('absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-transform', kw.periodic_enabled ? 'translate-x-4' : 'translate-x-0.5')}/>
                  </button>
                  <button onClick={() => handleRun(kw)} disabled={running[kw.id]}
                    className="h-7 px-2.5 text-xs rounded-lg border border-gray-200 text-gray-600 hover:border-blue-300 hover:text-blue-500 disabled:opacity-40 transition whitespace-nowrap">
                    {running[kw.id] ? '执行中' : '▶ 执行'}
                  </button>
                  <button onClick={async () => { if (!confirm('确认删除？')) return; await riskIntelApi.deleteKeyword(kw.id); await load() }}
                    className="h-7 w-7 flex items-center justify-center rounded-lg text-gray-300 hover:text-red-400 hover:bg-red-50 transition">✕</button>
                </div>
              </div>
              {historyId === kw.id && (
                <div className="bg-gray-50 border-t border-gray-100 px-4 py-3">
                  {historyLoading ? (
                    <div className="flex items-center gap-2 text-xs text-gray-400"><Spinner size="xs"/>加载历史…</div>
                  ) : history.length === 0 ? (
                    <p className="text-xs text-gray-400">暂无执行记录</p>
                  ) : (
                    <div className="space-y-1.5">
                      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-2">最近执行记录</p>
                      {history.slice(0, 8).map(r => (
                        <div key={r.id} className="flex items-center gap-3 text-xs">
                          <span className={cx('font-medium w-5', r.status === 'done' ? 'text-emerald-600' : r.status === 'failed' ? 'text-red-500' : 'text-amber-500')}>
                            {r.status === 'done' ? '✓' : r.status === 'failed' ? '✗' : '…'}
                          </span>
                          <span className="text-gray-500 w-10">{r.run_type === 'manual' ? '手动' : '定时'}</span>
                          <span className="text-gray-500">采集 <strong>{r.items_found}</strong> · 新增 <strong>{r.items_new}</strong> · 预警 <strong className="text-red-500">{r.alerts_created}</strong></span>
                          <span className="ml-auto text-gray-400"><Ago iso={r.created_at}/></span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Tab 3: 预警列表 ───────────────────────────────────────────────────────────

function AlertsPanel() {
  const [alerts, setAlerts] = useState<RiskAlertItem[]>([])
  const [loading, setLoading] = useState(true)
  const [sev, setSev] = useState('')
  const [type, setType] = useState('')
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(async () => {
    try { const r = await riskAlertsApi.list({ size: 60 }); setAlerts(r.alerts) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    load()
    timer.current = setInterval(load, 30000)
    return () => { if (timer.current) clearInterval(timer.current) }
  }, [load])

  const dismiss = async (id: string) => {
    await riskAlertsApi.dismiss(id)
    setAlerts(prev => prev.map(a => a.id === id ? { ...a, dismissed: true } : a))
  }

  const active = alerts.filter(a => !a.dismissed)
  const high = active.filter(a => ['high', 'critical'].includes(a.severity)).length
  const intelCount = active.filter(a => (a as any).alert_type === 'risk_intel').length
  const shown = active.filter(a => !sev || a.severity === sev).filter(a => !type || (a as any).alert_type === type)

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: '活跃预警', val: active.length, color: 'text-gray-800' },
          { label: '高危 / 极高', val: high, color: 'text-red-500' },
          { label: 'AI 情报预警', val: intelCount, color: 'text-violet-600' },
          { label: '全部（含已忽略）', val: alerts.length, color: 'text-gray-400' },
        ].map(s => (
          <div key={s.label} className="bg-white rounded-2xl border border-gray-200 px-4 py-3">
            <p className="text-xs text-gray-400">{s.label}</p>
            <p className={cx('text-2xl font-bold mt-1.5', s.color)}>{s.val}</p>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {(['', 'critical', 'high', 'medium', 'low'] as const).map(s => (
          <button key={s} onClick={() => setSev(s)}
            className={cx('h-8 px-3 text-xs font-medium rounded-lg border transition', sev === s ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-500 border-gray-200 hover:border-gray-400')}>
            {s === '' ? '全部' : SEV[s].label}
          </button>
        ))}
        <span className="w-px h-5 bg-gray-200"/>
        <button onClick={() => setType('')} className={cx('h-8 px-3 text-xs rounded-lg border transition', !type ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-500 border-gray-200 hover:border-gray-400')}>全部</button>
        <button onClick={() => setType('risk_intel')} className={cx('h-8 px-3 text-xs rounded-lg border transition', type === 'risk_intel' ? 'bg-violet-600 text-white border-violet-600' : 'bg-white text-gray-500 border-gray-200 hover:border-violet-400')}>✦ AI 情报</button>
        <button onClick={load} className="ml-auto h-8 px-3 text-xs bg-white rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition">刷新</button>
      </div>
      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden divide-y divide-gray-100">
        {loading ? (
          <div className="flex items-center justify-center py-12 gap-2 text-gray-400"><Spinner/><span className="text-sm">加载中</span></div>
        ) : shown.length === 0 ? (
          <EmptyTip icon="✅" title="暂无预警" sub="系统运行正常"/>
        ) : shown.map(a => (
          <div key={a.id} className={cx('px-4 py-3.5 flex items-start gap-3', a.dismissed && 'opacity-40')}>
            <span className={cx('mt-1.5 w-2 h-2 rounded-full shrink-0', ['critical','high'].includes(a.severity) ? 'bg-red-400' : a.severity === 'medium' ? 'bg-amber-400' : 'bg-emerald-400')}/>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={cx('text-sm font-medium', a.dismissed ? 'text-gray-400 line-through' : 'text-gray-800')}>{a.title}</span>
                <SevBadge severity={a.severity}/>
                {(a as any).alert_type === 'risk_intel' && <span className="text-[10px] bg-violet-50 text-violet-600 px-1.5 py-0.5 rounded-full font-semibold">✦ AI 情报</span>}
              </div>
              {(a as any).description && <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">{(a as any).description}</p>}
              <div className="flex items-center gap-3 mt-1 text-[11px] text-gray-300">
                {(a as any).source && <span>{(a as any).source}</span>}
                <span>{new Date(a.created_at).toLocaleString('zh-CN')}</span>
              </div>
            </div>
            {!a.dismissed && (
              <button onClick={() => dismiss(a.id)} className="shrink-0 h-7 px-3 text-xs rounded-lg border border-gray-200 text-gray-400 hover:bg-gray-50 hover:text-gray-600 transition">忽略</button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Tab 4: 热力图 ─────────────────────────────────────────────────────────────

function HeatmapPanel() {
  const [data, setData] = useState<RiskHeatmap | null>(null)
  const [hours, setHours] = useState(168)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    riskIntelApi.getHeatmap(hours).then(setData).catch(() => {}).finally(() => setLoading(false))
  }, [hours])

  if (loading) return <div className="flex items-center justify-center py-16 gap-2 text-gray-400"><Spinner/><span className="text-sm">加载中</span></div>
  if (!data) return <EmptyTip icon="📊" title="暂无数据"/>

  const total = Object.values(data.by_domain).reduce((s, d) => s + d.count, 0)
  const trend7 = data.trend.slice(-7).reverse()

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-400">时间窗口</span>
        {([72, 168, 720] as const).map(h => (
          <button key={h} onClick={() => setHours(h)}
            className={cx('h-8 px-3 text-xs font-medium rounded-lg border transition', hours === h ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-500 border-gray-200 hover:border-gray-400')}>
            {h === 72 ? '3天' : h === 168 ? '7天' : '30天'}
          </button>
        ))}
        <span className="ml-auto text-[11px] text-gray-400">更新 <Ago iso={data.generated_at}/></span>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {(['tariff', 'conflict', 'financial'] as const).map(d => {
          const m = DOMAIN[d]; const s = data.by_domain[d]
          const pct = s ? Math.round(s.count / Math.max(total, 1) * 100) : 0
          return (
            <div key={d} className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
              <div className="px-4 pt-4 pb-3">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-2xl">{m.icon}</span>
                  <span className="text-sm font-semibold text-gray-700">{m.label}风险</span>
                  <span className="ml-auto text-xs text-gray-400">{pct}%</span>
                </div>
                <p className="text-3xl font-bold" style={{ color: m.color }}>{s?.count ?? '—'}</p>
                {s && (
                  <div className="mt-2 space-y-1 text-xs text-gray-400">
                    <div className="flex justify-between"><span>高危以上</span><strong className="text-red-500">{(s.critical ?? 0) + (s.high ?? 0)}</strong></div>
                    <div className="flex justify-between"><span>平均分</span><strong className="text-gray-600">{Math.round((s.avg_score ?? 0) * 100)}</strong></div>
                  </div>
                )}
              </div>
              <div className="h-1 bg-gray-100"><div className="h-full" style={{ width: `${pct}%`, background: m.color }}/></div>
            </div>
          )
        })}
      </div>

      <div className="grid grid-cols-2 gap-4">
        {trend7.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-200 p-4">
            <p className="text-xs font-bold text-gray-400 uppercase tracking-wide mb-3">7 日趋势</p>
            <div className="space-y-2">
              {trend7.map((row, i) => {
                const tot = (row.tariff ?? 0) + (row.conflict ?? 0) + (row.financial ?? 0)
                const max = Math.max(...trend7.map(r => (r.tariff ?? 0) + (r.conflict ?? 0) + (r.financial ?? 0)), 1)
                return (
                  <div key={i} className="flex items-center gap-2">
                    <span className="text-[11px] text-gray-400 w-10">{(row.date ?? '').slice(5)}</span>
                    <div className="flex-1 h-4 rounded-full bg-gray-100 overflow-hidden flex">
                      {(['tariff', 'conflict', 'financial'] as const).map(d => {
                        const v = (row[d] ?? 0) / max * 100
                        return v > 0 ? <div key={d} className="h-full" style={{ width: `${v}%`, background: DOMAIN[d].color }}/> : null
                      })}
                    </div>
                    <span className="text-[11px] text-gray-500 w-6 text-right tabular-nums">{tot}</span>
                  </div>
                )
              })}
            </div>
            <div className="mt-3 flex items-center gap-3">
              {(['tariff', 'conflict', 'financial'] as const).map(d => (
                <span key={d} className="flex items-center gap-1 text-[10px] text-gray-400">
                  <span className="w-2 h-2 rounded-full" style={{ background: DOMAIN[d].color }}/>{DOMAIN[d].label}
                </span>
              ))}
            </div>
          </div>
        )}
        {data.top_markets.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-200 p-4">
            <p className="text-xs font-bold text-gray-400 uppercase tracking-wide mb-3">高频市场 Top 8</p>
            <div className="space-y-2">
              {data.top_markets.slice(0, 8).map(m => {
                const max = data.top_markets[0]?.count ?? 1
                return (
                  <div key={m.market} className="flex items-center gap-2">
                    <span className="text-xs font-mono w-7 text-gray-500">{m.market}</span>
                    <div className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
                      <div className="h-full rounded-full bg-blue-400" style={{ width: `${m.count / max * 100}%` }}/>
                    </div>
                    <span className="text-xs text-gray-400 w-6 text-right tabular-nums">{m.count}</span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {data.latest_critical.length > 0 && (
        <div className="rounded-2xl border border-red-100 bg-red-50/60 p-4">
          <p className="text-xs font-bold text-red-400 uppercase tracking-wide mb-3">🚨 最新极高风险</p>
          <div className="space-y-3">
            {data.latest_critical.slice(0, 4).map(item => (
              <div key={item.id} className="flex items-start gap-2">
                <DomainTag domain={item.risk_domain} compact/>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-gray-700 line-clamp-2">{item.headline_summary || item.title}</p>
                  <div className="flex items-center gap-2 mt-0.5 text-[11px] text-gray-400"><span>{item.source_name}</span><Ago iso={item.collected_at}/></div>
                </div>
                <ScoreBar score={item.risk_score}/>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Tab 5: 扫描监控 ───────────────────────────────────────────────────────────

function ScanPanel() {
  const [marketStatus, setMarketStatus] = useState<{ last_scan: string; active_alerts: number; markets: { code: string; alerts: number }[] } | null>(null)
  const [analyzeStats, setAnalyzeStats] = useState<{ total: number; done: number; pending: number; errors: number } | null>(null)
  const [scanning, setScanning] = useState(false)
  const [triggering, setTriggering] = useState(false)
  const [msg, setMsg] = useState('')

  const load = useCallback(async () => {
    const [mkt, stats] = await Promise.all([
      riskAlertsApi.getMarketStatus().catch(() => null),
      riskIntelApi.getAnalyzeStatus().catch(() => null),
    ])
    if (mkt) setMarketStatus(mkt)
    if (stats) setAnalyzeStats(stats)
  }, [])

  useEffect(() => { load() }, [load])

  const handleScan = async () => {
    setScanning(true); setMsg('正在触发市场扫描…')
    try {
      const r = await riskAlertsApi.triggerScan()
      setMsg(`扫描完成 · 新增预警 ${r.alerts_created} 条 · 发现事件 ${r.events_found} 条`)
      await load()
    } catch { setMsg('扫描服务暂不可用') } finally { setScanning(false) }
  }

  const handleAnalyze = async () => {
    setTriggering(true)
    try { await riskIntelApi.triggerAnalyze(20, 0); setMsg('AI 分析批次已提交'); await load() }
    catch { setMsg('提交失败') } finally { setTriggering(false) }
  }

  const pct = analyzeStats ? Math.round(analyzeStats.done / Math.max(analyzeStats.total, 1) * 100) : 0

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <button onClick={handleScan} disabled={scanning}
          className="h-9 px-5 text-sm font-semibold rounded-xl bg-gray-900 text-white hover:bg-gray-700 disabled:opacity-40 transition flex items-center gap-2">
          {scanning ? <><Spinner/>扫描中</> : '🔍 触发全市场扫描'}
        </button>
        <button onClick={handleAnalyze} disabled={triggering}
          className="h-9 px-4 text-sm font-medium rounded-xl border border-violet-200 bg-violet-50 text-violet-600 hover:bg-violet-100 disabled:opacity-40 transition flex items-center gap-1.5">
          {triggering ? <><Spinner/>提交中</> : '✦ 触发 AI 批量分析'}
        </button>
        <button onClick={load} className="h-9 px-4 text-sm rounded-xl border border-gray-200 bg-white text-gray-500 hover:bg-gray-50 transition">刷新</button>
        {msg && <span className="text-sm text-emerald-600 font-medium">{msg}</span>}
      </div>

      {analyzeStats && (
        <div className="bg-white rounded-2xl border border-gray-200 p-4">
          <p className="text-xs font-bold text-gray-400 uppercase tracking-wide mb-3">AI 分析队列</p>
          <div className="grid grid-cols-4 gap-3 mb-4">
            {[
              { label: '总情报', val: analyzeStats.total, color: 'text-gray-800' },
              { label: 'AI 已完成', val: analyzeStats.done, color: 'text-emerald-600' },
              { label: '待分析', val: analyzeStats.pending, color: 'text-amber-600' },
              { label: '分析失败', val: analyzeStats.errors, color: analyzeStats.errors > 0 ? 'text-red-500' : 'text-gray-400' },
            ].map(s => (
              <div key={s.label} className="text-center">
                <p className={cx('text-2xl font-bold', s.color)}>{s.val}</p>
                <p className="text-xs text-gray-400 mt-0.5">{s.label}</p>
              </div>
            ))}
          </div>
          <div>
            <div className="flex items-center justify-between mb-1.5 text-xs text-gray-400">
              <span>AI 分析完成率</span><span>{pct}%</span>
            </div>
            <div className="h-2.5 rounded-full bg-gray-100 overflow-hidden">
              <div className="h-full rounded-full bg-violet-500 transition-all duration-500" style={{ width: `${pct}%` }}/>
            </div>
          </div>
          {analyzeStats.errors > 0 && (
            <div className="mt-3 flex items-center gap-2 rounded-xl bg-red-50 border border-red-100 px-3 py-2 text-xs text-red-600">
              <span>⚠ {analyzeStats.errors} 条分析失败</span>
              <button onClick={handleAnalyze} className="ml-auto text-red-500 hover:text-red-700 font-medium">重试</button>
            </div>
          )}
        </div>
      )}

      <div className="bg-white rounded-2xl border border-gray-200 p-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-bold text-gray-400 uppercase tracking-wide">市场覆盖状态</p>
          {marketStatus?.last_scan && <span className="text-[11px] text-gray-400">最近扫描 <Ago iso={marketStatus.last_scan}/></span>}
        </div>
        {!marketStatus ? (
          <EmptyTip icon="🌍" title="加载中" />
        ) : marketStatus.markets.length === 0 ? (
          <EmptyTip icon="🌍" title="暂无市场数据" sub="触发全市场扫描后显示各市场状态"/>
        ) : (
          <>
            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2.5">
              {marketStatus.markets.map(m => {
                const level = m.alerts === 0 ? 'n' : m.alerts <= 2 ? 'w' : 'a'
                const cls = level === 'n' ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : level === 'w' ? 'bg-amber-50 border-amber-200 text-amber-700' : 'bg-red-50 border-red-200 text-red-600'
                const dot = level === 'n' ? 'bg-emerald-400' : level === 'w' ? 'bg-amber-400' : 'bg-red-400 animate-pulse'
                return (
                  <div key={m.code} className={cx('rounded-xl border px-3 py-2.5 text-center', cls)}>
                    <div className="flex items-center justify-center gap-1 mb-1">
                      <span className={cx('w-1.5 h-1.5 rounded-full', dot)}/>
                      <span className="text-sm font-bold">{m.code.toUpperCase()}</span>
                    </div>
                    <p className="text-xs">{m.alerts} 条预警</p>
                  </div>
                )
              })}
            </div>
            <div className="mt-3 pt-3 border-t border-gray-100 flex items-center gap-4 text-xs text-gray-400">
              <span>覆盖 <strong className="text-gray-700">{marketStatus.markets.length}</strong> 个市场</span>
              <span>活跃预警 <strong className="text-red-500">{marketStatus.active_alerts}</strong> 条</span>
            </div>
          </>
        )}
      </div>

      <div className="rounded-2xl border border-gray-100 bg-gray-50 p-4">
        <p className="text-xs font-bold text-gray-400 uppercase tracking-wide mb-3">自动调度任务</p>
        <div className="space-y-2">
          {[
            { name: 'AI 分析队列', freq: '每 15 分钟', desc: '处理 pending 情报，调用 glm-5.1 深度分析', color: 'bg-violet-400' },
            { name: '全域情报扫描', freq: '每 2 小时', desc: '三大域（关税/冲突/金融）全量采集', color: 'bg-blue-400' },
            { name: '关键词周期检索', freq: '每 6 小时', desc: '执行所有开启周期检索的用户关键词', color: 'bg-emerald-400' },
          ].map(t => (
            <div key={t.name} className="flex items-start gap-3 rounded-xl bg-white border border-gray-100 px-3.5 py-3">
              <span className={cx('mt-1.5 w-2 h-2 rounded-full shrink-0', t.color)}/>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-700">{t.name}</span>
                  <span className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">{t.freq}</span>
                </div>
                <p className="text-xs text-gray-400 mt-0.5">{t.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── 主页面 ────────────────────────────────────────────────────────────────────

type Tab = 'feed' | 'keywords' | 'alerts' | 'heatmap' | 'scan'

const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: 'feed',     label: '情报流',  icon: '📰' },
  { key: 'keywords', label: '关键词',  icon: '🔑' },
  { key: 'alerts',   label: '预警列表', icon: '⚠️' },
  { key: 'heatmap',  label: '热力图',  icon: '📊' },
  { key: 'scan',     label: '扫描监控', icon: '🔍' },
]

export default function RiskCenter() {
  const [tab, setTab] = useState<Tab>('feed')
  const [heatmap, setHeatmap] = useState<RiskHeatmap | null>(null)
  const [alertCount, setAlertCount] = useState<number | null>(null)
  const [analyzeStats, setAnalyzeStats] = useState<{ done: number; pending: number } | null>(null)
  const { on: wsOn } = useWebSocketContext()

  useEffect(() => {
    riskIntelApi.getHeatmap(168).then(setHeatmap).catch(() => {})
    riskAlertsApi.list({ size: 1 }).then(r => setAlertCount(r.alerts.filter((a: any) => !a.dismissed).length)).catch(() => {})
    riskIntelApi.getAnalyzeStatus().then(setAnalyzeStats).catch(() => {})
  }, [])

  useEffect(() => {
    const off = wsOn('intel_analyzed', () => { riskIntelApi.getAnalyzeStatus().then(setAnalyzeStats).catch(() => {}) })
    return off
  }, [wsOn])

  const totalItems = heatmap ? Object.values(heatmap.by_domain).reduce((s, d) => s + d.count, 0) : null
  const critHigh = heatmap ? Object.values(heatmap.by_domain).reduce((s, d) => s + (d.critical ?? 0) + (d.high ?? 0), 0) : null
  const avgScore = heatmap && totalItems ? Object.values(heatmap.by_domain).reduce((s, d) => s + d.avg_score * d.count, 0) / totalItems : null
  const topMarket = heatmap?.top_markets[0]?.market ?? null
  const llmPct = analyzeStats && analyzeStats.done + analyzeStats.pending > 0 ? Math.round(analyzeStats.done / (analyzeStats.done + analyzeStats.pending) * 100) : null

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50/40">
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">

        <div>
          <h1 className="text-xl font-bold text-gray-900">风险监控中心</h1>
          <p className="text-sm text-gray-400 mt-1">关税 · 冲突 · 金融 三大域 · 15+ 全球信源 · ZhipuAI glm-5.1 深度分析 · 实时推送</p>
        </div>

        {/* 顶部 5 卡指标 */}
        <div className="grid grid-cols-5 gap-3">
          {[
            { label: '近 7 天情报', val: totalItems != null ? String(totalItems) : '—', sub: '三大域合计', accent: 'text-gray-800' },
            { label: '高危 / 极高', val: critHigh != null ? String(critHigh) : '—', sub: 'score ≥ 0.6', accent: 'text-red-500' },
            { label: '平均风险分', val: avgScore != null ? String(Math.round(avgScore * 100)) : '—', sub: '全局均值', accent: 'text-amber-600' },
            { label: '高频市场', val: topMarket ?? '—', sub: '最多情报来源', accent: 'text-blue-600' },
            { label: 'AI 分析进度', val: llmPct != null ? `${llmPct}%` : '—', sub: analyzeStats ? `${analyzeStats.done} 已完成` : '加载中', accent: 'text-violet-600' },
          ].map(s => (
            <div key={s.label} className="bg-white rounded-2xl border border-gray-200 px-4 py-3.5">
              <p className="text-xs text-gray-400">{s.label}</p>
              <p className={cx('text-2xl font-bold mt-1.5 tabular-nums', s.accent)}>{s.val}</p>
              <p className="text-[11px] text-gray-400 mt-0.5">{s.sub}</p>
            </div>
          ))}
        </div>

        {/* Tab 容器 */}
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
          <div className="flex border-b border-gray-100 px-2 pt-1.5">
            {TABS.map(t => (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={cx('flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium rounded-t-xl transition-colors border-b-2 -mb-px',
                  tab === t.key ? 'border-blue-500 text-blue-600 bg-blue-50/50' : 'border-transparent text-gray-400 hover:text-gray-600')}>
                {t.icon} {t.label}
                {t.key === 'alerts' && alertCount != null && alertCount > 0 && (
                  <span className="ml-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">{alertCount > 9 ? '9+' : alertCount}</span>
                )}
                {t.key === 'scan' && analyzeStats?.pending != null && analyzeStats.pending > 0 && (
                  <span className="ml-1 flex h-4 w-4 items-center justify-center rounded-full bg-violet-500 text-[10px] font-bold text-white">{analyzeStats.pending > 9 ? '9+' : analyzeStats.pending}</span>
                )}
              </button>
            ))}
          </div>
          <div className="p-5">
            {tab === 'feed'     && <FeedPanel/>}
            {tab === 'keywords' && <KeywordsPanel/>}
            {tab === 'alerts'   && <AlertsPanel/>}
            {tab === 'heatmap'  && <HeatmapPanel/>}
            {tab === 'scan'     && <ScanPanel/>}
          </div>
        </div>

      </div>
    </div>
  )
}
