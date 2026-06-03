# Worker配置说明

> 本目录存放Worker类型定义配置文件。
> Worker通过配置文件驱动，支持QAAgent动态注册和管理。

## 文件列表

| 文件 | 说明 |
|------|------|
| builtin_workers.md | 内置Worker定义（11个核心Worker） |
| custom_workers.md | 用户自定义Worker（由QAAgent创建） |

## Worker Schema

每个Worker定义包含以下字段：

| 字段 | 必填 | 说明 |
|------|------|------|
| worker_code | 是 | Worker编码（唯一标识） |
| worker_name | 是 | Worker名称 |
| business_stage | 是 | 所属业务阶段 |
| description | 是 | 职责描述 |
| available_skills | 否 | 可用Skills列表（逗号分隔） |
| priority | 否 | 优先级（1-5，数字越小越高） |
| timeout | 否 | 执行超时时间（秒） |
