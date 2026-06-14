/**
 * Latest OS backend API client.
 *
 * This file adapts the astra frontend to the contest_hei backend routes without
 * importing contest frontend UI code.
 */

export type AuthFetch = (input: RequestInfo, init?: RequestInit) => Promise<Response>

const API = '/api/v1'

async function request<T>(
  authFetch: AuthFetch,
  url: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const res = await authFetch(url, { ...init, headers })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = body?.detail || body?.message || res.statusText
    throw new Error(`${detail || '请求失败'} (${res.status})`)
  }
  return res.json()
}

export type ProductLifecycle =
  | 'concept'
  | 'design'
  | 'sourcing'
  | 'ready'
  | 'active'
  | 'fulfilling'
  | 'aftersale'
  | 'end'

export interface ProductItem {
  id: string
  name: string
  product_type?: string
  target_markets: string[]
  hs_code?: string
  vendor?: string
  tags?: string[]
  lifecycle_stage: ProductLifecycle
  business_stage?: string | null
  compliance_status: 'pending' | 'checking' | 'passed' | 'failed' | string
  risk_level: 'low' | 'medium' | 'high' | 'critical' | string
  health_score?: number
  certifications?: { name: string; status: string }[]
  created_at: string
  updated_at: string
  metadata?: Record<string, unknown>
}

export interface ProductEvent {
  id?: string
  event_id?: string
  type: string
  category?: string
  source?: string
  product_id?: string | null
  business_stage?: string | null
  data?: Record<string, unknown>
  title?: string
  description_nl?: string
  description?: string
  error?: string | null
  timestamp?: string
  created_at?: string
  severity?: 'low' | 'medium' | 'high' | 'critical'
}

export interface ProductCreateBody {
  name: string
  product_type?: string
  target_markets?: string[]
  hs_code?: string
  vendor?: string
  tags?: string[]
}

export interface RiskAlertItem {
  id?: string
  alert_id?: string
  alert_type: string
  severity: 'low' | 'medium' | 'high' | 'critical' | string
  title: string
  message?: string
  description?: string
  created_at: string
  dismissed?: boolean
  affected_products?: string[]
  affected_markets?: string[]
  source?: string
  source_url?: string
}

