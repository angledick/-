import { useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect, useCallback } from 'react'
import StreamChat from '../components/StreamChat'
import EventTimeline from '../components/EventTimeline'
import { productsApi, type ProductItem, type ProductEvent } from '../api/config'
import { useNotificationContext } from '../context/NotificationContext'

const certStatusLabel: Record<string, string> = {
  valid: '有效', expiring: '即将到期', expired: '已过期', missing: '缺失',
}
const certStatusColor: Record<string, string> = {
  valid: 'text-[#34C759]', expiring: 'text-[#FF9500]', expired: 'text-[#FF3B30]', missing: 'text-[#86868B]',
}

export default function ProductChatPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [product, setProduct] = useState<ProductItem | null>(null)
  const [events, setEvents] = useState<ProductEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [rechecking, setRechecking] = useState(false)
  const [showCertDetail, setShowCertDetail] = useState(false)
  const { addToast } = useNotificationContext()

  const loadData = useCallback(async () => {
    if (!id) return
    setLoading(true)
    try {
      const [prod, evts] = await Promise.all([
        productsApi.get(id),
        productsApi.getEvents(id).catch(() => [] as ProductEvent[]),
      ])
      setProduct(prod)
      setEvents(evts)
    } catch {
      setProduct(null)
      setEvents([])
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { loadData() }, [loadData])

  const handleRecheck = useCallback(async () => {
    if (!id) return
    setRechecking(true)
    try {
      const fresh = await productsApi.get(id)
      setProduct(fresh)
      addToast({ severity: 'low', title: '合规检查完成', message: `${fresh.name} · 状态: ${fresh.compliance_status}` })
    } catch {
      addToast({ severity: 'high', title: '合规检查失败', message: '后端不可用，请稍后重试' })
    } finally {
      setRechecking(false)
    }
  }, [id, addToast])

  const handleExportReport = useCallback(() => {
    if (!product) return
    const rows = [
      ['产品名称', product.name],
      ['HS编码', product.hs_code || '-'],
      ['供应商', product.vendor || '-'],
      ['目标市场', product.target_markets.join(', ')],
      ['合规状态', product.compliance_status],
      ['生命周期', product.lifecycle_stage],
      ['健康度', `${product.health_score ?? 0}%`],
      ['认证', (product.certifications ?? []).map(c => `${c.name}: ${c.status}`).join('; ')],
    ]
    const csv = rows.map(r => r.map(v => `"${v}"`).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${product.name}_合规报告_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
    addToast({ severity: 'low', title: '报告已导出', message: `${product.name}_合规报告.csv` })
  }, [product, addToast])

  if (loading) {
    return <div className="flex-1 flex items-center justify-center text-sm text-[#86868B]">加载中...</div>
  }

  if (!product) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-[#86868B]">
        <div className="text-5xl mb-3">📦</div>
        <div className="text-base font-semibold text-[#1D1D1F] mb-1">产品未找到</div>
        <button onClick={() => navigate('/products')} className="text-sm text-[#0071E3] hover:underline mt-2">
          ← 返回产品列表
        </button>
      </div>
    )
  }

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Left: Product Info Panel */}
      <div className="w-64 shrink-0 border-r border-black/6 bg-white overflow-y-auto p-4">
        {/* Back button */}
        <button
          onClick={() => navigate('/products')}
          className="text-xs text-[#0071E3] mb-4 hover:underline"
        >
          ← 返回产品列表
        </button>

        <h2 className="font-semibold text-sm text-[#1D1D1F] mb-1">{product.name}</h2>
        <div className="text-xs text-[#86868B] mb-4">{product.target_markets.join(' · ')}</div>

        {/* HS Code */}
        {product.hs_code && (
          <div className="mb-3">
            <div className="text-[10px] font-semibold text-[#86868B] uppercase tracking-wider mb-1">HS编码</div>
            <div className="text-sm font-mono text-[#1D1D1F]">{product.hs_code}</div>
          </div>
        )}

        {/* Vendor */}
        {product.vendor && (
          <div className="mb-3">
            <div className="text-[10px] font-semibold text-[#86868B] uppercase tracking-wider mb-1">供应商</div>
            <div className="text-sm text-[#1D1D1F]">{product.vendor}</div>
          </div>
        )}

        {/* Health Score */}
        <div className="mb-3">
          <div className="text-[10px] font-semibold text-[#86868B] uppercase tracking-wider mb-1">健康度</div>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-[#F5F5F7] rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${(product.health_score ?? 0) >= 80 ? 'bg-[#34C759]' : (product.health_score ?? 0) >= 50 ? 'bg-[#FF9500]' : 'bg-[#FF3B30]'}`} style={{ width: `${product.health_score ?? 0}%` }} />
            </div>
            <span className="text-sm font-semibold text-[#1D1D1F]">{product.health_score ?? 0}%</span>
          </div>
        </div>

        {/* Certifications */}
        {(product.certifications ?? []).length > 0 && (
          <div className="mb-4">
            <div className="text-[10px] font-semibold text-[#86868B] uppercase tracking-wider mb-1">
              认证状态
              <button
                onClick={() => setShowCertDetail(!showCertDetail)}
                className="ml-1 text-[10px] text-[#0071E3] hover:underline"
              >
                {showCertDetail ? '收起' : '详情'}
              </button>
            </div>
            <div className="space-y-1.5">
              {(product.certifications ?? []).slice(0, showCertDetail ? undefined : 3).map(c => (
                <div key={c.name} className="flex items-center justify-between text-sm">
                  <span className="text-[#1D1D1F]">{c.name}</span>
                  <span className={`text-xs ${certStatusColor[c.status] || 'text-[#86868B]'}`}>{certStatusLabel[c.status] || c.status}</span>
                </div>
              ))}
              {!showCertDetail && (product.certifications ?? []).length > 3 && (
                <button
                  onClick={() => setShowCertDetail(true)}
                  className="text-xs text-[#0071E3] hover:underline"
                >
                  +{(product.certifications ?? []).length - 3} 个更多
                </button>
              )}
            </div>
          </div>
        )}

        {/* Event Timeline */}
        <EventTimeline events={events} title="事件时间线" />
      </div>

      {/* Center: StreamChat */}
      <div className="flex-1 min-w-0">
        <StreamChat
          title={product.name}
          subtitle={`${product.target_markets.join(' · ')} · 产品合规对话`}
          placeholder={`询问关于 ${product.name} 的合规问题...`}
          sessionId={`product_${product.id}`}
        />
      </div>

      {/* Right: Compliance Panel */}
      <div className="w-56 shrink-0 border-l border-black/6 bg-white overflow-y-auto p-4">
        <div className="text-[10px] font-semibold text-[#86868B] uppercase tracking-wider mb-3">合规面板</div>

        <div className="space-y-3">
          <div className="p-2.5 rounded-lg bg-[#F5F5F7]">
            <div className="text-[11px] text-[#86868B] mb-0.5">合规状态</div>
            <div className={`text-sm font-semibold ${
              product.compliance_status === 'passed' ? 'text-[#34C759]' :
              product.compliance_status === 'checking' ? 'text-[#FF9500]' :
              product.compliance_status === 'failed' ? 'text-[#FF3B30]' : 'text-[#86868B]'
            }`}>
              {product.compliance_status === 'passed' ? '合规' :
               product.compliance_status === 'checking' ? '待整改' :
               product.compliance_status === 'failed' ? '不合规' : '待检查'}
            </div>
          </div>

          <div className="p-2.5 rounded-lg bg-[#F5F5F7]">
            <div className="text-[11px] text-[#86868B] mb-0.5">生命周期</div>
            <div className="text-sm font-medium text-[#1D1D1F]">
              {({ concept: '概念', design: '设计', sourcing: '采购', ready: '就绪', active: '在售', fulfilling: '履约', aftersale: '售后', end: '下架' } as Record<string, string>)[product.lifecycle_stage] || product.lifecycle_stage}
            </div>
          </div>

          {/* Quick actions */}
          <div className="pt-2 border-t border-black/6">
            <div className="text-[10px] font-semibold text-[#86868B] uppercase tracking-wider mb-2">快捷操作</div>
            <div className="space-y-1.5">
              <button
                onClick={handleRecheck}
                disabled={rechecking}
                className="w-full text-left text-xs px-2.5 py-2 rounded-md bg-[#F5F5F7] hover:bg-[#E5E5EA] text-[#1D1D1F] transition-colors disabled:opacity-50"
              >
                {rechecking ? '检查中...' : '重新检查合规'}
              </button>
              <button
                onClick={() => setShowCertDetail(v => !v)}
                className="w-full text-left text-xs px-2.5 py-2 rounded-md bg-[#F5F5F7] hover:bg-[#E5E5EA] text-[#1D1D1F] transition-colors"
              >
                {showCertDetail ? '收起认证' : '查看认证详情'}
              </button>
              <button
                onClick={handleExportReport}
                className="w-full text-left text-xs px-2.5 py-2 rounded-md bg-[#F5F5F7] hover:bg-[#E5E5EA] text-[#1D1D1F] transition-colors"
              >
                导出合规报告
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
