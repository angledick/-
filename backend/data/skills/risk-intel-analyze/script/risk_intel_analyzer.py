#!/usr/bin/env python3
"""风险情报分析器 — 两阶段处理（规则引擎 + LLM 精确分析）。

阶段 1（规则引擎）：无需 LLM，基于关键词字典做基础打分
  - 域 / 分类由采集器预标注，此处补充打分
  - 信源权重 × 关键词密度 → base_score
  - Jin10 important=1 → 强制 severity >= medium

阶段 2（LLM 精确分析）：批量调用 LLM，输出完整字段
  - 输出：risk_score(0-1), affected_markets, affected_hs_codes, headline_summary
  - 无 LLM Key 时仅使用阶段 1 结果（置信度标注 [规则引擎]）

用法：
  # 分析数据库中未分析的条目
  python risk_intel_analyzer.py --limit 30 --save

  # 仅规则引擎（跳过 LLM）
  python risk_intel_analyzer.py --rules-only --limit 50 --save

  # 分析指定条目列表（JSON stdin）
  echo '{"items": [...], "save": true}' | python risk_intel_analyzer.py --stdin
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")

# 确保能导入 app.*
_BACKEND_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_BACKEND_ROOT))

# ─────────────────────────────────────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────────────────────────────────────

# 信源权重（与采集器保持一致）
SOURCE_WEIGHTS: dict[str, float] = {
    "ustr": 1.0, "ofac": 1.0, "cbp": 0.9, "eu_official": 0.9,
    "wto": 0.9, "imf": 0.9, "fed": 0.9, "ecb": 0.9, "bis": 0.9,
    "un_news": 0.8, "reuters_top": 0.8, "reuters_biz": 0.8,
    "china_customs": 0.8, "jin10": 0.7, "chinanews": 0.6,
    "metaso": 0.5, "default": 0.3,
}

# 风险分 → 严重度映射
def _score_to_severity(score: float) -> str:
    if score >= 0.8:
        return "critical"
    elif score >= 0.6:
        return "high"
    elif score >= 0.35:
        return "medium"
    else:
        return "low"

# 高密度风险关键词列表（出现即大幅提分）
_HIGH_RISK_KEYWORDS = [
    "sanction", "制裁", "embargo", "禁令",
    "tariff increase", "关税上调", "加征关税",
    "export ban", "出口禁止", "entity list", "实体清单",
    "war", "战争", "military conflict", "武装冲突",
    "market crash", "市场崩盘", "circuit breaker", "熔断",
    "default", "违约", "debt crisis", "债务危机",
    "rate hike", "加息", "rate cut", "降息",
    "currency collapse", "货币崩溃",
    "supply chain disruption", "供应链中断",
    "invasion", "入侵", "coup", "政变",
]

_MEDIUM_RISK_KEYWORDS = [
    "tariff", "关税", "trade restriction", "贸易限制",
    "regulation change", "法规变更", "compliance requirement", "合规要求",
    "inflation", "通胀", "depreciation", "贬值",
    "geopolit", "地缘政治", "political tension", "政治紧张",
    "import duty", "进口关税", "export control", "出口管制",
    "volatility", "波动",
]

# HS 编码关键词映射（可扩展）
_HS_KEYWORD_MAP: dict[str, list[str]] = {
    "8471": ["computer", "laptop", "笔记本", "电脑", "computing"],
    "8517": ["phone", "smartphone", "手机", "mobile", "5g"],
    "8543": ["electronic", "circuit", "电子", "芯片", "semiconductor"],
    "9405": ["led", "lighting", "灯", "light", "lamp"],
    "6203": ["clothing", "apparel", "服装", "garment", "textile"],
    "6403": ["shoe", "footwear", "鞋", "boot"],
    "9503": ["toy", "玩具", "game"],
    "8528": ["television", "monitor", "tv", "显示器"],
    "8708": ["auto part", "汽车零部件", "vehicle", "car part"],
    "3004": ["medicine", "pharmaceutical", "药", "medical"],
}

# 市场关键词映射
_MARKET_KEYWORD_MAP: dict[str, list[str]] = {
    "US": ["united states", "u.s.", "us ", "american", "america", "美国", "华盛顿", "白宫"],
    "EU": ["european", "europe", "eu ", "欧盟", "欧洲", "brussels", "布鲁塞尔"],
    "CN": ["china", "chinese", "中国", "北京", "beijing", "prc"],
    "DE": ["german", "germany", "德国", "deutsche", "柏林"],
    "UK": ["britain", "british", "uk ", "united kingdom", "英国", "london"],
    "JP": ["japan", "japanese", "日本", "tokyo", "东京"],
    "KR": ["korea", "korean", "韩国", "首尔", "seoul"],
    "FR": ["france", "french", "法国", "paris", "巴黎"],
    "RU": ["russia", "russian", "俄罗斯", "moscow", "克里姆林"],
    "IR": ["iran", "iranian", "伊朗", "tehran", "德黑兰"],
    "UA": ["ukraine", "ukrainian", "乌克兰", "kyiv", "基辅"],
    "SA": ["saudi", "arabia", "沙特", "riyadh"],
    "IN": ["india", "indian", "印度", "modi"],
    "GLOBAL": ["global", "worldwide", "international", "全球", "国际"],
}


# ─────────────────────────────────────────────────────────────────────────────
# 阶段 1：规则引擎分析
# ─────────────────────────────────────────────────────────────────────────────

def rule_engine_analyze(item: dict) -> dict:
    """纯规则引擎分析，无需 LLM。

    输入：risk_intel_item（或类似结构）
    输出：enriched dict，新增 risk_score / severity / affected_markets /
          affected_hs_codes / headline_summary（简单截取）
    """
    text = f"{item.get('title', '')} {item.get('summary', '') or ''}"
    text_lower = text.lower()

    # ── 基础分：信源权重 ───────────────────────────────────────
    source = item.get("source_name", "default")
    base_score = SOURCE_WEIGHTS.get(source, SOURCE_WEIGHTS["default"])

    # ── 高风险关键词命中（每命中一个加 0.15）───────────────────
    high_hits = sum(1 for kw in _HIGH_RISK_KEYWORDS if kw.lower() in text_lower)
    medium_hits = sum(1 for kw in _MEDIUM_RISK_KEYWORDS if kw.lower() in text_lower)

    # 公式：base_score × 0.4 + high命中 × 0.15 + medium命中 × 0.05
    computed = base_score * 0.4 + high_hits * 0.15 + medium_hits * 0.05

    # Jin10 important=1：至少 0.45（保证 medium 严重度）
    if item.get("jin10_important", 0) == 1:
        computed = max(computed, 0.45)

    # OFAC 制裁条目：直接设 0.75
    if item.get("source_name") == "ofac":
        computed = max(computed, 0.75)

    risk_score = round(min(computed, 1.0), 3)
    severity = _score_to_severity(risk_score)

    # ── 市场检测 ──────────────────────────────────────────────
    affected_markets = []
    for market, keywords in _MARKET_KEYWORD_MAP.items():
        if any(kw.lower() in text_lower for kw in keywords):
            if market not in affected_markets:
                affected_markets.append(market)

    # ── HS 编码关联 ────────────────────────────────────────────
    affected_hs_codes = []
    for hs, keywords in _HS_KEYWORD_MAP.items():
        if any(kw.lower() in text_lower for kw in keywords):
            if hs not in affected_hs_codes:
                affected_hs_codes.append(hs)

    # ── 简单摘要（截取标题首 50 字）─────────────────────────────
    title = item.get("title", "")
    headline_summary = title[:50] if len(title) > 50 else title

    return {
        **item,
        "risk_score": risk_score,
        "severity": severity,
        "affected_markets": affected_markets,
        "affected_hs_codes": affected_hs_codes,
        "headline_summary": headline_summary,
        "analyzed": 1,
        "_analysis_method": "rules",
    }


# ─────────────────────────────────────────────────────────────────────────────
# LLM 配置
# ─────────────────────────────────────────────────────────────────────────────

def _get_llm_config() -> tuple[str, str, str]:
    """获取 LLM 配置，多级回退。"""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("LLM_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.environ.get("LLM_MODEL", "anthropic/claude-haiku-4-5")

    if not api_key:
        try:
            from app.config import settings
            api_key = settings.anthropic_api_key
        except Exception:
            pass

    if not api_key:
        env_file = _BACKEND_ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k == "ANTHROPIC_API_KEY" and not api_key:
                    api_key = v
                elif k == "LLM_API_KEY" and not api_key:
                    api_key = v
                elif k == "LLM_BASE_URL" and v:
                    base_url = v
                elif k == "LLM_MODEL" and v:
                    model = v

    return api_key, base_url, model


_LLM_SYSTEM_PROMPT = """\
你是一名跨境电商合规风险分析师。分析给定的新闻，输出 JSON 格式的风险评估。

