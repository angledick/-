# 后端 API 文档

> 版本: v1.2 | 更新: 2026-06-14
> 技术栈: FastAPI + Pydantic v2 | 系统版本: 4.0.0
> 基础路径: `/api/v1` | API 文档: 启动后访问 `/docs` (Swagger UI)
> 架构变更: API 文件按领域拆分重构（Phase 1+P3.6），启动流程4阶段精简
> v1.2 新增: Phase 3.7 风险情报引擎 + Phase 3.8 生命周期管理 + Phase 3.9 LLM 调度 + 飞书集成
> 详见: 今日开发文档 (2026-06-14) — 三库整合迁移完成

---

## 一、总览

### 1.1 路由注册结构

API 路由按阶段/功能分组注册在 `backend/app/main.py`中：

| 注册阶段 | 导入来源 | 包含模块 |
|----------|----------|----------|
| 原有路由 | `chains, shopify, risk, sessions, auth, users, agent_config, agent_crud, agent_extensions, sdk_sessions` | 认证、Agent CRUD+扩展+执行、会话、Shopify |
| OS级智能体 | `products, events, pipeline, notifications, cli, rag, event_config, worker_config` | 产品、事件、流水线、通知、CLI、RAG |
| Phase 2 | `memory, metrics, tools, chat_stream, agent_tasks, proactive` | 记忆树、指标、Tools、SSE流式对话、任务管理、主动引擎 |
| Phase 3 | `skills, plugins, integrations, oauth, channels, sync, code_security.*` | Skills、插件、连接管理、OAuth、频道、同步、编码安全 |
| Phase 3.5 | `knowledge` | 知识库 |
| Phase 3.6 | `knowledge_import, news_monitor` | RAG知识导入、新闻监控 |
| Phase 4 | `admin_rbac, admin_approvals, admin_config, admin_reports` | RBAC、审批、后台配置、报表 |
| Phase 3.7 | `risk_intel` | 风险情报引擎（采集/分析/热力图/关键词） |
| Phase 3.8 | `suppliers, contracts, payment_channels, logistics, customs, orders` | 生命周期管理（供应商/合同/支付/物流/报关/订单） |
| Phase 3.9 | `llm_dispatch` | LLM 决策调度网关 |
| 飞书集成 | `feishu` | 飞书消息/审批/事件集成 |
| 独立 | `scheduler_config` | 定时任务管理 |
| 独立 | `model_config` | 模型配置 |

### 1.2 启动生命周期

```
main.py:on_startup()
  ├─ Phase 1: 基础设施 + 配置预绑定 ──────────────
  │   ├─ init_admin_if_empty() → 创建默认管理员
  │   ├─ get_event_registry() → 加载事件注册表
  │   ├─ get_worker_registry() → 加载 Worker 注册表
  │   └─ get_agent_initializer().scan_and_load() → Agent 文件驱动初始化
  │
  ├─ Phase 2: 核心组件 ──────────────────────────
  │   ├─ get_qa_agent().set_registries()
  │   ├─ get_manager_agent()
  │   └─ bus.on_all(manager.on_event)  # 事件驱动中枢
  │
  ├─ Phase 3: 扩展组件 ──────────────────────────
  │   ├─ get_oauth_manager() → OAuth 管理器
  │   ├─ get_auto_pull_engine().start() → 自动拉取引擎
  │   ├─ get_channel_registry() → 频道注册表
  │   ├─ get_security_sandbox() → 安全沙箱
  │   ├─ get_skill_registry/executor/recommender()
  │   ├─ get_plugin_manager() → 插件管理器
  │   ├─ get_rbac_manager/approval_engine/operation_guard()
  │   ├─ get_proactive_engine() → 主动引擎
  │   └─ get_risk_intel_engine() → 风险情报引擎
  │
  ├─ Phase 4: 调度器 ─────────────────────────────
  │   └─ start_scheduler() → 启动 APScheduler
  │
  └─ Phase 5: 外部事件监听器 ─────────────────
      ├─ FeishuListener → 飞书事件监听
      └─ ShopifyEventListener → Shopify 事件监听
```

### 1.3 认证体系

| 认证方式 | 说明 | 依赖 |
|----------|------|------|
| `Bearer Token` (JWT) | 标准认证，`Authorization: Bearer <token>` | `core/auth.py` |
| `get_current_user` | 解析 Token 返回用户 dict | 所有受保护端点 |
| `require_admin` | 在 get_current_user 基础上检查 role==admin | 管理端点 |
| `_optional_user` | Token 可选，无 Token 不报错 | chat_stream.py 对话端点 |
| `OAuth2PasswordForm` | Swagger UI 兼容登录 | `/auth/token` |

---

## 二、Agent 配置 API（按领域拆分）

Agent 配置 API 已按功能拆分为 3 个独立文件，端点路径不变：

| 文件 | 行数 | 负责模块 | 标签 |
|------|------|---------|------|
| `agent_crud.py` | 207 | Agent 增删改查 + 启用/禁用 | `agent-config` |
| `agent_extensions.py` | 130 | Agent-Skills/Tools/OAuth 关联 + 运行时状态 | `agent-extensions` |
| `agent_config.py` | — | Agent 身份对话执行 (chat/chat/stream) | — |

**存储:**
- Agent 核心配置: `data/agents/*.md`（文件驱动，启动时扫描） + SQLite (兼容旧流程)
- Agent 扩展关联: `data/agents/extensions.json`（原 `data/config/agent_extensions.json`）
- Agent 初始化器: `core/agent_initializer.py` → `scan_and_load()`

---

### 2.1 Agent CRUD（agent_crud.py）

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/api/v1/agents` | Agent 列表（含 system_prompt 预览 80字） | Bearer |
| GET | `/api/v1/agents/{agent_id}` | Agent 完整配置 | Bearer |
| POST | `/api/v1/agents` | 新建 Agent | Admin |
| PUT | `/api/v1/agents/{agent_id}` | 更新 Agent | Admin |
| DELETE | `/api/v1/agents/{agent_id}` | 删除（内置 Agent 不可删） | Admin |
| PUT | `/api/v1/agents/{agent_id}/toggle` | 启用/禁用 | Admin |

### 2.2 Agent 扩展关联（agent_extensions.py）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/PUT | `/api/v1/agents/{agent_id}/skills` | Skills 关联 (List[str]) |
| GET/PUT | `/api/v1/agents/{agent_id}/tools` | Tools 关联 (List[str]) |
| GET/PUT | `/api/v1/agents/{agent_id}/oauth` | OAuth 连接关联 (List[str]) |
| GET | `/api/v1/agents/{agent_id}/status` | 运行时状态（含关联skill/tool/oauth + active/inactive） |

### 2.3 Agent 对话执行（agent_config.py）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/agents/{agent_id}/chat` | Agent 身份对话（需 SDK） |
| POST | `/api/v1/agents/{agent_id}/chat/stream` | Agent 身份流式对话（SSE，需 SDK） |

