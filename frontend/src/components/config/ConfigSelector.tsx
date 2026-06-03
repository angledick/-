import { useState, useEffect } from 'react'
import type { SkillItem, ToolItem, OAuthConnection } from '../../api/config'
import { skillsApi, toolsApi, oauthApi } from '../../api/config'

interface Props {
  skillIds: string[]
  toolIds: string[]
  oauthIds: string[]
  onSkillChange: (ids: string[]) => void
  onToolChange: (ids: string[]) => void
  onOAuthChange: (ids: string[]) => void
}

export default function ConfigSelector({ skillIds, toolIds, oauthIds, onSkillChange, onToolChange, onOAuthChange }: Props) {
  const [allSkills, setAllSkills] = useState<SkillItem[]>([])
  const [allTools, setAllTools] = useState<ToolItem[]>([])
  const [allOAuth, setAllOAuth] = useState<OAuthConnection[]>([])

  useEffect(() => {
    skillsApi.list().then(r => setAllSkills(r.skills)).catch(() => {})
    toolsApi.list().then(r => setAllTools(r.tools)).catch(() => {})
    oauthApi.list().then(r => setAllOAuth(r.connections)).catch(() => {})
  }, [])

  return (
    <div className="border-t border-black/6 pt-4">
      <h3 className="text-sm font-semibold text-[#1D1D1F] mb-3">关联配置</h3>
      <div className="grid grid-cols-3 gap-4">
        {/* Skills */}
        <div>
          <label className="text-xs font-semibold text-[#86868B] block mb-1.5">
            Skills ({skillIds.length})
          </label>
          <div className="max-h-40 overflow-y-auto border border-black/10 rounded-lg p-1.5 space-y-0.5">
            {allSkills.length === 0 && (
              <div className="text-xs text-[#C7C7CC] p-2">暂无数据</div>
            )}
            {allSkills.map(s => (
              <label key={s.id} className="flex items-center gap-1.5 px-2 py-1 rounded hover:bg-[#F5F5F7] cursor-pointer text-sm">
                <input
                  type="checkbox"
                  checked={skillIds.includes(s.id)}
                  onChange={() =>
                    onSkillChange(
                      skillIds.includes(s.id) ? skillIds.filter(x => x !== s.id) : [...skillIds, s.id]
                    )
                  }
                  className="w-3.5 h-3.5"
                />
                <span className="truncate">{s.name}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Tools */}
        <div>
          <label className="text-xs font-semibold text-[#86868B] block mb-1.5">
            Tools ({toolIds.length})
          </label>
          <div className="max-h-40 overflow-y-auto border border-black/10 rounded-lg p-1.5 space-y-0.5">
            {allTools.length === 0 && (
              <div className="text-xs text-[#C7C7CC] p-2">暂无数据</div>
            )}
            {allTools.map(t => (
              <label key={t.id} className="flex items-center gap-1.5 px-2 py-1 rounded hover:bg-[#F5F5F7] cursor-pointer text-sm">
                <input
                  type="checkbox"
                  checked={toolIds.includes(t.id)}
                  onChange={() =>
                    onToolChange(
                      toolIds.includes(t.id) ? toolIds.filter(x => x !== t.id) : [...toolIds, t.id]
                    )
                  }
                  className="w-3.5 h-3.5"
                />
                <span className="truncate">{t.name}</span>
              </label>
            ))}
          </div>
        </div>

        {/* OAuth */}
        <div>
          <label className="text-xs font-semibold text-[#86868B] block mb-1.5">
            OAuth ({oauthIds.length})
          </label>
          <div className="max-h-40 overflow-y-auto border border-black/10 rounded-lg p-1.5 space-y-0.5">
            {allOAuth.length === 0 && (
              <div className="text-xs text-[#C7C7CC] p-2">暂无数据</div>
            )}
            {allOAuth.map(o => (
              <label key={o.id} className="flex items-center gap-1.5 px-2 py-1 rounded hover:bg-[#F5F5F7] cursor-pointer text-sm">
                <input
                  type="checkbox"
                  checked={oauthIds.includes(o.id)}
                  onChange={() =>
                    onOAuthChange(
                      oauthIds.includes(o.id) ? oauthIds.filter(x => x !== o.id) : [...oauthIds, o.id]
                    )
                  }
                  className="w-3.5 h-3.5"
                />
                <span className="truncate">{o.label || o.provider}</span>
              </label>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
