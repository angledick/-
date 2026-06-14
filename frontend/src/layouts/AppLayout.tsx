import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from '@/components/Sidebar'
import { CommandPalette } from '@/components/CommandPalette'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { MobileTabBar } from '@/components/common/MobileTabBar'
import { SessionProvider } from '@/hooks/useSessions'

export default function AppLayout() {
  const [commandOpen, setCommandOpen] = useState(false)

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      const isCommandK =
        (e.key.toLowerCase() === 'k' || e.code === 'KeyK') &&
        (e.metaKey || e.ctrlKey)

      if (isCommandK) {
        e.preventDefault()
        e.stopPropagation()
        setCommandOpen((open) => !open)
      }
    }

    document.addEventListener('keydown', down, true)
    return () => document.removeEventListener('keydown', down, true)
  }, [])

  return (
    <SessionProvider>
      {/* fixed inset-0：脱离文档流锁定视口，避免内容撑高 documentElement 触发最外层滚动条 */}
      <div className="fixed inset-0 flex overflow-hidden bg-background">
        <Sidebar />
        <main className="flex flex-1 flex-col overflow-hidden pt-14 pb-14 lg:pt-0 lg:pb-0">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
        <MobileTabBar />
        <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} />
      </div>
    </SessionProvider>
  )
}
