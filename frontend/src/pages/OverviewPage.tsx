import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { pipelineApi, productsApi, riskAlertsApi, type RiskAlertItem } from '../api/config'
import { useNotificationContext } from '../context/NotificationContext'
import DailyBrief from '../components/DailyBrief'

const QUICK_ACTIONS = [
  { icon: '💬', label: '新建对话', desc: '开始合规咨询', to: '/chat' },
  { icon: '📦', label: '产品管理', desc: '查看产品合规状态', to: '/products' },
  { icon: '⇌', label: '系统合规', desc: '10阶段合规总览', to: '/compliance/system' },
  { icon: '⚙', label: '配置中心', desc: 'Agent/Skill/工具管理', to: '/config' },
]

const SEVERITY_TABS = [
  { key: '', label: '全部' },
  { key: 'critical', label: '严重', cls: 'text-[#FF3B30]' },
  { key: 'high', label: '高危', cls: 'text-[#FF3B30]' },
  { key: 'medium', label: '中危', cls: 'text-[#FF9500]' },
  { key: 'low', label: '低危', cls: 'text-[#34C759]' },
] as const

const severityDot: Record<string, string> = {
  high: 'bg-[#FF3B30]',
  medium: 'bg-[#FF9500]',
  low: 'bg-[#34C759]',
  critical: 'bg-[#FF3B30] ring-2 ring-[#FF3B30]/30',
}

