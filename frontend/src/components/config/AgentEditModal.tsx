import { useState, useEffect } from 'react'
import ConfigSelector from './ConfigSelector'
import type { AgentDetail, AgentUpsertRequest } from '../../api/config'
import { agentsApi } from '../../api/config'

interface Props {
  agent: AgentDetail | null  // null = 新建模式
  onClose: () => void
  onSaved: () => void
}

export default function AgentEditModal({ agent, onClose, onSaved }: Props) {
  const isNew = !agent

  const [form, setForm] = useState<AgentUpsertRequest>({
    name: '',
    type: 'worker',
    description: '',
    system_prompt: '',
    enabled: true,
    sort_order: 99,
  })

  const [skillIds, setSkillIds] = useState<string[]>([])
  const [toolIds, setToolIds] = useState<string[]>([])
  const [oauthIds, setOauthIds] = useState<string[]>([])

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  // 加载关联数据
  useEffect(() => {
    if (!agent) return
    setForm({
      name: agent.name,
      type: agent.type,
      description: agent.description,
      system_prompt: agent.system_prompt,
      enabled: agent.enabled,
      sort_order: agent.sort_order,
    })
    agentsApi.getSkills(agent.id).then(r => setSkillIds(r.skill_ids)).catch(() => {})
    agentsApi.getTools(agent.id).then(r => setToolIds(r.tool_ids)).catch(() => {})
    agentsApi.getOAuth(agent.id).then(r => setOauthIds(r.connection_ids)).catch(() => {})
  }, [agent])

  // 已加载 Agent 的关联数据在 useEffect 上方获取

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      if (isNew) {
        const created = await agentsApi.create(form)
        // 新建后设置关联
        await Promise.all([
          agentsApi.setSkills(created.id, skillIds),
          agentsApi.setTools(created.id, toolIds),
          agentsApi.setOAuth(created.id, oauthIds),
        ])
      } else {
        await agentsApi.update(agent!.id, form)
        await Promise.all([
          agentsApi.setSkills(agent!.id, skillIds),
          agentsApi.setTools(agent!.id, toolIds),
          agentsApi.setOAuth(agent!.id, oauthIds),
        ])
      }
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="w-[680px] max-h-[85vh] bg-white rounded-2xl shadow-xl overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-black/6 px-6 py-4 flex items-center justify-between z-10">
          <h2 className="text-lg font-semibold text-[#1D1D1F]">
            {isNew ? '新建 Agent' : `编辑 Agent: ${agent?.name}`}
          </h2>
          <button onClick={onClose} className="text-sm text-[#86868B] hover:text-[#1D1D1F]">✕</button>
        </div>

        <div className="p-6 space-y-5">
          {/* Error */}
          {error && (
            <div className="p-3 rounded-lg bg-[#FF3B30]/5 border border-[#FF3B30]/20 text-sm text-[#FF3B30]">{error}</div>
          )}

          {/* Basic fields */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-[#86868B] block mb-1.5">名称</label>
              <input
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30"
                placeholder="Agent 名称"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-[#86868B] block mb-1.5">类型</label>
              <select
                value={form.type}
                onChange={e => setForm(f => ({ ...f, type: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30 bg-white"
              >
                <option value="manager">Manager</option>
                <option value="worker">Worker</option>
                <option value="qa">QA</option>
              </select>
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-[#86868B] block mb-1.5">描述</label>
            <input
              value={form.description || ''}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30"
              placeholder="Agent 职责描述"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-[#86868B] block mb-1.5">System Prompt</label>
            <textarea
              value={form.system_prompt}
              onChange={e => setForm(f => ({ ...f, system_prompt: e.target.value }))}
              rows={6}
              className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm font-mono outline-none focus:border-[#0071E3]/30 resize-y"
              placeholder="Agent system prompt..."
            />
          </div>

          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={e => setForm(f => ({ ...f, enabled: e.target.checked }))}
                className="w-4 h-4"
              />
              <span className="text-sm text-[#1D1D1F]">启用</span>
            </label>
            <div className="flex items-center gap-2">
              <label className="text-xs text-[#86868B]">排序</label>
              <input
                type="number"
                value={form.sort_order}
                onChange={e => setForm(f => ({ ...f, sort_order: parseInt(e.target.value) || 99 }))}
                className="w-16 px-2 py-1 rounded border border-black/10 text-sm outline-none"
              />
            </div>
          </div>

          <ConfigSelector
            skillIds={skillIds}
            toolIds={toolIds}
            oauthIds={oauthIds}
            onSkillChange={setSkillIds}
            onToolChange={setToolIds}
            onOAuthChange={setOauthIds}
          />
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-white border-t border-black/6 px-6 py-4 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-[#F5F5F7] text-[#86868B] hover:bg-[#E5E5EA] transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !form.name || !form.system_prompt}
            className="px-4 py-2 text-sm font-semibold rounded-lg bg-[#1D1D1F] text-white hover:bg-[#2D2D2F] transition-colors disabled:opacity-40"
          >
            {saving ? '保存中...' : isNew ? '创建' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}
