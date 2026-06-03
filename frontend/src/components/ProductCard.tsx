import { useNavigate } from 'react-router-dom'
import type { ProductItem } from '../api/config'

interface Props {
  product: ProductItem
}

const statusColors: Record<string, string> = {
  passed: 'bg-[#34C759]/10 text-[#34C759]',
  checking: 'bg-[#FF9500]/10 text-[#FF9500]',
  failed: 'bg-[#FF3B30]/10 text-[#FF3B30]',
  pending: 'bg-[#86868B]/10 text-[#86868B]',
}

const statusLabels: Record<string, string> = {
  passed: '合规',
  checking: '待整改',
  failed: '不合规',
  pending: '待检查',
}

const lifecycleLabels: Record<string, string> = {
  concept: '概念',
  design: '设计',
  sourcing: '采购',
  ready: '就绪',
  active: '在售',
  fulfilling: '履约',
  aftersale: '售后',
  end: '下架',
}

export default function ProductCard({ product }: Props) {
  const navigate = useNavigate()

  return (
    <button
      onClick={() => navigate(`/products/${product.id}/chat`)}
      className="w-full text-left p-4 rounded-xl border border-black/6 bg-white hover:border-[#0071E3]/30 hover:shadow-sm transition-all cursor-pointer group"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-sm text-[#1D1D1F] truncate group-hover:text-[#0071E3] transition-colors">
            {product.name}
          </div>
          <div className="text-xs text-[#86868B] mt-0.5">
            {product.target_markets.join(' · ')}
          </div>
        </div>
        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded shrink-0 ${statusColors[product.compliance_status]}`}>
          {statusLabels[product.compliance_status]}
        </span>
      </div>

      {/* Health score bar */}
      <div className="mt-3">
        <div className="flex items-center justify-between text-[11px] text-[#86868B] mb-1">
          <span>健康度</span>
          <span className="font-semibold">{product.health_score ?? 0}%</span>
        </div>
        <div className="h-1.5 bg-[#F5F5F7] rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              (product.health_score ?? 0) >= 80 ? 'bg-[#34C759]' :
              (product.health_score ?? 0) >= 50 ? 'bg-[#FF9500]' : 'bg-[#FF3B30]'
            }`}
            style={{ width: `${product.health_score ?? 0}%` }}
          />
        </div>
      </div>

      {/* Certifications */}
      {(product.certifications ?? []).length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {(product.certifications ?? []).slice(0, 4).map(cert => (
            <span
              key={cert.name}
              className={`text-[10px] px-1.5 py-0.5 rounded ${
                cert.status === 'valid' ? 'bg-[#0071E3]/8 text-[#0071E3]' :
                cert.status === 'expiring' ? 'bg-[#FF9500]/10 text-[#FF9500]' :
                cert.status === 'expired' ? 'bg-[#FF3B30]/10 text-[#FF3B30]' :
                'bg-[#86868B]/10 text-[#86868B]'
              }`}
            >
              {cert.name}
            </span>
          ))}
          {(product.certifications ?? []).length > 4 && (
            <span className="text-[10px] text-[#C7C7CC]">+{(product.certifications ?? []).length - 4}</span>
          )}
        </div>
      )}

      {/* Lifecycle badge */}
      <div className="mt-3 flex items-center gap-2">
        <span className="text-[10px] text-[#C7C7CC] bg-[#F5F5F7] px-2 py-0.5 rounded">
          {lifecycleLabels[product.lifecycle_stage] || product.lifecycle_stage}
        </span>
        {product.hs_code && (
          <span className="text-[10px] text-[#C7C7CC]">HS: {product.hs_code}</span>
        )}
      </div>
    </button>
  )
}
