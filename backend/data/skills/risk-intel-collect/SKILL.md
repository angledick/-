---
skill_id: risk-intel-collect
name: 风险情报采集
description: 从全球 15+ 信源（USTR/OFAC/Reuters/IMF/金十等）采集关税/冲突/金融三大域风险情报
version: "1.0"
author: system
category: risk
stage: all
enabled: true
script: script/risk_intel_collector.py
execution_mode: subprocess
timeout: 120
dependencies:
  - feedparser
  - httpx
env_vars:
  - METASO_API_KEY
inputs:
  - name: hours
    type: integer
    default: 48
    description: 时间窗口（小时）
  - name: domains
    type: array
    description: 过滤域（tariff/conflict/financial）
  - name: keyword
    type: string
    description: 附加米塔关键词搜索
  - name: save
    type: boolean
    default: false
    description: 是否写入数据库
outputs:
  - name: items
    type: array
    description: 情报条目列表
  - name: total
    type: integer
  - name: sources
    type: object
    description: 各信源采集数量
---

# 风险情报采集 Skill

从全球 15+ 主流信源采集三大风险域情报：

## 信源矩阵

| 域 | 信源 | 类型 |
|---|------|------|
| 关税 | USTR（美贸易代表）、CBP（美海关）、EU Official、WTO、海关总署 | RSS/HTTP |
| 冲突 | OFAC（制裁名单）、UN News | RSS |
| 金融 | Reuters、IMF、Fed、ECB、BIS、中国新闻网 | RSS |
| 综合 | 金十数据（channel 1/2/3/5，支持 important 标记） | HTTP JS |

## 金十数据特性

- `channel 1` = 全球宏观 → financial
- `channel 2` = 原油/商品 → financial
- `channel 3` = 综合快讯 → 规则引擎再判
- `channel 5` = 外文快讯 → 优先 conflict/tariff
- `important=1` → severity 预标注为 medium（至少）
- 过滤 `type=2`（行情价格数据）

## 用法

```bash
# 全量采集（48小时），保存到数据库
python risk_intel_collector.py --hours 48 --save

# 仅关税域 + 米塔关键词
python risk_intel_collector.py --domains tariff --keyword "美国加征关税" --save

# 仅金十重要新闻
python risk_intel_collector.py --important-only

# JSON stdin（Agent调用）
echo '{"hours":24,"domains":["conflict"],"save":true}' | python risk_intel_collector.py --stdin
```
