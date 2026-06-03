import { useState } from 'react'
import ReactMarkdown from 'react-markdown'

interface Props {
  content: string
  title?: string
  tags?: string[]
  updatedAt?: string
  onClose?: () => void
}

export default function MarkdownViewer({ content, title, tags, updatedAt, onClose }: Props) {
  const [raw, setRaw] = useState(false)

  return (
    <div className="bg-white rounded-xl border border-black/6 overflow-hidden">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-black/6 flex items-center justify-between">
        <div className="flex-1 min-w-0">
          {title && (
            <h2 className="text-sm font-semibold text-[#1D1D1F] truncate">{title}</h2>
          )}
          <div className="flex items-center gap-2 mt-0.5">
            {tags && tags.length > 0 && (
              <div className="flex gap-1 flex-wrap">
                {tags.map(t => (
                  <span
                    key={t}
                    className="text-[10px] px-1.5 py-0.5 rounded bg-[#F5F5F7] text-[#86868B]"
                  >
                    {t}
                  </span>
                ))}
              </div>
            )}
            {updatedAt && (
              <span className="text-[11px] text-[#C7C7CC]">
                {new Date(updatedAt).toLocaleDateString('zh-CN')}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setRaw(!raw)}
            className="text-xs text-[#86868B] px-2 py-1 rounded hover:bg-[#F5F5F7] transition-colors"
          >
            {raw ? '渲染' : '源码'}
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="text-xs text-[#86868B] hover:text-[#1D1D1F] transition-colors"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="px-5 py-4 max-w-none text-sm leading-relaxed text-[#1D1D1F] prose prose-sm prose-headings:text-[#1D1D1F] prose-a:text-[#0071E3]">
        {raw ? (
          <pre className="text-xs text-[#424245] whitespace-pre-wrap font-mono bg-[#F5F5F7] p-4 rounded-lg overflow-x-auto">
            {content}
          </pre>
        ) : (
          <ReactMarkdown>{content}</ReactMarkdown>
        )}
      </div>
    </div>
  )
}
