import { useState, useEffect, useCallback } from 'react'
import ProductCard from '../components/ProductCard'
import { productsApi, type ProductItem } from '../api/config'
import type { ProductLifecycle } from '../types'

const LIFECYCLE_GROUPS: { key: ProductLifecycle; label: string }[] = [
  { key: 'concept', label: '概念' },
  { key: 'design', label: '设计' },
  { key: 'sourcing', label: '采购' },
  { key: 'ready', label: '就绪' },
  { key: 'active', label: '在售' },
  { key: 'fulfilling', label: '履约' },
  { key: 'aftersale', label: '售后' },
  { key: 'end', label: '下架' },
]

export default function ProductListPage() {
  const [products, setProducts] = useState<ProductItem[]>([])
  const [loading, setLoading] = useState(true)

  const loadProducts = useCallback(async () => {
    setLoading(true)
    try {
      const data = await productsApi.list()
      setProducts(data)
    } catch {
      setProducts([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadProducts() }, [loadProducts])

  const grouped = LIFECYCLE_GROUPS
    .map(g => ({ ...g, items: products.filter(p => p.lifecycle_stage === g.key) }))
    .filter(g => g.items.length > 0)

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Title */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-[#1D1D1F]">产品合规</h1>
            <p className="text-sm text-[#86868B] mt-1">
              {products.length} 个产品 · 点击卡片进入产品对话
            </p>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-20 text-sm text-[#86868B]">加载中...</div>
        ) : products.length === 0 ? (
          <div className="text-center py-20">
            <div className="text-5xl mb-3">📦</div>
            <div className="text-base font-semibold text-[#1D1D1F] mb-1">暂无产品</div>
            <div className="text-sm text-[#86868B]">通过对话添加产品开始合规检查</div>
          </div>
        ) : (
          <div className="space-y-8">
            {grouped.map(group => (
              <div key={group.key}>
                <div className="flex items-center gap-2 mb-3">
                  <h2 className="text-sm font-semibold text-[#1D1D1F]">{group.label}</h2>
                  <span className="text-xs text-[#C7C7CC]">{group.items.length} 个</span>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  {group.items.map(p => (
                    <ProductCard key={p.id} product={p} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
