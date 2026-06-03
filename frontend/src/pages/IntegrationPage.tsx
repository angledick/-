import { useState, useEffect, useCallback } from 'react'
import { oauthApi } from '../api/config'
import type { OAuthConnection } from '../api/config'
import StreamChat from '../components/StreamChat'

// ── Provider 元数据 ──────────────────────────────────────────────────────────

interface ProviderMeta {
  provider: string
  name: string
  icon: string
  color: string
}

const KNOWN_PROVIDERS: Record<string, ProviderMeta> = {
  shopify:  { provider: 'shopify',  name: 'Shopify',        icon: '🛒', color: '#5E8E3E' },
  feishu:   { provider: 'feishu',   name: '飞书',           icon: '📮', color: '#3370FF' },
  dingtalk: { provider: 'dingtalk', name: '钉钉',           icon: '💬', color: '#0089FF' },
  slack:    { provider: 'slack',    name: 'Slack',          icon: '💬', color: '#4A154B' },
  discord:  { provider: 'discord',  name: 'Discord',        icon: '🎮', color: '#5865F2' },
  webhook:  { provider: 'webhook',  name: 'Webhook',        icon: '🔗', color: '#86868B' },
  email:    { provider: 'email',    name: '邮件推送',       icon: '📧', color: '#86868B' },
  notion:   { provider: 'notion',   name: 'Notion',         icon: '📝', color: '#000000' },
  google:   { provider: 'google',   name: 'Google',         icon: '🔍', color: '#4285F4' },
  github:   { provider: 'github',   name: 'GitHub',         icon: '🐙', color: '#181717' },
}

function getProviderMeta(provider: string): ProviderMeta {
  return KNOWN_PROVIDERS[provider] || { provider, name: provider, icon: '🔌', color: '#86868B' }
}

// ── 状态元数据 ────────────────────────────────────────────────────────────────

interface StatusMeta { label: string; color: string; bg: string; pulse?: boolean }

const connStatusMeta: Record<string, StatusMeta> = {
  connected:    { label: '已连接',   color: 'text-[#34C759]', bg: 'bg-[#34C759]/10' },
  disconnected: { label: '未连接',   color: 'text-[#86868B]', bg: 'bg-[#F5F5F7]' },
  connecting:   { label: '连接中',   color: 'text-[#FFD60A]', bg: 'bg-[#FFD60A]/10', pulse: true },
  error:        { label: '错误',     color: 'text-[#FF3B30]', bg: 'bg-[#FF3B30]/10' },
}

const providerStatusMeta: Record<string, StatusMeta> = {
  connected:       { label: '已连接',   color: 'text-[#34C759]', bg: 'bg-[#34C759]/10' },
  configured:      { label: '待连接',   color: 'text-[#FFD60A]', bg: 'bg-[#FFD60A]/10' },
  not_configured:  { label: '未配置',   color: 'text-[#86868B]', bg: 'bg-[#F5F5F7]' },
}

function fmtDate(iso?: string): string {
  if (!iso) return '-'
  try { return new Date(iso).toLocaleDateString('zh-CN') } catch { return iso }
}

// ── Provider 配置提示模板 ─────────────────────────────────────────────────────

function buildConfigPrompt(provider: string, name: string): string {
  const prompts: Record<string, string> = {
    shopify: `帮我配置 Shopify 集成。

请执行以下步骤：
1. 搜索 Shopify API 集成文档，确认最新 OAuth 流程和所需参数
2. 引导我完成 Shopify OAuth 授权：
   - 需要 API 密钥 (API Key)
   - 需要 API 密钥 (API Secret Key)
   - 需要商店域名 (myshopify.com)
   - 需要 Scopes 权限范围
3. 配置完成后测试连接有效性
4. 保存配置

请开始搜索 Shopify 集成文档，确认当前推荐的最佳实践。`,
    feishu: `帮我配置 飞书 机器人集成。

请执行以下步骤：
1. 搜索飞书开放平台文档，确认最新集成方式
2. 引导我完成飞书应用配置：
   - 需要 App ID
   - 需要 App Secret
   - 需要获取 Tenant Access Token
   - 配置 Webhook URL 用于消息推送
3. 配置完成后测试连接
4. 保存配置

请开始搜索飞书机器人集成文档。`,
    dingtalk: `帮我配置 钉钉 机器人集成。

请执行以下步骤：
1. 搜索钉钉开放平台文档，确认最新集成方式
2. 引导我完成钉钉机器人配置：
   - 需要 Client ID (AppKey)
   - 需要 Client Secret (AppSecret)
   - 需要 CustomKey / 机器人 Webhook URL
3. 配置完成后测试连接
4. 保存配置

请开始搜索钉钉机器人开发文档。`,
    slack: `帮我配置 Slack 集成。

请执行以下步骤：
1. 搜索 Slack API 文档，确认最新集成方式
2. 引导我完成 Slack App 配置：
   - 创建 Slack App
   - 配置 Bot Token Scopes
   - 获取 Bot User OAuth Token
   - 配置 Webhook URL
3. 测试连接有效性
4. 保存配置

请开始搜索 Slack API 集成文档。`,
    google: `帮我配置 Google 服务集成。

请执行以下步骤：
1. 搜索 Google API 文档
2. 引导我完成 Google Cloud 项目配置：
   - 创建服务账号
   - 获取 API Key 或 OAuth 2.0 凭据
   - 配置所需的 API 范围
3. 测试连接
4. 保存配置`,
    github: `帮我配置 GitHub 集成。

请执行以下步骤：
1. 搜索 GitHub API 集成文档
2. 引导我完成 GitHub App 或 Personal Access Token 配置：
   - 需要 Token 权限范围
   - 配置 Webhook（可选）
3. 测试连接
4. 保存配置`,
    webhook: `帮我配置 Webhook 集成。

请：
1. 告知需要接收的事件类型和格式
2. 提供 Webhook URL 和签名密钥配置
3. 我可以发送测试事件验证配置
4. 保存配置`,
  }

  return prompts[provider] || `帮我配置 ${name} (${provider}) 集成。\n\n请搜索该平台的集成文档，了解配置所需参数，然后引导我逐步完成配置，最后测试并保存。`
}