### 2.4 关键模型

```python
class AgentUpsertRequest:
    name: str
    type: str
    description: str = ""
    system_prompt: str
    enabled: bool = True
    sort_order: int = 99
    sdk_config: Optional[SDKAgentConfig] = None

class SDKAgentConfig:
    enabled: Optional[bool]
    model: Optional[str]
    max_turns: Optional[int]
    permission_mode: Optional[str]
    allowed_tools: Optional[List[str]]
    disallowed_tools: Optional[List[str]]
    include_hook_events: Optional[bool]
    skills: Optional[List[str]]
    agents: Optional[Dict]
```

---

## 三、SSE 流式对话 & 任务管理 & 主动引擎（按领域拆分）

原 `streaming.py` (744 行) 已按领域拆分为 3 个独立文件：

| 文件 | 行数 | 负责模块 | 标签 |
|------|------|---------|------|
| `chat_stream.py` | 563 | SSE 流式对话主入口 + 对话配置 | `chat-stream` |
| `agent_tasks.py` | 110 | Agent 任务提交/进度/干预 + Worker/模板 | `agent-tasks` |
| `proactive.py` | 58 | 主动引擎（心跳/洞察/简报/统计） | `proactive` |

---

### 3.1 对话配置（chat_stream.py）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/chat/config` | 获取对话配置（agent_id/tools/skills/pipeline_mode/model_role） |
| PUT | `/api/v1/chat/config` | 更新对话配置（持久化到 `data/chat_config.json`） |

### 3.2 流式对话主入口（chat_stream.py）

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/api/v1/chat/stream` | SSE 流式对话主入口 | Optional Bearer |

**请求体:**
```json
{
  "message": "手机出口德国需要什么认证",
  "agent_id": null,
  "skill_ids": null,
  "session_id": null
}
```

**处理管线（10 阶段）:**
1. RBAC 权限检查
2. Thinking — 意图解析（已内联至chat_stream） + 发布意图事件到 EventBus
3. Plan — 构建执行计划（general/compliance 分支）
4. 分支路由：
   - **通用问题 / 指定 agent_id** → `_handle_general_stream()` → AstraAssistant SDK / 降级回复
   - **合规查询** → `_handle_compliance_stream()`（5-10阶段）
5. 规则引擎检查（合规场景）
6. Skills 推荐
7. RAG 法规检索补充
8. 流式输出合规报告
9. Action Card（推荐操作，含 product_id 深度链接）
10. 记忆持久化 → 发布合规事件 → Done

### 3.3 Agent 任务管理（agent_tasks.py）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/agents/tasks` | 活跃任务列表 |
| POST | `/api/v1/agents/tasks` | 提交任务到 ManagerAgent |
| GET | `/api/v1/agents/tasks/{group_id}` | 任务进度 |
| POST | `/api/v1/agents/tasks/{group_id}/intervene` | 用户干预 (cancel/pause/resume/retry) |
| GET | `/api/v1/agents/workers` | Worker 状态 |
| GET | `/api/v1/agents/templates` | 任务分解模板 |

### 3.4 主动引擎（proactive.py）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/proactive/heartbeat` | 系统心跳 |
| GET | `/api/v1/proactive/insights` | 跨产品洞察 |
| GET | `/api/v1/proactive/brief` | 合规简报 (limit: 1-30, 默认7) |
| GET | `/api/v1/proactive/stats` | 引擎统计 |

---

## 四、Tools API

**文件:** `backend/app/api/tools.py` (333 行)  
**前缀:** `/api/v1/tools`  
**标签:** `tools`  
**存储:** `data/tools/tools.json`（运行时CRUD）初始化源：`data/tools/_registry.yaml`，脚本：`data/tools/impl/`（仅metaso_search.py）→ 3 个脚本已迁至 Skills: news-collect / news-analyze / browser-control

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `` | 列表（支持 category/enabled 筛选） |
| GET | `/{tool_id}` | 详情 |
| POST | `` | 创建（自动生成 tool_{uuid} ID） |
| PUT | `/{tool_id}` | 更新 |
| DELETE | `/{tool_id}` | 删除 |
| PUT | `/{tool_id}/toggle` | 启用/禁用切换 |

**内置默认 Tools (9 个，定义于 `data/tools/_registry.yaml`):**
- `tool_compliance_check` — 合规检查 (builtin, compliance)
- `tool_hs_lookup` — HS编码查询 (builtin, compliance)
- `tool_vat_query` — VAT税率查询 (builtin, compliance)
- `tool_regulation_scan` — 法规变更扫描 (builtin, compliance)
- `tool_metaso_search` — 米塔AI搜索 (script, search, impl/metaso_search.py)
| `tool_metaso_search` | 米塔AI搜索 | script | search | `impl/metaso_search.py` | ✅ 工具 |

---

## 五、Skills API

**文件:** `backend/app/api/skills.py` (162 行)  
**前缀:** `/api/v1/skills`  
**标签:** `skills`  
**存储:** `SkillRegistry` 内存 + `data/config/skills/registry.json`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `` | 列表（支持 status/stage 筛选） |
| GET | `/{skill_id}` | 详情 |
| POST | `/install` | 安装 |
| POST | `/{skill_id}/install` | 按 ID 安装 |
| POST | `/{skill_id}/refresh` | 刷新 |
| POST | `/{skill_id}/execute` | 执行 |
| GET | `/{skill_id}/status` | 执行状态 |
| GET | `/{skill_id}/config` | 获取配置 |
| PUT | `/{skill_id}/config` | 更新配置 |
| DELETE | `/{skill_id}` | 卸载 |
| POST | `/recommend` | Skill 推荐 |
| GET | `/matrix/stages` | Skills×阶段映射矩阵 |
| GET | `/executions/history` | 执行历史 |

