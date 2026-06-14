/**
 * 知识库导入 API 客户端。
 * 后端：app/api/knowledge_import.py
 *
 * 注意：所有函数都接收已认证的 fetch 函数（来自 useAuth().authFetch），
 * 避免模块顶层依赖 React Context。
 */
import type {
  KnowledgeDoc,
  KnowledgeImportAck,
  KnowledgeMarket,
  KnowledgeSearchRequest,
  KnowledgeSearchResponse,
  KnowledgeStats,
} from '@/types'

const BASE = '/api/v1/knowledge'

/** 列出当前用户已导入的文档 */
export async function listKnowledgeDocs(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
): Promise<KnowledgeDoc[]> {
  const res = await authFetch(`${BASE}/docs`)
  if (!res.ok) throw new Error(`list docs failed: HTTP ${res.status}`)
  return res.json()
}

/** 删除文档（含 ChromaDB 向量） */
export async function deleteKnowledgeDoc(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  docId: string,
): Promise<{ ok: boolean; doc_id: string }> {
  const res = await authFetch(`${BASE}/docs/${docId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`delete doc failed: HTTP ${res.status}`)
  return res.json()
}

/** 知识库统计：文档数 / 向量数 / 各市场分布 */
export async function getKnowledgeStats(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
): Promise<KnowledgeStats> {
  const res = await authFetch(`${BASE}/stats`)
  if (!res.ok) throw new Error(`get stats failed: HTTP ${res.status}`)
  return res.json()
}

/**
 * 上传 PDF（FormData，multipart/form-data）。
 * 后台向量化，立即返回 doc_id + status=indexing。
 */
export async function uploadKnowledgePdf(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  file: File,
  options?: { market?: KnowledgeMarket; regulationName?: string },
): Promise<KnowledgeImportAck> {
  const form = new FormData()
  form.append('file', file)
  if (options?.market) form.append('market', options.market)
  if (options?.regulationName) form.append('regulation_name', options.regulationName)

  const res = await authFetch(`${BASE}/upload`, {
    method: 'POST',
    body: form,
    // 不设 Content-Type，让浏览器自动加 multipart boundary
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `upload failed: HTTP ${res.status}`)
  }
  return res.json()
}

/** 从 URL 抓取并向量化 */
export async function importKnowledgeUrl(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  url: string,
  options?: { market?: KnowledgeMarket; regulationName?: string },
): Promise<KnowledgeImportAck> {
  const form = new FormData()
  form.append('url', url)
  if (options?.market) form.append('market', options.market)
  if (options?.regulationName) form.append('regulation_name', options.regulationName)

  const res = await authFetch(`${BASE}/url`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `import url failed: HTTP ${res.status}`)
  }
  return res.json()
}

/** 语义搜索预览（直接查询 ChromaDB） */
export async function searchKnowledge(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  req: KnowledgeSearchRequest,
): Promise<KnowledgeSearchResponse> {
  const res = await authFetch(`${BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(`search failed: HTTP ${res.status}`)
  return res.json()
}

/** 知识库支持的市场代码（与后端 market_routing.py 对齐）。 */
export const MARKET_VALUES: readonly KnowledgeMarket[] = [
  'eu',
  'us',
  'jp',
  'kr',
  'cn',
  'custom',
] as const

/** 知识库市场代码 → 中文标签 */
export const MARKET_LABEL: Record<KnowledgeMarket, string> = {
  eu: '欧盟',
  us: '美国',
  jp: '日本',
  kr: '韩国',
  cn: '中国',
  custom: '自定义',
}

/** 文档状态 → 视觉样式 */
export const STATUS_LABEL: Record<KnowledgeDoc['status'], string> = {
  indexing: '向量化中',
  done: '已就绪',
  error: '失败',
}