// ── 主页面 ────────────────────────────────────────────────────────────────────

export default function IntegrationPage() {
  const [connections, setConnections] = useState<OAuthConnection[]>([])
  const [providerStatus, setProviderStatus] = useState<Record<string, { name: string; icon?: string; status: string; connected: number; total_connections: number }>>({})
  const [loading, setLoading] = useState(true)
  const [testingId, setTestingId] = useState<string | null>(null)
  const [testResults, setTestResults] = useState<Record<string, { ok: boolean; message?: string }>>({})

  // 对话配置状态
  const [chatKey, setChatKey] = useState(0)
  const [initialMessage, setInitialMessage] = useState<string | null>(null)
  const [configuringProvider, setConfiguringProvider] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [connData, statusData] = await Promise.all([
        oauthApi.list(),
        oauthApi.getStatusSummary().catch(() => ({ status: {} })),
      ])
      setConnections(connData.connections)
      setProviderStatus(statusData.status || {})
    } catch {
      setConnections([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const handleTest = async (id: string) => {
    setTestingId(id)
    setTestResults(prev => ({ ...prev, [id]: undefined as unknown as { ok: boolean; message?: string } }))
    try {
      const result = await oauthApi.test(id)
      setTestResults(prev => ({ ...prev, [id]: result }))
    } catch (e) {
      setTestResults(prev => ({ ...prev, [id]: { ok: false, message: e instanceof Error ? e.message : '测试失败' } }))
    } finally {
      setTestingId(null)
    }
  }

  const handleDelete = async (id: string) => {
    if (!window.confirm('确定断开此连接？')) return
    try {
      await oauthApi.delete(id)
      loadData()
    } catch (e) {
      alert(e instanceof Error ? e.message : '断开失败')
    }
  }

  const handleConfigure = (provider: string, name: string) => {
    setConfiguringProvider(provider)
    setChatKey(k => k + 1)
    setInitialMessage(buildConfigPrompt(provider, name))
  }

  const handleNewCustom = () => {
    setConfiguringProvider(null)
    setChatKey(k => k + 1)
    setInitialMessage('我需要配置一个新的第三方系统集成。请搜索文档了解配置方式，引导我完成配置并保存。')
  }

  const providerEntries = Object.entries(providerStatus)
  const statusCount = {
    connected: connections.filter(c => c.status === 'connected').length,
    error: connections.filter(c => c.status === 'error').length,
    disconnected: connections.filter(c => c.status === 'disconnected').length,
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* ── 顶部：Provider 概览 + 连接列表 ── */}
      <div className="shrink-0 bg-white border-b border-black/6">
        <div className="max-w-5xl mx-auto px-6 py-4">
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <div>
              <h1 className="text-lg font-semibold text-[#1D1D1F]">集成管理 · 对话式配置工作台</h1>
              <p className="text-sm text-[#86868B] mt-0.5">
                点击 Provider 卡片通过对话完成配置 · 共 {connections.length} 个连接
                {statusCount.error > 0 && (
                  <span className="ml-2 text-[#FF3B30]">· {statusCount.error} 个异常</span>
                )}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-[#86868B]">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#34C759] mr-1" />
                {statusCount.connected} 已连接
                {statusCount.error > 0 && (
                  <><span className="inline-block w-1.5 h-1.5 rounded-full bg-[#FF3B30] ml-3 mr-1" />
                  {statusCount.error} 异常</>
                )}
              </span>
              <button
                onClick={loadData}
                className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-[#F5F5F7] text-[#1D1D1F] hover:bg-[#E5E5EA] transition-colors"
              >
                刷新
              </button>
              <button
                onClick={handleNewCustom}
                className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-[#1D1D1F] text-white hover:bg-[#2D2D2F] transition-colors"
              >
                + 自定义集成
              </button>
            </div>
          </div>

          {/* Provider 状态卡片（点击触发对话配置） */}
          {providerEntries.length > 0 && (
            <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
              {providerEntries.map(([key, ps]) => {
                const meta = providerStatusMeta[ps.status] || providerStatusMeta.not_configured
                const pm = getProviderMeta(key)
                const isConfiguring = configuringProvider === key
                return (
                  <button
                    key={key}
                    onClick={() => handleConfigure(key, ps.name || pm.name)}
                    className={`shrink-0 bg-white rounded-xl border p-3 text-left transition-all hover:shadow-md min-w-[140px] ${
                      isConfiguring ? 'border-[#1D1D1F] ring-1 ring-[#1D1D1F]/10' : 'border-black/6'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1.5">
                      <div
                        className="w-7 h-7 rounded-lg flex items-center justify-center text-sm shrink-0"
                        style={{ backgroundColor: pm.color + '15' }}
                      >
                        {ps.icon || pm.icon}
                      </div>
                      <span className="text-sm font-semibold text-[#1D1D1F] truncate">{ps.name || pm.name}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${meta.bg} ${meta.color}`}>
                        {meta.label}
                      </span>
                      <span className="text-[10px] text-[#86868B]">
                        {ps.connected}/{ps.total_connections}
                      </span>
                    </div>
                  </button>
                )
              })}
            </div>
          )}

          {/* 已配置连接列表（折叠） */}
          {loading ? (
            <div className="text-center py-4 text-sm text-[#86868B]">加载中...</div>
          ) : connections.length > 0 && (
            <div className="mt-3 bg-[#FAFAFA] rounded-xl border border-black/6 overflow-hidden">
              <details className="group" open>
                <summary className="px-3.5 py-2.5 flex items-center justify-between cursor-pointer hover:bg-[#F5F5F7]/50 transition-colors text-sm font-semibold text-[#1D1D1F] list-none">
                  <span>已配置的连接 ({connections.length})</span>
                  <span className="text-[11px] text-[#C7C7CC] group-open:rotate-180 transition-transform">▾</span>
                </summary>
                <div className="divide-y divide-black/6">
                  {connections.map(conn => {
                    const pm = getProviderMeta(conn.provider)
                    const sm = connStatusMeta[conn.status] || connStatusMeta.disconnected
                    const testResult = testResults[conn.id]
                    return (
                      <div key={conn.id} className="px-3.5 py-2.5 flex items-center gap-3 hover:bg-[#F5F5F7]/50 transition-colors">
                        <div
                          className="w-7 h-7 rounded-lg flex items-center justify-center text-xs shrink-0"
                          style={{ backgroundColor: pm.color + '12' }}
                        >
                          {pm.icon}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold text-[#1D1D1F] truncate">{conn.label || conn.provider}</span>
                            <span className="text-[10px] text-[#86868B] shrink-0">{pm.name}</span>
                            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${sm.bg} ${sm.color} ${sm.pulse ? 'animate-pulse' : ''}`}>
                              {sm.label}
                            </span>
                          </div>
                          {conn.last_error && (
                            <div className="text-[10px] text-[#FF3B30] mt-0.5 line-clamp-1">{conn.last_error}</div>
                          )}
                          {testResult && (
                            <div className={`text-[10px] mt-0.5 ${testResult.ok ? 'text-[#34C759]' : 'text-[#FF3B30]'}`}>
                              {testResult.ok ? '测试成功' : `失败: ${testResult.message || ''}`}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <button
                            onClick={() => handleTest(conn.id)}
                            disabled={testingId === conn.id}
                            className="px-2 py-1 text-[10px] font-medium rounded-md bg-white border border-black/6 hover:bg-[#F5F5F7] text-[#1D1D1F] transition-colors disabled:opacity-50"
                          >
                            {testingId === conn.id ? '...' : '测试'}
                          </button>
                          <button
                            onClick={() => handleDelete(conn.id)}
                            className="px-2 py-1 text-[10px] font-medium rounded-md bg-[#FF3B30]/5 hover:bg-[#FF3B30]/10 text-[#FF3B30] transition-colors"
                          >
                            断开
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </details>
            </div>
          )}

          {/* 快捷提示 */}
          {!configuringProvider && (
            <div className="mt-2 flex items-center gap-4 text-[10px] text-[#86868B]">
              <span>💡 点击上方卡片通过对话完成配置</span>
              <span>🔍 AI 将搜索文档获取最新参数</span>
              <span>🌐 支持浏览器 OAuth 授权</span>
              <span>/ 命令支持 CLI 操作</span>
            </div>
          )}
          {configuringProvider && (
            <div className="mt-2 text-[11px] text-[#0071E3] bg-[#0071E3]/5 px-3 py-1.5 rounded-lg">
              正在配置 {getProviderMeta(configuringProvider).name} · 与 AI 对话完成配置流程
            </div>
          )}
        </div>
      </div>

      {/* ── 底部：对话式配置工作台 ── */}
      <div className="flex-1 min-h-0">
        <StreamChat
          key={chatKey}
          initialMessage={initialMessage}
          onInitialMessageConsumed={() => setInitialMessage(null)}
          title="集成配置工作台"
          subtitle="对话式第三方系统接入 · AI 自动搜索文档 / 引导 OAuth / 测试连接"
          placeholder="描述要集成的第三方系统，AI 将引导完成全部配置..."
        />
      </div>
    </div>
  )
}