---

## 六、集成 / OAuth / 频道 / 同步 API（按领域拆分）

原 `integrations.py` (264 行) 已按领域拆分为 4 个独立文件：

| 文件 | 行数 | 负责模块 | 标签 |
|------|------|---------|------|
| `integrations.py` | 140 | 第三方连接管理（CRUD + OAuth授权/回调 + 测试） | `integrations` |
| `oauth.py` | 34 | OAuth 前端兼容别名路由 | `oauth` |
| `channels.py` | 90 | 频道适配器（注册/注销/发送/广播） | `channels` |
| `sync.py` | 51 | 自动拉取引擎管理（状态/触发/日志/追踪） | `sync` |

---

### 6.1 Integrations Router（integrations.py）

**前缀:** `/api/v1/integrations`  
**标签:** `integrations`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `` | 连接列表（支持 provider 筛选） |
| POST | `` | 创建连接 |
| GET | `/providers` | Provider 模板列表 |
| GET | `/status` | 各 Provider 状态汇总 |
| POST | `/{provider}/auth` | OAuth 授权（返回 auth_url） |
| GET | `/{provider}/callback` | OAuth 回调 |
| GET | `/{conn_id}/status` | 连接健康状态 |
| POST | `/{conn_id}/sync` | 手动触发同步 |
| PUT | `/{conn_id}/config` | 更新连接配置 |
| DELETE | `/{conn_id}` | 断开连接 |
| POST | `/{conn_id}/test` | 测试连接有效性 |

### 6.2 OAuth 兼容别名 Router（oauth.py）

**前缀:** `/api/v1/oauth`  
**标签:** `oauth`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/providers` | OAuth 应用列表 (别名) |
| GET | `/status` | 连接状态 (别名) |
| POST | `/{conn_id}/test` | 测试 OAuth 连接 (别名) |

### 6.3 Channels Router（channels.py）

**前缀:** `/api/v1/channels`  
**标签:** `channels`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `` | 频道列表 |
| POST | `` | 注册频道 (feishu/dingtalk/slack/email/webhook) |
| PUT | `/{name}` | 更新频道配置 |
| DELETE | `/{name}` | 注销频道 |
| POST | `/send` | 发送通知 |
| POST | `/broadcast` | 广播消息 |

### 6.4 Sync Router（sync.py）

**前缀:** `/api/v1/sync`  
**标签:** `sync`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/status` | 同步引擎状态 |
| POST | `/run` | 手动触发同步 |
| GET | `/jobs` | 同步任务列表 |
| GET | `/logs` | 同步日志 |
| POST | `/tracking` | 注册物流追踪号 |

---

## 七、模型配置 API

**文件:** `backend/app/api/model_config.py` (125 行)  
**前缀:** `/api/v1/model-configs`  
**标签:** `model-config`  
**存储:** `ModelRouter` 内存 + `data/models/routes.yaml`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `` | 所有模型路由配置（API Key 环境变量名，无真实 Key） |
| POST | `` | 创建/更新模型路由 |
| PUT | `/{role}` | 更新指定角色路由 |
| DELETE | `/{role}` | 删除（不允许最后一个） |
| GET | `/usage` | Token 使用统计 |

**角色 (roles):** `reasoning`, `fast`, `vision`, `embedding`

---

## 八、事件 API

### 8.1 事件运行时 API

**文件:** `backend/app/api/events.py` (109 行)  
**前缀:** `/api/v1/events`  
**标签:** `events`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `` | 最近全局事件 (limit/category/product_id/severity 筛选) |
| POST | `` | 发布事件 |
| GET | `/timeline` | 事件时间线 |
| GET | `/stats` | 事件统计 |
| GET | `/registry` | 事件定义列表 (支持 stage/category 筛选) |
| GET | `/registry/{event_code}` | 事件定义详情 |
| POST | `/subscribe` | 创建事件订阅 |
| DELETE | `/subscribe/{sub_id}` | 取消订阅 |
| GET | `/subscriptions` | 订阅列表 |

### 8.2 事件配置管理 API

**文件:** `backend/app/api/event_config.py` (93 行)  
**前缀:** `/api/v1/event-config`  
**标签:** `event-config`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `` | 事件配置列表 | - |
| GET | `/{event_code}` | 事件配置详情 | - |
| POST | `` | 注册新事件类型 | QAAgent |
| PUT | `/{event_code}` | 修改事件类型 | QAAgent |
| DELETE | `/{event_code}` | 删除事件类型 | QAAgent |

---

## 九、Worker 配置 API

**文件:** `backend/app/api/worker_config.py` (108 行)  
**前缀:** `/api/v1/worker-config`  
**标签:** `worker-config`  
**存储:** `WorkerRegistry` 内存 + `data/config/workers/*.md`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `` | 列表（支持 stage 筛选） | - |
| GET | `/status` | 所有 Worker 运行时状态 | - |
| GET | `/{worker_code}` | 详情 | - |
| GET | `/{worker_code}/status` | 运行时状态 | - |
| POST | `` | 注册新 Worker | QAAgent |
| PUT | `/{worker_code}` | 修改 Worker | QAAgent |
| DELETE | `/{worker_code}` | 删除/归档 | QAAgent |

---

## 十、定时任务 API

**文件:** `backend/app/api/scheduler_config.py` (397 行)  
**前缀:** `/api/v1/scheduler`  
**标签:** `scheduler`  
**核心:** APScheduler

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tasks` | 可调度任务模板列表 |
| GET | `/jobs` | 所有定时任务 |
| GET | `/jobs/grouped` | 分组任务 (global/products) |
| POST | `/jobs` | 创建任务 |
| POST | `/jobs/{job_id}/pause` | 暂停 |
| POST | `/jobs/{job_id}/resume` | 恢复 |
| DELETE | `/jobs/{job_id}` | 删除 |
| POST | `/jobs/{job_id}/trigger` | 立即触发 |
| GET | `/bindings` | 任务-Worker 绑定配置 |
| GET | `/tasks-with-workers` | 任务+Worker 联合视图 |
| PUT | `/bindings/{task_name}` | 更新绑定 |

---

## 十一、指标 API

**文件:** `backend/app/api/metrics.py` (260 行)  
**前缀:** `/api/v1/metrics`  
**标签:** `metrics`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/products/{product_id}` | 产品指标 |
| GET | `/products/{product_id}/history` | 产品指标历史 (days: 1-90) |
| GET | `/global` | 全局聚合指标 |
| GET | `/alerts` | 指标预警 (支持 severity 筛选) |
| GET | `/builtin_templates` | 内置指标模板 |
| GET | `/custom` | 自定义指标列表 |
| POST | `/custom` | 创建自定义指标 |
| PUT | `/custom/{metric_id}` | 更新 |
| DELETE | `/custom/{metric_id}` | 删除 |
| GET | `/cross_product` | 跨产品聚合洞察 |

