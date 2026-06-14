import { useState, useEffect, useCallback } from 'react'
import { agentsApi, pipelineApi, type AgentListItem } from '../api/config'

interface AgentStatus extends AgentListItem {
  enabled: boolean
}

interface AgentRuntime {
  agent_id: string
  associated_skills: string[]
  associated_tools: string[]
  associated_oauth: string[]
  status: string
}

function statusBadge(enabled: boolean) {
  return enabled
    ? { label: '活跃', cls: 'bg-[#34C759]/10 text-[#34C759]' }
    : { label: '停用', cls: 'bg-[#C7C7CC]/10 text-[#C7C7CC]' }
}

export default function AgentMonitorPage() {
  const [agents, setAgents] = useState<AgentStatus[]>([])
  const [runtimeMap, setRuntimeMap] = useState<Record<string, AgentRuntime>>({})
  const [pipelineScore, setPipelineScore] = useState<number | null>(null)
  const [pipelineUpdated, setPipelineUpdated] = useState('')
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [agentList, health] = await Promise.allSettled([
        agentsApi.list(),
        pipelineApi.health(),
      ])

      if (agentList.status === 'fulfilled') {
        const list = agentList.value
        setAgents(list.map(a => ({
          ...a,
          enabled: a.enabled ?? true,
        })))
        // 并行加载每个 Agent 的运行时状态
        const runtimes: Record<string, AgentRuntime> = {}
        await Promise.allSettled(
          list.map(async (a) => {
            try {
              const r = await agentsApi.getStatus(a.id) as unknown as AgentRuntime
              runtimes[a.id] = r
            } catch { /* ignore */ }
          })
        )
        setRuntimeMap(runtimes)
      }
      if (health.status === 'fulfilled') {
        setPipelineScore(Math.round(health.value.overall_score))
        setPipelineUpdated(health.value.last_updated)
      }
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const handleToggle = async (agentId: string, currentEnabled: boolean) => {
    try {
      await agentsApi.toggle(agentId, !currentEnabled)
      setAgents(prev => prev.map(a =>
        a.id === agentId ? { ...a, enabled: !currentEnabled } : a
      ))
    } catch {
      /* ignore */
    }
  }

  const filtered = searchQuery.trim()
    ? agents.filter(a =>
        a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        a.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (a.description || '').toLowerCase().includes(searchQuery.toLowerCase())
      )
    : agents

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-[#1D1D1F]">Agent 状态监控</h1>
              <p className="text-sm text-[#86868B] mt-1">
                系统 Agent 运行状态与健康度
                {pipelineScore !== null && ` · 流水线健康度: ${pipelineScore}%`}
              </p>
            </div>
            {pipelineUpdated && (
              <span className="text-xs text-[#C7C7CC]">
                更新于 {new Date(pipelineUpdated).toLocaleString('zh-CN')}
              </span>
            )}
          </div>
        </div>

        {loading ? (
          <div className="text-center py-16 text-sm text-[#86868B]">加载中...</div>
        ) : agents.length === 0 ? (
          <div className="bg-white rounded-xl border border-black/6 p-12 text-center">
            <div className="text-4xl mb-3">🤖</div>
            <div className="text-sm font-semibold text-[#1D1D1F] mb-1">暂无 Agent 数据</div>
            <div className="text-xs text-[#86868B]">连接后端后将自动加载 Agent 状态。</div>
          </div>
        ) : (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-4 gap-4 mb-6">
              <div className="bg-white rounded-xl border border-black/6 p-4">
                <div className="text-xs text-[#86868B] mb-1">Agent 总数</div>
                <div className="text-2xl font-semibold text-[#1D1D1F]">{agents.length}</div>
              </div>
              <div className="bg-white rounded-xl border border-black/6 p-4">
                <div className="text-xs text-[#86868B] mb-1">活跃中</div>
                <div className="text-2xl font-semibold text-[#34C759]">
                  {agents.filter(a => a.enabled).length}
                </div>
              </div>
              <div className="bg-white rounded-xl border border-black/6 p-4">
                <div className="text-xs text-[#86868B] mb-1">已停用</div>
                <div className="text-2xl font-semibold text-[#C7C7CC]">
                  {agents.filter(a => !a.enabled).length}
                </div>
              </div>
              <div className="bg-white rounded-xl border border-black/6 p-4">
                <div className="text-xs text-[#86868B] mb-1">关联配置总数</div>
                <div className="text-2xl font-semibold text-[#0071E3]">
                  {Object.values(runtimeMap).reduce((sum, r) =>
                    sum + r.associated_skills.length + r.associated_tools.length + r.associated_oauth.length, 0
                  )}
                </div>
              </div>
            </div>

            {/* 搜索 */}
            <div className="mb-4">
              <input
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30"
                placeholder="搜索 Agent 名称、类型或描述..."
              />
            </div>

            {/* Agent Cards */}
            <div className="space-y-3">
              {filtered.length === 0 ? (
                <div className="text-center py-8 text-sm text-[#86868B]">无匹配结果</div>
              ) : (
                filtered.map(agent => {
                  const badge = statusBadge(agent.enabled)
                  const rt = runtimeMap[agent.id]
                  const skillCount = rt?.associated_skills?.length ?? 0
                  const toolCount = rt?.associated_tools?.length ?? 0
                  const oauthCount = rt?.associated_oauth?.length ?? 0
                  return (
                    <div
                      key={agent.id}
                      className={`bg-white rounded-xl border border-black/6 p-5 transition-all ${
                        agent.enabled ? '' : 'opacity-60'
                      }`}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-white text-lg font-bold ${
                            agent.enabled ? 'bg-gradient-to-br from-[#1D1D1F] to-[#424245]' : 'bg-[#E5E5EA]'
                          }`}>
                            {(agent.name[0] || '?').toUpperCase()}
                          </div>
                          <div>
                            <div className="text-sm font-semibold text-[#1D1D1F]">{agent.name}</div>
                            <div className="flex items-center gap-2 mt-0.5">
                              <span className="text-xs text-[#86868B]">{agent.type}</span>
                              <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${badge.cls}`}>
                                {badge.label}
                              </span>
                            </div>
                          </div>
                        </div>
                        <button
                          onClick={() => handleToggle(agent.id, agent.enabled)}
                          className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                            agent.enabled
                              ? 'border-[#FF3B30]/30 text-[#FF3B30] hover:bg-[#FF3B30]/5'
                              : 'border-[#34C759]/30 text-[#34C759] hover:bg-[#34C759]/5'
                          }`}
                        >
                          {agent.enabled ? '停用' : '启用'}
                        </button>
                      </div>

                      <div className="text-sm text-[#86868B] line-clamp-2 mb-3">
                        {agent.description || '—'}
                      </div>

                      {/* 关联配置标签 */}
                      {(skillCount > 0 || toolCount > 0 || oauthCount > 0) && (
                        <div className="flex items-center gap-2 mb-3">
                          {skillCount > 0 && (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-[#0071E3]/10 text-[#0071E3]">
                              {skillCount} Skills
                            </span>
                          )}
                          {toolCount > 0 && (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-[#34C759]/10 text-[#34C759]">
                              {toolCount} Tools
                            </span>
                          )}
                          {oauthCount > 0 && (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-[#AF52DE]/10 text-[#AF52DE]">
                              {oauthCount} OAuth
                            </span>
                          )}
                        </div>
                      )}

                      <div className="grid grid-cols-3 gap-3 pt-3 border-t border-black/6">
                        <div>
                          <div className="text-[10px] text-[#C7C7CC] mb-0.5">系统提示</div>
                          <div className="text-xs text-[#424245] truncate">
                            {agent.system_prompt_preview
                              ? agent.system_prompt_preview.slice(0, 40) + (agent.system_prompt_preview.length > 40 ? '…' : '')
                              : '—'}
                          </div>
                        </div>
                        <div>
                          <div className="text-[10px] text-[#C7C7CC] mb-0.5">排序</div>
                          <div className="text-xs text-[#424245]">{agent.sort_order}</div>
                        </div>
                        <div>
                          <div className="text-[10px] text-[#C7C7CC] mb-0.5">更新</div>
                          <div className="text-xs text-[#424245]">
                            {agent.updated_at
                              ? new Date(agent.updated_at).toLocaleDateString('zh-CN')
                              : '—'}
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
