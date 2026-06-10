---
category: user_action
events:
  - event_code: "user:login"
    event_name: "用户登录"
    business_stage: "全阶段"
    severity: low
    worker: system_worker
    skills: []
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "用户登录系统"
    agent_action: "记录登录时间、IP地址和登录方式。检查是否有异常登录特征（异地登录/非常用设备）。记录审计日志。"
  - event_code: "user:logout"
    event_name: "用户登出"
    business_stage: "全阶段"
    severity: low
    worker: system_worker
    skills: []
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "用户登出系统"
    agent_action: "记录登出时间。清理用户会话缓存。更新在线状态。"
  - event_code: "user:config_changed"
    event_name: "配置变更"
    business_stage: "全阶段"
    severity: medium
    worker: qa_agent
    skills: ["config_manage"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "用户修改系统配置（通知/模型/安全策略）"
    agent_action: "记录配置变更前后的diff。验证新配置的有效性。通知影响范围给相关用户。回滚方案自动保存。"
  - event_code: "user:product_added"
    event_name: "添加产品"
    business_stage: "阶段2"
    severity: low
    worker: qa_agent
    skills: ["config_manage"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "用户手动添加产品"
    agent_action: "检查产品信息完整性（必填字段、HS编码）。触发新产品合规初始化流程。同步到Shopify产品库。"
  - event_code: "user:product_deleted"
    event_name: "删除产品"
    business_stage: "全阶段"
    severity: medium
    worker: qa_agent
    skills: ["config_manage"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "用户删除产品"
    agent_action: "确认删除操作意图。执行产品数据软删除（保留审计记录）。关闭关联的合规检查任务。更新Dashboard统计数据。"
  - event_code: "user:event_defined"
    event_name: "事件定义"
    business_stage: "全阶段"
    severity: medium
    worker: qa_agent
    skills: ["event_define", "config_manage"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "用户通过QAAgent定义新事件类型"
    agent_action: "验证事件定义的完整性（code/name/worker/skills）。注册新事件到事件注册表。检查事件是否需要在stage yaml中引用。"
  - event_code: "user:worker_configured"
    event_name: "Worker配置"
    business_stage: "全阶段"
    severity: medium
    worker: qa_agent
    skills: ["config_manage"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "用户配置Worker参数"
    agent_action: "验证Worker配置参数的有效性。重新加载Worker注册表。测试Worker实例化是否成功。如影响现有任务，需要用户确认。"
  - event_code: "user:notification_settings"
    event_name: "通知设置"
    business_stage: "全阶段"
    severity: low
    worker: qa_agent
    skills: ["config_manage"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "用户修改通知偏好"
    agent_action: "验证通知渠道配置（Webhook URL/Email SMTP/WebSocket）。发送测试通知到新渠道。记录变更。"
  - event_code: "user:export_data"
    event_name: "数据导出"
    business_stage: "全阶段"
    severity: low
    worker: qa_agent
    skills: []
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "用户导出数据（Obsidian Wiki/CSV）"
    agent_action: "确定导出范围和格式（Obsidian Wiki Markdown/CSV/JSON）。生成导出文件。提供下载链接。记录导出审计日志。"
  - event_code: "user:cli_command"
    event_name: "CLI命令"
    business_stage: "全阶段"
    severity: low
    worker: qa_agent
    skills: []
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "用户执行CLI命令"
    agent_action: "解析CLI命令参数。执行命令并返回结果。记录执行日志到审计。如果命令需要前端执行的，提示用户在终端执行。"
  - event_code: "user:magic_command"
    event_name: "魔法命令"
    business_stage: "全阶段"
    severity: low
    worker: qa_agent
    skills: []
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "用户执行魔法命令（/clear, /retry等）"
    agent_action: "识别魔法命令类型。执行对应操作。记录操作结果。如命令有状态变更，更新Dashboard。"
  - event_code: "user:approval_granted"
    event_name: "审批通过"
    business_stage: "全阶段"
    severity: medium
    worker: qa_agent
    skills: ["config_manage"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "用户批准敏感操作"
    agent_action: "记录审批人和审批时间。执行被批准的敏感操作。通知操作执行结果。更新审批状态为completed。"
  - event_code: "user:approval_denied"
    event_name: "审批拒绝"
    business_stage: "全阶段"
    severity: medium
    worker: qa_agent
    skills: ["config_manage"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "用户拒绝敏感操作"
    agent_action: "记录拒绝原因。取消待执行的操作。通知发起人拒绝结果和原因。如操作为自动审批，解除锁定状态。"
---
# 用户操作审计事件定义

> 由 QAAgent 维护，记录用户在系统内的所有关键操作
> 对应指南 §3 全阶段操作审计 + QAAgent自我管理

## QAAgent自我管理操作

QAAgent可代表用户执行以下管理操作：
- 定义/修改/删除事件类型
- 配置Worker参数和优先级
- 管理通知渠道和阈值
- 执行系统健康检查和诊断
- 生成合规简报和分析报告