---

## 十二、产品 API

**文件:** `backend/app/api/products.py` (173 行)  
**前缀:** `/api/v1/products`  
**标签:** `products`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `` | 列表 (lifecycle_stage/product_type/market/limit/offset) |
| POST | `` | 创建（自动发事件 + 注册产品级定时任务） |
| GET | `/count` | 统计 |
| GET | `/{product_id}` | 详情 |
| PUT | `/{product_id}` | 更新 |
| PUT | `/{product_id}/lifecycle` | 更新生命周期（发 status_changed 事件） |
| DELETE | `/{product_id}` | 删除/归档 |
| GET | `/{product_id}/events` | 产品事件列表 |
| POST | `/{product_id}/compliance-check` | 触发合规检查 |

---

## 十三、风险预警 API

**文件:** `backend/app/api/risk.py` (154 行)  
**前缀:** `/api/v1/risk/*` + `/api/v1/metrics/*` + `/api/v1/prompts/*`  
**标签:** `risk`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/risk/alerts` | 预警列表 (user_id/alert_type/severity/page/size) |
| GET | `/risk/alerts/unread-count` | 未读预警数 |
| POST | `/risk/alerts/{alert_id}/dismiss` | 忽略预警 |
| POST | `/risk/scan` | 手动触发市场扫描（含 WebSocket 推送） |
| GET | `/risk/market-status` | 市场监控状态 |
| GET | `/metrics/dashboard` | 用户合规仪表盘 |
| POST | `/prompts/reload` | 热加载 Prompt 模板 |

---

## 十四、通知 API

**文件:** `backend/app/api/notifications.py` (50 行)  
**前缀:** `/api/v1/notifications`  
**标签:** `notifications`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `` | 列表 (product_id/is_read/severity/limit/offset) |
| GET | `/unread-count` | 未读通知数 |
| PUT | `/{notification_id}/read` | 标记已读 |
| PUT | `/read-all` | 全部已读 |

---

## 十五、合规流水线 API

**文件:** `backend/app/api/pipeline.py` (94 行)  
**前缀:** `/api/v1/pipeline`  
**标签:** `pipeline`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 流水线健康度（10阶段评分） |
| GET | `/stages` | 各阶段聚合数据 |
| GET | `/metrics` | 聚合指标 |
| GET | `/mode` | 当前模式 (5step/6step) |
| PUT | `/mode` | 设置模式 |
| GET | `/interactions` | 待处理交互请求 |
| POST | `/interactions/{interaction_id}` | 处理用户交互 |

---

## 十六、知识库 API

**文件:** `backend/app/api/knowledge.py` (97 行)  
**前缀:** `/api/v1/knowledge`  
**标签:** `knowledge`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/sections` | 法规知识章节列表 |
| GET | `/sections/{section_id}` | 章节详情 |
| GET | `/search` | 关键词搜索 |

---

## 十七、RAG API

**文件:** `backend/app/api/rag.py` (97 行)  
**前缀:** `/api/v1/rag`  
**标签:** `rag`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/status` | RAG 系统状态（collection/文档数/model/chroma_path） |
| POST | `/search` | 语义搜索 |
| POST | `/reindex` | 重建索引 |
| GET | `/models` | 模型路由配置 |
| GET | `/token-juice/stats` | TokenJuice 压缩统计 |

---

## 十七·五、RAG 知识导入 & 新闻监控 API (Phase 3.6)

**新增 Phase 3.6** — RAG 知识导入与外部新闻/法规监控。

### 17.5a RAG 知识导入 API

**文件:** `backend/app/api/knowledge_import.py` (211 行)  
**前缀:** `/api/v1/knowledge/import`  
**标签:** `knowledge-import`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/file` | 上传文件导入知识 |
| POST | `/url` | 从 URL 抓取导入知识 |
| GET | `/jobs` | 导入任务列表 |
| GET | `/jobs/{job_id}` | 导入任务详情 |
| POST | `/jobs/{job_id}/retry` | 重试失败任务 |

### 17.5b 新闻监控 API

**文件:** `backend/app/api/news_monitor.py` (157 行)  
**前缀:** `/api/v1/news`  
**标签:** `news-monitor`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/feeds` | 新闻源列表 |
| POST | `/feeds` | 添加新闻源 |
| DELETE | `/feeds/{feed_id}` | 删除新闻源 |
| GET | `/articles` | 文章列表（支持筛选） |
| GET | `/articles/{article_id}` | 文章详情 |
| POST | `/scan` | 手动触发扫描 |
| GET | `/status` | 监控状态 |

---

## 十八、SDK 会话管理 API

**文件:** `backend/app/api/sdk_sessions.py` (167 行)  
**前缀:** `/api/v1/sdk`  
**标签:** `sdk`  
**依赖:** claude-agent-sdk 必须安装

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/sessions` | SDK 会话列表 |
| GET | `/sessions/{session_id}` | 会话详情 |
| GET | `/sessions/{session_id}/messages` | 消息历史 |
| DELETE | `/sessions/{session_id}` | 删除会话 |
| POST | `/sessions/{session_id}/fork` | Fork 会话 |
| POST | `/sessions/{session_id}/rename` | 重命名 |
| POST | `/sessions/{session_id}/tag` | 打标签 |
| GET | `/subagents` | 子代理列表 |
| GET | `/subagents/{subagent_id}/messages` | 子代理消息 |

---

## 十九、认证 API

**文件:** `backend/app/api/auth.py` (108 行)  
**前缀:** `/api/v1/auth`  
**标签:** `auth`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/auth/login` | 用户登录 (返回 JWT) | - |
| POST | `/auth/token` | OAuth2 表单登录 (Swagger) | - |
| POST | `/auth/register` | 新建用户 | Admin |
| GET | `/auth/me` | 当前用户信息 | Bearer |
| PUT | `/auth/me/password` | 修改密码 | Bearer |

---

## 二十、用户管理 API

**文件:** `backend/app/api/users.py` (55 行)  
**标签:** `users`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/api/v1/users` | 用户列表 | Admin |
| DELETE | `/api/v1/users/{user_id}` | 删除用户（不能删自己） | Admin |
| PUT | `/api/v1/users/{user_id}/role` | 修改角色 | Admin |

