import { useState, useEffect, useCallback, useRef } from 'react'
import { pipelineApi, modelConfigsApi, productsApi, riskAlertsApi, proactiveApi } from '../api/config'
import MetricCard from '../components/metrics/MetricCard'
import TrendChart from '../components/metrics/TrendChart'

interface ModelUsage {
  model: string
  tokens: number
}

export default function MetricsPage() {
  const [healthScore, setHealthScore] = useState(0)
  const [productCount, setProductCount] = useState(0)
  const [alertCount, setAlertCount] = useState(0)
  const [tokenUsage, setTokenUsage] = useState('—')
  const [modelUsage, setModelUsage] = useState<ModelUsage[]>([])
  const [stageData, setStageData] = useState<{ label: string; value: number }[]>([])
  const [weekData, setWeekData] = useState<{ label: string; value: number }[]>([])
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [lastUpdated, setLastUpdated] = useState('')
  const refreshTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadData = useCallback(async () => {
    try {
      const [health, products, alerts, usage] = await Promise.allSettled([
        pipelineApi.health(),
        productsApi.list(),
        riskAlertsApi.list({ size: 0 }),
        modelConfigsApi.getUsage(),
      ])

      if (health.status === 'fulfilled') {
        setHealthScore(Math.round(health.value.overall_score))
        setStageData(
          health.value.stages.map(s => ({
            label: s.stage_name,
            value: Math.round(s.pass_rate * 100),
          }))
        )
      }
      if (products.status === 'fulfilled') setProductCount(products.value.length)
      if (alerts.status === 'fulfilled') setAlertCount(alerts.value.alerts.length)
      if (usage.status === 'fulfilled') {
        const t = usage.value.total_tokens
        setTokenUsage(t >= 1000 ? `${(t / 1000).toFixed(1)}K` : String(t))
        setModelUsage(
          Object.entries(usage.value.by_model || {}).map(([model, tokens]) => ({
            model,
            tokens: tokens as number,
          }))
        )
      }
      setLastUpdated(new Date().toLocaleTimeString('zh-CN'))
    } catch {
      /* partial failure tolerated */
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

  // 自动刷新
  useEffect(() => {
    if (autoRefresh) {
      refreshTimer.current = setInterval(loadData, 30000)
    } else {
      if (refreshTimer.current) {
        clearInterval(refreshTimer.current)
        refreshTimer.current = null
      }
    }
    return () => {
      if (refreshTimer.current) clearInterval(refreshTimer.current)
    }
  }, [autoRefresh, loadData])

  // 从后端简报历史填充趋势数据
  useEffect(() => {
    proactiveApi.getBrief(7).then(res => {
      if (res.briefs && res.briefs.length > 0) {
        const dayNames = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
        const data = res.briefs
          .map(b => ({
            label: dayNames[new Date(b.date).getDay()] ?? '—',
            value: b.summary.compliance_pass_rate,
          }))
          .slice(-7)
        // 最后一天用当前实时 healthScore
        if (data.length > 0) {
          const lastIdx = data.length - 1
          const lastItem = data[lastIdx]
          if (lastItem) {
            lastItem.value = healthScore || lastItem.value
          }
        }
        setWeekData(data)
      } else {
        setWeekData([])
      }
    }).catch(() => setWeekData([]))
  }, [healthScore])

  const totalTokenEntries = modelUsage.reduce((s, m) => s + m.tokens, 0)

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Title */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-[#1D1D1F]">指标监控中心</h1>
            <p className="text-sm text-[#86868B] mt-1">
              系统健康度与关键指标总览
              {lastUpdated && <span className="ml-2">· 最近更新 {lastUpdated}</span>}
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
              30s 自动刷新
            </label>
            <button
              onClick={() => { setLoading(true); loadData() }}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-[#F5F5F7] text-[#86868B] hover:bg-[#E5E5EA] transition-colors"
            >
              刷新
            </button>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-16 text-sm text-[#86868B]">加载中...</div>
        ) : (
          <>
            {/* Metric Cards */}
            <div className="grid grid-cols-4 gap-4 mb-6">
              <MetricCard
                label="系统健康度"
                value={`${healthScore}%`}
                icon="📊"
                delta={{ value: `${healthScore > 80 ? '+' : ''}${healthScore - 75}%`, positive: healthScore >= 80 }}
                subtitle={`${stageData.length} 个阶段`}
              />
              <MetricCard
                label="产品总数"
                value={productCount}
                icon="📦"
                subtitle="全部生命周期"
              />
              <MetricCard
                label="活跃预警"
                value={alertCount}
                icon="⚠"
                delta={alertCount > 0 ? { value: `${alertCount}`, positive: false } : undefined}
                subtitle="需关注的风险"
              />
              <MetricCard
                label="Token 用量"
                value={tokenUsage}
                icon="⚡"
                subtitle="累计推理消耗"
              />
            </div>

            {/* Charts */}
            <div className="grid grid-cols-2 gap-4 mb-6">
              {/* Stage Pass Rates */}
              <div className="bg-white rounded-xl border border-black/6 p-5">
                <TrendChart
                  data={stageData.length > 0 ? stageData : weekData}
                  title="各阶段合规通过率 (%)"
                  height={160}
                  thresholds={{ good: 90, warn: 70 }}
                />
              </div>

              {/* Health Score Trend */}
              <div className="bg-white rounded-xl border border-black/6 p-5">
                {weekData.length > 0 ? (
                  <TrendChart
                    data={weekData}
                    title="近 7 日系统健康度趋势"
                    height={160}
                    thresholds={{ good: 85, warn: 70 }}
                  />
                ) : (
                  <div className="flex items-center justify-center h-[160px] text-sm text-[#86868B]">
                    暂无历史数据，系统将持续采集
                  </div>
                )}
              </div>
            </div>

            {/* 模型用量分解 */}
            {modelUsage.length > 0 && (
              <div className="bg-white rounded-xl border border-black/6 p-5 mb-6">
                <h2 className="text-sm font-semibold text-[#1D1D1F] mb-3">
                  模型 Token 用量分解
                  <span className="text-xs font-normal text-[#86868B] ml-2">
                    {totalTokenEntries >= 1000
                      ? `${(totalTokenEntries / 1000).toFixed(1)}K`
                      : totalTokenEntries}{' '}
                    total
                  </span>
                </h2>
                <div className="space-y-2">
                  {modelUsage.map(m => {
                    const pct = totalTokenEntries > 0 ? (m.tokens / totalTokenEntries) * 100 : 0
                    return (
                      <div key={m.model} className="flex items-center gap-3">
                        <span className="text-xs text-[#424245] w-24 truncate shrink-0">{m.model}</span>
                        <div className="flex-1 h-5 bg-[#F5F5F7] rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full bg-[#0071E3] transition-all duration-500"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="text-xs text-[#86868B] w-16 text-right shrink-0">
                          {m.tokens >= 1000 ? `${(m.tokens / 1000).toFixed(1)}K` : m.tokens}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Summary */}
            <div className="bg-white rounded-xl border border-black/6 p-5">
              <h2 className="text-sm font-semibold text-[#1D1D1F] mb-3">系统总结</h2>
              {productCount === 0 && healthScore === 0 ? (
                <div className="text-sm text-[#86868B]">
                  暂无数据，连接后端后将自动加载系统指标。
                </div>
              ) : (
                <ul className="space-y-2 text-sm text-[#424245]">
                  <li className="flex items-start gap-2">
                    <span className={`mt-0.5 text-sm ${healthScore >= 80 ? 'text-[#34C759]' : 'text-[#FF9500]'}`}>●</span>
                    <span>系统健康度 <strong>{healthScore}%</strong>，共 <strong>{stageData.length}</strong> 个合规阶段。</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-0.5 text-sm text-[#0071E3]">●</span>
                    <span>当前管理 <strong>{productCount}</strong> 个产品，覆盖 <strong>{stageData.length}</strong> 个业务流程阶段。</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className={`mt-0.5 text-sm ${alertCount > 0 ? 'text-[#FF3B30]' : 'text-[#34C759]'}`}>●</span>
                    <span>活跃预警 <strong>{alertCount}</strong> 条{alertCount > 0 ? '，建议及时处理。' : '，状态良好。'}</span>
                  </li>
                </ul>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
