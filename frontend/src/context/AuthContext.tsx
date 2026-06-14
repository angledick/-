import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { useWebSocket } from '@/hooks/useWebSocket'

const API = '/api/v1'

export interface AuthUser {
  id: string
  username: string
  role: 'admin' | 'user'
}

interface AuthContextValue {
  user: AuthUser | null
  token: string | null
  isAdmin: boolean
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  // 全局 WebSocket 连接；默认关闭，设置 VITE_ENABLE_WEBSOCKET=true 后启用
  useWebSocket(user?.id || 'default')

  // 启动时从 localStorage 恢复，并验证 token 有效性
  useEffect(() => {
    const storedToken = localStorage.getItem('astra_token')
    const storedUser = localStorage.getItem('astra_user')

    if (!storedToken || !storedUser) {
      setLoading(false)
      return
    }

    // 先恢复本地状态（快速渲染），再异步验证 token
    try {
      setToken(storedToken)
      setUser(JSON.parse(storedUser))
    } catch {
      localStorage.removeItem('astra_token')
      localStorage.removeItem('astra_user')
      setLoading(false)
      return
    }

    // 异步调用 /auth/me 验证 token 是否仍然有效
    fetch(`${API}/auth/me`, {
      headers: { Authorization: `Bearer ${storedToken}` },
    })
      .then((res) => {
        if (!res.ok) {
          // token 过期或无效，清除本地状态
          localStorage.removeItem('astra_token')
          localStorage.removeItem('astra_user')
          setToken(null)
          setUser(null)
        }
        // 验证通过则保持已恢复的状态，无需额外操作
      })
      .catch(() => {
        // 网络错误不登出，保留本地状态供离线使用
      })
      .finally(() => {
        setLoading(false)
      })
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || '登录失败')
    }
    const data = await res.json()
    const newToken: string = data.access_token
    const newUser: AuthUser = {
      id: data.user_id,
      username: data.username,
      role: data.role,
    }
    localStorage.setItem('astra_token', newToken)
    localStorage.setItem('astra_user', JSON.stringify(newUser))
    setToken(newToken)
    setUser(newUser)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('astra_token')
    localStorage.removeItem('astra_user')
    setToken(null)
    setUser(null)
  }, [])

  /** 带 Authorization 的 fetch 封装 */
  const authFetch = useCallback(
    (input: RequestInfo, init: RequestInit = {}): Promise<Response> => {
      const headers = new Headers(init.headers || {})
      if (token) headers.set('Authorization', `Bearer ${token}`)
      return fetch(input, { ...init, headers })
    },
    [token]
  )

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAdmin: user?.role === 'admin',
        loading,
        login,
        logout,
        authFetch,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
