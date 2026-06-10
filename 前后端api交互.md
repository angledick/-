# 前后端 API 交互规范

> 版本: 1.1 | 更新时间: 2026-06-08  
> 涵盖: 请求生命周期、认证、CRUD、SSE 流式、WebSocket 实时推送、配置同步、错误处理、降级策略
> 架构变更: 后端 API 文件按领域拆分（agent→3, streaming→3, admin→4, integrations→4）+ Phase 3.6 新增

---

## 目录

1. [总体交互架构](#1-总体交互架构)
2. [认证交互流程](#2-认证交互流程)
3. [通用 CRUD REST 交互](#3-通用-crud-rest-交互)
4. [SSE 流式对话交互](#4-sse-流式对话交互)
5. [WebSocket 实时推送交互](#5-websocket-实时推送交互)
6. [配置层级同步机制](#6-配置层级同步机制)
7. [错误处理体系](#7-错误处理体系)
8. [前端降级与容错策略](#8-前端降级与容错策略)
9. [交互场景速查表](#9-交互场景速查表)

---

## 1. 总体交互架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend React SPA                       │
│                                                                 │
│  ┌─────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │  Pages   │  │  Zustand     │  │  Context Providers       │   │
│  │ (19个)   │──│  Store       │──│  AuthContext              │   │
│  │          │  │  AgentConfig │  │  WebSocketContext         │   │
│  │          │  │  SidebarState│  │  NotificationContext      │   │
│  └────┬─────┘  └──────────────┘  └──────────────┬───────────┘   │
│       │                                          │              │
│       ▼                                          ▼              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              API Client Layer (config.ts)                │    │
│  │                                                          │    │
│  │  request<T>(url, options) → authHeaders() → fetch()     │    │
│  │                                                          │    │
│  │  agentsApi  skillsApi  toolsApi  oauthApi  modelConfigsApi │   │
│  │  productsApi  pipelineApi  riskAlertsApi  memoryApi      │    │
│  │  cliApi  knowledgeApi  proactiveApi  schedulerApi        │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           │                                     │
└───────────────────────────┼─────────────────────────────────────┘
                            │ HTTP / SSE / WebSocket
                            │ localhost:8000
┌───────────────────────────┼─────────────────────────────────────┐
│                    Backend FastAPI (Python)                      │
│                           │                                     │
│  ┌────────────────────────┴────────────────────────────────┐    │
│  │                  Middleware Layer                         │    │
│  │                                                          │    │
│  │  CORSMiddleware → Dev: localhost:5173, localhost:3000    │    │
│  │  OAuth2PasswordBearer → JWT Token 校验                   │    │
│  │  DEV_MODE=true → 跳过认证，mock admin 身份               │    │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              35 API Routers (Phase 1-4 + 3.6)            │    │
│  │                                                          │    │
│  │  auth  users  agent_crud  agent_extensions  skills  tools│    │
│  │  products  events  pipeline  notifications  cli  rag     │    │
│  │  memory  metrics  chat_stream  agent_tasks  proactive    │    │
│  │  integrations  oauth  channels  sync  plugins            │    │
│  │  code_security  model_config  knowledge  knowledge_import│    │
│  │  news_monitor  scheduler_config  sdk_sessions  chains    │    │
│  │  shopify  event_config  worker_config  sessions  risk   │    │
│  │  admin_rbac  admin_approvals  admin_config  admin_reports│    │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Core Engine Layer (Singletons)               │    │
│  │                                                          │    │
│  │  EventBus  WorkerRegistry  SkillRegistry  ModelRouter    │    │
│  │  QAAgent  ManagerAgent  OAuthManager  RBAC              │    │
│  │  ProactiveEngine  AutoPullEngine  RuleEngine             │    │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Storage Layer                                │    │
│  │                                                          │    │
│  │  SQLite(sessions.db)  JSON(*.json)  Markdown(*.md)       │    │
│  │  Chroma(Vector DB)  Local Filesystem                     │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 认证交互流程

### 2.1 登录流程

```
Frontend                          Backend
   │                                │
   │  1. POST /api/v1/auth/login    │
   │     { username, password }     │
   │ ────────────────────────────►  │
   │                                │  2. 验证用户名密码
   │                                │  3. JWT 创建 (HS256, exp)
   │                                │  4. 存储 token + user 到 localStorage
   │  5. { access_token,            │
   │       user_id, username, role } │
   │ ◄────────────────────────────  │
   │                                │
   │  6. 设置 localStorage:         │
   │     astra_token = token        │
   │     astra_user = {id,username,role}
```

### 2.2 请求认证机制

```typescript
// 前端: authHeaders() 从 localStorage 读取 token
function authHeaders() {
  const token = localStorage.getItem('astra_token')
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return headers
}
```

```python
# 后端: OAuth2PasswordBearer + JWT 解码 + 可选 Auth
_bearer = HTTPBearer(auto_error=False)

async def _optional_user(creds = Depends(_bearer)):
    if not creds: return None            # SSE 流式可选认证
    payload = _decode_token(creds.credentials)
    uid = payload.get("sub")
    return get_user_by_id(uid) if uid else None

async def get_current_user(token = Depends(oauth2_scheme)):
    if DEV_MODE: return _MOCK_ADMIN       # 开发模式跳过
    payload = _decode_token(token)
    # 查库验证用户存在
    return user
```

### 2.3 角色权限

| 角色 | 描述 | 后端检查 | 前端映射 |
|------|------|----------|----------|
| `admin` | 管理员，可操作所有功能 | `require_admin()` → `user.role == 'admin'` | `isAdmin` |
| `user` | 普通用户，受限 | RBAC 规则引擎 | 页面级条件渲染 |

---

## 3. 通用 CRUD REST 交互

### 3.1 标准请求/响应生命周期

```
Frontend Page                      API Client (config.ts)          Backend Router
     │                                     │                           │
     │ 1. 用户交互触发                      │                           │
     │ (点击/输入/页面加载)                   │                           │
     │ ───►                                │                           │
     │                                     │ 2. 构造 URL + 参数         │
     │                                     │ 3. authHeaders() 注入     │
     │                                     │    Bearer Token           │
     │                                     │ 4. fetch() 发送请求        │
     │                                     │ ───────────────────────►   │
     │                                     │                           │ 5. Token 解析
     │                                     │                           │ 6. 路由匹配
     │                                     │                           │ 7. 业务逻辑执行
     │                                     │                           │ 8. 存储层操作
     │                                     │ 9. JSON Response          │
     │                                     │ ◄───────────────────────  │
     │                                     │ 10. res.ok? → 解析 JSON   │
     │                                     │     !res.ok? → throw Error│
     │ 11. try/catch 处理                   │                           │
     │ ◄───                                │                           │
     │                                     │                           │
     │ 12. 成功: setState 更新 UI           │                           │
     │ 13. 失败: alert/fallback/降级         │                           │
```

### 3.2 典型 CRUD 交互对照

以 Agent 配置为例展示完整的 CRUD 映射：

| 操作 | 前端调用 | 后端端点 | HTTP | 请求体 / 参数 | 响应体 |
|------|----------|----------|------|--------------|--------|
| **列表** | `agentsApi.list()` → `fetch(GET /api/v1/agents)` | `agent_config.py:list_agents()` | `GET` | — | `AgentListItem[]` |
| **详情** | `agentsApi.get(id)` → `fetch(GET /api/v1/agents/{id})` | `agent_config.py:get_agent()` | `GET` | path: `id` | `AgentDetail` |
| **创建** | `agentsApi.create(data)` → `fetch(POST /api/v1/agents, {body})` | `agent_config.py:create_agent()` | `POST` | `AgentUpsertRequest` | `AgentDetail` |
| **更新** | `agentsApi.update(id, data)` → `fetch(PUT /api/v1/agents/{id})` | `agent_config.py:update_agent()` | `PUT` | path: `id`, body: `AgentUpsertRequest` | `AgentDetail` |
| **删除** | `agentsApi.delete(id)` → `fetch(DELETE /api/v1/agents/{id})` | `agent_config.py:delete_agent()` | `DELETE` | path: `id` | `{ok: boolean}` |
| **开关** | `agentsApi.toggle(id, enabled)` → `fetch(PUT /api/v1/agents/{id}/toggle)` | `agent_config.py:toggle_agent()` | `PUT` | `{enabled}` | `{ok, enabled}` |

### 3.3 前端调用代码模式

```typescript
// 典型页面调用模式（AgentConfigPage.tsx）
const loadAgents = useCallback(async () => {
    setLoading(true)
    try {
        const data = await agentsApi.list()
        setAgents(data)                    // 成功 → 更新状态
    } catch {
        setAgents([])                      // 失败 → 空列表降级
    } finally {
        setLoading(false)                  // 始终关闭 loading
    }
}, [])
```

```typescript
// 乐观更新模式（SchedulerConfigPage.tsx）
const handleAction = async (jobId, action) => {
    setActionLoading(`${jobId}_${action}`) // 按钮级 loading
    try {
        if (action === 'pause') await schedulerApi.pause(jobId)
        // ... 其他 action
        await loadData()                    // 操作后刷新列表
    } catch (e) {
        console.error(...)                  // 仅打印日志，不阻塞
    } finally {
        setActionLoading(null)
    }
}
```

---

## 4. SSE 流式对话交互

这是系统中最核心、最复杂的交互模式，覆盖对话/命令/合规查询三大场景。

### 4.1 完整交互时序

```
Frontend (StreamChat + useSSEChat)                     Backend (chat_stream.py)
     │                                                       │
     │  1. App.tsx 启动时                                    │
     │  ConfigLoader → loadConfig()                          │
     │     fetch(GET /api/v1/chat/config)                    │
     │  ────────────────────────────────────────────────►    │
     │  ◄────── { agent_id, tools, skills, ... } ────────── │
     │                                                       │
     │  2. 用户在工具栏选择 Agent / Skill / Tool              │
     │  AgentSelector/ToolPanel/SkillPanel 触发               │
     │  setAgentId() / toggleTool() / toggleSkill()           │
     │  → 更新 Zustand Store → updateConfig()                │
     │     PUT /api/v1/chat/config { patch }                 │
     │  ────────────────────────────────────────────────►    │
     │                                                       │
     │  3. 用户输入消息，点击发送                              │
     │  send("LED灯出口德国需要注意什么")                       │
     │                                                       │
     │  4. POST /api/v1/chat/stream                          │
     │     Headers: { Content-Type: application/json,         │
     │               Accept: text/event-stream }              │
     │     Body: { message, agent_id?, skill_ids?,            │
     │             session_id? }                              │
     │     Signal: AbortController (支持中断)                  │
     │  ────────────────────────────────────────────────►    │
     │                                                       │
     │  一次 SSE 对话的完整事件序列:                            │
     │                                                       │
     │  ◄────────── thinking ──────────────── Step 2: NLU    │
     │  ◄────────── plan ──────────────────── 多阶段规划     │
     │  ◄────────── token ── (流式文本) ───── Step 3: 合规模块│
     │  ◄────────── token ── (流式文本) ─────                │
     │  ◄────────── skill_start ───────────── Step 4: Skill  │
     │  ◄────────── token ── (流式文本) ─────                │
     │  ◄────────── skill_end ───────────────                │
     │  ◄────────── token ── (流式文本) ───── Step 5: 补充   │
     │  ◄────────── action_card ───────────── Step 6: 操作卡 │
     │  ◄────────── done ──────────────────── 完成           │
     │                                                       │
     │  5. 前端逐事件处理:                                     │
     │     parseSSEChunk(buffer) → 按 \n\n 分割               │
     │     → 提取 event: xxx + data: {json}                   │
     │     → 追加到当前 assistant message 的 events[]          │
     │     → 实时重渲染 (React state)                          │
     │                                                       │
     │  6. 收到 done 事件 → 停止流式状态                       │
     │     isStreaming=false, status='idle'                   │
     │                                                       │
     │  7. 用户中断 → abort()                                 │
     │     AbortController.abort()                            │
     │     → catch->AbortError → 标记 isStreaming=false       │
     │                                                       │
     │  8. 网络错误 → catch 生成 errorEvent                    │
     │     → 追加到 events, isStreaming=false, status='error' │
```

### 4.2 SSE 协议格式

```typescript
// 前端解析规则
const SSE_DELIMITER = '\n\n'
const EVENT_PREFIX = 'event: '
const DATA_PREFIX = 'data: '

// 每块格式:
event: token\n
data: {"content": "..."}\n\n

event: done\n
data: {"finish_reason": "...", "usage": {...}}\n\n
```

### 4.3 SSE 事件类型定义

| event 类型 | 触发时机 | data 结构 | 前端处理 |
|-----------|---------|-----------|---------|
| `thinking` | NLU 意图解析/中间推理步骤 | `{ content, depth, ... }` | 显示思考过程 |
| `plan` | 多阶段规划结果 | `{ steps: [...], current_step }` | 显示规划面板 |
| `token` | 流式文本生成 | `{ content }` | 追加到 `textContent` |
| `skill_start` | Skill 开始执行 | `{ skill_name, args, ... }` | 显示 Skill 调用卡片 |
| `skill_end` | Skill 执行完成 | `{ skill_name, result, ... }` | 关闭 Skill 卡片 |
| `action_card` | 合规操作建议 | `{ title, actions: [...] }` | 渲染操作按钮组 |
| `error` | 流程错误 | `{ code, message, recoverable }` | 显示错误，`recoverable=false` 则终止 |
| `done` | 流式完成 | `{ finish_reason, usage? }` | 标记 `isStreaming=false` |

### 4.4 消息状态机

```
                   用户输入 send()
                        │
                        ▼
                 ┌──────────────┐
          ┌─────►│   connecting  │
          │      └──────┬───────┘
          │             │ fetch 成功
          │      ┌──────▼───────┐
          │      │   connected   │←────── SSE 事件流
          │      └──────┬───────┘
          │             │ 收到 done
          │      ┌──────▼───────┐
          │      │     idle     │
          │      └──────┬───────┘
          │             │ 60s 无事件
          │      ┌──────▼───────┐
          └──────┤    error     │
                 └──────────────┘
                          ▲
                     网络错误 / 不可恢复错误
```

### 4.5 对话配置同步

```typescript
// Zustand Store (AppStore.tsx) 管理对话状态
const useAgentConfigStore = create({
    agent_id,      // 当前选中的 Agent
    tools: [],     // 启用的工具列表
    skills: [],    // 启用的技能列表
    pipeline_mode: '6step',
    model_role: 'reasoning',
})

// 每次变更: 乐观更新 Store → 同步后端
// 后端不可用时: 静默降级，保留本地状态
setAgentId(id) → set({ agent_id: id }) + fetch(PUT /api/v1/chat/config)
toggleSkill(id) → toggle array + fetch(PUT /api/v1/chat/config)
```

---

## 5. WebSocket 实时推送交互

### 5.1 连接生命周期

```
Frontend (WebSocketContext)                    Backend (main.py)
     │                                               │
     │  App启动 → 用户登录成功后                       │
     │  WebSocketProvider mount                       │
     │                                               │
     │  new WebSocket("ws://host:8000                 │
     │    /api/v1/ws?user_id={userId}")              │
     │ ──────────────────────────────────────────►   │
     │                                               │  接受连接
     │ ◄────────── WebSocket OPEN ────────────────── │
     │                                               │
     │  onopen: setStatus('connected')                │
     │  setInterval(30s)                              │
     │  send({ type: 'ping' }) ──────►               │
     │                                               │
     │  ... 持续监听 ...                              │
     │                                               │
     │ ◄──── { type: 'session_update',              │  EventBus 发布事件
     │          payload: {...} } ──────────────────  │  → ManagerAgent.on_event()
     │                                               │  → _route_to_websocket()
     │                                               │  → ws_manager.send_to_user()
     │                                               │
     │  onmessage → JSON.parse                        │
     │   → 匹配 handlers[type] 或 handlers[*]        │
     │   → setLastMessage(msg)                        │
     │   → NotificationProvider 消费                   │
     │                                               │
     │  断开/错误 → onclose/onerror                   │
     │    setStatus('disconnected')                   │
     │    setTimeout(5s, reconnect)                   │
     │    → 自动重连循环                              │
```

### 5.2 WebSocket 消息格式

```typescript
interface WSNotification {
    type: string       // 事件类型标识
    payload: unknown   // 事件数据
    timestamp?: number // 可选时间戳
}

// 已知事件类型:
// session_update            → 会话列表变更（创建/删除）
// new_message               → 新 AI 回复消息
// alert                     → 风险预警
// scan_update               → 扫描进度更新
// product_created           → 新产品创建
// compliance_check_failed   → 合规检查失败
// certification_expiry     → 认证到期预警
// regulation_change         → 法规变更通知
```

### 5.3 WebSocket → Notification 管道

```
WebSocketContext                       NotificationProvider
     │                                      │
     │  onmessage(msg)                       │
     │ ───────────────────────────►          │
     │                                      │  1. 解析 payload
     │                                      │  2. inferSeverity(type)
     │                                      │  3. 创建 NotificationItem
     │                                      │     → setNotifications(prev => [...prev, notif])
     │                                      │  4. 创建 ToastItem
     │                                      │     → addToast({severity, title, message})
     │                                      │     → setTimeout(duration, 自动移除)
     │                                      │
     │                                      │  5. 初始加载: riskAlertsApi.list()
     │                                      │     作为已有通知填充
     │                                      │
     │  页面组件通过 useContext 消费           │
     │  unreadCount / notifications / toasts  │
```

---

## 6. 配置层级同步机制

### 6.1 三级配置架构

```
┌─────────────────────────────────────────────────────────────────┐
│  Level 1: 页面交互层 (React Page)                               │
│  用户操作 → 触发 API 调用 → 更新 UI                              │
│  AgentConfigPage → agentsApi.update(id, data)                   │
└────────────────────────────────┬────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│  Level 2: API 层 (config.ts)                                   │
│  request<T>() → fetch → res.json() / throw Error               │
│  统一认证注入、错误封装                                          │
└────────────────────────────────┬────────────────────────────────┘
                                 │ HTTP
┌────────────────────────────────▼────────────────────────────────┐
│  Level 3: 后端持久化层                                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │  SQLite DB  │ │  JSON File  │ │  Markdown   │              │
│  │ sessions.db │ │ *.json      │ │ *.md        │              │
│  │ agents      │ │ tools.json  │ │ events/*.md │              │
│  │ users       │ │ routes.json │ │ workers/*.md│              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 配置生效链路对照

| 配置项 | 前端写入 | 后端持久化 | 运行时消费 | 生效时机 | 生效验证 |
|--------|---------|-----------|-----------|---------|---------|
| **Agent** | `agentsApi.create/update` | SQLite | `agent_config_store` | 下次对话 | ✅ |
| **Skills** | `skillsApi.install/update` | `registry.json` | `SkillRegistry` | 即时 | ✅ |
| **Tools** | `toolsApi.create/update` | `tools/tools.json`（初始化源`_registry.yaml`，脚本`impl/`） | 通过`astra_assistant.py` MCP 工厂消费 | 即时 | ✅ |
| **OAuth** | `oauthApi.create/update` | `connections.json` | `OAuthManager` | 即时 | ✅ |
| **模型路由** | `modelConfigsApi.create/update` | `models/routes.yaml` | ModelRouter 引擎 | 即时 | ✅ |
| **事件** | `event_config` | Markdown | `EventRegistry` | 即时 | ✅ |
| **Worker** | `worker_config` | Markdown | `WorkerRegistry` | 即时 | ✅ |
| **定时任务** | `schedulerApi.create/pause/resume` | APScheduler | APScheduler | 即时 | ✅ |
| **对话配置** | `updateConfig()` → Zustand + PUT | `chat_config.json` | SSE 流式管线 | 即时 | ✅ |

### 6.3 Token → 页面状态路由

```
App.tsx
  │
  ├─ AuthProvider ───────────────────────── 1. 恢复 localStorage token
  │    │                                          2. 校验/登录
  │    ▼
  ├─ AppRoutes
  │     │  loading=true → "加载中..."
  │     │  user=null    → <LoginPage />
  │     │  user!=null   → 登录后页面
  │     │
  │     ├─ WebSocketProvider(userId) ───── WebSocket 连接
  │     │    └─ NotificationProvider ─────   通知/Toast 系统
  │     │         └─ ConfigLoader ──────── 加载对话配置
  │     │              └─ Routes ───────── 页面路由
  │     │
  │     业务页面 (19个)
  │         │
  │         ├─ 配置页 (6个): agents / skills / tools / oauth / models / scheduler
  │         ├─ 监控页 (4个): Overview / AgentMonitor / Metrics / RiskCenter
  │         ├─ 对话页 (3个): ChatWorkspace / ProductChat / SystemCompliance
  │         ├─ 产品页 (2个): ProductList / ProductDetail
  │         └─ 其他 (4个): Knowledge / MemoryTree / Integration / UserManage
```

---

## 7. 错误处理体系

### 7.1 前端错误分层

```
┌─────────────────────────────────────────────┐
│   Layer 1: API 层 (config.ts)               │
│   ─────────────────────────────              │
│   if (!res.ok) {                              │
│     const errBody = await res.text()          │
│     throw new Error(`HTTP ${res.status}: ...`)│
│   }                                           │
│   统一抛出 Error，不区分 HTTP 状态码具体含义     │
├─────────────────────────────────────────────┤
│   Layer 2: 页面层 (Page component)            │
│   ─────────────────────────────              │
│   try {                                       │
│     const data = await api.xxx()              │
│     setState(data)                            │
│   } catch {                                   │
│     // 降级策略：空列表 / 默认值 / 错误提示     │
│   } finally {                                 │
│     setLoading(false)                         │
│   }                                           │
├─────────────────────────────────────────────┤
│   Layer 3: SSE 层 (useSSEChat)               │
│   ─────────────────────────────              │
│   • AbortError → 用户主动中断，正常关闭        │
│   • 网络错误 → 生成 errorEvent，标记 error    │
│   • 后端 error 事件 → 根据 recoverable 决策   │
│     recoverable=true  → 继续流式              │
│     recoverable=false → 终止                  │
└─────────────────────────────────────────────┘
```

### 7.2 常见错误场景与处理

| 场景 | 错误类型 | 前端处理 | 用户可见反馈 |
|------|---------|---------|------------|
| 后端未启动 | 网络错误 (fetch 拒绝) | catch → 降级/空状态 | 空白列表 / 错误提示 |
| Token 过期 | HTTP 401 | `AuthContext` 检测 | 重定向到登录页 |
| 权限不足 | HTTP 403 | try/catch → alert | `需要管理员权限` |
| 数据不存在 | HTTP 404 | try/catch → fallback | 默认值 / 空状态 |
| 服务端异常 | HTTP 500 | try/catch → error state | 加载失败提示 |
| SSE 连接中断 | AbortError / 网络错误 | 自动标记 `status='error'` | 状态指示变红 |
| WebSocket 断开 | `onclose` 事件 | 5s 后自动重连 | 短暂状态变化 |
| CLI 命令不可用 | API 无响应 | 本地回退执行 (help/clear/status) | 命令结果正常显示 |

### 7.3 后端认证错误处理

```python
# 后端 HTTPException 结构 (FastAPI 自动序列化)
HTTPException(
    status_code=401,
    detail="Token 无效或已过期",
    headers={"WWW-Authenticate": "Bearer"},
)
# 前端接收到: HTTP 401 → errBody 为 JSON → detail 字段
```

---

## 8. 前端降级与容错策略

### 8.1 按场景降级策略

| 场景 | 降级行为 | 示例 |
|------|---------|------|
| **配置列表加载失败** | 显示空列表，保留创建功能 | `setAgents([])` |
| **配置详情加载失败** | 用列表数据构造编辑对象 | `setEditing({ ...agent, system_prompt: '' })` |
| **操作请求失败** | alert 错误信息 | `alert(e.message)` |
| **对话配置同步失败** | 回滚到上次成功配置 | `get().loadConfig()` |
| **SSE 连接失败** | 显示错误消息在对话中 | `errorEvent: { type: 'error', code: 'connection_error' }` |
| **WebSocket 断开** | 5s 自动重连 | `setTimeout(connect, 5000)` |
| **CLI API 不可用** | 本地执行简单命令 | help/clear/status 在前端模拟 |
| **通知加载失败** | 静默忽略 | `// 静默降级` |

### 8.2 降级代码模式索引

| 文件 | 降级位置 | 策略 |
|------|---------|------|
| `AgentConfigPage.tsx:19-24` | `catch { setAgents([]) }` | 空列表降级 |
| `AgentConfigPage.tsx:32-35` | `catch { setEditing({...}) }` | 构造默认编辑对象 |
| `SchedulerConfigPage.tsx:74-77` | `catch { setError('...') }` | 显示错误状态 UI |
| `AppStore.tsx:41-44` | `catch { /* 保持默认值 */ }` | 静默保持默认 |
| `AppStore.tsx:63-66` | `catch { loadConfig() }` | 失败回滚 |
| `useSSEChat.ts:221-258` | `catch { errorEvent }` | 完整错误消息降级 |
| `NotificationContext.tsx:82-84` | `catch { /* 静默 */ }` | 静默降级 |
| `StreamChat.tsx:86-113` | `catch { CLI fallback }` | 本地模拟命令 |

---

## 9. 交互场景速查表

### 9.1 页面 → API → 后端文件对照

| 页面 | 前端 API 调用 | 后端文件 | 核心端点 |
|------|-------------|---------|---------|
| AgentConfigPage | `agentsApi.*` | `agent_crud.py` + `agent_extensions.py` | `/api/v1/agents/*` |
| SkillsManagePage | `skillsApi.*` | `skills.py` | `/api/v1/skills/*` |
| ToolsManagePage | `toolsApi.*` | `tools.py` | `/api/v1/tools/*` |
| OAuthManagePage | `oauthApi.*` | `integrations.py` | `/api/v1/integrations/*` |
| ModelConfigPage | `modelConfigsApi.*` | `model_config.py` | `/api/v1/model-configs/*` |
| SchedulerConfigPage | `schedulerApi.*` | `scheduler_config.py` | `/api/v1/scheduler/*` |
| ChatWorkspacePage | `fetch(chat/stream) SSE` | `chat_stream.py` | `POST /api/v1/chat/stream` |
| ProductListPage | `productsApi.*` | `products.py` | `/api/v1/products/*` |
| ProductChatPage | `fetch(chat/stream) SSE` | `chat_stream.py` | `POST /api/v1/chat/stream` |
| OverviewPage | `pipelineApi.*` + `riskAlertsApi.*` | `pipeline.py` + `risk.py` | `/api/v1/pipeline/health` |
| SystemCompliancePage | `fetch(chat/stream) SSE` | `chat_stream.py` | `POST /api/v1/chat/stream` |
| KnowledgePage | `knowledgeApi.*` | `knowledge.py` | `/api/v1/knowledge/*` |
| MemoryTreePage | `memoryApi.*` | `memory.py` | `/api/v1/memory/*` |
| MetricsPage | `metrics_api` (未封装在 config.ts) | `metrics.py` | `/api/v1/metrics/*` |
| AgentMonitorPage | `GET /agents/tasks` | `agent_tasks.py` | `/api/v1/agents/tasks` |
| RiskCenter | `riskAlertsApi.*` | `risk.py` | `/api/v1/risk/*` |
| UserManagePage | `users_api` (未封装在 config.ts) | `users.py` | `/api/v1/users/*` |
| IntegrationPage | `oauthApi.*` | `integrations.py` + `oauth.py` + `channels.py` | `/api/v1/integrations/*` |
| LoginPage | `fetch(auth/register)` | `auth.py` | `POST /api/v1/auth/register` |

### 9.2 三种通信模式对比

| 维度 | REST CRUD | SSE 流式 | WebSocket |
|------|-----------|---------|-----------|
| **传输层** | HTTP 请求/响应 | HTTP 长连接 (流式) | WebSocket 全双工 |
| **方向** | 客户端 → 服务端 | 客户端 → 服务端 (请求) | 双向 |
| | 服务端 → 客户端 (响应) | 服务端 → 客户端 (持续推送) | |
| **前端实现** | `fetch()` + `res.json()` | `fetch()` + `res.body.getReader()` | `new WebSocket(url)` |
| **状态管理** | try/catch + setState | useSSEChat hook | WebSocketContext |
| **自动重连** | 用户手动或页面刷新 | 无 (一次请求) | 5s 自动重连 |
| **适用场景** | 配置管理 CRUD | 对话/AI 生成 | 实时通知/事件推送 |
| **并发控制** | 无特殊 | AbortController 中断 | 心跳 + 重连 |

### 9.3 交互数据流汇总

```
┌──────────────────┐     ┌──────────────────────┐     ┌──────────────────┐
│  前端交互触发     │     │   API 调用模式         │     │  后端处理         │
├──────────────────┤     ├──────────────────────┤     ├──────────────────┤
│ 页面加载         │ ──► │ loading=true → API    │ ──► │ 查询存储 → 返回   │
│                  │     │ → setState → loading  │     │                  │
│                  │     │ false                 │     │                  │
├──────────────────┤     ├──────────────────────┤     ├──────────────────┤
│ 新建/编辑表单提交 │ ──► │ API(POST/PUT)        │ ──► │ 校验 → 持久化     │
│                  │     │ → 成功后刷新列表       │     │ → 返回最新数据    │
├──────────────────┤     ├──────────────────────┤     ├──────────────────┤
│ 删除操作 (确认后) │ ──► │ API(DELETE)          │ ──► │ 存储删除 → 返回   │
│                  │     │ → 刷新列表             │     │                  │
├──────────────────┤     ├──────────────────────┤     ├──────────────────┤
│ 开关/状态变更     │ ──► │ API(PUT toggle)      │ ──► │ 更新存储 → 返回   │
│                  │     │ → 刷新列表             │     │                  │
├──────────────────┤     ├──────────────────────┤     ├──────────────────┤
│ 发送聊天消息     │ ──► │ SSE POST              │ ──► │ 多阶段管线        │
│                  │     │ → 逐事件渲染            │     │ → 逐事件推送       │
├──────────────────┤     ├──────────────────────┤     ├──────────────────┤
│ 实时事件推送     │ ──► │ WebSocket onmessage   │ ──► │ EventBus 发布     │
│                  │     │ → 通知/Toast           │     │ → ws_manager广播   │
│                  │     │ → 自动重连维护          │     │                  │
├──────────────────┤     ├──────────────────────┤     ├──────────────────┤
│ 定时任务操作     │ ──► │ API → 加载/暂停/恢复   │ ──► │ APScheduler 控制  │
│                  │     │ → 刷新任务列表          │     │                  │
├──────────────────┤     ├──────────────────────┤     ├──────────────────┤
│ CLI 命令         │ ──► │ API(POST execute)     │ ──► │ 命令解析 → 执行   │
│                  │     │ → 失败时本地回退        │     │ → 返回结果         │
└──────────────────┘     └──────────────────────┘     └──────────────────┘
```
