import { useState } from 'react'

interface Props {
  open: boolean
  onClose: () => void
  onImport: (source: { type: 'github' | 'zip' | 'manual'; value: string }) => void
}

export default function FileImportModal({ open, onClose, onImport }: Props) {
  const [tab, setTab] = useState<'github' | 'zip' | 'manual'>('github')
  const [githubUrl, setGithubUrl] = useState('')
  const [manualContent, setManualContent] = useState('')
  const [zipFile, setZipFile] = useState<File | null>(null)

  if (!open) return null

  const handleSubmit = () => {
    if (tab === 'github' && githubUrl.trim()) {
      onImport({ type: 'github', value: githubUrl.trim() })
      setGithubUrl('')
      onClose()
    } else if (tab === 'zip' && zipFile) {
      onImport({ type: 'zip', value: zipFile.name })
      setZipFile(null)
      onClose()
    } else if (tab === 'manual' && manualContent.trim()) {
      onImport({ type: 'manual', value: manualContent.trim() })
      setManualContent('')
      onClose()
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl w-[480px] max-h-[80vh] overflow-hidden shadow-2xl" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="px-5 py-4 border-b border-black/6 flex items-center justify-between">
          <h3 className="font-semibold text-base text-[#1D1D1F]">导入 Skill</h3>
          <button onClick={onClose} className="text-sm text-[#86868B] hover:text-[#1D1D1F]">✕</button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-black/6">
          {([['github', 'GitHub 链接'], ['zip', 'ZIP 上传'], ['manual', '手动撰写']] as const).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex-1 px-4 py-2.5 text-sm transition-colors ${
                tab === key ? 'font-semibold text-[#1D1D1F] border-b-2 border-[#1D1D1F]' : 'text-[#86868B] hover:text-[#1D1D1F]'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="p-5">
          {tab === 'github' && (
            <div>
              <label className="block text-sm font-medium text-[#1D1D1F] mb-1.5">GitHub 仓库链接</label>
              <input
                type="url"
                value={githubUrl}
                onChange={e => setGithubUrl(e.target.value)}
                placeholder="https://github.com/org/skill-name"
                className="w-full px-3 py-2 rounded-lg border border-black/10 bg-[#F5F5F7] text-sm outline-none focus:border-[#0071E3]/30"
              />
              <p className="text-[11px] text-[#86868B] mt-1.5">SDK 将自动检测 skill.yaml 并生成配置</p>
            </div>
          )}

          {tab === 'zip' && (
            <div>
              <label className="block text-sm font-medium text-[#1D1D1F] mb-1.5">上传 ZIP 文件</label>
              <div className="border-2 border-dashed border-black/10 rounded-lg p-8 text-center relative">
                <div className="text-3xl mb-2">📦</div>
                {zipFile ? (
                  <div className="text-sm text-[#1D1D1F]">{zipFile.name}</div>
                ) : (
                  <>
                    <div className="text-sm text-[#86868B]">拖拽 ZIP 文件到此处</div>
                    <div className="text-xs text-[#C7C7CC] mt-1">或点击选择文件</div>
                  </>
                )}
                <input
                  type="file"
                  accept=".zip"
                  onChange={e => setZipFile(e.target.files?.[0] || null)}
                  className="absolute inset-0 opacity-0 cursor-pointer"
                />
              </div>
            </div>
          )}

          {tab === 'manual' && (
            <div>
              <label className="block text-sm font-medium text-[#1D1D1F] mb-1.5">Skill 配置 (Markdown + YAML Frontmatter)</label>
              <textarea
                value={manualContent}
                onChange={e => setManualContent(e.target.value)}
                placeholder={"---\nname: my-skill\ndescription: ...\n---\n\n# My Skill\n..."}
                rows={10}
                className="w-full px-3 py-2 rounded-lg border border-black/10 bg-[#F5F5F7] text-sm outline-none font-mono resize-none focus:border-[#0071E3]/30"
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-black/6 flex items-center justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg bg-[#F5F5F7] text-[#86868B] hover:bg-[#E5E5EA] transition-colors">
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={tab === 'zip' ? !zipFile : (tab === 'github' ? !githubUrl.trim() : !manualContent.trim())}
            className="px-4 py-2 text-sm font-semibold rounded-lg bg-[#1D1D1F] text-white hover:bg-[#2D2D2F] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            导入
          </button>
        </div>
      </div>
    </div>
  )
}
