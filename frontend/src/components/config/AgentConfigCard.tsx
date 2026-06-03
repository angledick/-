import type { AgentListItem } from '../../api/config'

interface Props {
  agent: AgentListItem
  onEdit?: (agent: AgentListItem) => void
  onDelete?: (id: string) => void
  onToggle?: (enabled: boolean) => void
}

const typeLabels: Record<string, string> = { manager: '协调者', worker: '执行者', qa: '问答' }

export default function AgentConfigCard({ agent, onEdit, onDelete, onToggle }: Props) {
  return (
    <div className="bg-white rounded-xl border border-black/6 p-4 hover:shadow-sm transition-all">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#1D1D1F] to-[#424245] flex items-center justify-center text-white text-xs font-bold">
            {agent.name[0]}
          </div>
          <div>
            <div className="font-semibold text-sm text-[#1D1D1F]">{agent.name}</div>
            <div className="text-[11px] text-[#86868B]">{typeLabels[agent.type] || agent.type}</div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {onToggle && (
            <button
              onClick={() => onToggle(!agent.enabled)}
              className={`text-xs font-semibold px-2 py-0.5 rounded ${agent.enabled ? 'bg-[#34C759]/10 text-[#34C759]' : 'bg-[#F5F5F7] text-[#86868B]'}`}
            >
              {agent.enabled ? '活跃' : '停用'}
            </button>
          )}
          {onEdit && (
            <button onClick={() => onEdit(agent)} className="text-xs text-[#0071E3] hover:underline px-1.5 py-0.5">编辑</button>
          )}
          {onDelete && (
            <button onClick={() => onDelete(agent.id)} className="text-xs text-[#FF3B30] hover:underline px-1.5 py-0.5">删除</button>
          )}
        </div>
      </div>

      {agent.description && (
        <div className="text-xs text-[#86868B] mt-2">{agent.description}</div>
      )}

      {agent.system_prompt_preview && (
        <div className="text-[11px] text-[#86868B] mt-2 line-clamp-2">{agent.system_prompt_preview}</div>
      )}
    </div>
  )
}
