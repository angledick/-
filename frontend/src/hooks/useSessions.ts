import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { Session, SessionMessage, SessionSummary, StreamEvent } from '@/types'
import { useAuth } from '@/context/AuthContext'
import {
  useDeleteSessionMutation,
  useSendMessageMutation,
  useSessionQuery,
  useSessionsQuery,
} from './queries/useSessions'
import { createMockStream } from '@/lib/mockStream'

const USE_MOCK_STREAM = import.meta.env.VITE_STREAM_MODE === 'mock'
const nowSec = () => Math.floor(Date.now() / 1000)
const isLocalSessionId = (id?: string | null) =>
  !id || id.startsWith('local_') || id.startsWith('mock_')

function parseSseEvent(rawEvent: string): StreamEvent | null {
  let eventType = ''
  const dataLines: string[] = []

  for (const line of rawEvent.split(/\r?\n/)) {
    if (line.startsWith('event:')) {
      eventType = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart())
    }
  }

  if (dataLines.length === 0) return null

  const payload = JSON.parse(dataLines.join('\n')) as Record<string, unknown>
  if (eventType && typeof payload.type !== 'string') {
    payload.type = eventType
  }
  return payload as StreamEvent
}

async function* readSseEvents(response: Response): AsyncGenerator<StreamEvent> {
  if (!response.body) throw new Error('流式响应为空')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const rawEvent = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      const event = parseSseEvent(rawEvent)
      if (event) yield event
      boundary = buffer.indexOf('\n\n')
    }
  }

  const event = parseSseEvent(buffer)
  if (event) yield event
}

type SessionsContextValue = {
  sessions: SessionSummary[]
  currentSession: Session | null
  loading: boolean
  sending: boolean
  loadSessions: () => Promise<void>
  openSession: (id: string) => Promise<void>
  newSession: () => void
  deleteSession: (id: string) => Promise<void>
  sendMessage: (text: string) => Promise<SessionMessage | null>
}

const SessionsContext = createContext<SessionsContextValue | null>(null)

function toSummary(session: Session): SessionSummary {
  const normalized = normalizeSession(session)
  return {
    id: normalized.id,
    title: normalized.title,
    created_at: normalized.created_at,
    updated_at: normalized.updated_at,
    message_count: normalized.message_count,
    preview: normalized.preview,
  }
}

function normalizeSession(session: Session): Session {
  const messages = session.messages ?? []
  const lastMessage = messages[messages.length - 1]
  return {
    ...session,
    message_count: session.message_count ?? messages.length,
    preview: session.preview ?? lastMessage?.content?.slice(0, 60) ?? '',
    messages,
  }
}

function sortSessions(items: Session[]) {
  return [...items].sort((a, b) => b.updated_at - a.updated_at)
}

