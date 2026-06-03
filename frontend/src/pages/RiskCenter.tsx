import { useState, useEffect, useCallback, useRef } from 'react'
import { riskAlertsApi, type RiskAlertItem } from '../api/config'
import { useNotificationContext } from '../context/NotificationContext'

interface MarketInfo {
  code: string
  alerts: number
}

interface MarketStatus {
  last_scan: string
  active_alerts: number
  markets: MarketInfo[]
}

const SEVERITY_TABS = [
  { key: '', label: '全部' },
  { key: 'critical', label: '严重', cls: 'bg-[#FF3B30]/10 text-[#FF3B30]' as const },
  { key: 'high', label: '高危', cls: 'bg-[#FF3B30]/10 text-[#FF3B30]' as const },
  { key: 'medium', label: '中危', cls: 'bg-[#FF9500]/10 text-[#FF9500]' as const },
  { key: 'low', label: '低危', cls: 'bg-[#34C759]/10 text-[#34C759]' as const },
] as const

function severityLabel(sev: string) {
  const found = SEVERITY_TABS.find(t => t.key === sev)
  if (!found || !('cls' in found)) return { label: sev, cls: 'bg-[#86868B]/10 text-[#86868B]' }
  return { label: found.label, cls: found.cls }
}

export default function RiskCenter() {
  const [alerts, setAlerts] = useState<RiskAlertItem[]>([])
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(null)
  const [scanning, setScanning] = useState(false)
  const [scanStatus, setScanStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [severityTab, setSeverityTab] = useState('')
  const [lastUpdated, setLastUpdated] = useState('')
  const { addToast } = useNotificationContext()
  const refreshTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadData = useCallback(async () => {
    try {
      const [alertRes, marketRes] = await Promise.all([
        riskAlertsApi.list({ size: 50 }),
        riskAlertsApi.getMarketStatus().catch(() => null),
      ])
      setAlerts(alertRes.alerts)
      if (marketRes) {
        setMarketStatus(marketRes)
      }
      setLastUpdated(new Date().toLocaleTimeString('zh-CN'))
    } catch {
      /* ignore */
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

  const handleScan = async () => {
    setScanning(true)
    setScanStatus('正在触发扫描...')
    try {
      const res = await riskAlertsApi.triggerScan()
      if (res.status === 'completed') {
        setScanStatus('扫描已触发，等待结果...')
        setTimeout(async () => {
          await loadData()
          setScanStatus('')
          setScanning(false)
        }, 3000)
      } else {
        setScanStatus('触发失败')
        setScanning(false)
      }
    } catch {
      setScanStatus('扫描服务不可用')
      setScanning(false)
    }
  }

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

  const activeAlerts = alerts.filter(a => !a.dismissed)
  const filtered = severityTab
    ? activeAlerts.filter(a => a.severity === severityTab)
    : activeAlerts
  const highCount = activeAlerts.filter(a => a.severity === 'high' || a.severity === 'critical').length

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Title */}
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-[#1D1D1F]">风险监控中心</h1>
              <p className="text-sm text-[#86868B] mt-1">
                实时监控与手动扫描
                {lastUpdated && <span className="ml-2">· 更新 {lastUpdated}</span>}
                {marketStatus?.last_scan && ` · 最近扫描: ${new Date(marketStatus.last_scan).toLocaleString('zh-CN')}`}
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
              <button
                onClick={handleScan}
                disabled={scanning}
                className="px-4 py-2 text-sm font-semibold rounded-lg bg-[#1D1D1F] text-white hover:bg-[#2D2D2F] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {scanning ? '扫描中...' : '立即扫描'}
              </button>
            </div>
          </div>
        </div>

        {/* Scan status */}
        {scanStatus && (
          <div className="mb-4 px-4 py-2.5 rounded-lg bg-[#F5F5F7] text-sm text-[#86868B] flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#0071E3] animate-pulse" />
            {scanStatus}
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-black/6 p-4">
            <div className="flex items-start justify-between mb-2">
              <div className="text-xs text-[#86868B]">活跃预警</div>
              <span className="text-sm">⚠</span>
            </div>
            <div className="text-2xl font-semibold text-[#1D1D1F]">{activeAlerts.length}</div>
          </div>
          <div className="bg-white rounded-xl border border-black/6 p-4">
            <div className="flex items-start justify-between mb-2">
              <div className="text-xs text-[#86868B]">高危预警</div>
              <span className={`text-sm ${highCount > 0 ? '' : ''}`}>🔴</span>
            </div>
            <div className={`text-2xl font-semibold ${highCount > 0 ? 'text-[#FF3B30]' : 'text-[#34C759]'}`}>
              {highCount}
            </div>
          </div>
          <div className="bg-white rounded-xl border border-black/6 p-4">
            <div className="flex items-start justify-between mb-2">
              <div className="text-xs text-[#86868B]">总预警</div>
              <span className="text-sm">📋</span>
            </div>
            <div className="text-2xl font-semibold text-[#1D1D1F]">{alerts.length}</div>
          </div>
          <div className="bg-white rounded-xl border border-black/6 p-4">
            <div className="flex items-start justify-between mb-2">
              <div className="text-xs text-[#86868B]">覆盖市场</div>
              <span className="text-sm">🌍</span>
            </div>
            <div className="text-2xl font-semibold text-[#1D1D1F]">{marketStatus?.markets.length ?? '-'}</div>
          </div>
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

        {/* Alerts list */}
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-[#1D1D1F] mb-3">
            预警列表
            {filtered.length > 0 && (
              <span className="ml-2 text-xs text-[#86868B] font-normal">{filtered.length} 条</span>
            )}
          </h2>
          {loading ? (
            <div className="bg-white rounded-xl border border-black/6 p-8 text-center text-sm text-[#86868B]">
              加载中...
            </div>
          ) : filtered.length === 0 ? (
            <div className="bg-white rounded-xl border border-black/6 p-8 text-center text-sm text-[#86868B]">
              {alerts.length === 0 ? '暂无预警' : '该等级暂无预警'}
            </div>
          ) : (
            <div className="space-y-2">
              {filtered.map(a => {
                const sv = severityLabel(a.severity)
                return (
                  <div
                    key={a.id}
                    className={`flex items-center justify-between px-4 py-3 rounded-xl bg-white border border-black/6 group ${
                      a.dismissed ? 'opacity-50' : ''
                    }`}
                  >
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <div className={`w-2 h-2 rounded-full shrink-0 ${
                        a.severity === 'critical' || a.severity === 'high'
                          ? 'bg-[#FF3B30]'
                          : a.severity === 'medium'
                          ? 'bg-[#FF9500]'
                          : 'bg-[#34C759]'
                      }`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <div className={`text-sm truncate ${a.dismissed ? 'text-[#86868B]' : 'text-[#1D1D1F] font-medium'}`}>
                            {a.title}
                          </div>
                          <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded shrink-0 ${sv.cls}`}>
                            {sv.label}
                          </span>
                        </div>
                        {a.message && (
                          <div className="text-xs text-[#86868B] mt-0.5 truncate">{a.message}</div>
                        )}
                      </div>
                      <span className="text-[11px] text-[#C7C7CC] shrink-0">
                        {new Date(a.created_at).toLocaleDateString('zh-CN')}
                      </span>
                    </div>
                    {!a.dismissed && (
                      <button
                        onClick={() => handleDismiss(a.id)}
                        className="shrink-0 ml-2 px-2.5 py-1 text-xs text-[#86868B] rounded-md border border-black/10 hover:bg-[#F5F5F7] transition-colors"
                      >
                        忽略
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Market status */}
        {marketStatus && (
          <div>
            <h2 className="text-sm font-semibold text-[#1D1D1F] mb-3">市场监控状态</h2>
            <div className="bg-white rounded-xl border border-black/6 p-4">
              {marketStatus.markets.length === 0 ? (
                <div className="text-center py-4 text-sm text-[#86868B]">暂无市场监控数据</div>
              ) : (
                <div className="flex gap-3 flex-wrap">
                  {marketStatus.markets.map(m => {
                    const hasAlerts = m.alerts > 0
                    return (
                      <div
                        key={m.code}
                        className={`flex-1 min-w-[80px] rounded-lg px-3 py-2.5 text-center border ${
                          hasAlerts ? 'bg-[#FFF5F5] border-[#FF3B30]/20' : 'bg-[#F5F5F7] border-transparent'
                        }`}
                      >
                        <div className="text-sm font-semibold text-[#1D1D1F]">{m.code.toUpperCase()}</div>
                        <div className={`text-[11px] mt-0.5 ${hasAlerts ? 'text-[#FF3B30]' : 'text-[#86868B]'}`}>
                          {m.alerts} 条预警
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
