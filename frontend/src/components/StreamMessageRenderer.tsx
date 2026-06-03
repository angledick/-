import type { StreamEvent, ChatAssistantMessage } from '../types'
import SkillEventBlock from './SkillEventBlock'
import ThinkingBlock from './ThinkingBlock'
import PlanBlock from './PlanBlock'
import ActionSuggestionCard from './ActionSuggestionCard'
import type { Action } from '../types'

interface Props {
  message: ChatAssistantMessage
  onAction?: (action: Action, decision: 'confirm' | 'skip') => void
}

/**
 * 将 SSE 事件流聚合为有序的 UI 块进行渲染。
 *
 * 聚合逻辑：
 * - 连续的 token 事件合并为一个文本段落
 * - skill_start 后紧跟同名 skill_end 合并为一个 SkillEventBlock
 * - thinking/plan/action_card 独立渲染
 * - error 事件渲染为错误提示
 */
export default function StreamMessageRenderer({ message, onAction }: Props) {
  const { events, textContent, isStreaming } = message

  // 将事件聚合为渲染块
  const blocks = aggregateBlocks(events)

  return (
    <div className="space-y-1">
      {blocks.map((block, i) => (
        <BlockRenderer key={i} block={block} onAction={onAction} />
      ))}

      {/* 流式光标 */}
      {isStreaming && (
        <span className="streaming-cursor inline-block" />
      )}

      {/* 空消息 + 正在加载 */}
      {events.length === 0 && isStreaming && (
        <div className="flex items-center gap-2 py-2">
          <div className="w-2 h-2 rounded-full bg-[#1D1D1F] animate-[pulse-dot_1.2s_infinite]" />
          <span className="text-sm text-[#86868B]">思考中...</span>
        </div>
      )}

      {/* 如果有纯文本内容且不在任何特殊块中 */}
      {textContent && !blocks.some(b => b.kind === 'tokens') && (
        <div className="text-sm leading-relaxed whitespace-pre-wrap">{textContent}</div>
      )}
    </div>
  )
}

// ── 块聚合 ───────────────────────────────────────────────────────────────────

type RenderBlock =
  | { kind: 'tokens'; text: string }
  | { kind: 'skill'; skill: string; start?: Extract<StreamEvent, { type: 'skill_start' }>; end?: Extract<StreamEvent, { type: 'skill_end' }>; status: 'running' | 'done' | 'error' }
  | { kind: 'thinking'; content: string; depth?: number }
  | { kind: 'plan'; steps: Extract<StreamEvent, { type: 'plan' }>['steps']; current: number }
  | { kind: 'action_card'; actions: Action[] }
  | { kind: 'error'; code: string; message: string; recoverable?: boolean }

function aggregateBlocks(events: StreamEvent[]): RenderBlock[] {
  const blocks: RenderBlock[] = []
  let tokenBuffer = ''

  const flushTokens = () => {
    if (tokenBuffer) {
      blocks.push({ kind: 'tokens', text: tokenBuffer })
      tokenBuffer = ''
    }
  }

  // 跟踪 skill 块
  const skillMap = new Map<string, number>() // skill name -> block index

  for (const event of events) {
    switch (event.type) {
      case 'token':
        tokenBuffer += event.content
        break

      case 'skill_start': {
        flushTokens()
        const idx = blocks.length
        skillMap.set(event.skill, idx)
        blocks.push({
          kind: 'skill',
          skill: event.skill,
          start: event,
          status: 'running',
        })
        break
      }

      case 'skill_end': {
        flushTokens()
        const idx = skillMap.get(event.skill)
        if (idx !== undefined) {
          const block = blocks[idx]
          if (block.kind === 'skill') {
            block.end = event
            block.status = event.status === 'error' ? 'error' : 'done'
          }
        } else {
          blocks.push({
            kind: 'skill',
            skill: event.skill,
            end: event,
            status: event.status === 'error' ? 'error' : 'done',
          })
        }
        break
      }

      case 'thinking':
        flushTokens()
        blocks.push({ kind: 'thinking', content: event.content, depth: event.depth })
        break

      case 'plan':
        flushTokens()
        blocks.push({ kind: 'plan', steps: event.steps, current: event.current })
        break

      case 'action_card':
        flushTokens()
        blocks.push({ kind: 'action_card', actions: event.actions })
        break

      case 'error':
        flushTokens()
        blocks.push({ kind: 'error', code: event.code, message: event.message, recoverable: event.recoverable })
        break

      case 'done':
        flushTokens()
        break
    }
  }

  flushTokens()
  return blocks
}

// ── 块渲染器 ─────────────────────────────────────────────────────────────────

function BlockRenderer({
  block,
  onAction,
}: {
  block: RenderBlock
  onAction?: (action: Action, decision: 'confirm' | 'skip') => void
}) {
  switch (block.kind) {
    case 'tokens':
      return (
        <div className="text-sm leading-relaxed whitespace-pre-wrap text-[#1D1D1F]">
          {block.text}
        </div>
      )

    case 'skill':
      return (
        <SkillEventBlock
          skill={block.skill}
          startEvent={block.start}
          endEvent={block.end}
          status={block.status}
        />
      )

    case 'thinking':
      return <ThinkingBlock content={block.content} depth={block.depth} />

    case 'plan':
      return <PlanBlock steps={block.steps} current={block.current} />

    case 'action_card':
      return <ActionSuggestionCard actions={block.actions} onAction={onAction} />

    case 'error':
      return (
        <div className="my-2 rounded-lg border border-[#FF3B30]/20 bg-[#FF3B30]/5 p-3">
          <div className="flex items-center gap-2">
            <span className="text-sm">❌</span>
            <span className="text-sm font-medium text-[#FF3B30]">
              {block.message}
            </span>
          </div>
          {block.code && (
            <div className="text-[11px] text-[#86868B] mt-1">错误码: {block.code}</div>
          )}
        </div>
      )
  }
}
