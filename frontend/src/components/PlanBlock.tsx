import type { PlanStep } from '../types'

interface Props {
  steps: PlanStep[]
  current: number
}

const statusIcon: Record<PlanStep['status'], string> = {
  pending: '⏳',
  running: '🔄',
  done: '✅',
  failed: '❌',
}

export default function PlanBlock({ steps, current }: Props) {
  const doneCount = steps.filter(s => s.status === 'done').length

  return (
    <div className="my-2 rounded-lg border border-black/8 bg-white overflow-hidden animate-[fade-in_0.2s_ease]">
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-black/6 flex items-center gap-2">
        <span className="text-sm">📋</span>
        <span className="font-semibold text-sm text-[#1D1D1F] flex-1">执行计划</span>
        <span className="text-xs text-[#86868B]">{doneCount}/{steps.length} 步</span>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-[#F5F5F7]">
        <div
          className="h-full bg-[#0071E3] transition-all duration-500 rounded-full"
          style={{ width: `${steps.length > 0 ? (doneCount / steps.length) * 100 : 0}%` }}
        />
      </div>

      {/* Steps */}
      <div className="px-3 py-2">
        {steps.map((step, i) => (
          <div
            key={step.id || i}
            className={`flex items-start gap-2 py-1.5 ${
              i === current ? 'bg-[#0071E3]/5 -mx-1 px-1 rounded' : ''
            }`}
          >
            <span className="text-sm mt-0.5 shrink-0">{statusIcon[step.status]}</span>
            <div className="flex-1 min-w-0">
              <div className={`text-sm ${
                step.status === 'done' ? 'text-[#86868B] line-through' :
                step.status === 'running' ? 'text-[#1D1D1F] font-medium' :
                step.status === 'failed' ? 'text-[#FF3B30]' :
                'text-[#4A4A4D]'
              }`}>
                {step.action}
              </div>
              {step.skill && (
                <div className="text-[11px] text-[#0071E3] mt-0.5">via {step.skill}</div>
              )}
              {step.duration_ms !== undefined && (
                <div className="text-[10px] text-[#C7C7CC] mt-0.5">
                  {(step.duration_ms / 1000).toFixed(1)}s
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
