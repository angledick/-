/**
 * 店铺合规 — Shopify 店铺总览
 *
 * 显示已连接店铺列表 + 各店铺产品数 + 快速合规检查入口
 */
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Search, ShoppingCart } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  useShopifyProducts,
  useShopifyShops,
} from '@/hooks/queries/useShopify'
import { cn } from '@/lib/utils'

export default function SystemCompliancePage() {
  const navigate = useNavigate()
  const {
    data: shops,
    isLoading: shopsLoading,
    isError: shopsError,
    error: shopsErr,
    refetch: refetchShops,
  } = useShopifyShops()

  return (
    <div className="h-full overflow-y-auto bg-background">
      <div className="border-b border-border/60">
        <div className="mx-auto max-w-[1400px] px-6 py-7 sm:px-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h1 className="text-[28px] font-semibold tracking-tight">店铺合规</h1>
              <p className="mt-1 max-w-2xl text-[14px] leading-6 text-muted-foreground">
                已连接 Shopify 店铺列表 · 对店铺产品批量合规检查
              </p>
            </div>
            <Button className="h-9 text-[13px]" onClick={() => navigate('/app/products')}>
              产品合规 <ArrowRight className="ml-2 size-4" />
            </Button>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-[1400px] space-y-6 px-6 py-8 sm:px-8">
        {/* Loading */}
        {shopsLoading && (
          <div className="flex items-center justify-center py-24 text-sm text-muted-foreground">
            <LoaderCircle className="mr-2 size-4 animate-spin" />
            加载店铺列表…
          </div>
        )}

        {/* Error */}
        {shopsError && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            加载失败：{shopsErr instanceof Error ? shopsErr.message : '未知错误'}
            <Button
              variant="link"
              size="sm"
              className="ml-2 h-auto p-0 text-destructive underline"
              onClick={() => refetchShops()}
            >
              重试
            </Button>
          </div>
        )}

        {/* Empty */}
        {!shopsLoading && !shopsError && shops?.length === 0 && (
          <div className="rounded-lg border border-dashed border-border bg-muted/30 p-12 text-center">
            <ShoppingCart className="mx-auto size-10 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">还没有连接 Shopify 店铺</h3>
            <p className="text-sm text-muted-foreground mb-6 max-w-md mx-auto">
              前往「产品合规」页面连接你的 Shopify 店铺，系统将自动拉取产品并执行合规检查。
            </p>
            <Button onClick={() => navigate('/app/products')}>
              前往产品合规
            </Button>
          </div>
        )}

        {/* Shop cards */}
        {shops && shops.length > 0 && (
          <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {shops.map((s) => (
              <ShopCard
                key={s.shop}
                shop={s.shop}
                scope={s.scope}
                onCheckProducts={() => navigate('/app/products')}
              />
            ))}
          </section>
        )}
      </div>
    </div>
  )
}

import { LoaderCircle } from 'lucide-react'

function ShopCard({
  shop,
  scope,
  onCheckProducts,
}: {
  shop: string
  scope: string
  onCheckProducts: () => void
}) {
  const { data: products, isLoading } = useShopifyProducts(shop)

  const scopes = scope.split(',').map((s) => s.trim())
  const hasProducts = scopes.includes('read_products') || scopes.includes('read_all_products')

  return (
    <div className="rounded-lg border border-border/60 bg-card p-5 space-y-4">
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <h3 className="truncate text-[15px] font-semibold">{shop}</h3>
          <p className="mt-1 text-[12px] text-muted-foreground line-clamp-1">
            {scope || '—'}
          </p>
        </div>
        <span
          className={cn(
            'shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium',
            hasProducts
              ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300'
              : 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300',
          )}
        >
          {hasProducts ? '产品可用' : '权限受限'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-md bg-muted/30 p-3">
          <div className="text-[11px] text-muted-foreground">授权范围</div>
          <div className="mt-1 text-[13px] font-medium">{scopes.length} 项</div>
        </div>
        <div className="rounded-md bg-muted/30 p-3">
          <div className="text-[11px] text-muted-foreground">产品</div>
          <div className="mt-1 text-[13px] font-medium tabular-nums">
            {isLoading ? '…' : products?.length ?? 0}
          </div>
        </div>
      </div>

      <Button
        variant="outline"
        size="sm"
        className="w-full text-xs"
        onClick={onCheckProducts}
        disabled={!hasProducts}
      >
        <Search className="mr-1.5 size-3.5" />
        {hasProducts ? '合规检查' : '产品权限不足'}
      </Button>
    </div>
  )
}
