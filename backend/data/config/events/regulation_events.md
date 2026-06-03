# 市场法规变更事件定义

> 由QAAgent维护，监控目标市场法规变更并触发影响分析
> 对应指南§3 全阶段法规监控 + MarketMonitor定时任务

## 事件注册表

| 事件编码 | 事件名称 | 业务阶段 | 触发条件 | 关联Worker | 严重级别 | 通知策略 |
|----------|----------|----------|----------|------------|----------|----------|
| regulation:updated | 法规更新 | 全阶段 | MarketMonitor检测到已知法规内容更新 | regulation_worker | high | dashboard,websocket,email |
| regulation:new | 新法规生效 | 全阶段 | 目标市场新法规正式生效 | regulation_worker | high | dashboard,websocket,email |
| regulation:repealed | 法规废止 | 全阶段 | 已知法规被废止或替代 | regulation_worker | medium | dashboard |
| regulation:tariff_changed | 关税变更 | 全阶段 | HS编码对应关税税率变更 | regulation_worker | high | dashboard,websocket |
| regulation:vat_changed | VAT变更 | 全阶段 | 目标市场VAT税率调整 | regulation_worker | medium | dashboard,websocket |
| regulation:cert_requirement_changed | 认证要求变更 | 全阶段 | 产品类目认证要求新增或变更 | regulation_worker | high | dashboard,websocket,email |
| regulation:import_restriction | 进口限制 | 全阶段 | 目标市场新增进口限制（禁运/配额） | regulation_worker | critical | dashboard,websocket,email |
| regulation:labeling_changed | 标签要求变更 | 全阶段 | 产品标签/包装要求更新 | regulation_worker | medium | dashboard |

## 法规数据源

| 市场 | 数据源 | 更新频率 | 采集方式 |
|------|--------|----------|----------|
| 欧盟 | EU Official Journal | 每日 | RSS/API |
| 德国 | BAFA/BfR | 每周 | 网页抓取 |
| 美国 | Federal Register | 每日 | API |
| 英国 | GOV.UK | 每周 | API |
