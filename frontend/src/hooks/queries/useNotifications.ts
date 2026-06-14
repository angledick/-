import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useAuth } from '@/context/AuthContext'

const API = '/api/v1'

/**
 * 通知项（字段以后端 NotificationItem.model_dump 为准；前端取常用字段，其余宽松保留）。
 * 后端端点：GET /notifications → { notifications: [...], total }。
 */
export interface NotificationItem {
  id: string
  title: string
  message?: string
  body?: string
  /** 后端可能用 is_read 或 read */
  is_read?: boolean
  read?: boolean
  severity?: string
  created_at?: string | number
  [key: string]: unknown
}

/** 未读通知数（铃铛红点）。30s 轮询保持红点新鲜。 */
export function useUnreadCount() {
  const { authFetch } = useAuth()
  return useQuery<number>({
    queryKey: ['notifications', 'unread-count'],
    queryFn: async () => {
      const res = await authFetch(`${API}/notifications/unread-count`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      return Number(data?.count ?? 0)
    },
    refetchInterval: 30000,
  })
}

/** 通知列表（抽屉最近 20 条）。enabled 控制抽屉关闭时不拉取。 */
export function useNotifications(enabled = true) {
  const { authFetch } = useAuth()
  return useQuery<NotificationItem[]>({
    queryKey: ['notifications', 'list'],
    enabled,
    queryFn: async () => {
      const res = await authFetch(`${API}/notifications?limit=20`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      return Array.isArray(data?.notifications) ? data.notifications : []
    },
  })
}

/** 标记单条已读 */
export function useMarkRead() {
  const qc = useQueryClient()
  const { authFetch } = useAuth()
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await authFetch(`${API}/notifications/${id}/read`, { method: 'PUT' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  })
}

/** 全部已读 */
export function useMarkAllRead() {
  const qc = useQueryClient()
  const { authFetch } = useAuth()
  return useMutation({
    mutationFn: async () => {
      const res = await authFetch(`${API}/notifications/read-all`, { method: 'PUT' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  })
}
