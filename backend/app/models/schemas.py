"""Pydantic data models for 避风港 OS级合规智能体."""

import uuid
from pydantic import BaseModel, Field, computed_field
from typing import Optional, Any, Literal, List, Dict
from datetime import datetime, timezone
from enum import Enum


class SDKAgentConfig(BaseModel):
    """Agent 级别 SDK 配置覆盖

    继承全局 SDK 配置，各 Agent 可选择性覆盖以下字段。
    空字典或 null 表示全部使用全局默认值。
    """
    enabled: bool = True
    """是否启用 SDK（全局 SDK_ENABLED 的 Agent 级开关）"""
    model: Optional[str] = None
    """覆盖 SDK_MODEL，如 'claude-sonnet-4-5'"""
    max_turns: Optional[int] = None
    """覆盖 SDK_MAX_TURNS"""
    permission_mode: Optional[str] = None
    """覆盖 SDK_PERMISSION_MODE"""
    allowed_tools: Optional[List[str]] = None
    """覆盖 SDK_ALLOWED_TOOLS"""
    disallowed_tools: Optional[List[str]] = None
    """覆盖 SDK_DISALLOWED_TOOLS"""
    include_hook_events: Optional[bool] = None
    """覆盖 SDK_INCLUDE_HOOK_EVENTS"""
    skills: Optional[List[str]] = None
    """覆盖 SDK_SKILLS_JSON"""
    agents: Optional[Dict[str, Any]] = None
    """子代理定义（覆盖 SDK_AGENTS_JSON）"""


# ── Shopify 模型 ──────────────────────────────

class ShopifyAuthRequest(BaseModel):
    """发起 Shopify OAuth 授权请求"""
    shop: str = Field(description="店铺域名，如 my-store.myshopify.com", examples=["my-store.myshopify.com"])


class ShopifyCallbackParams(BaseModel):
    """Shopify OAuth 回调参数"""
    code: str = Field(description="授权码")
    shop: str = Field(description="店铺域名")
    state: str = Field(description="CSRF 校验令牌")
    timestamp: str = Field(description="时间戳")
    hmac: str = Field(description="签名")


class ShopifyShopInfo(BaseModel):
    """已连接的 Shopify 店铺信息"""
    shop: str = Field(description="店铺域名")
    scope: str = Field(default="", description="授权范围")


class ShopifyVariantInfo(BaseModel):
    """Shopify 产品变体信息"""
    id: int = Field(description="变体ID")
    title: str = Field(description="变体标题")
    price: str = Field(description="价格", examples=["29.99"])
    sku: str = Field(default="", description="SKU")
    requires_shipping: bool = Field(default=True, description="是否需要运输")


class ShopifyProductInfo(BaseModel):
    """Shopify 产品信息"""
    shopify_id: int = Field(description="Shopify 产品ID")
    title: str = Field(description="产品标题")
    handle: str = Field(description="URL handle")
    product_type: str = Field(default="", description="产品类型")
    vendor: str = Field(default="", description="供应商")
    variants: list[ShopifyVariantInfo] = Field(default_factory=list, description="产品变体")
    tags: list[str] = Field(default_factory=list, description="标签")
    body_html: str = Field(default="", description="产品描述(HTML)", examples=["<p>高品质LED灯带</p>"])


class ShopifyComplianceCheckRequest(BaseModel):
    """对 Shopify 产品发起合规检查"""
    target_market: str = Field(default="欧盟", description="目标市场", examples=["德国", "法国", "欧盟"])


class ShopifyImportRequest(BaseModel):
    """从 Shopify 导入产品的聊天请求"""
    message: str = Field(description="用户消息（含目标市场信息）")
    shop: str = Field(description="Shopify 店铺域名", examples=["my-store.myshopify.com"])
    shopify_product_id: int = Field(description="Shopify 产品ID")
    session_id: Optional[str] = Field(default=None, description="会话ID")
    target_market: str = Field(default="欧盟", description="目标市场")


class HSCode(BaseModel):
    """HS编码信息"""
    code: str = Field(description="HS编码，如 9405.40")
    description_cn: str = Field(description="中文描述")
    description_en: str = Field(description="英文描述")
    category: str = Field(description="产品类别")


class ComplianceQuery(BaseModel):
    """用户合规查询请求"""
    message: str = Field(description="用户自然语言消息")
    session_id: Optional[str] = None


