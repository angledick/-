# 事件配置说明

> 本目录存放事件类型定义配置文件，每类事件一个Markdown文件。
> 事件类型通过配置文件驱动，支持QAAgent和用户动态添加/修改/删除。

## 文件列表

| 文件 | 事件类别 | 说明 |
|------|----------|------|
| lifecycle_events.md | lifecycle | 产品生命周期事件（创建/上架/下架等） |
| compliance_events.md | compliance | 合规检查事件（检查/通过/失败等） |
| certification_events.md | certification | 认证管理事件（上传/到期/续期等） |
| order_events.md | order | 订单履约事件（创建/发货/退货等） |
| regulation_events.md | regulation | 市场法规变更事件（更新/新增/废止等） |
| risk_alert_events.md | risk_alert | 风险预警事件（阈值突破/异常检测等） |
| system_events.md | system | 系统运维事件（同步/健康检查/备份等） |
| user_action_events.md | user_action | 用户操作审计事件（登录/配置变更等） |
| custom_events.md | - | 用户自定义事件（由QAAgent创建） |

## 事件Schema

每个事件定义包含以下字段：

| 字段 | 必填 | 说明 |
|------|------|------|
| event_code | 是 | 事件编码（唯一标识），格式 `category:name` |
| event_name | 是 | 事件名称 |
| business_stage | 是 | 所属业务阶段（阶段1-10 或 全阶段） |
| trigger_condition | 是 | 触发条件描述 |
| related_worker | 否 | 关联Worker编码 |
| severity | 否 | 严重级别（low/medium/high/critical） |
| notify_strategy | 否 | 通知策略（dashboard/websocket/email，逗号分隔） |