export const productsApi = {
  list: (authFetch: AuthFetch) => request<ProductItem[]>(authFetch, `${API}/products`),
  get: (authFetch: AuthFetch, id: string) => request<ProductItem>(authFetch, `${API}/products/${id}`),
  create: (authFetch: AuthFetch, body: ProductCreateBody) =>
    request<ProductItem>(authFetch, `${API}/products`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updateLifecycle: (
    authFetch: AuthFetch,
    productId: string,
    lifecycleStage: ProductLifecycle,
    reason = '',
  ) =>
    request<ProductItem>(authFetch, `${API}/products/${productId}/lifecycle`, {
      method: 'PUT',
      body: JSON.stringify({ lifecycle_stage: lifecycleStage, reason }),
    }),
  delete: (authFetch: AuthFetch, productId: string, archive = true) =>
    request<{ success: boolean; archived: boolean }>(
      authFetch,
      `${API}/products/${productId}?archive=${archive ? 'true' : 'false'}`,
      { method: 'DELETE' },
    ),
  events: (authFetch: AuthFetch, productId: string) =>
    request<{ events: ProductEvent[]; total: number }>(authFetch, `${API}/products/${productId}/events`),
  complianceCheck: (authFetch: AuthFetch, productId: string, targetMarket: string) =>
    request<unknown>(
      authFetch,
      `${API}/products/${productId}/compliance-check?target_market=${encodeURIComponent(targetMarket)}`,
      { method: 'POST' },
    ),
}

export interface PipelineHealthResponse {
  overall_score: number
  stages: Array<{
    stage_number: number
    stage_name: string
    pass_rate: number
    total_products: number
    passed_products: number
    risk_products: number
    pending_actions: number
    status: string
  }>
  last_updated: string
}

export const pipelineApi = {
  health: (authFetch: AuthFetch) => request<PipelineHealthResponse>(authFetch, `${API}/pipeline/health`),
}

export const riskApi = {
  alerts: (authFetch: AuthFetch, params: { severity?: string; size?: number } = {}) => {
    const query = new URLSearchParams()
    if (params.severity) query.set('severity', params.severity)
    query.set('size', String(params.size ?? 50))
    return request<{ alerts: RiskAlertItem[]; page: number; size: number }>(
      authFetch,
      `${API}/risk/alerts?${query.toString()}`,
    )
  },
  dismiss: (authFetch: AuthFetch, alertId: string) =>
    request<{ status: string; alert_id: string }>(authFetch, `${API}/risk/alerts/${alertId}/dismiss`, {
      method: 'POST',
    }),
}

export interface SchedulerJobItem {
  id: string
  name: string
  func_ref: string
  trigger: {
    type: 'interval' | 'cron' | 'unknown'
    interval_seconds?: number
    interval_human?: string
    expression?: string
    cron_human?: string
  }
  next_run_time: string | null
  pending: boolean
  coalesce: boolean
  max_instances: number
  misfire_grace_time: number | null
  scope: 'global' | 'product'
  product_id: string | null
}

export interface ProductTaskMeta {
  id: string
  name: string
  target_markets: string[]
  lifecycle_stage: ProductLifecycle
  compliance_status: string
  health_score: number
}

export interface SchedulerGroupedResponse {
  global: SchedulerJobItem[]
  products: Record<string, SchedulerJobItem[]>
  product_meta: Record<string, ProductTaskMeta>
  enabled: boolean
}

export interface SchedulerTaskWorker {
  task_name: string
  display_name: string
  description?: string
  default_trigger: 'interval' | 'cron' | string
  default_args: Record<string, unknown>
  bound_worker: string
  sdk_enabled: boolean
}

export interface SchedulerWorkerItem {
  worker_code: string
  worker_name: string
  description?: string
  sdk_enabled: boolean
  business_stage?: string
}

export interface SchedulerTasksWithWorkersResponse {
  tasks: SchedulerTaskWorker[]
  available_workers: SchedulerWorkerItem[]
  total_tasks: number
  total_workers: number
}

export const schedulerApi = {
  grouped: (authFetch: AuthFetch) =>
    request<SchedulerGroupedResponse>(authFetch, `${API}/scheduler/jobs/grouped`),
  tasksWithWorkers: (authFetch: AuthFetch) =>
    request<SchedulerTasksWithWorkersResponse>(authFetch, `${API}/scheduler/tasks-with-workers`),
  create: (
    authFetch: AuthFetch,
    body: {
      task: string
      trigger_type: 'interval' | 'cron'
      trigger_args: Record<string, unknown>
      job_id?: string
      replace_existing?: boolean
    },
  ) =>
    request<{ ok: boolean; job_id: string }>(authFetch, `${API}/scheduler/jobs`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  pause: (authFetch: AuthFetch, jobId: string) =>
    request<{ ok: boolean }>(authFetch, `${API}/scheduler/jobs/${jobId}/pause`, { method: 'POST' }),
  resume: (authFetch: AuthFetch, jobId: string) =>
    request<{ ok: boolean }>(authFetch, `${API}/scheduler/jobs/${jobId}/resume`, { method: 'POST' }),
  trigger: (authFetch: AuthFetch, jobId: string) =>
    request<{ ok: boolean }>(authFetch, `${API}/scheduler/jobs/${jobId}/trigger`, { method: 'POST' }),
  delete: (authFetch: AuthFetch, jobId: string) =>
    request<{ ok: boolean }>(authFetch, `${API}/scheduler/jobs/${jobId}`, { method: 'DELETE' }),
  updateBinding: (authFetch: AuthFetch, taskName: string, workerCode: string) =>
    request<{ ok: boolean }>(authFetch, `${API}/scheduler/bindings/${taskName}`, {
      method: 'PUT',
      body: JSON.stringify({ worker_code: workerCode, enabled: true }),
    }),
}

export interface IntegrationConnection {
  id: string
  provider: string
  label: string
  status: 'connected' | 'disconnected' | 'connecting' | 'error' | string
  config?: Record<string, unknown>
  token?: Record<string, unknown>
  last_sync_at?: number
  last_error?: string
  created_at?: string
  updated_at?: string
}

export interface IntegrationProviderTemplate {
  provider: string
  name: string
  icon?: string
  auth_type?: string
  config_fields?: string[]
  description?: string
  connection_count?: number
}

export const integrationsApi = {
  list: (authFetch: AuthFetch) =>
    request<{ connections: IntegrationConnection[] }>(authFetch, `${API}/integrations`),
  providers: (authFetch: AuthFetch) =>
    request<{ providers: IntegrationProviderTemplate[] }>(authFetch, `${API}/integrations/providers`),
  status: (authFetch: AuthFetch) =>
    request<{
      status: Record<
        string,
        { name: string; icon?: string; status: string; connected: number; total_connections: number }
      >
    }>(authFetch, `${API}/integrations/status`),
  create: (authFetch: AuthFetch, body: { provider: string; label?: string; config?: Record<string, unknown> }) =>
    request<IntegrationConnection>(authFetch, `${API}/integrations`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updateConfig: (authFetch: AuthFetch, id: string, config: Record<string, unknown>) =>
    request<IntegrationConnection>(authFetch, `${API}/integrations/${id}/config`, {
      method: 'PUT',
      body: JSON.stringify({ config }),
    }),
  test: (authFetch: AuthFetch, id: string) =>
    request<{ ok?: boolean; status?: string; message?: string; error?: string }>(
      authFetch,
      `${API}/integrations/${id}/test`,
      { method: 'POST' },
    ),
  sync: (authFetch: AuthFetch, id: string) =>
    request<{ ok?: boolean; status?: string; message?: string; synced?: number; errors?: number }>(
      authFetch,
      `${API}/integrations/${id}/sync`,
      { method: 'POST' },
    ),
  delete: (authFetch: AuthFetch, id: string) =>
    request<{ status: string; connection_id: string }>(authFetch, `${API}/integrations/${id}`, {
      method: 'DELETE',
    }),
}

export type ChannelType = 'feishu' | 'dingtalk' | 'wecom' | 'slack' | 'email' | 'webhook'

export interface ChannelItem {
  name: string
  channel: ChannelType | string
  status: string
}

export const channelsApi = {
  list: (authFetch: AuthFetch) => request<{ channels: ChannelItem[] }>(authFetch, `${API}/channels`),
  register: (authFetch: AuthFetch, body: { name: string; channel_type: ChannelType; config: Record<string, unknown> }) =>
    request<{ name: string; channel_type: string; status: string }>(authFetch, `${API}/channels`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  update: (authFetch: AuthFetch, name: string, config: Record<string, unknown>) =>
    request<{ name: string; channel_type: string; status: string }>(authFetch, `${API}/channels/${name}`, {
      method: 'PUT',
      body: JSON.stringify({ config }),
    }),
  delete: (authFetch: AuthFetch, name: string) =>
    request<{ status: string; name: string }>(authFetch, `${API}/channels/${name}`, { method: 'DELETE' }),
  sendTest: (authFetch: AuthFetch, channel: string) =>
    request<{ channel?: string; status?: string; error?: string }>(authFetch, `${API}/channels/send`, {
      method: 'POST',
      body: JSON.stringify({
        channel,
        target: 'broadcast',
        notification: {
          title: '避风港通知测试',
          message: '这是一条来自前端配置页的测试消息。',
          severity: 'info',
        },
      }),
    }),
}

export interface BriefItem {
  type: string
  date: string
  generated_at: string
  summary?: Record<string, number>
  highlights?: string[]
  recommendations?: string[]
}

export const proactiveApi = {
  brief: (authFetch: AuthFetch, limit = 7) =>
    request<{ briefs: BriefItem[] }>(authFetch, `${API}/proactive/brief?limit=${limit}`),
}
