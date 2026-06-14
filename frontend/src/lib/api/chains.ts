/**
 * ActionChain 与 EventChain API 客户端。
 * 后端：app/api/chains.py
 */
import type {
  ActionChain,
  ActionChainSummary,
  EventChain,
  EventChainSummary,
  EventCreateRequest,
  EventNode,
} from '@/types'

const BASE = '/api/v1/chains'

/** 事件筛选参数 */
export interface EventFilterParams {
  source?: string
  event_type?: string
  severity?: string
  tags?: string
  max_count?: number
}

/** 获取操作链列表摘要 */
export async function listActionChains(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
): Promise<ActionChainSummary[]> {
  const res = await authFetch(`${BASE}/actions`)
  if (!res.ok) throw new Error(`获取操作链列表失败: HTTP ${res.status}`)
  return res.json()
}

/** 获取单个操作链详情 */
export async function getActionChain(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  chainId: string,
): Promise<ActionChain> {
  const res = await authFetch(`${BASE}/actions/${encodeURIComponent(chainId)}`)
  if (!res.ok) throw new Error(`获取操作链详情失败: HTTP ${res.status}`)
  return res.json()
}

/** 获取操作链路人类可读描述 */
export async function getActionChainTrail(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  chainId: string,
): Promise<string[]> {
  const res = await authFetch(`${BASE}/actions/${encodeURIComponent(chainId)}/trail`)
  if (!res.ok) throw new Error(`获取操作链路失败: HTTP ${res.status}`)
  return res.json()
}

/** 获取事件链列表摘要 */
export async function listEventChains(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
): Promise<EventChainSummary[]> {
  const res = await authFetch(`${BASE}/events`)
  if (!res.ok) throw new Error(`获取事件链列表失败: HTTP ${res.status}`)
  return res.json()
}

/** 获取单个事件链详情 */
export async function getEventChain(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  chainId: string,
): Promise<EventChain> {
  const res = await authFetch(`${BASE}/events/${encodeURIComponent(chainId)}`)
  if (!res.ok) throw new Error(`获取事件链详情失败: HTTP ${res.status}`)
  return res.json()
}

/** 获取事件链时间线人类可读描述 */
export async function getEventChainTimeline(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  chainId: string,
): Promise<string[]> {
  const res = await authFetch(`${BASE}/events/${encodeURIComponent(chainId)}/timeline`)
  if (!res.ok) throw new Error(`获取事件时间线失败: HTTP ${res.status}`)
  return res.json()
}

/** 按条件筛选事件链中的事件 */
export async function filterEventChain(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  chainId: string,
  params: EventFilterParams = {},
): Promise<EventNode[]> {
  const sp = new URLSearchParams()
  if (params.source) sp.set('source', params.source)
  if (params.event_type) sp.set('event_type', params.event_type)
  if (params.severity) sp.set('severity', params.severity)
  if (params.tags) sp.set('tags', params.tags)
  if (params.max_count) sp.set('max_count', String(params.max_count))
  const qs = sp.toString()
  const url = `${BASE}/events/${encodeURIComponent(chainId)}/filter${qs ? `?${qs}` : ''}`
  const res = await authFetch(url)
  if (!res.ok) throw new Error(`事件筛选失败: HTTP ${res.status}`)
  return res.json()
}

/** 向事件链追加事件 */
export async function createEventChainEvent(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  body: EventCreateRequest,
): Promise<EventNode> {
  const res = await authFetch(`${BASE}/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`创建事件失败: HTTP ${res.status}`)
  return res.json()
}
