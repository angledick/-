import { useState, useEffect, useCallback } from 'react'
import type { RiskAlert, MarketStatus } from '../types'
import { useWebSocket } from '../hooks/useWebSocket'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import { EmptyState } from '@/components/common/EmptyState'
import { toast } from 'sonner'
import { AlertTriangle, Info, Plus, RefreshCw, Search, Shield, Store } from 'lucide-react'

const API_BASE = '/api/v1'
const USE_BACKEND_RISK = import.meta.env.VITE_STREAM_MODE !== 'mock'

const SEVERITY_CONFIG: Record<RiskAlert['severity'], { label: string; pillClass: string; dotClass: string; actionClass: string }> = {
  critical: {
    label: '红色',
    pillClass: 'border-red-200 bg-red-50 text-red-700 dark:border-red-900/70 dark:bg-red-950/30 dark:text-red-300',
    dotClass: 'bg-red-500',
    actionClass: 'bg-emerald-500 text-white hover:bg-emerald-600',
  },
  high: {
    label: '红色',
    pillClass: 'border-red-200 bg-red-50 text-red-700 dark:border-red-900/70 dark:bg-red-950/30 dark:text-red-300',
    dotClass: 'bg-red-500',
    actionClass: 'bg-emerald-500 text-white hover:bg-emerald-600',
  },
  medium: {
    label: '黄色',
    pillClass: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-300',
    dotClass: 'bg-amber-500',
    actionClass: 'border-border/70 bg-card text-foreground hover:bg-muted/60',
  },
  low: {
    label: '蓝色',
    pillClass: 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900/70 dark:bg-blue-950/30 dark:text-blue-300',
    dotClass: 'bg-blue-500',
    actionClass: 'border-border/70 bg-card text-foreground hover:bg-muted/60',
  },
}

const CONNECTED_STORES = [
  { name: 'Amazon US', region: 'US' },
  { name: 'Amazon UK', region: 'UK' },
  { name: 'Shopee SG', region: 'SG' },
]

const MOCK_ALERTS: RiskAlert[] = [
  {
    alert_id: 'mock_risk_001',
    alert_type: 'product_impacted',
    severity: 'high',
    title: 'WEEE 注册即将到期',
    description: 'LED 灯带德国 WEEE 注册 30 天后到期，需要续期或补充注册证明。',
    affected_products: ['LED 灯带'],
    affected_markets: ['德国'],
    source: 'certification_monitor',
    source_url: '',
    dismissed: false,
    created_at: String(Math.floor(Date.now() / 1000) - 720),
  },
  {
    alert_id: 'mock_risk_002',
    alert_type: 'product_impacted',
    severity: 'high',
    title: 'PSE 证书附件缺失',
    description: '锂离子电池组上架日本前缺少 PSE 证书附件，当前检查未通过。',
    affected_products: ['锂离子电池组'],
    affected_markets: ['日本'],
    source: 'compliance_checker',
    source_url: '',
    dismissed: false,
    created_at: String(Math.floor(Date.now() / 1000) - 3600),
  },
  {
    alert_id: 'mock_risk_003',
    alert_type: 'regulation_change',
    severity: 'medium',
    title: 'GPSR 标签字段新增校验',
    description: '欧盟 GPSR 对电商 Listing 展示的制造商与安全标签字段提出更严格要求。',
    affected_products: ['LED 灯带', '儿童益智玩具'],
    affected_markets: ['欧盟', '法国', '德国'],
    source: 'market_monitor',
    source_url: '',
    dismissed: false,
    created_at: String(Math.floor(Date.now() / 1000) - 86400),
  },
  {
    alert_id: 'mock_risk_004',
    alert_type: 'market_hotspot',
    severity: 'low',
    title: '美国 CA Prop 65 文案复核',
    description: '蓝牙耳机美国市场 Listing 建议复核 CA Prop 65 警示文案展示位置。',
    affected_products: ['蓝牙耳机'],
    affected_markets: ['美国'],
    source: 'rule_engine',
    source_url: '',
    dismissed: true,
    created_at: String(Math.floor(Date.now() / 1000) - 172800),
  },
]

