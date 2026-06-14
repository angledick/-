/** HS编码信息 */
export interface HSCode {
  code: string
  description_cn: string
  description_en: string
  category: string
}

/** 合规查询请求 */
export interface ComplianceQuery {
  message: string
  session_id?: string
}

/** Chat API 请求体 */
export type ChatPayload = ComplianceQuery

/** 合规检查结果 */
export interface ComplianceResult {
  hs_code: string
  hs_description: string
  vat_rate: number
  certifications: string[]
  risk_level: 'low' | 'medium' | 'high'
  risk_score?: number
  risk_flags: string[]
  logistics_flags?: string[]
  customs_documents?: string[]
  cultural_notes?: string[]
  remediation_steps?: string[]
  checklist: string[]
}

/** 对话回复 */
export interface ChatResponse {
  message: string
  compliance_result?: ComplianceResult
  sources?: string[]
  session_id?: string
  /** 操作链ID，可用于前端回溯展示决策链路 */
  action_chain_id?: string
  intent?: Record<string, unknown>
  browser_result?: BrowserResult
  conflicts?: ConflictResult[]
}

/** 聊天消息 */
export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  compliance?: ComplianceResult | null
  sources?: string[]
}

// ── 操作链 (ActionChain) 类型 ──────────────────

/** 操作节点 */
export interface ActionNode {
  action_id: string
  chain_id: string
  parent_id?: string
  type: string
  description_nl: string
  agent: string
  input: Record<string, unknown>
  output: Record<string, unknown>
  status: 'pending' | 'running' | 'success' | 'failed'
  timestamp: string
  duration_ms: number
}

/** 操作链 */
export interface ActionChain {
  chain_id: string
  total_actions: number
  status: 'empty' | 'running' | 'completed' | 'failed' | 'partial'
  actions: ActionNode[]
  trail: string[]
}

/** 操作链摘要（列表用） */
export interface ActionChainSummary {
  chain_id: string
  total_actions: number
  status: string
  trail_preview: string[]
  updated_at: string
}

export interface BrowserResult {
  ok: boolean
  action_type: string
  url?: string | null
  title?: string | null
  data?: unknown[] | null
  error?: string | null
  raw?: Record<string, unknown> | null
}

export interface AgentStatus {
  agent: string
  status: 'pending' | 'running' | 'complete' | 'error'
  result?: Record<string, unknown>
  error?: string
  timestamp?: number
}

export interface ConflictResult {
  type: 'hs_code' | 'vat_rate' | 'certification' | 'risk_level' | string
  sources: Record<string, string>
  resolution: string
  reason: string
}

// ── 事件链 (EventChain) 类型 ──────────────────

/** 事件节点 */
export interface EventNode {
  event_id: string
  chain_id: string
  source: string
  type: string
  description_nl: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  payload: Record<string, unknown>
  tags: string[]
  timestamp: string
}

/** 事件链 */
export interface EventChain {
  chain_id: string
  total_events: number
  events: EventNode[]
  timeline: string[]
}

/** 事件创建请求 */
export interface EventCreateRequest {
  chain_id: string
  source: string
  type: string
  description_nl: string
  severity?: string
  payload?: Record<string, unknown>
  tags?: string[]
}

/** 事件链摘要（列表用） */
export interface EventChainSummary {
  chain_id: string
  total_events: number
  timeline_preview: string[]
  updated_at: string
}

// ── 自然语言存储 (NLStore) 类型 ──────────────

/** 自然语言存储记录 */
export interface NLRecord {
  record_id: string
  namespace: string
  key: string
  title: string
  content_nl: string
  metadata: Record<string, unknown>
  tags: string[]
  created_at: string
  updated_at: string
}

/** 创建 NL 记录请求 */
export interface NLRecordCreateRequest {
  key: string
  title: string
  content_nl: string
  metadata?: Record<string, unknown>
  tags?: string[]
}

/** NL 搜索单条结果 */
export interface NLSearchResult {
  namespace: string
  key: string
  title: string
  content_preview: string
  tags: string[]
  score: number
  updated_at: string
}

/** Namespace 列表摘要项 */
export interface NLSummaryItem {
  key: string
  title: string
  tags: string[]
  updated_at: string
}

// ── Shopify 类型 ──────────────────────────────

/** Shopify 产品变体 */
export interface ShopifyVariantInfo {
  id: number
  title: string
  price: string
  sku: string
  requires_shipping: boolean
}

/** Shopify 产品信息 */
export interface ShopifyProductInfo {
  shopify_id: number
  title: string
  handle: string
  product_type: string
  vendor: string
  variants: ShopifyVariantInfo[]
  tags: string[]
  /** 产品描述(HTML) */
  body_html: string
}

/** 已连接的 Shopify 店铺 */
export interface ShopifyShopInfo {
  shop: string
  scope: string
}

/** Shopify OAuth 授权请求 */
export interface ShopifyAuthRequest {
  shop: string
}

/** Shopify 产品合规检查请求 */
export interface ShopifyComplianceCheckRequest {
  target_market: string
}

/** 从 Shopify 导入产品的聊天请求 */
export interface ShopifyImportRequest {
  message: string
  shop: string
  shopify_product_id: number
  session_id?: string
  target_market: string
}

