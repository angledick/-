import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/context/AuthContext'
import type { Session, SessionSummary } from '@/types'

const API = '/api/v1'
const USE_MOCK_STREAM = import.meta.env.VITE_STREAM_MODE === 'mock'

/**
 * 会话列表查询
 */
export function useSessionsQuery() {
  const { authFetch } = useAuth()

  return useQuery({
    queryKey: ['sessions'],
    queryFn: async (): Promise<SessionSummary[]> => {
      if (USE_MOCK_STREAM) return []
      const res = await authFetch(`${API}/sessions`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    },
    enabled: !USE_MOCK_STREAM,
    initialData: USE_MOCK_STREAM ? [] : undefined,
    staleTime: 30_000, // 30 秒内不重新请求
  })
}

/**
 * 单个会话详情查询
 */
export function useSessionQuery(id: string | null) {
  const { authFetch } = useAuth()

  return useQuery({
    queryKey: ['session', id],
    queryFn: async (): Promise<Session> => {
      if (!id) throw new Error('No session id')
      const res = await authFetch(`${API}/sessions/${id}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    },
    enabled: !!id && !USE_MOCK_STREAM, // 只有当 id 存在且后端模式启用时才执行查询
    staleTime: 60_000, // 1 分钟内不重新请求
  })
}

/**
 * 删除会话 mutation
 */
export function useDeleteSessionMutation() {
  const { authFetch } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (sessionId: string) => {
      const res = await authFetch(`${API}/sessions/${sessionId}`, {
        method: 'DELETE',
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
    },
    onSuccess: () => {
      // 删除成功后重新获取会话列表
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
    },
  })
}

/**
 * 发送消息 mutation
 */
export function useSendMessageMutation() {
  const { token } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      message,
      sessionId,
    }: {
      message: string
      sessionId: string | null
    }) => {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const res = await fetch(`${API}/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message,
          session_id: sessionId,
        }),
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    },
    onSuccess: () => {
      // 发送成功后重新获取会话列表
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
    },
  })
}
