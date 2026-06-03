interface DataPoint {
  label: string
  value: number
}

interface Props {
  data: DataPoint[]
  title?: string
  height?: number
  /** 可选颜色阈值：good（绿）, warn（黄）, bad（红） */
  thresholds?: { good: number; warn: number }
}

function barColor(value: number, thresholds?: { good: number; warn: number }): string {
  if (!thresholds) return 'bg-[#0071E3]'
  if (value >= thresholds.good) return 'bg-[#34C759]'
  if (value >= thresholds.warn) return 'bg-[#FFD60A]'
  return 'bg-[#FF3B30]'
}

export default function TrendChart({ data, title, height = 120, thresholds }: Props) {
  if (data.length === 0) return null

  const maxVal = Math.max(...data.map(d => d.value), 1)

  return (
    <div>
      {title && (
        <div className="text-xs font-medium text-[#86868B] mb-2">{title}</div>
      )}
      <div className="flex items-end gap-1.5" style={{ height }}>
        {data.map((d, i) => {
          const pct = (d.value / maxVal) * 100
          const color = barColor(d.value, thresholds)
          return (
            <div
              key={i}
              className="flex-1 flex flex-col items-center justify-end h-full group relative"
            >
              {/* 悬浮提示 */}
              <div className="absolute bottom-full mb-1 hidden group-hover:block z-10">
                <div className="bg-[#1D1D1F] text-white text-[10px] px-2 py-1 rounded-md whitespace-nowrap shadow-lg">
                  {d.label}: {d.value}
                  <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-[#1D1D1F]" />
                </div>
              </div>
              {/* 柱状条 */}
              <div
                className={`w-full rounded-t transition-all duration-300 ${color} hover:opacity-80`}
                style={{ height: `${Math.max(pct, 4)}%` }}
                title={`${d.label}: ${d.value}`}
              />
              {/* 短标签 */}
              {data.length <= 12 && (
                <span className="text-[9px] text-[#C7C7CC] mt-1 truncate w-full text-center">
                  {d.label.length > 4 ? d.label.slice(0, 4) + '…' : d.label}
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
