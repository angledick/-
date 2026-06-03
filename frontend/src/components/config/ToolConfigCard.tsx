import type { ToolItem } from '../../api/config'

interface Props {
  tool: ToolItem
  onEdit?: (tool: ToolItem) => void
  onDelete?: (id: string) => void
  onToggle?: (id: string) => void
}

export default function ToolConfigCard({ tool, onEdit, onDelete, onToggle }: Props) {
  const configKeys = tool.config ? Object.keys(tool.config) : []

  return (
    <div className="bg-white rounded-xl border border-black/6 p-4 hover:shadow-sm transition-all">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-[#34C759]/10 flex items-center justify-center shrink-0">🔧</div>
          <div className="min-w-0">
            <div className="font-semibold text-sm text-[#1D1D1F] truncate">{tool.name}</div>
            <div className="flex items-center gap-2 mt-0.5">
              {tool.tool_type && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#F5F5F7] text-[#86868B]">{tool.tool_type}</span>
              )}
              {tool.category && (
                <span className="text-[11px] text-[#86868B]">{tool.category}</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {onToggle && (
            <button
              onClick={() => onToggle(tool.id)}
              className={`text-xs font-semibold px-2 py-0.5 rounded transition-colors ${
                tool.enabled
                  ? 'bg-[#34C759]/10 text-[#34C759] hover:bg-[#34C759]/20'
                  : 'bg-[#F5F5F7] text-[#86868B] hover:bg-[#E5E5EA]'
              }`}
            >
              {tool.enabled ? '已启用' : '停用'}
            </button>
          )}
          {onEdit && (
            <button onClick={() => onEdit(tool)} className="text-xs text-[#0071E3] hover:underline px-1.5 py-0.5">编辑</button>
          )}
          {onDelete && (
            <button onClick={() => onDelete(tool.id)} className="text-xs text-[#FF3B30] hover:underline px-1.5 py-0.5">删除</button>
          )}
        </div>
      </div>

      {tool.description && (
        <div className="text-xs text-[#86868B] mb-2 line-clamp-2">{tool.description}</div>
      )}

      {/* Config preview */}
      {configKeys.length > 0 && (
        <div className="bg-[#F5F5F7] rounded-lg px-3 py-2 flex flex-wrap gap-x-4 gap-y-1">
          {configKeys.map(key => (
            <div key={key} className="text-[11px]">
              <span className="text-[#C7C7CC]">{key}</span>
              <span className="text-[#424245] ml-1">
                {typeof tool.config![key] === 'string'
                  ? (tool.config![key] as string).length > 20
                    ? (tool.config![key] as string).slice(0, 20) + '…'
                    : tool.config![key] as string
                  : JSON.stringify(tool.config![key]).slice(0, 20)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