class ComplianceResult(BaseModel):
    """合规检查结果"""
    hs_code: str = Field(default="", description="HS编码，如 9405.40")
    hs_description: str = Field(default="", description="HS编码对应的品名描述")
    vat_rate: float = Field(default=0.0, description="目标国家VAT税率百分比", examples=[19.0])
    certifications: list[str] = Field(default_factory=list, description="需要的认证列表，如 ['CE', 'WEEE']")
    risk_level: Literal["low", "medium", "high", "critical"] = Field(default="low", description="总体风险等级")
    risk_score: int = Field(default=20, ge=0, le=100, description="量化风险分，0-100，越高风险越大")
    risk_flags: list[str] = Field(default_factory=list, description="具体风险提示列表")
    logistics_flags: list[str] = Field(default_factory=list, description="物流与运输合规提示，如危险品、标签、申报要求")
    customs_documents: list[str] = Field(default_factory=list, description="建议准备的清关/报关文件清单")
    cultural_notes: list[str] = Field(default_factory=list, description="目标市场文化、标签、消费者保护注意事项")
    remediation_steps: list[str] = Field(default_factory=list, description="风险整改建议步骤")
    checklist: list[str] = Field(default_factory=list, description="出口待办清单，如 ['获取CE认证', '完成WEEE注册']")


class ChatResponse(BaseModel):
    """对话回复"""
    message: str = Field(description="格式化的合规报告")
    compliance_result: Optional[ComplianceResult] = None
    sources: list[str] = Field(default_factory=list, description="检索来源摘要")
    session_id: Optional[str] = None
    action_chain_id: Optional[str] = None
    # NLU 解析结果（透传给前端展示）
    intent: Optional[dict] = Field(default=None, description="MiMo NLU 解析结果: product/target_country/action/confidence")


# ── 操作链 (ActionChain) 模型 ──────────────────

class ActionNodeSchema(BaseModel):
    """操作节点 — 一次操作中的单个步骤"""
    action_id: str = Field(description="操作节点唯一ID", examples=["act_a1b2c3d4"])
    chain_id: str = Field(description="所属操作链ID", examples=["chain_session_xxx"])
    parent_id: Optional[str] = Field(default=None, description="父操作节点ID，用于构建树状链路", examples=["act_00000001"])
    type: str = Field(description="操作类型，如 nlu_parse / compliance_check / rag_retrieval", examples=["nlu_parse"])
    description_nl: str = Field(description="操作的自然语言描述，人可读", examples=["NLU 解析用户输入 → 产品=电子产品, 目标市场=德国"])
    agent: str = Field(description="执行操作的Agent名称", examples=["NLU", "ComplianceRules", "RAG"])
    input: dict = Field(default_factory=dict, description="操作输入数据")
    output: dict = Field(default_factory=dict, description="操作输出数据")
    status: str = Field(default="pending", description="操作状态: pending / running / success / failed", examples=["success"])
    timestamp: str = Field(default="", description="ISO格式时间戳", examples=["2026-05-24T10:30:00Z"])
    duration_ms: int = Field(default=0, description="操作耗时（毫秒）", examples=[152])


class ActionChainSchema(BaseModel):
    """操作链 — 一次交互中所有操作步骤的完整链路"""
    chain_id: str = Field(description="操作链唯一ID", examples=["chain_session_abc123"])
    total_actions: int = Field(default=0, description="操作节点总数")
    status: str = Field(default="empty", description="整体状态: empty / running / completed / failed / partial", examples=["completed"])
    actions: list[ActionNodeSchema] = Field(default_factory=list, description="按时间排序的操作节点列表")
    trail: list[str] = Field(default_factory=list, description="自然语言描述的操作链路（用于直接展示）", examples=[["✅ 第1步: [NLU] 解析用户输入...", "✅ 第2步: [ComplianceRules] 执行合规检查..."]])


class ActionChainSummary(BaseModel):
    """操作链摘要（列表用）"""
    chain_id: str = Field(description="操作链唯一ID")
    total_actions: int = Field(description="操作节点总数")
    status: str = Field(description="整体状态")
    trail_preview: list[str] = Field(default_factory=list, description="操作链路预览（前3条）")
    updated_at: str = Field(default="", description="最后更新时间", examples=["2026-05-24T10:30:00Z"])


