/**
 * Shopify 集成 API 客户端。
 * 后端：app/api/shopify.py
 */
import type {
  ChatResponse,
  ShopifyComplianceCheckRequest,
  ShopifyProductInfo,
  ShopifyShopInfo,
} from '@/types'

const BASE = '/api/v1/shopify'

/** 发起 OAuth 授权，返回 Shopify 授权页 URL */
export async function getShopifyAuthUrl(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  shop: string,
): Promise<{ authorization_url: string; shop: string; state: string }> {
  const res = await authFetch(`${BASE}/auth?shop=${encodeURIComponent(shop)}`)
  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    throw new Error(e.detail || `获取授权 URL 失败: HTTP ${res.status}`)
  }
  return res.json()
}

/** 已连接的 Shopify 店铺列表 */
export async function listShopifyShops(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
): Promise<ShopifyShopInfo[]> {
  const res = await authFetch(`${BASE}/shops`)
  if (!res.ok) throw new Error(`获取店铺列表失败: HTTP ${res.status}`)
  return res.json()
}

/** 获取店铺产品列表 */
export async function listShopifyProducts(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  shop: string,
  maxCount = 50,
): Promise<ShopifyProductInfo[]> {
  const res = await authFetch(`${BASE}/${encodeURIComponent(shop)}/products?max_count=${maxCount}`)
  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    throw new Error(e.detail || `获取产品列表失败: HTTP ${res.status}`)
  }
  return res.json()
}

/** 对单个产品执行合规检查 */
export async function checkShopifyProduct(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  shop: string,
  productId: number,
  req: ShopifyComplianceCheckRequest,
): Promise<ChatResponse> {
  const res = await authFetch(
    `${BASE}/${encodeURIComponent(shop)}/check/${productId}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    },
  )
  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    throw new Error(e.detail || `合规检查失败: HTTP ${res.status}`)
  }
  return res.json()
}

/** 市场代码 → 中文标签（常用目标市场） */
export const TARGET_MARKETS = [
  { code: 'de', label: '德国 🇩🇪' },
  { code: 'fr', label: '法国 🇫🇷' },
  { code: 'uk', label: '英国 🇬🇧' },
  { code: 'us', label: '美国 🇺🇸' },
  { code: 'jp', label: '日本 🇯🇵' },
  { code: 'kr', label: '韩国 🇰🇷' },
] as const
