---
category: compliance
events:
  - event_code: "compliance:check_started"
    event_name: "合规检查开始"
    business_stage: "全阶段"
    severity: low
    worker: compliance_worker
    skills: ["compliance_check", "hs_lookup", "vat_query"]
    tools:
      - name: compliance_check
        impl: data/tools/impl/compliance_check.py
      - name: hs_lookup
        impl: data/tools/impl/hs_lookup.py
    notify_strategy: ["dashboard"]
    trigger_condition: "对产品发起合规检查（手动或自动触发）"
    agent_action: "加载目标产品的HS编码、VAT税率、认证要求数据，启动六阶段合规流水线。调用compliance-check skill执行完整检查。"
  - event_code: "compliance:check_passed"
    event_name: "合规检查通过"
    business_stage: "全阶段"
    severity: low
    worker: compliance_worker
    skills: ["compliance_check"]
    tools: []
    notify_strategy: ["dashboard", "websocket"]
    trigger_condition: "所有合规规则检查通过，风险评分在阈值内"
    agent_action: "确认合规状态为通过，更新产品合规评分记录，通过Dashboard和WebSocket推送通过通知。不需要额外整改操作。"
  - event_code: "compliance:check_failed"
    event_name: "合规检查失败"
    business_stage: "全阶段"
    severity: high
    worker: compliance_worker
    skills: ["compliance_check"]
    tools: []
    notify_strategy: ["dashboard", "websocket", "email"]
    trigger_condition: "存在未通过的合规规则或风险评分超阈值"
    agent_action: "标记产品合规状态为failed。列出所有未通过的合规规则，生成整改建议列表。通过所有通知渠道推送失败详情和整改指引。"
  - event_code: "compliance:hs_code_matched"
    event_name: "HS编码匹配"
    business_stage: "阶段3"
    severity: low
    worker: compliance_worker
    skills: ["hs_lookup"]
    tools:
      - name: hs_lookup
        impl: data/tools/impl/hs_lookup.py
    notify_strategy: ["dashboard"]
    trigger_condition: "成功匹配HS编码并获取关税信息"
    agent_action: "将匹配到的HS编码和关税税率绑定到产品记录。更新产品的合规元数据。"
  - event_code: "compliance:vat_queried"
    event_name: "VAT税率查询"
    business_stage: "阶段4"
    severity: low
    worker: compliance_worker
    skills: ["vat_query"]
    tools:
      - name: vat_query
        impl: data/tools/impl/vat_query.py
    notify_strategy: ["dashboard"]
    trigger_condition: "查询目标市场VAT税率完成"
    agent_action: "将VAT税率信息绑定到目标市场的产品记录。更新产品的价格计算和合规元数据。"
  - event_code: "compliance:risk_scored"
    event_name: "风险评分完成"
    business_stage: "全阶段"
    severity: medium
    worker: compliance_worker
    skills: ["risk_score"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "产品风险评分计算完成"
    agent_action: "记录风险评分结果。如果评分为high/critical，升级为预警事件并触发通知。"
  - event_code: "compliance:recommendation_generated"
    event_name: "推荐生成"
    business_stage: "全阶段"
    severity: low
    worker: compliance_worker
    skills: ["compliance_check"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "六阶段流水线Step3生成推荐操作"
    agent_action: "展示合规整改推荐操作列表。等待用户确认或自动执行低风险推荐操作。"
  - event_code: "compliance:pipeline_completed"
    event_name: "流水线完成"
    business_stage: "全阶段"
    severity: low
    worker: compliance_worker
    skills: ["compliance_check"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "六阶段合规流水线完整执行完毕"
    agent_action: "生成流水线执行总结报告，包含检查结果、推荐操作、处理状态。推送到Dashboard。"
  - event_code: "compliance:regulation_impact"
    event_name: "法规影响分析"
    business_stage: "全阶段"
    severity: high
    worker: compliance_worker
    skills: ["impact_analysis"]
    tools: []
    notify_strategy: ["dashboard", "websocket"]
    trigger_condition: "法规变更对现有产品的影响分析完成"
    agent_action: "汇总影响分析结果，列出受影响产品清单和整改操作。高影响项立即推送WebSocket通知，标记产品合规状态。"
---
# 合规检查事件定义

> 由 QAAgent 维护，贯穿10大业务阶段的合规六阶段流水线（感知→检查→推荐→告知→交互→处理）
> 对应指南 §6.15 事件驱动合规流水线
