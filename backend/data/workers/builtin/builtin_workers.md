---
category: builtin
workers:
  - worker_code: product_worker
    worker_name: "产品管理Worker"
    business_stage: "阶段2-4"
    description: "产品CRUD、生命周期状态管理"
    available_skills: ["product_crud", "lifecycle_manager"]
    priority: 2
    timeout: 300
    sdk_enabled: true
  - worker_code: compliance_worker
    worker_name: "合规检查Worker"
    business_stage: "全阶段"
    description: "执行六阶段合规流水线"
    available_skills: ["compliance_check", "hs_lookup", "vat_query"]
    priority: 1
    timeout: 600
    sdk_enabled: true
  - worker_code: cert_worker
    worker_name: "认证管理Worker"
    business_stage: "阶段3"
    description: "认证上传/验证/到期预警"
    available_skills: ["cert_verify", "cert_monitor"]
    priority: 2
    timeout: 300
    sdk_enabled: true
  - worker_code: listing_worker
    worker_name: "商品上架Worker"
    business_stage: "阶段4"
    description: "Listing内容合规检查"
    available_skills: ["content_check", "shopify_publish"]
    priority: 2
    timeout: 300
    sdk_enabled: true
  - worker_code: order_worker
    worker_name: "订单处理Worker"
    business_stage: "阶段6-9"
    description: "订单生命周期管理"
    available_skills: ["order_track", "logistics_query"]
    priority: 3
    timeout: 300
    sdk_enabled: true
  - worker_code: customs_worker
    worker_name: "报关清关Worker"
    business_stage: "阶段7-8"
    description: "出口报关/进口清关"
    available_skills: ["customs_declare", "duty_calc"]
    priority: 2
    timeout: 600
    sdk_enabled: true
  - worker_code: logistics_worker
    worker_name: "物流Worker"
    business_stage: "阶段7-8"
    description: "跨境运输追踪"
    available_skills: ["tracking_query", "eta_calc"]
    priority: 3
    timeout: 300
    sdk_enabled: true
  - worker_code: regulation_worker
    worker_name: "法规监控Worker"
    business_stage: "全阶段"
    description: "法规变更扫描、影响分析"
    available_skills: ["regulation_scan", "impact_analysis"]
    priority: 1
    timeout: 600
    sdk_enabled: true
  - worker_code: risk_worker
    worker_name: "风险预警Worker"
    business_stage: "全阶段"
    description: "风险评分、异常检测"
    available_skills: ["risk_score", "anomaly_detect"]
    priority: 1
    timeout: 300
    sdk_enabled: true
  - worker_code: system_worker
    worker_name: "系统运维Worker"
    business_stage: "全阶段"
    description: "API健康检查、同步任务"
    available_skills: ["health_check", "sync_task"]
    priority: 3
    timeout: 120
    sdk_enabled: true
  - worker_code: qa_agent
    worker_name: "QAAgent"
    business_stage: "全阶段"
    description: "系统自我管理"
    available_skills: ["config_manage", "event_define", "diagnose"]
    priority: 1
    timeout: 600
    sdk_enabled: true
---
# 内置 Worker 定义

> 由系统维护，用户可通过前端管理界面或对话添加自定义 Worker

## 说明

- `worker_code`: Worker 唯一编码
- `business_stage`: 适用的业务阶段
- `available_skills`: Worker 可调用的技能列表
- `priority`: 优先级（1=最高）, 同一事件绑定多个 Worker 时按优先级调用
- `sdk_enabled`: 是否启用 Claude Agent SDK 执行
