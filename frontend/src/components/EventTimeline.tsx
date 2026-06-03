interface TimelineEvent {
  id: string
  type: string
  title: string
  description?: string
  timestamp: string
  severity?: 'low' | 'medium' | 'high' | 'critical'
}

interface Props {
  events: TimelineEvent[]
  title?: string
}

const severityColors = {
  low: 'bg-[#34C759]',
  medium: 'bg-[#FF9500]',
  high: 'bg-[#FF3B30]',
  critical: 'bg-[#FF3B30] ring-2 ring-[#FF3B30]/30',
}

const typeIcons: Record<string, string> = {
  compliance: '✓',
  certification: '📜',
  regulation: '⚖',
  risk_alert: '⚠',
  order: '📦',
  lifecycle: '🔄',
  system: '⚙',
  user_action: '👤',
}

export default function EventTimeline({ events, title = '事件时间线' }: Props) {
  if (events.length === 0) {
    return (
      <div className="p-4 text-center text-sm text-[#86868B]">
        暂无事件记录
      </div>
    )
  }

  return (
    <div>
      <div className="text-sm font-semibold text-[#1D1D1F] mb-3">{title}</div>
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-[9px] top-2 bottom-2 w-px bg-[#E5E5EA]" />

        {events.map((event, i) => (
          <div key={event.id || i} className="relative pl-7 pb-4 last:pb-0">
            {/* Dot */}
            <div
              className={`absolute left-[5px] top-1 w-2.5 h-2.5 rounded-full ${
                severityColors[event.severity || 'low'] || 'bg-[#86868B]'
              }`}
            />

            {/* Content */}
            <div>
              <div className="flex items-center gap-1.5">
                <span className="text-xs">{typeIcons[event.type] || '•'}</span>
                <span className="text-sm font-medium text-[#1D1D1F]">{event.title}</span>
              </div>
              {event.description && (
                <div className="text-xs text-[#86868B] mt-0.5 leading-relaxed">
                  {event.description}
                </div>
              )}
              <div className="text-[10px] text-[#C7C7CC] mt-1">{event.timestamp}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
