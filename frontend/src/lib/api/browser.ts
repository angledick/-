/**
 * Browser 自动化 API 客户端。
 * 后端：app/api/browser.py
 */

const BASE = '/api/v1/browser'

export interface BrowserStatus {
  active: boolean
  current_url?: string
  page_title?: string
  session_count?: number
  last_action?: string
  last_action_time?: string
  daemon_running?: boolean
  daemon_url?: string
  sites?: string[]
}

export interface BrowserSnapshot {
  ok?: boolean
  url: string
  title: string
  screenshot?: string
  html_preview?: string
  timestamp: string
  error?: string | null
}

/** 站点命令请求 */
export interface SiteCommandRequest {
  site: string
  command: string
  args?: string[]
}

/** 浏览器操作请求 */
export interface BrowserActionRequest {
  action: string
  params?: Record<string, unknown>
  session?: string
}

/** 导航请求 */
export interface NavigateRequest {
  url: string
  session?: string
}

/** 导航结果 */
export interface NavigateResult {
  ok: boolean
  url: string
  title: string
}

/** 获取浏览器自动化状态 */
export async function getBrowserStatus(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
): Promise<BrowserStatus> {
  const res = await authFetch(`${BASE}/status`)
  if (!res.ok) throw new Error(`获取浏览器状态失败: HTTP ${res.status}`)
  return res.json()
}

/** 获取浏览器快照 */
export async function getBrowserSnapshot(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
): Promise<BrowserSnapshot> {
  const res = await authFetch(`${BASE}/snapshot`, { method: 'POST' })
  if (!res.ok) throw new Error(`获取浏览器快照失败: HTTP ${res.status}`)
  return res.json()
}

/** 执行站点适配器命令（无需浏览器，通过 HTTP 获取结构化数据） */
export async function runSiteCommand(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  req: SiteCommandRequest,
): Promise<Record<string, unknown>> {
  const res = await authFetch(`${BASE}/site`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(`站点命令执行失败: HTTP ${res.status}`)
  return res.json()
}

/** 执行浏览器自动化命令（需要守护进程 + Chrome 扩展） */
export async function runBrowserAction(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  req: BrowserActionRequest,
): Promise<Record<string, unknown>> {
  const res = await authFetch(`${BASE}/action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(`浏览器操作失败: HTTP ${res.status}`)
  return res.json()
}

/** 导航到指定 URL，返回页面标题和 URL */
export async function browserNavigate(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  req: NavigateRequest,
): Promise<NavigateResult> {
  const res = await authFetch(`${BASE}/navigate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(`导航失败: HTTP ${res.status}`)
  return res.json()
}
