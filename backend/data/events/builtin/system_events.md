---
category: system
events:
  - event_code: "system:sync_completed"
    event_name: "同步完成"
    business_stage: "全阶段"
    severity: low
    worker: system_worker
    skills: ["sync_task"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "Shopify产品/订单同步成功"
    agent_action: "确认同步完成状态，记录同步时间戳和同步数量。检查同步日志是否有警告，无异常则正常更新Dashboard。"
  - event_code: "system:sync_failed"
    event_name: "同步失败"
    business_stage: "全阶段"
    severity: medium
    worker: system_worker
    skills: ["sync_task"]
    tools: []
    notify_strategy: ["dashboard", "websocket"]
    trigger_condition: "外部系统同步失败（Shopify/17TRACK）"
    agent_action: "立即记录失败原因和异常信息。标记同步状态为failed，触发重试逻辑。推送失败通知到Dashboard/WebSocket，通知运维人员。"
  - event_code: "system:api_health_ok"
    event_name: "API健康"
    business_stage: "全阶段"
    severity: low
    worker: system_worker
    skills: ["health_check"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "API健康检查通过"
    agent_action: "记录健康检查结果，更新Dashboard状态为绿色。无需执行额外操作。"
  - event_code: "system:api_health_degraded"
    event_name: "API降级"
    business_stage: "全阶段"
    severity: high
    worker: system_worker
    skills: ["health_check"]
    tools: []
    notify_strategy: ["dashboard", "websocket", "email"]
    trigger_condition: "API响应时间超阈值或部分端点异常"
    agent_action: "自动执行诊断流程：检查各端点响应时间、数据库连接、外部API状态。生成降级报告并推送通知。触发system_worker自动恢复尝试。"
  - event_code: "system:scheduler_tick"
    event_name: "调度器心跳"
    business_stage: "全阶段"
    severity: low
    worker: system_worker
    skills: ["health_check"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "APScheduler定时任务执行"
    agent_action: "记录调度器心跳时间戳。检查是否有积压任务，确保任务队列消费正常。"
  - event_code: "system:knowledge_updated"
    event_name: "知识库更新"
    business_stage: "全阶段"
    severity: low
    worker: system_worker
    skills: ["sync_task"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "ChromaDB知识库增量更新完成"
    agent_action: "确认更新范围和向量维度。更新RAG检索状态。如涉及法规知识库更新，触发产品合规重新评估。"
  - event_code: "system:backup_completed"
    event_name: "备份完成"
    business_stage: "全阶段"
    severity: low
    worker: system_worker
    skills: []
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "数据备份成功"
    agent_action: "记录备份完成状态、备份大小和路径。清理过期备份。更新Dashboard备份状态。"
  - event_code: "system:backup_failed"
    event_name: "备份失败"
    business_stage: "全阶段"
    severity: high
    worker: system_worker
    skills: []
    tools: []
    notify_strategy: ["dashboard", "email"]
    trigger_condition: "数据备份失败"
    agent_action: "记录备份失败原因。发送紧急通知到Dashboard和Email。建议手动触发备份或检查存储空间。"
  - event_code: "system:token_usage_alert"
    event_name: "Token用量告警"
    business_stage: "全阶段"
    severity: medium
    worker: system_worker
    skills: ["health_check"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "Claude API Token使用量超预算"
    agent_action: "计算当前周期Token消耗和预算比例。生成用量报告推送Dashboard。如超预算80%以上，建议调整模型配置或限流策略。"
  - event_code: "system:webhook_received"
    event_name: "Webhook接收"
    business_stage: "全阶段"
    severity: low
    worker: system_worker
    skills: []
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "接收到外部Webhook事件"
    agent_action: "解析Webhook事件类型和负载。根据事件类型路由到对应的Worker处理（订单创建→order_worker，产品更新→product_worker等）。"
  - event_code: "system:rag_index_built"
    event_name: "RAG索引构建"
    business_stage: "全阶段"
    severity: low
    worker: system_worker
    skills: ["sync_task"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "向量索引重建或增量更新完成"
    agent_action: "确认索引构建完成状态。更新RAG服务状态。验证索引查询响应正常。"
---
# 系统运维事件定义

> 由 QAAgent 维护，监控系统健康状态和外部集成
> 对应指南 §3 阶段1：建站与基础环境搭建 + 全阶段系统监控

## 外部集成状态（参考指南开源推荐）

| 集成 | 开源方案 | 状态监控 |
|------|----------|----------|
| Shopify | OAuth + REST API | 每20分钟同步 |
| 物流追踪 | 17TRACK API | Webhook回调 |
| 邮件通知 | Listmonk (21.2k⭐) | SMTP健康检查 |
| 客服工单 | Chatwoot (29.9k⭐) | Webhook回调 |
| ERP | ERPNext (35.2k⭐) | REST API心跳 |