# ── 事件链 (EventChain) 模型 ──────────────────

class EventNodeSchema(BaseModel):
    """事件节点 — 系统内外部发生的单个事件"""
    event_id: str = Field(description="事件唯一ID", examples=["evt_e1f2g3h4"])
    chain_id: str = Field(description="所属事件链ID", examples=["eu_regulations_2026"])
    source: str = Field(description="事件来源，如 EU_Official_Journal / DE_Regulator", examples=["EU_Official_Journal"])
    type: str = Field(description="事件类型，如 regulation_change / cert_update", examples=["regulation_change"])
    description_nl: str = Field(description="事件的自然语言描述", examples=["欧盟更新GPSR法规，新增电子产品进口附加安全要求"])
    severity: str = Field(default="medium", description="严重度: low / medium / high / critical", examples=["high"])
    payload: dict = Field(default_factory=dict, description="事件负载数据")
    tags: list[str] = Field(default_factory=list, description="事件标签", examples=[["欧盟", "GPSR", "电子产品"]])
    timestamp: str = Field(default="", description="ISO格式时间戳", examples=["2026-05-24T10:30:00Z"])


class EventChainSchema(BaseModel):
    """事件链 — 按来源/主题组织的事件序列"""
    chain_id: str = Field(description="事件链唯一ID", examples=["eu_regulations_2026"])
    total_events: int = Field(default=0, description="事件总数")
    events: list[EventNodeSchema] = Field(default_factory=list, description="按时间排序的事件列表")
    timeline: list[str] = Field(default_factory=list, description="自然语言事件时间线（用于直接展示）", examples=[["🔴 [High] 2026-05-24 欧盟更新GPSR...", "🟡 [Medium] 2026-05-23 CE认证申请流程更新..."]])


class EventCreateRequest(BaseModel):
    """创建事件请求"""
    chain_id: str = Field(description="事件链 ID，如 'eu_regulations_2026'")
    source: str = Field(description="事件来源")
    type: str = Field(description="事件类型")
    description_nl: str = Field(description="自然语言描述")
    severity: str = "medium"
    payload: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class EventChainSummary(BaseModel):
    """事件链摘要（列表用）"""
    chain_id: str = Field(description="事件链唯一ID")
    total_events: int = Field(description="事件总数")
    timeline_preview: list[str] = Field(default_factory=list, description="时间线预览（前3条）")
    updated_at: str = Field(default="", description="最后更新时间", examples=["2026-05-24T10:30:00Z"])


# ── 自然语言本地存储 (NLStore) 模型 ──────────────

class NLRecordSchema(BaseModel):
    """自然语言存储记录"""
    record_id: str = Field(description="记录唯一ID", examples=["rec_a1b2c3d4"])
    namespace: str = Field(description="所属命名空间", examples=["products", "memories"])
    key: str = Field(description="记录键名", examples=["电子产品_德国"])
    title: str = Field(description="短标题", examples=["电子产品出口德国合规要求"])
    content_nl: str = Field(description="自然语言正文（人可读）", examples=["电子产品出口德国需要CE认证、WEEE注册、RoHS合规..."])
    metadata: dict = Field(default_factory=dict, description="结构化元数据（机器可读）")
    tags: list[str] = Field(default_factory=list, description="标签", examples=[["电子产品", "德国", "CE认证"]])
    created_at: str = Field(default="", description="创建时间", examples=["2026-05-24T10:30:00Z"])
    updated_at: str = Field(default="", description="最后更新时间", examples=["2026-05-24T11:00:00Z"])


class NLRecordCreateRequest(BaseModel):
    """创建 NL 记录请求"""
    key: str = Field(description="记录键名")
    title: str = Field(description="标题")
    content_nl: str = Field(description="自然语言内容")
    metadata: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class NLRecordUpdateRequest(BaseModel):
    """更新 NL 记录请求（所有字段可选）"""
    title: Optional[str] = Field(default=None, description="新标题")
    content_nl: Optional[str] = Field(default=None, description="新自然语言内容")
    metadata: Optional[dict] = Field(default=None, description="新结构化元数据")
    tags: Optional[list[str]] = Field(default=None, description="新标签列表")


