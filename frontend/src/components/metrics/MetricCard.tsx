interface Props {
  label: string
  value: string | number
  delta?: { value: string; positive: boolean }
  icon: string
  subtitle?: string
}

export default function MetricCard({ label, value, delta, icon, subtitle }: Props) {
  return (
    <div className="bg-white rounded-xl border border-black/6 p-5">
      <div className="flex items-start justify-between mb-3">
        <span className="text-sm text-[#86868B] font-medium">{label}</span>
        <span className="text-lg shrink-0">{icon}</span>
      </div>
      <div className="text-2xl font-semibold text-[#1D1D1F] tabular-nums">{value}</div>
      {subtitle && (
        <div className="text-xs text-[#86868B] mt-1">{subtitle}</div>
      )}
      {delta && (
        <div className={`flex items-center gap-1 mt-2 text-xs font-medium ${
          delta.positive ? 'text-[#34C759]' : 'text-[#FF3B30]'
        }`}>
          <span>{delta.positive ? '↑' : '↓'}</span>
          <span>{delta.value}</span>
          <span className="text-[#C7C7CC] font-normal">vs 上月</span>
        </div>
      )}
    </div>
  )
}
