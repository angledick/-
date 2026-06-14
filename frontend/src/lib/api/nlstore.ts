/**
 * 自然语言存储 (NL Store) API 客户端。
 * 后端：app/api/chains.py (/nl-store/*)
 */
import type { NLRecord, NLRecordCreateRequest, NLSearchResult, NLSummaryItem } from '@/types'

const BASE = '/api/v1/nl-store'

/** 全文搜索 */
export async function searchNL(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  q: string,
  namespace?: string,
  maxResults = 20,
): Promise<NLSearchResult[]> {
  const params = new URLSearchParams({ q })
  if (namespace) params.set('namespace', namespace)
  params.set('max_results', String(maxResults))
  const res = await authFetch(`${BASE}/search?${params}`)
  if (!res.ok) throw new Error(`搜索失败: HTTP ${res.status}`)
  return res.json()
}

/** 列出 namespace 下的记录摘要 */
export async function listNLNamespace(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  namespace: string,
): Promise<NLSummaryItem[]> {
  const res = await authFetch(`${BASE}/${encodeURIComponent(namespace)}`)
  if (!res.ok) throw new Error(`获取列表失败: HTTP ${res.status}`)
  return res.json()
}

/** 获取单条记录 */
export async function getNLRecord(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  namespace: string,
  key: string,
): Promise<NLRecord> {
  const res = await authFetch(`${BASE}/${encodeURIComponent(namespace)}/${encodeURIComponent(key)}`)
  if (!res.ok) throw new Error(`获取记录失败: HTTP ${res.status}`)
  return res.json()
}

/** 创建记录 (key 已存在则更新) */
export async function createNLRecord(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  namespace: string,
  req: NLRecordCreateRequest,
): Promise<NLRecord> {
  const res = await authFetch(`${BASE}/${encodeURIComponent(namespace)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    throw new Error(e.detail || `创建失败: HTTP ${res.status}`)
  }
  return res.json()
}

/** 更新记录 */
export async function updateNLRecord(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  namespace: string,
  key: string,
  req: Partial<NLRecordCreateRequest>,
): Promise<NLRecord> {
  const res = await authFetch(`${BASE}/${encodeURIComponent(namespace)}/${encodeURIComponent(key)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    throw new Error(e.detail || `更新失败: HTTP ${res.status}`)
  }
  return res.json()
}

/** 删除记录 */
export async function deleteNLRecord(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  namespace: string,
  key: string,
): Promise<void> {
  const res = await authFetch(`${BASE}/${encodeURIComponent(namespace)}/${encodeURIComponent(key)}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`删除失败: HTTP ${res.status}`)
}
