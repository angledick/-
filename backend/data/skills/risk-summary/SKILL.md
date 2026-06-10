---
name: risk-summary
display_name: 风险摘要
description: 生成合规风险摘要报告
source: prompt
prompt: risk_summary
business_stages: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
---

# 风险摘要

## 概述

此技能用于**生成合规风险摘要报告**。它汇总来自 regulation-scan、impact-analysis 和 compliance-check 的输出，结合产品库和认证数据，生成结构化的风险报告和优先级排序。

系统通过 Claude Agent SDK 执行 `data/prompts/risk_summary.yaml` 中的 prompt 模板。

## 执行方式

此技能通过 **prompt 模板驱动**，通常由定时任务 (`daily_compliance_brief`) 或手动触发。

| 步骤 | 说明 |
|------|------|
| 路由 | `SkillExecutor._run_skill()` → `_execute_prompt_skill()` |
| 执行 | `AstraAssistant.run_task(prompt_name="risk_summary", context=args)` |
| 输入 | 整合其它技能的输出结果 |
| 输出 | 格式化风险报告，推送到 Dashboard / 通知渠道 |

## 输入参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| scope | string | 否 | 汇总范围：all / market / product |
| market | string | 否 | 目标市场（scope=market 时必填） |
| product_id | string | 否 | 产品 ID（scope=product 时必填） |
| include_chart | bool | 否 | 是否包含图表数据，默认 false |
| output_format | string | 否 | 输出格式：markdown / json / html，默认 markdown |

## 输出格式（Markdown 版）

```markdown
# 合规风险摘要报告
**生成时间**: 2026-06-08T10:00:00Z
**范围**: 全市场

## 高风险项
| 风险 | 市场 | 产品数 | 截止日 | 状态 |
|------|------|--------|--------|------|
| GPSR 生效 | EU | 23 | 2026-12-13 | ⚠️ 待处理 |

## 合规评分
- 全盘合规率: 87.3%
- 高风险产品: 5
- 到期预警: 12 项认证

## 建议操作
1. 立即启动 impact-analysis 评估 GPSR 影响
2. ...
```

## 相关 Worker

- `risk_worker` — 风险预警Worker，生成风险评分
- `compliance_worker` — 合规检查Worker，提供流水线数据
- `system_worker` — 系统运维Worker，生成聚合报告

## 相关定时任务

| 任务名 | 频率 | 说明 |
|--------|------|------|
| `daily_compliance_brief` | 每天 09:00 | 生成每日合规简报 |
| `generate_cross_product_insights` | 每 4 小时 | 跨产品洞察 |

## scripts/

当前无独立脚本。完全由 Claude Agent SDK 通过 prompt 模板驱动。

## references/

可在此目录存放风险评级标准、报告模板样例等参考文档。

## assets/

可在此目录存放风险 Dashboard 截图、报告封面模板等。
