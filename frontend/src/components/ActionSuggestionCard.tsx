import type { Action } from '../types'

interface Props {
  actions: Action[]
  onAction?: (action: Action, decision: 'confirm' | 'skip') => void
}

const riskColors = {
  low: 'bg-[#34C759]/10 text-[#34C759]',
  medium: 'bg-[#FF9500]/10 text-[#FF9500]',
  high: 'bg-[#FF3B30]/10 text-[#FF3B30]',
  critical: 'bg-[#FF3B30]/20 text-[#FF3B30] font-semibold',
}

const riskLabels = { low: '低风险', medium: '中风险', high: '高风险', critical: '严重' }

const statusLabels: Record<string, string> = {
  pending: '',
  confirmed: '已确认',
  executing: '执行中...',
  done: '已完成',
  skipped: '已跳过',
}

export default function ActionSuggestionCard({ actions, onAction }: Props) {
  return (
    <div className="my-2 space-y-2 animate-[fade-in_0.2s_ease]">
      {actions.map(action => {
        const isDisabled = action.status === 'done' || action.status === 'skipped' || action.status === 'executing'

        return (
          <div
            key={action.id}
            className="rounded-lg border border-black/8 bg-white p-3"
          >
            {/* Title row */}
            <div className="flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm text-[#1D1D1F]">{action.label}</div>
                {action.description && (
                  <div className="text-xs text-[#86868B] mt-0.5">{action.description}</div>
                )}
              </div>
              {action.risk_level && (
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded shrink-0 ${riskColors[action.risk_level]}`}>
                  {riskLabels[action.risk_level]}
                </span>
              )}
            </div>

            {/* Metadata */}
            <div className="flex items-center gap-3 mt-2 text-[11px] text-[#86868B]">
              {action.skill && <span>via {action.skill}</span>}
              {action.confidence !== undefined && (
                <span>置信度 {Math.round(action.confidence * 100)}%</span>
              )}
              {action.expected_result && <span>{action.expected_result}</span>}
            </div>

            {/* Actions */}
            {action.status && action.status !== 'pending' ? (
              <div className="mt-2 text-xs text-[#86868B]">
                {statusLabels[action.status] || action.status}
              </div>
            ) : (
              <div className="flex items-center gap-2 mt-3">
                <button
                  disabled={isDisabled}
                  onClick={() => onAction?.(action, 'confirm')}
                  className="px-3 py-1.5 text-xs font-semibold rounded-md bg-[#1D1D1F] text-white hover:bg-[#2D2D2F] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  确认执行
                </button>
                <button
                  disabled={isDisabled}
                  onClick={() => onAction?.(action, 'skip')}
                  className="px-3 py-1.5 text-xs font-medium rounded-md bg-[#F5F5F7] text-[#86868B] hover:bg-[#E5E5EA] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  跳过
                </button>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
