---
category: risk_alert
events:
  - event_code: "risk:threshold_breached"
    event_name: "风险阈值突破"
    business_stage: "全阶段"
    severity: high
    worker: risk_worker
    skills: ["risk_score", "anomaly_detect"]
    tools: []
    notify_strategy: ["dashboard", "websocket", "email"]
    trigger_condition: "合规指标超过预设阈值"
    agent_action: "识别触发阈值的关键指标和当前值。立即生成风险报告，列出影响范围。通过所有配置渠道推送预警。触发自动或手动整改流程。"
  - event_code: "risk:metric_alert"
    event_name: "指标预警"
    business_stage: "全阶段"
    severity: medium
    worker: risk_worker
    skills: ["risk_score"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "自定义指标异常波动"
    agent_action: "分析异常指标的趋势和可能原因。生成诊断报告，标记异常类型。推送到Dashboard供运营人员查看。如连续3次异常，升级为high级别预警。"
  - event_code: "risk:chargeback_alert"
    event_name: "拒付预警"
    business_stage: "阶段5"
    severity: high
    worker: risk_worker
    skills: ["risk_score", "anomaly_detect"]
    tools: []
    notify_strategy: ["dashboard", "websocket", "email"]
    trigger_condition: "拒付率超过阈值（默认2%）"
    agent_action: "汇总拒付订单清单和拒付原因分析。检查是否有集中拒付模式（特定产品/地区/时间段）。生成拒付防范建议。推送到客服和运营部门。"
  - event_code: "risk:cert_expiry_batch"
    event_name: "批量认证到期"
    business_stage: "全阶段"
    severity: high
    worker: risk_worker
    skills: ["risk_score"]
    tools: []
    notify_strategy: ["dashboard", "email"]
    trigger_condition: "多个产品认证同期即将到期"
    agent_action: "列出所有即将到期或已过期的认证清单。按严重程度排序。生成批量续期建议和优先级。推送到Dashboard和Email通知相关责任人。"
  - event_code: "risk:regulation_conflict"
    event_name: "法规冲突"
    business_stage: "全阶段"
    severity: high
    worker: risk_worker
    skills: ["risk_score", "impact_analysis"]
    tools: []
    notify_strategy: ["dashboard", "websocket"]
    trigger_condition: "产品同时出口多市场时法规要求冲突"
    agent_action: "识别具体冲突的法规条款和涉及的产品市场组合。生成冲突分析报告，列出可选的合规路径。通知产品经理和合规团队决策。"
  - event_code: "risk:fraud_detected"
    event_name: "欺诈检测"
    business_stage: "阶段6"
    severity: critical
    worker: risk_worker
    skills: ["anomaly_detect"]
    tools: []
    notify_strategy: ["dashboard", "websocket", "email"]
    trigger_condition: "订单欺诈风险评分异常（PyOD异常检测）"
    agent_action: "识别欺诈订单详情和风险评分。根据评分执行阻断或人工审核。记录欺诈模式到黑名单。推送到财务和风控团队处理。"
  - event_code: "risk:supply_chain_alert"
    event_name: "供应链风险"
    business_stage: "阶段3"
    severity: high
    worker: risk_worker
    skills: ["risk_score"]
    tools: []
    notify_strategy: ["dashboard", "websocket"]
    trigger_condition: "供应商合规状态异常"
    agent_action: "确认异常供应商和受影响产品清单。评估备选供应商方案和切换成本。生成供应链风险报告推送到Dashboard。"
  - event_code: "risk:compliance_score_drop"
    event_name: "合规评分下降"
    business_stage: "全阶段"
    severity: medium
    worker: risk_worker
    skills: ["risk_score"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "产品合规评分显著下降"
    agent_action: "分析合规评分下降的主要因素（法规变更/认证到期/新禁令）。生成改进措施列表。推送到Dashboard并通知产品负责人。"
---
# 风险预警事件定义

> 由 QAAgent 维护，RiskAlert 模块定时扫描触发
> 对应指南 §3 全阶段风险监控 + 反欺诈（开源推荐：PyOD 8.5k⭐）

## 风险评分规则

| 评分区间 | 风险等级 | 处理策略 |
|----------|----------|----------|
| 0-30 | low | 正常运营 |
| 31-60 | medium | 关注并制定预案 |
| 61-80 | high | 立即整改 |
| 81-100 | critical | 暂停运营直到整改完成 |
