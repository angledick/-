---
name: compliance-check
display_name: 合规检查
description: 执行六阶段合规流水线检查
source: prompt
prompt: chat_compliance
business_stages: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
---

# 合规检查

## 概述

此技能用于**执行六阶段合规流水线**，从感知→检查→推荐→告知→交互→处理，贯穿产品的全生命周期。它整合法规数据（RAG知识库）、产品信息、认证状态，生成完整的合规评估报告。

系统通过 Claude Agent SDK 执行 `data/prompts/chat_compliance.yaml` 中的 prompt 模板，Claude 可调用 MCP 工具（如 `lookup_hs_code`、`lookup_vat_rate`）获取实时数据。

## 执行方式

此技能通过 **prompt 模板驱动**，是六阶段合规流水线的核心执行入口。

| 步骤 | 说明 |
|------|------|
| 路由 | `SkillExecutor._run_skill()` 识别 `source: prompt` → `_execute_prompt_skill()` |
| 执行 | `AstraAssistant.run_task(prompt_name="chat_compliance", context=args)` |
| MCP 工具 | `astra_tools.py` 中的 `lookup_hs_code` / `lookup_vat_rate` / `check_certification` |
| 数据源 | `data/storage/` 产品库 + `data/raw/` 法规文档 + ChromaDB 知识库 |

## 流水线结构

```
Step 1 感知   → 接收事件/用户请求
Step 2 检查   → HS编码查询 → VAT税率 → 认证要求 → 风险评估
Step 3 推荐   → 生成合规整改建议
Step 4 告知   → 通过 Dashboard/WebSocket/Email 推送
Step 5 交互   → 用户确认/调整操作
Step 6 处理   → 执行操作并记录结果
```

## 输入参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| product_id | string | 是 | 产品 ID |
| market | string | 是 | 目标市场 |
| action | string | 否 | 触发动作：check / recommend / report |
| pipeline_steps | list | 否 | 要执行的步骤列表，默认全部 |

## 相关 Worker

- `compliance_worker` — 合规检查Worker，此技能的核心执行者
- `cert_worker` — 认证管理Worker，提供认证状态数据
- `customs_worker` — 报关清关Worker

## scripts/

当前无独立脚本。完全由 Claude Agent SDK 通过 prompt 模板驱动，运行时按需调用 MCP 工具。

## references/

可在此目录存放合规检查清单、各国法规要求汇总等参考文档。

## assets/

可在此目录存放合规报告模板、流水线状态图等静态资源。
