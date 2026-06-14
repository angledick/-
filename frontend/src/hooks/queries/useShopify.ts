/**
 * Shopify 集成 TanStack Query hooks。
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useAuth } from '@/context/AuthContext'
import {
  checkShopifyProduct,
  getShopifyAuthUrl,
  listShopifyProducts,
  listShopifyShops,
} from '@/lib/api/shopify'
import type { ShopifyComplianceCheckRequest } from '@/types'

const KEYS = {
  shops: ['shopify', 'shops'] as const,
  products: (shop: string) => ['shopify', 'products', shop] as const,
}

/** 已连接店铺列表 */
export function useShopifyShops() {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: KEYS.shops,
    queryFn: () => listShopifyShops(authFetch),
    staleTime: 30_000,
  })
}

/** 获取某店铺产品列表 — 手动触发，不被 auto-fetch */
export function useShopifyProducts(shop: string | null) {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: KEYS.products(shop ?? ''),
    queryFn: () => listShopifyProducts(authFetch, shop!),
    enabled: !!shop,
    staleTime: 15_000,
  })
}

/** 发起 OAuth 授权 — 成功后不立刻刷新（OAuth 跳转会离开当前页面） */
export function useShopifyAuth() {
  const { authFetch } = useAuth()
  return useMutation({
    mutationFn: (shop: string) => getShopifyAuthUrl(authFetch, shop),
  })
}

/** 产品合规检查 — 手动触发 mutation */
export function useShopifyCheck(shop: string, productId: number) {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: ShopifyComplianceCheckRequest) =>
      checkShopifyProduct(authFetch, shop, productId, req),
    onSuccess: () => {
      // 合规检查完成，刷新该店铺的产品列表（check 结果目前不在 products 响应里，但前端可以用 ChatPage 展示）
      qc.invalidateQueries({ queryKey: KEYS.products(shop) })
    },
  })
}
