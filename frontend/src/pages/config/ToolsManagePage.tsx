import { useState, useEffect, useCallback } from 'react'
import ToolConfigCard from '../../components/config/ToolConfigCard'
import ToolEditModal from '../../components/config/ToolEditModal'
import ConfigTabs from '../../components/config/ConfigTabs'
import type { ToolItem } from '../../api/config'
import { toolsApi } from '../../api/config'

const CATEGORY_TABS = [
  { key: '', label: '全部' },
  { key: 'compliance', label: '合规' },
  { key: 'logistics', label: '物流' },
  { key: 'certification', label: '认证' },
  { key: 'general', label: '通用' },
  { key: 'custom', label: '自定义' },
] as const

export default function ToolsManagePage() {
  const [tools, setTools] = useState<ToolItem[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<ToolItem | null>(null)
  const [showNew, setShowNew] = useState(false)
  const [categoryFilter, setCategoryFilter] = useState('')

  const loadTools = useCallback(async () => {
    setLoading(true)
    try {
      const data = await toolsApi.list({ category: categoryFilter || undefined })
      setTools(data.tools)
    } catch {
      setTools([])
    } finally {
      setLoading(false)
    }
  }, [categoryFilter])

  useEffect(() => { loadTools() }, [loadTools])

  const handleEdit = (tool: ToolItem) => setEditing(tool)

  const handleDelete = async (id: string) => {
    if (!window.confirm('确定删除此 Tool？')) return
    try {
      await toolsApi.delete(id)
      loadTools()
    } catch (e) {
      alert(e instanceof Error ? e.message : '删除失败')
    }
  }

  const handleToggle = async (id: string) => {
    try {
      await toolsApi.toggle(id)
      loadTools()
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
            <h1 className="text-lg font-semibold text-[#1D1D1F]">Tools 管理</h1>
            <p className="text-sm text-[#86868B] mt-0.5">
              {tools.filter(t => t.enabled).length}/{tools.length} 个已启用
            </p>
          </div>
          <button onClick={() => setShowNew(true)} className="px-4 py-2 text-sm font-semibold rounded-lg bg-[#1D1D1F] text-white hover:bg-[#2D2D2F] transition-colors">
            + 新建 Tool
          </button>
        </div>

        {/* 分类过滤 */}
        <div className="flex items-center gap-1 mb-4">
          {CATEGORY_TABS.map(tab => (
            <button
              key={tab.key}
              onClick={() => setCategoryFilter(tab.key)}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                categoryFilter === tab.key
                  ? 'bg-[#1D1D1F] text-white font-semibold'
                  : 'bg-[#F5F5F7] text-[#86868B] hover:bg-[#E5E5EA]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="text-center py-16 text-sm text-[#86868B]">加载中...</div>
        ) : tools.length === 0 ? (
          <div className="text-center py-16 text-sm text-[#86868B]">暂无 Tool</div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {tools.map(t => (
              <ToolConfigCard
                key={t.id}
                tool={t}
                onEdit={() => handleEdit(t)}
                onDelete={() => handleDelete(t.id)}
                onToggle={() => handleToggle(t.id)}
              />
            ))}
          </div>
        )}

        {(editing || showNew) && (
          <ToolEditModal
            tool={editing}
            onClose={() => { setEditing(null); setShowNew(false) }}
            onSaved={() => { setEditing(null); setShowNew(false); loadTools() }}
          />
        )}
      </div>
    </div>
  )
}