---

## 二十一、会话历史 API

**文件:** `backend/app/api/sessions.py` (79 行)  
**标签:** `sessions`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/api/v1/sessions` | 列表（admin 看全部，user 看自己） | Bearer |
| GET | `/api/v1/sessions/{session_id}` | 详情+消息 | Bearer |
| DELETE | `/api/v1/sessions/{session_id}` | 删除 | Bearer |

---

## 二十二、记忆树 API

**文件:** `backend/app/api/memory.py` (234 行)  
**前缀:** `/api/v1/memory`  
**标签:** `memory`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/namespaces` | NLStore 命名空间列表 |
| GET | `/tree` | 记忆树层级结构 (product_id/level 筛选) |
| GET | `/tree/{node_id}` | 记忆节点详情 |
| POST | `/search` | 语义搜索记忆 |
| POST | `/export` | 导出 Obsidian Wiki 格式 |
| POST | `/fragments` | 追加 L0 片段 |
| GET | `/fragments` | 查询 L0 片段 |
| GET | `/summaries` | 查询 L1-L3 摘要 |
| GET | `/{ns}` | 列出命名空间下记录 |
| GET | `/{ns}/{key}` | 单条 NLRecord |

---

## 二十三、CLI API

**文件:** `backend/app/api/cli.py` (128 行)  
**前缀:** `/api/v1/cli`  
**标签:** `cli`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/execute` | 执行命令（`/`开头→魔法命令；`astra *` → QAAgent） |
| POST | `/magic` | 执行魔法命令 |
| GET | `/complete` | 自动补全 |
| GET | `/history` | 命令历史 |

**内置魔法命令:** `/help`, `/clear`, `/status`, `/config`, `/history`, `/agent`, `/export`, `/events`, `/workers`, `/products`, `/retry`

---

## 二十四、操作链 / 事件链 API

**文件:** `backend/app/api/chains.py` (282 行)  
**前缀:** `/api/v1/chains`  
**标签:** `chains`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/chains/actions` | 操作链列表 |
| GET | `/chains/actions/{chain_id}` | 操作链详情 |
| GET | `/chains/actions/{chain_id}/trail` | 操作链路（自然语言） |
| GET | `/chains/events` | 事件链列表 |
| GET | `/chains/events/{chain_id}` | 事件链详情 |
| GET | `/chains/events/{chain_id}/timeline` | 事件时间线 |
| GET | `/chains/events/{chain_id}/filter` | 筛选事件（source/type/severity/tags） |
| POST | `/chains/events` | 创建事件/追加到事件链 |

### NLStore API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/nl-store/search` | 全文搜索 |
| GET | `/api/v1/nl-store/{namespace}` | Namespace 下记录列表 |
| GET | `/api/v1/nl-store/{namespace}/{key}` | 记录详情 |
| POST | `/api/v1/nl-store/{namespace}` | 创建记录 |
| PUT | `/api/v1/nl-store/{namespace}/{key}` | 更新记录 |
| DELETE | `/api/v1/nl-store/{namespace}/{key}` | 删除记录 |

---

## 二十五、Shopify 集成 API

**文件:** `backend/app/api/shopify.py` (257 行)  
**前缀:** `/api/v1/shopify/*`  
**标签:** `shopify`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/shopify/auth` | 发起 OAuth 授权 |
| GET | `/shopify/callback` | OAuth 回调 |
| GET | `/shopify/shops` | 已连接店铺列表 |
| GET | `/shopify/{shop}/products` | 获取产品列表 |
| POST | `/shopify/{shop}/check/{product_id}` | 产品合规检查 |
| POST | `/shopify/webhook` | Webhook 接收 |

---

## 二十六、后台管理 API (Phase 4，按领域拆分)

原 `admin.py` (405 行) 已按领域拆分为 4 个独立文件：

| 文件 | 行数 | 负责模块 | 标签 |
|------|------|---------|------|
| `admin_rbac.py` | 81 | RBAC 角色分配/撤销/权限检查 | `rbac` |
| `admin_approvals.py` | 80 | 审批请求创建/审批/驳回/规则/统计 | `approvals` |
| `admin_config.py` | 177 | 集成配置/功能开关/健康检查/通知规则 | `config-ext` |
| `admin_reports.py` | 122 | 合规报表列表/导出（6种内置报表） | `reports` |

---

### 26.1 RBAC Router（admin_rbac.py）

**前缀:** `/api/v1/rbac`  
**标签:** `rbac`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/roles` | 角色定义列表 |
| POST | `/assign` | 分配角色 |
| DELETE | `/users/{user_id}` | 撤销用户角色 |
| GET | `/users` | 用户 RBAC 列表 |
| GET | `/users/{user_id}` | 用户权限详情 |
| GET | `/users/{user_id}/permissions` | 用户权限列表 |
| POST | `/check` | 权限检查 |

### 26.2 Approvals Router（admin_approvals.py）

**前缀:** `/api/v1/approvals`  
**标签:** `approvals`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `` | 审批列表 |
| POST | `` | 创建审批请求 |
| POST | `/{approval_id}/approve` | 审批通过 |
| POST | `/{approval_id}/reject` | 审批驳回 |
| GET | `/rules` | 审批规则 |
| GET | `/stats` | 审批统计 |

### 26.3 Config Ext Router（admin_config.py）

