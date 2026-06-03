import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import NotificationCenter from './NotificationCenter'
import ToastNotification from './ToastNotification'
import { useWebSocketContext } from '../context/WebSocketContext'
import { useSidebarStore } from '../context/AppStore'

const wsStatusConfig: Record<string, { label: string; color: string }> = {
  connected: { label: '已连接', color: 'text-[#34C759]' },
  connecting: { label: '连接中...', color: 'text-[#FF9500]' },
  disconnected: { label: '已断开', color: 'text-[#86868B]' },
  error: { label: '连接错误', color: 'text-[#FF3B30]' },
}

export default function Layout() {
  const { status: wsStatus, reconnect } = useWebSocketContext()
  const collapsed = useSidebarStore(s => s.collapsed)

  const wsInfo = wsStatusConfig[wsStatus] || wsStatusConfig.disconnected

  return (
    <div className="flex h-screen bg-[#F5F5F7]">
      <Sidebar />
      <main className="flex-1 overflow-hidden flex flex-col">
        {/* Top status bar */}
        <header className="shrink-0 h-8 px-4 flex items-center justify-between bg-white border-b border-black/6">
          <div className="flex items-center gap-2">
            <button
              onClick={() => useSidebarStore.getState().toggle()}
              className="text-xs text-[#86868B] hover:text-[#1D1D1F] transition-colors"
              title={collapsed ? '展开侧边栏' : '折叠侧边栏'}
            >
              {collapsed ? '☰' : '◁'}
            </button>
          </div>
          <div className="flex items-center gap-2">
            <NotificationCenter />
            <button
              onClick={reconnect}
              className={`text-[11px] flex items-center gap-1.5 ${wsInfo.color} hover:underline`}
              title="点击重新连接"
            >
              <span>●</span>
              <span>{wsInfo.label}</span>
            </button>
          </div>
        </header>

        {/* Page content */}
        <div className="flex-1 overflow-hidden">
          <Outlet />
        </div>

        {/* Toast notifications (fixed overlay) */}
        <ToastNotification />
      </main>
    </div>
  )
}
