---
event_code: "custom:your_event"
event_name: "自定义事件名称"
category: custom
business_stage: "阶段1"
severity: low
worker: compliance_worker
skills: []
tools: []
notify_strategy: ["dashboard"]
trigger_condition: "事件触发条件描述"
agent_action: ""  # Agent收到此事件时的处理操作描述
---
# 自定义事件

> 用户自定义事件，由 QAAgent 或用户手动创建

## 事件描述

请在此处描述事件的处理逻辑和注意事项。

## 数据 Schema（可选）

```yaml
data_schema:
  required:
    - field1
  optional:
    - field2
```
