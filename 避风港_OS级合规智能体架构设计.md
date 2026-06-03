# 避风港 · OS级跨境合规智能体架构设计

> 版本：v4.0 ｜ 参考设计：[QwenPaw](https://github.com/agentscope-ai/QwenPaw)、[OpenHuman](https://github.com/tinyhumansai/openhuman)
>
> 目标：将避风港从「合规检查工具」升级为**OS级合规智能体**——一个能感知、记忆、推理、行动、自我进化的合规操作系统。

---

## 一、架构总览

### 1.1 设计哲学

| 原则 | 说明 | 参考来源 |
|------|------|----------|
| **事件驱动，主动感知** | 不等用户提问，系统主动感知合规热点并推送 | OpenHuman 自动拉取 |
| **记忆优先，上下文完整** | 所有数据规范化为记忆树，Agent 每天已拥有全天上下文 | OpenHuman 记忆树 |
| **多Agent协作，职责隔离** | Manager拆解任务，Worker隔离执行，群聊式调度 | QwenPaw 多智能体 |
| **Token经济，成本可控** | 所有工具输出经压缩层处理，降低80% token消耗 | OpenHuman TokenJuice |
| **本地优先，数据主权** | 记忆/配置/密钥存储在本地，加密不动 | QwenPaw 本地部署 |
| **OS级组件化** | 像操作系统一样提供进程管理、文件系统、权限控制、网络栈 | 两者皆有 |

### 1.2 系统全景图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        避风港 OS级合规智能体                               │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────┐   ┌─────────┐   ┌──────────┐   ┌──────────┐               │
│  │ 控制台   │   │ CLI     │   │ 频道适配器 │   │ 桌面应用  │               │
│  │ (Web)   │   │ (终端)  │   │(飞书/钉钉)│   │ (Tauri)  │               │
│  └────┬────┘   └────┬────┘   └─────┬────┘   └─────┬────┘               │
│       └──────────────┴──────────────┴──────────────┘                     │
│                              │                                           │
│                      ┌───────▼───────┐                                   │
│                      │  消息总线层     │  ← 统一入口/路由                   │
│                      └───────┬───────┘                                   │
│                              │                                           │
│  ┌────────────────────────────▼───────────────────────────────────┐      │
│  │                    多Agent调度层（聊天室）                        │      │
│  │                                                                │      │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │      │
│  │  │ Manager  │  │ QA Agent │  │Worker(1) │  │Worker(N) │      │      │
│  │  │ 协调者    │  │ 系统问答  │  │ 合规检查  │  │ 自定义    │      │      │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │      │
│  └────────────────────────────────┬───────────────────────────────┘      │
│                                   │                                      │
│  ┌────────────────────────────────▼───────────────────────────────┐      │
│  │                    核心服务层                                    │      │
│  │                                                                │      │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │      │
│  │  │ TokenJuice│  │ 记忆树   │  │ 规则引擎  │  │ 事件总线  │      │      │
│  │  │ 压缩层    │  │ +Wiki   │  │ RuleEng  │  │ EventBus │      │      │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │      │
│  │                                                                │      │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │      │
│  │  │ 主动引擎  │  │ 心跳系统  │  │ 安全沙箱  │  │ 魔法命令  │      │      │
│  │  │ Proactive │  │ Heartbeat│  │ Sandbox  │  │ MagicCmd │      │      │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │      │
│  └────────────────────────────────────────────────────────────────┘      │
│                                   │                                      │
│  ┌────────────────────────────────▼───────────────────────────────┐      │
│  │                    数据与集成层                                  │      │
│  │                                                                │      │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │      │
│  │  │ SQLite   │  │ Obsidian │  │ ChromaDB │  │ OAuth    │      │      │
│  │  │ (记忆)   │  │ Wiki(.md)│  │ (向量)   │  │ 集成层   │      │      │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │      │
│  └────────────────────────────────────────────────────────────────┘      │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 二、事件驱动合规流（Event-Driven Compliance Pipeline）

### 2.1 六阶段合规流

```
感知 → 检查 → 推荐 → 告知 → 交互 → 处理
(Sense) (Check) (Recommend) (Notify) (Interact) (Process)
```

| 阶段 | 触发方式 | 执行者 | 输出 |
|------|----------|--------|------|
| **感知** | 用户动作 / 外部API事件 / 定时调度 / 规则引擎 | EventBus + RuleEngine | 标准化EventRecord |
| **检查** | 事件路由到对应Skill/规则集 | Worker Agent + Skill | 检查结果 + 风险等级 |
| **推荐** | 检查结果匹配规则库，AI生成操作建议 | Skill推荐器 + 规则引擎 | 操作建议列表（含置信度） |
| **告知** | 推荐结果匹配通知规则 | 通知引擎 + 频道适配器 | 多端消息推送 |
| **交互** | 用户确认/修改/补充/委派 | 对话引擎 + Cowork入口 | 执行指令 |
| **处理** | 确认指令编排执行 | Workflow + Skill流 | 操作结果 + 回写 |

> **六阶段流水线演进说明**：相比原五阶段设计，新增「推荐」阶段作为独立的Action生成步骤。推荐阶段由Skill推荐器根据检查结果和规则库，生成含置信度和预期结果的结构化操作建议。此改进与《shopify跨境合规全事件流程与系统对接指南》§6.15.2 六步执行流水线完全对齐。

### 2.2 事件分类体系

> **8类事件体系**：与《shopify跨境合规全事件流程与系统对接指南》§6.10.1 完全对齐。
> 以下产品关键节点属于 `lifecycle`（生命周期事件）的细粒度拆分。

| 事件类别 | 类别编码 | 子类示例 | 作用域 | 说明 |
|----------|----------|----------|--------|------|
| **生命周期事件** | `lifecycle` | `product:created` / `product:status_changed` / `product:ended` | 产品级 | 产品从创建到下架的完整生命周期状态变更 |
| **合规检查事件** | `compliance` | `compliance:check_started` / `compliance:check_passed` / `compliance:check_failed` | 产品级 | 合规检查结果触发的事件 |
| **认证管理事件** | `certification` | `certification:uploaded` / `certification:expiring` / `certification:expired` | 产品级 | 认证生命周期相关事件 |
| **订单事件** | `order` | `order:created` / `order:shipped` / `order:returned` | 产品级 | 订单流转相关事件 |
| **市场法规事件** | `regulation` | `regulation:updated` / `regulation:new` / `regulation:repealed` | 全局 | 目标市场法规变更事件 |
| **风险预警事件** | `risk_alert` | `risk_alert:new` / `risk_alert:resolved` / `risk_alert:escalated` | 全局/产品级 | 风险预警产生和处置事件 |
| **系统事件** | `system` | `system:config_changed` / `system:error` / `system:health_check` | 全局 | 系统自身状态变更事件 |
| **用户操作事件** | `user_action` | `user_action:login` / `user_action:config_modified` / `user_action:approved` | 全局 | 用户操作审计事件 |

#### 产品关键节点事件定义（lifecycle类别细粒度拆分）

> 以下7个关键节点属于 `lifecycle` 事件类别，用于产品级别的细化管理。

```yaml
product_lifecycle_events:
  - node: "创建纳管"
    trigger: "user:product_added"
    checks: ["HS编码校验", "目标市场法规扫描", "EPR/GPSR适用性检查"]
    
  - node: "样品认证"
    trigger: "certification:uploaded"
    checks: ["CE/WEEE/REACH认证完整性", "认证有效期校验", "认证机构合规性"]
    
  - node: "上架发布"
    trigger: "product:published"
    checks: ["广告法合规检查", "产品标签完整性", "Cookie/隐私合规", "价格标注规范"]
    
  - node: "订单履约"
    trigger: "order:created"
    checks: ["三单一致性校验", "出口报关合规", "IOSS/VAT适用性"]
    
  - node: "物流配送"
    trigger: "order:shipped"
    checks: ["承运商合规性", "追踪信息完整性", "清关文件齐备性"]
    
  - node: "售后退货"
    trigger: "order:returned"
    checks: ["消费者权益合规(Right to Repair)", "退货政策合规", "数据删除义务"]
    
  - node: "财务结算"
    trigger: "settlement:completed"
    checks: ["税务申报合规", "结汇通道合规", "发票合规性"]
```

### 2.3 业务阶段体系对齐映射

> 系统设计包含三套并行的阶段体系，分别面向业务编排、产品生命周期管理和架构对齐。
> 以下建立显式映射关系。三套体系在系统内部通过 `business_stage` 和 `lifecycle_stage` 两个字段分别标识。

| 业务指南 §1（10阶段） | 产品状态机（8阶段） | 架构设计 §2.2（7节点） | 说明 |
|----------------------|---------------------|------------------------|------|
| 1. 建站与基础环境搭建 | `concept` | — | 建站阶段，产品概念形成 |
| 2. 选品与样品设计 | `design` | 创建纳管 | 选品设计，HS编码查询 |
| 3. 供应商审核与采购 | `sourcing` | — | 供应链合规审查 |
| 4. 商品上架与内容合规 | `ready` | 样品认证 → 上架发布 | Listing准备，内容合规检查 |
| 5. 支付与收款配置 | `ready` | — | 收款渠道合规 |
| 6. 订单处理与境内物流 | `active` → `fulfilling` | 订单履约 | 在售订单处理 |
| 7. 出口报关（跨境干线） | `fulfilling` | — | 跨境合规申报 |
| 8. 进口清关与境外派送 | `fulfilling` | — | 目的国清关合规 |
| 9. 交付、售后与退货 | `aftersale` | 售后退货 | 售后合规处理 |
| 10. 财务结算与税务申报 | `end` | 财务结算 | 税务合规申报 |

> **使用说明**：
> - 业务指南10阶段 用于事件路由、Worker分配、Pipeline阶段状态聚合
> - 产品状态机8阶段 用于产品卡片分组展示、生命周期状态转换、合规检查触发时机
> - 架构设计7节点 用于与上游架构文档对齐

---

## 三、QAAgent——系统自我管理智能体

### 3.1 定位

QAAgent 是系统的**自我管理智能体**，负责：
- 回答用户关于系统配置、事件定义、流程串联的问答
- 接受自然语言指令修改系统配置（如「把WEEE预警阈值从30天改为60天」）
- 维护事件定义的完整性（新增/删除/修改事件类型时自动检查一致性）
- 编排和调试Workflow流程

### 3.2 能力矩阵

| 能力 | 输入 | 动作 | 输出 |
|------|------|------|------|
| **配置问答** | 「当前合规检查有哪些规则？」 | 读取规则引擎配置 | 结构化规则列表 |
| **配置修改** | 「把德国市场的EPR检查设为每日执行」 | 修改Scheduler配置 + 验证 | 配置变更确认 |
| **事件定义** | 「新增一个product:price_changed事件」 | 更新事件注册表 + 生成Skill骨架 | 新事件注册确认 |
| **流程串联** | 「认证过期后自动触发续期提醒并生成工单」 | 编排Workflow + 绑定触发器 | 流程上线确认 |
| **故障排查** | 「为什么德国产品的合规检查没有触发？」 | 查询事件链 + 规则引擎日志 | 根因分析报告 |

### 3.3 实现方案

```python
class QAAgent:
    """系统自我管理智能体"""
    
    tools = [
        "read_config",       # 读取系统配置（规则引擎/Scheduler/通知规则）
        "write_config",      # 修改系统配置（需安全沙箱验证）
        "query_events",      # 查询事件注册表和事件链
        "register_event",    # 注册新事件类型
        "compose_workflow",  # 编排Workflow流程
        "debug_pipeline",    # 调试事件管道
        "health_check",      # 系统健康自检
    ]
    
    permissions = {
        "read_config": "safe",       # 无需审批
        "write_config": "guarded",   # 需要用户确认
        "register_event": "guarded",
        "compose_workflow": "guarded",
    }
```

---

## 四、多Agent调度（聊天室模式）

### 4.1 架构设计

```
┌──────────────────────────────────────────────────┐
│              Agent 聊天室（全局记忆可见）            │
│                                                  │
│  ┌──────────┐                                    │
│  │ Manager  │  ← 协调者：任务拆解 + 分配 + 监督    │
│  │ Agent    │                                    │
│  └────┬─────┘                                    │
│       │ 读取全局记忆：活跃Agent列表 + 各Agent事件流 │
│       │                                          │
│  ┌────▼──────────────────────────────────────────┤
│  │  Worker 池                                    │
│  │                                               │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │
│  │  │合规检查 │ │认证管理 │ │数据采集 │ │报告生成 │ │
│  │  │Worker  │ │Worker  │ │Worker  │ │Worker  │ │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ │
│  └───────────────────────────────────────────────┘
└──────────────────────────────────────────────────┘
```

### 4.2 Agent间通信协议

```yaml
# Agent间消息格式
agent_message:
  from: "manager_agent"
  to: "compliance_worker"
  type: "task_assign"          # task_assign | result_report | status_query | chat
  task_id: "task_20260615_001"
  payload:
    action: "run_compliance_check"
    target_products: ["p_led_de_001", "p_led_eu_002"]
    scope: "full"
  context:
    trigger_event: "regulation:updated"
    urgency: "high"
```

### 4.3 全局记忆中的Agent状态

```json
// data/global/memory/agent_registry.json
{
  "active_agents": [
    {
      "agent_id": "manager_agent",
      "role": "coordinator",
      "status": "active",
      "current_tasks": ["task_20260615_001"],
      "last_heartbeat": "2026-06-15T10:30:00Z"
    },
    {
      "agent_id": "compliance_worker",
      "role": "worker",
      "skills": ["shopify-admin", "shopify-custom-data", "compliance-checker"],
      "status": "busy",
      "current_task": "task_20260615_001",
      "last_output": "检查LED灯带德国市场合规性... 3/5项通过"
    }
  ]
}
```

---

## 五、第三方集成 + 自动拉取

### 5.1 一键OAuth接入

```yaml
integrations:
  shopify:
    auth_type: "oauth2"
    scopes: ["read_products", "write_products", "read_orders"]
    auto_pull_interval: 20m
    typed_tools:
      - name: "shopify_product_sync"
        description: "同步Shopify产品数据到记忆树"
        schedule: "*/20 * * * *"
      - name: "shopify_order_sync"
        description: "同步订单数据到记忆树"
        schedule: "*/20 * * * *"
  
  feishu:
    auth_type: "oauth2"
    scopes: ["im:message", "approval:approval"]
    auto_pull_interval: 20m
    typed_tools:
      - name: "feishu_notification"
        description: "推送合规预警到飞书群"
      - name: "feishu_approval"
        description: "发起合规审批流"
  
  # 未来扩展
  dingtalk:
    auth_type: "oauth2"
  slack:
    auth_type: "oauth2"
  discord:
    auth_type: "bot_token"
```

### 5.2 自动拉取引擎

```python
class AutoPullEngine:
    """每20分钟遍历所有活跃连接，将新数据拉入记忆树"""
    
    interval = 20 * 60  # 20分钟
    
    async def pull_cycle(self):
        connections = await self.get_active_connections()
        for conn in connections:
            new_data = await conn.fetch_incremental(last_sync=self.last_sync[conn.id])
            if new_data:
                compressed = TokenJuice.compress(new_data)  # 压缩后存入
                await MemoryTree.ingest(compressed, source=conn.id)
                self.last_sync[conn.id] = now()
    
    # 效果：智能体每天早上已经拥有当天的全部上下文
    # 无需提示词，无需手动轮询
```

---

## 六、记忆树 + Obsidian Wiki

### 6.1 记忆树架构

```
┌────────────────────────────────────────────┐
│               记忆树（Memory Tree）          │
│                                            │
│  原始数据 → 规范化(≤3k token) → 评分 → 摘要树│
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │ Level 0: 原始片段（Fragments）        │  │
│  │  - 每条数据规范化为 ≤3k token 的 MD   │  │
│  │  - 来源：API事件/用户交互/自动拉取     │  │
│  └──────────────┬───────────────────────┘  │
│                 │ 评分+聚类                  │
│  ┌──────────────▼───────────────────────┐  │
│  │ Level 1: 话题摘要（Topic Summaries）   │  │
│  │  - 按产品/市场/法规/认证 聚类          │  │
│  │  - 每个摘要 ≤2k token                │  │
│  └──────────────┬───────────────────────┘  │
│                 │ 再聚合                     │
│  ┌──────────────▼───────────────────────┐  │
│  │ Level 2: 领域概览（Domain Overview）   │  │
│  │  - 德国市场合规全景 / LED产品线全景    │  │
│  │  - 每个概览 ≤1k token                │  │
│  └──────────────┬───────────────────────┘  │
│                 │ 再聚合                     │
│  ┌──────────────▼───────────────────────┐  │
│  │ Level 3: 全局索引（Global Index）      │  │
│  │  - 所有领域概览的索引                   │  │
│  │  - ≤500 token                        │  │
│  └──────────────────────────────────────┘  │
│                                            │
│  存储：SQLite（本地）+ .md文件（Obsidian）    │
└────────────────────────────────────────────┘
```

### 6.2 SQLite存储结构

```sql
-- 片段表：存储规范化后的≤3k token片段
CREATE TABLE fragments (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,          -- 来源：shopify/feishu/manual/auto_pull
    source_id TEXT,                -- 原始数据ID
    product_id TEXT,               -- 关联产品
    market TEXT,                   -- 关联市场
    category TEXT,                 -- 分类：event/metric/knowledge/config
    content TEXT NOT NULL,         -- ≤3k token 的 Markdown内容
    score REAL DEFAULT 0,          -- 重要性评分（0-1）
    level INTEGER DEFAULT 0,       -- 记忆树层级（0=原始，1=话题，2=领域，3=全局）
    parent_id TEXT,                -- 父摘要ID（用于树结构）
    created_at DATETIME,
    updated_at DATETIME,
    expires_at DATETIME            -- 过期时间（用于记忆衰减）
);

-- 摘要表：存储聚合后的摘要
CREATE TABLE summaries (
    id TEXT PRIMARY KEY,
    level INTEGER NOT NULL,        -- 1/2/3
    topic TEXT NOT NULL,           -- 话题名
    content TEXT NOT NULL,         -- ≤2k/1k/500 token
    child_ids TEXT,                -- 子片段ID列表（JSON）
    updated_at DATETIME
);
```

### 6.3 Obsidian Wiki输出

```
data/
├── memory_wiki/                  # Obsidian兼容仓库
│   ├── 00-全局索引.md
│   ├── 德国市场/
│   │   ├── 合规概览.md
│   │   ├── LED灯带/
│   │   │   ├── 合规记录.md
│   │   │   ├── 认证状态.md
│   │   │   └── 事件时间线.md
│   │   └── 玩具/
│   ├── 欧盟市场/
│   │   ├── 法规变更日志.md
│   │   └── EPR注册状态.md
│   └── 系统配置/
│       ├── 规则引擎配置.md
│       ├── 通知规则.md
│       └── Workflow定义.md
```

> 灵感来源：Karpathy 的 obsidian-wiki 工作流。同样的片段以 .md 文件落地，用户可在 Obsidian 中打开、浏览、编辑。

---

## 七、智能Token压缩（TokenJuice）

### 7.1 压缩管道

```
原始数据 → 格式转换 → 冗余去除 → 结构压缩 → 多字节保护 → 压缩输出
          (HTML→MD)   (重复删除)  (长URL缩短)  (中文/emoji完整保留)
```

### 7.2 压缩规则层

```yaml
token_juice_rules:
  # HTML → Markdown 转换
  html_to_markdown:
    enabled: true
    strip_tags: ["script", "style", "nav", "footer", "header"]
    preserve_tags: ["table", "pre", "code", "img"]
  
  # 长URL缩短
  url_shortening:
    enabled: true
    max_length: 80
    pattern: "保留域名+路径前2级，省略参数"
  
  # 工具输出去重
  deduplication:
    enabled: true
    strategy: "hash_based"      # 相同内容块只保留一份
    min_block_size: 50          # 最小去重块大小（字符）
  
  # 冗余模板去除
  template_strip:
    enabled: true
    patterns:
      - "Remove repetitive Shopify API response wrappers"
      - "Compress JSON by removing null/default fields"
  
  # 多字节字符保护（中文、emoji等）
  multibyte_protection:
    enabled: true
    strategy: "grapheme_aware"  # 按字形（grapheme）完整保留
    never_truncate: ["CJK", "Emoji", "Arabic", "Thai"]
  
  # 摘要压缩（超长内容）
  summarization:
    enabled: true
    threshold: 4000             # 超过4000 token才触发
    target_ratio: 0.3           # 压缩到原长的30%
    method: "extractive"        # 抽取式摘要（不改原意）
```

### 7.3 压缩效果预估

| 数据类型 | 原始大小 | 压缩后 | 压缩率 |
|----------|---------|--------|--------|
| Shopify API 响应 | 2000 token | 400 token | 80% |
| 法规文本抓取 | 5000 token | 1500 token | 70% |
| 邮件正文 | 800 token | 300 token | 62% |
| 搜索结果 | 3000 token | 800 token | 73% |
| 工具调用日志 | 1500 token | 300 token | 80% |

---

## 八、必要组件清单

### 8.1 组件总览

| 组件 | 类型 | 说明 | 参考 |
|------|------|------|------|
| 客户端 | 基础 | Web控制台 + CLI + 桌面应用(Tauri) | QwenPaw 桌面应用 |
| 模型配置 | 基础 | 多模型提供商、按任务路由（推理型/快速型/视觉型） | OpenHuman 模型路由 |
| 主动引擎 | 核心 | 定时任务、心跳、主动简报、洞察挖掘 | QwenPaw 心跳 + 主动性 |
| 工作区 | 基础 | Sandbox文件权限、子目录划分（config/production/data） | QwenPaw 工作区 |
| 编码能力 | 扩展 | 兼容Claude Code等既有Agent，LSP跳转、AST搜索 | QwenPaw Coding模式 |
| 多Agent | 核心 | Manager协调 + Worker隔离 + 群聊式调度 | QwenPaw 多智能体 |
| 控制台 | 基础 | Web界面：对话、配置、定时任务、Dashboard | QwenPaw 控制台 |
| 频道配置 | 扩展 | 钉钉、飞书、微信、Discord、Telegram | QwenPaw 频道配置 |
| 技能系统 | 核心 | Skills扩展、自定义能力、安全扫描 | QwenPaw Skills |
| 插件系统 | 扩展 | 第三方插件安装/管理/安全审查 | QwenPaw 插件系统 |
| MCP和工具 | 核心 | 管理MCP客户端和工具，类型化工具暴露 | OpenHuman 集成层 |
| 记忆 | 核心 | 记忆树 + SQLite + Obsidian Wiki | OpenHuman 记忆树 |
| 上下文 | 核心 | TokenJuice压缩、上下文窗口管理 | OpenHuman TokenJuice |
| 魔法命令 | 体验 | /clear /retry /compact /export 等快捷指令 | QwenPaw 魔法命令 |
| 安全 | 基础 | 工具防护、文件防护、技能安全扫描、沙箱 | QwenPaw 安全特性 |
| 心跳 | 核心 | 定时自检、主动简报、状态摘要推送 | QwenPaw 心跳 |
| CLI | 基础 | 初始化、定时任务、Skills管理、清理 | QwenPaw CLI |

### 8.2 主动引擎详解

```yaml
proactive_engine:
  # 定时任务
  scheduled_tasks:
    - name: "每日合规简报"
      schedule: "0 8 * * *"        # 每天早8点
      action: "generate_daily_compliance_brief"
      channels: ["feishu", "dashboard"]
      
    - name: "认证到期预警"
      schedule: "0 9 * * 1"        # 每周一早9点
      action: "check_certification_expiry"
      threshold_days: 30
      
    - name: "法规变更扫描"
      schedule: "0 */6 * * *"      # 每6小时
      action: "scan_regulation_changes"
      
  # 心跳自检
  heartbeat:
    interval: 5m                   # 每5分钟
    checks:
      - "event_bus_health"
      - "rule_engine_status"
      - "agent_registry_status"
      - "memory_tree_integrity"
      - "integration_connections"
    on_failure: "notify_admin"
    
  # 洞察挖掘
  insight_mining:
    trigger: "daily"
    analyze:
      - "user_interaction_patterns"   # 从对话中挖掘用户需求
      - "event_cluster_analysis"      # 事件聚类发现新热点
      - "cross_product_correlation"   # 跨产品相关性分析
```

### 8.3 安全沙箱设计

```yaml
security:
  # 工具防护
  tool_guard:
    blocked_commands:
      - "rm -rf"
      - "DROP TABLE"
      - "fork bomb patterns"
    allowed_paths:
      - "data/**"
      - "config/**"
    forbidden_paths:
      - "~/.ssh/**"
      - "~/.env"
      - "/etc/**"
    
  # 技能安全扫描
  skill_scanner:
    checks:
      - "prompt_injection_detection"
      - "command_injection_detection"
      - "hardcoded_secrets_scan"
      - "data_exfiltration_risk"
      - "permission_scope_audit"
    
  # 文件防护
  file_guard:
    sensitive_patterns:
      - "*.key"
      - "*.pem"
      - ".env*"
    require_confirmation: true
```

---

## 九、工作区与目录规范

### 9.1 工作区结构

```
避风港/
├── config/                        # 配置区（用户可编辑）
│   ├── models.yaml                # 模型提供商配置
│   ├── rules/                     # 规则引擎配置
│   │   ├── compliance_rules.yaml
│   │   ├── notification_rules.yaml
│   │   └── risk_thresholds.yaml
│   ├── integrations/              # 第三方集成配置
│   │   ├── shopify.yaml
│   │   ├── feishu.yaml
│   │   └── dingtalk.yaml
│   └── agents/                    # Agent配置
│       ├── manager.yaml
│       ├── qa_agent.yaml
│       └── workers.yaml
│
├── production/                    # 生产区（系统运行时生成）
│   ├── data/                      # 数据存储
│   │   ├── products/              # 产品级隔离数据
│   │   ├── global/                # 全局共享数据
│   │   ├── memory/                # 记忆树SQLite
│   │   └── memory_wiki/           # Obsidian Wiki .md文件
│   ├── logs/                      # 运行日志
│   └── backups/                   # 自动备份
│
├── workspace/                     # 工作区（临时文件/沙箱执行）
│   ├── sandbox/                   # Agent沙箱执行目录
│   ├── temp/                      # 临时文件
│   └── exports/                   # 导出文件
│
├── plugins/                       # 插件目录
├── skills/                        # Skills目录
└── .secrets/                      # 密钥（加密存储，不进Git）
```

### 9.2 Sandbox权限模型

| 路径 | Agent读 | Agent写 | 用户读 | 用户写 | 说明 |
|------|:-------:|:-------:|:------:|:------:|------|
| `config/` | ✅ | 🔒需确认 | ✅ | ✅ | 配置修改需用户审批 |
| `production/data/` | ✅ | ✅ | ✅ | ✅ | 数据读写自由 |
| `workspace/sandbox/` | ✅ | ✅ | ✅ | 🔒受限 | Agent自由，用户可查看 |
| `.secrets/` | 🔒受限 | 🔒受限 | ✅ | ✅ | Agent默认不可访问密钥 |
| `plugins/` | ✅ | 🔒需扫描 | ✅ | ✅ | 写入前需安全扫描 |

---

## 十、消息渠道与频道配置

### 10.1 支持的渠道

| 渠道 | 接入方式 | 消息能力 | 操作能力 | 优先级 |
|------|----------|----------|----------|--------|
| **Web控制台** | 内置 | 实时对话、Dashboard | 全功能 | P0 |
| **飞书** | 飞书开放平台OAuth | 富文本卡片、操作按钮 | 审批流、对话 | P0 |
| **钉钉** | 钉钉开放平台OAuth | 互动卡片、工作通知 | 卡片操作 | P0 |
| **企业微信** | 企业微信OAuth | 文本/卡片消息 | 跳转操作 | P1 |
| **Discord** | Bot Token | Embed消息、按钮 | 斜杠命令 | P1 |
| **Telegram** | Bot API | Markdown消息、Inline按钮 | 回调操作 | P1 |
| **Slack** | Slack App OAuth | Block Kit消息 | Modal表单 | P2 |
| **桌面应用** | Tauri原生 | 系统通知、窗口对话 | 全功能 | P1 |

### 10.2 频道配置示例

```yaml
channels:
  feishu:
    app_id: "${FEISHU_APP_ID}"
    app_secret: "${FEISHU_APP_SECRET}"
    event_mode: "webhook"
    webhook_url: "https://your-domain.com/api/feishu/webhook"
    capabilities:
      - "notification"        # 推送合规预警
      - "approval"            # 发起合规审批
      - "chat"                # 对话式交互
    
  dingtalk:
    robot_token: "${DINGTALK_ROBOT_TOKEN}"
    secret: "${DINGTALK_SECRET}"
    capabilities:
      - "notification"
      - "chat"
```

---

## 十一、CLI命令规范

```bash
# 初始化
避风港 init                        # 交互式初始化（配置模型、工作区、首次集成）
避风港 init --defaults             # 默认配置一键初始化

# 启动
避风港 app                         # 启动Web控制台
避风港 app --port 9090             # 指定端口
避风港 daemon start                # 后台守护进程模式

# Agent管理
避风港 agent list                  # 列出所有Agent及状态
避风港 agent create --name "认证Worker" --skills "shopify-custom-data"
避风港 agent chat                  # 进入Agent群聊模式

# 定时任务
避风港 cron list                   # 列出所有定时任务
避风港 cron add "每日简报" --schedule "0 8 * * *" --action "daily_brief"
避风港 cron logs                   # 查看定时任务执行日志

# Skills管理
避风港 skill list                  # 列出已安装Skills
避风港 skill install <name>        # 安装Skill（含安全扫描）
避风港 skill scan <name>           # 单独安全扫描

# 记忆管理
避风港 memory status               # 记忆树状态（片段数、存储大小）
避风港 memory search "WEEE认证"    # 搜索记忆
避风港 memory compact              # 手动触发记忆压缩
避风港 memory export               # 导出Obsidian Wiki

# 集成管理
避风港 integration list            # 列出所有集成及状态
避风港 integration add shopify     # 添加Shopify集成（OAuth流程）
避风港 integration pull --force    # 手动触发一次全量拉取

# 系统维护
避风港 doctor                      # 系统健康自检
避风港 backup create               # 创建备份
避风港 backup restore <id>         # 恢复备份
避风港 clean                       # 清理临时文件/过期日志
```

---

## 十二、与现有系统的对接方案

### 12.1 现有代码模块映射

| 现有模块 | 路径 | OS级架构中对应 | 改造说明 |
|----------|------|---------------|----------|
| RuleEngine | `backend/app/core/rule_engine.py` | 规则引擎层 | 保持不变，增加QAAgent可配置接口 |
| EventChain | `backend/app/core/event_chain.py` | 事件总线层 | 扩展为全局事件总线 |
| Scheduler | `backend/app/core/scheduler.py` | 主动引擎 | 增加心跳和洞察挖掘 |
| NLU | `backend/app/core/nlu.py` | Manager Agent | 升级为多Agent NLU路由 |
| RAG | `backend/app/core/rag.py` | 记忆树查询层 | 接入记忆树 + Obsidian Wiki |
| MarketMonitor | `backend/app/core/market_monitor.py` | 自动拉取引擎 | 接入OAuth集成层 |
| RiskAlert | `backend/app/core/risk_alert.py` | Worker Agent | 合规检查Worker |
| AstraAssistant | `backend/app/services/astra_assistant.py` | Manager Agent | 升级为协调者角色 |
| AstraTools | `backend/app/services/astra_tools.py` | MCP工具层 | 类型化工具暴露 |
| SessionStore | `backend/app/storage/session_store.py` | 上下文管理 | 接入TokenJuice压缩 |
| ProjectMemory | `backend/app/storage/project_memory.py` | 产品记忆库 | 对接记忆树SQLite |
| WebSocket Manager | `backend/app/services/ws_manager.py` | 控制台实时通信 | 保持不变 |

### 12.2 分阶段实施路线

```
Phase 1 (MVP): 事件驱动 + QAAgent + TokenJuice
  ├─ 升级EventBus为全局事件总线
  ├─ 实现QAAgent基础能力（配置问答/修改）
  ├─ 接入TokenJuice压缩层
  └─ 时间：4-6周

Phase 2: 记忆树 + 多Agent
  ├─ 记忆树SQLite + 片段规范化
  ├─ Obsidian Wiki输出
  ├─ Manager/Worker Agent架构
  └─ 时间：4-6周

Phase 3: 第三方集成 + 频道
  ├─ OAuth集成层（Shopify/飞书/钉钉）
  ├─ 自动拉取引擎（20分钟周期）
  ├─ 频道适配器（飞书/钉钉/Discord）
  └─ 时间：3-4周

Phase 4: 主动引擎 + 安全 + 桌面
  ├─ 主动引擎（定时任务/心跳/洞察）
  ├─ 安全沙箱（工具防护/文件防护/技能扫描）
  ├─ Tauri桌面应用
  └─ 时间：3-4周
```

---

## 附录：术语对照

| 术语 | 英文 | 说明 |
|------|------|------|
| 记忆树 | Memory Tree | 层级化摘要树，存储于SQLite |
| TokenJuice | TokenJuice | 智能Token压缩层 |
| 魔法命令 | Magic Commands | /clear /retry 等快捷指令 |
| 心跳 | Heartbeat | 定时自检机制 |
| 主动引擎 | Proactive Engine | 定时任务+洞察挖掘+主动推送 |
| 消息总线 | Message Bus | Agent间/渠道间统一消息路由 |
| 频道适配器 | Channel Adapter | 飞书/钉钉等消息平台适配层 |
| 类型化工具 | Typed Tools | 有类型定义的MCP工具 |