// ── 风险监控类型 ──────────────────────────────

/** 风险预警 */
export interface RiskAlert {
  alert_id: string
  alert_type: 'regulation_change' | 'market_hotspot' | 'product_impacted'
  severity: 'low' | 'medium' | 'high' | 'critical'
  title: string
  description: string
  affected_products: string[]
  affected_markets: string[]
  source: string
  source_url: string
  dismissed: boolean
  created_at: string
}

/** 市场事件 */
export interface MarketEvent {
  event_id: string
  market: string
  has_change: boolean
  summary: string
  affected_categories: string[]
  severity: string
  source: string
  source_url: string
  key_points: string[]
  timestamp: string
}

/** 仪表盘数据 */
export interface DashboardData {
  total_products: number
  risk_distribution: Record<'low' | 'medium' | 'high' | 'critical', number>
  recent_alerts: RiskAlert[]
  active_markets: string[]
  health_score: number
  trend: { date: string; checks: number }[]
}

/** 市场监控状态 */
export interface MarketStatus {
  last_scan: string
  active_alerts: number
  markets: { code: string; alerts: number }[]
}

/** 预警列表响应 */
export interface AlertsResponse {
  alerts: RiskAlert[]
  page: number
  size: number
}

// ── 会话历史 (Session) 类型 ──────────────────

export interface PlanStep {
  id: string
  action: string
  expected_result?: string
  status: 'pending' | 'running' | 'done' | 'failed'
  skill?: string
  duration_ms?: number
}

export interface StreamAction {
  id: string
  label: string
  description?: string
  skill?: string
  confidence?: number
  expected_result?: string
  risk_level?: 'low' | 'medium' | 'high'
  status?: 'pending' | 'confirmed' | 'executing' | 'done' | 'skipped'
}

export type StreamEvent =
  | { type: 'token'; content: string }
  | { type: 'skill_start'; skill: string; args: Record<string, unknown> }
  | {
      type: 'skill_end'
      skill: string
      result: Record<string, unknown>
      duration_ms?: number
      status?: 'success' | 'error'
    }
  | { type: 'thinking'; content: string; depth?: number }
  | { type: 'plan'; steps: PlanStep[]; current: number }
  | { type: 'action_card'; actions: StreamAction[] }
  | { type: 'agent_status'; agents: AgentStatus[] }
  | { type: 'conflict'; conflicts: ConflictResult[] }
  | { type: 'browser_result'; result: BrowserResult }
  | { type: 'error'; code: string; message: string; recoverable?: boolean }
  | {
      type: 'done'
      finish_reason?: string
      usage?: Record<string, unknown>
      message?: string
      compliance_result?: ComplianceResult
      intent?: Record<string, unknown>
      browser_result?: BrowserResult
      action_chain_id?: string
      session_id?: string
      sources?: string[]
    }

/** 会话消息 */
export interface SessionMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  compliance_result?: ComplianceResult
  intent?: Record<string, unknown>
  browser_result?: BrowserResult
  action_chain_id?: string
  conflicts?: ConflictResult[]
  sources: string[]
  stream_events?: StreamEvent[]
  streaming?: boolean
  created_at: number
}

/** 会话摘要（列表页） */
export interface SessionSummary {
  id: string
  title: string
  created_at: number
  updated_at: number
  message_count: number
  preview: string
}

/** 完整会话（含全部消息） */
export interface Session extends SessionSummary {
  messages: SessionMessage[]
}

// ── 知识库导入 (Knowledge Import) 类型 ─────────────

/** 市场代码（用于知识库 PDF/URL 导入） */
export type KnowledgeMarket = 'eu' | 'us' | 'jp' | 'kr' | 'cn' | 'custom'

/** 已导入的知识库文档 */
export interface KnowledgeDoc {
  id: string
  user_id: string
  doc_type: 'pdf' | 'url'
  name: string
  source_url: string
  market: KnowledgeMarket
  status: 'indexing' | 'done' | 'error'
  chunk_count: number
  error_msg: string
  /** Unix epoch **秒**（不是毫秒）— 与后端 `int(time.time())` 对齐 */
  created_at: number
  /** Unix epoch 秒 */
  updated_at: number
}

/** 知识库统计 */
export interface KnowledgeStats {
  total_docs: number
  total_chunks: number
  done_count: number
  indexing_count: number
  error_count: number
  market_distribution: Record<string, number>
  total_vectors: number
}

/** 语义搜索请求 */
export interface KnowledgeSearchRequest {
  query: string
  market?: KnowledgeMarket | ''
  top_k?: number
}

/** 语义搜索单条命中（来自 ChromaDB） */
export interface KnowledgeSearchHit {
  text: string
  score: number
  market: string
  regulation_name: string
  source_url: string
  page_hint: string
  doc_id: string
}

/** 语义搜索响应 */
export interface KnowledgeSearchResponse {
  query: string
  results: KnowledgeSearchHit[]
  count: number
}

/** PDF 上传 / URL 导入 异步响应 */
export interface KnowledgeImportAck {
  doc_id: string
  name?: string
  status: 'indexing'
  message: string
}
