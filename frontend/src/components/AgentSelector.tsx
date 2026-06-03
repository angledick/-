import { useState, useRef, useEffect, useCallback } from 'react'
import { useAgentConfigStore } from '../context/AppStore'
import { agentsApi, type AgentListItem } from '../api/config'

export default function AgentSelector() {
  const agentId = useAgentConfigStore(s => s.agent_id)
  const setAgentId = useAgentConfigStore(s => s.setAgentId)
  const [agents, setAgents] = useState<AgentListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const data = await agentsApi.list()
        setAgents(data)
      } catch {
        setAgents([])
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const selected = agents.find(a => a.id === agentId) || agents.find(a => a.id === 'agent_qa') || agents[0]

  // 点击外部关闭
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleSelect = useCallback((id: string) => {
    setAgentId(id)
    setOpen(false)
  }, [setAgentId])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#F5F5F7] hover:bg-[#E5E5EA] text-sm transition-colors"
      >
        <span>🤖</span>
        <span className="font-medium text-[#1D1D1F]">
          {loading ? '加载中...' : selected?.name || '未选择 Agent'}
        </span>
        <span className="text-xs text-[#86868B]">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 w-64 bg-white rounded-lg border border-black/8 shadow-lg z-20 overflow-hidden">
          <div className="px-3 py-2 border-b border-black/6">
            <div className="text-[10px] font-semibold text-[#86868B] uppercase">选择 Agent</div>
          </div>
          {loading ? (
            <div className="px-3 py-4 text-center text-xs text-[#86868B]">加载中...</div>
          ) : agents.length === 0 ? (
            <div className="px-3 py-4 text-center text-xs text-[#86868B]">暂无可用 Agent</div>
          ) : agents.map(a => (
            <button
              key={a.id}
              onClick={() => handleSelect(a.id)}
              className={`w-full text-left px-3 py-2.5 flex items-center gap-2.5 transition-colors ${
                a.id === selected?.id ? 'bg-[#0071E3]/5' : 'hover:bg-[#F5F5F7]'
              }`}
            >
              <div className={`w-2 h-2 rounded-full ${a.id === selected?.id ? 'bg-[#0071E3]' : 'bg-[#C7C7CC]'}`} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-[#1D1D1F]">{a.name}</div>
                <div className="text-[11px] text-[#86868B] truncate">{a.description}</div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
