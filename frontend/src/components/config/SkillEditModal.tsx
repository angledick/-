import { useState, useEffect } from 'react'
import type { SkillItem } from '../../api/config'
import { skillsApi } from '../../api/config'

interface Props {
  skill: SkillItem | null  // null = 新建模式
  onClose: () => void
  onSaved: () => void
}

export default function SkillEditModal({ skill, onClose, onSaved }: Props) {
  const isNew = !skill

  const [name, setName] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [enabled, setEnabled] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (skill) {
      setName(skill.name)
      setEnabled(skill.enabled)
    }
  }, [skill])

  const handleSave = async () => {
    if (isNew) {
      if (!name.trim()) { setError('请输入名称'); return }
      setSaving(true)
      setError('')
      try {
        await skillsApi.install({
          name: name.trim(),
          source: 'manual',
          source_url: sourceUrl.trim() || undefined,
        })
        onSaved()
      } catch (e) {
        setError(e instanceof Error ? e.message : '安装失败')
      } finally {
        setSaving(false)
      }
    } else {
      setSaving(true)
      setError('')
      try {
        await skillsApi.update(skill!.id, { config: { enabled } })
        onSaved()
      } catch (e) {
        setError(e instanceof Error ? e.message : '保存失败')
      } finally {
        setSaving(false)
      }
    }
  }

  const handleDelete = async () => {
    if (!skill || !window.confirm(`确定卸载 Skill「${skill.name}」？`)) return
    setSaving(true)
    try {
      await skillsApi.delete(skill.id)
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败')
    } finally {
      setSaving(false)
    }
  }

  const handleRefresh = async () => {
    if (!skill) return
    setSaving(true)
    try {
      await skillsApi.refresh(skill.id)
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : '刷新失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="w-[480px] max-h-[85vh] bg-white rounded-2xl shadow-xl overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-black/6 px-6 py-4 flex items-center justify-between z-10">
          <h2 className="text-lg font-semibold text-[#1D1D1F]">
            {isNew ? '安装 Skill' : `Skill: ${skill?.name}`}
          </h2>
          <button onClick={onClose} className="text-sm text-[#86868B] hover:text-[#1D1D1F]">✕</button>
        </div>

        <div className="p-6 space-y-5">
          {error && (
            <div className="p-3 rounded-lg bg-[#FF3B30]/5 border border-[#FF3B30]/20 text-sm text-[#FF3B30]">{error}</div>
          )}

          {isNew ? (
            <>
              <div>
                <label className="text-xs font-semibold text-[#86868B] block mb-1.5">名称</label>
                <input
                  value={name}
                  onChange={e => setName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30"
                  placeholder="Skill 名称"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-[#86868B] block mb-1.5">来源 URL</label>
                <input
                  value={sourceUrl}
                  onChange={e => setSourceUrl(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30"
                  placeholder="https://github.com/org/skill-name"
                />
              </div>
            </>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-semibold text-[#86868B] block mb-1.5">名称</label>
                  <div className="text-sm text-[#1D1D1F] px-3 py-2 bg-[#F5F5F7] rounded-lg">{skill.name}</div>
                </div>
                <div>
                  <label className="text-xs font-semibold text-[#86868B] block mb-1.5">版本</label>
                  <div className="text-sm text-[#1D1D1F] px-3 py-2 bg-[#F5F5F7] rounded-lg">{skill.version || '-'}</div>
                </div>
              </div>

              {skill.description && (
                <div>
                  <label className="text-xs font-semibold text-[#86868B] block mb-1.5">描述</label>
                  <div className="text-sm text-[#1D1D1F] px-3 py-2 bg-[#F5F5F7] rounded-lg">{skill.description}</div>
                </div>
              )}

              <div>
                <label className="text-xs font-semibold text-[#86868B] block mb-1.5">来源</label>
                <div className="text-sm text-[#1D1D1F] px-3 py-2 bg-[#F5F5F7] rounded-lg">{skill.source}</div>
              </div>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={e => setEnabled(e.target.checked)}
                  className="w-4 h-4"
                />
                <span className="text-sm text-[#1D1D1F]">启用</span>
              </label>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-white border-t border-black/6 px-6 py-4 flex items-center justify-between">
          <div className="flex gap-2">
            {!isNew && (
              <>
                <button
                  onClick={handleRefresh}
                  disabled={saving}
                  className="px-3 py-2 text-sm font-medium rounded-lg bg-[#F5F5F7] text-[#86868B] hover:bg-[#E5E5EA] transition-colors disabled:opacity-40"
                >
                  刷新
                </button>
                <button
                  onClick={handleDelete}
                  disabled={saving}
                  className="px-3 py-2 text-sm font-medium rounded-lg bg-[#FF3B30]/10 text-[#FF3B30] hover:bg-[#FF3B30]/20 transition-colors disabled:opacity-40"
                >
                  卸载
                </button>
              </>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-[#F5F5F7] text-[#86868B] hover:bg-[#E5E5EA] transition-colors"
            >
              取消
            </button>
            <button
              onClick={handleSave}
              disabled={saving || (isNew && !name.trim())}
              className="px-4 py-2 text-sm font-semibold rounded-lg bg-[#1D1D1F] text-white hover:bg-[#2D2D2F] transition-colors disabled:opacity-40"
            >
              {saving ? '处理中...' : isNew ? '安装' : '保存'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
