import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { WebSocketProvider } from './context/WebSocketContext'
import { NotificationProvider } from './context/NotificationContext'
import { useAgentConfigStore } from './context/AppStore'
import { useEffect } from 'react'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import OverviewPage from './pages/OverviewPage'
import SystemCompliancePage from './pages/SystemCompliancePage'
import ProductListPage from './pages/ProductListPage'
import ProductChatPage from './pages/ProductChatPage'
import ChatWorkspacePage from './pages/ChatWorkspacePage'
import KnowledgePage from './pages/KnowledgePage'
import UserManagePage from './pages/UserManagePage'
import RiskCenter from './pages/RiskCenter'
import ProductLifecyclePage from './pages/ProductLifecyclePage'
import LogisticsTrackingPage from './pages/LogisticsTrackingPage'
import MemoryTreePage from './pages/MemoryTreePage'
import MetricsPage from './pages/MetricsPage'
import AgentMonitorPage from './pages/AgentMonitorPage'
import AgentConfigPage from './pages/config/AgentConfigPage'
import SkillsManagePage from './pages/config/SkillsManagePage'
import ToolsManagePage from './pages/config/ToolsManagePage'
import OAuthManagePage from './pages/config/OAuthManagePage'
import ModelConfigPage from './pages/config/ModelConfigPage'
import SchedulerConfigPage from './pages/config/SchedulerConfigPage'
import IntegrationPage from './pages/IntegrationPage'

/** 加载 Agent 配置 */
function ConfigLoader({ children }: { children: React.ReactNode }) {
  const loadConfig = useAgentConfigStore(s => s.loadConfig)
  useEffect(() => { loadConfig() }, [loadConfig])
  return <>{children}</>
}

function AppRoutes() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-[#F5F5F7]">
        <div className="text-sm text-[#86868B]">加载中...</div>
      </div>
    )
  }

  if (!user) {
    return <LoginPage />
  }

  return (
    <WebSocketProvider userId={user.id}>
      <NotificationProvider>
        <ConfigLoader>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<OverviewPage />} />
              <Route path="compliance/system" element={<SystemCompliancePage />} />
              <Route path="products" element={<ProductListPage />} />
              <Route path="products/:id/chat" element={<ProductChatPage />} />
              <Route path="chat" element={<ChatWorkspacePage />} />
              <Route path="knowledge" element={<KnowledgePage />} />
              <Route path="config" element={<Navigate to="/config/agents" replace />} />
              <Route path="config/agents" element={<AgentConfigPage />} />
              <Route path="config/skills" element={<SkillsManagePage />} />
              <Route path="config/tools" element={<ToolsManagePage />} />
              <Route path="config/oauth" element={<OAuthManagePage />} />
              <Route path="config/models" element={<ModelConfigPage />} />
              <Route path="config/scheduler" element={<SchedulerConfigPage />} />
              <Route path="config/integrations" element={<IntegrationPage />} />
              <Route path="memory" element={<MemoryTreePage />} />
              <Route path="metrics" element={<MetricsPage />} />
              <Route path="agents" element={<AgentMonitorPage />} />
              <Route path="system/users" element={<UserManagePage />} />
              <Route path="system/risk" element={<RiskCenter />} />
              <Route path="products/lifecycle" element={<ProductLifecyclePage />} />
              <Route path="logistics/track" element={<LogisticsTrackingPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </ConfigLoader>
      </NotificationProvider>
    </WebSocketProvider>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}