class NLSearchResult(BaseModel):
    """搜索单条结果"""
    namespace: str = Field(description="所属命名空间")
    key: str = Field(description="记录键名")
    title: str = Field(description="记录标题")
    content_preview: str = Field(description="内容预览（前150字符）")
    tags: list[str] = Field(default_factory=list, description="标签")
    score: int = Field(default=0, description="匹配分数（关键词命中数）")
    updated_at: str = Field(default="", description="最后更新时间")


class NLSummaryItem(BaseModel):
    """Namespace 列表摘要项"""
    key: str = Field(description="记录键名")
    title: str = Field(description="记录标题")
    tags: list[str] = Field(default_factory=list, description="标签")
    updated_at: str = Field(default="", description="最后更新时间")


# ── 会话历史 (Session) 模型 ──────────────────────

class SessionMessage(BaseModel):
    """单条会话消息"""
    id: str = Field(description="消息唯一 ID")
    role: str = Field(description="角色: user | assistant")
    content: str = Field(description="消息内容（Markdown 格式化报告 or 用户输入）")
    compliance_result: Optional[ComplianceResult] = Field(default=None, description="合规检查结果（仅 assistant 消息）")
    intent: Optional[dict] = Field(default=None, description="NLU 解析结果")
    sources: list[str] = Field(default_factory=list, description="RAG 来源列表")
    created_at: int = Field(description="Unix 时间戳（秒）")


class SessionSummary(BaseModel):
    """会话摘要（列表页用）"""
    id: str = Field(description="会话 ID")
    title: str = Field(description="会话标题（取自首条用户消息）")
    created_at: int = Field(description="创建时间（Unix 秒）")
    updated_at: int = Field(description="最后更新时间（Unix 秒）")
    message_count: int = Field(default=0, description="消息总条数")
    preview: str = Field(default="", description="最后一条用户消息预览（前 60 字）")


class Session(BaseModel):
    """完整会话（含全部消息）"""
    id: str
    title: str
    created_at: int
    updated_at: int
    messages: list[SessionMessage] = Field(default_factory=list)


# ── OS级智能体：事件模型 ──────────────────────────────

class EventCategory(str, Enum):
    """8类事件体系（对齐架构设计§2.2 + 指南§6.10.1）"""
    lifecycle = "lifecycle"
    compliance = "compliance"
    certification = "certification"
    order = "order"
    regulation = "regulation"
    risk_alert = "risk_alert"
    system = "system"
    user_action = "user_action"


class DataSourceInfo(BaseModel):
    """数据血缘信息（存储层级映射）"""
    read: List[str] = Field(default_factory=list, description="读取的数据源，如 ['L0:hs_codes', 'L2:product_meta']")
    write: List[str] = Field(default_factory=list, description="写入的数据源，如 ['L2:product_memory', 'L5:event_chain']")


class EventRecord(BaseModel):
    """标准化事件记录（OS级全局事件总线核心数据结构）"""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12], description="事件唯一ID")
    type: str = Field(description="事件类型，如 'product:created'")
    category: EventCategory = Field(default=EventCategory.system, description="事件分类（8类）")
    source: str = Field(description="事件来源，如 'shopify:webhook', 'scheduler', 'user'")
    product_id: Optional[str] = Field(default=None, description="关联产品ID")
    business_stage: Optional[str] = Field(default=None, description="所属业务阶段（1-10）")
    data: Dict[str, Any] = Field(default_factory=dict, description="事件载荷")
    data_sources: DataSourceInfo = Field(default_factory=DataSourceInfo, description="数据血缘")
    severity: str = Field(default="low", description="严重级别: low/medium/high/critical")
    error: Optional[str] = Field(default=None, description="错误信息（失败时）")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="创建时间")


