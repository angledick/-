import { useState } from 'react'

type Status = 'pending' | 'running' | 'completed' | 'failed'

interface Step {
  name: string
  status: Status
  message?: string
}

interface Props {
  title: string
  steps: Step[]
  onRetry?: () => void
  onClose?: () => void
}

const statusConfig: Record<Status, { icon: string; text: string; color: string }> = {
  pending: { icon: '○', text: '等待中', color: 'text-[#C7C7CC]' },
  running: { icon: '◌', text: '执行中', color: 'text-[#0071E3]' },
  completed: { icon: '✓', text: '已完成', color: 'text-[#34C759]' },
  failed: { icon: '✕', text: '失败', color: 'text-[#FF3B30]' },
}

export default function ExecutionResult({ title, steps, onRetry, onClose }: Props) {
  const [collapsed, setCollapsed] = useState(false)

  const completedCount = steps.filter(s => s.status === 'completed').length
  const allDone = steps.every(s => s.status === 'completed' || s.status === 'failed')
  const hasError = steps.some(s => s.status === 'failed')
  const isRunning = steps.some(s => s.status === 'running')

  return (
    <div className="bg-white rounded-xl border border-black/6 overflow-hidden">
      {/* Header */}
      <div
        className="px-4 py-3 flex items-center justify-between cursor-pointer border-b border-black/6"
        onClick={() => setCollapsed(!collapsed)}
      >
        <div className="flex items-center gap-2">
          <span>{allDone ? (hasError ? '⚠' : '✅') : isRunning ? '⏳' : '📋'}</span>
          <div>
            <span className="text-sm font-semibold text-[#1D1D1F]">{title}</span>
            <span className="text-xs text-[#86868B] ml-2">{completedCount}/{steps.length}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {onClose && (
            <button
              onClick={(e) => { e.stopPropagation(); onClose() }}
              className="text-xs text-[#86868B] hover:text-[#1D1D1F]"
            >
              ✕
            </button>
          )}
          <span className="text-xs text-[#86868B]">{collapsed ? '▶' : '▼'}</span>
        </div>
      </div>

      {/* Steps */}
      {!collapsed && (
        <div className="px-4 py-3 space-y-2.5">
          {steps.map((step, i) => {
            const cfg = statusConfig[step.status]
            return (
              <div key={i} className="flex items-start gap-3">
                <span className={`text-sm font-mono shrink-0 mt-0.5 ${cfg.color}`}>{cfg.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`text-sm ${step.status === 'failed' ? 'text-[#FF3B30] font-medium' : 'text-[#1D1D1F]'}`}>
                      {step.name}
                    </span>
                    <span className={`text-[10px] ${cfg.color}`}>{cfg.text}</span>
                  </div>
                  {step.message && (
                    <div className="text-[11px] text-[#86868B] mt-0.5">{step.message}</div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Footer */}
      {hasError && onRetry && (
        <div className="px-4 py-2.5 border-t border-black/6 bg-[#FFF5F5] flex items-center justify-between">
          <span className="text-xs text-[#FF3B30]">部分步骤执行失败</span>
          <button
            onClick={onRetry}
            className="text-xs font-semibold text-[#0071E3] hover:underline"
          >
            重新执行
          </button>
        </div>
      )}
    </div>
  )
}
