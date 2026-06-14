import { useEffect, useState } from 'react'
import { proactiveApi, type BriefItem } from '../api/config'
import { useNotificationContext } from '../context/NotificationContext'

interface Props {
  className?: string
}

export default function DailyBrief({ className = '' }: Props) {
  const { notifications } = useNotificationContext()
  const [brief, setBrief] = useState<BriefItem | null>(null)

  useEffect(() => {
    proactiveApi.getBrief(1)
      .then(res => {
        if (res.briefs && res.briefs.length > 0) {
          const lastBrief = res.briefs[res.briefs.length - 1]
          if (lastBrief) setBrief(lastBrief)
        }
      })
      .catch(() => { /* partial failure tolerated */ })
  }, [])

  const todayStart = new Date()
  todayStart.setHours(0, 0, 0, 0)

  const todayNotifs = notifications.filter(n => n.timestamp >= todayStart.getTime())
  const unread = notifications.filter(n => !n.read)
  const recentAffected = notifications
    .filter(n => n.affectedProducts && n.affectedProducts.length > 0)
    .slice(0, 5)

  return (
    <div className={`bg-white rounded-xl border border-black/6 p-5 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-[#1D1D1F]">每日简报</h2>
          <p className="text-xs text-[#86868B] mt-0.5">
            {new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })}
          </p>
        </div>
        <div className="text-2xl">📊</div>
      </div>

      {/* Stats grid — 优先展示后端brief数据，fallback到前端通知 */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        <BriefStat label="活跃产品" value={brief?.summary.active_products ?? todayNotifs.length} color="text-[#1D1D1F]" />
        <BriefStat label="待处理预警" value={brief?.summary.pending_alerts ?? unread.length} color={(brief?.summary.pending_alerts ?? 0) > 0 ? 'text-[#FF9500]' : 'text-[#34C759]'} />
        <BriefStat label="合规通过率" value={brief ? `${brief.summary.compliance_pass_rate}%` : '-'} color={brief && brief.summary.compliance_pass_rate >= 80 ? 'text-[#34C759]' : 'text-[#FF9500]'} />
        <BriefStat label="法规更新" value={brief?.summary.regulation_changes ?? notifications.length} color={(brief?.summary.regulation_changes ?? 0) > 0 ? 'text-[#FF3B30]' : 'text-[#86868B]'} />
      </div>

      {/* 后端简报建议 */}
      {brief && brief.recommendations.length > 0 && (
        <div className="pt-3 border-t border-black/6 mb-3">
          <div className="text-[10px] font-semibold text-[#86868B] uppercase tracking-wider mb-2">建议</div>
          <ul className="space-y-1">
            {brief.recommendations.map((rec, i) => (
              <li key={i} className="text-[11px] text-[#1D1D1F] flex items-start gap-1.5">
                <span className="text-[#0071E3] mt-0.5 shrink-0">•</span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 后端简报高亮 */}
      {brief && brief.highlights.length > 0 && (
        <div className="pt-3 border-t border-black/6 mb-3">
          <div className="text-[10px] font-semibold text-[#86868B] uppercase tracking-wider mb-2">今日亮点</div>
          <ul className="space-y-1">
            {brief.highlights.map((hl, i) => (
              <li key={i} className="text-[11px] text-[#1D1D1F] flex items-start gap-1.5">
                <span className="text-[#34C759] mt-0.5 shrink-0">✦</span>
                <span>{hl}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Affected products */}
      {recentAffected.length > 0 && (
        <div className="pt-3 border-t border-black/6">
          <div className="text-[10px] font-semibold text-[#86868B] uppercase tracking-wider mb-2">涉及产品</div>
          <div className="flex flex-wrap gap-1.5">
            {recentAffected.map((n) =>
              n.affectedProducts?.map(pid => (
                <span
                  key={`${n.id}_${pid}`}
                  className="text-[11px] px-2 py-0.5 rounded-full bg-[#F5F5F7] text-[#86868B]"
                >
                  {pid}
                </span>
              ))
            ).flat().slice(0, 8)}
          </div>
        </div>
      )}

      {/* Empty state */}
      {notifications.length === 0 && (
        <div className="text-center py-4">
          <div className="text-sm text-[#86868B]">暂无数据，连接后端后将自动加载</div>
        </div>
      )}
    </div>
  )
}

function BriefStat({ label, value, color }: { label: string; value: number | string; color: string }) {
  return (
    <div className="text-center">
      <div className={`text-lg font-semibold ${color}`}>{value}</div>
      <div className="text-[10px] text-[#86868B] mt-0.5">{label}</div>
    </div>
  )
}
