import { useState, useEffect, useCallback } from 'react'
import type { ToolItem } from '../../api/config'
import { toolsApi } from '../../api/config'
import { useNotificationContext } from '../../context/NotificationContext'

interface Props {
  tool: ToolItem | null  // null = 新建模式
  onClose: () => void
  onSaved: () => void
}

export default function ToolEditModal({ tool, onClose, onSaved }: Props) {
  const isNew = !tool
  const { addToast } = useNotificationContext()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [toolType, setToolType] = useState('')
  const [category, setCategory] = useState('general')
  const [enabled, setEnabled] = useState(true)

  // Config 键值对
  const [configEntries, setConfigEntries] = useState<{ key: string; value: string }[]>([])

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (tool) {
      setName(tool.name)
      setDescription(tool.description || '')
      setToolType(tool.tool_type || '')
      setCategory(tool.category || 'general')
      setEnabled(tool.enabled)
      if (tool.config) {
        setConfigEntries(
          Object.entries(tool.config).map(([k, v]) => ({
            key: k,
            value: typeof v === 'string' ? v : JSON.stringify(v),
          }))
        )
      }
    }
  }, [tool])

  const buildConfig = useCallback(() => {
    const cfg: Record<string, unknown> = {}
    for (const entry of configEntries) {
      if (entry.key.trim()) {
        // Try to parse as JSON, fallback to string
        try { cfg[entry.key.trim()] = JSON.parse(entry.value) }
        catch { cfg[entry.key.trim()] = entry.value }
      }
    }
    return Object.keys(cfg).length > 0 ? cfg : undefined
  }, [configEntries])

  const handleSave = async () => {
    if (!name.trim()) { setError('请输入名称'); return }
    setSaving(true)
    setError('')
    try {
      const payload = {
        name: name.trim(),
        description,
        tool_type: toolType || undefined,
        category,
        enabled,
        config: buildConfig(),
      }
      if (isNew) {
        await toolsApi.create(payload)
        addToast({ severity: 'low', title: 'Tool 已创建', message: name.trim() })
      } else {
        await toolsApi.update(tool!.id, payload)
        addToast({ severity: 'low', title: 'Tool 已更新', message: name.trim() })
      }
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败')
      addToast({ severity: 'high', title: '保存失败', message: e instanceof Error ? e.message : '未知错误' })
    } finally {
      setSaving(false)
    }
  }

  const addEntry = () => setConfigEntries(prev => [...prev, { key: '', value: '' }])
  const removeEntry = (i: number) => setConfigEntries(prev => prev.filter((_, idx) => idx !== i))
  const updateEntry = (i: number, field: 'key' | 'value', val: string) => {
    setConfigEntries(prev => prev.map((e, idx) => idx === i ? { ...e, [field]: val } : e))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="w-[540px] max-h-[90vh] bg-white rounded-2xl shadow-xl overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-black/6 px-6 py-4 flex items-center justify-between z-10">
          <h2 className="text-lg font-semibold text-[#1D1D1F]">
            {isNew ? '新建 Tool' : `编辑 Tool: ${tool?.name}`}
          </h2>
          <button onClick={onClose} className="text-sm text-[#86868B] hover:text-[#1D1D1F]">✕</button>
        </div>

        <div className="p-6 space-y-5">
          {error && (
            <div className="p-3 rounded-lg bg-[#FF3B30]/5 border border-[#FF3B30]/20 text-sm text-[#FF3B30]">{error}</div>
          )}

          {/* 名称 */}
          <div>
            <label className="text-xs font-semibold text-[#86868B] block mb-1.5">名称 *</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30"
              placeholder="Tool 名称"
            />
          </div>

          {/* 描述 */}
          <div>
            <label className="text-xs font-semibold text-[#86868B] block mb-1.5">描述</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30 resize-none"
              placeholder="Tool 功能描述"
            />
          </div>

          {/* 类型 + 分类 */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-[#86868B] block mb-1.5">类型</label>
              <select
                value={toolType}
                onChange={e => setToolType(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30 bg-white"
              >
                <option value="custom">自定义</option>
                <option value="builtin">内置</option>
                <option value="mcp">MCP</option>
                <option value="api">API</option>
                <option value="skill_wrapper">Skill 封装</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-[#86868B] block mb-1.5">分类</label>
              <select
                value={category}
                onChange={e => setCategory(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30 bg-white"
              >
                <option value="general">通用</option>
                <option value="compliance">合规</option>
                <option value="logistics">物流</option>
                <option value="certification">认证</option>
                <option value="custom">自定义</option>
              </select>
            </div>
          </div>

          {/* 启用开关 */}
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={enabled}
              onChange={e => setEnabled(e.target.checked)}
              className="w-4 h-4"
            />
            <span className="text-sm text-[#1D1D1F]">启用</span>
          </label>

          {/* Config 键值编辑器 */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-[#86868B]">配置参数</label>
              <button
                onClick={addEntry}
                className="text-xs text-[#0071E3] hover:underline px-1.5 py-0.5"
              >
                + 添加参数
              </button>
            </div>
            {configEntries.length === 0 ? (
              <div className="text-xs text-[#C7C7CC] px-1">暂无配置参数</div>
            ) : (
              <div className="space-y-2">
                {configEntries.map((entry, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input
                      value={entry.key}
                      onChange={e => updateEntry(i, 'key', e.target.value)}
                      className="w-[140px] px-2.5 py-1.5 rounded-lg border border-black/10 text-xs outline-none focus:border-[#0071E3]/30 font-mono"
                      placeholder="参数名"
                    />
                    <input
                      value={entry.value}
                      onChange={e => updateEntry(i, 'value', e.target.value)}
                      className="flex-1 px-2.5 py-1.5 rounded-lg border border-black/10 text-xs outline-none focus:border-[#0071E3]/30 font-mono"
                      placeholder="值（JSON 或字符串）"
                    />
                    <button
                      onClick={() => removeEntry(i)}
                      className="text-xs text-[#FF3B30] hover:underline shrink-0 px-1"
                    >
                      删除
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-white border-t border-black/6 px-6 py-4 flex items-center justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm font-medium rounded-lg bg-[#F5F5F7] text-[#86868B] hover:bg-[#E5E5EA] transition-colors">取消</button>
          <button
            onClick={handleSave}
            disabled={saving || !name.trim()}
            className="px-4 py-2 text-sm font-semibold rounded-lg bg-[#1D1D1F] text-white hover:bg-[#2D2D2F] transition-colors disabled:opacity-40"
          >
            {saving ? '保存中...' : isNew ? '创建' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}
