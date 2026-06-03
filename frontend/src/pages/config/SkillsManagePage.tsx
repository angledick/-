import { useState, useEffect, useCallback } from 'react'
import SkillConfigCard from '../../components/config/SkillConfigCard'
import FileImportModal from '../../components/config/FileImportModal'
import SkillEditModal from '../../components/config/SkillEditModal'
import ConfigTabs from '../../components/config/ConfigTabs'
import type { SkillItem } from '../../api/config'
import { skillsApi } from '../../api/config'

const STATUS_TABS = [
  { key: '', label: '全部' },
  { key: 'installed', label: '已安装' },
  { key: 'not_installed', label: '未安装' },
] as const

export default function SkillsManagePage() {
  const [skills, setSkills] = useState<SkillItem[]>([])
  const [loading, setLoading] = useState(true)
  const [showImport, setShowImport] = useState(false)
  const [editing, setEditing] = useState<SkillItem | null>(null)
  const [statusFilter, setStatusFilter] = useState('')

  const loadSkills = useCallback(async () => {
    setLoading(true)
    try {
      const data = await skillsApi.list({ status: statusFilter || undefined })
      setSkills(data.skills)
    } catch {
      setSkills([])
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => { loadSkills() }, [loadSkills])

  const handleEdit = (skill: SkillItem) => setEditing(skill)

  const handleDelete = async (id: string) => {
    if (!window.confirm('确定卸载此 Skill？')) return
    try {
      await skillsApi.delete(id)
      loadSkills()
    } catch (e) {
      alert(e instanceof Error ? e.message : '卸载失败')
    }
  }

  const handleRefresh = async (id: string) => {
    try {
      await skillsApi.refresh(id)
      loadSkills()
    } catch (e) {
      alert(e instanceof Error ? e.message : '刷新失败')
    }
  }

  const handleImport = async (source: { type: 'github' | 'zip' | 'manual'; value: string }) => {
    try {
      await skillsApi.install({
        name: source.value.split('/').pop() || source.value,
        source: source.type,
        source_url: source.type === 'github' ? source.value : undefined,
      })
      loadSkills()
    } catch (e) {
      alert(e instanceof Error ? e.message : '导入失败')
    }
    setShowImport(false)
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <ConfigTabs />

        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-[#1D1D1F]">Skills 管理</h1>
            <p className="text-sm text-[#86868B] mt-0.5">
              {skills.filter(s => s.installed).length}/{skills.length} 个已安装
            </p>
          </div>
          <button onClick={() => setShowImport(true)} className="px-4 py-2 text-sm font-semibold rounded-lg bg-[#1D1D1F] text-white hover:bg-[#2D2D2F] transition-colors">
            + 导入 Skill
          </button>
        </div>

        {/* 状态过滤 */}
        <div className="flex items-center gap-1 mb-4">
          {STATUS_TABS.map(tab => (
            <button
              key={tab.key}
              onClick={() => setStatusFilter(tab.key)}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                statusFilter === tab.key
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
        ) : skills.length === 0 ? (
          <div className="text-center py-16 text-sm text-[#86868B]">暂无 Skill，点击上方按钮导入</div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {skills.map(s => (
              <SkillConfigCard
                key={s.id}
                skill={s}
                onEdit={() => handleEdit(s)}
                onDelete={() => handleDelete(s.id)}
                onRefresh={() => handleRefresh(s.id)}
              />
            ))}
          </div>
        )}

        <FileImportModal
          open={showImport}
          onClose={() => setShowImport(false)}
          onImport={handleImport}
        />

        {editing && (
          <SkillEditModal
            skill={editing}
            onClose={() => setEditing(null)}
            onSaved={() => { setEditing(null); loadSkills() }}
          />
        )}
      </div>
    </div>
  )
}
