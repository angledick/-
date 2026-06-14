import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import NotificationCenter from './NotificationCenter'
import ToastNotification from './ToastNotification'
import { useWebSocketContext } from '../context/WebSocketContext'
import { useSidebarStore } from '../context/AppStore'

const wsStatusConfig: Record<string, { label: string; color: string; dot: string }> = {
  connected: { label: '实时连接正常', color: 'text-[#166534]', dot: 'bg-[#22C55E]' },
  connecting: { label: '正在连接', color: 'text-[#9A6700]', dot: 'bg-[#F59E0B]' },
  disconnected: { label: '连接断开', color: 'text-[#6B7280]', dot: 'bg-[#9CA3AF]' },
  error: { label: '连接错误', color: 'text-[#B42318]', dot: 'bg-[#EF4444]' },
}

const titleMap: Array<{ match: (path: string) => boolean; title: string; subtitle: string }> = [
  { match: p => p === '/', title: '控制台概览', subtitle: '查看产品、预警、简报和系统状态' },
  { match: p => p.startsWith('/products'), title: '产品合规', subtitle: '按生命周期管理产品与合规状态' },
  { match: p => p.startsWith('/chat'), title: '对话工作台', subtitle: '统一处理合规咨询、配置与执行' },
  { match: p => p.startsWith('/knowledge'), title: '知识库', subtitle: '浏览与检索法规、规则和导入内容' },
  { match: p => p.startsWith('/memory'), title: '记忆树', subtitle: '追踪系统记忆与上下文结构' },
  { match: p => p.startsWith('/metrics'), title: '指标监控', subtitle: '查看系统健康度与运行指标' },
  { match: p => p.startsWith('/agents'), title: 'Agent 监控', subtitle: '查看 Agent 状态与协同执行情况' },
  { match: p => p.startsWith('/system/risk'), title: '风险监控', subtitle: '监控情报流、预警、关键词与风险热力图' },
  { match: p => p.startsWith('/system/users'), title: '用户管理', subtitle: '管理用户、角色与访问权限' },
  { match: p => p.startsWith('/config'), title: '配置中心', subtitle: '管理 Agent、技能、工具与模型配置' },
  { match: p => p.startsWith('/compliance/system'), title: '系统合规', subtitle: '查看十阶段流程与系统合规状态' },
]

export default function Layout() {
  const { status: wsStatus, reconnect } = useWebSocketContext()
  const collapsed = useSidebarStore(s => s.collapsed)
  const location = useLocation()

  const wsInfo = wsStatusConfig[wsStatus] ?? wsStatusConfig.disconnected ?? {
    label: '—', color: 'text-[#6B7280]', dot: 'bg-[#9CA3AF]',
  }
  const current = titleMap.find(item => item.match(location.pathname)) || {
    title: '避风港',
    subtitle: '跨境合规智能体工作台',
  }

  return (
    <div className="flex h-screen bg-[#F4F6F8] text-[#111827]">
      <Sidebar />

      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="shrink-0 border-b border-black/[0.06] bg-white/95 backdrop-blur">
          <div className="flex h-[72px] items-center justify-between px-6">
            <div className="flex min-w-0 items-center gap-4">
              <button
                onClick={() => useSidebarStore.getState().toggle()}
                className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-black/[0.06] bg-[#F8FAFC] text-[#4B5563] transition hover:border-black/[0.12] hover:bg-white hover:text-[#111827]"
                title={collapsed ? '展开侧边栏' : '收起侧边栏'}
              >
                <span className="text-base">{collapsed ? '☰' : '←'}</span>
              </button>

              <div className="min-w-0">
                <div className="truncate text-[18px] font-semibold tracking-[-0.02em] text-[#111827]">
                  {current.title}
                </div>
                <div className="truncate text-sm text-[#6B7280]">
                  {current.subtitle}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={reconnect}
                className="inline-flex h-10 items-center gap-2 rounded-full border border-black/[0.06] bg-[#F8FAFC] px-4 text-sm text-[#4B5563] transition hover:border-black/[0.12] hover:bg-white"
                title="重新连接实时通道"
              >
                <span className={`h-2 w-2 rounded-full ${wsInfo.dot}`} />
                <span className={wsInfo.color}>{wsInfo.label}</span>
              </button>
              <NotificationCenter />
            </div>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-hidden">
          <Outlet />
        </div>

        <ToastNotification />
      </main>
    </div>
  )
}