**前缀:** `/api/v1/config`  
**标签:** `config-ext`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/integrations` | 集成配置状态 |
| PUT | `/integrations/{provider}` | 更新集成配置 |
| GET | `/features` | 功能开关列表 |
| PUT | `/features/{key}` | 功能开关切换 |
| GET | `/health` | 系统健康检查（10 核心组件） |
| GET | `/notifications` | 通知规则配置 |
| POST | `/notifications` | 添加通知规则 |
| PUT | `/notifications/{rule_id}` | 更新通知规则 |
| DELETE | `/notifications/{rule_id}` | 删除通知规则 |

### 26.4 Reports Router（admin_reports.py）

**前缀:** `/api/v1/reports`  
**标签:** `reports`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `` | 合规报表列表（6种内置报表） |
| POST | `/{report_id}/export` | 导出报表 (json/csv/pdf/excel) |

---

## 二十七、编码能力 / 安全 API

### 27.1 Code Router

**文件:** `backend/app/api/code_security.py`  
**前缀:** `/api/v1/code`  
**标签:** `code`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/lsp/definition` | LSP 跳转到定义 |
| POST | `/lsp/references` | 查找引用 |
| POST | `/lsp/hover` | 悬停提示 |
| POST | `/ast/search` | AST 模式搜索 |
| POST | `/patch` | 应用代码变更 |

### 27.2 Security Router

**前缀:** `/api/v1/security`  
**标签:** `security`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/check/tool` | 工具调用安全检查 |
| POST | `/check/file` | 文件访问检查 |
| POST | `/scan/skill` | 技能安全扫描 |
| GET | `/events` | 安全事件日志 |
| GET | `/stats` | 安全统计 |
| GET | `/rules` | 防护规则列表 |
| POST | `/rules` | 添加防护规则 |
| DELETE | `/rules/{rule_id}` | 删除防护规则 |

---

## 二十八、插件 API

**文件:** `backend/app/api/plugins.py` (80 行)  
**前缀:** `/api/v1/plugins`  
**标签:** `plugins`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `` | 已安装插件列表 |
| POST | `` | 安装插件 |
| GET | `/recommended` | 推荐插件清单 |
| DELETE | `/{plugin_id}` | 卸载 |
| POST | `/{plugin_id}/audit` | 安全审查 |
| POST | `/{plugin_id}/enable` | 启用 |
| POST | `/{plugin_id}/disable` | 停用 |

---

## 二十九、风险情报引擎 API (Phase 3.7)

**文件:** `backend/app/api/risk_intel.py` (442 行)  
**前缀:** `/api/v1/risk-intel`  
**标签:** `risk-intel`  
**核心依赖:** `core/risk_intel_engine.py` + `storage/risk_intel_store.py` + `data/skills/risk-intel-collect/`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/search` | 搜索情报条目 (keyword 必填，触发采集器) |
| GET | `/feed` | 情报流 (page/size 分页) |
| GET | `/heatmap` | 风险热力图 (by_domain/trend/top_markets/latest_critical) |
| GET | `/keywords` | 监控关键词列表 |
| POST | `/keywords` | 创建关键词 (keyword/label/sources) |
| POST | `/keywords/suggest` | AI 建议关键词 |
| PUT | `/keywords/{keyword_id}` | 更新关键词 |
| DELETE | `/keywords/{keyword_id}` | 删除关键词 |
| POST | `/keywords/{keyword_id}/run` | 手动触发采集 |
| GET | `/runs` | 采集运行记录列表 |
| GET | `/runs/{run_id}` | 运行详情 |
| POST | `/admin/global-scan` | 全局扫描 (Admin) |
| GET | `/analyze/status` | 分析器状态 |
| POST | `/analyze/trigger` | 触发分析 |
| POST | `/analyze/item/{item_id}` | 分析单条情报 |

**响应示例:**

```json
// GET /heatmap
{
  "by_domain": {"tariff": 3, "sanction": 1},
  "trend": [{"date": "2026-06-14", "count": 5}],
  "top_markets": ["US", "EU"],
  "latest_critical": [],
  "generated_at": "2026-06-14T07:25:17Z"
}

// GET /keywords
[{"id": "uuid", "keyword": "tariff LED 2026", "label": "LED关税", "sources": [...], "created_at": "..."}]
```

---

## 三十、生命周期管理 API (Phase 3.8)

产品出海全生命周期管理：供应商 → 合同 → 支付 → 物流 → 报关 → 订单。

### 30.1 供应商管理

**文件:** `backend/app/api/suppliers.py` (172 行)  
**前缀:** `/api/v1/suppliers`  
**标签:** `suppliers`  
**核心依赖:** `storage/supplier_store.py` + `core/lifecycle_analyzer.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `` | 供应商列表 (country/category/search 筛选) |
| POST | `` | 创建供应商 (name/source_type/country/contact_*) |
| GET | `/{supplier_id}` | 供应商详情 |
| PUT | `/{supplier_id}` | 更新供应商 |
| DELETE | `/{supplier_id}` | 删除 |
| GET | `/{supplier_id}/products` | 关联产品 |
| POST | `/{supplier_id}/rate` | 评级 |
| GET | `/{supplier_id}/risk-assessment` | AI 风险评估结果 |
| POST | `/{supplier_id}/verify` | 触发 AI 资质审核 (lifecycle_analyzer) |

**响应示例:**

```json
// GET /suppliers
[{"id": "sup_xxx", "name": "供应商名", "source_type": "factory", "country": "CN", "ai_risk_level": null, "created_at": "..."}]

// GET /suppliers/{id}/risk-assessment
{"supplier_id": "sup_xxx", "status": "not_reviewed", "message": "尚未进行 AI 审核，请调用 POST /{id}/verify"}
```

### 30.2 合同管理

**文件:** `backend/app/api/contracts.py` (217 行)  
**前缀:** `/api/v1/contracts`  
**标签:** `contracts`  
**核心依赖:** `storage/contract_store.py` + `core/lifecycle_analyzer.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/templates` | 合同模板列表 |
| GET | `/templates/{template_id}` | 模板详情 |
| POST | `/templates/{template_id}/render` | 渲染模板 |
| GET | `` | 合同列表 |
| POST | `` | 创建合同 |
| GET | `/{contract_id}` | 合同详情 |
| PUT | `/{contract_id}` | 更新合同 |
| POST | `/{contract_id}/sign` | 签署合同 |
| GET | `/{contract_id}/versions` | 版本历史 |
| POST | `/{contract_id}/compliance-review` | AI 合同合规审查 (lifecycle_analyzer) |

### 30.3 支付渠道

**文件:** `backend/app/api/payment_channels.py` (179 行)  
**前缀:** `/api/v1/payment-channels`  
**标签:** `payment-channels`  
**核心依赖:** `storage/payment_store.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `` | 渠道列表 (country/currency 筛选) |
| POST | `` | 创建渠道 (name/provider/currencies/countries) |
| GET | `/{channel_id}` | 渠道详情 |
| PUT | `/{channel_id}` | 更新渠道 |
| POST | `/{channel_id}/test` | 支付测试 |
| GET | `/{channel_id}/chargeback-stats` | 拒付统计 |
| POST | `/{channel_id}/chargeback` | 添加拒付事件 |

