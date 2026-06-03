import { useNotificationContext, type Severity } from '../context/NotificationContext'

const severityStyle: Record<Severity, { bg: string; dot: string; border: string }> = {
  low: { bg: 'bg-[#F5F5F7]', dot: 'bg-[#34C759]', border: 'border-[#E5E5EA]' },
  medium: { bg: 'bg-[#FFF9F0]', dot: 'bg-[#FF9500]', border: 'border-[#FFE5C4]' },
  high: { bg: 'bg-[#FFF5F5]', dot: 'bg-[#FF3B30]', border: 'border-[#FFD0CF]' },
  critical: { bg: 'bg-[#FF3B30]/5', dot: 'bg-[#FF3B30] ring-2 ring-[#FF3B30]/30', border: 'border-[#FF3B30]/30' },
}

export default function ToastNotification() {
  const { toasts, removeToast } = useNotificationContext()

  if (toasts.length === 0) return null

  return (
    <div className="fixed top-12 right-4 z-[9999] flex flex-col gap-2 w-80 pointer-events-none">
      {toasts.map(toast => {
        const style = severityStyle[toast.severity] || severityStyle.low
        return (
          <div
            key={toast.id}
            className={`pointer-events-auto animate-slide-in rounded-xl border ${style.border} ${style.bg} shadow-lg p-4 transition-all`}
          >
            <div className="flex items-start gap-3">
              <div className={`w-2 h-2 rounded-full shrink-0 mt-1 ${style.dot}`} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-[#1D1D1F]">{toast.title}</div>
                {toast.message && (
                  <div className="text-xs text-[#86868B] mt-0.5 line-clamp-2">{toast.message}</div>
                )}
                {toast.action && (
                  <button
                    onClick={toast.action.onClick}
                    className="mt-1.5 text-xs font-semibold text-[#0071E3] hover:underline"
                  >
                    {toast.action.label}
                  </button>
                )}
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="text-xs text-[#C7C7CC] hover:text-[#86868B] shrink-0"
              >
                ✕
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
