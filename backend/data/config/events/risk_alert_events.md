# 风险预警事件定义

> 由QAAgent维护，RiskAlert模块定时扫描触发
> 对应指南§3 全阶段风险监控 + 反欺诈（开源推荐：PyOD 8.5k⭐）

## 事件注册表

| 事件编码 | 事件名称 | 业务阶段 | 触发条件 | 关联Worker | 严重级别 | 通知策略 |
|----------|----------|----------|----------|------------|----------|----------|
| risk:threshold_breached | 风险阈值突破 | 全阶段 | 合规指标超过预设阈值 | risk_worker | high | dashboard,websocket,email |
| risk:metric_alert | 指标预警 | 全阶段 | 自定义指标异常波动 | risk_worker | medium | dashboard |
| risk:chargeback_alert | 拒付预警 | 阶段5 | 拒付率超过阈值（默认2%） | risk_worker | high | dashboard,websocket,email |
| risk:cert_expiry_batch | 批量认证到期 | 全阶段 | 多个产品认证同期即将到期 | risk_worker | high | dashboard,email |
| risk:regulation_conflict | 法规冲突 | 全阶段 | 产品同时出口多市场时法规要求冲突 | risk_worker | high | dashboard,websocket |
| risk:fraud_detected | 欺诈检测 | 阶段6 | 订单欺诈风险评分异常（PyOD异常检测） | risk_worker | critical | dashboard,websocket,email |
| risk:supply_chain_alert | 供应链风险 | 阶段3 | 供应商合规状态异常 | risk_worker | high | dashboard,websocket |
| risk:compliance_score_drop | 合规评分下降 | 全阶段 | 产品合规评分显著下降 | risk_worker | medium | dashboard |

## 风险评分规则

| 评分区间 | 风险等级 | 处理策略 |
|----------|----------|----------|
| 0-30 | low | 正常运营 |
| 31-60 | medium | 关注并制定预案 |
| 61-80 | high | 立即整改 |
| 81-100 | critical | 暂停运营直到整改完成 |
