import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { pipelineApi, productsApi, riskAlertsApi, type RiskAlertItem } from '../api/config'
import { useNotificationContext } from '../context/NotificationContext'
import DailyBrief from '../components/DailyBrief'

const QUICK_ACTIONS = [
  { label: '进入对话工作台', desc: '开始合规咨询与系统交互', to: '/chat' },
  { label: '查看产品合规', desc: '按产品维度检查状态与阶段', to: '/products' },
  { label: '打开风险监控', desc: '查看预警、情报流与热力图', to: '/system/risk' },
  { label: '进入配置中心', desc: '管理 Agent、技能、工具与模型', to: '/config' },
]

const SEVERITY_TABS = [
  { key: '', label: '全部' },
  { key: 'critical', label: '严重' },
  { key: 'high', label: '高危' },
  { key: 'medium', label: '中危' },
  { key: 'low', label: '低危' },
] as const

const severityDot: Record<string, string> = {
  high: 'bg-[#DC2626]',
  medium: 'bg-[#D97706]',
  low: 'bg-[#16A34A]',
  critical: 'bg-[#B91C1C]',
}

function formatTime(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} 小时前`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days} 天前`
  return new Date(ts).toLocaleDateString('zh-CN')
}

function StatCard({ label, value, hint, tone = 'neutral' }: { label: string; value: React.ReactNode; hint: string; tone?: 'neutral' | 'blue' | 'amber' | 'red' | 'green' }) {
  const toneMap = {
    neutral: 'text-[#111827]',
    blue: 'text-[#1D4ED8]',
    amber: 'text-[#B45309]',
    red: 'text-[#B91C1C]',
    green: 'text-[#15803D]',
  }[tone]

  return (
    <div className="rounded-[24px] border border-black/[0.06] bg-white p-5 shadow-[0_12px_32px_rgba(15,23,42,0.04)]">
      <div className="text-sm font-medium text-[#6B7280]">{label}</div>
      <div className={`mt-3 text-[34px] font-semibold tracking-[-0.04em] ${toneMap}`}>{value}</div>
      <div className="mt-2 text-sm text-[#6B7280]">{hint}</div>
    </div>
  )
}

