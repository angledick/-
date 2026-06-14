import { Outlet } from 'react-router-dom'

/**
 * 登录/未授权页的外壳。
 * 当前 LoginPage 自己处理居中布局与背景，这里只占位 + 提供 Outlet。
 */
export default function AuthLayout() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Outlet />
    </div>
  )
}