### 30.4 物流管理

**文件:** `backend/app/api/logistics.py` (417 行)  
**前缀:** `/api/v1/logistics`  
**标签:** `logistics`  
**核心依赖:** `storage/logistics_store.py` + `storage/order_store.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/carriers` | 物流商列表 (8个内置: DHL/FedEx/UPS等) |
| GET | `/shipments` | 货运单列表 |
| POST | `/shipments` | 创建货运单 (carrier/tracking_num/origin/dest) |
| GET | `/shipments/{shipment_id}` | 货运详情 |
| GET | `/shipments/{shipment_id}/tracking` | 物流追踪 |
| POST | `/shipments/{shipment_id}/refresh` | 刷新追踪信息 |
| POST | `/webhook/17track` | 17Track Webhook |
| POST | `/webhook/aftership` | AfterShip Webhook |

**响应示例:**

```json
// GET /carriers
[{"code": "dhl", "name": "DHL Express", "tracking_url": "https://www.dhl.com/tracking?id={num}"}, ...]
```

### 30.5 报关管理

**文件:** `backend/app/api/customs.py` (379 行)  
**前缀:** `/api/v1/customs`  
**标签:** `customs`  
**核心依赖:** `storage/customs_store.py` + `core/three_way_checker.py` + `core/controlled_goods_checker.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/declarations` | 报关单列表 |
| POST | `/declarations` | 创建报关单 (hs_code/declared_name/declared_value/dest_country) |
| GET | `/declarations/{declaration_id}` | 报关单详情 |
| POST | `/declarations/{declaration_id}/submit` | 提交报关 |
| POST | `/declarations/{declaration_id}/check` | 合规检查 |
| POST | `/declarations/{declaration_id}/clear` | 清关确认 |
| GET | `/declarations/{declaration_id}/exception` | 异常情况 |
| GET | `/duty-calculator` | 关税计算 (hs_code/value/country) |
| GET | `/tariff-rates` | 税率查询 (country/hs_code) |
| POST | `/three-way-check` | 三单比对 (发票/装箱单/报关单) |
| GET | `/controlled-goods/check` | 管制商品检查 (declared_name/hs_code/dest_country 必填) |

**响应示例:**

```json
// GET /controlled-goods/check?declared_name=laser&hs_code=9013.20&dest_country=US
{"passed": true, "level": "pass", "errors": [], "warnings": [], "infos": [{"rule": "HS_HIGH_RISK", "level": "info", "message": "..."}]}
```

### 30.6 订单管理

**文件:** `backend/app/api/orders.py` (214 行)  
**前缀:** `/api/v1/orders`  
**标签:** `orders`  
**核心依赖:** `storage/order_store.py` + `core/three_way_checker.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `` | 订单列表 (status/customer_id/date_from 筛选) |
| POST | `` | 创建订单 (customer_id/items/shipping_address) |
| GET | `/{order_id}` | 订单详情 |
| PUT | `/{order_id}` | 更新订单 |
| GET | `/{order_id}/payments` | 支付记录 |
| GET | `/{order_id}/payment-summary` | 支付汇总 |
| POST | `/{order_id}/payments` | 添加支付记录 |
| POST | `/{order_id}/three-way-check` | 三单比对 |

---

## 三十一、LLM 决策调度 API (Phase 3.9)

**文件:** `backend/app/api/llm_dispatch.py` (215 行)  
**前缀:** `/api/v1/llm-dispatch`  
**标签:** `llm-dispatch`  
**核心依赖:** `core/llm_gateway.py` (GLM-5.1) + `core/llm_dispatcher.py` + `data/models/routes.yaml`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/status` | 网关状态 (gateway_available/roles/call_stats) |
| POST | `/risk/dispatch` | 风险情报分析调度 |
| POST | `/risk/dispatch-item` | 单条情报分析 |
| POST | `/lifecycle/scan` | 生命周期全局扫描 |
| POST | `/lifecycle/supplier/{supplier_id}` | 供应商分析调度 |
| POST | `/lifecycle/contract/{contract_id}` | 合同分析调度 |

**响应示例:**

```json
// GET /status
{
  "gateway_available": true,
  "roles": {
    "risk_analysis": {"available": true, "provider": "zhipu", "model": "glm-5.1"},
    "lifecycle_analysis": {"available": true, "provider": "zhipu", "model": "glm-5.1"}
  },
  "call_stats": {"total_calls": 0, "total_tokens": 0}
}
```

---

## 三十二、飞书集成 API

**文件:** `backend/app/api/feishu.py`  
**标签:** `feishu`  
**核心依赖:** `core/feishu_client.py` + `core/event_listeners/feishu_listener.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/feishu/status` | 飞书集成状态 |
| POST | `/api/v1/feishu/webhook` | 飞书事件 Webhook |

---

## 三十三、WebSocket 端点

**定义在:** `backend/app/main.py`

| 协议 | 路径 | 说明 |
|------|------|------|
| WebSocket | `/api/v1/ws?user_id={user_id}` | 实时推送（session_update / new_message / alert / scan_update） |

---

## 三十四、系统健康端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/system/health` | 系统详细健康检查 (event_bus/scheduler/skill_registry 等10组件) |
| GET | `/api/v1/config/health` | 10 个核心组件健康检查 |
| GET | `/api/v1/metrics/dashboard` | 指标仪表盘 (total_products/risk_distribution/recent_alerts) |
| GET | `/api/v1/metrics/global` | 全局指标 (total_managed_products/system_health_score) |

---

## 三十五、文件索引（v1.2 三库整合后）

### Phase 1 重构（文件拆分）：

