import { Navigate, Outlet, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from '@/context/AuthContext'

function LoadingScreen() {
  return (
    <div className="flex h-screen items-center justify-center bg-muted">
      <div className="text-sm text-muted-foreground">加载中…</div>
    </div>
  )
}

/** 必须登录才能访问；否则跳 /auth/login 并带 from 用于回跳 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <LoadingScreen />
  if (!user) return <Navigate to="/auth/login" state={{ from: location }} replace />
  return <>{children}</>
}

/** 已登录用户不应再进认证页，自动跳回应用首页 */
export function PublicOnly({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <LoadingScreen />
  if (user) return <Navigate to="/app/dashboard" replace />
  return <>{children}</>
}

/** Admin 路由 layout：非 admin 直接踢回 /app/chat */
export function RequireAdmin() {
  const { isAdmin, loading } = useAuth()
  if (loading) return <LoadingScreen />
  if (!isAdmin) return <Navigate to="/app/chat" replace />
  return <Outlet />
}
