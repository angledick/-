import { createContext, useContext, useEffect, useRef, useCallback, useState, type ReactNode } from 'react'

// ── 类型 ─────────────────────────────────────────────────────────────────────

export interface WSNotification {
  type: string       // product_created | compliance_check_failed | certification_expiry | regulation_change | ...
  payload: unknown
  timestamp?: number
}

type WsStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

interface WebSocketContextValue {
  status: WsStatus
  lastMessage: WSNotification | null
  reconnect: () => void
  /** 注册事件监听器（返回取消注册函数） */
  on: (eventType: string, handler: (msg: WSNotification) => void) => () => void
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null)

// ── 配置 ─────────────────────────────────────────────────────────────────────

const WS_BASE = `ws://${typeof window !== 'undefined' ? (window.location.hostname || 'localhost') : 'localhost'}:8000`
const RECONNECT_DELAY = 5000
const HEARTBEAT_INTERVAL = 30_000

// ── Provider ─────────────────────────────────────────────────────────────────

export function WebSocketProvider({ children, userId = 'default' }: { children: ReactNode; userId?: string }) {
  const wsRef = useRef<WebSocket | null>(null)
  const [status, setStatus] = useState<WsStatus>('disconnected')
  const [lastMessage, setLastMessage] = useState<WSNotification | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const heartbeatTimer = useRef<ReturnType<typeof setInterval> | null>(null)
  const handlersRef = useRef<Map<string, Set<(msg: WSNotification) => void>>>(new Map())

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    setStatus('connecting')
    const url = `${WS_BASE}/api/v1/ws?user_id=${userId}`
    try {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        setStatus('connected')
        // 启动心跳
        heartbeatTimer.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }))
          }
        }, HEARTBEAT_INTERVAL)
      }

      ws.onclose = () => {
        setStatus('disconnected')
        wsRef.current = null
        if (heartbeatTimer.current) clearInterval(heartbeatTimer.current)
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY)
      }

      ws.onerror = () => {
        setStatus('error')
        ws.close()
      }

      ws.onmessage = (evt) => {
        try {
          const msg: WSNotification = JSON.parse(evt.data)
          setLastMessage(msg)
          // 分发到注册的处理器
          const handlers = handlersRef.current.get(msg.type)
          if (handlers) {
            handlers.forEach(h => h(msg))
          }
          // 通配符 * 处理器
          const wildcardHandlers = handlersRef.current.get('*')
          if (wildcardHandlers) {
            wildcardHandlers.forEach(h => h(msg))
          }
        } catch {
          // ignore non-JSON
        }
      }
    } catch {
      setStatus('error')
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY)
    }
  }, [userId])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      if (heartbeatTimer.current) clearInterval(heartbeatTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  const reconnect = useCallback(() => {
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    if (heartbeatTimer.current) clearInterval(heartbeatTimer.current)
    wsRef.current?.close()
    connect()
  }, [connect])

  const on = useCallback((eventType: string, handler: (msg: WSNotification) => void) => {
    if (!handlersRef.current.has(eventType)) {
      handlersRef.current.set(eventType, new Set())
    }
    handlersRef.current.get(eventType)!.add(handler)
    return () => {
      handlersRef.current.get(eventType)?.delete(handler)
    }
  }, [])

  return (
    <WebSocketContext.Provider value={{ status, lastMessage, reconnect, on }}>
      {children}
    </WebSocketContext.Provider>
  )
}

export function useWebSocketContext(): WebSocketContextValue {
  const ctx = useContext(WebSocketContext)
  if (!ctx) throw new Error('useWebSocketContext must be used inside WebSocketProvider')
  return ctx
}
