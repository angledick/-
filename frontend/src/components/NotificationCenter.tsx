import { useState, useRef, useEffect } from 'react'
import { useNotificationContext, type Severity } from '../context/NotificationContext'
import { useNavigate } from 'react-router-dom'

const severityDot: Record<Severity, string> = {
  low: 'bg-[#34C759]',
  medium: 'bg-[#FF9500]',
  high: 'bg-[#FF3B30]',
  critical: 'bg-[#FF3B30] ring-2 ring-[#FF3B30]/30',
}

const typeIcons: Record<string, string> = {
  compliance_check_failed: '❌',
  certification_expiry: '🔐',
  regulation_change: '📜',
  risk_alert: '⚠',
  product_created: '📦',
  product_updated: '🔄',
  system: '⚙',
}

function formatTime(ts: number): string {
  const diff = Date.now() - ts
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return `${Math.floor(diff / 86400000)}天前`
}

export default function NotificationCenter() {
  const { notifications, unreadCount, dismissNotification, markAllRead, clearAll } = useNotificationContext()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const sorted = [...notifications].sort((a, b) => b.timestamp - a.timestamp).slice(0, 30)

  return (
    <div ref={ref} className="relative">
      {/* Bell button */}
      <button
        onClick={() => setOpen(!open)}
        className="relative text-sm text-[#86868B] hover:text-[#1D1D1F] transition-colors"
        title="通知中心"
      >
        <span className="text-base">🔔</span>
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[16px] h-4 flex items-center justify-center px-1 rounded-full bg-[#FF3B30] text-[10px] font-bold text-white leading-none">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute top-full right-0 mt-2 w-80 bg-white rounded-xl border border-black/8 shadow-xl z-50 max-h-[70vh] flex flex-col">
          {/* Header */}
          <div className="shrink-0 px-4 py-3 border-b border-black/6 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-[#1D1D1F]">通知</span>
              {unreadCount > 0 && (
                <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-[#FF3B30]/10 text-[#FF3B30]">
                  {unreadCount} 条未读
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && (
                <button onClick={markAllRead} className="text-[11px] text-[#0071E3] hover:underline">全部已读</button>
              )}
              <button onClick={clearAll} className="text-[11px] text-[#86868B] hover:text-[#1D1D1F]">清空</button>
            </div>
          </div>

          {/* List */}
          <div className="flex-1 overflow-y-auto">
            {sorted.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-[#86868B]">暂无通知</div>
            ) : sorted.map(n => (
              <div
                key={n.id}
                className={`px-4 py-3 flex items-start gap-2.5 border-b border-black/4 last:border-none cursor-pointer transition-colors ${
                  n.read ? 'opacity-60 hover:opacity-80' : 'hover:bg-[#F5F5F7]'
                }`}
                onClick={() => {
                  dismissNotification(n.id)
                  if (n.actionUrl) navigate(n.actionUrl)
                }}
              >
                <span className="text-sm shrink-0 mt-0.5">{typeIcons[n.type] || '📋'}</span>
                <div className="flex-1 min-w-0">
                  <div className={`text-sm ${n.read ? 'text-[#86868B]' : 'text-[#1D1D1F] font-medium'}`}>
                    {n.title}
                  </div>
                  {n.message && (
                    <div className="text-[11px] text-[#86868B] mt-0.5 line-clamp-2">{n.message}</div>
                  )}
                  <div className="flex items-center gap-2 mt-1">
                    <div className={`w-1.5 h-1.5 rounded-full ${severityDot[n.severity] || 'bg-[#86868B]'}`} />
                    <span className="text-[10px] text-[#C7C7CC]">{formatTime(n.timestamp)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
