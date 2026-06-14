import { useState, useEffect, useCallback } from 'react'
import { schedulerApi, type SchedulerJobItem, type ProductTaskMeta } from '../../api/config'

// ── 任务名称映射 ─────────────────────────────────

function resolveJobName(id: string): string {
  const nameMap: Record<string, string> = {
    market_poll: '市场轮询',
    metrics_collect: '指标收集',
    proactive_daily_brief: '每日合规简报',
    proactive_cert_expiry: '认证到期预警',
    proactive_regulation_scan: '法规变更扫描',
    proactive_heartbeat: '心跳自检',
    proactive_insights: '跨产品洞察',
    proactive_global_metrics: '全局指标聚合',
  }
  // 处理产品级任务: check_cert_expiry_p_xxx, scan_regulation_changes_p_xxx
  for (const [prefix, label] of Object.entries(nameMap)) {
    if (id.startsWith(prefix)) return label
  }
  return id
}

function triggerIcon(job: SchedulerJobItem) {
  if (job.trigger.type === 'interval') return '🔄'
  if (job.trigger.type === 'cron') return '⏰'
  return '⏱'
}

function pauseState(job: SchedulerJobItem) {
  if (job.pending) return { label: '已暂停', cls: 'bg-[#FF9500]/10 text-[#FF9500]' }
  if (!job.next_run_time) return { label: '已停止', cls: 'bg-[#FF3B30]/10 text-[#FF3B30]' }
  return { label: '运行中', cls: 'bg-[#34C759]/10 text-[#34C759]' }
}

// ── 合规状态样式 ─────────────────────────────────

const complianceColors: Record<string, string> = {
  passed: 'bg-[#34C759]/10 text-[#34C759]',
  checking: 'bg-[#FF9500]/10 text-[#FF9500]',
  failed: 'bg-[#FF3B30]/10 text-[#FF3B30]',
  pending: 'bg-[#86868B]/10 text-[#86868B]',
}

const complianceLabels: Record<string, string> = {
  passed: '合规',
  checking: '待整改',
  failed: '不合规',
  pending: '待检查',
}

// ── 主组件 ─────────────────────────────────────

