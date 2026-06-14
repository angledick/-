# 避风港 SafeHarbor

> 面向中小出海企业的低成本、全链路、可解释 AI 合规基础设施

**在线 Demo：** [https://hks-frontend-eight.vercel.app](https://hks-frontend-eight.vercel.app)

---

## 项目简介

避风港是一款跨境电商合规智能体平台，将传统高昂的合规服务转化为普惠型数字化解决方案。系统集成规则引擎 + LLM 混合推理 + 多 Agent 协同架构，覆盖产品出海全生命周期的合规需求。

平台核心定位是 **"OS 级合规智能体"**——不是一个简单的合规查询工具，而是一个能感知事件、主动响应、自动告知、闭环处理的合规操作系统。

**核心能力：**

| 能力 | 说明 |
|------|------|
| 产品合规预检 | HS 编码匹配、VAT 税率、认证矩阵（CE/FCC/REACH）、风险标记 |
| 多市场法规监控 | EU/US/JP/KR 法规变更实时感知与推送预警 |
| Shopify 深度集成 | OAuth 授权、产品同步、缺失商品检测与飞书推送 |
| 六步执行流水线 | 感知 → 检查 → 推荐 → 告知 → 交互 → 处理 |
| 多 Agent 协同 | Manager/QA/Worker 分层调度，Skills/Tools 动态扩展 |
| RAG 知识库 | ChromaDB 向量检索 + Markdown 文档导入 |
| SSE 流式 AI 对话 | 实时流式响应，支持多 Agent 路由 |
| 物流报关全链路 | 销售订单 → 三单一致性 → 报关单 → 20 国关税计算 |

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.13 + FastAPI + APScheduler |
| 前端 | React 18 + TypeScript + Vite + TailwindCSS + Radix UI |
| 向量数据库 | ChromaDB（RAG 知识检索） |
| 关系存储 | SQLite（会话/订单/报关单） |
| LLM | OpenRouter（多模型路由） + Claude Agent SDK |
| 认证 | JWT (HS256) + OAuth2 |
| 实时通信 | WebSocket + SSE |
| 第三方平台 | Shopify Admin API + 飞书 Bot |

---

## 目录结构

```
astra-main/
├── backend/                   # 后端服务
│   ├── app/
│   │   ├── api/               # 50 个 REST API 路由模块
│   │   ├── core/              # 核心引擎（31 个模块）
│   │   │   ├── event_bus.py          # 事件总线
│   │   │   ├── scheduler.py          # 定时调度器
│   │   │   ├── compliance_rules.py   # 合规规则引擎
│   │   │   ├── manager_agent.py      # 管理 Agent
│   │   │   ├── qa_agent.py           # QA Agent
│   │   │   ├── proactive_engine.py   # 主动响应引擎
│   │   │   ├── risk_intel_engine.py  # 风险情报引擎
│   │   │   ├── channel_adapter.py    # 多渠道适配器
│   │   │   ├── feishu_client.py      # 飞书 Bot
│   │   │   ├── security_sandbox.py   # 安全沙箱
│   │   │   └── ...
│   │   ├── services/          # 业务服务层（12 个服务）
│   │   │   ├── shopify_api.py        # Shopify API 封装
│   │   │   ├── astra_assistant.py    # Claude Agent SDK 集成
│   │   │   ├── ws_manager.py         # WebSocket 管理
│   │   │   └── ...
│   │   ├── storage/           # 分层存储引擎（14 个存储）
│   │   ├── knowledge/         # 知识库与市场路由
│   │   ├── models/            # 数据模型
│   │   ├── config.py          # 全局配置
│   │   └── main.py            # FastAPI 入口
│   ├── data/                  # 运行时数据
│   │   ├── agents/            # Agent 定义
│   │   ├── events/            # 事件模板
│   │   ├── skills/            # 技能定义
│   │   ├── prompts/           # 提示词模板（21 个）
│   │   ├── scheduler/         # 定时任务配置
│   │   └── global/            # 全局索引
│   ├── tests/                 # 测试套件
│   └── requirements.txt
├── frontend/                  # 前端 SPA
│   ├── src/
│   │   ├── pages/             # 31 个页面组件
│   │   ├── components/        # 22 个 UI 组件
│   │   ├── context/           # React Context（Auth/WS/Notification）
│   │   ├── hooks/             # 自定义 Hooks
│   │   └── lib/api/           # 统一 API 客户端
│   └── package.json
├── data/config/               # 全局配置
├── .env.example               # 环境变量模板
├── 产品文档.md                 # 产品视角说明
├── 技术文档.md                 # 技术架构说明
└── 历史代码参考说明.md          # 架构演进说明
```

---

## 快速启动

### 环境准备

- Python 3.13+
- Node.js 18+
- (可选) ChromaDB 实例

### 后端启动

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 OPENROUTER_API_KEY / SHOPIFY_API_KEY 等

# 启动服务（默认 8001 端口）
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 开发模式启动（默认 5173 端口）
npm run dev
```

### 访问

- **在线 Demo**：[https://hks-frontend-eight.vercel.app](https://hks-frontend-eight.vercel.app)
- 前端页面：http://localhost:5173
- 后端 API：http://localhost:8001/api/v1
- API 文档：http://localhost:8001/docs
- 默认账号：`admin` / `admin123`

---

## API 概览

系统提供 200+ 个 REST 端点，主要分组：

| 模块 | 路径前缀 | 说明 |
|------|----------|------|
| 认证 | `/api/v1/auth` | 登录、用户管理 |
| 对话 | `/api/v1/chat/stream` | SSE 流式 AI 对话 |
| 产品 | `/api/v1/products` | 产品全生命周期管理 |
| 事件 | `/api/v1/events` | 事件总线 |
| Shopify | `/api/v1/shopify` | OAuth + 产品同步 |
| Agent | `/api/v1/agents` | 多 Agent 配置调度 |
| Skills | `/api/v1/skills` | 技能扩展管理 |
| 风险 | `/api/v1/risk` + `/api/v1/risk-intel` | 预警与市场扫描 |
| 知识库 | `/api/v1/knowledge` | RAG 文档检索 |
| 记忆 | `/api/v1/memory` | 记忆树浏览 |
| 调度 | `/api/v1/scheduler` | 定时任务 |
| 订单 | `/api/v1/orders` | 销售订单 + 三单一致性 |
| 报关 | `/api/v1/customs` | 报关单 + 关税计算 |
| 物流 | `/api/v1/logistics` | 物流追踪 + Webhook |
| 管理 | `/api/v1/admin` | RBAC 权限管理 |
| 飞书 | `/api/v1/feishu` | 飞书 Bot 集成 |

完整文档请启动后端后访问 `/docs`（Swagger UI）。

---

## 核心功能

### 1. 产品合规预检
- 输入产品名称/类型 → 自动匹配 HS 编码 → 检索 VAT 税率 → 检查认证要求（CE/FCC/REACH）
- 生成结构化合规报告，标记风险等级（低/中/高/禁运）

### 2. Shopify 店铺集成
- OAuth 授权流程（CLI + Web 双模式）
- 定时产品同步（每 20 分钟）
- 缺失商品检测 → 飞书群推送
- Webhook 事件监听 → 自动触发合规检查

### 3. 风险情报监控
- EU/US/JP/KR 多市场法规变更监控
- 定时扫描（每小时）→ 风险评估 → 多渠道推送（飞书/Webhook）
- 风险等级分级（低/中/高/紧急）

### 4. 多 Agent 协同
- Manager Agent：事件分发与任务路由
- QA Agent：质量保证与系统诊断
- Worker Agents：合规检查、法规扫描、商品同步等
- Skills/Tools 动态扩展：可热插拔的能力体系

### 5. 物流报关全链路
- 销售订单管理 → 三单一致性检查（6 维度）
- 报关单生成（15 个扩展字段）
- 关税计算（20 国税率表）
- 17TRACK/AfterShip Webhook 物流追踪

---

## 开发指引

### 运行测试

```bash
cd backend
pytest                           # 运行全部测试
pytest tests/test_rule_engine.py # 运行指定文件
pytest --cov=app                 # 带覆盖率
```

### 前端类型检查

```bash
cd frontend
npx tsc --noEmit
```

### 代码风格

- 后端：Python 类型注解、FastAPI Depends 依赖注入
- 前端：TypeScript strict、函数式组件、TailwindCSS utility-first
- API 客户端：集中在 `frontend/src/lib/api/`，类型安全

---

## 环境变量

参考 `.env.example`：

```env
OPENROUTER_API_KEY=your_key_here
JWT_SECRET=your_jwt_secret
SHOPIFY_API_KEY=your_shopify_key
SHOPIFY_API_SECRET=your_shopify_secret
SHOPIFY_SHOP_DOMAIN=your-store.myshopify.com
ANTHROPIC_API_KEY=your_anthropic_key
FEISHU_APP_ID=your_feishu_app_id
FEISHU_APP_SECRET=your_feishu_app_secret
```

---

## 文档

| 文档 | 说明 |
|------|------|
| [产品文档.md](产品文档.md) | 产品视角：功能矩阵、用户场景、价值主张 |
| [技术文档.md](技术文档.md) | 技术视角：架构设计、数据流转、API 规格 |
| [历史代码参考说明.md](历史代码参考说明.md) | 架构演进：从 Mock 原型到全链路实现 |

---

## 许可证

私有项目，未经授权不得分发。
