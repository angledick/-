---
skill_id: risk-intel-analyze
name: 风险情报分析
description: 两阶段（规则引擎+LLM）分析风险情报，输出三级分类/风险分/市场/HS编码
version: "1.0"
author: system
category: risk
stage: all
enabled: true
script: script/risk_intel_analyzer.py
execution_mode: subprocess
timeout: 300
dependencies:
  - openai
env_vars:
  - ANTHROPIC_API_KEY
  - LLM_API_KEY
  - LLM_BASE_URL
  - LLM_MODEL
inputs:
  - name: limit
    type: integer
    default: 30
    description: 最多分析条数
  - name: rules_only
    type: boolean
    default: false
    description: 仅规则引擎（跳过LLM）
  - name: save
    type: boolean
    default: false
    description: 是否回写数据库
outputs:
  - name: analyzed
    type: integer
    description: 分析条数
  - name: high_risk
    type: integer
    description: 高风险条数
  - name: items
    type: array
    description: 分析结果列表
---

# 风险情报分析 Skill

## 两阶段处理

### 阶段 1：规则引擎（无 LLM，毫秒级）

- 信源权重 × 关键词密度 → `risk_score`
- 高风险关键词（制裁/战争/加息）命中加分
- 市场检测（20+ 市场关键词字典）
- HS 编码关联（10 个品类）
- Jin10 `important=1` → 强制 score ≥ 0.45
- OFAC 制裁来源 → 直接 score = 0.75

### 阶段 2：LLM 精确分析（可选）

- 输入：阶段1结果 + 原文
- 输出精化：`risk_domain/risk_category/risk_score/affected_markets/affected_hs_codes/headline_summary`
- LLM Key 未配置时自动降级为纯规则引擎

## 严重度映射

| risk_score | severity |
|-----------|----------|
| ≥ 0.8 | critical |
| ≥ 0.6 | high |
| ≥ 0.35 | medium |
| < 0.35 | low |

## 用法

```bash
# 分析数据库中前30条未分析条目（含LLM）
python risk_intel_analyzer.py --limit 30 --save

# 纯规则引擎（快速）
python risk_intel_analyzer.py --rules-only --limit 100 --save

# JSON stdin（直接分析给定条目列表）
echo '{"items":[...],"save":true}' | python risk_intel_analyzer.py --stdin
```
