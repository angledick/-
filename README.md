# 避风港 SafeHarbor

> 面向中小出海企业的低成本、全链路、可解释 AI 合规基础设施

---

## 项目简介

避风港是一款跨境电商合规智能体平台，将传统高昂的合规服务转化为普惠型数字化解决方案。系统集成规则引擎 + LLM 混合推理 + 多 Agent 协同架构，覆盖产品出海全生命周期的合规需求。

**核心能力：**

- 产品合规预检（HS 编码、VAT、认证矩阵、风险标记）
- 多市场法规监控（EU/US/JP/KR）与实时预警
- Shopify 店铺集成与自动化合规检查
- 六步执行流水线（感知→通知→推荐→对话→执行→回写）
- 多 Agent 调度与 Skills 扩展体系
- SSE 流式 AI 对话与 WebSocket 实时推送

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.13 + FastAPI |
| 前端 | React 18 + TypeScript + Vite + TailwindCSS |
| 向量数据库 | ChromaDB |
| 关系存储 | SQLite |
| LLM | OpenRouter（多模型路由） |
| 认证 | JWT (HS256) |
| 实时通信 | WebSocket + SSE |
| 调度 | APScheduler |

---

## 目录结构

```
astra-main/
├── backend/                   # 后端服务
│   ├── app/
│   │   ├── api/               # 27 个 REST API 路由模块
│   │   ├── core/              # 核心引擎（NLU/规则/事件/调度等）
│   │   ├── services/          # 业务服务层
│   │   ├── storage/           # 分层存储引擎
│   │   ├── knowledge/         # 知识库与市场路由
│   │   ├── models/            # 数据模型
│   │   ├── config.py          # 全局配置
│   │   └── main.py            # FastAPI 入口
│   ├── data/                  # 运行时数据（config/products/prompts等）
│   ├── tests/                 # 测试套件
│   └── requirements.txt       # Python 依赖
├── frontend/                  # 前端 SPA
│   ├── src/
│   │   ├── pages/             # 13 个页面组件
│   │   ├── components/        # 22 个 UI 组件
│   │   ├── context/           # React Context
│   │   ├── hooks/             # 自定义 Hook
│   │   └── api/config.ts      # 统一 API 客户端
│   └── package.json
├── data/config/               # 全局配置
└── .env.example               # 环境变量模板
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
# 编辑 .env 填入 OPENROUTER_API_KEY 等

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
| 风险 | `/api/v1/risk` | 预警与市场扫描 |
| 知识库 | `/api/v1/knowledge` | RAG 文档检索 |
| 记忆 | `/api/v1/memory` | 记忆树浏览 |
| 调度 | `/api/v1/scheduler` | 定时任务 |
| 管理 | `/api/v1/admin` | RBAC 权限管理 |

完整文档请启动后端后访问 `/docs`（Swagger UI）。

---

## 开发指引

### 运行测试

```bash
cd backend
pytest                           # 运行全部测试
pytest tests/test_rule_engine.py # 运行指定文件
pytest --cov=app                 # 带覆盖率
```

详细规范见 [backend/tests/测试规范.md](backend/tests/测试规范.md)。

### 前端类型检查

```bash
cd frontend
npx tsc --noEmit
```

### 代码风格

- 后端：Python 类型注解、FastAPI Depends 依赖注入
- 前端：TypeScript strict、函数式组件、TailwindCSS utility-first
- API 客户端：集中在 `frontend/src/api/config.ts`，类型安全

---

## 环境变量

参考 `.env.example`：

```env
OPENROUTER_API_KEY=your_key_here
JWT_SECRET=your_jwt_secret
SHOPIFY_API_KEY=your_shopify_key
SHOPIFY_API_SECRET=your_shopify_secret
```

---

## 许可证

私有项目，未经授权不得分发。
