import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import {
  LayoutDashboard,
  Search,
  MessageSquare,
  AlertTriangle,
  Library,
  Bot,
  Settings,
  Users,
  LogOut,
  Anchor,
  ChevronDown,
  Menu,
  X,
  Radar,
  PackageCheck,
  Newspaper,
  Bell,
  KeyRound,
  Brain,
  PlugZap,
  Timer,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { SessionList } from '@/components/chat/SessionList'
import { useSessions } from '@/hooks/useSessions'
import { useChangePassword } from '@/hooks/queries/useNotify'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { NotificationBell } from '@/components/common/NotificationBell'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { toast } from 'sonner'

const mainNav: { to: string; label: string; Icon: React.ComponentType<{ className?: string }> }[] = [
  { to: '/app/dashboard', label: '首页', Icon: LayoutDashboard },
  { to: '/app/chat', label: '智能对话', Icon: MessageSquare },
  { to: '/app/monitor', label: '风险监控', Icon: AlertTriangle },
  { to: '/app/settings/profile', label: '系统管理', Icon: Settings },
  { to: '/app/knowledge', label: '知识库', Icon: Library },
]

const toolNav: { to: string; label: string; Icon: React.ComponentType<{ className?: string }> }[] = [
  { to: '/app/compliance/system', label: '店铺合规', Icon: Radar },
  { to: '/app/products', label: '产品合规', Icon: PackageCheck },
  { to: '/app/compliance', label: '合规查询', Icon: Search },
  { to: '/app/news-monitor', label: '新闻监控', Icon: Newspaper },
  { to: '/app/nl-store', label: '记忆库', Icon: Brain },
]

const adminNav: { to: string; label: string; Icon: React.ComponentType<{ className?: string }> }[] = [
  { to: '/app/agent-config', label: 'Agent 配置', Icon: Bot },
  { to: '/app/model-config', label: '模型配置', Icon: Settings },
  { to: '/app/notify-config', label: '通知配置', Icon: Bell },
  { to: '/app/integrations', label: '第三方平台', Icon: PlugZap },
  { to: '/app/scheduler', label: '定时任务', Icon: Timer },
  { to: '/app/user-manage', label: '用户管理', Icon: Users },
]

export default function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, isAdmin, logout } = useAuth()
  const {
    sessions,
    currentSession,
    openSession,
    deleteSession,
    newSession,
  } = useSessions()

  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [pwOpen, setPwOpen] = useState(false)
  const changePw = useChangePassword()

  // Escape 键关闭用户菜单
  useEffect(() => {
    if (!userMenuOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setUserMenuOpen(false)
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [userMenuOpen])
  const isOnChat =
    location.pathname.startsWith('/app/chat') ||
    location.pathname.startsWith('/app/products/')

  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  const handleSelect = async (id: string) => {
    await openSession(id)
    if (location.pathname !== '/app/chat') navigate('/app/chat')
    setMobileOpen(false)
  }

  const handleNew = () => {
    newSession()
    if (location.pathname !== '/app/chat') navigate('/app/chat')
    setMobileOpen(false)
  }

  const handleNavClick = () => {
    setMobileOpen(false)
  }

  const sidebarContent = (
    <aside className="flex h-full w-full flex-col border-r border-border/60 bg-card lg:w-[240px]">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-5">
        <div className="flex size-8 items-center justify-center rounded-lg bg-foreground text-background">
          <Anchor className="size-4" />
        </div>
        <div className="leading-tight">
          <div className="text-[14px] font-semibold tracking-tight">避风港</div>
          <div className="text-[10.5px] text-muted-foreground">跨境合规智能体</div>
        </div>
        <NotificationBell className="ml-auto hidden lg:flex" />
      </div>

      {/* 主导航 */}
      <nav aria-label="主导航" className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-4">
        {mainNav.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={handleNavClick}
            className={({ isActive }) =>
              cn(
                'flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[13.5px] transition-colors',
                isActive
                  ? 'bg-foreground/[0.06] font-medium text-foreground'
                  : 'text-foreground/75 hover:bg-muted/60 hover:text-foreground',
              )
            }
          >
            <Icon className="size-4 shrink-0" />
            {label}
          </NavLink>
        ))}

        <div className="pt-5">
          <div className="px-2.5 pb-1 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground/70">
            合规工具
          </div>
          <div className="space-y-0.5">
            {toolNav.map(({ to, label, Icon }) => (
              <NavLink
                key={to}
                to={to}
                onClick={handleNavClick}
                className={({ isActive }) =>
                  cn(
                    'flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[13.5px] transition-colors',
                    isActive
                      ? 'bg-foreground/[0.06] font-medium text-foreground'
                      : 'text-foreground/75 hover:bg-muted/60 hover:text-foreground',
                  )
                }
              >
                <Icon className="size-4 shrink-0" />
                {label}
              </NavLink>
            ))}
          </div>
        </div>

        {/* 会话历史 */}
        {isOnChat && (
          <div className="pt-3">
            <SessionList
              sessions={sessions}
              currentId={currentSession?.id}
              onSelect={handleSelect}
              onDelete={deleteSession}
              onNew={handleNew}
              defaultOpen
            />
          </div>
        )}

        {/* Admin 专区 */}
        {isAdmin && (
          <div className="pt-5">
            <div className="px-2.5 pb-1 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground/70">
              管理员
            </div>
            <div className="space-y-0.5">
              {adminNav.map(({ to, label, Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  onClick={handleNavClick}
                  className={({ isActive }) =>
                    cn(
                      'flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[13.5px] transition-colors',
                      isActive
                        ? 'bg-foreground/[0.06] font-medium text-foreground'
                        : 'text-foreground/75 hover:bg-muted/60 hover:text-foreground',
                    )
                  }
                >
                  <Icon className="size-4 shrink-0" />
                  {label}
                </NavLink>
              ))}
            </div>
          </div>
        )}
      </nav>

      {/* 用户区 */}
      {user && (
        <div className="relative border-t border-border/60 p-2">
          <button
            onClick={() => setUserMenuOpen((o) => !o)}
            aria-label="用户菜单"
            aria-expanded={userMenuOpen}
            aria-haspopup="true"
            className="flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted/60"
          >
            <div
              className={cn(
                'flex size-7 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold',
                isAdmin
                  ? 'bg-foreground text-background'
                  : 'bg-muted text-foreground',
              )}
            >
              {user.username?.[0]?.toUpperCase() ?? '?'}
            </div>
            <div className="min-w-0 flex-1 leading-tight">
              <div className="truncate text-[12.5px] font-medium">{user.username}</div>
              <Badge
                variant={isAdmin ? 'secondary' : 'outline'}
                className="mt-0.5 h-[18px] px-1.5 text-[10px] font-medium"
              >
                {/* PRD 三角色（独立卖家/企业/入门小白）待后端 roleLabel 字段；现回退 admin/user */}
                {(user as { roleLabel?: string }).roleLabel ?? (isAdmin ? '管理员' : '成员')}
              </Badge>
            </div>
            <ChevronDown
              className={cn(
                'size-3.5 shrink-0 text-muted-foreground transition-transform',
                userMenuOpen && 'rotate-180',
              )}
            />
          </button>

          {userMenuOpen && (
            <>
              <button
                aria-label="关闭菜单"
                onClick={() => setUserMenuOpen(false)}
                className="fixed inset-0 z-40 cursor-default"
              />
              <div
                role="menu"
                className="absolute bottom-full left-2 right-2 z-50 mb-1 overflow-hidden rounded-lg border border-border/60 bg-popover shadow-md animate-fade-in"
              >
                <button
                  onClick={() => {
                    setPwOpen(true)
                    setUserMenuOpen(false)
                  }}
                  role="menuitem"
                  className="flex w-full items-center gap-2 px-3 py-2 text-[12.5px] text-foreground/80 transition-colors hover:bg-muted/60 hover:text-foreground"
                >
                  <KeyRound className="size-3.5" />
                  修改密码
                </button>
                <button
                  onClick={() => {
                    logout()
                    setUserMenuOpen(false)
                    setMobileOpen(false)
                  }}
                  role="menuitem"
                  className="flex w-full items-center gap-2 px-3 py-2 text-[12.5px] text-foreground/80 transition-colors hover:bg-muted/60 hover:text-foreground"
                >
                  <LogOut className="size-3.5" />
                  退出登录
                </button>
                <div className="border-t border-border/60 px-3 py-1.5 text-[10.5px] text-muted-foreground">
                  v0.2.0
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </aside>
  )

  /** 修改密码 Dialog */
  const PwDialog = (
    <PwChangeDialog
      open={pwOpen}
      onClose={() => setPwOpen(false)}
      onChange={(oldPw, newPw) =>
        changePw
          .mutateAsync({ oldPw, newPw })
          .then(() => {
            setPwOpen(false)
            toast.success('密码已修改')
          })
          .catch((e) => toast.error(e.message))
      }
      saving={changePw.isPending}
    />
  )

  return (
    <>
      {/* 桌面端：固定侧边栏 */}
      <div className="hidden lg:block">{sidebarContent}</div>
      {PwDialog}

      {/* 移动端：Sheet 抽屉 + 顶栏汉堡菜单 */}
      <div className="fixed inset-x-0 top-0 z-40 lg:hidden">
        {/* 顶栏 */}
        <header className="flex h-14 w-full items-center gap-3 border-b border-border/60 bg-card px-4">
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger asChild>
              <button
                aria-label="打开菜单"
                className="flex size-9 items-center justify-center rounded-md text-foreground/75 transition-colors hover:bg-muted/60 hover:text-foreground"
              >
                <Menu className="size-5" />
              </button>
            </SheetTrigger>
            <SheetContent
              side="left"
              hideClose
              className="w-[min(84vw,280px)] p-0"
            >
              <SheetTitle className="sr-only">主导航</SheetTitle>
              <SheetDescription className="sr-only">
                打开页面导航、会话历史和管理员入口。
              </SheetDescription>
              <button
                type="button"
                aria-label="关闭菜单"
                onClick={() => setMobileOpen(false)}
                className="absolute right-3 top-3 z-10 flex size-8 items-center justify-center rounded-md text-foreground/70 transition-colors hover:bg-muted/60 hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <X className="size-4" />
              </button>
              {sidebarContent}
            </SheetContent>
          </Sheet>

          {/* 顶栏标题 */}
          <div className="flex items-center gap-2">
            <div className="flex size-7 items-center justify-center rounded-lg bg-foreground text-background">
              <Anchor className="size-3.5" />
            </div>
            <div className="text-[13px] font-semibold">避风港</div>
          </div>
          <NotificationBell className="ml-auto" />
        </header>
      </div>
    </>
  )
}

/* ─────────────────────────── 修改密码 Dialog ─────────────────────────── */

function PwChangeDialog({
  open,
  onClose,
  onChange,
  saving,
}: {
  open: boolean
  onClose: () => void
  onChange: (oldPw: string, newPw: string) => Promise<unknown>
  saving: boolean
}) {
  const [oldPw, setOldPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirm, setConfirm] = useState('')

  const handle = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!oldPw) return
    if (newPw.length < 6) return
    if (newPw !== confirm) return
    await onChange(oldPw, newPw)
    setOldPw(''); setNewPw(''); setConfirm('')
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>修改密码</DialogTitle>
          <DialogDescription>输入原密码并设置新密码（至少 6 位）</DialogDescription>
        </DialogHeader>
        <form onSubmit={handle} className="space-y-4">
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">原密码</label>
            <input
              type="password"
              value={oldPw}
              onChange={(e) => setOldPw(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">新密码</label>
            <input
              type="password"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">确认新密码</label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            />
            {confirm && newPw !== confirm && (
              <p className="mt-1 text-xs text-destructive">两次密码不一致</p>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>取消</Button>
            <Button type="submit" disabled={saving || !oldPw || newPw.length < 6 || newPw !== confirm}>
              {saving ? '修改中…' : '确认修改'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