class EventDefinition(BaseModel):
    """事件类型定义（配置文件驱动，QAAgent管理）"""
    event_code: str = Field(description="事件编码（唯一标识），如 'product:created'")
    event_name: str = Field(description="事件名称")
    business_stage: str = Field(description="所属业务阶段")
    category: EventCategory = Field(default=EventCategory.lifecycle, description="事件分类")
    trigger_condition: str = Field(description="触发条件")
    related_worker: str = Field(default="", description="关联Worker")
    severity: str = Field(default="low", description="严重级别")
    notify_strategy: List[str] = Field(default_factory=lambda: ["dashboard"], description="通知策略")
    tools: List[str] = Field(default_factory=list, description="Worker 使用的工具列表")
    skills: List[str] = Field(default_factory=list, description="Worker 使用的技能列表")
    agent_action: str = Field(default="", description="Agent 执行指令描述")
    description: str = Field(default="", description="事件描述")
    data_schema: Optional[Dict[str, Any]] = Field(default=None, description="事件数据Schema")
    data_sources: DataSourceInfo = Field(default_factory=DataSourceInfo, description="数据血缘")
    config_file: Optional[str] = Field(default=None, description="对应事件配置文件路径")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EventCreateOSRequest(BaseModel):
    """创建OS级事件请求"""
    type: str = Field(description="事件类型")
    category: EventCategory = Field(default=EventCategory.system)
    source: str = Field(description="事件来源")
    product_id: Optional[str] = None
    business_stage: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    severity: str = "low"


# ── OS级智能体：Worker模型 ──────────────────────────────

class WorkerDefinition(BaseModel):
    """Worker类型定义（配置文件驱动，QAAgent管理）

    新增 SDK 执行配置:
      - sdk_enabled: 是否走 Claude Agent SDK 执行
      - sdk_agent_id: 选用的 Agent 配置 ID（走 SDK 时使用其 system_prompt）
    """
    worker_code: str = Field(description="Worker编码（唯一标识）")
    worker_name: str = Field(description="Worker名称")
    business_stage: str = Field(description="所属业务阶段")
    description: str = Field(description="职责描述")
    available_skills: List[str] = Field(default_factory=list, description="可用Skills列表")
    priority: int = Field(default=5, ge=1, le=5, description="优先级（1-5，数字越小越高）")
    resource_limit: str = Field(default="", description="资源限制")
    max_concurrent: int = Field(default=1, description="最大并发数")
    timeout: int = Field(default=300, description="执行超时时间（秒）")
    status: str = Field(default="idle", description="当前状态: idle/busy/error")
    sdk_enabled: bool = Field(default=True, description="是否使用 Claude Agent SDK 执行任务")
    sdk_agent_id: Optional[str] = Field(default=None, description="SDK 执行时使用的 Agent 配置 ID")
    config_file: Optional[str] = Field(default=None, description="对应 Worker 配置文件路径")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class WorkerStatus(BaseModel):
    """Worker运行时状态"""
    worker_code: str
    worker_name: str
    status: str = "idle"
    current_task: Optional[str] = None
    last_heartbeat: Optional[str] = None
    tasks_completed: int = 0
    tasks_failed: int = 0





# ── OS级智能体：产品模型 ──────────────────────────────

class ProductLifecycleStage(str, Enum):
    """产品生命周期8阶段状态机"""
    CONCEPT = "concept"
    DESIGN = "design"
    SOURCING = "sourcing"
    READY = "ready"
    ACTIVE = "active"
    FULFILLING = "fulfilling"
    AFTERSALE = "aftersale"
    END = "end"


class ProductCreateRequest(BaseModel):
    """创建产品请求"""
    name: str = Field(description="产品名称")
    product_type: str = Field(default="", description="产品类型")
    target_markets: List[str] = Field(default_factory=list, description="目标市场列表")
    hs_code: str = Field(default="", description="HS编码")
    vendor: str = Field(default="", description="供应商")
    tags: List[str] = Field(default_factory=list, description="标签")


class ProductUpdateRequest(BaseModel):
    """更新产品请求"""
    name: Optional[str] = None
    product_type: Optional[str] = None
    target_markets: Optional[List[str]] = None
    hs_code: Optional[str] = None
    vendor: Optional[str] = None
    tags: Optional[List[str]] = None


class ProductLifecycleUpdate(BaseModel):
    """产品生命周期状态变更请求"""
    lifecycle_stage: ProductLifecycleStage = Field(description="新生命周期阶段")
    reason: str = Field(default="", description="变更原因")


