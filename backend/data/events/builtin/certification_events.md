---
category: certification
events:
  - event_code: "certification:uploaded"
    event_name: "认证上传"
    business_stage: "阶段3"
    severity: low
    worker: cert_worker
    skills: ["cert_verify", "cert_monitor"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "上传认证文件（PDF/图片）到产品记录"
    agent_action: "接收上传的认证文件。调用 cert_verify skill 进行文件有效性验证。将验证结果推送到 Dashboard。"
  - event_code: "certification:verified"
    event_name: "认证验证通过"
    business_stage: "阶段3"
    severity: low
    worker: cert_worker
    skills: ["cert_verify"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "认证文件经RAG比对验证有效"
    agent_action: "更新产品认证状态为有效。记录认证有效期。如果该产品此前因缺认证被阻止上架，触发重新上架检查。"
  - event_code: "certification:rejected"
    event_name: "认证验证失败"
    business_stage: "阶段3"
    severity: high
    worker: cert_worker
    skills: ["cert_verify"]
    tools: []
    notify_strategy: ["dashboard", "websocket"]
    trigger_condition: "认证文件无效或信息不匹配"
    agent_action: "标记认证验证失败原因。通知用户重新上传有效认证文件。如果产品已上架，标记合规状态为可疑。"
  - event_code: "certification:expiring"
    event_name: "认证即将到期"
    business_stage: "全阶段"
    severity: high
    worker: cert_worker
    skills: ["cert_monitor"]
    tools: []
    notify_strategy: ["dashboard", "websocket", "email"]
    trigger_condition: "认证在30天内到期（可配置阈值）"
    agent_action: "生成到期预警。通知用户和供应商启动认证续期流程。列出所有需要续期的认证清单和截止日期。"
  - event_code: "certification:expired"
    event_name: "认证已过期"
    business_stage: "全阶段"
    severity: critical
    worker: cert_worker
    skills: ["cert_monitor"]
    tools: []
    notify_strategy: ["dashboard", "websocket", "email"]
    trigger_condition: "认证超过有效期，产品合规状态变为failed"
    agent_action: "标记产品合规状态为failed。阻止相关产品继续销售。通过所有渠道推送紧急通知要求立即处理。记录过期认证信息供审计。"
  - event_code: "certification:renewed"
    event_name: "认证已续期"
    business_stage: "全阶段"
    severity: low
    worker: cert_worker
    skills: ["cert_monitor"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "认证续期完成，更新有效期"
    agent_action: "更新认证有效期和状态。如果产品因过期而合规失败，重新计算合规状态并恢复。推送续期完成通知。"
  - event_code: "certification:required"
    event_name: "认证需求识别"
    business_stage: "阶段3"
    severity: medium
    worker: cert_worker
    skills: ["cert_verify"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "根据产品类目和目标市场识别所需认证"
    agent_action: "根据产品类目和出口目标市场，计算需要的认证类型列表。展示认证清单和获取指南。"
  - event_code: "certification:missing"
    event_name: "认证缺失"
    business_stage: "阶段3"
    severity: high
    worker: cert_worker
    skills: ["cert_monitor"]
    tools: []
    notify_strategy: ["dashboard", "websocket"]
    trigger_condition: "产品缺少必要认证，阻止上架"
    agent_action: "标记产品上架状态为blocked。列出缺失认证清单和获取指引。推送通知要求补充认证后再上架。"
---
# 认证管理事件定义

> 由 QAAgent 维护，管理产品所需的各类合规认证（CE/WEEE/RoHS/FCC 等）
> 对应指南 §3 阶段3：供应商审核与采购中的认证合规

## 认证类型参考

| 认证名称 | 适用市场 | 适用品类 | 有效期 |
|----------|----------|----------|--------|
| CE | 欧盟 | 电子/玩具/机械 | 无固定（需定期复查） |
| WEEE | 德国/欧盟 | 电子电气 | 1年 |
| RoHS | 欧盟 | 电子电气 | 无固定 |
| FCC | 美国 | 电子产品 | 无固定 |
| UKCA | 英国 | 同CE | 无固定 |
| PSE | 日本 | 电子产品 | 3-7年 |
