/**
 * Dashboard — 概览仪表盘
 *
 * 整合 Shopify 店铺 / 知识库 / 聊天入口，用真实 API 数据替换旧的 complianceMock。
 */
import { useEffect, useMemo, useState, type ComponentType } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  AlertTriangle,
  Database,
  Globe,
  MessageSquare,
  PackageCheck,
  PlugZap,
  ShieldCheck,
  Store,
  Timer,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { cn } from '@/lib/utils'
import { useAuth } from '@/context/AuthContext'
import { useKnowledgeStats } from '@/hooks/queries/useKnowledge'
import { useOverview } from '@/hooks/queries/useOverview'
import { useShopifyShops } from '@/hooks/queries/useShopify'
import { TARGET_MARKETS } from '@/lib/api/shopify'

const API = '/api/v1'

interface DashboardMetrics {
  total_products: number
  risk_distribution: {
    low: number
    medium: number
    high: number
    critical: number
  }
  recent_alerts: unknown[]
  active_markets: string[]
  health_score: number
  trend: Array<{ date: string; checks: number }>
}

/* ─────────────────────────── Quick Start ─────────────────────────── */

const quickQueries = [
  { product: 'LED 灯带', country: '德国', tag: 'CE · WEEE · LUCID' },
  { product: '锂离子电池组', country: '日本', tag: 'PSE · UN38.3 · MSDS' },
  { product: '儿童益智玩具', country: '法国', tag: 'CE · EN71 · REACH' },
  { product: '蓝牙耳机', country: '美国', tag: 'FCC · UL · CA Prop 65' },
]

/* ─────────────────────────── TrendBadge ─────────────────────────── */

/** 数据卡「较昨日」趋势徽标（PRD：绿色增 / 红色减）。delta 真实派生自环比数据。 */
function TrendBadge({ delta, label }: { delta: number; label?: string }) {
  // delta=0（无环比变化）不显示徽标，避免标题旁孤立的占位
  if (delta === 0) return null
  const up = delta > 0
  return (
    <span
      className={cn(
        'inline-flex items-center gap-0.5 text-[11px] font-medium tabular-nums',
        up ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive',
      )}
      title={`较昨日 ${up ? '+' : ''}${delta}${label ? ` ${label}` : ''}`}
    >
      {up ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />}
      {up ? '+' : ''}
      {delta}
    </span>
  )
}

/* ─────────────────────────── Metric ─────────────────────────── */

function Metric({
  label,
  value,
  detail,
  Icon,
  onClick,
  loading,
  trend,
}: {
  label: string
  value: string | number
  detail: string
  Icon: ComponentType<{ className?: string }>
  onClick?: () => void
  loading?: boolean
  /** 较昨日环比；后端 /dashboard/summary 提供每卡 delta 后可直接传入 */
  trend?: { delta: number; label?: string }
}) {
  const C = onClick ? 'button' : 'div'
  return (
    <C
      onClick={onClick}
      className="rounded-lg border border-border/60 bg-card p-4 text-left w-full transition-colors hover:bg-muted/10 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <div className="mb-5 flex items-center justify-between">
        <div className="text-[12px] font-medium text-muted-foreground">{label}</div>
        <div className="flex items-center gap-2">
          {trend && <TrendBadge delta={trend.delta} label={trend.label} />}
          <Icon className="size-4 text-muted-foreground" />
        </div>
      </div>
      {loading ? (
        <Skeleton className="h-9 w-20" />
      ) : (
        <div className="text-[30px] font-semibold leading-none tracking-tight tabular-nums">{value}</div>
      )}
      <div className="mt-2 text-[12px] leading-5 text-muted-foreground">{detail}</div>
    </C>
  )
}

/* ─────────────────────────── Dashboard ─────────────────────────── */

