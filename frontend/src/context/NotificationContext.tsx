import { createContext, useContext, useEffect, useRef, useState, useCallback, type ReactNode } from 'react'
import { useWebSocketContext } from './WebSocketContext'
import { riskAlertsApi } from '../api/config'

// ── 类型 ─────────────────────────────────────────────────────────────────────

export type Severity = 'low' | 'medium' | 'high' | 'critical'

export interface NotificationItem {
  id: string
  type: string
  severity: Severity
  title: string
  message?: string
  timestamp: number
  read: boolean
  category?: string
  actionUrl?: string
  affectedProducts?: string[]
}

export interface ToastItem {
  id: string
  severity: Severity
  title: string
  message?: string
  duration?: number   // 毫秒，默认 6000
  action?: { label: string; onClick: () => void }
}

interface NotificationContextValue {
  notifications: NotificationItem[]
  toasts: ToastItem[]
  unreadCount: number
  addNotification: (item: Omit<NotificationItem, 'id' | 'timestamp' | 'read'>) => void
  dismissNotification: (id: string) => void
  markAllRead: () => void
  clearAll: () => void
  addToast: (item: Omit<ToastItem, 'id'>) => void
  removeToast: (id: string) => void
}

const NotificationContext = createContext<NotificationContextValue | null>(null)

// ── 工具 ─────────────────────────────────────────────────────────────────────

let _toastId = 0
function nextId(): string { return `n_${++_toastId}_${Date.now()}` }

function inferSeverity(type: string): Severity {
  if (type.includes('expire') || type.includes('fail') || type.includes('critical')) return 'critical'
  if (type.includes('change') || type.includes('warning') || type.includes('risk')) return 'high'
  if (type.includes('update') || type.includes('remind')) return 'medium'
  return 'low'
}

// ── Provider ─────────────────────────────────────────────────────────────────

export function NotificationProvider({ children }: { children: ReactNode }) {
  const { on } = useWebSocketContext()
  const [notifications, setNotifications] = useState<NotificationItem[]>([])
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const toastTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  // 初始加载风险预警作为已有通知
  useEffect(() => {
    const load = async () => {
      try {
        const res = await riskAlertsApi.list({ size: 50 })
        const items: NotificationItem[] = res.alerts.map(a => ({
          id: a.id,
          type: a.alert_type,
          severity: (a.severity === 'critical' ? 'critical' : a.severity) as Severity,
          title: a.title,
          message: a.message,
          timestamp: new Date(a.created_at).getTime(),
          read: a.dismissed ?? false,
          category: 'risk_alert',
          affectedProducts: a.affected_products,
        }))
        setNotifications(items)
      } catch {
        // 静默降级
      }
    }
    load()
  }, [])

  // 注册 WebSocket 事件 → 通知/Toast
  useEffect(() => {
    const unsub = on('*', (msg) => {
      const payload = msg.payload as Record<string, unknown> | undefined
      const title = (payload?.title as string) || msg.type
      const severity = inferSeverity(msg.type)

      // 加入通知中心
      const notif: NotificationItem = {
        id: `ws_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
        type: msg.type,
        severity,
        title,
        message: payload?.message as string | undefined,
        timestamp: msg.timestamp ?? Date.now(),
        read: false,
      }
      setNotifications(prev => [notif, ...prev])

      // 弹出 Toast
      addToast({
        severity,
        title,
        message: payload?.message as string | undefined,
        duration: severity === 'critical' ? 10000 : 6000,
      })
    })
    return unsub
  }, [on])

  const addNotification = useCallback((item: Omit<NotificationItem, 'id' | 'timestamp' | 'read'>) => {
    const notif: NotificationItem = {
      ...item,
      id: nextId(),
      timestamp: Date.now(),
      read: false,
    }
    setNotifications(prev => [notif, ...prev])
  }, [])

  const dismissNotification = useCallback((id: string) => {
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n))
  }, [])

  const markAllRead = useCallback(() => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })))
  }, [])

  const clearAll = useCallback(() => {
    setNotifications([])
  }, [])

  const addToast = useCallback((item: Omit<ToastItem, 'id'>) => {
    const id = nextId()
    const toast: ToastItem = { ...item, id }
    const duration = item.duration ?? 6000

    setToasts(prev => [...prev, toast])

    // 自动移除
    const timer = setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
      toastTimers.current.delete(id)
    }, duration)
    toastTimers.current.set(id, timer)
  }, [])

  const removeToast = useCallback((id: string) => {
    const timer = toastTimers.current.get(id)
    if (timer) { clearTimeout(timer); toastTimers.current.delete(id) }
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  // 清理 timers
  useEffect(() => {
    return () => {
      toastTimers.current.forEach(t => clearTimeout(t))
    }
  }, [])

  const unreadCount = notifications.filter(n => !n.read).length

  return (
    <NotificationContext.Provider value={{
      notifications, toasts, unreadCount,
      addNotification, dismissNotification, markAllRead, clearAll,
      addToast, removeToast,
    }}>
      {children}
    </NotificationContext.Provider>
  )
}

export function useNotificationContext(): NotificationContextValue {
  const ctx = useContext(NotificationContext)
  if (!ctx) throw new Error('useNotificationContext must be used inside NotificationProvider')
  return ctx
}
