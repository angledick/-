import { NavLink } from 'react-router-dom'
import { AlertTriangle, LayoutDashboard, Library, MessageSquare, Settings } from 'lucide-react'

import { cn } from '@/lib/utils'

const tabs = [
  { to: '/app/dashboard', label: '首页', Icon: LayoutDashboard },
  { to: '/app/chat', label: '对话', Icon: MessageSquare },
  { to: '/app/monitor', label: '风险', Icon: AlertTriangle },
  { to: '/app/settings/profile', label: '系统', Icon: Settings },
  { to: '/app/knowledge', label: '知识库', Icon: Library },
]

/**
 * 移动端底部 Tab Bar（PRD：移动端侧栏→底部 Tab）。
 * 与现有 Sheet 抽屉共存：本组件为高频 5 项快捷导航，顶栏汉堡 Sheet 保留完整 9+6 项导航（不删功能）。
 * 仅 <lg 显示（lg:hidden）；AppLayout main 需配 pb-14 lg:pb-0 避免内容被遮挡。
 */
export function MobileTabBar() {
  return (
    <nav
      aria-label="移动端底部导航"
      className="fixed inset-x-0 bottom-0 z-40 flex h-14 items-stretch border-t border-border/60 bg-card pb-[env(safe-area-inset-bottom)] lg:hidden"
    >
      {tabs.map(({ to, label, Icon }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            cn(
              'flex flex-1 flex-col items-center justify-center gap-0.5 text-[10.5px] transition-colors',
              isActive
                ? 'font-medium text-foreground'
                : 'text-foreground/60 hover:text-foreground',
            )
          }
        >
          {({ isActive }) => (
            <>
              <Icon className={cn('size-5', isActive && 'text-primary')} />
              {label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}
