# React应用结构

<cite>
**本文档引用的文件**
- [frontend/src/main.tsx](file://frontend/src/main.tsx)
- [frontend/index.html](file://frontend/index.html)
- [frontend/src/App.tsx](file://frontend/src/App.tsx)
- [frontend/vite.config.ts](file://frontend/vite.config.ts)
- [frontend/package.json](file://frontend/package.json)
- [frontend/tsconfig.json](file://frontend/tsconfig.json)
- [frontend/src/context/AuthContext.tsx](file://frontend/src/context/AuthContext.tsx)
- [frontend/src/context/AppStore.tsx](file://frontend/src/context/AppStore.tsx)
- [frontend/src/context/WebSocketContext.tsx](file://frontend/src/context/WebSocketContext.tsx)
- [frontend/src/context/NotificationContext.tsx](file://frontend/src/context/NotificationContext.tsx)
- [frontend/src/components/Layout.tsx](file://frontend/src/components/Layout.tsx)
- [frontend/src/components/Sidebar.tsx](file://frontend/src/components/Sidebar.tsx)
- [frontend/src/components/NotificationCenter.tsx](file://frontend/src/components/NotificationCenter.tsx)
- [frontend/src/components/ToastNotification.tsx](file://frontend/src/components/ToastNotification.tsx)
- [frontend/src/pages/LoginPage.tsx](file://frontend/src/pages/LoginPage.tsx)
- [frontend/src/pages/OverviewPage.tsx](file://frontend/src/pages/OverviewPage.tsx)
- [frontend/src/api/config.ts](file://frontend/src/api/config.ts)
- [frontend/src/types/index.ts](file://frontend/src/types/index.ts)
- [shopify-app/astra-compliance/app/root.jsx](file://shopify-app/astra-compliance/app/root.jsx)
- [shopify-app/astra-compliance/app/routes/_index/route.jsx](file://shopify-app/astra-compliance/app/routes/_index/route.jsx)
- [shopify-app/astra-compliance/app/routes/auth.login/route.jsx](file://shopify-app/astra-compliance/app/routes/auth.login/route.jsx)
- [shopify-app/astra-compliance/app/db.server.js](file://shopify-app/astra-compliance/app/db.server.js)
- [shopify-app/astra-compliance/prisma/schema.prisma](file://shopify-app/astra-compliance/prisma/schema.prisma)
- [shopify-app/astra-compliance/package.json](file://shopify-app/astra-compliance/package.json)
- [shopify-app/astra-compliance/vite.config.js](file://shopify-app/astra-compliance/vite.config.js)
- [shopify-app/astra-compliance/tsconfig.json](file://shopify-app/astra-compliance/tsconfig.json)
</cite>

## 更新摘要
**所做更改**
- 新增Shopify应用前端架构章节，涵盖React Router 7.12.0、TypeScript、Prisma集成
- 更新架构总览图，包含Shopify应用的现代前端技术栈
- 新增Shopify应用的数据库设计与Prisma集成说明
- 扩展依赖关系分析，包含Shopify应用的现代化技术栈
- 更新性能考虑章节，增加Shopify应用的优化策略

## 目录
1. [引言](#引言)
2. [项目结构](#项目结构)
3. [核心组件](#核心组件)
4. [架构总览](#架构总览)
5. [详细组件分析](#详细组件分析)
6. [Shopify应用前端架构](#shopify应用前端架构)
7. [依赖关系分析](#依赖关系分析)
8. [性能考虑](#性能考虑)
9. [故障排查指南](#故障排查指南)
10. [结论](#结论)
11. [附录](#附录)

## 引言
本文件面向避风港平台的React前端应用，系统性梳理从应用入口到页面渲染的完整流程，重点覆盖以下方面：
- 应用入口与初始化：main.tsx如何挂载根组件App.tsx
- 根组件设计模式：路由、认证、通知、WebSocket与全局状态的组合使用
- Vite构建与开发服务器：插件、代理与脚本配置
- 路由系统与页面组织：静态路由与布局嵌套
- 生命周期管理、错误边界与性能监控集成
- 组件树结构、代码分割与Bundle优化策略
- **新增** Shopify应用前端架构：React Router 7.12.0、TypeScript、Prisma集成等现代化前端技术栈

## 项目结构
前端位于frontend目录，采用React + TypeScript + Vite技术栈，使用TailwindCSS进行样式管理。项目采用按功能域划分的目录组织方式，核心目录包括：
- src：源码目录
  - api：统一的后端API封装
  - components：可复用UI组件
  - context：全局状态与上下文（认证、WebSocket、通知、Zustand）
  - hooks：自定义Hook
  - pages：页面组件
  - types：类型定义
  - main.tsx：应用入口
  - App.tsx：根组件
- 构建配置：vite.config.ts、tsconfig.json、package.json
- HTML入口：index.html

**新增** Shopify应用位于shopify-app目录，采用Shopify React App架构，包含：
- app：应用路由和组件
- prisma：数据库模式和迁移
- 现代化技术栈：React Router 7.12.0、TypeScript、Prisma集成

```mermaid
graph TB
A["index.html<br/>挂载点 #root"] --> B["main.tsx<br/>创建根容器"]
B --> C["App.tsx<br/>BrowserRouter + Providers"]
C --> D["AuthContext<br/>登录/鉴权"]
C --> E["WebSocketContext<br/>实时通知"]
C --> F["NotificationContext<br/>通知/Toast"]
C --> G["AppRoutes<br/>路由与页面"]
G --> H["Layout<br/>侧边栏/顶部栏/Outlet"]
H --> I["Sidebar<br/>导航"]
H --> J["Outlet<br/>子路由内容"]
J --> K["OverviewPage<br/>概览页"]
J --> L["其他页面组件..."]
subgraph "Shopify应用架构"
S["shopify-app/<br/>React Router 7.12.0"]
S --> R["app/<br/>路由与组件"]
S --> P["prisma/<br/>数据库模式"]
S --> T["TypeScript<br/>类型安全"]
S --> PR["Prisma<br/>ORM集成"]
end
```

**图表来源**
- [frontend/index.html:8-11](file://frontend/index.html#L8-L11)
- [frontend/src/main.tsx:1-10](file://frontend/src/main.tsx#L1-L10)
- [frontend/src/App.tsx:1-93](file://frontend/src/App.tsx#L1-L93)
- [shopify-app/astra-compliance/app/root.jsx](file://shopify-app/astra-compliance/app/root.jsx)
- [shopify-app/astra-compliance/prisma/schema.prisma](file://shopify-app/astra-compliance/prisma/schema.prisma)

**章节来源**
- [frontend/index.html:1-12](file://frontend/index.html#L1-L12)
- [frontend/src/main.tsx:1-10](file://frontend/src/main.tsx#L1-L10)
- [shopify-app/astra-compliance/package.json](file://shopify-app/astra-compliance/package.json)

## 核心组件
本节聚焦应用启动与根组件的关键职责与实现要点。

- 应用入口 main.tsx
  - 使用React 18的createRoot挂载App组件
  - 引入全局样式与根组件
  - 严格模式包裹，便于捕获潜在问题

- 根组件 App.tsx
  - 使用BrowserRouter包裹，提供路由能力
  - 通过AuthProvider注入认证上下文
  - AppRoutes根据登录状态决定渲染登录页或受保护路由
  - 在受保护路由下，嵌套WebSocketProvider、NotificationProvider与ConfigLoader，实现实时通知、通知中心与Agent配置加载
  - 路由表定义了完整的页面映射，包含概览、合规、产品、对话、知识库、配置中心、内存树、指标、Agent监控、用户管理、风险中心等

- 全局状态与上下文
  - AuthContext：负责登录、登出、token持久化、鉴权fetch封装
  - WebSocketContext：WebSocket连接、心跳、自动重连、事件分发
  - NotificationContext：通知中心与Toast管理，支持WebSocket事件驱动
  - AppStore（Zustand）：Agent配置、侧边栏状态等

**新增** Shopify应用核心组件
- root.jsx：应用根组件，提供路由容器和上下文提供者
- db.server.js：数据库服务器配置，集成Prisma ORM
- 路由组件：基于React Router 7.12.0的现代化路由系统

**章节来源**
- [frontend/src/main.tsx:1-10](file://frontend/src/main.tsx#L1-L10)
- [frontend/src/App.tsx:1-93](file://frontend/src/App.tsx#L1-L93)
- [frontend/src/context/AuthContext.tsx:1-106](file://frontend/src/context/AuthContext.tsx#L1-L106)
- [frontend/src/context/WebSocketContext.tsx:1-132](file://frontend/src/context/WebSocketContext.tsx#L1-L132)
- [frontend/src/context/NotificationContext.tsx:1-187](file://frontend/src/context/NotificationContext.tsx#L1-L187)
- [frontend/src/context/AppStore.tsx:1-107](file://frontend/src/context/AppStore.tsx#L1-L107)
- [shopify-app/astra-compliance/app/root.jsx](file://shopify-app/astra-compliance/app/root.jsx)
- [shopify-app/astra-compliance/app/db.server.js](file://shopify-app/astra-compliance/app/db.server.js)

## 架构总览
应用采用"入口 -> 根组件 -> 上下文提供者 -> 路由 -> 页面"的分层架构。认证与实时通信贯穿整个应用，全局状态通过Zustand集中管理。

**更新** 新增Shopify应用的现代化前端技术栈架构：

```mermaid
graph TB
subgraph "传统React应用"
M["main.tsx"]
I["index.html"]
A["App.tsx"]
AC["AuthContext"]
WC["WebSocketContext"]
NC["NotificationContext"]
ZS["Zustand Store(AppStore)"]
R["AppRoutes"]
L["Layout"]
S["Sidebar"]
P1["OverviewPage"]
P2["LoginPage"]
P3["其他页面..."]
end
subgraph "Shopify应用架构"
SR["Shopify Root"]
SC["Shopify Components"]
SP["Prisma ORM"]
SD["Database Schema"]
ST["TypeScript"]
SRT["React Router 7.12.0"]
end
I --> M --> A
A --> AC
A --> WC
A --> NC
A --> ZS
A --> R
R --> L
L --> S
L --> P1
R --> P2
R --> P3
SR --> SC
SC --> SP
SP --> SD
SC --> ST
SC --> SRT
```

**图表来源**
- [frontend/src/main.tsx:1-10](file://frontend/src/main.tsx#L1-L10)
- [frontend/src/App.tsx:1-93](file://frontend/src/App.tsx#L1-L93)
- [shopify-app/astra-compliance/app/root.jsx](file://shopify-app/astra-compliance/app/root.jsx)
- [shopify-app/astra-compliance/prisma/schema.prisma](file://shopify-app/astra-compliance/prisma/schema.prisma)
- [shopify-app/astra-compliance/package.json](file://shopify-app/astra-compliance/package.json)

**章节来源**
- [frontend/src/main.tsx:1-10](file://frontend/src/main.tsx#L1-L10)
- [frontend/src/App.tsx:1-93](file://frontend/src/App.tsx#L1-L93)
- [shopify-app/astra-compliance/app/root.jsx](file://shopify-app/astra-compliance/app/root.jsx)

## 详细组件分析

### 应用入口与初始化流程
- HTML提供挂载点#root
- main.tsx创建根容器并渲染<App />
- App.tsx在BrowserRouter内注入AuthProvider，随后根据登录状态决定渲染路径

```mermaid
sequenceDiagram
participant Browser as "浏览器"
participant HTML as "index.html"
participant Main as "main.tsx"
participant App as "App.tsx"
participant Auth as "AuthContext"
Browser->>HTML : 加载页面
HTML-->>Browser : 渲染 <div id="root"></div>
Browser->>Main : 执行入口脚本
Main->>App : createRoot(...).render(<App />)
App->>Auth : 初始化AuthProvider
App->>App : 判断登录状态并渲染路由
```

**图表来源**
- [frontend/index.html:8-11](file://frontend/index.html#L8-L11)
- [frontend/src/main.tsx:1-10](file://frontend/src/main.tsx#L1-L10)
- [frontend/src/App.tsx:1-93](file://frontend/src/App.tsx#L1-L93)
- [frontend/src/context/AuthContext.tsx:1-106](file://frontend/src/context/AuthContext.tsx#L1-L106)

**章节来源**
- [frontend/index.html:1-12](file://frontend/index.html#L1-L12)
- [frontend/src/main.tsx:1-10](file://frontend/src/main.tsx#L1-L10)
- [frontend/src/App.tsx:1-93](file://frontend/src/App.tsx#L1-L93)

### 根组件设计模式与路由系统
- 根组件App.tsx通过BrowserRouter提供路由能力
- AppRoutes根据useAuth的状态决定渲染：
  - loading态：显示加载中
  - 未登录：渲染LoginPage
  - 已登录：渲染Layout与受保护路由
- 路由表覆盖概览、系统合规、产品、对话、知识库、配置中心、内存树、指标、Agent监控、用户管理、风险中心等页面
- Layout组件负责侧边栏、顶部状态栏与Outlet，形成主内容区域

```mermaid
flowchart TD
Start(["进入 AppRoutes"]) --> CheckLoading{"是否正在加载?"}
CheckLoading --> |是| ShowLoading["显示加载中界面"]
CheckLoading --> |否| CheckUser{"是否有用户?"}
CheckUser --> |否| RenderLogin["渲染 LoginPage"]
CheckUser --> |是| RenderLayout["渲染 Layout + 受保护路由"]
RenderLayout --> Routes["Routes 定义页面映射"]
Routes --> End(["完成渲染"])
```

**图表来源**
- [frontend/src/App.tsx:35-82](file://frontend/src/App.tsx#L35-L82)
- [frontend/src/components/Layout.tsx:1-60](file://frontend/src/components/Layout.tsx#L1-L60)
- [frontend/src/pages/LoginPage.tsx:1-90](file://frontend/src/pages/LoginPage.tsx#L1-L90)

**章节来源**
- [frontend/src/App.tsx:1-93](file://frontend/src/App.tsx#L1-L93)
- [frontend/src/components/Layout.tsx:1-60](file://frontend/src/components/Layout.tsx#L1-L60)
- [frontend/src/pages/LoginPage.tsx:1-90](file://frontend/src/pages/LoginPage.tsx#L1-L90)

### 认证上下文与登录流程
- AuthProvider负责：
  - 启动时从localStorage恢复token与用户信息
  - 提供login、logout方法
  - 封装authFetch，自动附加Authorization头
- LoginPage接收用户名/密码，调用login并处理错误

```mermaid
sequenceDiagram
participant UI as "LoginPage"
participant Auth as "AuthContext"
participant API as "后端 /api/v1/auth/login"
UI->>Auth : login(username, password)
Auth->>API : POST /api/v1/auth/login
API-->>Auth : 返回 access_token 与 user_id/role
Auth->>Auth : 写入 localStorage
Auth-->>UI : 设置 user/token 状态
```

**图表来源**
- [frontend/src/context/AuthContext.tsx:44-72](file://frontend/src/context/AuthContext.tsx#L44-L72)
- [frontend/src/pages/LoginPage.tsx:11-23](file://frontend/src/pages/LoginPage.tsx#L11-L23)

**章节来源**
- [frontend/src/context/AuthContext.tsx:1-106](file://frontend/src/context/AuthContext.tsx#L1-L106)
- [frontend/src/pages/LoginPage.tsx:1-90](file://frontend/src/pages/LoginPage.tsx#L1-L90)

### 实时通知与WebSocket集成
- WebSocketContext：
  - 连接URL基于当前主机与固定端口
  - 支持心跳与自动重连
  - 事件分发：按type分发至注册处理器，支持通配符*
- NotificationContext：
  - 初始化时拉取风险预警作为通知
  - 监听WebSocket事件，生成通知与Toast
  - 提供通知增删改查与Toast管理

```mermaid
sequenceDiagram
participant WS as "WebSocketContext"
participant NC as "NotificationContext"
participant API as "后端 /api/v1/risk/alerts"
participant UI as "NotificationCenter/Toast"
WS->>WS : 连接 ws : //host : 8000/api/v1/ws?user_id=...
WS->>NC : on('*', handler)
NC->>API : GET /api/v1/risk/alerts
API-->>NC : 返回 alerts
NC->>UI : 渲染通知与Toast
WS-->>NC : 收到消息 -> 触发 handler
NC->>UI : 新增通知/Toast
```

**图表来源**
- [frontend/src/context/WebSocketContext.tsx:31-108](file://frontend/src/context/WebSocketContext.tsx#L31-L108)
- [frontend/src/context/NotificationContext.tsx:59-117](file://frontend/src/context/NotificationContext.tsx#L59-L117)
- [frontend/src/api/config.ts:408-434](file://frontend/src/api/config.ts#L408-L434)

**章节来源**
- [frontend/src/context/WebSocketContext.tsx:1-132](file://frontend/src/context/WebSocketContext.tsx#L1-L132)
- [frontend/src/context/NotificationContext.tsx:1-187](file://frontend/src/context/NotificationContext.tsx#L1-L187)
- [frontend/src/api/config.ts:1-635](file://frontend/src/api/config.ts#L1-L635)

### 全局状态与配置加载
- AppStore（Zustand）：
  - Agent配置：loadConfig、updateConfig、切换工具/技能、设置当前Agent
  - 侧边栏状态：collapsed、toggle、setCollapsed
- ConfigLoader在AppRoutes中首次渲染时触发loadConfig，保证页面渲染前具备基础配置

```mermaid
flowchart TD
Start(["AppRoutes 渲染"]) --> LoadCfg["ConfigLoader 调用 loadConfig()"]
LoadCfg --> FetchAPI["GET /api/v1/chat/config"]
FetchAPI --> UpdateStore["更新 Zustand Store"]
UpdateStore --> RenderRoutes["渲染受保护路由"]
```

**图表来源**
- [frontend/src/App.tsx:29-33](file://frontend/src/App.tsx#L29-L33)
- [frontend/src/context/AppStore.tsx:28-44](file://frontend/src/context/AppStore.tsx#L28-L44)

**章节来源**
- [frontend/src/context/AppStore.tsx:1-107](file://frontend/src/context/AppStore.tsx#L1-L107)
- [frontend/src/App.tsx:28-33](file://frontend/src/App.tsx#L28-L33)

### 页面组件与数据流
- OverviewPage：
  - 并行加载产品数量、市场数量、合规总分与风险预警
  - 支持自动刷新与手动刷新
  - 提供风险预警忽略、严重级别筛选、快速入口等交互
- API封装：
  - api/config.ts统一管理各类API，提供request封装与鉴权头处理
  - types/index.ts定义了对话、事件链、风险预警、产品、定时任务等核心类型

```mermaid
sequenceDiagram
participant OP as "OverviewPage"
participant API as "api/config.ts"
participant BE as "后端接口"
OP->>API : 并行调用 productsApi.list/pipelineApi.health/riskAlertsApi.list
API->>BE : GET /api/v1/products, /api/v1/pipeline/health, /api/v1/risk/alerts
BE-->>API : 返回数据
API-->>OP : Promise.allSettled 结果
OP->>OP : 更新状态/渲染UI
```

**图表来源**
- [frontend/src/pages/OverviewPage.tsx:54-81](file://frontend/src/pages/OverviewPage.tsx#L54-L81)
- [frontend/src/api/config.ts:362-434](file://frontend/src/api/config.ts#L362-L434)
- [frontend/src/types/index.ts:448-477](file://frontend/src/types/index.ts#L448-L477)

**章节来源**
- [frontend/src/pages/OverviewPage.tsx:1-316](file://frontend/src/pages/OverviewPage.tsx#L1-L316)
- [frontend/src/api/config.ts:1-635](file://frontend/src/api/config.ts#L1-L635)
- [frontend/src/types/index.ts:1-477](file://frontend/src/types/index.ts#L1-L477)

### 组件树结构与交互
- 组件树（简化）：index.html -> main.tsx -> App.tsx -> AuthProvider -> AppRoutes -> Layout -> Sidebar + Outlet -> 子页面
- 交互链路：用户操作 -> 上下文/状态更新 -> 重新渲染 -> 可能触发API调用

```mermaid
graph TB
Root["App.tsx"] --> Auth["AuthContext"]
Root --> WS["WebSocketContext"]
Root --> Noti["NotificationContext"]
Root --> Store["Zustand Store"]
Root --> Routes["AppRoutes"]
Routes --> Layout["Layout"]
Layout --> Sidebar["Sidebar"]
Layout --> Outlet["Outlet"]
Outlet --> Overview["OverviewPage"]
```

**图表来源**
- [frontend/src/App.tsx:1-93](file://frontend/src/App.tsx#L1-L93)
- [frontend/src/components/Layout.tsx:1-60](file://frontend/src/components/Layout.tsx#L1-L60)
- [frontend/src/components/Sidebar.tsx:1-163](file://frontend/src/components/Sidebar.tsx#L1-L163)
- [frontend/src/pages/OverviewPage.tsx:1-316](file://frontend/src/pages/OverviewPage.tsx#L1-L316)

## Shopify应用前端架构

**新增** Shopify应用采用现代化前端技术栈，包含React Router 7.12.0、TypeScript、Prisma集成等先进特性：

### 应用入口与根组件
- root.jsx：Shopify应用的根组件，提供路由容器和上下文提供者
- 基于React Router 7.12.0的现代化路由系统，支持最新的路由特性
- TypeScript类型安全，提供更好的开发体验和运行时保障

### 路由系统与页面组织
- app/routes：采用Shopify推荐的路由组织方式
- _index：默认首页路由
- auth.login：登录认证路由
- app：主应用路由
- webhooks：Shopify Webhook处理路由

### 数据库与ORM集成
- prisma/schema.prisma：数据库模式定义
- db.server.js：数据库服务器配置
- Prisma ORM：类型安全的数据库操作
- 支持多种数据库后端（PostgreSQL、MySQL、SQLite等）

### 现代化技术栈特性
- React Router 7.12.0：最新版本的路由库，提供更好的性能和开发体验
- TypeScript：完整的类型系统，提升代码质量和可维护性
- Prisma：现代化ORM，支持数据库迁移和模式验证
- Vite构建：快速的开发服务器和构建工具
- TailwindCSS：实用优先的CSS框架

```mermaid
graph TB
subgraph "Shopify应用技术栈"
R7["React Router 7.12.0<br/>现代化路由"]
TS["TypeScript<br/>类型安全"]
PR["Prisma ORM<br/>数据库操作"]
VITE["Vite<br/>构建工具"]
TW["TailwindCSS<br/>样式框架"]
END
end
subgraph "应用结构"
ROOT["root.jsx<br/>根组件"]
ROUTES["routes/<br/>路由组织"]
DB["db.server.js<br/>数据库配置"]
PRISMA["prisma/schema.prisma<br/>数据库模式"]
END
end
R7 --> ROOT
TS --> ROUTES
PR --> DB
VITE --> PRISMA
TW --> ROOT
```

**图表来源**
- [shopify-app/astra-compliance/app/root.jsx](file://shopify-app/astra-compliance/app/root.jsx)
- [shopify-app/astra-compliance/prisma/schema.prisma](file://shopify-app/astra-compliance/prisma/schema.prisma)
- [shopify-app/astra-compliance/app/db.server.js](file://shopify-app/astra-compliance/app/db.server.js)
- [shopify-app/astra-compliance/package.json](file://shopify-app/astra-compliance/package.json)

**章节来源**
- [shopify-app/astra-compliance/app/root.jsx](file://shopify-app/astra-compliance/app/root.jsx)
- [shopify-app/astra-compliance/app/routes/_index/route.jsx](file://shopify-app/astra-compliance/app/routes/_index/route.jsx)
- [shopify-app/astra-compliance/app/routes/auth.login/route.jsx](file://shopify-app/astra-compliance/app/routes/auth.login/route.jsx)
- [shopify-app/astra-compliance/prisma/schema.prisma](file://shopify-app/astra-compliance/prisma/schema.prisma)
- [shopify-app/astra-compliance/package.json](file://shopify-app/astra-compliance/package.json)

## 依赖关系分析
- 构建与开发
  - Vite插件：@vitejs/plugin-react、@tailwindcss/vite
  - 开发服务器：本地端口5173，代理/api到后端服务
  - 脚本：dev/build/preview
- 类型与编译：TypeScript配置为ESNext模块解析，bundler模式，JSX使用react-jsx
- 运行时依赖：react、react-dom、react-router-dom、zustand、react-markdown

**更新** Shopify应用依赖关系：
- React Router 7.12.0：现代化路由库
- Prisma：数据库ORM和迁移工具
- TypeScript：类型系统
- Vite：构建工具
- TailwindCSS：样式框架

```mermaid
graph LR
Vite["vite.config.ts"] --> Plugins["插件: react, tailwindcss"]
Vite --> DevServer["开发服务器: 5173, 代理 /api"]
Pkg["package.json"] --> Scripts["脚本: dev/build/preview"]
TS["tsconfig.json"] --> Module["moduleResolution: bundler"]
TS --> JSX["jsx: react-jsx"]
subgraph "Shopify应用依赖"
R7["react-router@7.12.0"]
PR["prisma"]
TS2["typescript"]
VITE2["vite"]
TAIL["tailwindcss"]
end
```

**图表来源**
- [frontend/vite.config.ts:1-16](file://frontend/vite.config.ts#L1-L16)
- [frontend/package.json:1-28](file://frontend/package.json#L1-L28)
- [frontend/tsconfig.json:1-20](file://frontend/tsconfig.json#L1-L20)
- [shopify-app/astra-compliance/package.json](file://shopify-app/astra-compliance/package.json)

**章节来源**
- [frontend/vite.config.ts:1-16](file://frontend/vite.config.ts#L1-L16)
- [frontend/package.json:1-28](file://frontend/package.json#L1-L28)
- [frontend/tsconfig.json:1-20](file://frontend/tsconfig.json#L1-L20)
- [shopify-app/astra-compliance/package.json](file://shopify-app/astra-compliance/package.json)

## 性能考虑
- 代码分割与懒加载
  - 当前路由以静态导入为主；如需进一步优化，可在路由层面引入动态导入（例如将大型页面组件按需加载），减少首屏包体积
- 构建优化
  - 使用Vite默认Rollup打包器，结合Tree-shaking与最小化策略
  - TailwindCSS按需生成样式，避免冗余类
- 状态与渲染
  - 使用Zustand替代Redux，降低样板代码与内存占用
  - 合理拆分组件，避免不必要的重渲染
- 网络与缓存
  - API封装统一处理鉴权头，减少重复逻辑
  - WebSocket长连接配合心跳维持，提升实时性

**新增** Shopify应用性能优化策略：
- React Router 7.12.0的路由懒加载支持，减少初始包大小
- Prisma的查询优化和连接池管理
- TypeScript的编译时优化
- Vite的快速热重载和构建优化

## 故障排查指南
- 登录失败
  - 检查AuthContext.login的错误处理与提示
  - 确认后端登录接口返回格式与异常分支
- WebSocket无法连接
  - 核对WebSocketContext中的连接地址与端口
  - 关注自动重连逻辑与心跳机制
- 通知不显示
  - 确认NotificationContext已订阅WebSocket事件
  - 检查风险预警API是否可用
- 页面空白或路由不生效
  - 确认BrowserRouter包裹与路由表配置
  - 检查Layout与Outlet的嵌套关系

**新增** Shopify应用故障排查：
- 路由问题：检查React Router 7.12.0的路由配置和组件导入
- 数据库连接：确认Prisma连接字符串和数据库可用性
- 类型错误：检查TypeScript编译错误和类型定义
- 构建问题：验证Vite配置和依赖版本兼容性

**章节来源**
- [frontend/src/context/AuthContext.tsx:44-72](file://frontend/src/context/AuthContext.tsx#L44-L72)
- [frontend/src/context/WebSocketContext.tsx:39-108](file://frontend/src/context/WebSocketContext.tsx#L39-L108)
- [frontend/src/context/NotificationContext.tsx:89-117](file://frontend/src/context/NotificationContext.tsx#L89-L117)
- [frontend/src/App.tsx:35-82](file://frontend/src/App.tsx#L35-L82)

## 结论
避风港React应用采用清晰的分层架构：入口负责挂载，根组件负责路由与上下文整合，页面组件承载业务逻辑。通过认证、WebSocket与通知三大上下文，应用实现了安全、实时与可观测的用户体验。结合Zustand与Vite，整体具备良好的可维护性与性能表现。

**新增** Shopify应用前端架构展示了现代化前端技术栈的最佳实践：
- React Router 7.12.0提供了最新的路由特性和性能优化
- TypeScript确保了代码质量和开发体验
- Prisma集成实现了类型安全的数据库操作
- 现代化的构建工具链提升了开发效率

后续可在路由层引入动态导入以进一步优化首屏加载，并完善错误边界与性能监控集成。同时，Shopify应用的现代化技术栈为平台扩展提供了坚实的技术基础。

## 附录
- API与类型
  - api/config.ts：统一的API客户端，封装鉴权头与错误处理
  - types/index.ts：核心业务类型定义，覆盖对话、事件链、风险预警、产品、定时任务等
- UI组件
  - Layout/Sidebar/NotificationCenter/ToastNotification：提供一致的导航与通知体验
- **新增** Shopify应用组件
  - root.jsx：应用根组件
  - db.server.js：数据库服务器配置
  - 路由组件：基于React Router 7.12.0的现代化路由系统

**章节来源**
- [frontend/src/api/config.ts:1-635](file://frontend/src/api/config.ts#L1-L635)
- [frontend/src/types/index.ts:1-477](file://frontend/src/types/index.ts#L1-L477)
- [frontend/src/components/Layout.tsx:1-60](file://frontend/src/components/Layout.tsx#L1-L60)
- [frontend/src/components/Sidebar.tsx:1-163](file://frontend/src/components/Sidebar.tsx#L1-L163)
- [frontend/src/components/NotificationCenter.tsx:1-119](file://frontend/src/components/NotificationCenter.tsx#L1-L119)
- [frontend/src/components/ToastNotification.tsx:1-53](file://frontend/src/components/ToastNotification.tsx#L1-L53)
- [shopify-app/astra-compliance/app/root.jsx](file://shopify-app/astra-compliance/app/root.jsx)
- [shopify-app/astra-compliance/app/db.server.js](file://shopify-app/astra-compliance/app/db.server.js)