function StatusDot({ status }: { status: 'connected' | 'connecting' | 'disconnected' | 'error' }) {
  return (
    <span
      className={cn(
        'inline-block size-2 rounded-full',
        status === 'connected' && 'bg-emerald-500',
        status === 'connecting' && 'bg-amber-500 animate-pulse',
        (status === 'disconnected' || status === 'error') && 'bg-rose-500',
      )}
    />
  )
}

function formatLastScan(value?: string | null) {
  if (!value || value === 'never') return '尚未扫描'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '尚未扫描'
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatAlertTime(value?: string | number | null) {
  if (value === undefined || value === null || value === '') return '—'
  const raw = String(value)
  const numeric = Number(raw)
  const date = Number.isFinite(numeric) && raw.trim() !== ''
    ? new Date(numeric * 1000)
    : new Date(raw)
  if (Number.isNaN(date.getTime())) return '—'
  const diffMs = Date.now() - date.getTime()
  const diffMinutes = Math.max(0, Math.floor(diffMs / 60000))
  if (diffMinutes < 1) return '刚刚'
  if (diffMinutes < 60) return `${diffMinutes} 分钟前`
  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours} 小时前`
  if (diffHours < 48) return '昨天'
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays} 天前`
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
  })
}

function isRedSeverity(severity: RiskAlert['severity']) {
  return severity === 'critical' || severity === 'high'
}

