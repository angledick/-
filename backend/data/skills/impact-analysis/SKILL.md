---
name: impact-analysis
display_name: 影响分析
description: 分析法规变更对用户产品的潜在影响
source: prompt
prompt: impact_analysis
business_stages: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
---

# 影响分析

## 概述

此技能用于**分析法规变更对现有产品的潜在影响**。当扫描到法规变更后，此技能评估哪些产品 SKU 受影响、影响范围（必须下架/修改Listing/补充认证/无需操作）、紧急程度和时间窗口。

系统通过 Claude Agent SDK 执行 `data/prompts/impact_analysis.yaml` 中的 prompt 模板。

## 执行方式

此技能通过 **prompt 模板驱动**，不包含可执行脚本。

| 步骤 | 说明 |
|------|------|
| 路由 | `SkillExecutor._run_skill()` 识别 `source: prompt` → `_execute_prompt_skill()` |
| 执行 | `AstraAssistant.run_task(prompt_name="impact_analysis", context=args)` |
| 输入 | regulation-scan 输出的法规变更 JSON + 产品目录 |
| 输出 | 各产品 SKU 的影响等级与操作建议 |

## 输入参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| regulation_changes | list | 是 | 法规变更列表（来自 regulation-scan 输出） |
| product_skus | list | 否 | 待分析的产品 SKU 列表 |
| markets | list | 否 | 目标市场 |

## 输出格式

```json
[
  {
    "sku": "PROD-001",
    "market": "EU",
    "regulation": "GPSR",
    "impact_level": "high|medium|low|none",
    "actions": ["补充CE认证文件", "更新产品标签"],
    "deadline": "2026-09-01",
    "notes": "需在生效日前完成整改"
  }
]
```

## 相关 Worker

- `compliance_worker` — 合规检查Worker，使用此技能生成影响报告
- `risk_worker` — 风险预警Worker，依赖此评估结果

## scripts/

当前无独立脚本。完全由 Claude Agent SDK 通过 prompt 模板驱动。

## references/

可在此目录存放影响分析模板、产品分类规则等参考文档。

## assets/

可在此目录存放影响等级标签、分析图表模板等静态资源。
