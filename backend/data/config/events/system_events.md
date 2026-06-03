# 系统运维事件定义

> 由QAAgent维护，监控系统健康状态和外部集成
> 对应指南§3 阶段1：建站与基础环境搭建 + 全阶段系统监控

## 事件注册表

| 事件编码 | 事件名称 | 业务阶段 | 触发条件 | 关联Worker | 严重级别 | 通知策略 |
|----------|----------|----------|----------|------------|----------|----------|
| system:sync_completed | 同步完成 | 全阶段 | Shopify产品/订单同步成功 | system_worker | low | dashboard |
| system:sync_failed | 同步失败 | 全阶段 | 外部系统同步失败（Shopify/17TRACK） | system_worker | medium | dashboard,websocket |
| system:api_health_ok | API健康 | 全阶段 | API健康检查通过 | system_worker | low | dashboard |
| system:api_health_degraded | API降级 | 全阶段 | API响应时间超阈值或部分端点异常 | system_worker | high | dashboard,websocket,email |
| system:scheduler_tick | 调度器心跳 | 全阶段 | APScheduler定时任务执行 | system_worker | low | dashboard |
| system:knowledge_updated | 知识库更新 | 全阶段 | ChromaDB知识库增量更新完成 | system_worker | low | dashboard |
| system:backup_completed | 备份完成 | 全阶段 | 数据备份成功 | system_worker | low | dashboard |
| system:backup_failed | 备份失败 | 全阶段 | 数据备份失败 | system_worker | high | dashboard,email |
| system:token_usage_alert | Token用量告警 | 全阶段 | Claude API Token使用量超预算 | system_worker | medium | dashboard |
| system:webhook_received | Webhook接收 | 全阶段 | 接收到外部Webhook事件 | system_worker | low | dashboard |
| system:rag_index_built | RAG索引构建 | 全阶段 | 向量索引重建或增量更新完成 | system_worker | low | dashboard |

## 外部集成状态（参考指南开源推荐）

| 集成 | 开源方案 | 状态监控 |
|------|----------|----------|
| Shopify | OAuth + REST API | 每20分钟同步 |
| 物流追踪 | 17TRACK API | Webhook回调 |
| 邮件通知 | Listmonk (21.2k⭐) | SMTP健康检查 |
| 客服工单 | Chatwoot (29.9k⭐) | Webhook回调 |
| ERP | ERPNext (35.2k⭐) | REST API心跳 |
