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
  risk_level: 'low' | 'medium' | 'high' | 'critical'
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

/** 会话消息 */
export interface SessionMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  compliance_result?: ComplianceResult
  intent?: Record<string, unknown>
  sources: string[]
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

// ── SSE 流式对话类型 ──────────────────────────

/** SSE 连接状态 */
export type ConnectionStatus = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'error'

/** 执行计划步骤 */
export interface PlanStep {
  id: string
  action: string
  expected_result?: string
  status: 'pending' | 'running' | 'done' | 'failed'
  skill?: string
  duration_ms?: number
}

/** 操作建议 */
export interface Action {
  id: string
  label: string
  description?: string
  skill?: string
  confidence?: number
  expected_result?: string
  risk_level?: 'low' | 'medium' | 'high' | 'critical'
  status?: 'pending' | 'confirmed' | 'executing' | 'done' | 'skipped'
}

/** Skill执行结果 */
export interface SkillResult {
  output?: Record<string, unknown>
  summary?: string
  [key: string]: unknown
}

/** SSE事件: token */
export interface StreamEventToken {
  type: 'token'
  content: string
}

/** SSE事件: skill_start */
export interface StreamEventSkillStart {
  type: 'skill_start'
  skill: string
  args: Record<string, unknown>
}

/** SSE事件: skill_end */
export interface StreamEventSkillEnd {
  type: 'skill_end'
  skill: string
  result: SkillResult
  duration_ms?: number
  status?: 'success' | 'error'
}

/** SSE事件: thinking */
export interface StreamEventThinking {
  type: 'thinking'
  content: string
  depth?: number
}

/** SSE事件: plan */
export interface StreamEventPlan {
  type: 'plan'
  steps: PlanStep[]
  current: number
}

/** SSE事件: action_card */
export interface StreamEventActionCard {
  type: 'action_card'
  actions: Action[]
}

/** SSE事件: error */
export interface StreamEventError {
  type: 'error'
  code: string
  message: string
  recoverable?: boolean
}

/** SSE事件: done */
export interface StreamEventDone {
  type: 'done'
  finish_reason?: string
  usage?: Record<string, unknown>
}

/** SSE事件联合类型 */
export type StreamEvent =
  | StreamEventToken
  | StreamEventSkillStart
  | StreamEventSkillEnd
  | StreamEventThinking
  | StreamEventPlan
  | StreamEventActionCard
  | StreamEventError
  | StreamEventDone

/** 用户消息（对话区展示） */
export interface ChatUserMessage {
  kind: 'user'
  id: string
  content: string
  timestamp: number
}

/** AI流式回复（含全部SSE事件） */
export interface ChatAssistantMessage {
  kind: 'assistant'
  id: string
  events: StreamEvent[]
  /** 聚合的token文本（从events中提取） */
  textContent: string
  isStreaming: boolean
  timestamp: number
}

/** 对话消息联合类型 */
export type ChatMessage = ChatUserMessage | ChatAssistantMessage

// ── 业务流程阶段类型 ────────────────────────────

/** 10阶段合规状态（同时兼容后端 PipelineStageStatus 格式） */
export interface PipelineStage {
  id: string
  stage_number?: number     // 后端字段，可选
  name: string
  order: number
  description?: string
  pass_rate: number        // 0-100（前端显示）
  risk_products: number
  pending_tasks: number
  status?: string           // healthy/warning/critical/unknown
  checklist?: { item: string; passed: boolean }[]   // 后端暂无，可选
  products?: { id: string; name: string; status: string }[]
}

// ── 产品类型 ─────────────────────────────────────

/** 产品生命周期阶段（对齐后端 ProductLifecycleStage） */
export type ProductLifecycle = 'concept' | 'design' | 'sourcing' | 'ready' | 'active' | 'fulfilling' | 'aftersale' | 'end'

/** 产品信息 */
export interface Product {
  id: string
  name: string
  target_markets: string[]
  lifecycle_stage: ProductLifecycle
  health_score?: number
  compliance_status: 'passed' | 'failed' | 'checking' | 'pending'
  certifications?: { name: string; status: string }[]
  hs_code?: string
  vendor?: string
  created_at?: string
  updated_at?: string
}

// ── 对话配置类型 ─────────────────────────────────

/** 对话配置（对应 GET/PUT /api/v1/chat/config） */
export interface ChatConfigData {
  agent_id?: string
  tools?: string[]
  skills?: string[]
  pipeline_mode?: string
  model_role?: string
}