export default function Dashboard() {
  const navigate = useNavigate()
  const { authFetch, user, isAdmin } = useAuth()
  const { data: shops, isLoading: shopsLoading, isError: shopsError, refetch: refetchShops } = useShopifyShops()
  const { data: kStats, isLoading: statsLoading } = useKnowledgeStats()
  const overview = useOverview(true)
  const [dashboardMetrics, setDashboardMetrics] = useState<DashboardMetrics | null>(null)
  const [dashboardLoading, setDashboardLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setDashboardLoading(true)
    authFetch(`${API}/metrics/dashboard?user_id=${encodeURIComponent(user?.id ?? 'default')}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled) setDashboardMetrics(data)
      })
      .catch(() => {
        if (!cancelled) setDashboardMetrics(null)
      })
      .finally(() => {
        if (!cancelled) setDashboardLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [authFetch, user?.id])

  // 合规检查「较昨日」趋势 — 真实派生自 trend 序列（PRD 数据卡环比）
  const checksDelta = useMemo(() => {
    const t = dashboardMetrics?.trend
    if (!t || t.length < 2) return null
    return (t[t.length - 1]?.checks ?? 0) - (t[t.length - 2]?.checks ?? 0)
  }, [dashboardMetrics?.trend])

  const totalDocs = kStats?.total_docs ?? 0
  const metricsLoading = statsLoading || dashboardLoading || overview.isLoading
  const riskDistribution = dashboardMetrics?.risk_distribution
  const activeRiskCount = overview.data?.activeAlerts.length ?? (riskDistribution
    ? riskDistribution.medium + riskDistribution.high + riskDistribution.critical
    : 0)
  const activeMarketCount = overview.data?.marketCount || dashboardMetrics?.active_markets?.length || TARGET_MARKETS.length
  const healthScore = overview.data?.overallScore ?? Math.round(dashboardMetrics?.health_score ?? 100)
  const schedulerStats = overview.data?.schedulerStats
  const integrationStatus = overview.data?.integrationStatus ?? {}
  const integrationConnected = Object.values(integrationStatus).reduce((sum, item) => sum + (item.connected || 0), 0)

  const startChat = (product: string, country: string) => {
    navigate('/app/chat', {
      state: { initialMessage: `${product} 出口 ${country} 需要哪些合规认证？` },
    })
  }

  return (
    <div className="h-full overflow-y-auto bg-background">
      {/* Header */}
      <div className="border-b border-border/60">
        <div className="mx-auto max-w-[1400px] px-6 py-7 sm:px-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="mb-2 flex items-center gap-2 text-[12px] font-medium text-muted-foreground">
                <span className="h-px w-6 bg-border" />
                OS 级合规智能体控制台
              </div>
              <h1 className="flex items-center gap-2 text-[28px] font-semibold tracking-tight">
                概览
                {checksDelta !== null && !dashboardLoading && (
                  <TrendBadge delta={checksDelta} label="次合规检查" />
                )}
              </h1>
              <p className="mt-1 max-w-2xl text-[14px] leading-6 text-muted-foreground">
                Shopify 店铺纳管 · RAG 知识库 · 合规对话工作台
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                className="h-9 text-[13px]"
                onClick={() => navigate('/app/compliance/system')}
              >
                <Store className="mr-2 size-4" />
                店铺合规
              </Button>
              <Button className="h-9 text-[13px]" onClick={() => navigate('/app/products')}>
                <PackageCheck className="mr-2 size-4" />
                产品合规
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-[1400px] space-y-8 px-6 py-8 sm:px-8">
        {/* Metrics */}
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
          <Metric
            label="活跃产品"
            value={overview.data?.productCount ?? dashboardMetrics?.total_products ?? 0}
            detail={`${activeMarketCount} 个目标市场覆盖`}
            Icon={PackageCheck}
            onClick={() => navigate('/app/products')}
            loading={metricsLoading}
          />
          <Metric
            label="知识库文档"
            value={totalDocs}
            detail="法规 PDF / URL 导入并向量化"
            Icon={Database}
            onClick={() => navigate('/app/knowledge')}
            loading={metricsLoading}
          />
          <Metric
            label="合规健康分"
            value={healthScore}
            detail="聚合产品、预警与流水线计算"
            Icon={ShieldCheck}
            onClick={() => navigate('/app/monitor')}
            loading={metricsLoading}
          />
          <Metric
            label="活跃预警"
            value={activeRiskCount}
            detail="中高风险和严重风险待处理数"
            Icon={AlertTriangle}
            onClick={() => navigate('/app/monitor')}
            loading={metricsLoading}
          />
          {isAdmin && (
            <>
              <Metric
                label="定时任务"
                value={schedulerStats?.total ?? 0}
                detail={schedulerStats ? `${schedulerStats.active} 运行中 · ${schedulerStats.paused} 暂停` : '调度器状态待加载'}
                Icon={Timer}
                onClick={() => navigate('/app/scheduler')}
                loading={metricsLoading}
              />
              <Metric
                label="第三方连接"
                value={integrationConnected}
                detail={`${Object.keys(integrationStatus).length} 类 Provider 状态`}
                Icon={PlugZap}
                onClick={() => navigate('/app/integrations')}
                loading={metricsLoading}
              />
            </>
          )}
        </section>

        {/* Quick Start + Markets */}
        <section className="grid gap-4 lg:grid-cols-2">
          {/* Quick Chat */}
          <div className="rounded-lg border border-border/60 bg-card p-4">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-[14px] font-semibold">热门查询场景</h2>
                <p className="mt-0.5 text-[12px] text-muted-foreground">
                  直接带产品和市场进入对话工作台
                </p>
              </div>
              <MessageSquare className="size-4 text-muted-foreground" />
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {quickQueries.map((q) => (
                <button
                  key={`${q.product}-${q.country}`}
                  onClick={() => startChat(q.product, q.country)}
                  className="rounded-md border border-border/60 bg-background px-3 py-3 text-left transition-colors hover:bg-muted/30 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  <div className="text-[13px] font-semibold">
                    {q.product}
                    <span className="font-normal text-muted-foreground"> → {q.country}</span>
                  </div>
                  <div className="mt-1.5 text-[11px] text-muted-foreground">{q.tag}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Markets */}
          <div className="rounded-lg border border-border/60 bg-card p-4">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-[14px] font-semibold">目标市场</h2>
                <p className="mt-0.5 text-[12px] text-muted-foreground">
                  点击市场进入合规查询并预填目标国家
                </p>
              </div>
              <Globe className="size-4 text-muted-foreground" />
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {TARGET_MARKETS.map((m) => (
                <button
                  key={m.code}
                  onClick={() =>
                    navigate('/app/compliance', { state: { country: m.label } })
                  }
                  className="rounded-md border border-border/60 bg-background px-3 py-2 text-left transition-colors hover:bg-muted/30 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  <span className="text-[12px] font-semibold">{m.label}</span>
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* Connected Shops */}
        {shopsLoading ? (
          <section>
            <div className="mb-4">
              <Skeleton className="h-5 w-28" />
              <Skeleton className="mt-1 h-4 w-48" />
            </div>
            <LoadingState variant="cards" count={3} />
          </section>
        ) : shopsError ? (
          <section>
            <div className="mb-4">
              <h2 className="text-[16px] font-semibold tracking-tight">已连接店铺</h2>
              <p className="mt-1 text-[13px] text-muted-foreground">点击进入产品合规检查</p>
            </div>
            <ErrorState
              title="店铺加载失败"
              description="无法获取已连接店铺列表，请重试"
              onRetry={() => refetchShops()}
            />
          </section>
        ) : shops && shops.length > 0 ? (
          <section>
            <div className="mb-4 flex items-end justify-between gap-4">
              <div>
                <h2 className="text-[16px] font-semibold tracking-tight">已连接店铺</h2>
                <p className="mt-1 text-[13px] text-muted-foreground">
                  点击进入产品合规检查
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 text-[12px]"
                onClick={() => navigate('/app/products')}
              >
                产品合规 <ArrowRight className="ml-1 size-3.5" />
              </Button>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {shops.map((s) => (
                <button
                  key={s.shop}
                  onClick={() => navigate('/app/products')}
                  className="group rounded-lg border border-border/60 bg-card p-4 text-left transition-colors hover:border-foreground/20 hover:bg-muted/20 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Store className="size-4 text-muted-foreground shrink-0" />
                        <span className="text-[14px] font-semibold truncate">{s.shop}</span>
                      </div>
                      <div className="mt-1 text-[12px] text-muted-foreground truncate">
                        scope: {s.scope || '—'}
                      </div>
                    </div>
                  </div>
                  <div className="mt-4 flex items-center justify-between">
                    <span className="text-[11px] text-muted-foreground">查看产品</span>
                    <ArrowRight className="size-3.5 text-muted-foreground group-hover:text-foreground transition-colors" />
                  </div>
                </button>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </div>
  )
}
