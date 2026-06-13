"""风险情报 LLM 分析器 — 内联版。

Provider 优先链：
  1. routes.yaml[risk_analysis] → 读取 provider/model/base_url/api_key_env
  2. 环境变量 ZHIPUAI_API_KEY + ZHIPUAI_BASE_URL + ZHIPUAI_MODEL
  3. 环境变量 ANTHROPIC_API_KEY（Anthropic SDK）
  4. 规则引擎 fallback（无 LLM 时）

目前默认 provider = zhipu (glm-5.1，推理模型)
  - 每条消耗 ~700 reasoning + ~150 output token
  - max_tokens 必须 ≥ 2000 以容纳推理预算

单例访问：get_risk_intel_analyzer()
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
你是一名资深跨境电商合规顾问，专注于全球贸易风险分析。

任务：分析一条全球新闻，从跨境电商卖家视角输出结构化风险评估。

## 输出格式（严格 JSON，无 Markdown 包裹，所有字段必须存在）

{
  "headline_summary": "≤25字的核心事件摘要",
  "risk_domain": "tariff 或 conflict 或 financial 或 null",
  "risk_category": "二级分类",
  "risk_score": 0.00,
  "severity": "critical 或 high 或 medium 或 low",
  "affected_markets": ["ISO两字母代码"],
  "affected_hs_codes": ["4位HS编码，无法确定则[]"],
  "summary": "≤80字的事件概述：发生了什么、关键数字",
  "impact": "≤60字的影响：对跨境卖家的直接影响",
  "actions": ["≤3条具体行动，每条≤20字"],
  "confidence": 0.00
}

## risk_domain 判断
- tariff：关税变动、贸易制裁、出口管制、实体清单、反倾销
- conflict：军事冲突、地缘政治、制裁名单更新、政治动荡
- financial：利率决策、汇率波动、通胀数据、市场崩盘、大宗商品
- null：与跨境贸易无关

## risk_score 量化
- 0.80–1.00：已生效政策，直接影响跨境出口，立即行动
- 0.60–0.79：确定性强的政策信号，需提前应对
- 0.35–0.59：政策讨论/提案阶段，或影响间接
- 0.00–0.34：背景信息，影响轻微

## 注意
- risk_score 使用两位小数
- confidence 反映分析确定性（信息充分=0.9，信息模糊=0.5）
- actions 必须具体可执行，不写套话
- 若与跨境无关：risk_domain=null, risk_score=0.05, severity=low, actions=[]
"""

_USER_TEMPLATE = """\
请分析以下新闻：

【来源】{source_name}
【时间】{pub_time}
【标题】{title}
【内容】{content}
"""

# ─────────────────────────────────────────────────────────────────────────────
# 配置读取
# ─────────────────────────────────────────────────────────────────────────────

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _read_env_file() -> dict[str, str]:
    """解析 .env 文件，返回 key→value 字典。"""
    result: dict[str, str] = {}
    if not _ENV_FILE.exists():
        return result
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        result[k.strip()] = v.strip().strip('"').strip("'")
    return result


def _get_env(key: str, default: str = "") -> str:
    """优先 os.environ，回退 .env 文件。"""
    val = os.environ.get(key, "")
    if val:
        return val
    return _read_env_file().get(key, default)


def _get_route_config() -> dict:
    """从 routes.yaml 读取 risk_analysis 路由配置。"""
    try:
        import yaml
        from app.config import settings
        from pathlib import Path as P
        routes_file = P(settings.data_dir) / "models" / "routes.yaml"
        if routes_file.exists():
            data = yaml.safe_load(routes_file.read_text(encoding="utf-8"))
            return data.get("routes", {}).get("risk_analysis", {})
    except Exception:
        pass
    return {}


def _get_llm_config() -> tuple[str, str, str, str]:
    """返回 (provider, api_key, base_url, model)。

    优先链：routes.yaml[risk_analysis] → ZHIPUAI_* 环境变量 → ANTHROPIC_API_KEY
    """
    route = _get_route_config()
    provider = route.get("provider", "")
    api_key_env = route.get("api_key_env", "")
    base_url = route.get("base_url", "")
    model = route.get("model", "")

    # 从路由指定的环境变量获取 key
    api_key = _get_env(api_key_env) if api_key_env else ""

    # 如果路由配置已完整，直接返回
    if provider and api_key and model:
        return provider, api_key, base_url, model

    # 回退：ZhipuAI 环境变量
    zkey = _get_env("ZHIPUAI_API_KEY")
    if zkey:
        return (
            "zhipu",
            zkey,
            _get_env("ZHIPUAI_BASE_URL", "https://open.bigmodel.cn/api/coding/paas/v4"),
            _get_env("ZHIPUAI_MODEL", "glm-5.1"),
        )

    # 回退：Anthropic
    akey = _get_env("ANTHROPIC_API_KEY")
    if akey:
        return "anthropic", akey, "", _get_env("LLM_MODEL", "claude-haiku-4-5-20251001")

    return "none", "", "", ""


