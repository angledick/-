/**
 * 新闻监控 API 客户端。
 * 后端：app/api/news_monitor.py
 */

const BASE = '/api/v1/news-monitor'

/** 新闻条 */
export interface NewsItem {
  id: string
  title: string
  content: string
  source: string
  url: string
  risk_direction: '利多' | '利空' | '中性'
  risk_level: 'high' | 'medium' | 'low'
  /** AI 分析推理 */
  logic: string
  keywords: string[]
  published_at: string
  analyzed_at: string
}

/** 新闻列表响应 */
export interface NewsListResponse {
  news: NewsItem[]
  total: number
}

/** 市场摘要 */
export interface MarketSummary {
  bullish_count: number
  bearish_count: number
  neutral_count: number
  high_risk_news: NewsItem[]
  period_hours: number
}

/** 关键词配置 */
export interface KeywordConfig {
  keywords: string[]
  high_words: string[]
}

/** 列出新闻 */
export async function listNews(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  params?: { hours?: number; limit?: number; direction?: string; level?: string },
): Promise<NewsListResponse> {
  const q = new URLSearchParams()
  if (params?.hours) q.set('hours', String(params.hours))
  if (params?.limit) q.set('limit', String(params.limit))
  if (params?.direction) q.set('direction', params.direction)
  if (params?.level) q.set('level', params.level)
  const res = await authFetch(`${BASE}/news?${q.toString()}`)
  if (!res.ok) throw new Error(`获取新闻失败: HTTP ${res.status}`)
  return res.json()
}

/** 市场摘要 */
export async function getMarketSummary(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  hours = 24,
): Promise<MarketSummary> {
  const res = await authFetch(`${BASE}/summary?hours=${hours}`)
  if (!res.ok) throw new Error(`获取摘要失败: HTTP ${res.status}`)
  return res.json()
}

/** 手动触发采集 */
export async function triggerCollect(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
): Promise<{ status: string; message: string }> {
  const res = await authFetch(`${BASE}/collect`, { method: 'POST' })
  if (!res.ok) throw new Error(`采集失败: HTTP ${res.status}`)
  return res.json()
}

/** 获取关键词 */
export async function getKeywords(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
): Promise<KeywordConfig> {
  const res = await authFetch(`${BASE}/keywords`)
  if (!res.ok) throw new Error(`获取关键词失败: HTTP ${res.status}`)
  return res.json()
}

/** 更新关键词 */
export async function updateKeywords(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  config: KeywordConfig,
): Promise<{ ok: boolean; keywords: string[]; high_words: string[] }> {
  const res = await authFetch(`${BASE}/keywords`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })
  if (!res.ok) throw new Error(`更新关键词失败: HTTP ${res.status}`)
  return res.json()
}

export const DIRECTION_LABEL: Record<string, string> = {
  '利多': '利多',
  '利空': '利空',
  '中性': '中性',
}

export const LEVEL_LABEL: Record<string, string> = {
  high: '高风险',
  medium: '中风险',
  low: '低风险',
}
