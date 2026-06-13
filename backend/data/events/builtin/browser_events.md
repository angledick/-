---
category: browser
events:
  - event_code: "browser:status_check"
    event_name: "浏览器状态检查"
    business_stage: "全阶段"
    severity: low
    worker: browser_worker
    skills: ["browser-control"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "用户或系统请求检查 OpenCLI 守护进程状态"
    agent_action: "调用 browser-control 技能执行 status 检查，返回守护进程状态和可用站点列表。"
  - event_code: "browser:site_query"
    event_name: "站点数据查询"
    business_stage: "全阶段"
    severity: low
    worker: browser_worker
    skills: ["browser-control"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "用户请求获取某个站点的数据（如 HackerNews 热门、GitHub trending）"
    agent_action: "调用 browser-control 技能的 site action，传入 site 和 command 参数获取结构化数据。"
  - event_code: "browser:navigate"
    event_name: "浏览器导航"
    business_stage: "全阶段"
    severity: low
    worker: browser_worker
    skills: ["browser-control"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "用户请求导航到指定 URL"
    agent_action: "调用 browser-control 技能的 navigate action，导航到目标 URL 并返回页面标题和快照。"
---
# 浏览器控制事件定义

> 由 browser_worker 处理，通过 OpenCLI 实现浏览器自动化

## 事件 Schema 定义

```yaml
event_schema:
  required:
    - event_code
    - event_name
    - worker
    - skills
  optional:
    - severity
    - notify_strategy
    - agent_action
