import { useState, useEffect } from 'react'
import { useAgentConfigStore } from '../context/AppStore'
import { toolsApi, type ToolItem } from '../api/config'

export default function ToolPanel() {
  const enabledTools = useAgentConfigStore(s => s.tools) ?? []
  const toggleTool = useAgentConfigStore(s => s.toggleTool)
  const [tools, setTools] = useState<ToolItem[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        const data = await toolsApi.list()
        setTools(data.tools)
      } catch {
        setTools([])
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  return (
    <div className="relative">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#F5F5F7] hover:bg-[#E5E5EA] text-sm transition-colors"
      >
        <span>🔧</span>
        <span className="text-[#1D1D1F]">工具</span>
        <span className="text-xs text-[#86868B]">
          {loading ? '...' : `${enabledTools.length}/${tools.length}`}
        </span>
      </button>

      {expanded && (
        <div className="absolute top-full left-0 mt-1 w-64 bg-white rounded-lg border border-black/8 shadow-lg z-20 overflow-hidden">
          <div className="px-3 py-2 border-b border-black/6 flex items-center justify-between">
            <div className="text-[10px] font-semibold text-[#86868B] uppercase">工具列表</div>
            <button onClick={() => setExpanded(false)} className="text-xs text-[#86868B] hover:text-[#1D1D1F]">关闭</button>
          </div>
          <div className="max-h-64 overflow-y-auto">
            {loading ? (
              <div className="px-3 py-4 text-center text-xs text-[#86868B]">加载中...</div>
            ) : tools.length === 0 ? (
              <div className="px-3 py-4 text-center text-xs text-[#86868B]">暂无可用工具</div>
            ) : tools.map(tool => {
              const enabled = enabledTools.includes(tool.id)
              return (
                <button
                  key={tool.id}
                  onClick={() => toggleTool(tool.id)}
                  className="w-full text-left px-3 py-2 flex items-center gap-2 hover:bg-[#F5F5F7] transition-colors"
                >
                  <span className={`text-sm ${enabled ? 'text-[#34C759]' : 'text-[#C7C7CC]'}`}>
                    {enabled ? '✅' : '⬚'}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-[#1D1D1F] truncate">{tool.name}</div>
                    <div className="text-[11px] text-[#86868B]">{tool.description}</div>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
