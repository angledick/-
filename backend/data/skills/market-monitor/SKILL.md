---
name: market-monitor
display_name: 市场监控
description: 联网监控目标市场合规动态
source: prompt
prompt: market_monitor
business_stages: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
---

# 市场监控

## 概述

此技能用于**持续联网监控目标市场的合规动态**。它定期检查各目标市场的法规公告、政策变化和行业新闻，并在发现重要变更时触发后续合规流程（影响分析→风险预警→推送通知）。

系统通过 Claude Agent SDK 执行 `data/prompts/market_monitor.yaml` 中的 prompt 模板，由 Claude 使用 WebSearch 工具进行定期巡查。

## 执行方式

此技能通过 **prompt 模板驱动**，通常由定时任务 (`scan_regulation_changes` / `poll_all_markets`) 触发。

| 步骤 | 说明 |
|------|------|
| 触发 | Scheduler 的定时任务 → `regulation_worker` → `AstraAssistant` |
| 执行 | `SkillExecutor._run_skill()` → `_execute_prompt_skill()` |
| prompt | `market_monitor.yaml` — 定义市场巡查范围和输出格式 |
| 工具 | Claude 内置 WebSearch 联网搜索 |

## 输入参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| markets | list | 否 | 监控市场列表，默认全部已配置市场 |
| categories | list | 否 | 监控类别：regulation / tariff / certification / labeling |
| since | string | 否 | 起始时间 ISO8601 |

## 输出格式

```json
{
  "monitored_markets": ["EU", "US", "UK"],
  "findings": [
    {
      "market": "EU",
      "type": "regulation",
      "title": "GPSR 正式生效",
      "summary": "...",
      "severity": "high",
      "source_url": "https://...",
      "detected_at": "2026-06-08T00:00:00Z"
    }
  ],
  "summary": "本次巡查发现 3 项变更，其中 1 项高风险",
  "recommended_actions": ["立即启动 impact-analysis"]
}
```

## 相关 Worker

- `regulation_worker` — 法规监控Worker，此技能的核心执行者
- `risk_worker` — 风险预警Worker，接收此技能的发现进行评分

## 相关定时任务

| 任务名 | 频率 | 说明 |
|--------|------|------|
| `poll_all_markets` | 可配置（默认 60 分钟） | 全市场轮询 |
| `scan_regulation_changes` | 每小时 | 法规变更扫描 |

## scripts/

当前无独立脚本。完全由 Claude Agent SDK 通过 prompt 模板驱动。

## references/

可在此目录存放各市场监控清单、数据源地址等参考文档。

## assets/

可在此目录存放监控 Dashboard 模板、通知卡片模板等。
