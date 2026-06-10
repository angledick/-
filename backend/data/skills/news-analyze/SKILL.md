---
name: news-analyze
display_name: 新闻AI分析
description: 使用LLM分析新闻对跨境电商的风险方向（利多/利空/中性）
source: script
script: script/news_analyzer.py
script_args: ["--limit", "{limit}"]
business_stages: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
---

# 新闻 AI 分析 Skill

## 概述

使用配置的 LLM（MiMo 等）对采集的新闻进行风险方向分析，判断其对跨境电商卖家
的潜在影响（利多 / 利空 / 中性），输出结构化分析结果。

## 执行方式

此 Skill 为 **脚本驱动**，通过 Python subprocess 执行独立脚本。

| 步骤 | 说明 |
|------|------|
| 触发 | API (`POST /api/v1/news-monitor/collect`) 或定时任务 `news_collect_and_analyze` 中的分析步骤 |
| 路由 | `SkillExecutor._run_skill()` → `_execute_script_skill()` |
| 脚本 | `script/news_analyzer.py` |
| LLM | 从环境变量 / app.config / .env 读取 `LLM_API_KEY` 配置 |

## 输入参数

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| limit | int | 否 | 20 | 分析条数上限 |
| hours | int | 否 | 24 | 市场摘要时间窗口 |

## 输出

```json
{
  "analyzed": 15,
  "total_pending": 20,
  "results": [...]
}
```

## script/

此目录包含独立可执行 Python 脚本 `news_analyzer.py`，支持 CLI 参数和 stdin JSON 调用。
