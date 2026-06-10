---
category: lifecycle
events:
  - event_code: "product:created"
    event_name: "产品创建"
    business_stage: "阶段2"
    severity: low
    worker: product_worker
    skills: ["product_crud", "lifecycle_manager"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "新产品纳入管理（Shopify导入或手动添加）"
    agent_action: "初始化产品合规记录，分配产品ID。触发HS编码查询流程。标记产品生命周期状态为concept。通知QA Agent配置初始合规参数。"
  - event_code: "product:design_started"
    event_name: "设计启动"
    business_stage: "阶段2"
    severity: low
    worker: product_worker
    skills: ["product_crud", "lifecycle_manager"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "产品进入设计阶段，开始HS编码查询"
    agent_action: "更新产品状态为design。启动合规检查：HS编码预查、目标市场法规概要。将设计要求和合规约束关联到产品记录。"
  - event_code: "product:status_changed"
    event_name: "状态变更"
    business_stage: "全阶段"
    severity: medium
    worker: product_worker
    skills: ["product_crud", "lifecycle_manager"]
    tools: []
    notify_strategy: ["dashboard", "websocket"]
    trigger_condition: "产品生命周期状态变更（8阶段状态机转换）"
    agent_action: "验证状态转换的合法性（符合8阶段状态机规则）。更新产品合规状态。如转换为active，触发上架前最终合规检查。"
  - event_code: "product:listed"
    event_name: "产品上架"
    business_stage: "阶段4"
    severity: medium
    worker: listing_worker
    skills: ["content_check", "shopify_publish"]
    tools: []
    notify_strategy: ["dashboard", "websocket"]
    trigger_condition: "产品状态变为active，Listing发布到Shopify"
    agent_action: "确认Listing已发布到Shopify。记录上架时间和SKU。执行上架后合规验证：Listing内容合规检查、价格标签合规、认证信息展示。"
  - event_code: "product:content_updated"
    event_name: "内容更新"
    business_stage: "阶段4"
    severity: low
    worker: listing_worker
    skills: ["content_check"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "产品Listing内容变更（标题/描述/图片）"
    agent_action: "检查更新内容是否涉及合规敏感字段（材质/产地/用途等）。如涉及，标记产品需要重新合规检查。同步更新到Shopify。"
  - event_code: "product:ended"
    event_name: "产品下架"
    business_stage: "全阶段"
    severity: low
    worker: product_worker
    skills: ["product_crud"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "产品状态变为end，从Shopify下架"
    agent_action: "确认产品下架完成。更新生命周期状态为end。归档合规记录。标记产品为历史数据不移除，保留审计线索。"
  - event_code: "product:archived"
    event_name: "产品归档"
    business_stage: "全阶段"
    severity: low
    worker: product_worker
    skills: ["product_crud"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "产品长期未活跃自动归档"
    agent_action: "确认归档完成。压缩历史合规数据和检查记录。更新存储状态。如180天内无恢复操作，自动清理临时缓存。"
  - event_code: "product:duplicate"
    event_name: "产品复制"
    business_stage: "阶段2"
    severity: low
    worker: product_worker
    skills: ["product_crud"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "基于现有产品创建新产品"
    agent_action: "复制源产品的合规配置和HS编码/VAT数据。为新分配产品ID。触发新产品的基础合规检查。"
---
# 产品生命周期事件定义

> 由 QAAgent 维护，用户可通过前端管理界面或对话添加新事件
> 对应指南 §3 阶段2-4：选品设计 → 供应商审核 → 商品上架

## 状态机转换规则

```
concept → design → sourcing → ready → active → fulfilling → aftersale → end
                  ↗                                         ↗
         (可直接跳过)                              (可并行多订单)
```

## 事件 Schema 定义

```yaml
event_schema:
  required:
    - event_code
    - event_name
    - business_stage
    - trigger_condition
  optional:
    - related_worker
    - severity
    - notify_strategy
    - description
    - data_schema
```
