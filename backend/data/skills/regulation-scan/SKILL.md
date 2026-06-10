---
name: regulation-scan
display_name: 法规扫描
description: 扫描目标市场最新法规/政策变更并评估影响
source: prompt
prompt: regulation_scan
business_stages: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
---

# 法规扫描

## 概述

此技能用于**扫描目标市场的最新法规/政策变更**，并评估对跨境电商卖家产品的合规影响。系统通过 Claude Agent SDK 执行 `data/prompts/regulation_scan.yaml` 中的 prompt 模板，由 Claude 使用 WebSearch 工具联网搜索各目标市场的法规公告。

## 执行方式

此技能通过 **prompt 模板驱动**，不包含可执行脚本。

| 步骤 | 说明 |
|------|------|
| 路由 | `SkillExecutor._run_skill()` 识别 `source: prompt` → 调用 `_execute_prompt_skill()` |
| 执行 | `AstraAssistant.run_task(prompt_name="regulation_scan", context=args)` |
| Agent | Claude Agent SDK 加载 `regulation_scan.yaml` 的 system_prompt + output_format |
| 工具 | Claude 内置 WebSearch 工具执行联网搜索 |

## 输入参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| markets | list | 否 | 目标市场列表，默认 ["EU", "US", "UK", "JP", "KR"] |
| days_back | int | 否 | 扫描回溯天数，默认 7 |

## 输出格式

```json
[
  {
    "market": "eu",
    "regulation": "GPSR",
    "change_type": "new_requirement|amendment|deadline|enforcement",
    "summary": "变更摘要",
    "effective_date": "2026-01-01",
    "affected_categories": ["电子产品", "玩具"],
    "severity": "critical|high|medium|low",
    "action_required": "卖家需采取的行动",
    "source_url": "https://..."
  }
]
```

## 相关工具

| 工具 | 用途 |
|------|------|
| WebSearch | Claude 内置：联网搜索法规公告 |
| `regulation_scan.yaml` | prompt 模板（`data/prompts/`） |

## 相关 Worker

- `regulation_worker` — 法规监控Worker，此技能为它的核心技能之一
- `compliance_worker` — 合规检查Worker，依赖此技能的扫描结果

## scripts/

当前无独立脚本。此技能完全由 Claude Agent SDK 通过 prompt 模板驱动。

## references/

可在此目录存放目标市场法规参考文档。

## assets/

可在此目录存放法规通知模板、示例报告等静态资源。