function formatTime(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins}分钟前`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}小时前`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}天前`
  return new Date(ts).toLocaleDateString('zh-CN')
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
        // 计算去重目标市场数
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
  const filtered = severityTab
    ? activeAlerts.filter(a => a.severity === severityTab)
    : activeAlerts
  const highCount = alerts.filter(a => (a.severity === 'high' || a.severity === 'critical') && !a.dismissed).length

  const handleDismiss = async (alertId: string) => {
    try {
      await riskAlertsApi.dismiss(alertId)
      setAlerts(prev => prev.map(a =>
        a.id === alertId ? { ...a, dismissed: true } : a
      ))
      addToast({ severity: 'low', title: '预警已忽略' })
    } catch {
      addToast({ severity: 'high', title: '操作失败', message: '后端不可用' })
    }
  }

  const scoreColor = overallScore !== null
    ? overallScore >= 80 ? 'text-[#34C759]' : overallScore >= 60 ? 'text-[#FF9500]' : 'text-[#FF3B30]'
    : 'text-[#1D1D1F]'

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Title */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-[#1D1D1F]">概览</h1>
            <p className="text-sm text-[#86868B] mt-1">
              跨境合规全局视图
              {lastUpdated && <span className="ml-2">· 更新 {lastUpdated}</span>}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 text-xs text-[#86868B] cursor-pointer">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={e => setAutoRefresh(e.target.checked)}
                className="w-3 h-3"
              />
              30s 自动
            </label>
            <button
              onClick={() => { setLoading(true); loadData() }}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-[#F5F5F7] text-[#86868B] hover:bg-[#E5E5EA] transition-colors"
            >
              刷新
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-black/6 p-4">
            <div className="flex items-start justify-between mb-2">
              <div className="text-xs text-[#86868B]">覆盖市场</div>
              <span className="text-sm">🌍</span>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-2xl font-semibold text-[#1D1D1F]">
                {loading ? '...' : marketCount !== null ? marketCount : 0}
              </span>
              <span className="text-sm text-[#86868B]">国</span>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-black/6 p-4">
            <div className="flex items-start justify-between mb-2">
              <div className="text-xs text-[#86868B]">活跃产品</div>
              <span className="text-sm">📦</span>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-2xl font-semibold text-[#1D1D1F]">
                {loading ? '...' : productCount ?? 0}
              </span>
              <span className="text-sm text-[#86868B]">个</span>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-black/6 p-4">
            <div className="flex items-start justify-between mb-2">
              <div className="text-xs text-[#86868B]">合规通过率</div>
              <span className="text-sm">📊</span>
            </div>
            <div className="flex items-baseline gap-1">
              <span className={`text-2xl font-semibold ${scoreColor}`}>
                {loading ? '...' : overallScore ?? 0}
              </span>
              <span className="text-sm text-[#86868B]">%</span>
            </div>
            {overallScore !== null && (
              <div className="mt-2 h-1.5 bg-[#F5F5F7] rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    overallScore >= 80 ? 'bg-[#34C759]' : overallScore >= 60 ? 'bg-[#FF9500]' : 'bg-[#FF3B30]'
                  }`}
                  style={{ width: `${overallScore}%` }}
                />
              </div>
            )}
          </div>
          <div className="bg-white rounded-xl border border-black/6 p-4">
            <div className="flex items-start justify-between mb-2">
              <div className="text-xs text-[#86868B]">待处理预警</div>
              <span className={`text-sm ${highCount > 0 ? '' : ''}`}>⚠</span>
            </div>
            <div className={`text-2xl font-semibold ${highCount > 0 ? 'text-[#FF3B30]' : 'text-[#1D1D1F]'}`}>
              {loading ? '...' : activeAlerts.length}
            </div>
            {highCount > 0 && (
              <div className="text-xs text-[#FF3B30] mt-1">
                {highCount} 条高危
              </div>
            )}
          </div>
        </div>

        {/* Quick Actions + DailyBrief */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="col-span-2">
            <h2 className="text-sm font-semibold text-[#1D1D1F] mb-3">快速入口</h2>
            <div className="grid grid-cols-2 gap-3">
              {QUICK_ACTIONS.map(a => (
                <button
                  key={a.to}
                  onClick={() => navigate(a.to)}
                  className="p-4 rounded-xl border border-black/6 bg-white hover:border-[#0071E3]/30 hover:shadow-sm transition-all text-left"
                >
                  <div className="text-2xl mb-2">{a.icon}</div>
                  <div className="font-medium text-sm text-[#1D1D1F]">{a.label}</div>
                  <div className="text-xs text-[#86868B] mt-0.5">{a.desc}</div>
                </button>
              ))}
            </div>
          </div>
          <DailyBrief />
        </div>

        {/* Recent Events */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-[#1D1D1F]">
              近期预警
              {!loading && activeAlerts.length > 0 && (
                <span className="ml-2 text-xs text-[#86868B] font-normal">{activeAlerts.length} 条未处理</span>
              )}
            </h2>
            <button
              onClick={() => navigate('/system/risk')}
              className="text-xs text-[#0071E3] hover:underline"
            >
              查看全部 →
            </button>
          </div>

          {/* Severity filter tabs */}
          {activeAlerts.length > 0 && (
            <div className="flex items-center gap-1 mb-3">
              {SEVERITY_TABS.map(tab => (
                <button
                  key={tab.key}
                  onClick={() => setSeverityTab(tab.key)}
                  className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                    severityTab === tab.key
                      ? 'bg-[#1D1D1F] text-white'
                      : 'bg-[#F5F5F7] text-[#86868B] hover:bg-[#E5E5EA]'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          )}

          {loading ? (
            <div className="bg-white rounded-xl border border-black/6 p-8 text-center text-sm text-[#86868B]">加载中...</div>
          ) : activeAlerts.length === 0 ? (
            <div className="bg-white rounded-xl border border-black/6 p-8 text-center">
              <div className="text-3xl mb-2">✅</div>
              <div className="text-sm text-[#86868B]">暂无预警，系统运行正常</div>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-black/6 divide-y divide-black/6">
              {filtered.length === 0 ? (
                <div className="px-4 py-6 text-center text-sm text-[#86868B]">该等级暂无预警</div>
              ) : (
                filtered.slice(0, 10).map(a => (
                  <div key={a.id} className="px-4 py-3 flex items-center gap-3 group">
                    <div className={`w-2 h-2 rounded-full shrink-0 ${severityDot[a.severity] || 'bg-[#86868B]'}`} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-[#1D1D1F] truncate">{a.title}</div>
                      {a.message && (
                        <div className="text-xs text-[#86868B] truncate mt-0.5">{a.message}</div>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[11px] text-[#C7C7CC]">{formatTime(a.created_at)}</span>
                      <button
                        onClick={() => handleDismiss(a.id)}
                        className="text-[10px] px-1.5 py-0.5 rounded text-[#86868B] opacity-0 group-hover:opacity-100 hover:bg-[#F5F5F7] transition-all"
                      >
                        忽略
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
