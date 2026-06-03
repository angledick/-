import { useState } from 'react'

interface Props {
  content: string
  depth?: number
}

export default function ThinkingBlock({ content, depth }: Props) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="my-2 rounded-lg border border-black/8 bg-[#F9F9FB] overflow-hidden animate-[fade-in_0.2s_ease]">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-black/2 transition-colors"
      >
        <span className="text-sm">💭</span>
        <span className="text-sm text-[#86868B] flex-1">思考过程</span>
        {depth !== undefined && (
          <span className="text-[10px] text-[#C7C7CC]">depth: {depth}</span>
        )}
        <span className="text-xs text-[#86868B]">{expanded ? '▲ 折叠' : '▼ 展开'}</span>
      </button>

      {expanded && (
        <div className="px-3 pb-3 border-t border-black/6">
          <div className="text-sm text-[#4A4A4D] leading-relaxed whitespace-pre-wrap mt-2">
            {content}
          </div>
        </div>
      )}
    </div>
  )
}