def _max_tokens(route: dict) -> int:
    """读取路由配置的 max_tokens，glm-5.1 至少 2000。"""
    val = route.get("max_tokens", 2000)
    return max(int(val), 2000)


def _score_to_severity(score: float) -> str:
    if score >= 0.8:  return "critical"
    if score >= 0.6:  return "high"
    if score >= 0.35: return "medium"
    return "low"


# ─────────────────────────────────────────────────────────────────────────────
# 分析器主类
# ─────────────────────────────────────────────────────────────────────────────

class RiskIntelAnalyzer:
    """风险情报 LLM 分析器（支持 ZhipuAI / Anthropic / 规则兜底）。"""

    def __init__(self):
        self._provider: Optional[str] = None
        self._api_key: Optional[str] = None
        self._base_url: Optional[str] = None
        self._model: Optional[str] = None
        self._openai_client = None    # AsyncOpenAI（zhipu / openai provider）
        self._anthropic_client = None # AsyncAnthropic（anthropic provider）
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._initialized = False

    # ── 惰性初始化 ────────────────────────────────────────────────────────────

    def _init(self) -> bool:
        if self._initialized:
            return self._provider not in (None, "none")

        provider, api_key, base_url, model = _get_llm_config()
        self._provider = provider
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._initialized = True

        if provider == "none" or not api_key:
            logger.warning("[RiskIntelAnalyzer] 未找到可用 LLM 配置，降级为规则引擎")
            return False

        self._semaphore = asyncio.Semaphore(4)  # 最多 4 个并发（推理模型延迟高）

        if provider in ("zhipu", "openai"):
            try:
                from openai import AsyncOpenAI
                self._openai_client = AsyncOpenAI(
                    api_key=api_key,
                    base_url=base_url or None,
                )
                logger.info("[RiskIntelAnalyzer] provider=%s model=%s base_url=%s",
                            provider, model, base_url or "(default)")
                return True
            except ImportError:
                logger.error("[RiskIntelAnalyzer] openai 包未安装")
                return False

        if provider == "anthropic":
            try:
                import anthropic
                self._anthropic_client = anthropic.AsyncAnthropic(
                    api_key=api_key,
                    base_url=base_url or None,
                )
                logger.info("[RiskIntelAnalyzer] provider=anthropic model=%s", model)
                return True
            except ImportError:
                logger.error("[RiskIntelAnalyzer] anthropic 包未安装")
                return False

        logger.warning("[RiskIntelAnalyzer] 未知 provider: %s", provider)
        return False

    @property
    def available(self) -> bool:
        """是否有可用的 LLM 配置（懒检查）。"""
        provider, api_key, _, _ = _get_llm_config()
        return provider not in ("none", "") and bool(api_key)

    # ── 单条分析 ──────────────────────────────────────────────────────────────

    async def analyze_item(self, item: dict, retry: int = 2) -> dict:
        """对单条情报执行 LLM 分析，失败时返回规则兜底结果。"""
        if not self._init():
            return self._rule_fallback(item)

        content = (item.get("summary") or item.get("title") or "")[:1500]
        user_msg = _USER_TEMPLATE.format(
            source_name=item.get("source_name", "未知"),
            pub_time=(item.get("pub_time") or item.get("collected_at") or "")[:19],
            title=item.get("title", "")[:250],
            content=content,
        )

        route = _get_route_config()
        max_tok = _max_tokens(route)

        for attempt in range(retry + 1):
            try:
                raw = await self._call_llm(user_msg, max_tok)
                result = self._parse_json(raw)
                if result:
                    return self._validate(result, item)
                # JSON 解析失败，重试
            except Exception as e:
                err = str(e)
                if "rate_limit" in err.lower() or "429" in err:
                    wait = 15 * (attempt + 1)
                    logger.warning("[Analyzer] 限流，等待 %ds id=%s",
                                   wait, item.get("id", "?")[:8])
                    await asyncio.sleep(wait)
                elif attempt < retry:
                    await asyncio.sleep(2.0 * (attempt + 1))
                else:
                    logger.error("[Analyzer] 分析失败 id=%s: %s",
                                 item.get("id", "?")[:8], e)
                    return {**self._rule_fallback(item), "error": err,
                            "_model": self._model or ""}

        logger.warning("[Analyzer] 重试耗尽 id=%s", item.get("id", "?")[:8])
        return {**self._rule_fallback(item), "_model": self._model or ""}

    async def _call_llm(self, user_msg: str, max_tokens: int) -> str:
        """调用 LLM，返回原始文本（在 semaphore 内执行）。"""
        async with self._semaphore:
            if self._openai_client:
                resp = await self._openai_client.chat.completions.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    temperature=0.1,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user",   "content": user_msg},
                    ],
                )
                return resp.choices[0].message.content or ""

            if self._anthropic_client:
                resp = await self._anthropic_client.messages.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    temperature=0.1,
                    system=_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_msg}],
                )
                return resp.content[0].text or ""

        return ""

    # ── 批量分析 ──────────────────────────────────────────────────────────────

    async def analyze_batch(
        self,
        items: list[dict],
        on_done: Optional[callable] = None,
    ) -> list[tuple[dict, dict]]:
        """并发分析多条情报，每条完成后回调 on_done(item, result)。"""
        if not items:
            return []

        async def _one(item: dict) -> tuple[dict, dict]:
            result = await self.analyze_item(item)
            result["_model"] = result.get("_model") or self._model or ""
            if on_done:
                try:
                    await on_done(item, result)
                except Exception as e:
                    logger.warning("[Analyzer] on_done 失败: %s", e)
            return item, result

        pairs = await asyncio.gather(*[_one(i) for i in items],
                                     return_exceptions=True)
        output = []
        for pair in pairs:
            if isinstance(pair, Exception):
                logger.warning("[Analyzer] gather 异常: %s", pair)
            else:
                output.append(pair)
        return output

    # ── JSON 解析 ─────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_json(raw: str) -> Optional[dict]:
        """解析 LLM 输出的 JSON，容忍 Markdown 代码块包裹。"""
        if not raw:
            return None
        # 去掉 ```json ... ``` 包裹
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 找第一个 { ... } 尝试解析
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except Exception:
                    pass
        return None

    # ── 结果校验 ──────────────────────────────────────────────────────────────

    def _validate(self, result: dict, item: dict) -> dict:
        """校验并补全 LLM 输出，确保所有必填字段存在。"""
        defaults = {
            "headline_summary": (item.get("headline_summary") or item.get("title", ""))[:25],
            "risk_domain":      item.get("risk_domain"),
            "risk_category":    item.get("risk_category"),
            "risk_score":       float(item.get("risk_score", 0.3)),
            "severity":         item.get("severity", "low"),
            "affected_markets": item.get("affected_markets", []),
            "affected_hs_codes":item.get("affected_hs_codes", []),
            "summary":          "",
            "impact":           "",
            "actions":          [],
            "confidence":       0.5,
            "_model":           self._model or "",
        }
        for k, v in defaults.items():
            if k not in result or result[k] is None:
                result[k] = v

        # 类型强制
        result["risk_score"]  = round(float(result.get("risk_score", 0.3)), 2)
        result["confidence"]  = round(float(result.get("confidence", 0.5)), 2)
        result["severity"]    = _score_to_severity(result["risk_score"])
        result["_model"]      = self._model or ""

        if not isinstance(result.get("affected_markets"), list):
            result["affected_markets"] = []
        if not isinstance(result.get("affected_hs_codes"), list):
            result["affected_hs_codes"] = []
        if not isinstance(result.get("actions"), list):
            result["actions"] = []

        # 截断过长字段
        result["headline_summary"] = str(result.get("headline_summary", ""))[:60]
        result["summary"]          = str(result.get("summary", ""))[:300]
        result["impact"]           = str(result.get("impact", ""))[:200]
        result["actions"]          = [str(a)[:50] for a in result["actions"][:3]]

        return result

    # ── 规则引擎兜底 ──────────────────────────────────────────────────────────

    def _rule_fallback(self, item: dict) -> dict:
        """LLM 不可用时的规则兜底。"""
        title = item.get("title", "")
        text  = (f"{title} {item.get('summary', '') or ''}").lower()
        score = float(item.get("risk_score", 0.3))
        domain   = item.get("risk_domain")
        category = item.get("risk_category")

        _HIGH = [
            # ── 关税域 ───────────────────────────────────────────
            ("sanction",      "tariff",   "sanctions"),
            ("制裁",           "tariff",   "sanctions"),
            ("tariff",        "tariff",   "trade_war"),
            ("关税",           "tariff",   "trade_war"),
            ("anti-dumping",  "tariff",   "trade_war"),
            ("反倾销",         "tariff",   "trade_war"),
            ("section 301",   "tariff",   "trade_war"),
            ("export ban",    "tariff",   "export_control"),
            ("entity list",   "tariff",   "export_control"),
            ("实体清单",        "tariff",   "export_control"),
            ("export control","tariff",   "export_control"),
            ("出口管制",        "tariff",   "export_control"),
            ("出口许可",        "tariff",   "export_control"),
            ("surtax",        "tariff",   "import_duty"),
            ("import duty",   "tariff",   "import_duty"),
            ("进口关税",        "tariff",   "import_duty"),
            ("usmca",         "tariff",   "rules_of_origin"),
            ("rules of origin","tariff",  "rules_of_origin"),
            ("原产地",         "tariff",   "rules_of_origin"),
            # ── 冲突域 ───────────────────────────────────────────
            ("war",           "conflict", "military"),
            ("战争",           "conflict", "military"),
            ("invasion",      "conflict", "military"),
            ("入侵",           "conflict", "military"),
            ("airstrike",     "conflict", "military"),
            ("空袭",           "conflict", "military"),
            ("military",      "conflict", "military"),
            ("稀土",           "conflict", "export_control"),
            ("rare earth",    "conflict", "export_control"),
            ("chip supplier", "conflict", "export_control"),
            ("ceasefire",     "conflict", "military"),
            ("停火",           "conflict", "military"),
            ("geopolit",      "conflict", "geopolitics"),
            ("地缘",           "conflict", "geopolitics"),
            # ── 金融域 ───────────────────────────────────────────
            ("rate hike",     "financial","interest_rate"),
            ("加息",           "financial","interest_rate"),
            ("interest rate", "financial","interest_rate"),
            ("利率",           "financial","interest_rate"),
            ("市场崩盘",        "financial","market_crash"),
            ("market crash",  "financial","market_crash"),
            ("exchange rate", "financial","exchange_rate"),
            ("汇率",           "financial","exchange_rate"),
            ("currency",      "financial","exchange_rate"),
            ("贬值",           "financial","exchange_rate"),
            ("depreciation",  "financial","exchange_rate"),
            ("steel price",   "financial","commodity"),
            ("钢铁",           "financial","commodity"),
            ("oil price",     "financial","commodity"),
            ("油价",           "financial","commodity"),
            ("inflation",     "financial","inflation"),
            ("通胀",           "financial","inflation"),
        ]
        # 收集所有命中，取信号最强的域（不 break，支持多信号叠加）
        # 注：text 已是 lower()，直接匹配
        _domain_scores: dict[str, float] = {}
        _domain_cats:   dict[str, str]   = {}
        for kw, d, c in _HIGH:
            if kw in text:
                _domain_scores[d] = _domain_scores.get(d, 0) + 1
                if d not in _domain_cats:
                    _domain_cats[d] = c
        if _domain_scores:
            best_d = max(_domain_scores, key=lambda k: _domain_scores[k])
            domain   = domain or best_d
            category = category or _domain_cats.get(best_d, "")
            score    = max(score, 0.6)

        return {
            "headline_summary": (title[:25] + "…") if len(title) > 25 else title,
            "risk_domain":      domain,
            "risk_category":    category,
            "risk_score":       round(min(score, 1.0), 2),
            "severity":         _score_to_severity(score),
            "affected_markets": item.get("affected_markets", []),
            "affected_hs_codes":item.get("affected_hs_codes", []),
            "summary":          title[:80],
            "impact":           "（LLM 不可用，使用规则引擎评估）",
            "actions":          [],
            "confidence":       0.35,
            "_model":           "rules_fallback",
        }


# ─────────────────────────────────────────────────────────────────────────────
# 单例
# ─────────────────────────────────────────────────────────────────────────────

_analyzer: Optional[RiskIntelAnalyzer] = None


def get_risk_intel_analyzer() -> RiskIntelAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = RiskIntelAnalyzer()
    return _analyzer
