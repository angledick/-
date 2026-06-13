/**
 * 配置中心 API 客户端层
 *
 * 统一封装所有配置管理相关的后端 API 调用。
 * 每个函数返回 Promise<T>，调用方通过 try/catch 处理错误。
 */

const API = '/api/v1'

// ── 通用工具 ─────────────────────────────────────────────────────────────────

/** 从 localStorage 读取 token 并附加 Authorization 头 */
function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('astra_token') : null
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return headers
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { ...authHeaders(), ...(options?.headers as Record<string, string> || {}) },
    ...options,
  })
  if (!res.ok) {
    const errBody = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}: ${errBody || res.statusText}`)
  }
  return res.json()
}

// ── Agent 配置 API ───────────────────────────────────────────────────────────

export interface AgentListItem {
  id: string
  name: string
  type: string
  description: string
  system_prompt_preview: string
  enabled: boolean
  sort_order: number
  sdk_config: SDKAgentConfig
  created_at: number
  updated_at: number
}

export interface AgentDetail extends AgentListItem {
  system_prompt: string
}

export interface SDKAgentConfig {
  enabled?: boolean
  model?: string | null
  max_turns?: number | null
  permission_mode?: string | null
  allowed_tools?: string[] | null
  disallowed_tools?: string[] | null
  include_hook_events?: boolean | null
  skills?: string[] | null
  agents?: Record<string, unknown> | null
}

export interface AgentUpsertRequest {
  name: string
  type: string
  description?: string
  system_prompt: string
  enabled?: boolean
  sort_order?: number
  sdk_config?: SDKAgentConfig
}

export const agentsApi = {
  list: () => request<AgentListItem[]>(`${API}/agents`),

  get: (id: string) => request<AgentDetail>(`${API}/agents/${id}`),

  create: (data: AgentUpsertRequest) =>
    request<AgentDetail>(`${API}/agents`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: AgentUpsertRequest) =>
    request<AgentDetail>(`${API}/agents/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (id: string) =>
    request<{ ok: boolean }>(`${API}/agents/${id}`, { method: 'DELETE' }),

  toggle: (id: string, enabled: boolean) =>
    request<{ ok: boolean; enabled: boolean }>(`${API}/agents/${id}/toggle`, {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
    }),

  getSkills: (agentId: string) =>
    request<{ agent_id: string; skill_ids: string[] }>(`${API}/agents/${agentId}/skills`),

  setSkills: (agentId: string, skillIds: string[]) =>
    request<{ agent_id: string; skill_ids: string[] }>(`${API}/agents/${agentId}/skills`, {
      method: 'PUT',
      body: JSON.stringify({ skill_ids: skillIds }),
    }),

  getTools: (agentId: string) =>
    request<{ agent_id: string; tool_ids: string[] }>(`${API}/agents/${agentId}/tools`),

  setTools: (agentId: string, toolIds: string[]) =>
    request<{ agent_id: string; tool_ids: string[] }>(`${API}/agents/${agentId}/tools`, {
      method: 'PUT',
      body: JSON.stringify({ tool_ids: toolIds }),
    }),

  getOAuth: (agentId: string) =>
    request<{ agent_id: string; connection_ids: string[] }>(`${API}/agents/${agentId}/oauth`),

  setOAuth: (agentId: string, connectionIds: string[]) =>
    request<{ agent_id: string; connection_ids: string[] }>(`${API}/agents/${agentId}/oauth`, {
      method: 'PUT',
      body: JSON.stringify({ connection_ids: connectionIds }),
    }),

  getStatus: (agentId: string) =>
    request<{
      agent_id: string
      name: string
      enabled: boolean
      associated_skills: string[]
      associated_tools: string[]
      associated_oauth: string[]
      status: string
    }>(`${API}/agents/${agentId}/status`),
}

// ── Skills 配置 API ──────────────────────────────────────────────────────────

export interface SkillItem {
  id: string
  name: string
  description?: string
  source: string
  source_url?: string
  version?: string
  enabled: boolean
  installed: boolean
  created_at?: string
  updated_at?: string
}

