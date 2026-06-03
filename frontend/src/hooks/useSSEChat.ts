import { useCallback, useRef, useState } from 'react'
import type {
  StreamEvent,
  ChatMessage,
  ChatUserMessage,
  ChatAssistantMessage,
  ConnectionStatus,
} from '../types'

// ── 常量 ─────────────────────────────────────────────────────────────────────

const API_BASE = '/api/v1'
const IDLE_TIMEOUT_MS = 60_000

// ── SSE 解析工具 ─────────────────────────────────────────────────────────────

function parseSSEChunk(chunk: string): { event?: string; data?: string }[] {
  const events: { event?: string; data?: string }[] = []
  // 按双换行分割（SSE 事件之间以 \n\n 分隔）
  const blocks = chunk.split('\n\n').filter(Boolean)
  for (const block of blocks) {
    let eventType: string | undefined
    let dataStr: string | undefined
    for (const line of block.split('\n')) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        dataStr = line.slice(6)
      }
    }
    if (eventType && dataStr) {
      events.push({ event: eventType, data: dataStr })
    }
  }
  return events
}

function parseStreamEvent(eventType: string, dataStr: string): StreamEvent | null {
  try {
    const data = JSON.parse(dataStr)
    return { type: eventType, ...data } as StreamEvent
  } catch {
    return null
  }
}

/** 从事件数组中提取纯文本 token 内容 */
function extractTextContent(events: StreamEvent[]): string {
  return events
    .filter((e): e is Extract<StreamEvent, { type: 'token' }> => e.type === 'token')
    .map(e => e.content)
    .join('')
}

// ── Hook ─────────────────────────────────────────────────────────────────────

interface UseSSEChatOptions {
  /** 可选的 Agent ID */
  agentId?: string
  /** 可选的 Skill ID 列表 */
  skillIds?: string[]
  /** 可选的 Session ID */
  sessionId?: string
  /** 自定义 SSE 端点（默认 /api/v1/chat/stream） */
  endpoint?: string
  /** 自定义 Authorization token */
  token?: string | null
}

interface UseSSEChatReturn {
  /** 对话消息列表（用户+AI交替） */
  messages: ChatMessage[]
  /** SSE 连接状态 */
  status: ConnectionStatus
  /** 是否正在流式输出 */
  isStreaming: boolean
  /** 发送消息 */
  send: (text: string) => void
  /** 中断当前生成 */
  abort: () => void
  /** 清空消息 */
  clear: () => void
}

export function useSSEChat(options: UseSSEChatOptions = {}): UseSSEChatReturn {
  const { agentId, skillIds, sessionId, endpoint, token } = options

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [status, setStatus] = useState<ConnectionStatus>('idle')
  const [isStreaming, setIsStreaming] = useState(false)

  const abortRef = useRef<AbortController | null>(null)
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const resetIdleTimer = useCallback(() => {
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current)
    idleTimerRef.current = setTimeout(() => {
      setStatus(prev => (prev === 'connected' ? 'idle' : prev))
    }, IDLE_TIMEOUT_MS)
  }, [])

  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || isStreaming) return

      // 用户消息
      const userMsg: ChatUserMessage = {
        kind: 'user',
        id: `u_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
        content: text.trim(),
        timestamp: Date.now(),
      }

      // AI 消息占位
      const assistantMsg: ChatAssistantMessage = {
        kind: 'assistant',
        id: `a_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
        events: [],
        textContent: '',
        isStreaming: true,
        timestamp: Date.now(),
      }

      setMessages(prev => [...prev, userMsg, assistantMsg])
      setIsStreaming(true)
      setStatus('connecting')

      // 中断上一个请求（如果有）
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      try {
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        }
        if (token) headers['Authorization'] = `Bearer ${token}`

        const body = JSON.stringify({
          message: text.trim(),
          agent_id: agentId ?? undefined,
          skill_ids: skillIds ?? undefined,
          session_id: sessionId ?? undefined,
        })

        const res = await fetch(endpoint ?? `${API_BASE}/chat/stream`, {
          method: 'POST',
          headers,
          body,
          signal: controller.signal,
        })

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: ${res.statusText}`)
        }

        setStatus('connected')
        resetIdleTimer()

        const reader = res.body?.getReader()
        if (!reader) throw new Error('No response body')

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const parsed = parseSSEChunk(buffer)
          // 保留未完成的块（不以 \n\n 结尾的部分）
          const lastDoubleNewline = buffer.lastIndexOf('\n\n')
          buffer = lastDoubleNewline >= 0 ? buffer.slice(lastDoubleNewline + 2) : buffer

          for (const { event, data } of parsed) {
            if (!event || !data) continue
            const streamEvent = parseStreamEvent(event, data)
            if (!streamEvent) continue

            resetIdleTimer()

            setMessages(prev =>
              prev.map(m => {
                if (m.kind !== 'assistant' || m.id !== assistantMsg.id) return m
                const updated: ChatAssistantMessage = {
                  ...m,
                  events: [...m.events, streamEvent],
                  textContent: extractTextContent([...m.events, streamEvent]),
                  isStreaming: streamEvent.type !== 'done' && streamEvent.type !== 'error',
                }
                return updated
              })
            )

            // done 或 不可恢复错误时停止
            if (streamEvent.type === 'done') {
              setIsStreaming(false)
              setStatus('idle')
              return
            }
            if (streamEvent.type === 'error' && !streamEvent.recoverable) {
              setIsStreaming(false)
              setStatus('error')
              return
            }
          }
        }

        // 流正常结束但没有 done 事件
        setIsStreaming(false)
        setStatus('idle')
        setMessages(prev =>
          prev.map(m =>
            m.kind === 'assistant' && m.id === assistantMsg.id
              ? { ...m, isStreaming: false }
              : m
          )
        )
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          // 用户主动中断
          setIsStreaming(false)
          setStatus('idle')
          setMessages(prev =>
            prev.map(m =>
              m.kind === 'assistant' && m.id === assistantMsg.id
                ? { ...m, isStreaming: false }
                : m
            )
          )
          return
        }

        // 网络错误
        const errMsg = err instanceof Error ? err.message : '未知错误'
        const errorEvent: StreamEvent = {
          type: 'error',
          code: 'connection_error',
          message: `连接失败: ${errMsg}。请确认后端已启动 (http://localhost:8000)`,
          recoverable: false,
        }

        setMessages(prev =>
          prev.map(m =>
            m.kind === 'assistant' && m.id === assistantMsg.id
              ? {
                  ...m,
                  events: [...m.events, errorEvent],
                  isStreaming: false,
                }
              : m
          )
        )
        setIsStreaming(false)
        setStatus('error')
      }
    },
    [agentId, skillIds, sessionId, endpoint, token, isStreaming, resetIdleTimer]
  )

  const abort = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
  }, [])

  const clear = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setMessages([])
    setIsStreaming(false)
    setStatus('idle')
  }, [])

  return { messages, status, isStreaming, send, abort, clear }
}