class ProductInfo(BaseModel):
    """产品信息（含生命周期状态）"""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = Field(description="产品名称")
    product_type: str = Field(default="", description="产品类型")
    target_markets: List[str] = Field(default_factory=list)
    hs_code: str = Field(default="")
    vendor: str = Field(default="")
    tags: List[str] = Field(default_factory=list)
    lifecycle_stage: ProductLifecycleStage = Field(default=ProductLifecycleStage.CONCEPT)
    business_stage: Optional[str] = None
    compliance_status: str = Field(default="pending", description="合规状态: pending/checking/passed/failed")
    risk_level: str = Field(default="low")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # ── 计算字段：健康度 ───────────────────────────
    @computed_field
    @property
    def health_score(self) -> int:
        """基于合规状态和风险等级计算健康度（0-100）"""
        score_map = {"passed": 90, "checking": 60, "pending": 30, "failed": 10}
        risk_map = {"low": 0, "medium": -20, "high": -40, "critical": -60}
        base = score_map.get(self.compliance_status, 50)
        penalty = risk_map.get(self.risk_level, 0)
        return max(0, min(100, base + penalty))

    # ── 计算字段：认证列表 ───────────────────────────
    @computed_field
    @property
    def certifications(self) -> List[Dict[str, str]]:
        """基于元数据或目标市场生成认证列表"""
        stored = self.metadata.get("certifications", [])
        if stored:
            return stored
        # 从目标市场推断认证要求
        market_certs = {
            "eu": [{"name": "CE", "status": "checking"}, {"name": "RoHS", "status": "checking"}],
            "de": [{"name": "WEEE", "status": "checking"}],
            "uk": [{"name": "UKCA", "status": "checking"}],
            "us": [{"name": "FDA", "status": "checking"}],
            "ca": [{"name": "CSA", "status": "checking"}],
            "jp": [{"name": "PSE", "status": "checking"}],
            "cn": [{"name": "CCC", "status": "checking"}],
            "kr": [{"name": "KC", "status": "checking"}],
        }
        seen = set()
        result = []
        for m in self.target_markets:
            code = m[:2].lower()
            for prefix, certs in market_certs.items():
                if prefix in code or prefix in m.lower():
                    for c in certs:
                        if c["name"] not in seen:
                            seen.add(c["name"])
                            result.append(c)
        return result


# ── OS级智能体：合规流水线 ──────────────────────────────

# ── OS级智能体：合规流水线（CheckResult/RecommendAction/CompliancePipelineResult 已移除，对应 compliance_flow.py 已删除）──


# ── OS级智能体：事件订阅 ──────────────────────────────

class SubscriptionFilter(BaseModel):
    """事件订阅过滤器"""
    product_ids: Optional[List[str]] = Field(default=None, description="产品ID列表（精准订阅）")
    tags: Optional[List[str]] = Field(default=None, description="标签列表（批量订阅）")
    event_types: Optional[List[str]] = Field(default=None, description="事件类型列表")
    severity: Optional[List[str]] = Field(default=None, description="严重级别过滤")
    condition_expr: Optional[str] = Field(default=None, description="条件表达式（条件订阅）")


class EventSubscriptionRequest(BaseModel):
    """创建事件订阅请求"""
    subscriber: str = Field(description="订阅者标识（WebSocket连接ID/Webhook URL）")
    subscription_type: str = Field(default="precise", description="订阅类型: precise/batch/global/conditional")
    filter: SubscriptionFilter = Field(default_factory=SubscriptionFilter)
    channels: List[str] = Field(default_factory=lambda: ["websocket"])


# ── OS级智能体：通知 ──────────────────────────────

class NotificationPayload(BaseModel):
    """通知payload（含深度链接，对齐指南§6.9.5）"""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    type: str = Field(description="通知类型: compliance_check/certification_expiry/risk_alert/regulation_change/system_notice")
    title: str
    message: str
    product_id: Optional[str] = Field(default=None, description="深度链接跳转目标")
    stage: Optional[str] = Field(default=None, description="业务阶段")
    severity: str = Field(default="low")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_read: bool = Field(default=False)


# ── OS级智能体：RAG管理 ──────────────────────────────

class RAGStatusResponse(BaseModel):
    """RAG系统状态"""
    collections: List[str] = Field(default_factory=list)
    total_documents: int = 0
    embedding_model: str = ""
    chroma_path: str = ""
    status: str = "healthy"


class RAGSearchRequest(BaseModel):
    """RAG语义搜索请求"""
    query: str = Field(description="搜索查询")
    market: Optional[str] = Field(default=None, description="目标市场")
    top_k: int = Field(default=5, description="返回结果数")