export default function OverviewPage() {
  const navigate = useNavigate()
  const { addToast } = useNotificationContext()
  const [productCount, setProductCount] = useState<number | null>(null)
  const [marketCount, setMarketCount] = useState<number | null>(null)
  const [overallScore, setOverallScore] = useState<number | null>(null)
  const [alerts, setAlerts] = useState<RiskAlertItem[]>([])
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [severityTab, setSeverityTab] = useState('')
  const [lastUpdated, setLastUpdated] = useState('')
  const refreshTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadData = useCallback(async () => {
    try {
      const results = await Promise.allSettled([
        productsApi.list(),
        pipelineApi.health(),
        riskAlertsApi.list({ size: 20 }),
      ])

      if (results[0].status === 'fulfilled') {
        const products = results[0].value
        setProductCount(products.length)
        const markets = new Set<string>()
        products.forEach((p: { target_markets?: string[] }) =>
          (p.target_markets ?? []).forEach(m => markets.add(m))
        )
        setMarketCount(markets.size)
      }
      if (results[1].status === 'fulfilled') {
        setOverallScore(Math.round(results[1].value.overall_score))
      }
      if (results[2].status === 'fulfilled') {
        setAlerts(results[2].value.alerts)
      }
      setLastUpdated(new Date().toLocaleTimeString('zh-CN'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
    return () => {
      if (refreshTimer.current) clearInterval(refreshTimer.current)
    }
  }, [loadData])

  useEffect(() => {
    if (autoRefresh) {
      refreshTimer.current = setInterval(loadData, 30000)
    } else if (refreshTimer.current) {
      clearInterval(refreshTimer.current)
      refreshTimer.current = null
    }
    return () => {
      if (refreshTimer.current) clearInterval(refreshTimer.current)
    }
  }, [autoRefresh, loadData])

  const activeAlerts = alerts.filter(a => !a.dismissed)
  const filtered = severityTab ? activeAlerts.filter(a => a.severity === severityTab) : activeAlerts
  const highCount = alerts.filter(a => (a.severity === 'high' || a.severity === 'critical') && !a.dismissed).length

  const handleDismiss = async (alertId: string) => {
    try {
      await riskAlertsApi.dismiss(alertId)
      setAlerts(prev => prev.map(a => (a.id === alertId ? { ...a, dismissed: true } : a)))
      addToast({ severity: 'low', title: '预警已忽略' })
    } catch {
      addToast({ severity: 'high', title: '操作失败', message: '后端不可用' })
    }
  }

  return (
    <div className="flex-1 overflow-y-auto bg-[#F4F6F8]">
      <div className="mx-auto max-w-[1380px] px-6 py-8">
        <section className="rounded-[28px] border border-black/[0.06] bg-[linear-gradient(135deg,#111827_0%,#1F2937_60%,#334155_100%)] px-7 py-7 text-white shadow-[0_24px_60px_rgba(15,23,42,0.18)]">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div className="max-w-[720px]">
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white/60">daily overview</div>
              <h1 className="mt-3 text-[40px] font-semibold tracking-[-0.05em] leading-[1.02]">跨境合规全局视图</h1>
              <p className="mt-4 max-w-[64ch] text-[15px] leading-7 text-white/72">
                在一个页面里查看产品规模、覆盖市场、系统通过率和待处理风险。先判断系统状态，再进入具体工作流。
              </p>
              <div className="mt-5 text-sm text-white/60">
                {lastUpdated ? `最近更新于 ${lastUpdated}` : '正在加载最新数据'}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <label className="inline-flex h-11 items-center gap-2 rounded-full border border-white/12 bg-white/8 px-4 text-sm text-white/78">
                <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} className="accent-white" />
                30 秒自动刷新
              </label>
              <button
                onClick={() => {
                  setLoading(true)
                  loadData()
                }}
                className="inline-flex h-11 items-center justify-center rounded-full bg-white px-5 text-sm font-semibold text-[#111827] transition hover:-translate-y-[1px] hover:bg-[#F8FAFC]"
              >
                立即刷新
              </button>
            </div>
          </div>
        </section>

        <section className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard label="覆盖市场" value={loading ? '--' : (marketCount ?? 0)} hint="已纳入合规管理的目标国家或地区" tone="blue" />
          <StatCard label="活跃产品" value={loading ? '--' : (productCount ?? 0)} hint="当前存在生命周期状态的产品数量" tone="neutral" />
          <StatCard label="合规通过率" value={loading ? '--' : `${overallScore ?? 0}%`} hint="基于系统健康度计算的总通过率" tone={overallScore !== null && overallScore >= 80 ? 'green' : overallScore !== null && overallScore >= 60 ? 'amber' : 'red'} />
          <StatCard label="待处理预警" value={loading ? '--' : activeAlerts.length} hint={highCount > 0 ? `${highCount} 条高危以上预警待处理` : '当前没有高危预警'} tone={highCount > 0 ? 'red' : 'green'} />
        </section>

        <section className="mt-6 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-6">
            <div className="rounded-[24px] border border-black/[0.06] bg-white p-5 shadow-[0_12px_32px_rgba(15,23,42,0.04)]">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#94A3B8]">quick actions</div>
                  <h2 className="mt-2 text-[22px] font-semibold tracking-[-0.04em] text-[#111827]">快速入口</h2>
                </div>
              </div>
              <div className="mt-5 grid gap-3 md:grid-cols-2">
                {QUICK_ACTIONS.map(action => (
                  <button
                    key={action.to}
                    onClick={() => navigate(action.to)}
                    className="rounded-[20px] border border-black/[0.06] bg-[#F8FAFC] p-4 text-left transition hover:-translate-y-[1px] hover:border-black/[0.12] hover:bg-white"
                  >
                    <div className="text-[15px] font-semibold text-[#111827]">{action.label}</div>
                    <div className="mt-2 text-sm leading-6 text-[#6B7280]">{action.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-[24px] border border-black/[0.06] bg-white p-5 shadow-[0_12px_32px_rgba(15,23,42,0.04)]">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#94A3B8]">alerts</div>
                  <h2 className="mt-2 text-[22px] font-semibold tracking-[-0.04em] text-[#111827]">近期预警</h2>
                </div>
                <button onClick={() => navigate('/system/risk')} className="text-sm font-medium text-[#2563EB] hover:underline">
                  查看全部
                </button>
              </div>

              {activeAlerts.length > 0 && (
                <div className="mt-5 flex flex-wrap gap-2">
                  {SEVERITY_TABS.map(tab => (
                    <button
                      key={tab.key}
                      onClick={() => setSeverityTab(tab.key)}
                      className={`h-9 rounded-full px-3.5 text-xs font-medium transition ${severityTab === tab.key ? 'bg-[#111827] text-white' : 'bg-[#F3F4F6] text-[#6B7280] hover:bg-[#E5E7EB]'}`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              )}

              <div className="mt-5">
                {loading ? (
                  <div className="rounded-[20px] border border-dashed border-black/[0.08] px-4 py-10 text-center text-sm text-[#6B7280]">正在加载预警</div>
                ) : activeAlerts.length === 0 ? (
                  <div className="rounded-[20px] border border-dashed border-black/[0.08] px-4 py-10 text-center text-sm text-[#6B7280]">暂无预警，系统运行正常</div>
                ) : filtered.length === 0 ? (
                  <div className="rounded-[20px] border border-dashed border-black/[0.08] px-4 py-10 text-center text-sm text-[#6B7280]">当前筛选条件下没有预警</div>
                ) : (
                  <div className="overflow-hidden rounded-[20px] border border-black/[0.06]">
                    {filtered.slice(0, 8).map(a => (
                      <div key={a.id} className="flex items-center gap-3 border-b border-black/[0.06] px-4 py-3 last:border-b-0">
                        <span className={`h-2.5 w-2.5 rounded-full ${severityDot[a.severity] || 'bg-[#94A3B8]'}`} />
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium text-[#111827]">{a.title}</div>
                          {a.message && <div className="mt-1 truncate text-xs text-[#6B7280]">{a.message}</div>}
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-[#9CA3AF]">{formatTime(a.created_at)}</span>
                          <button onClick={() => handleDismiss(a.id)} className="text-xs font-medium text-[#6B7280] hover:text-[#111827]">
                            忽略
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          <DailyBrief className="h-fit rounded-[24px] border border-black/[0.06] bg-white shadow-[0_12px_32px_rgba(15,23,42,0.04)]" />
        </section>
      </div>
    </div>
  )
}