export default function SchedulerConfigPage() {
  const [tab, setTab] = useState<'global' | 'product'>('global')
  const [globalJobs, setGlobalJobs] = useState<SchedulerJobItem[]>([])
  const [productJobs, setProductJobs] = useState<Record<string, SchedulerJobItem[]>>({})
  const [productMeta, setProductMeta] = useState<Record<string, ProductTaskMeta>>({})
  const [enabled, setEnabled] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await schedulerApi.listGrouped()
      setGlobalJobs(data.global)
      setProductJobs(data.products)
      setProductMeta(data.product_meta)
      setEnabled(data.enabled)
    } catch (e) {
      setError('无法加载定时任务数据，请确认后端已启动。')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const handleAction = async (jobId: string, action: 'pause' | 'resume' | 'trigger') => {
    setActionLoading(`${jobId}_${action}`)
    try {
      if (action === 'pause') await schedulerApi.pause(jobId)
      else if (action === 'resume') await schedulerApi.resume(jobId)
      else await schedulerApi.trigger(jobId)
      await loadData()
    } catch (e) {
      console.error(`Action ${action} failed for ${jobId}`, e)
    } finally {
      setActionLoading(null)
    }
  }

  const allProductIds = Object.keys(productJobs)
  const totalGlobal = globalJobs.length
  const totalProduct = allProductIds.length
  const activeGlobal = globalJobs.filter(j => !j.pending && j.next_run_time).length
  const pausedGlobal = globalJobs.filter(j => j.pending).length

  // ── Render ─────────────────────────────────

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-[#1D1D1F]">定时任务管理</h1>
              <p className="text-sm text-[#86868B] mt-1">
                查看和管理系统定时任务，支持全局维度和产品维度
                {!enabled && <span className="ml-2 text-[#FF9500]">· 调度器已关闭</span>}
              </p>
            </div>
            <button
              onClick={loadData}
              disabled={loading}
              className="px-3 py-1.5 text-xs font-medium rounded-lg border border-black/10 text-[#86868B] hover:bg-[#F5F5F7] disabled:opacity-50"
            >
              {loading ? '刷新中...' : '刷新'}
            </button>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-16 text-sm text-[#86868B]">加载中...</div>
        ) : error ? (
          <div className="bg-white rounded-xl border border-black/6 p-12 text-center">
            <div className="text-4xl mb-3">⏱</div>
            <div className="text-sm font-semibold text-[#FF3B30] mb-1">加载失败</div>
            <div className="text-xs text-[#86868B]">{error}</div>
          </div>
        ) : !enabled ? (
          <div className="bg-white rounded-xl border border-black/6 p-12 text-center">
            <div className="text-4xl mb-3">⏱</div>
            <div className="text-sm font-semibold text-[#1D1D1F] mb-1">调度器未启用</div>
            <div className="text-xs text-[#86868B]">请在配置中将 scheduler_enabled 设为 True。</div>
          </div>
        ) : (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-4 gap-4 mb-6">
              <div className="bg-white rounded-xl border border-black/6 p-4">
                <div className="text-xs text-[#86868B] mb-1">全局任务</div>
                <div className="text-2xl font-semibold text-[#1D1D1F]">{totalGlobal}</div>
              </div>
              <div className="bg-white rounded-xl border border-black/6 p-4">
                <div className="text-xs text-[#86868B] mb-1">产品覆盖</div>
                <div className="text-2xl font-semibold text-[#1D1D1F]">{totalProduct}</div>
              </div>
              <div className="bg-white rounded-xl border border-black/6 p-4">
                <div className="text-xs text-[#86868B] mb-1">运行中</div>
                <div className="text-2xl font-semibold text-[#34C759]">{activeGlobal}</div>
              </div>
              <div className="bg-white rounded-xl border border-black/6 p-4">
                <div className="text-xs text-[#86868B] mb-1">已暂停</div>
                <div className="text-2xl font-semibold text-[#FF9500]">{pausedGlobal}</div>
              </div>
            </div>

            {/* Tab Navigation */}
            <div className="flex gap-1 mb-6 bg-[#F5F5F7] rounded-lg p-1 w-fit">
              <button
                onClick={() => setTab('global')}
                className={`px-4 py-2 text-sm font-medium rounded-md transition-all ${
                  tab === 'global'
                    ? 'bg-white text-[#1D1D1F] shadow-sm'
                    : 'text-[#86868B] hover:text-[#1D1D1F]'
                }`}
              >
                全局任务
                <span className="ml-1.5 text-[10px] opacity-60">{totalGlobal}</span>
              </button>
              <button
                onClick={() => setTab('product')}
                className={`px-4 py-2 text-sm font-medium rounded-md transition-all ${
                  tab === 'product'
                    ? 'bg-white text-[#1D1D1F] shadow-sm'
                    : 'text-[#86868B] hover:text-[#1D1D1F]'
                }`}
              >
                产品任务
                <span className="ml-1.5 text-[10px] opacity-60">{totalProduct}</span>
              </button>
            </div>

            {/* Tab Content */}
            {tab === 'global' ? (
              <GlobalJobsView
                jobs={globalJobs}
                actionLoading={actionLoading}
                onAction={handleAction}
              />
            ) : (
              <ProductJobsView
                productIds={allProductIds}
                productJobs={productJobs}
                productMeta={productMeta}
                actionLoading={actionLoading}
                onAction={handleAction}
                selectedProductId={selectedProductId}
                onSelectProduct={setSelectedProductId}
              />
            )}
          </>
        )}
      </div>

      {/* Product Detail Drawer */}
      {selectedProductId && (
        <ProductDetailDrawer
          productId={selectedProductId}
          productMeta={productMeta[selectedProductId]}
          jobs={productJobs[selectedProductId] || []}
          actionLoading={actionLoading}
          onAction={handleAction}
          onClose={() => setSelectedProductId(null)}
        />
      )}
    </div>
  )
}

// ── 全局任务视图 ─────────────────────────────────