**风险域（risk_domain）必须为以下之一：**
- "tariff"    关税、贸易限制、出口管制、制裁、原产地规则、进口关税
- "conflict"  战争、地缘政治冲突、政治动荡、恐怖主义
- "financial" 利率变动、汇率波动、通胀、信用风险、市场崩盘、大宗商品
- null        与跨境电商合规无关

**风险分类（risk_category）参考值（可自由填写，不限于此）：**
tariff: trade_war / import_duty / export_control / sanctions / rules_of_origin / eu_regulation
conflict: military / geopolitics / political_risk / terrorism
financial: interest_rate / exchange_rate / inflation / credit_risk / market_crash / commodity

**风险评分（risk_score）0.0~1.0：**
- 0.0~0.3: 低，背景信息
- 0.3~0.6: 中，需关注
- 0.6~0.8: 高，需预警
- 0.8~1.0: 极高，立即行动

**affected_markets** 使用 ISO 两字母代码：US, EU, CN, DE, UK, JP, KR, FR, IN, GLOBAL 等

**affected_hs_codes** 仅填写可明确关联的 4 位 HS 编码，无法确定则留空数组

**headline_summary** ≤30字的中文摘要，概括核心事件（不含引号）

必须输出标准 JSON，不含 Markdown 代码块，所有字段必须存在。
"""

_LLM_USER_TEMPLATE = """\
来源：{source_name}
时间：{pub_time}
标题：{title}
摘要：{summary}
"""

_LLM_EXPECTED_KEYS = {
    "risk_domain", "risk_category", "risk_score",
    "affected_markets", "affected_hs_codes", "headline_summary",
}


def _llm_analyze_single(item: dict, client, model: str) -> Optional[dict]:
    """单条 LLM 分析，失败返回 None。"""
    user_prompt = _LLM_USER_TEMPLATE.format(
        source_name=item.get("source_name", "unknown"),
        pub_time=item.get("pub_time", ""),
        title=item.get("title", "")[:200],
        summary=(item.get("summary") or "")[:400],
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _LLM_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_completion_tokens=300,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        result = json.loads(raw)

        # 字段验证：缺失字段用默认值补全
        if not isinstance(result.get("affected_markets"), list):
            result["affected_markets"] = []
        if not isinstance(result.get("affected_hs_codes"), list):
            result["affected_hs_codes"] = []
        if not isinstance(result.get("risk_score"), (int, float)):
            result["risk_score"] = 0.3
        if "risk_domain" not in result:
            result["risk_domain"] = None
        result["risk_score"] = round(float(result["risk_score"]), 3)
        result["severity"] = _score_to_severity(result["risk_score"])
        return result

    except Exception as e:
        log.warning("[llm] 分析失败 id=%s: %s", item.get("id", "?")[:8], e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 阶段 2：LLM 批量分析
# ─────────────────────────────────────────────────────────────────────────────

def llm_batch_analyze(
    items: list[dict],
    save: bool = False,
    batch_size: int = 10,
    delay: float = 0.5,
) -> list[dict]:
    """LLM 批量分析（流水线：先规则引擎，再 LLM 精化）。

    Args:
        items:      待分析条目列表
        save:       是否将结果回写数据库
        batch_size: 每批次条目数（控制并发）
        delay:      批次间延迟（秒）

    Returns:
        enriched items 列表
    """
    api_key, base_url, model = _get_llm_config()

    if not api_key:
        log.warning("[analyzer] LLM API Key 未配置，降级为纯规则引擎")
        results = [rule_engine_analyze(item) for item in items]
        if save:
            _save_results(results)
        return results

    try:
        from openai import OpenAI
        client = OpenAI(base_url=base_url, api_key=api_key)
    except ImportError:
        log.warning("[analyzer] openai 包未安装，降级为规则引擎")
        results = [rule_engine_analyze(item) for item in items]
        if save:
            _save_results(results)
        return results

    results = []
    total = len(items)

    for i in range(0, total, batch_size):
        batch = items[i: i + batch_size]
        log.info("[analyzer] 处理批次 %d/%d，共 %d 条", i // batch_size + 1,
                 (total + batch_size - 1) // batch_size, len(batch))

        for item in batch:
            # 先用规则引擎做基础分析
            enriched = rule_engine_analyze(item)

            # 再用 LLM 精化
            llm_result = _llm_analyze_single(enriched, client, model)
            if llm_result:
                # LLM 结果覆盖关键字段
                enriched["risk_domain"] = llm_result.get("risk_domain") or enriched.get("risk_domain")
                enriched["risk_category"] = llm_result.get("risk_category") or enriched.get("risk_category")
                enriched["risk_score"] = llm_result["risk_score"]
                enriched["severity"] = llm_result["severity"]
                enriched["affected_markets"] = (
                    llm_result["affected_markets"] or enriched["affected_markets"]
                )
                enriched["affected_hs_codes"] = (
                    llm_result["affected_hs_codes"] or enriched["affected_hs_codes"]
                )
                enriched["headline_summary"] = llm_result.get("headline_summary", enriched["headline_summary"])
                enriched["_analysis_method"] = "llm"

            results.append(enriched)

        if i + batch_size < total:
            time.sleep(delay)

    if save:
        _save_results(results)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# 数据库写回
# ─────────────────────────────────────────────────────────────────────────────

def _save_results(results: list[dict]) -> int:
    """将分析结果回写 risk_intel_store。"""
    try:
        from app.storage.risk_intel_store import update_item_analysis
        saved = 0
        for r in results:
            if r.get("id"):
                ok = update_item_analysis(r["id"], r)
                if ok:
                    saved += 1
        log.info("[analyzer] 回写数据库: %d/%d 条成功", saved, len(results))
        return saved
    except ImportError:
        log.warning("[analyzer] 无法导入 risk_intel_store，未回写")
        return 0


def analyze_from_db(limit: int = 30, rules_only: bool = False, save: bool = True) -> dict:
    """从数据库拉取未分析条目，批量分析并回写。"""
    try:
        from app.storage.risk_intel_store import get_unanalyzed_items
        items = get_unanalyzed_items(limit)
    except ImportError:
        log.error("[analyzer] 无法导入存储层")
        return {"error": "无法导入存储层", "analyzed": 0}

    if not items:
        log.info("[analyzer] 无待分析条目")
        return {"analyzed": 0, "items": []}

    log.info("[analyzer] 拉取到 %d 条未分析条目", len(items))

    if rules_only:
        results = [rule_engine_analyze(item) for item in items]
        if save:
            _save_results(results)
    else:
        results = llm_batch_analyze(items, save=save)

    # 统计
    high_count = sum(1 for r in results if r.get("severity") in ("high", "critical"))
    return {
        "analyzed": len(results),
        "high_risk": high_count,
        "method": "rules" if rules_only else "llm",
        "items": results,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="风险情报分析器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 分析数据库中前 30 条未分析条目（含 LLM）
  python risk_intel_analyzer.py --limit 30 --save

  # 纯规则引擎（快速，无 LLM）
  python risk_intel_analyzer.py --rules-only --limit 100 --save

  # JSON stdin 模式（接收条目列表直接分析，不查数据库）
  echo '{"items": [...], "save": true}' | python risk_intel_analyzer.py --stdin
        """,
    )
    parser.add_argument("--limit", type=int, default=30, help="最多分析条数")
    parser.add_argument("--rules-only", action="store_true", help="仅规则引擎，不调用 LLM")
    parser.add_argument("--save", action="store_true", help="回写数据库")
    parser.add_argument("--pretty", action="store_true", help="美化 JSON 输出")
    parser.add_argument("--stdin", action="store_true", help="从 stdin 读取 JSON（含 items 列表）")

    args = parser.parse_args()

    if args.stdin:
        try:
            cfg = json.loads(sys.stdin.read())
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"stdin JSON 解析失败: {e}"}, ensure_ascii=False))
            sys.exit(1)
        items = cfg.get("items", [])
        save = cfg.get("save", False)
        rules_only = cfg.get("rules_only", False)
        if rules_only:
            results = [rule_engine_analyze(i) for i in items]
            if save:
                _save_results(results)
            out = {"analyzed": len(results), "method": "rules", "items": results}
        else:
            out = {"analyzed": len(items),
                   "items": llm_batch_analyze(items, save=save)}
    else:
        out = analyze_from_db(
            limit=args.limit,
            rules_only=args.rules_only,
            save=args.save,
        )

    indent = 2 if args.pretty else None
    # 输出：去掉超大字段，保留分析结果
    output_items = []
    for item in out.get("items", []):
        output_items.append({
            k: v for k, v in item.items()
            if k not in ("summary",)  # summary 可能很长
        })
    out["items"] = output_items[:50]  # 最多输出 50 条
    print(json.dumps(out, ensure_ascii=False, indent=indent))


if __name__ == "__main__":
    main()
