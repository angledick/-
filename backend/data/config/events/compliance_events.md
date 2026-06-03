# 合规检查事件定义

> 由QAAgent维护，贯穿10大业务阶段的合规六阶段流水线（感知→检查→推荐→告知→交互→处理）
> 对应指南§6.15 事件驱动合规流水线

## 事件注册表

| 事件编码 | 事件名称 | 业务阶段 | 触发条件 | 关联Worker | 严重级别 | 通知策略 |
|----------|----------|----------|----------|------------|----------|----------|
| compliance:check_started | 合规检查开始 | 全阶段 | 对产品发起合规检查（手动或自动触发） | compliance_worker | low | dashboard |
| compliance:check_passed | 合规检查通过 | 全阶段 | 所有合规规则检查通过，风险评分在阈值内 | compliance_worker | low | dashboard,websocket |
| compliance:check_failed | 合规检查失败 | 全阶段 | 存在未通过的合规规则或风险评分超阈值 | compliance_worker | high | dashboard,websocket,email |
| compliance:hs_code_matched | HS编码匹配 | 阶段3 | 成功匹配HS编码并获取关税信息 | compliance_worker | low | dashboard |
| compliance:vat_queried | VAT税率查询 | 阶段4 | 查询目标市场VAT税率完成 | compliance_worker | low | dashboard |
| compliance:risk_scored | 风险评分完成 | 全阶段 | 产品风险评分计算完成 | compliance_worker | medium | dashboard |
| compliance:recommendation_generated | 推荐生成 | 全阶段 | 六阶段流水线Step3生成推荐操作 | compliance_worker | low | dashboard |
| compliance:pipeline_completed | 流水线完成 | 全阶段 | 六阶段合规流水线完整执行完毕 | compliance_worker | low | dashboard |
| compliance:regulation_impact | 法规影响分析 | 全阶段 | 法规变更对现有产品的影响分析完成 | compliance_worker | high | dashboard,websocket |
