import { useEffect, useRef, useCallback, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

interface WSMessage {
  type: 'alert' | 'scan_update' | 'session_update' | 'new_message'
  payload: unknown
}

type WsStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

interface UseWebSocketReturn {
  status: WsStatus
  lastMessage: WSMessage | null
  reconnect: () => void
}

const WS_ENABLED = import.meta.env.VITE_ENABLE_WEBSOCKET === 'true'
const WS_BASE =
  import.meta.env.VITE_WS_BASE_URL ||
  `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname || 'localhost'}:8000`

export function useWebSocket(userId = 'default', enabled = WS_ENABLED): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null)
  const [status, setStatus] = useState<WsStatus>('disconnected')
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const retryCount = useRef(0)
  const queryClient = useQueryClient()

  const connect = useCallback(() => {
    if (!enabled) {
      setStatus('disconnected')
      return
    }
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    setStatus('connecting')
    const url = `${WS_BASE}/api/v1/ws?user_id=${userId}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      retryCount.current = 0
      setStatus('connected')
    }

    ws.onclose = () => {
      setStatus('disconnected')
      wsRef.current = null
      if (!enabled) return

      retryCount.current += 1
      const delay = Math.min(30000, 5000 * retryCount.current)
      reconnectTimer.current = setTimeout(connect, delay)
    }

    ws.onerror = () => {
      setStatus('error')
      ws.close()
    }

    ws.onmessage = (evt) => {
      try {
        const msg: WSMessage = JSON.parse(evt.data)
        setLastMessage(msg)

        // 根据消息类型自动更新 TanStack Query 缓存
        switch (msg.type) {
          case 'session_update':
            // 会话列表更新 - 自动失效缓存，触发重新获取
            queryClient.invalidateQueries({ queryKey: ['sessions'] })
            break

          case 'new_message':
            // 新消息到达 - 自动失效当前会话缓存
            const sessionId = (msg.payload as { session_id?: string })?.session_id
            if (sessionId) {
              queryClient.invalidateQueries({ queryKey: ['session', sessionId] })
            }
            break

          case 'alert':
            break

          case 'scan_update':
            break

          default:
            break
        }
      } catch (err) {
        if (import.meta.env.DEV) {
          console.warn('[WebSocket] Failed to parse message:', err)
        }
      }
    }
  }, [enabled, userId, queryClient])

  useEffect(() => {
    if (!enabled) {
      setStatus('disconnected')
      return
    }
    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect, enabled])

  const reconnect = useCallback(() => {
    if (!enabled) return
    retryCount.current = 0
    wsRef.current?.close()
    connect()
  }, [connect, enabled])

  return { status, lastMessage, reconnect }
}