function useSessionsController(): SessionsContextValue {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [currentSession, setCurrentSession] = useState<Session | null>(null)
  const [mockSessions, setMockSessions] = useState<Session[]>([])
  const [sending, setSending] = useState(false)
  const pendingSessionId = useRef<string | null>(null)

  const { data: serverSessions = [], isLoading: loadingList } = useSessionsQuery()
  const { isLoading: loadingSession } = useSessionQuery(currentSessionId)
  const deleteSessionMutation = useDeleteSessionMutation()
  const sendMessageMutation = useSendMessageMutation()

  const sessions = useMemo(
    () => (USE_MOCK_STREAM ? mockSessions.map(toSummary) : serverSessions),
    [mockSessions, serverSessions],
  )
  const loading = !currentSession && (loadingList || loadingSession)

  const upsertServerSessionCache = useCallback(
    (session: Session) => {
      if (USE_MOCK_STREAM || isLocalSessionId(session.id)) return
      const normalized = normalizeSession(session)
      queryClient.setQueryData(['session', normalized.id], normalized)
      queryClient.setQueryData<SessionSummary[]>(['sessions'], (prev = []) => {
        const summary = toSummary(normalized)
        return [summary, ...prev.filter((item) => item.id !== summary.id)]
          .sort((a, b) => b.updated_at - a.updated_at)
          .slice(0, 50)
      })
    },
    [queryClient],
  )

  const upsertMockSession = useCallback((session: Session) => {
    if (!USE_MOCK_STREAM) return
    setMockSessions((prev) =>
      sortSessions([session, ...prev.filter((item) => item.id !== session.id)]),
    )
  }, [])

  const updateCurrentMessage = useCallback(
    (messageId: string, updater: (message: SessionMessage) => SessionMessage) => {
      const updatedAt = nowSec()
      const applyUpdate = (session: Session): Session => {
        let changed = false
        const messages = session.messages.map((message) => {
          if (message.id !== messageId) return message
          changed = true
          return updater(message)
        })

        if (!changed) return session

        return {
          ...session,
          messages,
          message_count: messages.length,
          preview: messages[messages.length - 1]?.content.slice(0, 60) || session.preview,
          updated_at: updatedAt,
        }
      }

      setCurrentSession((prev) => (prev ? applyUpdate(prev) : prev))
      if (USE_MOCK_STREAM) {
        setMockSessions((prev) => sortSessions(prev.map((session) => applyUpdate(session))))
      }
    },
    [],
  )

  const loadSessions = useCallback(async () => {
    // Server sessions are handled by TanStack Query; mock sessions live in local state.
  }, [])

  const openSession = useCallback(
    async (id: string) => {
      setCurrentSessionId(id)

      if (USE_MOCK_STREAM) {
        const local = mockSessions.find((session) => session.id === id)
        if (local) {
          setCurrentSession(local)
          pendingSessionId.current = id
        }
        return
      }

      try {
        const headers: Record<string, string> = {}
        if (token) headers.Authorization = `Bearer ${token}`

        const res = await fetch(`/api/v1/sessions/${id}`, { headers })
        if (res.ok) {
          const data: Session = normalizeSession(await res.json())
          setCurrentSession(data)
          pendingSessionId.current = id
          upsertServerSessionCache(data)
        }
      } catch {
        // Keep the current UI state if the history request fails.
      }
    },
    [mockSessions, token],
  )

  const newSession = useCallback(() => {
    setCurrentSession(null)
    setCurrentSessionId(null)
    pendingSessionId.current = null
  }, [])

  const deleteSession = useCallback(
    async (id: string) => {
      if (USE_MOCK_STREAM) {
        setMockSessions((prev) => prev.filter((session) => session.id !== id))
        if (currentSession?.id === id) {
          setCurrentSession(null)
          setCurrentSessionId(null)
          pendingSessionId.current = null
        }
        return
      }

      try {
        await deleteSessionMutation.mutateAsync(id)
        if (currentSession?.id === id) {
          setCurrentSession(null)
          setCurrentSessionId(null)
          pendingSessionId.current = null
        }
      } catch {
        // Keep the existing list if deletion fails.
      }
    },
    [currentSession, deleteSessionMutation],
  )

  const sendMessage = useCallback(
    async (text: string): Promise<SessionMessage | null> => {
      const trimmed = text.trim()
      if (!trimmed || sending) return null
      setSending(true)

      const requestId = Date.now()
      const createdAt = nowSec()
      const existingSessionId = pendingSessionId.current ?? currentSession?.id ?? null
      const localSessionId =
        existingSessionId ??
        (USE_MOCK_STREAM ? `mock_${requestId}` : `local_${requestId}`)

      if (!pendingSessionId.current) {
        pendingSessionId.current = localSessionId
      }

      const userMsg: SessionMessage = {
        id: `local_${requestId}`,
        role: 'user',
        content: trimmed,
        sources: [],
        created_at: createdAt,
      }

      const sessionAfterUser: Session =
        currentSession && currentSession.id === localSessionId
          ? {
              ...currentSession,
              messages: [...currentSession.messages, userMsg],
              message_count: currentSession.messages.length + 1,
              preview: trimmed.slice(0, 60),
              updated_at: createdAt,
            }
          : {
              id: localSessionId,
              title: trimmed.slice(0, 30),
              created_at: createdAt,
              updated_at: createdAt,
              message_count: 1,
              preview: trimmed.slice(0, 60),
              messages: [userMsg],
            }

      setCurrentSession(sessionAfterUser)
      upsertMockSession(sessionAfterUser)

      if (USE_MOCK_STREAM) {
        const assistantId = `stream_${requestId}`
        let assistantMsg: SessionMessage = {
          id: assistantId,
          role: 'assistant',
          content: '',
          sources: [],
          stream_events: [],
          streaming: true,
          created_at: nowSec(),
        }

        const sessionWithAssistant: Session = {
          ...sessionAfterUser,
          messages: [...sessionAfterUser.messages, assistantMsg],
          message_count: sessionAfterUser.messages.length + 1,
          preview: trimmed.slice(0, 60),
          updated_at: assistantMsg.created_at,
        }

        setCurrentSession(sessionWithAssistant)
        upsertMockSession(sessionWithAssistant)

        try {
          for await (const event of createMockStream(trimmed)) {
            if (event.type === 'token') {
              assistantMsg = {
                ...assistantMsg,
                content: assistantMsg.content + event.content,
              }
            } else {
              assistantMsg = {
                ...assistantMsg,
                stream_events: [...(assistantMsg.stream_events ?? []), event],
                streaming: event.type === 'done' ? false : assistantMsg.streaming,
              }
            }

            updateCurrentMessage(assistantId, () => assistantMsg)
          }

          assistantMsg = { ...assistantMsg, streaming: false }
          updateCurrentMessage(assistantId, () => assistantMsg)
          return assistantMsg
        } catch (error) {
          const errorEvent: StreamEvent = {
            type: 'error',
            code: 'MOCK_STREAM_ERROR',
            message: error instanceof Error ? error.message : '流式响应中断',
            recoverable: true,
          }
          assistantMsg = {
            ...assistantMsg,
            stream_events: [...(assistantMsg.stream_events ?? []), errorEvent],
            streaming: false,
          }
          updateCurrentMessage(assistantId, () => assistantMsg)
          return assistantMsg
        } finally {
          setSending(false)
        }
      }

      let streamStarted = false
      let streamAssistantId = ''
      let streamAssistantMsg: SessionMessage | null = null

      try {
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
        }
        if (token) headers.Authorization = `Bearer ${token}`

        const res = await fetch('/api/v1/chat/stream', {
          method: 'POST',
          headers,
          body: JSON.stringify({
            message: trimmed,
            session_id: isLocalSessionId(existingSessionId) ? null : existingSessionId,
          }),
        })

        if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)

        streamStarted = true
        streamAssistantId = `stream_${requestId}`
        streamAssistantMsg = {
          id: streamAssistantId,
          role: 'assistant',
          content: '',
          sources: [],
          stream_events: [],
          streaming: true,
          created_at: nowSec(),
        }

        setCurrentSession((prev) => {
          if (!prev) return prev
          const messages = [...prev.messages, streamAssistantMsg as SessionMessage]
          return {
            ...prev,
            messages,
            message_count: messages.length,
            updated_at: (streamAssistantMsg as SessionMessage).created_at,
          }
        })

        let completed = false
        for await (const event of readSseEvents(res)) {
          if (!streamAssistantMsg) continue

          if (event.type === 'token') {
            streamAssistantMsg = {
              ...streamAssistantMsg,
              content: streamAssistantMsg.content + event.content,
            }
          } else if (event.type === 'done') {
            completed = true
            const sid = event.session_id ?? (!isLocalSessionId(existingSessionId) ? existingSessionId : null)
            if (sid) {
              pendingSessionId.current = sid
              setCurrentSessionId(sid)
            }
            streamAssistantMsg = {
              ...streamAssistantMsg,
              content: event.message ?? streamAssistantMsg.content,
              compliance_result: event.compliance_result ?? streamAssistantMsg.compliance_result,
              intent: event.intent ?? streamAssistantMsg.intent,
              browser_result: event.browser_result ?? streamAssistantMsg.browser_result,
              action_chain_id: event.action_chain_id ?? streamAssistantMsg.action_chain_id,
              sources: event.sources ?? streamAssistantMsg.sources,
              stream_events: [...(streamAssistantMsg.stream_events ?? []), event],
              streaming: false,
            }
            setCurrentSession((prev) => {
              if (!prev) return prev
              const nextSession = normalizeSession({
                ...prev,
                id: sid || prev.id,
                messages: prev.messages,
                message_count: prev.messages.length,
                preview: streamAssistantMsg?.content.slice(0, 60) || prev.preview,
                updated_at: nowSec(),
              })
              if (sid) upsertServerSessionCache(nextSession)
              return {
                ...nextSession,
              }
            })
          } else {
            streamAssistantMsg = {
              ...streamAssistantMsg,
              stream_events: [...(streamAssistantMsg.stream_events ?? []), event],
              streaming: event.type === 'error' ? false : streamAssistantMsg.streaming,
            }
          }

          updateCurrentMessage(streamAssistantId, () => streamAssistantMsg as SessionMessage)

          if (event.type === 'error') {
            completed = true
            break
          }
        }

        if (streamAssistantMsg && !completed) {
          streamAssistantMsg = { ...streamAssistantMsg, streaming: false }
          updateCurrentMessage(streamAssistantId, () => streamAssistantMsg as SessionMessage)
        }

        queryClient.invalidateQueries({ queryKey: ['sessions'] })
        setSending(false)
        return streamAssistantMsg
      } catch (error) {
        if (streamStarted && streamAssistantMsg) {
          const errorEvent: StreamEvent = {
            type: 'error',
            code: 'STREAM_ERROR',
            message: error instanceof Error ? error.message : '流式响应中断',
            recoverable: true,
          }
          streamAssistantMsg = {
            ...streamAssistantMsg,
            stream_events: [...(streamAssistantMsg.stream_events ?? []), errorEvent],
            streaming: false,
          }
          updateCurrentMessage(streamAssistantId, () => streamAssistantMsg as SessionMessage)
          setSending(false)
          return streamAssistantMsg
        }
      }

      try {
        const data = await sendMessageMutation.mutateAsync({
          message: trimmed,
          sessionId: isLocalSessionId(existingSessionId) ? null : existingSessionId,
        })

        const sid: string = data.session_id ?? ''
        if (sid) {
          pendingSessionId.current = sid
          setCurrentSessionId(sid)
        }

        const assistantMsg: SessionMessage = {
          id: `resp_${Date.now()}`,
          role: 'assistant',
          content: data.message ?? '',
          compliance_result: data.compliance_result ?? undefined,
          intent: data.intent ?? undefined,
          browser_result: data.browser_result ?? undefined,
          action_chain_id: data.action_chain_id ?? undefined,
          conflicts: data.conflicts ?? undefined,
          sources: data.sources ?? [],
          created_at: nowSec(),
        }

        setCurrentSession((prev) => {
          if (!prev) return null
          const messages = [...prev.messages, assistantMsg]
          const nextSession = normalizeSession({
            ...prev,
            id: sid || prev.id,
            messages,
            message_count: messages.length,
            preview: assistantMsg.content.slice(0, 60) || prev.preview,
            updated_at: assistantMsg.created_at,
          })
          if (sid) upsertServerSessionCache(nextSession)
          return nextSession
        })

        return assistantMsg
      } catch {
        const errMsg: SessionMessage = {
          id: `err_${Date.now()}`,
          role: 'assistant',
          content: '请求失败，请检查后端服务是否运行。',
          sources: [],
          created_at: nowSec(),
        }
        setCurrentSession((prev) => {
          if (!prev) return null
          const messages = [...prev.messages, errMsg]
          return {
            ...prev,
            messages,
            message_count: messages.length,
            preview: errMsg.content.slice(0, 60),
            updated_at: errMsg.created_at,
          }
        })
        return errMsg
      } finally {
        setSending(false)
      }
    },
    [
      currentSession,
      queryClient,
      sending,
      sendMessageMutation,
      token,
      updateCurrentMessage,
      upsertServerSessionCache,
      upsertMockSession,
    ],
  )

  return {
    sessions,
    currentSession,
    loading,
    sending,
    loadSessions,
    openSession,
    newSession,
    deleteSession,
    sendMessage,
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const value = useSessionsController()
  return createElement(SessionsContext.Provider, { value }, children)
}

export function useSessions() {
  const ctx = useContext(SessionsContext)
  if (!ctx) {
    throw new Error('useSessions must be used inside SessionProvider')
  }
  return ctx
}
