import { useState, useEffect, useCallback } from 'react'
import ModelConfigCard from '../../components/config/ModelConfigCard'
import ModelEditModal from '../../components/config/ModelEditModal'
import ConfigTabs from '../../components/config/ConfigTabs'
import type { ModelConfigItem } from '../../api/config'
import { modelConfigsApi } from '../../api/config'

export default function ModelConfigPage() {
  const [configs, setConfigs] = useState<ModelConfigItem[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<ModelConfigItem | null>(null)
  const [showNew, setShowNew] = useState(false)

  const loadConfigs = useCallback(async () => {
    setLoading(true)
    try {
      const data = await modelConfigsApi.list()
      setConfigs(data.configs)
    } catch {
      setConfigs([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadConfigs() }, [loadConfigs])

  const handleEdit = (cfg: ModelConfigItem) => setEditing(cfg)

  const handleDelete = async (role: string) => {
    if (!window.confirm(`确定删除「${role}」模型配置？`)) return
    try {
      await modelConfigsApi.delete(role)
      loadConfigs()
    } catch (e) {
      alert(e instanceof Error ? e.message : '删除失败')
    }
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <ConfigTabs />

        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-[#1D1D1F]">模型配置</h1>
            <p className="text-sm text-[#86868B] mt-0.5">{configs.length} 个模型路由</p>
          </div>
          <button
            onClick={() => setShowNew(true)}
            className="px-4 py-2 text-sm font-semibold rounded-lg bg-[#1D1D1F] text-white hover:bg-[#2D2D2F] transition-colors"
          >
            + 新建配置
          </button>
        </div>

        {loading ? (
          <div className="text-center py-16 text-sm text-[#86868B]">加载中...</div>
        ) : configs.length === 0 ? (
          <div className="text-center py-16 text-sm text-[#86868B]">暂无模型配置，点击上方按钮创建</div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {configs.map(c => (
              <ModelConfigCard
                key={c.role}
                config={c}
                onEdit={() => handleEdit(c)}
                onDelete={() => handleDelete(c.role)}
              />
            ))}
          </div>
        )}

        {(editing || showNew) && (
          <ModelEditModal
            config={editing}
            onClose={() => { setEditing(null); setShowNew(false) }}
            onSaved={() => { setEditing(null); setShowNew(false); loadConfigs() }}
          />
        )}
      </div>
    </div>
  )
}
