---
category: regulation
events:
  - event_code: "regulation:updated"
    event_name: "法规更新"
    business_stage: "全阶段"
    severity: high
    worker: regulation_worker
    skills: ["regulation_scan", "impact_analysis"]
    tools:
      - name: regulation_scan
        impl: data/tools/impl/regulation_scan.py
    notify_strategy: ["dashboard", "websocket", "email"]
    trigger_condition: "MarketMonitor检测到已知法规内容更新"
    agent_action: "立即启动 impact-analysis skill 评估对所有产品的潜在影响。生成变更对比和影响范围报告，通过 Dashboard 和邮件推送。"
  - event_code: "regulation:new"
    event_name: "新法规生效"
    business_stage: "全阶段"
    severity: high
    worker: regulation_worker
    skills: ["regulation_scan", "impact_analysis"]
    tools:
      - name: regulation_scan
        impl: data/tools/impl/regulation_scan.py
    notify_strategy: ["dashboard", "websocket", "email"]
    trigger_condition: "目标市场新法规正式生效"
    agent_action: "启动完整合规流水线：1) 评估受影响产品范围 2) 检查现有认证是否满足新要求 3) 生成整改计划 4) 通过所有渠道推送紧急通知。"
  - event_code: "regulation:repealed"
    event_name: "法规废止"
    business_stage: "全阶段"
    severity: medium
    worker: regulation_worker
    skills: ["regulation_scan"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "已知法规被废止或替代"
    agent_action: "更新法规状态为废止。检查依赖此法规的产品是否受影响（通常废止为正面影响），通知用户法规变更结果。"
  - event_code: "regulation:tariff_changed"
    event_name: "关税变更"
    business_stage: "全阶段"
    severity: high
    worker: regulation_worker
    skills: ["regulation_scan", "impact_analysis"]
    tools: []
    notify_strategy: ["dashboard", "websocket"]
    trigger_condition: "HS编码对应关税税率变更"
    agent_action: "更新受影响的HS编码关税税率。重新计算涉及产品的成本和利润。推送关税变更到 Dashboard 和 WebSocket。"
  - event_code: "regulation:vat_changed"
    event_name: "VAT变更"
    business_stage: "全阶段"
    severity: medium
    worker: regulation_worker
    skills: ["regulation_scan"]
    tools: []
    notify_strategy: ["dashboard", "websocket"]
    trigger_condition: "目标市场VAT税率调整"
    agent_action: "更新目标市场VAT税率配置。重新计算受影响产品的含税价格。推送VAT变更通知。"
  - event_code: "regulation:cert_requirement_changed"
    event_name: "认证要求变更"
    business_stage: "全阶段"
    severity: high
    worker: regulation_worker
    skills: ["regulation_scan", "impact_analysis"]
    tools: []
    notify_strategy: ["dashboard", "websocket", "email"]
    trigger_condition: "产品类目认证要求新增或变更"
    agent_action: "识别受影响的类目和产品。检查现有产品是否满足新认证要求，标记缺失认证的产品，推动补充认证流程。"
  - event_code: "regulation:import_restriction"
    event_name: "进口限制"
    business_stage: "全阶段"
    severity: critical
    worker: regulation_worker
    skills: ["regulation_scan", "impact_analysis"]
    tools: []
    notify_strategy: ["dashboard", "websocket", "email"]
    trigger_condition: "目标市场新增进口限制（禁运/配额）"
    agent_action: "这是最高级别事件。立即识别所有受影响产品SKU。标记为'进口受限'状态。暂停所有面向该市场的订单。生成高优先级通知推送所有渠道。"
  - event_code: "regulation:labeling_changed"
    event_name: "标签要求变更"
    business_stage: "全阶段"
    severity: medium
    worker: regulation_worker
    skills: ["regulation_scan"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "产品标签/包装要求更新"
    agent_action: "更新受影响产品的标签要求规范。生成标签更新通知指向供应商。推动产品Listing内容更新。"
---
# 市场法规变更事件定义

> 由 QAAgent 维护，监控目标市场法规变更并触发影响分析
> 对应指南 §3 全阶段法规监控 + MarketMonitor定时任务

## 法规数据源

| 市场 | 数据源 | 更新频率 | 采集方式 |
|------|--------|----------|----------|
| 欧盟 | EU Official Journal | 每日 | RSS/API |
| 德国 | BAFA/BfR | 每周 | 网页抓取 |
| 美国 | Federal Register | 每日 | API |
| 英国 | GOV.UK | 每周 | API |
