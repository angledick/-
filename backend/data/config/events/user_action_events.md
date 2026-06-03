# 用户操作审计事件定义

> 由QAAgent维护，记录用户在系统内的所有关键操作
> 对应指南§3 全阶段操作审计 + QAAgent自我管理

## 事件注册表

| 事件编码 | 事件名称 | 业务阶段 | 触发条件 | 关联Worker | 严重级别 | 通知策略 |
|----------|----------|----------|----------|------------|----------|----------|
| user:login | 用户登录 | 全阶段 | 用户登录系统 | system_worker | low | dashboard |
| user:logout | 用户登出 | 全阶段 | 用户登出系统 | system_worker | low | dashboard |
| user:config_changed | 配置变更 | 全阶段 | 用户修改系统配置（通知/模型/安全策略） | qa_agent | medium | dashboard |
| user:product_added | 添加产品 | 阶段2 | 用户手动添加产品 | qa_agent | low | dashboard |
| user:product_deleted | 删除产品 | 全阶段 | 用户删除产品 | qa_agent | medium | dashboard |
| user:event_defined | 事件定义 | 全阶段 | 用户通过QAAgent定义新事件类型 | qa_agent | medium | dashboard |
| user:worker_configured | Worker配置 | 全阶段 | 用户配置Worker参数 | qa_agent | medium | dashboard |
| user:notification_settings | 通知设置 | 全阶段 | 用户修改通知偏好 | qa_agent | low | dashboard |
| user:export_data | 数据导出 | 全阶段 | 用户导出数据（Obsidian Wiki/CSV） | qa_agent | low | dashboard |
| user:cli_command | CLI命令 | 全阶段 | 用户执行CLI命令 | qa_agent | low | dashboard |
| user:magic_command | 魔法命令 | 全阶段 | 用户执行魔法命令（/clear, /retry等） | qa_agent | low | dashboard |
| user:approval_granted | 审批通过 | 全阶段 | 用户批准敏感操作 | qa_agent | medium | dashboard |
| user:approval_denied | 审批拒绝 | 全阶段 | 用户拒绝敏感操作 | qa_agent | medium | dashboard |

## QAAgent自我管理操作

QAAgent可代表用户执行以下管理操作：
- 定义/修改/删除事件类型
- 配置Worker参数和优先级
- 管理通知渠道和阈值
- 执行系统健康检查和诊断
- 生成合规简报和分析报告
