import { useState, useEffect, useRef, useCallback } from 'react'
import { useSSEChat } from '../hooks/useSSEChat'
import { useAgentConfigStore } from '../context/AppStore'
import StreamMessageRenderer from './StreamMessageRenderer'
import ChatInput from './ChatInput'
import CLICommandResult from './CLICommandResult'
import { cliApi, type CLIExecuteResponse } from '../api/config'
import type { ConnectionStatus, Action } from '../types'

interface Props {
  /** 可选的初始消息（自动发送一次） */
  initialMessage?: string | null
  /** 初始消息消费回调 */
  onInitialMessageConsumed?: () => void
  /** 自定义端点 */
  endpoint?: string
  /** 自定义 session ID */
  sessionId?: string
  /** 标题（显示在 header） */
  title?: string
  /** 副标题 */
  subtitle?: string
  /** 空状态提示 */
  placeholder?: string
  /** 操作建议回调 */
  onAction?: (action: Action, decision: 'confirm' | 'skip') => void
}

const statusLabels: Record<ConnectionStatus, { label: string; color: string }> = {
  idle: { label: '就绪', color: 'text-[#86868B]' },
  connecting: { label: '连接中...', color: 'text-[#FF9500]' },
  connected: { label: '已连接', color: 'text-[#34C759]' },
  reconnecting: { label: '重连中...', color: 'text-[#FF9500]' },
  disconnected: { label: '已断开', color: 'text-[#FF3B30]' },
  error: { label: '连接错误', color: 'text-[#FF3B30]' },
}

export default function StreamChat({
  initialMessage,
  onInitialMessageConsumed,
  endpoint,
  sessionId,
  title = '避风港 跨境合规智能体',
  subtitle,
  placeholder,
  onAction,
}: Props) {
  const agentId = useAgentConfigStore(s => s.agent_id)
  const skillIds = useAgentConfigStore(s => s.skills)

  const { messages, status, isStreaming, send, abort, clear } = useSSEChat({
    agentId: agentId ?? undefined,
    skillIds: skillIds?.length ? skillIds : undefined,
    sessionId,
    endpoint,
  })

  const [cliResults, setCliResults] = useState<CLIExecuteResponse[]>([])

  const bottomRef = useRef<HTMLDivElement>(null)
  const initialSent = useRef(false)

  // 自动滚动到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, cliResults])

  // 发送初始消息
  useEffect(() => {
    if (initialMessage && !initialSent.current) {
      initialSent.current = true
      send(initialMessage)
      onInitialMessageConsumed?.()
    }
  }, [initialMessage, send, onInitialMessageConsumed])

  // CLI 命令执行
  const handleCLI = useCallback(async (command: string) => {
    // /clear 命令：无论 API 是否可用都清空本地对话
    if (command === '/clear') {
      clear()
    }
    try {
      const result = await cliApi.execute(command)
      setCliResults(prev => [...prev, result])
    } catch {
      // CLI API 不可用时的本地回退处理
      if (command === '/help') {
        setCliResults(prev => [...prev, {
          success: true,
          command,
          output: '可用命令:\n  /help    查看帮助\n  /clear   清空对话\n  /status  查看系统状态\n  /config  查看当前配置',
        }])
      } else if (command === '/status') {
        setCliResults(prev => [...prev, {
          success: true,
          command,
          output: '系统状态: 运行中\nSSE连接: ' + status,
        }])
      } else if (command.startsWith('/config')) {
        setCliResults(prev => [...prev, {
          success: true,
          command,
          output: `当前配置:\n  Agent: ${agentId || '默认'}\n  Skills: ${skillIds?.join(', ') || '无'}`,
        }])
      } else if (command !== '/clear') {
        setCliResults(prev => [...prev, {
          success: false,
          command,
          error: `未知命令: ${command}\n输入 /help 查看可用命令`,
        }])
      }
    }
  }, [status, agentId, skillIds, clear])

  const statusInfo = statusLabels[status]

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header */}
      <header className="px-5 py-4 border-b border-black/6 flex items-center gap-3 shrink-0">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#1D1D1F] to-[#424245] flex items-center justify-center text-white text-sm font-bold">
          A
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-[15px] text-[#1D1D1F]">{title}</div>
          <div className={`text-xs ${statusInfo.color}`}>
            ● {subtitle || statusInfo.label}
          </div>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clear}
            className="text-xs text-[#86868B] hover:text-[#1D1D1F] px-2 py-1 rounded hover:bg-[#F5F5F7] transition-colors"
          >
            清空对话
          </button>
        )}
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-5 bg-[#FAFAFA]">
        {messages.length === 0 && cliResults.length === 0 && (
          <div className="text-center mt-20 text-[#86868B]">
            <div className="text-5xl mb-3">🌍</div>
            <div className="text-base font-semibold text-[#1D1D1F] mb-1.5">
              {placeholder ? '开始对话' : '跨境合规，一问便知'}
            </div>
            <div className="text-[13px]">
              {placeholder || '试试：LED灯出口德国需要注意什么'}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div
            key={msg.id}
            className={`mb-5 flex flex-col ${msg.kind === 'user' ? 'items-end' : 'items-start'}`}
          >
            {/* Sender label */}
            <span className="text-xs text-[#86868B] mb-1 font-medium">
              {msg.kind === 'user' ? '你' : '避风港 · 合规智能体'}
            </span>

            {msg.kind === 'user' ? (
              <div className="max-w-[80%] px-4 py-3 rounded-2xl rounded-br bg-[#1D1D1F] text-white text-[15px] leading-relaxed whitespace-pre-wrap">
                {msg.content}
              </div>
            ) : (
              <div className="max-w-[85%] px-4 py-3 rounded-2xl rounded-bl bg-[#F5F5F7] text-[#1D1D1F]">
                <StreamMessageRenderer message={msg} onAction={onAction} />
              </div>
            )}
          </div>
        ))}

        {/* CLI 执行结果 */}
        {cliResults.map((r, i) => (
          <div key={`cli-${i}`} className="mb-3 max-w-[85%]">
            <span className="text-xs text-[#86868B] mb-1 font-medium block">
              CLI 命令
            </span>
            <CLICommandResult
              result={r}
              onRerun={() => handleCLI(r.command)}
              onCopy={() => navigator.clipboard.writeText(r.output || r.error || '')}
            />
          </div>
        ))}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="shrink-0 border-t border-black/6 px-4 py-3">
        <ChatInput
          onSend={send}
          onCLI={handleCLI}
          disabled={isStreaming}
          onAbort={abort}
          isStreaming={isStreaming}
        />
      </div>
    </div>
  )
}
