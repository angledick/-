import type { PipelineStage } from '../types'

interface Props {
  stages: PipelineStage[]
  activeStage: string | null
  onStageClick: (id: string | null) => void
}

const PASS_RATE_COLORS = {
  high: { bar: 'bg-[#34C759]', text: 'text-[#34C759]', bg: 'bg-[#34C759]/10' },
  mid: { bar: 'bg-[#FF9500]', text: 'text-[#FF9500]', bg: 'bg-[#FF9500]/10' },
  low: { bar: 'bg-[#FF3B30]', text: 'text-[#FF3B30]', bg: 'bg-[#FF3B30]/10' },
} as const

function getRateColor(rate: number) {
  if (rate >= 90) return PASS_RATE_COLORS.high
  if (rate >= 70) return PASS_RATE_COLORS.mid
  return PASS_RATE_COLORS.low
}

export default function PipelineNav({ stages, activeStage, onStageClick }: Props) {
  return (
    <div className="space-y-2">
      {stages.map((stage, idx) => {
        const isActive = activeStage === stage.id
        const colors = getRateColor(stage.pass_rate)

        return (
          <div key={stage.id}>
            <button
              onClick={() => onStageClick(isActive ? null : stage.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all text-left ${
                isActive
                  ? 'bg-[#F5F5F7] ring-1 ring-black/6'
                  : 'hover:bg-[#FAFAFA]'
              }`}
            >
              {/* Order with connector */}
              <div className="flex items-center gap-2 shrink-0">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold ${colors.bg} ${colors.text}`}>
                  {stage.order}
                </div>
                {idx < stages.length - 1 && (
                  <div className="w-px h-4 bg-[#E5E5EA]" />
                )}
              </div>

              {/* Name + desc */}
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-[#1D1D1F]">{stage.name}</div>
                {stage.description && (
                  <div className="text-xs text-[#86868B] mt-0.5 truncate">{stage.description}</div>
                )}
              </div>

              {/* Stats row */}
              <div className="flex items-center gap-4 shrink-0">
                {/* Pass rate */}
                <div className="text-right min-w-[48px]">
                  <div className="text-[10px] text-[#86868B]">通过率</div>
                  <div className={`text-sm font-semibold ${colors.text}`}>{stage.pass_rate}%</div>
                </div>
                {/* Progress bar */}
                <div className="w-20 h-1.5 bg-[#F5F5F7] rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${colors.bar} transition-all`}
                    style={{ width: `${stage.pass_rate}%` }}
                  />
                </div>
                {/* Risk products */}
                {stage.risk_products > 0 && (
                  <div className="text-right min-w-[40px]">
                    <div className="text-[10px] text-[#86868B]">风险</div>
                    <div className="text-sm font-semibold text-[#FF9500]">{stage.risk_products}</div>
                  </div>
                )}
                {/* Pending */}
                {stage.pending_tasks > 0 && (
                  <div className="text-right min-w-[40px]">
                    <div className="text-[10px] text-[#86868B]">待办</div>
                    <div className="text-sm font-semibold text-[#FF3B30]">{stage.pending_tasks}</div>
                  </div>
                )}
              </div>

              {/* Expand indicator */}
              <span className="text-xs text-[#86868B] shrink-0">{isActive ? '▲' : '▼'}</span>
            </button>
          </div>
        )
      })}
    </div>
  )
}