function GlobalJobsView({
  jobs,
  actionLoading,
  onAction,
}: {
  jobs: SchedulerJobItem[]
  actionLoading: string | null
  onAction: (id: string, action: 'pause' | 'resume' | 'trigger') => void
}) {
  if (jobs.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-black/6 p-12 text-center">
        <div className="text-4xl mb-3">🔄</div>
        <div className="text-sm font-semibold text-[#1D1D1F] mb-1">暂无全局任务</div>
        <div className="text-xs text-[#86868B]">所有全局定时任务尚未注册。</div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {jobs.map(job => {
        const state = pauseState(job)
        const actKey = `${job.id}_`
        return (
          <div
            key={job.id}
            className={`bg-white rounded-xl border border-black/6 p-5 transition-all ${
              job.pending ? 'opacity-70' : ''
            }`}
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#F5F5F7] flex items-center justify-center text-lg">
                  {triggerIcon(job)}
                </div>
                <div>
                  <div className="text-sm font-semibold text-[#1D1D1F]">
                    {resolveJobName(job.id)}
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs text-[#86868B]">{job.id}</span>
                    <span
                      className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${state.cls}`}
                    >
                      {state.label}
                    </span>
                    <span className="text-[10px] text-[#0071E3] bg-[#0071E3]/8 px-1.5 py-0.5 rounded">
                      全局
                    </span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {!job.pending ? (
                  <button
                    disabled={actionLoading?.startsWith(actKey)}
                    onClick={() => onAction(job.id, 'pause')}
                    className="px-3 py-1.5 text-xs font-medium rounded-lg border border-[#FF9500]/30 text-[#FF9500] hover:bg-[#FF9500]/5 disabled:opacity-50"
                  >
                    {actionLoading === `${job.id}_pause` ? '...' : '暂停'}
                  </button>
                ) : (
                  <button
                    disabled={actionLoading?.startsWith(actKey)}
                    onClick={() => onAction(job.id, 'resume')}
                    className="px-3 py-1.5 text-xs font-medium rounded-lg border border-[#34C759]/30 text-[#34C759] hover:bg-[#34C759]/5 disabled:opacity-50"
                  >
                    {actionLoading === `${job.id}_resume` ? '...' : '恢复'}
                  </button>
                )}
                <button
                  disabled={actionLoading?.startsWith(actKey)}
                  onClick={() => onAction(job.id, 'trigger')}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg border border-[#0071E3]/30 text-[#0071E3] hover:bg-[#0071E3]/5 disabled:opacity-50"
                >
                  {actionLoading === `${job.id}_trigger` ? '...' : '立即执行'}
                </button>
              </div>
            </div>

            <div className="grid grid-cols-4 gap-3 pt-3 border-t border-black/6">
              <div>
                <div className="text-[10px] text-[#C7C7CC] mb-0.5">触发器</div>
                <div className="text-xs text-[#424245]">
                  {job.trigger.type === 'interval'
                    ? `间隔 ${job.trigger.interval_human}`
                    : job.trigger.type === 'cron'
                      ? job.trigger.cron_human || 'Cron'
                      : '未知'}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-[#C7C7CC] mb-0.5">下次执行</div>
                <div className="text-xs text-[#424245]">
                  {job.next_run_time
                    ? new Date(job.next_run_time).toLocaleString('zh-CN')
                    : '—'}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-[#C7C7CC] mb-0.5">最大实例</div>
                <div className="text-xs text-[#424245]">{job.max_instances}</div>
              </div>
              <div>
                <div className="text-[10px] text-[#C7C7CC] mb-0.5">合并执行</div>
                <div className="text-xs text-[#424245]">{job.coalesce ? '是' : '否'}</div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── 产品任务视图 ─────────────────────────────────

function ProductJobsView({
  productIds,
  productJobs,
  productMeta,
  actionLoading: _actionLoading,
  onAction: _onAction,
  selectedProductId,
  onSelectProduct,
}: {
  productIds: string[]
  productJobs: Record<string, SchedulerJobItem[]>
  productMeta: Record<string, ProductTaskMeta>
  actionLoading: string | null
  onAction: (id: string, action: 'pause' | 'resume' | 'trigger') => void
  selectedProductId: string | null
  onSelectProduct: (id: string | null) => void
}) {
  if (productIds.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-black/6 p-12 text-center">
        <div className="text-4xl mb-3">📦</div>
        <div className="text-sm font-semibold text-[#1D1D1F] mb-1">暂无产品任务</div>
        <div className="text-xs text-[#86868B]">
          请先在产品管理中创建产品，系统会自动为每个产品注册定时任务。
        </div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-3 gap-3">
      {productIds.map(pid => {
        const meta = productMeta[pid]
        const jobs = productJobs[pid] || []
        const activeJobs = jobs.filter(j => !j.pending && j.next_run_time).length
        const pausedJobs = jobs.filter(j => j.pending).length
        const isSelected = selectedProductId === pid

        return (
          <button
            key={pid}
            onClick={() => onSelectProduct(pid)}
            className={`w-full text-left p-4 rounded-xl border transition-all cursor-pointer group ${
              isSelected
                ? 'border-[#0071E3] bg-[#0071E3]/5'
                : 'border-black/6 bg-white hover:border-[#0071E3]/30 hover:shadow-sm'
            }`}
          >
            {meta ? (
              <>
                {/* Product header */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm text-[#1D1D1F] truncate group-hover:text-[#0071E3] transition-colors">
                      {meta.name}
                    </div>
                    <div className="text-xs text-[#86868B] mt-0.5 truncate">
                      {meta.target_markets?.join(' · ') || '—'}
                    </div>
                  </div>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded shrink-0 ${
                      complianceColors[meta.compliance_status] || 'bg-[#86868B]/10 text-[#86868B]'
                    }`}
                  >
                    {complianceLabels[meta.compliance_status] || meta.compliance_status}
                  </span>
                </div>

                {/* Health bar */}
                <div className="mt-3">
                  <div className="flex items-center justify-between text-[11px] text-[#86868B] mb-1">
                    <span>健康度</span>
                    <span className="font-semibold">{meta.health_score ?? 0}%</span>
                  </div>
                  <div className="h-1.5 bg-[#F5F5F7] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        (meta.health_score ?? 0) >= 80
                          ? 'bg-[#34C759]'
                          : (meta.health_score ?? 0) >= 50
                            ? 'bg-[#FF9500]'
                            : 'bg-[#FF3B30]'
                      }`}
                      style={{ width: `${meta.health_score ?? 0}%` }}
                    />
                  </div>
                </div>

                {/* Jobs summary */}
                <div className="mt-3 pt-3 border-t border-black/6">
                  <div className="flex items-center gap-3 text-xs text-[#86868B]">
                    <span>{jobs.length} 个任务</span>
                    {activeJobs > 0 && <span className="text-[#34C759]">{activeJobs} 运行中</span>}
                    {pausedJobs > 0 && (
                      <span className="text-[#FF9500]">{pausedJobs} 已暂停</span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {jobs.map(job => (
                      <span
                        key={job.id}
                        className={`text-[10px] px-1.5 py-0.5 rounded ${
                          job.pending
                            ? 'bg-[#FF9500]/10 text-[#FF9500]'
                            : 'bg-[#34C759]/10 text-[#34C759]'
                        }`}
                      >
                        {resolveJobName(job.id)}
                      </span>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="text-sm text-[#86868B] py-4 text-center">
                {pid}
                <div className="text-xs mt-1">{jobs.length} 个任务</div>
              </div>
            )}
          </button>
        )
      })}
    </div>
  )
}

// ── 产品详情抽屉 ─────────────────────────────────

function ProductDetailDrawer({
  productId,
  productMeta,
  jobs,
  actionLoading,
  onAction,
  onClose,
}: {
  productId: string
  productMeta?: ProductTaskMeta
  jobs: SchedulerJobItem[]
  actionLoading: string | null
  onAction: (id: string, action: 'pause' | 'resume' | 'trigger') => void
  onClose: () => void
}) {
  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/20 z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="fixed top-0 right-0 h-full w-[480px] bg-white z-50 shadow-2xl overflow-y-auto transition-transform">
        <div className="p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              {productMeta ? (
                <>
                  <h2 className="text-lg font-semibold text-[#1D1D1F]">{productMeta.name}</h2>
                  <p className="text-sm text-[#86868B] mt-0.5">{productId}</p>
                </>
              ) : (
                <h2 className="text-lg font-semibold text-[#1D1D1F]">{productId}</h2>
              )}
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg bg-[#F5F5F7] flex items-center justify-center text-sm text-[#86868B] hover:bg-[#E5E5EA] transition-colors"
            >
              ✕
            </button>
          </div>

          {/* Product Info */}
          {productMeta && (
            <div className="bg-[#F5F5F7] rounded-xl p-4 mb-6">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-[10px] text-[#C7C7CC] mb-0.5">目标市场</div>
                  <div className="text-xs text-[#424245]">
                    {productMeta.target_markets?.join(' · ') || '—'}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-[#C7C7CC] mb-0.5">生命周期</div>
                  <div className="text-xs text-[#424245]">
                    {productMeta.lifecycle_stage || '—'}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-[#C7C7CC] mb-0.5">合规状态</div>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded inline-block ${
                      complianceColors[productMeta.compliance_status] || 'bg-[#86868B]/10 text-[#86868B]'
                    }`}
                  >
                    {complianceLabels[productMeta.compliance_status] || productMeta.compliance_status}
                  </span>
                </div>
                <div>
                  <div className="text-[10px] text-[#C7C7CC] mb-0.5">健康度</div>
                  <span
                    className={`text-xs font-semibold ${
                      (productMeta.health_score ?? 0) >= 80
                        ? 'text-[#34C759]'
                        : (productMeta.health_score ?? 0) >= 50
                          ? 'text-[#FF9500]'
                          : 'text-[#FF3B30]'
                    }`}
                  >
                    {productMeta.health_score ?? 0}%
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Jobs for this product */}
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-[#1D1D1F] mb-3">
              关联定时任务
              <span className="ml-1.5 text-xs text-[#86868B] font-normal">{jobs.length} 个</span>
            </h3>
          </div>

          {jobs.length === 0 ? (
            <div className="text-center py-8 text-sm text-[#86868B]">该产品暂无定时任务</div>
          ) : (
            <div className="space-y-2">
              {jobs.map(job => {
                const state = pauseState(job)
                const actKey = `${job.id}_`
                return (
                  <div
                    key={job.id}
                    className={`bg-white rounded-xl border border-black/6 p-4 transition-all ${
                      job.pending ? 'opacity-70' : ''
                    }`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-base">{triggerIcon(job)}</span>
                        <div>
                          <div className="text-sm font-semibold text-[#1D1D1F]">
                            {resolveJobName(job.id)}
                          </div>
                          <span
                            className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${state.cls}`}
                          >
                            {state.label}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {!job.pending ? (
                          <button
                            disabled={actionLoading?.startsWith(actKey)}
                            onClick={() => onAction(job.id, 'pause')}
                            className="px-2.5 py-1 text-[10px] font-medium rounded-lg border border-[#FF9500]/30 text-[#FF9500] hover:bg-[#FF9500]/5 disabled:opacity-50"
                          >
                            {actionLoading === `${job.id}_pause` ? '...' : '暂停'}
                          </button>
                        ) : (
                          <button
                            disabled={actionLoading?.startsWith(actKey)}
                            onClick={() => onAction(job.id, 'resume')}
                            className="px-2.5 py-1 text-[10px] font-medium rounded-lg border border-[#34C759]/30 text-[#34C759] hover:bg-[#34C759]/5 disabled:opacity-50"
                          >
                            {actionLoading === `${job.id}_resume` ? '...' : '恢复'}
                          </button>
                        )}
                        <button
                          disabled={actionLoading?.startsWith(actKey)}
                          onClick={() => onAction(job.id, 'trigger')}
                          className="px-2.5 py-1 text-[10px] font-medium rounded-lg border border-[#0071E3]/30 text-[#0071E3] hover:bg-[#0071E3]/5 disabled:opacity-50"
                        >
                          {actionLoading === `${job.id}_trigger` ? '...' : '执行'}
                        </button>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-2 border-t border-black/6">
                      <div>
                        <div className="text-[10px] text-[#C7C7CC]">触发器</div>
                        <div className="text-xs text-[#424245]">
                          {job.trigger.type === 'interval'
                            ? `间隔 ${job.trigger.interval_human}`
                            : job.trigger.type === 'cron'
                              ? job.trigger.cron_human || 'Cron'
                              : '未知'}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-[#C7C7CC]">下次执行</div>
                        <div className="text-xs text-[#424245]">
                          {job.next_run_time
                            ? new Date(job.next_run_time).toLocaleString('zh-CN')
                            : '—'}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