export const skillsApi = {
  list: (params?: { status?: string; stage?: number }) => {
    const query = new URLSearchParams()
    if (params?.status) query.set('status', params.status)
    if (params?.stage !== undefined) query.set('stage', String(params.stage))
    const qs = query.toString()
    return request<{ skills: SkillItem[] }>(`${API}/skills${qs ? '?' + qs : ''}`)
  },

  install: (data: { name: string; source?: string; source_url?: string; config?: Record<string, unknown> }) =>
    request<SkillItem>(`${API}/skills/install`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: { config?: Record<string, unknown> }) =>
    request<{ ok: boolean }>(`${API}/skills/${id}/config`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (id: string) =>
    request<{ status: string; skill_id: string }>(`${API}/skills/${id}`, { method: 'DELETE' }),

  refresh: (id: string) =>
    request<{ status: string; skill_id: string }>(`${API}/skills/${id}/refresh`, { method: 'POST' }),
}

// ── Tools 配置 API ───────────────────────────────────────────────────────────

export interface ToolItem {
  id: string
  name: string
  description?: string
  tool_type?: string
  category?: string
  config?: Record<string, unknown>
  enabled: boolean
  created_at?: string
  updated_at?: string
}

export const toolsApi = {
  list: (params?: { category?: string; enabled?: boolean }) => {
    const query = new URLSearchParams()
    if (params?.category) query.set('category', params.category)
    if (params?.enabled !== undefined) query.set('enabled', String(params.enabled))
    const qs = query.toString()
    return request<{ tools: ToolItem[]; total: number }>(`${API}/tools${qs ? '?' + qs : ''}`)
  },

  get: (id: string) => request<ToolItem>(`${API}/tools/${id}`),

  create: (data: { name: string; description?: string; tool_type?: string; category?: string; enabled?: boolean; config?: Record<string, unknown> }) =>
    request<ToolItem>(`${API}/tools`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: { name?: string; description?: string; tool_type?: string; category?: string; config?: Record<string, unknown>; enabled?: boolean }) =>
    request<ToolItem>(`${API}/tools/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (id: string) =>
    request<{ deleted: string }>(`${API}/tools/${id}`, { method: 'DELETE' }),

  toggle: (id: string) =>
    request<{ id: string; enabled: boolean; name: string }>(`${API}/tools/${id}/toggle`, {
      method: 'PUT',
    }),
}

// ── OAuth / 集成配置 API ─────────────────────────────────────────────────────

export interface OAuthConnection {
  id: string
  provider: string
  label: string
  status: 'connected' | 'disconnected' | 'connecting' | 'error'
  config?: Record<string, unknown>
  token?: { access_token?: string }
  last_error?: string
  created_at?: string
  updated_at?: string
}

export const oauthApi = {
  list: (provider?: string) => {
    const query = provider ? `?provider=${provider}` : ''
    return request<{ connections: OAuthConnection[] }>(`${API}/integrations${query}`)
  },

  getProviders: () =>
    request<{ providers: Array<{ provider: string; name: string; icon?: string; config_fields?: string[] }> }>(
      `${API}/integrations/providers`
    ),

  getStatusSummary: () =>
    request<{ status: Record<string, { name: string; icon?: string; status: string; connected: number; total_connections: number }> }>(
      `${API}/integrations/status`
    ),

  create: (data: { provider: string; label?: string; config?: Record<string, unknown> }) =>
    request<OAuthConnection>(`${API}/integrations`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateConfig: (id: string, config: Record<string, unknown>) =>
    request<OAuthConnection>(`${API}/integrations/${id}/config`, {
      method: 'PUT',
      body: JSON.stringify({ config }),
    }),

  delete: (id: string) =>
    request<{ status: string; connection_id: string }>(`${API}/integrations/${id}`, { method: 'DELETE' }),

  test: (id: string) =>
    request<{ ok: boolean; status?: string; message?: string; error?: string }>(`${API}/integrations/${id}/test`, { method: 'POST' }),

  // OAuth 兼容别名
  testOAuth: (id: string) =>
    request<{ ok: boolean; message?: string }>(`${API}/oauth/${id}/test`, { method: 'POST' }),
}

// ── 模型配置 API ─────────────────────────────────────────────────────────────

export interface ModelConfigItem {
  role: string
  provider: string
  model: string
  api_key_env: string
  base_url?: string
  max_tokens: number
  temperature: number
  top_p?: number
}

export const modelConfigsApi = {
  list: () => request<{ configs: ModelConfigItem[] }>(`${API}/model-configs`),

  create: (data: {
    role: string
    provider: string
    model: string
    api_key_env?: string
    base_url?: string
    max_tokens?: number
    temperature?: number
    top_p?: number
  }) =>
    request<{ ok: boolean; role: string }>(`${API}/model-configs`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (role: string, data: {
    role: string
    provider: string
    model: string
    api_key_env?: string
    base_url?: string
    max_tokens?: number
    temperature?: number
    top_p?: number
  }) =>
    request<{ ok: boolean; role: string }>(`${API}/model-configs/${role}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (role: string) =>
    request<{ ok: boolean; role: string }>(`${API}/model-configs/${role}`, { method: 'DELETE' }),

  getUsage: () =>
    request<{ total_tokens: number; by_model: Record<string, number>; routes: Record<string, string> }>(
      `${API}/model-configs/usage`
    ),
}

// ── 产品 API ─────────────────────────────────────────────────────────────────

// ── 产品类型 ─────────────────────────────────────────────────────────────────

export interface ProductItem {
  id: string
  name: string
  target_markets: string[]
  lifecycle_stage: string
  health_score?: number
  compliance_status: string
  certifications?: { name: string; status: string }[]
  hs_code?: string
  vendor?: string
  created_at?: string
  updated_at?: string
}

export interface ProductEvent {
  id: string
  type: string
  title: string
  description: string
  timestamp: string
  severity: 'low' | 'medium' | 'high' | 'critical'
}

export const productsApi = {
  list: () => request<ProductItem[]>(`${API}/products`),
  get: (id: string) => request<ProductItem>(`${API}/products/${id}`),
  getEvents: (id: string) =>
    request<{ events: ProductEvent[]; total: number }>(`${API}/products/${id}/events`)
      .then(res => res.events),
}

// ── 流水线/合规 API ──────────────────────────────────────────────────────────

/** 后端返回的单阶段状态 */
export interface PipelineStageStatus {
  stage_number: number
  stage_name: string
  pass_rate: number        // 0.0~1.0
  total_products: number
  passed_products: number
  risk_products: number
  pending_actions: number
  status: string            // healthy/warning/critical/unknown
}

/** 后端返回的流水线健康度 */
export interface PipelineHealthResponse {
  overall_score: number
  stages: PipelineStageStatus[]
  last_updated: string
}

export const pipelineApi = {
  health: () => request<PipelineHealthResponse>(`${API}/pipeline/health`),
}

// ── 风险预警 API ──────────────────────────────────────────────────────────────

export interface RiskAlertItem {
  id: string
  alert_type: string
  severity: string
  title: string
  message: string
  created_at: string
  dismissed?: boolean
  affected_products?: string[]
}

export const riskAlertsApi = {
  list: (params?: { alert_type?: string; severity?: string; page?: number; size?: number }) => {
    const query = new URLSearchParams()
    if (params?.alert_type) query.set('alert_type', params.alert_type)
    if (params?.severity) query.set('severity', params.severity)
    if (params?.page) query.set('page', String(params.page))
    if (params?.size) query.set('size', String(params.size))
    const qs = query.toString()
    return request<{ alerts: RiskAlertItem[]; page: number; size: number }>(`${API}/risk/alerts${qs ? '?' + qs : ''}`)
  },

  dismiss: (alertId: string) =>
    request<{ status: string; alert_id: string }>(`${API}/risk/alerts/${alertId}/dismiss`, { method: 'POST' }),

  /** 获取各市场监控状态 */
  getMarketStatus: () =>
    request<{ last_scan: string; active_alerts: number; markets: { code: string; alerts: number }[] }>(
      `${API}/risk/market-status`
    ),

  /** 手动触发市场扫描 */
  triggerScan: () =>
    request<{ status: string; alerts_created: number; events_found: number }>(
      `${API}/risk/scan`,
      { method: 'POST' }
    ),
}

// ── 记忆树 API ───────────────────────────────────────────────────────────────

export const memoryApi = {
  listNamespaces: () => request<{ namespaces: string[] }>(`${API}/memory/namespaces`),
  listRecords: (ns: string) => request<{ records: unknown[] }>(`${API}/memory/${ns}`),
  getRecord: (ns: string, key: string) => request<unknown>(`${API}/memory/${ns}/${key}`),
}

// ── CLI 命令 API ──────────────────────────────────────────────────────────────

export interface CLICommand {
  cmd: string
  desc: string
  usage?: string
  category?: string
}

export interface CLIExecuteResponse {
  success: boolean
  output?: string
  command: string
  duration_ms?: number
  error?: string
}

export const cliApi = {
  /** 执行 CLI 命令 */
  execute: (command: string) =>
    request<CLIExecuteResponse>(`${API}/cli/execute`, {
      method: 'POST',
      body: JSON.stringify({ command }),
    }),

  /** 自动补全建议 */
  complete: (prefix: string) =>
    request<{ suggestions: CLICommand[]; prefix: string }>(
      `${API}/cli/complete?prefix=${encodeURIComponent(prefix)}`
    ),

  /** 命令执行历史 */
  history: (limit?: number) =>
    request<{ history: CLIExecuteResponse[] }>(
      `${API}/cli/history${limit ? `?limit=${limit}` : ''}`
    ),
}

// ── 知识库 API ────────────────────────────────────────────────────────────────

export interface KnowledgeSection {
  id: string
  title: string
  content: string
  tags?: string[]
  markets?: string[]
  updated_at?: string
}

export const knowledgeApi = {
  list: () => request<{ sections: KnowledgeSection[] }>(`${API}/knowledge/sections`),
  get: (id: string) => request<KnowledgeSection>(`${API}/knowledge/sections/${id}`),
  search: (q: string) =>
    request<{ results: KnowledgeSection[] }>(
      `${API}/knowledge/search?q=${encodeURIComponent(q)}`
    ),
}

// ── 主动引擎 API ────────────────────────────────────────────────────────────

export interface BriefItem {
  type: string
  date: string
  generated_at: string
  summary: {
    active_products: number
    pending_alerts: number
    compliance_pass_rate: number
    cert_expiry_warnings: number
    regulation_changes: number
  }
  highlights: string[]
  recommendations: string[]
}

export const proactiveApi = {
  /** 获取合规简报 */
  getBrief: (limit = 7) =>
    request<{ briefs: BriefItem[] }>(`${API}/proactive/brief?limit=${limit}`),
}

// ── 定时任务管理 API ─────────────────────────────────────────────────────────

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
  /** 任务范围: global（全局） | product（产品级） */
  scope: 'global' | 'product'
  /** 产品级任务关联的产品ID */
  product_id: string | null
}

export interface SchedulerListResponse {
  jobs: SchedulerJobItem[]
  enabled: boolean
}
export interface ProductTaskMeta {
  id: string
  name: string
  target_markets: string[]
  lifecycle_stage: string
  compliance_status: string
  health_score: number
}

export interface SchedulerGroupedResponse {
  global: SchedulerJobItem[]
  products: Record<string, SchedulerJobItem[]>
  product_meta: Record<string, ProductTaskMeta>
  enabled: boolean
}

export const schedulerApi = {
  /** 获取所有定时任务 */
  list: () => request<SchedulerListResponse>(`${API}/scheduler/jobs`),

  /** 获取按维度(global/product)分组的定时任务 */
  listGrouped: () => request<SchedulerGroupedResponse>(`${API}/scheduler/jobs/grouped`),

  /** 获取可调度的任务模板 */
  listTasks: () =>
    request<{ tasks: Array<{ name: string; description?: string; func_ref?: string }> }>(
      `${API}/scheduler/tasks`
    ),

  /** 创建定时任务 */
  create: (data: {
    task: string
    trigger_type: 'interval' | 'cron'
    trigger_args: Record<string, unknown>
    job_id?: string
    replace_existing?: boolean
  }) =>
    request<{ ok: boolean; job_id: string; task: string; trigger: string }>(
      `${API}/scheduler/jobs`,
      { method: 'POST', body: JSON.stringify(data) }
    ),

  /** 暂停任务 */
  pause: (jobId: string) =>
    request<{ ok: boolean; job_id: string; status: string }>(
      `${API}/scheduler/jobs/${jobId}/pause`,
      { method: 'POST' }
    ),

  /** 恢复任务 */
  resume: (jobId: string) =>
    request<{ ok: boolean; job_id: string; status: string }>(
      `${API}/scheduler/jobs/${jobId}/resume`,
      { method: 'POST' }
    ),

  /** 删除任务 */
  delete: (jobId: string) =>
    request<{ ok: boolean; job_id: string; status: string }>(
      `${API}/scheduler/jobs/${jobId}`,
      { method: 'DELETE' }
    ),

  /** 立即触发任务 */
  trigger: (jobId: string) =>
    request<{ ok: boolean; job_id: string; status: string }>(
      `${API}/scheduler/jobs/${jobId}/trigger`,
      { method: 'POST' }
    ),

  /** 获取任务-Worker绑定 */
  getBindings: () =>
    request<{ bindings: Record<string, string> }>(`${API}/scheduler/bindings`),

  /** 更新任务-Worker绑定 */
  updateBinding: (taskName: string, workerId: string) =>
    request<{ ok: boolean; task: string; worker_id: string }>(
      `${API}/scheduler/bindings/${taskName}`,
      { method: 'PUT', body: JSON.stringify({ worker_id: workerId }) }
    ),
}


// ── 风险情报引擎 API ──────────────────────────────────────────────────────────

export type RiskDomain = 'tariff' | 'conflict' | 'financial'
export type RiskSeverity = 'critical' | 'high' | 'medium' | 'low'

export interface LlmAnalysis {
  summary: string       // ≤80字事件概述
  impact: string        // ≤60字影响分析
  actions: string[]     // ≤3条建议行动
  confidence: number    // 置信度 0~1
  analyzed_at?: string
  model?: string
}

export interface RiskIntelItem {
  id: string
  source_type: string
  source_name: string
  title: string
  summary?: string
  url?: string
  pub_time?: string
  collected_at: string
  risk_domain?: RiskDomain
  risk_category?: string
  risk_score: number
  severity: RiskSeverity
  sentiment?: string
  affected_markets: string[]
  affected_hs_codes: string[]
  matched_keywords: string[]
  trigger_source?: string
  jin10_id?: string
  jin10_important?: number
  jin10_channel?: number[]
  analyzed: number
  alert_id?: string
  headline_summary?: string
  // LLM 深度分析字段
  llm_analysis?: LlmAnalysis | null
  llm_analyzed?: number   // 0=未分析, 1=已分析
  llm_error?: string | null
}

export interface RiskIntelKeyword {
  id: string
  user_id: string
  keyword: string
  label?: string
  domain: string
  auto_suggested: number
  source_hint?: string
  periodic_enabled: number
  cron_expr: string
  last_run_at?: string
  next_run_at?: string
  total_runs: number
  total_hits: number
  enabled: number
  created_at: string
  updated_at: string
}

export interface RiskIntelRun {
  id: string
  run_type: string
  keyword_id?: string
  keyword: string
  user_id?: string
  status: 'pending' | 'running' | 'done' | 'failed'
  items_found: number
  items_new: number
  alerts_created: number
  error_msg?: string
  started_at?: string
  finished_at?: string
  created_at: string
}

export interface RiskIntelSearchResult {
  run_id: string
  keyword: string
  total_found: number
  items_new: number
  alerts_triggered: number
  duration_ms?: number
  items: RiskIntelItem[]
  error?: string
}

export interface RiskHeatmap {
  by_domain: Record<string, { count: number; critical: number; high: number; avg_score: number }>
  trend: Array<{ date: string; tariff?: number; conflict?: number; financial?: number }>
  top_markets: Array<{ market: string; count: number }>
  latest_critical: RiskIntelItem[]
  generated_at: string
}

export const riskIntelApi = {
  // 主动关键词检索
  search: (keyword: string, domain?: string, save = true) =>
    request<RiskIntelSearchResult>(`${API}/risk-intel/search`, {
      method: 'POST',
      body: JSON.stringify({ keyword, domain: domain || undefined, save }),
    }),

  // 历史情报流
  getFeed: (params?: {
    q?: string; domain?: string; severity?: string
    min_score?: number; hours?: number; source_name?: string
    jin10_only?: boolean; important_only?: boolean
    page?: number; size?: number
  }) => {
    const p = new URLSearchParams()
    if (params?.q)             p.set('q', params.q)
    if (params?.domain)        p.set('domain', params.domain)
    if (params?.severity)      p.set('severity', params.severity)
    if (params?.min_score)     p.set('min_score', String(params.min_score))
    if (params?.hours)         p.set('hours', String(params.hours))
    if (params?.source_name)   p.set('source_name', params.source_name)
    if (params?.jin10_only)    p.set('jin10_only', 'true')
    if (params?.important_only) p.set('important_only', 'true')
    if (params?.page)          p.set('page', String(params.page))
    if (params?.size)          p.set('size', String(params.size))
    return request<{ items: RiskIntelItem[]; total: number; page: number; has_next: boolean }>(
      `${API}/risk-intel/feed?${p.toString()}`
    )
  },

  // 热力图
  getHeatmap: (hours = 168) =>
    request<RiskHeatmap>(`${API}/risk-intel/heatmap?hours=${hours}`),

  // 关键词 CRUD
  listKeywords: (domain?: string) => {
    const p = domain ? `?domain=${domain}` : ''
    return request<RiskIntelKeyword[]>(`${API}/risk-intel/keywords${p}`)
  },
  addKeyword: (data: {
    keyword: string; label?: string; domain?: string
    periodic_enabled?: boolean; cron_expr?: string
  }) =>
    request<RiskIntelKeyword>(`${API}/risk-intel/keywords`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateKeyword: (id: string, data: Partial<RiskIntelKeyword>) =>
    request<RiskIntelKeyword>(`${API}/risk-intel/keywords/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  deleteKeyword: (id: string) =>
    fetch(`${API}/risk-intel/keywords/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    }),
  suggestKeywords: (markets?: string[], domains?: string[]) =>
    request<{ suggestions: Array<{ keyword: string; domain: string; source_hint: string; already_tracked: boolean }> }>(
      `${API}/risk-intel/keywords/suggest`,
      { method: 'POST', body: JSON.stringify({ markets, domains }) }
    ),
  runKeyword: (id: string) =>
    request<{ run_id: string; keyword: string; status: string }>(`${API}/risk-intel/keywords/${id}/run`, {
      method: 'POST',
    }),

  // 执行记录
  getRuns: (keyword_id?: string) => {
    const p = keyword_id ? `?keyword_id=${keyword_id}` : ''
    return request<RiskIntelRun[]>(`${API}/risk-intel/runs${p}`)
  },
  getRun: (runId: string) =>
    request<RiskIntelRun>(`${API}/risk-intel/runs/${runId}`),

  // LLM 分析管理
  getAnalyzeStatus: () =>
    request<{ total: number; done: number; pending: number; errors: number }>(
      `${API}/risk-intel/analyze/status`
    ),
  triggerAnalyze: (batchSize = 20, minScore = 0) =>
    request<{ status: string; batch_size: number; queue_before: number }>(
      `${API}/risk-intel/analyze/trigger?batch_size=${batchSize}&min_score=${minScore}`,
      { method: 'POST' }
    ),
  analyzeItem: (itemId: string) =>
    request<{ status: string; item_id: string; message: string }>(
      `${API}/risk-intel/analyze/item/${itemId}`,
      { method: 'POST' }
    ),
}