export default function RiskCenter() {
  const { authFetch, user } = useAuth()
  const userId = user?.id || 'default'
  const [alerts, setAlerts] = useState<RiskAlert[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(null)
  const [scanning, setScanning] = useState(false)
  const [, setScanStatus] = useState('')
  const [severityFilter, setSeverityFilter] = useState('all')
  const [marketFilter, setMarketFilter] = useState('all')
  const [query, setQuery] = useState('')

  const { status: wsStatus, lastMessage } = useWebSocket(
    'default',
    USE_BACKEND_RISK && import.meta.env.VITE_ENABLE_WEBSOCKET === 'true',
  )

  const loadAlerts = useCallback(async () => {
    if (!USE_BACKEND_RISK) {
      setAlerts(MOCK_ALERTS)
      setUnreadCount(MOCK_ALERTS.filter((alert) => !alert.dismissed).length)
      return
    }
    try {
      const [alertsRes, unreadRes] = await Promise.all([
        authFetch(`${API_BASE}/risk/alerts?user_id=${userId}&size=100`),
        authFetch(`${API_BASE}/risk/alerts/unread-count?user_id=${userId}`),
      ])
      const alertsData = await alertsRes.json()
      const unreadData = await unreadRes.json()
      setAlerts(alertsData.alerts || [])
      setUnreadCount(unreadData.unread_count || 0)
    } catch {
      setAlerts(MOCK_ALERTS)
      setUnreadCount(MOCK_ALERTS.filter((alert) => !alert.dismissed).length)
    }
  }, [authFetch, userId])

  const loadMarketStatus = useCallback(async () => {
    const mockStatus: MarketStatus = {
      last_scan: 'never',
      active_alerts: MOCK_ALERTS.filter((alert) => !alert.dismissed).length,
      markets: [
        { code: 'DE', alerts: 1 },
        { code: 'JP', alerts: 1 },
        { code: 'EU', alerts: 1 },
        { code: 'US', alerts: 1 },
      ],
    }
    if (!USE_BACKEND_RISK) {
      setMarketStatus(mockStatus)
      return
    }
    try {
      const res = await authFetch(`${API_BASE}/risk/market-status?user_id=${userId}`)
      setMarketStatus(await res.json())
    } catch {
      setMarketStatus(mockStatus)
    }
  }, [authFetch, userId])

  useEffect(() => {
    loadAlerts()
    loadMarketStatus()
  }, [loadAlerts, loadMarketStatus])

  useEffect(() => {
    if (!lastMessage) return
    if (lastMessage.type === 'alert') {
      setAlerts(prev => [lastMessage.payload as RiskAlert, ...prev])
      setUnreadCount(prev => prev + 1)
      toast.info('收到新的风险预警')
    } else if (lastMessage.type === 'scan_update') {
      const payload = lastMessage.payload as { status: string; detail?: string }
      if (payload.status === 'scanning') {
        setScanStatus('正在扫描市场...')
      } else if (payload.status === 'completed') {
        setScanStatus(payload.detail || '扫描完成')
        loadAlerts()
        loadMarketStatus()
        setScanning(false)
        toast.success('市场扫描完成')
      } else if (payload.status === 'error') {
        setScanStatus(`扫描失败: ${payload.detail || ''}`)
        setScanning(false)
        toast.error('市场扫描失败')
      }
    }
  }, [lastMessage, loadAlerts, loadMarketStatus])

  const handleScan = async () => {
    setScanning(true)
    setScanStatus('正在触发扫描...')
    if (!USE_BACKEND_RISK) {
      window.setTimeout(() => {
        setScanStatus('扫描完成，当前使用前端示例风险数据')
        setMarketStatus(prev => prev ? { ...prev, last_scan: new Date().toISOString() } : prev)
        setScanning(false)
        toast.success('市场扫描完成')
      }, 500)
      return
    }
    try {
      const res = await authFetch(`${API_BASE}/risk/scan?user_id=${userId}`, { method: 'POST' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json().catch(() => ({}))
      setScanStatus(`扫描完成，发现 ${data.alerts_created ?? 0} 条预警`)
      await Promise.all([loadAlerts(), loadMarketStatus()])
      setScanning(false)
      toast.success('市场扫描完成')
    } catch (e) {
      setScanStatus('触发失败')
      setScanning(false)
      toast.error('触发扫描失败')
    }
  }

  const handleDismiss = async (alertId: string) => {
    if (USE_BACKEND_RISK) {
      try {
        await authFetch(`${API_BASE}/risk/alerts/${alertId}/dismiss?user_id=${userId}`, { method: 'POST' })
      } catch {
        // Frontend-only fallback: keep the action usable without backend.
      }
    }
    setAlerts(prev => prev.map(a =>
      a.alert_id === alertId ? { ...a, dismissed: true } : a
    ))
    setUnreadCount(prev => Math.max(0, prev - 1))
    toast.success('已标记为已处理')
  }

  const filteredAlerts = alerts.filter(alert => {
    if (severityFilter === 'red' && !isRedSeverity(alert.severity)) return false
    if (severityFilter === 'yellow' && alert.severity !== 'medium') return false
    if (severityFilter === 'blue' && alert.severity !== 'low') return false
    if (marketFilter !== 'all' && !(alert.affected_markets || []).includes(marketFilter)) return false
    const q = query.trim().toLowerCase()
    if (q) {
      const haystack = [
        alert.title,
        alert.description,
        ...(alert.affected_products || []),
        ...(alert.affected_markets || []),
      ].join(' ').toLowerCase()
      if (!haystack.includes(q)) return false
    }
    return true
  })
  const markets = Array.from(new Set(alerts.flatMap(alert => alert.affected_markets || [])))
  const activeAlerts = alerts.filter(alert => !alert.dismissed)
  const redCount = activeAlerts.filter(alert => isRedSeverity(alert.severity)).length
  const yellowCount = activeAlerts.filter(alert => alert.severity === 'medium').length
  const blueCount = activeAlerts.filter(alert => alert.severity === 'low').length
  const summaryCards = [
    {
      label: '红色 · 紧急',
      value: redCount,
      Icon: AlertTriangle,
      borderClass: 'border-red-400/80',
      textClass: 'text-red-600',
      iconClass: 'text-red-500',
      iconBgClass: 'bg-red-50 dark:bg-red-950/30',
    },
    {
      label: '黄色 · 关注',
      value: yellowCount,
      Icon: AlertTriangle,
      borderClass: 'border-amber-400/90',
      textClass: 'text-amber-600',
      iconClass: 'text-amber-500',
      iconBgClass: 'bg-amber-50 dark:bg-amber-950/30',
    },
    {
      label: '蓝色 · 提示',
      value: blueCount,
      Icon: Info,
      borderClass: 'border-blue-400/90',
      textClass: 'text-blue-600',
      iconClass: 'text-blue-500',
      iconBgClass: 'bg-blue-50 dark:bg-blue-950/30',
    },
  ]

  return (
    <div className="min-h-full bg-muted/40 text-foreground dark:bg-background">
      <div className="mx-auto flex max-w-[1440px] flex-col gap-5 px-3 py-4 sm:px-5 lg:px-6">
        <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-blue-50 text-blue-600 ring-1 ring-blue-100 dark:bg-blue-950/30 dark:text-blue-300 dark:ring-blue-900/70">
              <Shield className="size-4" />
            </span>
            <div className="min-w-0">
              <h1 className="truncate text-[18px] font-semibold tracking-normal">风险监控</h1>
              <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-muted-foreground">
                <span className="inline-flex items-center gap-1.5">
                  <StatusDot status={wsStatus === 'connecting' ? 'connecting' : 'connected'} />
                  {wsStatus === 'connected'
                    ? '实时同步已连接'
                    : wsStatus === 'connecting'
                      ? '实时同步连接中'
                      : '轮询模式'}
                </span>
                <span>待处理 {unreadCount} 条</span>
                <span>最近扫描 {formatLastScan(marketStatus?.last_scan)}</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              onClick={handleScan}
              disabled={scanning}
              className="h-8 rounded-md border-border/70 bg-card px-3 text-[12px] shadow-sm"
            >
              <RefreshCw className={cn('mr-1.5 size-3.5', scanning && 'animate-spin')} />
              {scanning ? '扫描中' : '立即扫描'}
            </Button>
            <Button
              onClick={() => toast.info('新建监控配置即将开放')}
              className="h-8 rounded-md bg-emerald-500 px-3 text-[12px] text-white shadow-sm hover:bg-emerald-600"
            >
              <Plus className="mr-1.5 size-3.5" />
              新建监控
            </Button>
          </div>
        </header>

        <section className="grid gap-3 md:grid-cols-3" aria-label="风险等级概览">
          {summaryCards.map(({ label, value, Icon, borderClass, textClass, iconClass, iconBgClass }) => (
            <article
              key={label}
              className={cn(
                'relative min-h-[74px] overflow-hidden rounded-lg border bg-card px-4 py-3.5 shadow-sm',
                borderClass,
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[12px] font-medium text-muted-foreground">{label}</p>
                  <p className={cn('mt-1 text-[26px] font-semibold leading-none tracking-normal', textClass)}>
                    {value}
                  </p>
                </div>
                <span className={cn('flex size-8 items-center justify-center rounded-md', iconBgClass)}>
                  <Icon className={cn('size-4', iconClass)} />
                </span>
              </div>
            </article>
          ))}
        </section>

        <section className="overflow-hidden rounded-lg border border-border/70 bg-card shadow-sm">
          <div className="flex flex-col gap-3 border-b border-border/60 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-[14px] font-semibold tracking-normal">监控列表</h2>
              <p className="mt-0.5 text-[12px] text-muted-foreground">
                共 {filteredAlerts.length} 条匹配结果，覆盖 {markets.length || marketStatus?.markets.length || 0} 个市场
              </p>
            </div>
            <div className="grid gap-2 sm:grid-cols-[minmax(220px,1fr)_132px_132px] lg:w-[560px]">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="搜索风险、产品或市场"
                  className="h-8 rounded-md border-border/70 bg-background pl-8 text-[12px] shadow-none"
                />
              </div>
              <Select value={marketFilter} onValueChange={setMarketFilter}>
                <SelectTrigger className="h-8 rounded-md border-border/70 bg-background text-[12px] shadow-none">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部店铺</SelectItem>
                  {markets.map((market) => (
                    <SelectItem key={market} value={market}>{market}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={severityFilter} onValueChange={setSeverityFilter}>
                <SelectTrigger className="h-8 rounded-md border-border/70 bg-background text-[12px] shadow-none">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部级别</SelectItem>
                  <SelectItem value="red">红色</SelectItem>
                  <SelectItem value="yellow">黄色</SelectItem>
                  <SelectItem value="blue">蓝色</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {filteredAlerts.length === 0 ? (
            <div className="p-6">
              <EmptyState
                title="暂无匹配预警"
                description="系统会自动监控市场动态并推送风险提示"
              />
            </div>
          ) : (
            <div className="overflow-x-auto" role="region" aria-live="polite" aria-label="风险预警列表">
              <table className="w-full min-w-[920px]">
                <thead>
                  <tr className="border-b border-border/50 bg-muted/30">
                    <th className="w-[120px] px-4 py-3 text-left text-[12px] font-semibold text-muted-foreground">级别</th>
                    <th className="px-4 py-3 text-left text-[12px] font-semibold text-muted-foreground">问题</th>
                    <th className="w-[240px] px-4 py-3 text-left text-[12px] font-semibold text-muted-foreground">店铺 / SKU</th>
                    <th className="w-[150px] px-4 py-3 text-left text-[12px] font-semibold text-muted-foreground">国家</th>
                    <th className="w-[140px] px-4 py-3 text-left text-[12px] font-semibold text-muted-foreground">发现时间</th>
                    <th className="w-[140px] px-4 py-3 text-left text-[12px] font-semibold text-muted-foreground">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/45">
                  {filteredAlerts.map((alert) => {
                    const sev = SEVERITY_CONFIG[alert.severity]
                    const urgent = isRedSeverity(alert.severity)
                    return (
                      <tr
                        key={alert.alert_id}
                        className={cn(
                          'bg-card transition-colors hover:bg-muted/25',
                          alert.dismissed && 'opacity-60',
                        )}
                      >
                        <td className="px-4 py-3">
                          <span className={cn('inline-flex h-6 items-center gap-1.5 rounded-full border px-2.5 text-[12px] font-medium', sev.pillClass)}>
                            <span className={cn('size-2 rounded-full', sev.dotClass)} />
                            {sev.label}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="max-w-[520px]">
                            <p className="truncate text-[13px] font-semibold text-foreground">{alert.title}</p>
                            <p className="mt-1 truncate text-[12px] text-muted-foreground">{alert.description}</p>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-[13px] text-muted-foreground">
                          {(alert.affected_products || []).join('、') || alert.source || '—'}
                        </td>
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center gap-1.5 text-[13px] font-medium text-muted-foreground">
                            <span className="text-[10px] uppercase tracking-normal text-muted-foreground/70">
                              {(alert.affected_markets || [])[0]?.slice(0, 2) || '--'}
                            </span>
                            {(alert.affected_markets || []).join(' / ') || '—'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-[13px] text-muted-foreground">
                          {formatAlertTime(alert.created_at)}
                        </td>
                        <td className="px-4 py-3">
                          {alert.dismissed ? (
                            <span className="text-[12px] font-medium text-muted-foreground">已处理</span>
                          ) : urgent ? (
                            <button
                              onClick={() => handleDismiss(alert.alert_id)}
                              className={cn('h-7 rounded-md px-3 text-[12px] font-semibold transition-colors', sev.actionClass)}
                            >
                              立即处理
                            </button>
                          ) : (
                            <button
                              onClick={() => toast.info(alert.title)}
                              className="h-7 rounded-md border border-border/70 bg-card px-3 text-[12px] font-medium text-foreground transition-colors hover:bg-muted/60"
                            >
                              查看
                            </button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="rounded-lg border border-border/70 bg-card px-4 py-3.5 shadow-sm">
          <div className="mb-3 flex items-center gap-2">
            <Store className="size-3.5 text-muted-foreground" />
            <h2 className="text-[14px] font-semibold tracking-normal">已连接平台</h2>
          </div>
          <div className="grid gap-2 md:grid-cols-4">
            {CONNECTED_STORES.map((store) => (
              <div
                key={store.name}
                className="flex h-11 items-center justify-between rounded-md border border-border/60 bg-background px-3"
              >
                <span className="truncate text-[13px] font-semibold">{store.name}</span>
                <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-emerald-50 px-2 py-1 text-[11px] font-medium text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">
                  <span className="size-2 rounded-full bg-emerald-600" />
                  已连接
                </span>
              </div>
            ))}
            <button
              onClick={() => toast.info('添加店铺能力即将开放')}
              className="flex h-11 items-center justify-center rounded-md border border-dashed border-border/80 bg-background px-3 text-[13px] font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
            >
              <Plus className="mr-1.5 size-3.5" />
              添加店铺
            </button>
          </div>
        </section>
      </div>
    </div>
  )
}
