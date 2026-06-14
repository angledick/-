---
category: shopify
events:
  - event_code: "shopify:sync_products"
    event_name: "Shopify产品同步"
    business_stage: "阶段2"
    severity: low
    worker: product_worker
    skills: ["product_crud", "lifecycle_manager"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "前端请求同步Shopify店铺产品列表，或手动触发产品同步"
    agent_action: "通过shopify-ai-toolkit技能（shopify-admin）拉取店铺产品列表。将每个产品导入本地产品管理体系，初始化合规记录。对新产品触发product:created事件。返回同步结果摘要。"
  - event_code: "shopify:sync_orders"
    event_name: "Shopify订单同步"
    business_stage: "阶段6"
    severity: low
    worker: order_worker
    skills: ["order_track"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "定时拉取或手动触发Shopify店铺订单同步"
    agent_action: "通过shopify-ai-toolkit技能（shopify-admin）拉取店铺订单列表。将每个订单导入本地订单管理体系。对新订单触发order:created事件。返回同步结果摘要。"
  - event_code: "shopify:sync_inventory"
    event_name: "Shopify库存同步"
    business_stage: "阶段5"
    severity: low
    worker: product_worker
    skills: ["product_crud"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "定时拉取或手动触发Shopify店铺库存同步"
    agent_action: "通过shopify-ai-toolkit技能（shopify-admin）拉取店铺库存水平数据。更新本地产品库存记录。识别低库存产品并触发预警。"
  - event_code: "shopify:oauth_start"
    event_name: "Shopify OAuth授权发起"
    business_stage: "阶段1"
    severity: low
    worker: product_worker
    skills: []
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "前端发起Shopify店铺OAuth授权连接"
    agent_action: "通过shopify-ai-toolkit技能（shopify-use-shopify-cli）发起OAuth授权流程。生成授权URL并返回给前端。等待商家在Shopify端确认。"
  - event_code: "shopify:oauth_callback"
    event_name: "Shopify OAuth授权回调"
    business_stage: "阶段1"
    severity: high
    worker: product_worker
    skills: []
    tools: []
    notify_strategy: ["dashboard", "websocket"]
    trigger_condition: "Shopify OAuth授权流程回调，携带授权码"
    agent_action: "通过shopify-ai-toolkit技能（shopify-use-shopify-cli）完成OAuth令牌交换。将获取的access_token通过save_token_from_sdk持久化。通知前端授权完成。"
  - event_code: "order:updated"
    event_name: "订单更新"
    business_stage: "阶段6"
    severity: low
    worker: order_worker
    skills: ["order_track"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "Shopify Webhook推送订单更新"
    agent_action: "从Webhook负载中提取更新后的订单详情。对比变更字段（金额、地址、商品）。如涉及合规敏感变更（目标国家、商品清单），重新触发合规检查。更新本地订单记录。"
  - event_code: "order:cancelled"
    event_name: "订单取消"
    business_stage: "阶段6"
    severity: medium
    worker: order_worker
    skills: ["order_track"]
    tools: []
    notify_strategy: ["dashboard", "websocket"]
    trigger_condition: "Shopify Webhook推送订单取消"
    agent_action: "确认订单取消状态和取消原因。检查是否需要退款处理。更新库存（恢复占用数量）。通知财务和仓库团队。记录取消原因到合规分析。"
  - event_code: "order:fulfilled"
    event_name: "订单履约完成"
    business_stage: "阶段6"
    severity: low
    worker: order_worker
    skills: ["order_track", "logistics_query"]
    tools: []
    notify_strategy: ["dashboard", "websocket"]
    trigger_condition: "Shopify Webhook推送订单履约完成"
    agent_action: "确认订单已履约，提取物流追踪号和承运商信息。更新订单状态为shipped。自动发起物流追踪订阅。触发出口报关准备流程。通知买家发货信息。"
---
# Shopify 集成事件定义

> 对接 Shopify Webhook 和前端 API 请求的事件定义
> 参照飞书监听模式：外部事件 → UnifiedDispatcher → EventBus → Manager → Worker → Claude Agent SDK

## Webhook Topic 映射

| Shopify Webhook Topic | 内部事件编码 | 定义位置 |
|---|---|---|
| products/create | product:created | lifecycle_events.md |
| products/update | product:content_updated | lifecycle_events.md |
| products/delete | product:ended | lifecycle_events.md |
| orders/create | order:created | order_events.md |
| orders/updated | order:updated | 本文件 |
| orders/cancelled | order:cancelled | 本文件 |
| orders/fulfilled | order:fulfilled | 本文件 |
| inventory_levels/update | product:status_changed | lifecycle_events.md |

## 前端 API 触发的事件

| API 端点 | 触发事件 | Worker |
|---|---|---|
| GET /shopify/{shop}/products | shopify:sync_products | product_worker |
| POST /shopify/{shop}/check/{id} | compliance:check_started | compliance_worker |
