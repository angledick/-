import type { OAuthConnection } from '../../api/config'

interface Props {
  oauth: OAuthConnection
  onEdit?: (oauth: OAuthConnection) => void
  onDelete?: (id: string) => void
  onTest?: (id: string) => void
}

const statusColors: Record<string, string> = {
  connected: 'bg-[#34C759]/10 text-[#34C759]',
  disconnected: 'bg-[#86868B]/10 text-[#86868B]',
  connecting: 'bg-[#FFD60A]/10 text-[#FFD60A]',
  error: 'bg-[#FF3B30]/10 text-[#FF3B30]',
}
const statusIcons: Record<string, string> = {
  connected: '✓',
  disconnected: '○',
  connecting: '◌',
  error: '✕',
}
const statusLabels: Record<string, string> = { connected: '已连接', disconnected: '未连接', connecting: '连接中', error: '错误' }

function fmtDate(iso?: string): string {
  if (!iso) return ''
  try { return new Date(iso).toLocaleDateString('zh-CN') } catch { return iso }
}

export default function OAuthConfigCard({ oauth, onEdit, onDelete, onTest }: Props) {
  const hasToken = !!oauth.token?.access_token
  const providerIcon = oauth.provider === 'shopify' ? '🛒' : oauth.provider === 'feishu' ? '📮' : oauth.provider === 'dingtalk' ? '💬' : '🔗'

  return (
    <div className="bg-white rounded-xl border border-black/6 p-4 hover:shadow-sm transition-all">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-[#AF52DE]/10 flex items-center justify-center shrink-0 text-sm">{providerIcon}</div>
          <div className="min-w-0">
            <div className="font-semibold text-sm text-[#1D1D1F] truncate">{oauth.label || oauth.provider}</div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-[11px] text-[#86868B]">{oauth.provider}</span>
              <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${statusColors[oauth.status]}`}>
                {statusIcons[oauth.status]} {statusLabels[oauth.status]}
              </span>
              {hasToken && (
                <span className="text-[10px] text-[#34C759]">● token</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Error detail */}
      {oauth.last_error && (
        <div className="text-xs text-[#FF3B30] mb-2 px-2.5 py-1.5 rounded-lg bg-[#FF3B30]/5 line-clamp-2">
          {oauth.last_error}
        </div>
      )}

      {/* Timestamps */}
      <div className="flex items-center gap-4 text-[10px] text-[#C7C7CC] mb-2">
        {oauth.created_at && <span>创建于 {fmtDate(oauth.created_at)}</span>}
        {oauth.updated_at && <span>更新于 {fmtDate(oauth.updated_at)}</span>}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 mt-1">
        {onTest && (
          <button onClick={() => onTest(oauth.id)} className="text-xs px-2.5 py-1 rounded-md bg-[#F5F5F7] hover:bg-[#E5E5EA] text-[#1D1D1F] transition-colors">
            测试连接
          </button>
        )}
        {onEdit && (
          <button onClick={() => onEdit(oauth)} className="text-xs text-[#0071E3] hover:underline px-1.5 py-0.5">编辑</button>
        )}
        {onDelete && (
          <button onClick={() => onDelete(oauth.id)} className="text-xs text-[#FF3B30] hover:underline px-1.5 py-0.5">断开</button>
        )}
      </div>
    </div>
  )
}
