import type { ModelConfigItem } from '../../api/config'

interface Props {
  config: ModelConfigItem
  onEdit: (config: ModelConfigItem) => void
  onDelete: (role: string) => void
}

/** 对 API Key 环境变量名做部分遮蔽 */
function maskKey(key: string): string {
  if (!key) return ''
  if (key.length <= 8) return key.slice(0, 3) + '****'
  return key.slice(0, 4) + '****' + key.slice(-4)
}

const roleLabels: Record<string, string> = {
  reasoning: '推理',
  fast: '快速',
  vision: '视觉',
  embedding: '嵌入',
}

export default function ModelConfigCard({ config, onEdit, onDelete }: Props) {
  return (
    <div className="bg-white rounded-xl border border-black/6 p-4 hover:shadow-sm transition-all">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-[#FF9F0A]/10 flex items-center justify-center text-sm font-bold text-[#FF9F0A]">
            {config.role[0].toUpperCase()}
          </div>
          <div>
            <div className="font-semibold text-sm text-[#1D1D1F]">
              {roleLabels[config.role] || config.role}
            </div>
            <div className="text-[11px] text-[#86868B]">{config.provider} · {config.model}</div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {onEdit && (
            <button onClick={() => onEdit(config)} className="text-xs text-[#0071E3] hover:underline px-1.5 py-0.5">编辑</button>
          )}
          {onDelete && (
            <button onClick={() => onDelete(config.role)} className="text-xs text-[#FF3B30] hover:underline px-1.5 py-0.5">删除</button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 mt-3 text-[11px] text-[#86868B]">
        <span>Role: <span className="text-[#1D1D1F] font-medium">{config.role}</span></span>
        <span>API Key: <span className="font-mono text-[#1D1D1F]">{maskKey(config.api_key_env)}</span></span>
        <span>Max Tokens: <span className="text-[#1D1D1F]">{config.max_tokens}</span></span>
        <span>Temperature: <span className="text-[#1D1D1F]">{config.temperature}</span></span>
      </div>

      {config.base_url && (
        <div className="text-[11px] text-[#0071E3] mt-1.5 truncate">{config.base_url}</div>
      )}
    </div>
  )
}
