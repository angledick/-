import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'

import AppLayout from '@/layouts/AppLayout'
import AuthLayout from '@/layouts/AuthLayout'
import { RequireAuth, RequireAdmin, PublicOnly } from '@/router/guards'

// 首屏关键页面 - 直接导入
import Dashboard from '@/pages/Dashboard'
import ChatPage from '@/pages/ChatPage'

// 二级页面 - 懒加载（减小首屏主 Bundle）
const CompliancePage = lazy(() => import('@/pages/CompliancePage'))
const SystemCompliancePage = lazy(() => import('@/pages/SystemCompliancePage'))
const ProductCompliancePage = lazy(() => import('@/pages/ProductCompliancePage'))

// 次要页面 - 懒加载
const LandingPage = lazy(() => import('@/pages/LandingPage'))
const LoginPage = lazy(() => import('@/pages/LoginPage'))
const RegisterPage = lazy(() => import('@/pages/RegisterPage'))
const KnowledgePage = lazy(() => import('@/pages/KnowledgePage'))
const RiskCenter = lazy(() => import('@/pages/RiskCenter'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const NewsMonitorPage = lazy(() => import('@/pages/NewsMonitorPage'))
const NotifyConfigPage = lazy(() => import('@/pages/NotifyConfigPage'))
const OrdersPage = lazy(() => import('@/pages/OrdersPage'))
const LogisticsTrackingPage = lazy(() => import('@/pages/LogisticsTrackingPage'))
const NLStorePage = lazy(() => import('@/pages/NLStorePage'))
const IntegrationPage = lazy(() => import('@/pages/IntegrationPage'))
const SchedulerConfigPage = lazy(() => import('@/pages/SchedulerConfigPage'))
const ShopifyCallbackPage = lazy(() => import('@/pages/ShopifyCallbackPage'))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'))

// Admin 配置页 - 懒加载
const AgentConfigPage = lazy(() => import('@/pages/AgentConfigPage'))
const ModelConfigPage = lazy(() => import('@/pages/ModelConfigPage'))
const UserManagePage = lazy(() => import('@/pages/UserManagePage'))

// 加载占位组件
const PageLoader = () => (
  <div className="flex items-center justify-center h-full">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
  </div>
)

// 懒加载包装器
const Lazy = ({ children }: { children: React.ReactNode }) => (
  <Suspense fallback={<PageLoader />}>{children}</Suspense>
)

/**
 * 路由表
 * ── /             marketing LandingPage（公开）
 * ── /auth/login   PublicOnly + AuthLayout → LoginPage
 * ── /auth/signup  PublicOnly + AuthLayout → RegisterPage
 * ── /login        legacy redirect → /auth/login
 * ── /register     legacy redirect → /auth/signup
 * ── /app/*        RequireAuth + AppLayout
 * ── /app/monitor  风险监控规范路由（/app/risk-center 保留重定向）
 * ── /app/agent-config 等  RequireAdmin
 * ── *             NotFoundPage（友好 404）
 */

export const router = createBrowserRouter([
  {
    path: '/',
    element: (
      <Lazy>
        <LandingPage />
      </Lazy>
    ),
  },
  {
    path: '/login',
    element: <Navigate to="/auth/login" replace />,
  },
  {
    path: '/register',
    element: <Navigate to="/auth/signup" replace />,
  },
  {
    path: '/auth',
    element: (
      <PublicOnly>
        <AuthLayout />
      </PublicOnly>
    ),
    children: [
      { index: true, element: <Navigate to="/auth/login" replace /> },
      {
        path: 'login',
        element: (
          <Lazy>
            <LoginPage />
          </Lazy>
        ),
      },
      {
        path: 'signup',
        element: (
          <Lazy>
            <RegisterPage />
          </Lazy>
        ),
      },
    ],
  },
  {
    path: '/app',
    element: (
      <RequireAuth>
        <AppLayout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Navigate to="/app/dashboard" replace /> },
      { path: 'dashboard', element: <Dashboard /> },
      { path: 'chat', element: <ChatPage /> },
      { path: 'products', element: <Lazy><ProductCompliancePage /></Lazy> },
      { path: 'products/:productId/chat', element: <ChatPage /> },
      { path: 'compliance', element: <Lazy><CompliancePage /></Lazy> },
      { path: 'compliance/system', element: <Lazy><SystemCompliancePage /></Lazy> },
      {
        path: 'knowledge',
        element: (
          <div className="flex-1 overflow-auto">
            <Lazy>
              <KnowledgePage />
            </Lazy>
          </div>
        ),
      },
      {
        path: 'monitor',
        element: (
          <div className="flex-1 overflow-auto">
            <Lazy>
              <RiskCenter />
            </Lazy>
          </div>
        ),
      },
      { path: 'risk-center', element: <Navigate to="/app/monitor" replace /> },
      { path: 'settings', element: <Navigate to="/app/settings/profile" replace /> },
      {
        path: 'settings/profile',
        element: (
          <div className="flex-1 overflow-auto">
            <Lazy>
              <SettingsPage />
            </Lazy>
          </div>
        ),
      },
      {
        path: 'news-monitor',
        element: (
          <div className="flex-1 overflow-auto">
            <Lazy>
              <NewsMonitorPage />
            </Lazy>
          </div>
        ),
      },
      {
        path: 'notify-config',
        element: (
          <div className="flex-1 overflow-auto">
            <Lazy>
              <NotifyConfigPage />
            </Lazy>
          </div>
        ),
      },
      {
        path: 'orders',
        element: (
          <div className="flex-1 overflow-auto">
            <Lazy>
              <OrdersPage />
            </Lazy>
          </div>
        ),
      },
      {
        path: 'logistics',
        element: (
          <div className="flex-1 overflow-auto">
            <Lazy>
              <LogisticsTrackingPage />
            </Lazy>
          </div>
        ),
      },
      {
        path: 'nl-store',
        element: (
          <div className="flex-1 overflow-auto">
            <Lazy>
              <NLStorePage />
            </Lazy>
          </div>
        ),
      },
      {
        element: <RequireAdmin />,
        children: [
          {
            path: 'agent-config',
            element: (
              <Lazy>
                <AgentConfigPage />
              </Lazy>
            ),
          },
          {
            path: 'model-config',
            element: (
              <Lazy>
                <ModelConfigPage />
              </Lazy>
            ),
          },
          {
            path: 'integrations',
            element: (
              <div className="flex-1 overflow-auto">
                <Lazy>
                  <IntegrationPage />
                </Lazy>
              </div>
            ),
          },
          {
            path: 'scheduler',
            element: (
              <div className="flex-1 overflow-auto">
                <Lazy>
                  <SchedulerConfigPage />
                </Lazy>
              </div>
            ),
          },
          {
            path: 'user-manage',
            element: (
              <div className="flex-1 overflow-auto">
                <Lazy>
                  <UserManagePage />
                </Lazy>
              </div>
            ),
          },
        ],
      },
    ],
  },
  {
    path: '/shopify/callback',
    element: (
      <Lazy>
        <ShopifyCallbackPage />
      </Lazy>
    ),
  },
  {
    path: '*',
    element: (
      <Lazy>
        <NotFoundPage />
      </Lazy>
    ),
  },
])
