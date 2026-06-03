import { create } from 'zustand'
import type { ChatConfigData } from '../types'

// ── Agent 配置 Store ─────────────────────────────────────────────────────────

interface AgentConfigState extends ChatConfigData {
  /** 从后端加载配置 */
  loadConfig: () => Promise<void>
  /** 更新配置（同时推送到后端） */
  updateConfig: (patch: Partial<ChatConfigData>) => Promise<void>
  /** 设置当前 agent */
  setAgentId: (id: string | undefined) => void
  /** 切换工具启用状态 */
  toggleTool: (toolId: string) => void
  /** 切换技能启用状态 */
  toggleSkill: (skillId: string) => void
}

const API = '/api/v1'

export const useAgentConfigStore = create<AgentConfigState>((set, get) => ({
  agent_id: undefined,
  tools: [],
  skills: [],
  pipeline_mode: '6step',
  model_role: 'reasoning',

  loadConfig: async () => {
    try {
      const res = await fetch(`${API}/chat/config`)
      if (res.ok) {
        const data: ChatConfigData = await res.json()
        set({
          agent_id: data.agent_id,
          tools: data.tools ?? [],
          skills: data.skills ?? [],
          pipeline_mode: data.pipeline_mode ?? '6step',
          model_role: data.model_role ?? 'reasoning',
        })
      }
    } catch {
      // 后端不可用时保持默认值
    }
  },

  updateConfig: async (patch) => {
    const current = get()
    const merged: ChatConfigData = {
      agent_id: current.agent_id,
      tools: current.tools,
      skills: current.skills,
      pipeline_mode: current.pipeline_mode,
      model_role: current.model_role,
      ...patch,
    }
    // 乐观更新
    set(merged)
    try {
      await fetch(`${API}/chat/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(merged),
      })
    } catch {
      // 失败时回滚（简单策略：重新加载）
      get().loadConfig()
    }
  },

  setAgentId: (id) => {
    set({ agent_id: id })
    get().updateConfig({ agent_id: id })
  },

  toggleTool: (toolId) => {
    const tools = get().tools ?? []
    const next = tools.includes(toolId)
      ? tools.filter(t => t !== toolId)
      : [...tools, toolId]
    set({ tools: next })
    get().updateConfig({ tools: next })
  },

  toggleSkill: (skillId) => {
    const skills = get().skills ?? []
    const next = skills.includes(skillId)
      ? skills.filter(s => s !== skillId)
      : [...skills, skillId]
    set({ skills: next })
    get().updateConfig({ skills: next })
  },
}))

// ── 侧边栏 Store ─────────────────────────────────────────────────────────────

interface SidebarState {
  collapsed: boolean
  toggle: () => void
  setCollapsed: (v: boolean) => void
}

export const useSidebarStore = create<SidebarState>((set) => ({
  collapsed: false,
  toggle: () => set(s => ({ collapsed: !s.collapsed })),
  setCollapsed: (v) => set({ collapsed: v }),
}))
