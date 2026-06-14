"""风险情报 LLM 分析器 — 网关版。

通过 LLMGateway（glm-5.1）统一调用，不再持有自己的 OpenAI 客户端。
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
你是资深跨境电商合规风险分析师。分析新闻，从卖家视角输出 JSON 风险评估：
{
  "headline_summary": "≤25字核心事件",
  "risk_domain": "tariff|conflict|financial|null",
  "risk_category": "二级分类",
  "risk_score": 0.00,
  "severity": "critical|high|medium|low",
  "affected_markets": ["ISO代码"],
  "affected_hs_codes": ["4位HS编码，不确定则[]"],
  "summary": "≤80字事件概述",
  "impact": "≤60字对跨境卖家影响",
  "actions": ["≤3条具体行动，每条≤20字"],
  "confidence": 0.00
}
risk_domain 标准：tariff=关税/制裁/出口管制，conflict=战争/地缘/政治，financial=利率/汇率/大宗商品，null=无关。
risk_score: 0.8+极高/立即行动，0.6-0.8高危，0.35-0.6中危，<0.35背景信息。
JSON 无 Markdown 包裹，所有字段必须存在。"""


def _score_to_severity(score: float) -> str:
    if score >= 0.8:  return "critical"
    if score >= 0.6:  return "high"
    if score >= 0.35: return "medium"
    return "low"


# ─────────────────────────────────────────────────────────────────────────────
# 分析器主类
# ─────────────────────────────────────────────────────────────────────────────

class RiskIntelAnalyzer:
    """风险情报 LLM 分析器（通过 LLMGateway 调用 glm-5.1）。"""

    @property
    def available(self) -> bool:
        from app.core.llm_gateway import get_llm_gateway
        return get_llm_gateway().available("risk_analysis")

    async def analyze_item(self, item: dict, retry: int = 2) -> dict:
        """分析单条情报，失败时降级规则引擎。"""
        from app.core.llm_gateway import get_llm_gateway
        gw = get_llm_gateway()

        content = (item.get("summary") or item.get("title") or "")[:1500]
        user_msg = (
            f"来源：{item.get('source_name','未知')}\n"
            f"时间：{(item.get('pub_time') or item.get('collected_at') or '')[:19]}\n"
            f"标题：{item.get('title','')[:250]}\n"
            f"内容：{content}"
        )

        result = await gw.chat_json(_SYSTEM_PROMPT, user_msg, role="risk_analysis", retry=retry)
        if result:
            return self._validate(result, item)

        return self._rule_fallback(item)

    async def analyze_batch(
        self,
        items: list[dict],
        on_done: Optional[callable] = None,
    ) -> list[tuple[dict, dict]]:
        """并发分析多条情报。"""
        import asyncio
        if not items:
            return []

        async def _one(item: dict) -> tuple[dict, dict]:
            result = await self.analyze_item(item)
            if on_done:
                try:
                    await on_done(item, result)
                except Exception as e:
                    logger.warning("[RiskIntelAnalyzer] on_done 失败: %s", e)
            return item, result

        pairs = await asyncio.gather(*[_one(i) for i in items], return_exceptions=True)
        return [(p[0], p[1]) for p in pairs if not isinstance(p, Exception)]

    def _validate(self, result: dict, item: dict) -> dict:
        defaults = {
            "headline_summary": (item.get("headline_summary") or item.get("title",""))[:25],
            "risk_domain":      item.get("risk_domain"),
            "risk_category":    item.get("risk_category"),
            "risk_score":       float(item.get("risk_score", 0.3)),
            "severity":         item.get("severity","low"),
            "affected_markets": item.get("affected_markets",[]),
            "affected_hs_codes":item.get("affected_hs_codes",[]),
            "summary": "", "impact": "", "actions": [], "confidence": 0.5,
        }
        for k, v in defaults.items():
            if k not in result or result[k] is None:
                result[k] = v
        result["risk_score"]  = round(float(result.get("risk_score", 0.3)), 2)
        result["confidence"]  = round(float(result.get("confidence", 0.5)), 2)
        result["severity"]    = _score_to_severity(result["risk_score"])
        if not isinstance(result.get("affected_markets"), list):  result["affected_markets"] = []
        if not isinstance(result.get("affected_hs_codes"), list): result["affected_hs_codes"] = []
        if not isinstance(result.get("actions"), list):           result["actions"] = []
        result["headline_summary"] = str(result.get("headline_summary",""))[:60]
        result["summary"]          = str(result.get("summary",""))[:300]
        result["impact"]           = str(result.get("impact",""))[:200]
        result["actions"]          = [str(a)[:50] for a in result["actions"][:3]]
        return result

    def _rule_fallback(self, item: dict) -> dict:
        title = item.get("title","")
        text  = (f"{title} {item.get('summary','') or ''}").lower()
        score = float(item.get("risk_score", 0.3))
        domain = item.get("risk_domain")
        category = item.get("risk_category")
        _HIGH = [
            ("sanction","tariff","sanctions"), ("制裁","tariff","sanctions"),
            ("tariff","tariff","trade_war"),   ("关税","tariff","trade_war"),
            ("anti-dumping","tariff","trade_war"), ("entity list","tariff","export_control"),
            ("出口管制","tariff","export_control"), ("稀土","conflict","export_control"),
            ("war","conflict","military"),      ("战争","conflict","military"),
            ("airstrike","conflict","military"),("空袭","conflict","military"),
            ("rate hike","financial","interest_rate"), ("加息","financial","interest_rate"),
            ("exchange rate","financial","exchange_rate"), ("汇率","financial","exchange_rate"),
            ("inflation","financial","inflation"), ("通胀","financial","inflation"),
            ("oil price","financial","commodity"), ("油价","financial","commodity"),
        ]
        domain_scores: dict[str, int] = {}
        domain_cats:   dict[str, str] = {}
        for kw, d, c in _HIGH:
            if kw in text:
                domain_scores[d] = domain_scores.get(d, 0) + 1
                if d not in domain_cats: domain_cats[d] = c
        if domain_scores:
            best = max(domain_scores, key=lambda k: domain_scores[k])
            domain = domain or best; category = category or domain_cats.get(best,""); score = max(score, 0.6)
        return {
            "headline_summary": (title[:25]+"…") if len(title)>25 else title,
            "risk_domain": domain, "risk_category": category,
            "risk_score": round(min(score,1.0),2),
            "severity": _score_to_severity(score),
            "affected_markets": item.get("affected_markets",[]),
            "affected_hs_codes": item.get("affected_hs_codes",[]),
            "summary": title[:80], "impact": "（规则引擎评估）", "actions": [], "confidence": 0.35,
            "_model": "rules_fallback",
        }


_analyzer: Optional[RiskIntelAnalyzer] = None

def get_risk_intel_analyzer() -> RiskIntelAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = RiskIntelAnalyzer()
    return _analyzer
