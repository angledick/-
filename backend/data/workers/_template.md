---
worker_code: "custom_worker"
worker_name: "自定义 Worker 名称"
business_stage: "全阶段"
description: "Worker 职责描述"
available_skills: []
priority: 5
timeout: 300
sdk_enabled: true
---
# 自定义 Worker

> 用户可通过 QAAgent 或手动创建此文件来注册新的 Worker

## 说明

- 自定义 Worker 放在 `data/workers/custom/` 目录下
- 每个文件定义一个 Worker
- Worker 可通过 `sdk_enabled` 控制是否启用 Claude Agent SDK
