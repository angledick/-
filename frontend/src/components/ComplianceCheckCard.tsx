import type { PipelineStageStatus } from '../api/config'

interface Props {
  stage: PipelineStageStatus
  checklist?: { item: string; passed: boolean }[]
}

const stageStatusConfig: Record<string, { label: string; color: string; bg: string }> = {
  healthy: { label: '健康', color: 'text-[#34C759]', bg: 'bg-[#34C759]/10' },
  warning: { label: '警告', color: 'text-[#FF9500]', bg: 'bg-[#FF9500]/10' },
  critical: { label: '危险', color: 'text-[#FF3B30]', bg: 'bg-[#FF3B30]/10' },
  unknown: { label: '未知', color: 'text-[#86868B]', bg: 'bg-[#86868B]/10' },
}

export default function ComplianceCheckCard({ stage, checklist }: Props) {
  const items = checklist || []
  const passed = items.filter(i => i.passed).length
  const total = items.length
  const st = stageStatusConfig[stage.status] || stageStatusConfig.unknown
  const passPct = Math.round(stage.pass_rate * 100)

  return (
    <div className="bg-white rounded-xl border border-black/6 overflow-hidden">
      {/* Header */}
      <div className="px-5 py-3 border-b border-black/6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-[#1D1D1F]">{stage.stage_name}</span>
          <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${st.bg} ${st.color}`}>
            {st.label}
          </span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-[#34C759]">{stage.passed_products} 通过</span>
          <span className={stage.risk_products > 0 ? 'text-[#FF3B30]' : 'text-[#86868B]'}>
            {stage.risk_products} 风险
          </span>
          {stage.pending_actions > 0 && (
            <span className="text-[#FF9500]">{stage.pending_actions} 待办</span>
          )}
        </div>
      </div>

      {/* Stats grid */}
      <div className="px-5 py-3 bg-[#F5F5F7]/50">
        <div className="grid grid-cols-3 gap-4">
          <StatItem label="总产品数" value={stage.total_products} color="text-[#1D1D1F]" />
          <StatItem label="通过率" value={`${passPct}%`} color={passPct >= 90 ? 'text-[#34C759]' : passPct >= 70 ? 'text-[#FF9500]' : 'text-[#FF3B30]'} />
          <StatItem label="待办事项" value={stage.pending_actions} color={stage.pending_actions > 0 ? 'text-[#FF9500]' : 'text-[#34C759]'} />
        </div>
        {/* Pass rate bar */}
        <div className="mt-3 h-2 bg-[#E5E5EA] rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              passPct >= 90 ? 'bg-[#34C759]' : passPct >= 70 ? 'bg-[#FF9500]' : 'bg-[#FF3B30]'
            }`}
            style={{ width: `${passPct}%` }}
          />
        </div>
      </div>

      {/* Checklist items */}
      {items.length > 0 && (
        <div className="px-5 py-3 space-y-2">
          <div className="text-[10px] font-semibold text-[#86868B] uppercase tracking-wider mb-2">
            检查项 · {passed}/{total} 通过
          </div>
          {items.map((item, i) => (
            <div key={i} className="flex items-start gap-2.5">
              <span className="mt-0.5 shrink-0">{item.passed ? '✅' : '❌'}</span>
              <div className="flex-1 min-w-0">
                <span className={`text-sm ${item.passed ? 'text-[#1D1D1F]' : 'text-[#FF3B30] font-medium'}`}>
                  {item.item}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function StatItem({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div>
      <div className={`text-lg font-semibold ${color}`}>{value}</div>
      <div className="text-[10px] text-[#86868B] mt-0.5">{label}</div>
    </div>
  )
}
