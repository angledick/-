import { useState } from 'react'
import type { StreamEventSkillStart, StreamEventSkillEnd } from '../types'

interface Props {
  skill: string
  startEvent?: StreamEventSkillStart
  endEvent?: StreamEventSkillEnd
  status: 'running' | 'done' | 'error'
}

export default function SkillEventBlock({ skill, startEvent, endEvent, status }: Props) {
  const [expanded, setExpanded] = useState(false)

  const statusIcon = status === 'running' ? '🔄' : status === 'done' ? '✅' : '❌'
  const statusText = status === 'running' ? '执行中...' : status === 'done' ? '完成' : '失败'
  const duration = endEvent?.duration_ms ? `${(endEvent.duration_ms / 1000).toFixed(1)}s` : null

  return (
    <div className="my-2 rounded-lg border border-black/8 bg-white overflow-hidden animate-[fade-in_0.2s_ease]">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-black/2 transition-colors"
      >
        <span className="text-sm">🔧</span>
        <span className="font-semibold text-sm text-[#1D1D1F] flex-1">{skill}</span>
        {duration && <span className="text-xs text-[#86868B]">{duration}</span>}
        <span className="text-xs">{statusIcon} {statusText}</span>
        <span className="text-xs text-[#86868B]">{expanded ? '▲' : '▼'}</span>
      </button>

      {/* Details */}
      {expanded && (
        <div className="px-3 pb-3 border-t border-black/6">
          {/* 入参 */}
          {startEvent?.args && Object.keys(startEvent.args).length > 0 && (
            <div className="mt-2">
              <div className="text-[11px] font-semibold text-[#86868B] mb-1">入参</div>
              <pre className="text-xs bg-[#F5F5F7] rounded p-2 overflow-x-auto font-mono text-[#1D1D1F]">
                {JSON.stringify(startEvent.args, null, 2)}
              </pre>
            </div>
          )}
          {/* 结果 */}
          {endEvent?.result && (
            <div className="mt-2">
              <div className="text-[11px] font-semibold text-[#86868B] mb-1">结果</div>
              {endEvent.result.summary ? (
                <div className="text-xs text-[#1D1D1F]">{String(endEvent.result.summary)}</div>
              ) : (
                <pre className="text-xs bg-[#F5F5F7] rounded p-2 overflow-x-auto font-mono text-[#1D1D1F]">
                  {JSON.stringify(endEvent.result, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>
      )}

      {/* Running indicator */}
      {status === 'running' && (
        <div className="h-0.5 bg-[#F5F5F7]">
          <div className="h-full bg-[#0071E3] animate-pulse w-2/3 rounded-full" />
        </div>
      )}
    </div>
  )
}
