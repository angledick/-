import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useSidebarStore } from '../context/AppStore'

const mainItems = [
  { to: '/', label: '概览', icon: '◫', end: true },
  { to: '/products', label: '产品合规', icon: '□' },
  { to: '/products/lifecycle', label: '出海生命周期', icon: '⟳' },
  { to: '/chat', label: '对话工作台', icon: '◇' },
  { to: '/knowledge', label: '知识库', icon: '▣' },
  { to: '/memory', label: '记忆树', icon: '△' },
  { to: '/compliance/system', label: '系统合规', icon: '◎' },
] as const

const adminItems = [
  { to: '/system/risk', label: '风险监控', icon: '!' },
  { to: '/metrics', label: '指标监控', icon: '≈' },
  { to: '/agents', label: 'Agent 监控', icon: '∴' },
  { to: '/config', label: '配置中心', icon: '⚙' },
  { to: '/config/scheduler', label: '定时任务', icon: '◌' },
  { to: '/system/users', label: '用户管理', icon: '⊙' },
] as const

export default function Sidebar() {
  const { user, isAdmin, logout } = useAuth()
  const collapsed = useSidebarStore(s => s.collapsed)
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <aside
      className={`
        flex shrink-0 flex-col border-r border-black/[0.06] bg-[#0F1720] text-white transition-all duration-200
        ${collapsed ? 'w-[84px]' : 'w-[258px]'}
      `}
    >
      <div className="border-b border-white/8 px-4 py-5">
        <div className={`flex items-center ${collapsed ? 'justify-center' : 'gap-3'}`}>
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#FFFFFF_0%,#CBD5E1_100%)] text-lg font-bold text-[#0F1720] shadow-[0_12px_28px_rgba(0,0,0,0.18)]">
            A
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="truncate text-[16px] font-semibold tracking-[-0.02em]">避风港</div>
              <div className="truncate text-xs text-white/60">跨境合规智能体工作台</div>
            </div>
          )}
        </div>
      </div>

      {user && !collapsed && (
        <div className="px-4 py-4">
          <div className="rounded-2xl border border-white/8 bg-white/5 px-3 py-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white text-sm font-bold text-[#0F1720]">
                {user.username[0].toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-white">{user.username}</div>
                <div className="mt-1 inline-flex rounded-full bg-white/8 px-2 py-0.5 text-[10px] text-white/70">
                  {user.role}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <nav className="flex-1 overflow-y-auto px-3 py-3">
        <div className="space-y-1">
          {mainItems.map(item => (
            <SidebarLink key={item.to} {...item} collapsed={collapsed} />
          ))}
        </div>

        {isAdmin && (
          <div className="mt-6">
            {!collapsed && (
              <div className="px-3 pb-2 text-[11px] font-semibold tracking-[0.14em] text-white/35 uppercase">
                管理区域
              </div>
            )}
            <div className="space-y-1">
              {adminItems.map(item => (
                <SidebarLink key={item.to} {...item} collapsed={collapsed} />
              ))}
            </div>
          </div>
        )}
      </nav>

      <div className="border-t border-white/8 px-3 py-3">
        <button
          onClick={() => useSidebarStore.getState().toggle()}
          className={`flex h-11 w-full items-center rounded-2xl px-3 text-sm text-white/75 transition hover:bg-white/6 hover:text-white ${collapsed ? 'justify-center' : 'gap-3'}`}
          title={collapsed ? '展开侧边栏' : '收起侧边栏'}
        >
          <span className="w-5 text-center text-sm">{collapsed ? '»' : '«'}</span>
          {!collapsed && <span>收起侧边栏</span>}
        </button>
        <button
          onClick={handleLogout}
          className={`mt-1 flex h-11 w-full items-center rounded-2xl px-3 text-sm text-white/75 transition hover:bg-[#3B1218] hover:text-white ${collapsed ? 'justify-center' : 'gap-3'}`}
        >
          <span className="w-5 text-center text-sm">×</span>
          {!collapsed && <span>退出登录</span>}
        </button>
      </div>
    </aside>
  )
}

function SidebarLink({
  to,
  label,
  icon,
  collapsed,
  end,
}: {
  to: string
  label: string
  icon: string
  collapsed: boolean
  end?: boolean
}) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `group flex w-full items-center rounded-2xl px-3 py-3 text-sm transition-all ${
          isActive
            ? 'bg-white text-[#0F1720] shadow-[0_12px_24px_rgba(0,0,0,0.18)]'
            : 'text-white/68 hover:bg-white/6 hover:text-white'
        } ${collapsed ? 'justify-center' : 'gap-3'}`
      }
    >
      <span className="inline-flex w-5 justify-center text-sm font-medium">{icon}</span>
      {!collapsed && <span className="truncate">{label}</span>}
    </NavLink>
  )
}
