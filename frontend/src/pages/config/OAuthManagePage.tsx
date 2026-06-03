import { useState, useEffect, useCallback } from 'react'
import OAuthConfigCard from '../../components/config/OAuthConfigCard'
import OAuthEditModal from '../../components/config/OAuthEditModal'
import ConfigTabs from '../../components/config/ConfigTabs'
import type { OAuthConnection } from '../../api/config'
import { oauthApi } from '../../api/config'

interface ProviderStatus {
  name: string
  icon?: string
  status: string
  connected: number
  total_connections: number
}

const statusMeta: Record<string, { label: string; color: string; bg: string }> = {
  connected:       { label: '已连接', color: 'text-[#34C759]', bg: 'bg-[#34C759]/10' },
  configured:      { label: '待连接', color: 'text-[#FFD60A]', bg: 'bg-[#FFD60A]/10' },
  not_configured:  { label: '未配置', color: 'text-[#86868B]', bg: 'bg-[#F5F5F7]' },
}

export default function OAuthManagePage() {
  const [integrations, setIntegrations] = useState<OAuthConnection[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<OAuthConnection | null>(null)
  const [showNew, setShowNew] = useState(false)

  /** Provider 状态汇总 */
  const [statusSummary, setStatusSummary] = useState<Record<string, ProviderStatus>>({})

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [connData, statusData] = await Promise.all([
        oauthApi.list(),
        oauthApi.getStatusSummary().catch(() => ({ status: {} })),
      ])
      setIntegrations(connData.connections)
      setStatusSummary(statusData.status)
    } catch {
      setIntegrations([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const handleEdit = (conn: OAuthConnection) => setEditing(conn)

  const handleDelete = async (id: string) => {
    if (!window.confirm('确定断开此连接？')) return
    try {
      await oauthApi.delete(id)
      loadData()
    } catch (e) {
      alert(e instanceof Error ? e.message : '删除失败')
    }
  }

  const handleTest = async (id: string) => {
    try {
      const result = await oauthApi.test(id)
      const msg = result.message || result.error || ''
      if (result.ok) {
        alert('连接测试成功')
      } else {
        alert(`测试失败: ${msg}`)
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : '测试失败')
    }
  }

  const summaryEntries = Object.entries(statusSummary)

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <ConfigTabs />

        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-[#1D1D1F]">OAuth / 集成管理</h1>
            <p className="text-sm text-[#86868B] mt-0.5">{integrations.length} 个集成</p>
          </div>
          <button onClick={() => setShowNew(true)} className="px-4 py-2 text-sm font-semibold rounded-lg bg-[#1D1D1F] text-white hover:bg-[#2D2D2F] transition-colors">
            + 新建集成
          </button>
        </div>

        {/* Provider 状态概览 */}
        {summaryEntries.length > 0 && (
          <div className="mb-6 grid grid-cols-4 gap-3">
            {summaryEntries.map(([key, ps]) => {
              const meta = statusMeta[ps.status] || statusMeta.not_configured
              return (
                <div key={key} className="bg-white rounded-xl border border-black/6 p-3 hover:shadow-sm transition-all">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-base">{ps.icon || '🔗'}</span>
                    <span className="text-sm font-semibold text-[#1D1D1F]">{ps.name}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${meta.bg} ${meta.color}`}>
                      {meta.label}
                    </span>
                    <span className="text-[11px] text-[#86868B]">
                      {ps.connected}/{ps.total_connections}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {loading ? (
          <div className="text-center py-16 text-sm text-[#86868B]">加载中...</div>
        ) : integrations.length === 0 ? (
          <div className="text-center py-16 text-sm text-[#86868B]">暂无集成，点击上方按钮创建</div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {integrations.map(o => (
              <OAuthConfigCard
                key={o.id}
                oauth={o}
                onEdit={() => handleEdit(o)}
                onDelete={() => handleDelete(o.id)}
                onTest={() => handleTest(o.id)}
              />
            ))}
          </div>
        )}

        {(editing || showNew) && (
          <OAuthEditModal
            oauth={editing}
            onClose={() => { setEditing(null); setShowNew(false) }}
            onSaved={() => { setEditing(null); setShowNew(false); loadData() }}
          />
        )}
      </div>
    </div>
  )
}
