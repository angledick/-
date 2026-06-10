---
name: news-collect
display_name: 新闻采集
description: 多数据源新闻采集器（Fed/中国新闻网/金十数据等），支持关键词评分和存储
source: script
script: script/news_collector.py
script_args: ["--hours", "{hours}", "--user-id", "{user_id}", "--save"]
business_stages: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
---

# 新闻采集 Skill

## 概述

从多个数据源（美联储 RSS、中国新闻网 RSS、金十数据 flash API 等）采集跨境行业新闻，
通过关键词评分过滤出与跨境电商合规相关的新闻，可选写入 `news_store` 供后续分析。

## 执行方式

此 Skill 为 **脚本驱动**，通过 Python subprocess 执行独立脚本。

| 步骤 | 说明 |
|------|------|
| 触发 | API (`POST /api/v1/news-monitor/collect`) 或定时任务 `news_collect_and_analyze` |
| 路由 | `SkillExecutor._run_skill()` → `_execute_script_skill()` |
| 脚本 | `script/news_collector.py` |
| 数据源 | FedCollector / ChinaNewsCollector / Jin10Collector |

## 输入参数

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| hours | int | 否 | 48 | 时间窗口（小时） |
| user_id | str | 否 | default | 关键词配置用户 ID |
| save | bool | 否 | false | 是否写入 news_store |

## 输出

```json
{
  "total_collected": 42,
  "saved": 42,
  "items": [...]
}
```

## script/

此目录包含独立可执行 Python 脚本 `news_collector.py`，支持 CLI 参数和 stdin JSON 调用。
