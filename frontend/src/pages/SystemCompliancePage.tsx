import { useState, useEffect, useCallback, useRef } from 'react'
import PipelineNav from '../components/PipelineNav'
import ComplianceCheckCard from '../components/ComplianceCheckCard'
import type { PipelineStage } from '../types'
import { pipelineApi, riskAlertsApi } from '../api/config'
import type { PipelineStageStatus, RiskAlertItem } from '../api/config'

/** 将后端 PipelineStageStatus 转为前端 PipelineStage */
function toPipelineStage(s: PipelineStageStatus): PipelineStage {
  const id = `stage_${s.stage_number}`
  return {
    id,
    stage_number: s.stage_number,
    name: s.stage_name,
    order: s.stage_number,
    description: `${s.total_products} 个产品 · ${s.passed_products} 通过 · ${s.risk_products} 风险`,
    pass_rate: Math.round(s.pass_rate * 100),
    risk_products: s.risk_products,
    pending_tasks: s.pending_actions,
    status: s.status,
  }
}

/** 预警类型 → 图标 */
function alertIcon(type: string): string {
  if (type.includes('regulation') || type.includes('compliance')) return '📜'
  if (type.includes('cert') || type.includes('expire')) return '🔐'
  return '📊'
}

/** 严重度 → 中文标签 */
function severityLabel(sev: string): { label: string; cls: string } {
  if (sev === 'high' || sev === 'critical') return { label: '高危', cls: 'bg-[#FF3B30]/10 text-[#FF3B30]' }
  if (sev === 'medium') return { label: '中危', cls: 'bg-[#FF9500]/10 text-[#FF9500]' }
  return { label: '低危', cls: 'bg-[#34C759]/10 text-[#34C759]' }
}

/** 格式化时间 */
function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('zh-CN')
  } catch {
    return iso || ''
  }
}

export default function SystemCompliancePage() {
  const [stages, setStages] = useState<PipelineStageStatus[]>([])
  const [alerts, setAlerts] = useState<RiskAlertItem[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedStage, setExpandedStage] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const refreshTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadData = useCallback(async () => {
    try {
      const [health, alertRes] = await Promise.all([
        pipelineApi.health(),
        riskAlertsApi.list({ size: 20 }),
      ])
      setStages(health.stages)
      setAlerts(alertRes.alerts)
    } catch {
      setStages([])
      setAlerts([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

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

  const pipelineStages = stages.map(toPipelineStage)
  const activeStage = expandedStage ? stages.find(s => `stage_${s.stage_number}` === expandedStage) : null

  const totalProducts = stages.reduce((s, st) => s + st.total_products, 0)
  const totalPassed = stages.reduce((s, st) => s + st.passed_products, 0)
  const totalRisk = stages.reduce((s, st) => s + st.risk_products, 0)
  const totalPending = stages.reduce((s, st) => s + st.pending_actions, 0)
  const overallPassRate = totalProducts > 0 ? Math.round((totalPassed / totalProducts) * 100) : 0
  const criticalStages = stages.filter(s => s.status === 'critical')

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Title */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-[#1D1D1F]">系统合规</h1>
            <p className="text-sm text-[#86868B] mt-1">10阶段业务流程合规总览</p>
          </div>
          <label className="flex items-center gap-1.5 text-xs text-[#86868B] cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={e => setAutoRefresh(e.target.checked)}
              className="w-3 h-3"
            />
            30s 自动
          </label>
        </div>

        {/* Pipeline Summary */}
        {!loading && stages.length > 0 && (
          <div className="grid grid-cols-5 gap-3 mb-6">
            <SummaryCard label="总产品数" value={totalProducts} color="text-[#1D1D1F]" />
            <SummaryCard
              label="整体通过率"
              value={`${overallPassRate}%`}
              color={overallPassRate >= 80 ? 'text-[#34C759]' : overallPassRate >= 60 ? 'text-[#FF9500]' : 'text-[#FF3B30]'}
            />
            <SummaryCard
              label="风险产品"
              value={totalRisk}
              color={totalRisk > 0 ? 'text-[#FF3B30]' : 'text-[#34C759]'}
            />
            <SummaryCard
              label="待办事项"
              value={totalPending}
              color={totalPending > 0 ? 'text-[#FF9500]' : 'text-[#34C759]'}
            />
            <SummaryCard
              label="危险阶段"
              value={criticalStages.length}
              color={criticalStages.length > 0 ? 'text-[#FF3B30]' : 'text-[#34C759]'}
            />
          </div>
        )}

        {loading ? (
          <div className="text-center py-16 text-sm text-[#86868B]">加载中...</div>
        ) : stages.length === 0 && alerts.length === 0 ? (
          <div className="text-center py-16 text-sm text-[#86868B]">暂无合规数据</div>
        ) : (
          <>
            {/* Pipeline Navigation */}
            {stages.length > 0 && (
              <>
                <PipelineNav
                  stages={pipelineStages}
                  activeStage={expandedStage}
                  onStageClick={setExpandedStage}
                />

                {/* Expanded Stage Detail */}
                {activeStage && (
                  <div className="mt-4">
                    <ComplianceCheckCard stage={activeStage} />
                  </div>
                )}
              </>
            )}

            {/* Global Alert Summary */}
            {alerts.length > 0 && (
              <div className="mt-8">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-base font-semibold text-[#1D1D1F]">全局合规预警汇总</h2>
                  <span className="text-xs text-[#86868B]">{alerts.length} 条</span>
                </div>
                <div className="space-y-2">
                  {alerts.map(alert => {
                    const sv = severityLabel(alert.severity)
                    return (
                      <div key={alert.id} className="flex items-start gap-3 p-4 bg-white rounded-xl border border-black/6">
                        <span className="text-lg shrink-0">{alertIcon(alert.alert_type)}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold text-[#1D1D1F]">{alert.title}</span>
                            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${sv.cls}`}>
                              {sv.label}
                            </span>
                          </div>
                          <div className="text-xs text-[#86868B] mt-0.5">{alert.message}</div>
                          <div className="text-[11px] text-[#C7C7CC] mt-1">{formatDate(alert.created_at)}</div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function SummaryCard({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div className="bg-white rounded-xl border border-black/6 p-4">
      <div className="text-xs text-[#86868B] mb-1">{label}</div>
      <div className={`text-xl font-semibold ${color}`}>{value}</div>
    </div>
  )
}