class RAGSearchResult(BaseModel):
    """RAG搜索结果"""
    content: str
    source: str = ""
    market: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── OS级智能体：CLI命令 ──────────────────────────────

class CLICommandRequest(BaseModel):
    """CLI命令执行请求"""
    command: str = Field(description="CLI命令，如 'astra status'")
    args: Dict[str, Any] = Field(default_factory=dict, description="命令参数")


class CLICommandResult(BaseModel):
    """CLI命令执行结果"""
    command: str
    success: bool
    output: str = ""
    error: Optional[str] = None
    duration_ms: int = 0


class CLICommand(BaseModel):
    """CLI命令定义（前端自动补全用）"""
    cmd: str = Field(description="命令名称，如 /help")
    desc: str = Field(description="命令描述")
    usage: Optional[str] = Field(default=None, description="用法示例")
    category: Optional[str] = Field(default=None, description="命令分类")


class CLICompleteResponse(BaseModel):
    """CLI补全响应"""
    suggestions: List[CLICommand] = Field(default_factory=list)
    prefix: str = Field(default="")


class CLIHistoryResponse(BaseModel):
    """CLI历史记录响应"""
    history: List[CLICommandResult] = Field(default_factory=list)


class MagicCommandRequest(BaseModel):
    """魔法命令执行请求"""
    command: str = Field(description="魔法命令，如 '/clear', '/retry'")
    session_id: Optional[str] = None


# ── OS级智能体：TokenJuice ──────────────────────────────

class CompressedData(BaseModel):
    """TokenJuice压缩结果"""
    original: str = Field(description="原始数据")
    compressed: str = Field(description="压缩后数据")
    ratio: float = Field(default=1.0, description="压缩率（压缩后/原始）")
    tokens_saved: int = Field(default=0, description="节省的token数")


# ── OS级智能体：模型路由 ──────────────────────────────

class ModelConfig(BaseModel):
    """模型配置"""
    role: str = Field(description="模型角色: reasoning/fast/vision/embedding")
    provider: str = Field(description="提供商: anthropic/openai/local")
    model: str = Field(description="模型名称")
    api_key_env: str = Field(default="", description="API Key环境变量名")
    base_url: str = Field(default="", description="API 基础地址（可选）")
    max_tokens: int = Field(default=4096)
    temperature: float = Field(default=0.7)
    top_p: float = Field(default=0.9)


class ModelRouteRequest(BaseModel):
    """模型路由请求"""
    task_type: str = Field(description="任务类型")
    timeout: int = Field(default=30, description="超时（秒）")


# ── OS级智能体：Pipeline合规流水线 ──────────────────────

class PipelineStageStatus(BaseModel):
    """单阶段合规状态"""
    stage_number: int = Field(description="阶段编号（1-10）")
    stage_name: str = Field(description="阶段名称")
    pass_rate: float = Field(default=0.0, description="通过率")
    total_products: int = Field(default=0, description="该阶段产品总数")
    passed_products: int = Field(default=0, description="通过数")
    risk_products: int = Field(default=0, description="风险产品数")
    pending_actions: int = Field(default=0, description="待办数")
    status: str = Field(default="unknown", description="阶段状态: healthy/warning/critical/unknown")


class PipelineHealthResponse(BaseModel):
    """流水线整体健康度"""
    overall_score: float = Field(default=0.0, description="整体健康度 0-100")
    stages: List[PipelineStageStatus] = Field(default_factory=list)
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── OS级智能体：自定义指标 ──────────────────────────────

# ── OS级智能体：自定义指标（CustomMetricDefinition/MetricValue 已移除，无外部引用）──


# ── OS级智能体：Workflow ──────────────────────────────

# ── OS级智能体：Workflow（WorkflowStep/WorkflowDefinition 已移除，无外部引用）──


# ── OS级智能体：Agent通信 ──────────────────────────────

class AgentMessage(BaseModel):
    """Agent间通信消息"""
    from_agent: str = Field(description="发送者Agent")
    to_agent: str = Field(description="接收者Agent")
    msg_type: str = Field(description="消息类型: task_assign/result_report/status_query/chat")
    task_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── OS级智能体：安全沙箱 ──────────────────────────────

class GuardResult(BaseModel):
    """安全守卫检查结果"""
    allowed: bool = True
    reason: str = ""
    need_confirm: bool = False



