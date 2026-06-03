import { useState, useEffect, useCallback } from 'react'
import AgentConfigCard from '../../components/config/AgentConfigCard'
import AgentEditModal from '../../components/config/AgentEditModal'
import ConfigTabs from '../../components/config/ConfigTabs'
import type { AgentListItem, AgentDetail } from '../../api/config'
import { agentsApi } from '../../api/config'

export default function AgentConfigPage() {
  const [agents, setAgents] = useState<AgentListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<AgentDetail | null>(null)
  const [showNew, setShowNew] = useState(false)

  const loadAgents = useCallback(async () => {
    setLoading(true)
    try {
      const data = await agentsApi.list()
      setAgents(data)
    } catch {
      // 后端不可用时保持空列表
      setAgents([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadAgents() }, [loadAgents])

  const handleEdit = async (agent: AgentListItem) => {
    try {
      const detail = await agentsApi.get(agent.id)
      setEditing(detail)
    } catch {
      setEditing({ ...agent, system_prompt: '' })
    }
  }

  const handleDelete = async (id: string) => {
    if (!window.confirm('确定删除此 Agent？')) return
    try {
      await agentsApi.delete(id)
      loadAgents()
    } catch (e) {
      alert(e instanceof Error ? e.message : '删除失败')
    }
  }

  const handleToggle = async (id: string, enabled: boolean) => {
    try {
      await agentsApi.toggle(id, enabled)
      loadAgents()
    } catch (e) {
      alert(e instanceof Error ? e.message : '操作失败')
    }
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <ConfigTabs />

        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-[#1D1D1F]">Agent 配置</h1>
            <p className="text-sm text-[#86868B] mt-0.5">{agents.length} 个 Agent</p>
          </div>
          <button
            onClick={() => setShowNew(true)}
            className="px-4 py-2 text-sm font-semibold rounded-lg bg-[#1D1D1F] text-white hover:bg-[#2D2D2F] transition-colors"
          >
            + 新建 Agent
          </button>
        </div>

        {loading ? (
          <div className="text-center py-16 text-sm text-[#86868B]">加载中...</div>
        ) : agents.length === 0 ? (
          <div className="text-center py-16 text-sm text-[#86868B]">暂无 Agent，点击上方按钮创建</div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {agents.map(a => (
              <AgentConfigCard
                key={a.id}
                agent={a}
                onEdit={() => handleEdit(a)}
                onDelete={() => handleDelete(a.id)}
                onToggle={(enabled: boolean) => handleToggle(a.id, enabled)}
              />
            ))}
          </div>
        )}

        {/* Edit Modal */}
        {(editing || showNew) && (
          <AgentEditModal
            agent={editing}
            onClose={() => { setEditing(null); setShowNew(false) }}
            onSaved={() => { setEditing(null); setShowNew(false); loadAgents() }}
          />
        )}
      </div>
    </div>
  )
}