| 原文件 | 行数 | → 新文件 | 行数 | 路由数 | 主要功能 |
|--------|------|---------|------|-------|----------|
| `agent_config.py` | 423 | `agent_crud.py` | 207 | 6 | Agent CRUD（增删改查 + 开关） |
| | | `agent_extensions.py` | 130 | 7 | Agent-Skills/Tools/OAuth 关联 + 状态 |
| | | `agent_config.py` | — | 2 | Agent 对话执行（chat/chat/stream） |
| `streaming.py` | 744 | `chat_stream.py` | 563 | 3 | SSE 流式对话主入口 + 对话配置 |
| | | `agent_tasks.py` | 110 | 6 | Agent 任务管理 + Worker/模板 |
| | | `proactive.py` | 58 | 4 | 主动引擎（心跳/洞察/简报/统计） |
| `integrations.py` | 264 | `integrations.py` | 140 | 11 | 第三方连接管理 |
| | | `oauth.py` | 34 | 3 | OAuth 别名路由 |
| | | `channels.py` | 90 | 6 | 频道适配器 |
| | | `sync.py` | 51 | 5 | 自动拉取引擎管理 |
| `admin.py` | 405 | `admin_rbac.py` | 81 | 7 | RBAC 管理 |
| | | `admin_approvals.py` | 80 | 6 | 审批管理 |
| | | `admin_config.py` | 177 | 9 | 后台配置 |
| | | `admin_reports.py` | 122 | 2 | 合规报表 |

### Phase 3.6 新增：

| 文件 | 行数 | 路由数 | 主要功能 |
|------|------|-------|----------|
| `knowledge_import.py` | 211 | 5 | RAG 知识导入（文件/URL/任务管理） |
| `news_monitor.py` | 157 | 7 | 新闻监控 |

### Phase 3.7 新增（风险情报引擎）：

| 文件 | 行数 | 路由数 | 主要功能 |
|------|------|-------|----------|
| `api/risk_intel.py` | 442 | 15 | 风险情报 API (采集/分析/热力图/关键词) |
| `core/risk_intel_engine.py` | 718 | - | 风险情报引擎 (采集器+分析器+周期任务) |
| `core/risk_intel_analyzer.py` | 190 | - | 风险情报分析器 |
| `storage/risk_intel_store.py` | 870 | - | 情报数据存储 |
| `data/skills/risk-intel-collect/` | 977 | - | 采集器 Skill (15+ RSS 源) |
| `data/skills/risk-intel-analyze/` | 220 | - | 分析器 Skill |

### Phase 3.8 新增（生命周期管理）：

| 文件 | 行数 | 路由数 | 主要功能 |
|------|------|-------|----------|
| `api/suppliers.py` | 172 | 9 | 供应商 CRUD + AI 审核 |
| `api/contracts.py` | 217 | 10 | 合同模板 + CRUD + AI 合规审查 |
| `api/payment_channels.py` | 179 | 7 | 支付渠道 + 拒付统计 |
| `api/logistics.py` | 417 | 8 | 物流管理 + Webhook |
| `api/customs.py` | 379 | 11 | 报关 + 关税 + 管制商品 + 三单比对 |
| `api/orders.py` | 214 | 8 | 订单 CRUD + 支付记录 |
| `core/lifecycle_analyzer.py` | 172 | - | 生命周期 LLM 分析器 (供应商/合同/报关) |
| `core/three_way_checker.py` | 422 | - | 三单比对器 (发票/装箱单/报关单) |
| `core/controlled_goods_checker.py` | 398 | - | 管制商品检查器 |
| `storage/supplier_store.py` | 210 | - | 供应商数据存储 |
| `storage/contract_store.py` | 252 | - | 合同数据存储 |
| `storage/payment_store.py` | 224 | - | 支付渠道存储 |
| `storage/logistics_store.py` | 228 | - | 物流数据存储 |
| `storage/customs_store.py` | 306 | - | 报关数据存储 |
| `storage/order_store.py` | 294 | - | 订单数据存储 |

### Phase 3.9 新增（LLM 决策调度）：

| 文件 | 行数 | 路由数 | 主要功能 |
|------|------|-------|----------|
| `api/llm_dispatch.py` | 215 | 6 | LLM 调度 API (风险/生命周期) |
| `core/llm_gateway.py` | 275 | - | LLM 网关 (GLM-5.1 统一接口) |
| `core/llm_dispatcher.py` | 408 | - | LLM 决策调度器 |
| `data/models/routes.yaml` | 36 | - | 模型路由配置 |

### 飞书集成（astra-main 独有）：

| 文件 | 行数 | 路由数 | 主要功能 |
|------|------|-------|----------|
| `api/feishu.py` | - | 2 | 飞书消息/事件 API |
| `core/feishu_client.py` | - | - | 飞书客户端 |
| `core/unified_dispatcher.py` | - | - | 统一事件分发器 |
| `core/event_listeners/feishu_listener.py` | - | - | 飞书事件监听 (lark-cli) |
| `core/event_listeners/shopify_listener.py` | - | - | Shopify 事件监听 |

### Phase 2-3 未变文件：

| 文件 | 行数 | 路由数 | 主要功能 |
|------|------|-------|----------|
| `tools.py` | 242 | 6 | Tools CRUD |
| `skills.py` | 162 | 12 | Skills 管理 |
| `model_config.py` | 125 | 5 | 模型路由配置 |
| `events.py` | 109 | 9 | 事件运行时 API |
| `event_config.py` | 93 | 5 | 事件配置管理 (QAAgent) |
| `worker_config.py` | 108 | 7 | Worker 配置管理 (QAAgent) |
| `scheduler_config.py` | 397 | 11 | 定时任务管理 |
| `metrics.py` | 260 | 10 | 指标监控 |
| `products.py` | 173 | 9 | 产品管理 |
| `risk.py` | 154 | 4 | 风险预警 + 仪表盘 + Prompts |
| `notifications.py` | 50 | 4 | 通知管理 |
| `pipeline.py` | 94 | 7 | 合规流水线 |
| `knowledge.py` | 97 | 3 | 知识库 |
| `rag.py` | 97 | 5 | RAG 管理 |
| `auth.py` | 108 | 5 | 认证 |
| `sessions.py` | 79 | 3 | 会话历史 |
| `sdk_sessions.py` | 167 | 9 | SDK 会话管理 |
| `memory.py` | 234 | 11 | 记忆树 |
| `cli.py` | 128 | 4 | CLI 命令 |
| `chains.py` | 282 | 12 | 操作链/事件链/NLStore |
| `shopify.py` | 257 | 6 | Shopify 集成 |
| `users.py` | 55 | 3 | 用户管理 |
| `code_security.py` | 160 | 13 | Code/Security API |
| `plugins.py` | 80 | 7 | 插件管理 |
| `main.py` | 215 | 2 | 根端点 + WebSocket |
