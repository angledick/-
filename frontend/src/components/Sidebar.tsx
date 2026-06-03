import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useSidebarStore } from '../context/AppStore'

// ── 导航项 ───────────────────────────────────────────────────────────────────

const mainItems = [
  { to: '/',              label: '概览',      icon: '◉',  end: true },
  { to: '/compliance/system', label: '系统合规', icon: '⇌' },
  { to: '/products',      label: '产品合规',  icon: '📦' },
  { to: '/chat',          label: '对话工作台', icon: '💬' },
  { to: '/config',        label: '配置中心',  icon: '⚙' },
  { to: '/knowledge',     label: '知识库',    icon: '▦' },
  { to: '/memory',        label: '记忆树',    icon: '🌳' },
] as const

const adminItems = [
  { to: '/metrics',       label: '指标监控',  icon: '📊' },
  { to: '/agents',        label: 'Agent监控', icon: '🤖' },
  { to: '/config/scheduler', label: '定时任务', icon: '⏱' },
  { to: '/system/users',  label: '用户管理',  icon: '👥' },
  { to: '/system/risk',   label: '风险监控',  icon: '⚠' },
] as const

// ── 组件 ─────────────────────────────────────────────────────────────────────

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
        flex flex-col shrink-0 bg-white border-r border-black/6 py-6
        transition-all duration-200
        ${collapsed ? 'w-16' : 'w-56'}
      `}
    >
      {/* Logo */}
      <div className="px-5 pb-5">
        <div className="flex items-center gap-2.5">
          <div className="w-8.5 h-8.5 rounded-lg bg-gradient-to-br from-[#1D1D1F] to-[#424245] flex items-center justify-center text-white text-base font-bold shrink-0 w-[34px] h-[34px]">
            A
          </div>
          {!collapsed && (
            <div>
              <div className="font-semibold text-[15px] text-[#1D1D1F] leading-tight">避风港</div>
              <div className="text-[11px] text-[#86868B] leading-tight">跨境合规智能体</div>
            </div>
          )}
        </div>
      </div>

      {/* 当前用户 */}
      {user && !collapsed && (
        <div className="mx-3 mb-4 px-3 py-2 rounded-lg bg-[#F5F5F7] flex items-center gap-2">
          <div
            className={`w-6.5 h-6.5 rounded-full flex items-center justify-center text-[11px] font-bold shrink-0 w-[26px] h-[26px] ${
              isAdmin ? 'bg-[#1D1D1F] text-white' : 'bg-[#E5E5EA] text-[#1D1D1F]'
            }`}
          >
            {user.username[0].toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-semibold text-[#1D1D1F] truncate">{user.username}</div>
            <span
              className={`text-[10px] font-semibold px-1.5 py-px rounded inline-block ${
                isAdmin
                  ? 'bg-black/6 text-[#1D1D1F]'
                  : 'bg-[#0071E3]/10 text-[#0071E3]'
              }`}
            >
              {user.role}
            </span>
          </div>
        </div>
      )}

      {/* 主导航 */}
      <nav className="flex-1 overflow-y-auto">
        {mainItems.map(item => (
          <SidebarLink key={item.to} to={item.to} label={item.label} icon={item.icon} collapsed={collapsed} end={'end' in item && item.end} />
        ))}

        {/* 管理员专区 */}
        {isAdmin && (
          <>
            {!collapsed && (
              <div className="mx-5 mt-3 mb-1.5 text-[10px] font-semibold text-[#C7C7CC] uppercase tracking-wider">
                管理员
              </div>
            )}
            {adminItems.map(item => (
              <SidebarLink key={item.to} to={item.to} label={item.label} icon={item.icon} collapsed={collapsed} />
            ))}
          </>
        )}
      </nav>

      {/* 底部：折叠 + 退出 */}
      <div className="px-3 pt-2 space-y-1">
        <button
          onClick={() => useSidebarStore.getState().toggle()}
          className="w-full px-3 py-2 border-none bg-transparent cursor-pointer text-[13px] text-[#86868B] flex items-center gap-2 rounded-md text-left font-[inherit] hover:bg-[#F5F5F7] transition-colors"
          title={collapsed ? '展开侧边栏' : '折叠侧边栏'}
        >
          <span className="text-sm">{collapsed ? '▶' : '◀'}</span>
          {!collapsed && '折叠侧边栏'}
        </button>
        <button
          onClick={handleLogout}
          className="w-full px-3 py-2 border-none bg-transparent cursor-pointer text-[13px] text-[#86868B] flex items-center gap-2 rounded-md text-left font-[inherit] hover:bg-red-500/6 transition-colors"
        >
          <span className="text-sm">⬡</span>
          {!collapsed && '退出登录'}
        </button>
        {!collapsed && (
          <div className="px-2 pt-1.5 text-[11px] text-[#C7C7CC]">v4.0.0</div>
        )}
      </div>
    </aside>
  )
}

// ── 导航链接 ─────────────────────────────────────────────────────────────────

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
        `flex items-center gap-2.5 w-full px-5 py-2.5 border-none cursor-pointer text-sm transition-all font-[inherit] text-left border-r-2 ${
          isActive
            ? 'font-semibold text-[#1D1D1F] bg-[#F5F5F7] border-r-[#1D1D1F]'
            : 'font-normal text-[#86868B] bg-transparent border-r-transparent hover:text-[#1D1D1F]'
        } ${collapsed ? 'justify-center px-2' : ''}`
      }
    >
      <span className="text-base w-6 text-center">{icon}</span>
      {!collapsed && label}
    </NavLink>
  )
}
