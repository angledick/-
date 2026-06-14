#!/usr/bin/env python3
"""风险情报采集器 — 全球 15+ 信源，覆盖关税/战争/金融三大风险域。

信源清单：
  ── 关税域（tariff）──────────────────────────────────────────
  USTRCollector       美国贸易代表办公室 RSS                 ✅
  CBPCollector        美国海关边境保护局 RSS                 ✅
  EUOfficialCollector 欧盟官方公报 RSS                       ✅
  ChinaCustomsCollector 中国海关总署 HTTP                    ✅（降级可用）
  WTOCollector        世界贸易组织 RSS                       ✅
  ── 冲突域（conflict）───────────────────────────────────────
  OFACCollector       美国财政部制裁名单 RSS                 ✅
  UNNewsCollector     联合国新闻 RSS                        ✅
  ── 金融域（financial）──────────────────────────────────────
  ReutersTopCollector Reuters 头条 RSS                      ✅
  ReutersBizCollector Reuters 商业 RSS                      ✅
  IMFCollector        国际货币基金 RSS                       ✅
  FedCollector        美联储 RSS（原有，保留）                ✅
  ECBCollector        欧洲央行 RSS（原有，保留）              ✅
  BISCollector        国际清算银行 RSS（原有，保留）           ✅
  ── 综合快讯（mixed）────────────────────────────────────────
  Jin10Collector      金十数据 flash_newest（增强版）         ✅
    - channel 1 = 全球宏观 → financial
    - channel 2 = 原油/商品 → financial
    - channel 3 = 综合快讯 → mixed（由分析器再判）
    - channel 5 = 外文快讯 → conflict/tariff（优先）
    - important=1 → 自动提升 severity 预标注
  ChinaNewsCollector  中国新闻网财经 RSS（原有，保留）         ✅

用法：
  python risk_intel_collector.py --hours 48 --domains tariff,conflict --save
  python risk_intel_collector.py --keyword "美国关税" --save
  echo '{"hours":24,"save":true}' | python risk_intel_collector.py --stdin

输出：JSON → stdout
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

try:
    import feedparser
except ImportError:
    feedparser = None  # type: ignore

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")


# ─────────────────────────────────────────────────────────────────────────────
# 信源权重配置
# ─────────────────────────────────────────────────────────────────────────────

SOURCE_WEIGHTS: dict[str, int] = {
    # 官方/高权威
    "ustr": 10,
    "ofac": 10,
    "cbp": 9,
    "eu_official": 9,
    "wto": 9,
    "imf": 9,
    "fed": 9,
    "ecb": 9,
    "bis": 9,
    "un_news": 8,
    # 主流媒体
    "reuters_top": 8,
    "reuters_biz": 8,
    "china_customs": 8,
    # 快讯
    "jin10": 7,
    "chinanews": 6,
    "default": 3,
}

# ─────────────────────────────────────────────────────────────────────────────
# 三级域分类规则引擎（纯关键词，无 LLM）
# ─────────────────────────────────────────────────────────────────────────────

# 格式：(domain, category, keywords_list)，按权重从高到低排列
_DOMAIN_RULES: list[tuple[str, str, list[str]]] = [
    # ── 关税域 ──────────────────────────────────────────────────────────────
    ("tariff", "sanctions",
     ["sanction", "制裁", "blacklist", "entity list", "ofac", "export control", "出口管制",
      "embargo", "禁令", "restricted party", "denied party"]),
    ("tariff", "trade_war",
     ["tariff", "关税", "trade war", "贸易战", "trade restriction", "trade dispute",
      "section 301", "section 232", "301条款", "anti-dumping", "反倾销",
      "countervailing duty", "反补贴税", "trade tension"]),
    ("tariff", "import_duty",
     ["import duty", "进口关税", "customs duty", "海关税", "duty rate", "tariff rate",
      "hs code", "hs编码", "mfn rate", "最惠国税率"]),
    ("tariff", "export_control",
     ["export control", "出口许可", "export license", "dual use", "两用", "munitions",
      "arms embargo", "weapon export"]),
    ("tariff", "rules_of_origin",
     ["rules of origin", "原产地", "fta", "free trade agreement", "自贸协定",
      "rcep", "cptpp", "usmca", "nafta"]),
    ("tariff", "eu_regulation",
     ["cbam", "碳边境税", "carbon border", "gpsr", "epr", "extended producer",
      "reach regulation", "rohs", "weee", "eu regulation", "欧盟法规",
      "ce marking", "ce认证", "product safety"]),

    # ── 冲突域 ──────────────────────────────────────────────────────────────
    ("conflict", "military",
     ["war", "战争", "military", "军事", "invasion", "入侵", "attack", "攻击",
      "missile", "导弹", "airstrike", "空袭", "ceasefire", "停火",
      "troops", "armed forces", "武装部队"]),
    ("conflict", "geopolitics",
     ["geopolit", "地缘", "sovereignty", "主权", "territorial", "领土",
      "strait", "海峡", "south china sea", "南海", "taiwan strait", "台海",
      "nato", "北约", "alliance"]),
    ("conflict", "political_risk",
     ["coup", "政变", "election", "选举", "political instability", "政治不稳",
      "protest", "抗议", "revolution", "革命", "regime change", "政权更迭"]),
    ("conflict", "terrorism",
     ["terror", "恐怖", "extremist", "极端", "isis", "al-qaeda", "bomb",
      "suicide attack", "自杀袭击"]),

    # ── 金融域 ──────────────────────────────────────────────────────────────
    ("financial", "interest_rate",
     ["interest rate", "利率", "rate hike", "加息", "rate cut", "降息",
      "fed rate", "ecb rate", "boe rate", "fomc", "央行", "central bank",
      "monetary policy", "货币政策", "quantitative easing", "量化宽松"]),
    ("financial", "inflation",
     ["inflation", "通胀", "cpi", "ppi", "deflation", "通缩", "consumer price",
      "producer price", "price surge", "价格上涨", "hyperinflation"]),
    ("financial", "exchange_rate",
     ["exchange rate", "汇率", "currency", "货币", "depreciation", "贬值",
      "appreciation", "升值", "devaluation", "外汇", "forex",
      "usd", "eur", "cny", "jpy", "rmb"]),
    ("financial", "credit_risk",
     ["credit risk", "信用风险", "default", "违约", "debt crisis", "债务危机",
      "sovereign debt", "主权债务", "rating downgrade", "评级下调",
      "bankruptcy", "破产", "liquidity crisis", "流动性危机"]),
    ("financial", "market_crash",
     ["market crash", "市场崩盘", "stock market", "股市", "correction", "调整",
      "bear market", "熊市", "circuit breaker", "熔断", "volatility", "波动",
      "vix", "sell-off", "抛售"]),
    ("financial", "commodity",
     ["oil price", "油价", "crude oil", "原油", "gold", "黄金", "commodity",
      "大宗商品", "copper", "铜", "iron ore", "铁矿石", "opec", "石油",
      "energy", "能源"]),
]

# Jin10 channel → 预设域
_JIN10_CHANNEL_DOMAIN: dict[int, str] = {
    1: "financial",
    2: "financial",
    3: None,      # mixed，由规则引擎判断
    5: None,      # 外文，由规则引擎判断
}


def _classify_domain(text: str) -> tuple[Optional[str], Optional[str]]:
    """规则引擎快速分类，返回 (domain, category)，无匹配返回 (None, None)。"""
    text_lower = text.lower()
    for domain, category, keywords in _DOMAIN_RULES:
        for kw in keywords:
            if kw.lower() in text_lower:
                return domain, category
    return None, None


def _score_text(text: str, keywords: list[str]) -> float:
    """计算文本与关键词的相关性分（0.0~1.0）。"""
    if not text or not keywords:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for kw in keywords if kw.lower() in text_lower)
    return min(1.0, hits / max(len(keywords), 3))


# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _make_id(source: str, title: str, pub_time: str) -> str:
    raw = f"{source}:{title[:80]}:{pub_time}"
    return hashlib.md5(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _parse_time(time_str: str) -> str:
    """标准化时间字符串 → ISO8601。"""
    if not time_str:
        return datetime.now(timezone.utc).isoformat()
    try:
        # RFC 2822（RSS 标准）
        dt = parsedate_to_datetime(time_str)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        pass
    try:
        # "2026-06-13 13:32:09"（金十格式）
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        pass
    return datetime.now(timezone.utc).isoformat()


def _is_within(pub_time: str, hours: int) -> bool:
    """判断条目是否在时间窗口内。"""
    try:
        dt = datetime.fromisoformat(pub_time.replace("Z", "+00:00"))
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return dt >= cutoff
    except Exception:
        return True  # 无法解析时保留


# ─────────────────────────────────────────────────────────────────────────────
# 基础采集器
# ─────────────────────────────────────────────────────────────────────────────

class BaseCollector:
    source: str = "unknown"
    default_domain: Optional[str] = None

    def collect(self) -> list[dict]:
        raise NotImplementedError

    def _rss(self, url: str, timeout: int = 15) -> list[dict]:
        """通用 RSS 采集，返回标准化条目列表。"""
        if feedparser is None:
            log.warning("[%s] feedparser 未安装，跳过", self.source)
            return []
        try:
            d = feedparser.parse(url, request_headers={
                "User-Agent": "Mozilla/5.0 (compatible; RiskIntelBot/1.0)",
            })
            items = []
            for entry in d.entries:
                title = _strip_html(entry.get("title", "")).strip()
                if not title:
                    continue
                summary = _strip_html(
                    entry.get("summary") or entry.get("description") or ""
                )
                pub = entry.get("published") or entry.get("updated") or ""
                pub_iso = _parse_time(pub)
                text = f"{title} {summary}"
                domain, category = _classify_domain(text)
                if domain is None:
                    domain = self.default_domain
                items.append({
                    "id": _make_id(self.source, title, pub_iso),
                    "source_type": "rss",
                    "source_name": self.source,
                    "title": title[:500],
                    "summary": summary[:2000] if summary else None,
                    "url": entry.get("link", ""),
                    "pub_time": pub_iso,
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "risk_domain": domain,
                    "risk_category": category,
                    "risk_score": 0.0,
                    "severity": "low",
                    "matched_keywords": [],
                    "trigger_source": "auto",
                })
            return items
        except Exception as e:
            log.warning("[%s] RSS 采集失败: %s", self.source, e)
            return []

    def _http_json(self, url: str, headers: Optional[dict] = None,
                   timeout: int = 10) -> Optional[dict]:
        """通用 HTTP JSON 请求。"""
        if httpx is None:
            return None
        try:
            h = {"User-Agent": "Mozilla/5.0", **(headers or {})}
            r = httpx.get(url, headers=h, timeout=timeout, follow_redirects=True)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.warning("[%s] HTTP 请求失败: %s", self.source, e)
            return None

    def _http_text(self, url: str, headers: Optional[dict] = None,
                   timeout: int = 10) -> Optional[str]:
        """通用 HTTP 文本请求。"""
        if httpx is None:
            return None
        try:
            h = {"User-Agent": "Mozilla/5.0", **(headers or {})}
            r = httpx.get(url, headers=h, timeout=timeout, follow_redirects=True)
            r.raise_for_status()
            return r.text
        except Exception as e:
            log.warning("[%s] HTTP 请求失败: %s", self.source, e)
            return None


# ─────────────────────────────────────────────────────────────────────────────
# 关税域采集器
# ─────────────────────────────────────────────────────────────────────────────

class USTRCollector(BaseCollector):
    """美国贸易代表办公室 — 关税/贸易协议一手来源。"""
    source = "ustr"
    default_domain = "tariff"

    def collect(self) -> list[dict]:
        return self._rss("https://ustr.gov/rss.xml")


class CBPCollector(BaseCollector):
    """美国海关与边境保护局 — 关税执行/清关政策。"""
    source = "cbp"
    default_domain = "tariff"

    def collect(self) -> list[dict]:
        return self._rss("https://www.cbp.gov/newsroom/rss")


class EUOfficialCollector(BaseCollector):
    """欧盟官方公报 — 欧盟法规/关税变更。"""
    source = "eu_official"
    default_domain = "tariff"

    def collect(self) -> list[dict]:
        # EUR-Lex 最新条例
        items = self._rss("https://eur-lex.europa.eu/RSSEP.xml")
        if not items:
            # 降级到欧盟新闻
            items = self._rss("https://ec.europa.eu/commission/presscorner/api/rss")
        return items


class WTOCollector(BaseCollector):
    """世界贸易组织 — 贸易争端/关税通报。"""
    source = "wto"
    default_domain = "tariff"

    def collect(self) -> list[dict]:
        return self._rss("https://www.wto.org/english/news_e/rss_e.xml")


class ChinaCustomsCollector(BaseCollector):
    """中国海关总署 — 中国关税政策/进出口数据。"""
    source = "china_customs"
    default_domain = "tariff"

    def collect(self) -> list[dict]:
        # 尝试 RSS（如无则降级）
        items = self._rss("http://www.customs.gov.cn/customs/xwfb34/rss.xml")
        if not items:
            # HTTP 降级：解析海关总署新闻列表
            items = self._scrape_customs()
        return items

    def _scrape_customs(self) -> list[dict]:
        """海关总署 HTTP 页面降级爬取（无 JavaScript 静态部分）。"""
        text = self._http_text(
            "http://www.customs.gov.cn/customs/xwfb34/index.html"
        )
        if not text:
            return []
        # 简单提取 <a href="...">标题</a> 结构
        links = re.findall(
            r'href="(/customs/xwfb34/[^"]+\.html)"[^>]*>([^<]{5,100})</a>',
            text
        )
        items = []
        now = datetime.now(timezone.utc).isoformat()
        for path, title in links[:20]:
            title = _strip_html(title).strip()
            if not title:
                continue
            url = f"http://www.customs.gov.cn{path}"
            items.append({
                "id": _make_id(self.source, title, now),
                "source_type": "http",
                "source_name": self.source,
                "title": title[:500],
                "summary": None,
                "url": url,
                "pub_time": now,
                "collected_at": now,
                "risk_domain": "tariff",
                "risk_category": "import_duty",
                "risk_score": 0.0,
                "severity": "low",
                "matched_keywords": [],
                "trigger_source": "auto",
            })
        return items


# ─────────────────────────────────────────────────────────────────────────────
# 冲突域采集器
# ─────────────────────────────────────────────────────────────────────────────

class OFACCollector(BaseCollector):
    """美国财政部 OFAC 制裁名单 — 制裁/出口管制核心来源。"""
    source = "ofac"
    default_domain = "conflict"

    def collect(self) -> list[dict]:
        items = self._rss("https://ofac.treasury.gov/recent-actions/rss.xml")
        # OFAC 制裁自动提升严重度
        for item in items:
            item["risk_domain"] = "conflict"
            item["risk_category"] = "sanctions"
            item["risk_score"] = 0.75   # 制裁默认高分
            item["severity"] = "high"
        return items


class UNNewsCollector(BaseCollector):
    """联合国新闻 — 全球冲突/人道主义危机。"""
    source = "un_news"
    default_domain = "conflict"

    def collect(self) -> list[dict]:
        return self._rss(
            "https://news.un.org/feed/subscribe/en/news/all/rss.xml"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 金融域采集器
# ─────────────────────────────────────────────────────────────────────────────

class ReutersTopCollector(BaseCollector):
    """Reuters 全球头条。"""
    source = "reuters_top"
    default_domain = "financial"

    def collect(self) -> list[dict]:
        # Reuters 已停止公开 RSS，尝试备用
        items = self._rss("https://feeds.reuters.com/reuters/topNews")
        if not items:
            items = self._rss("https://www.reutersagency.com/feed/?best-topics=top")
        return items


class ReutersBizCollector(BaseCollector):
    """Reuters 商业/金融新闻。"""
    source = "reuters_biz"
    default_domain = "financial"

    def collect(self) -> list[dict]:
        items = self._rss("https://feeds.reuters.com/reuters/businessNews")
        if not items:
            items = self._rss("https://www.reutersagency.com/feed/?best-topics=business-finance")
        return items


class IMFCollector(BaseCollector):
    """国际货币基金组织 — 宏观经济/汇率/债务。"""
    source = "imf"
    default_domain = "financial"

    def collect(self) -> list[dict]:
        return self._rss("https://www.imf.org/en/News/rss")


class FedCollector(BaseCollector):
    """美联储 — 利率决策/货币政策（原有，保留）。"""
    source = "fed"
    default_domain = "financial"

    def collect(self) -> list[dict]:
        items = self._rss("https://www.federalreserve.gov/feeds/press_all.xml")
        if not items:
            items = self._rss("https://www.federalreserve.gov/newsevents/rss/all.xml")
        return items


class ECBCollector(BaseCollector):
    """欧洲央行 — 欧元区货币政策（原有，保留）。"""
    source = "ecb"
    default_domain = "financial"

    def collect(self) -> list[dict]:
        return self._rss("https://www.ecb.europa.eu/rss/news.html")


class BISCollector(BaseCollector):
    """国际清算银行 — 国际金融监管（原有，保留）。"""
    source = "bis"
    default_domain = "financial"

    def collect(self) -> list[dict]:
        return self._rss("https://www.bis.org/rss/home.rss")


class ChinaNewsCollector(BaseCollector):
    """中国新闻网财经（原有，保留）。"""
    source = "chinanews"
    default_domain = "financial"

    def collect(self) -> list[dict]:
        return self._rss("https://www.chinanews.com.cn/rss/finance.xml")


# ─────────────────────────────────────────────────────────────────────────────
# 金十数据采集器（强化版）
# ─────────────────────────────────────────────────────────────────────────────

class Jin10Collector(BaseCollector):
    """金十数据快讯（强化版）。

    频道说明：
      channel 1 — 全球宏观     → financial
      channel 2 — 原油/商品    → financial/commodity
      channel 3 — 综合快讯     → 由规则引擎判断
      channel 5 — 外文快讯     → 优先判断 conflict/tariff

    特性：
      - important=1 的条目 severity 预标注为 medium（至少）
      - 过滤 type=2（行情价格数据，非新闻文本）
      - 支持按 channel 过滤
    """
    source = "jin10"

    # channel_id → 预设域（None 表示由规则引擎决定）
    _CHANNEL_DOMAIN: dict[int, Optional[str]] = {
        1: "financial",
        2: "financial",
        3: None,
        5: None,
    }

    def __init__(self, channels: Optional[list[int]] = None):
        """channels: 要采集的频道列表，默认全部（1/2/3/5）。"""
        self.channels = set(channels) if channels else {1, 2, 3, 5}

    def collect(self) -> list[dict]:
        if httpx is None:
            log.warning("[jin10] httpx 未安装，跳过")
            return []
        try:
            r = httpx.get(
                "https://www.jin10.com/flash_newest.js",
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://www.jin10.com/",
                    "Accept": "*/*",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
                timeout=12,
                follow_redirects=True,
            )
            if r.status_code != 200:
                log.warning("[jin10] 非 200: %d", r.status_code)
                return []

            raw = r.text.strip()
            json_str = re.sub(r"^var \w+ = ", "", raw).rstrip(";")
            raw_items: list[dict] = json.loads(json_str)

            now = datetime.now(timezone.utc).isoformat()
            items = []

            for d in raw_items:
                # 过滤行情数据（type=2 是价格 ticker，不是新闻）
                if d.get("type", 0) == 2:
                    continue

                # 频道过滤
                item_channels: list[int] = d.get("channel", [])
                if not any(c in self.channels for c in item_channels):
                    continue

                data_obj = d.get("data", {}) or {}
                content = _strip_html(
                    data_obj.get("content") or data_obj.get("title") or ""
                ).strip()
                if not content or len(content) < 10:
                    continue

                pub_raw = d.get("time", "")
                pub_iso = _parse_time(pub_raw)
                important = int(d.get("important", 0))
                source_name_inner = data_obj.get("source") or ""

                # 域分类：先用频道预设，再用规则引擎
                domain_preset: Optional[str] = None
                for ch in item_channels:
                    if ch in self._CHANNEL_DOMAIN and self._CHANNEL_DOMAIN[ch]:
                        domain_preset = self._CHANNEL_DOMAIN[ch]
                        break

                rule_domain, rule_category = _classify_domain(content)
                final_domain = rule_domain or domain_preset
                final_category = rule_category

                # 严重度预标注
                severity = "low"
                if important == 1:
                    severity = "medium"   # 至少 medium，LLM 分析后可调升

                # 生成唯一 ID（优先用金十原始 ID）
                jin10_id = str(d.get("id", ""))
                item_id = _make_id("jin10", content, pub_iso)

                items.append({
                    "id": item_id,
                    "source_type": "http",
                    "source_name": "jin10",
                    "title": content[:500],
                    "summary": content,
                    "url": data_obj.get("source_link") or "https://www.jin10.com/",
                    "pub_time": pub_iso,
                    "collected_at": now,
                    "risk_domain": final_domain,
                    "risk_category": final_category,
                    "risk_score": 0.0,        # 由分析器填充
                    "severity": severity,
                    "sentiment": "neutral",
                    "affected_markets": [],
                    "affected_hs_codes": [],
                    "matched_keywords": [],
                    "trigger_source": "auto",
                    # 金十专属字段
                    "jin10_id": jin10_id,
                    "jin10_important": important,
                    "jin10_channel": item_channels,
                    # 内嵌信源标注
                    "_inner_source": source_name_inner,
                })

            return items

        except Exception as e:
            log.warning("[jin10] 采集失败: %s", e)
            return []


# ─────────────────────────────────────────────────────────────────────────────
# 米塔搜索采集器（关键词驱动）
# ─────────────────────────────────────────────────────────────────────────────

class MetasoCollector(BaseCollector):
    """米塔AI搜索 — 关键词驱动的实时联网检索。"""
    source = "metaso"

    def __init__(self, keyword: str, count: int = 10):
        self.keyword = keyword
        self.count = count

    def collect(self) -> list[dict]:
        # 调用项目内的 metaso_search.py
        script_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "tools" / "impl" / "metaso_search.py"
        )
        if not script_path.exists():
            log.warning("[metaso] 脚本不存在: %s", script_path)
            return self._fallback_search()

        import subprocess
        try:
            result = subprocess.run(
                ["python3", str(script_path),
                 "--query", self.keyword,
                 "--count", str(self.count)],
                capture_output=True, text=True, timeout=20,
                cwd=str(script_path.parent),
            )
            if result.returncode != 0:
                log.warning("[metaso] 返回非零: %s", result.stderr[:200])
                return []
            data = json.loads(result.stdout)
            return self._parse_metaso(data)
        except Exception as e:
            log.warning("[metaso] 调用失败: %s", e)
            return []

    def _parse_metaso(self, data: dict) -> list[dict]:
        results = data.get("results", [])
        now = datetime.now(timezone.utc).isoformat()
        items = []
        for r in results:
            title = r.get("title", "").strip()
            snippet = r.get("snippet", "").strip()
            if not title:
                continue
            text = f"{title} {snippet}"
            domain, category = _classify_domain(text)
            items.append({
                "id": _make_id("metaso", title, now),
                "source_type": "metaso",
                "source_name": "metaso",
                "title": title[:500],
                "summary": snippet[:2000] if snippet else None,
                "url": r.get("link", ""),
                "pub_time": now,
                "collected_at": now,
                "risk_domain": domain,
                "risk_category": category,
                "risk_score": 0.0,
                "severity": "low",
                "affected_markets": [],
                "affected_hs_codes": [],
                "matched_keywords": [self.keyword],
                "trigger_source": f"keyword:{self.keyword}",
            })
        return items

    def _fallback_search(self) -> list[dict]:
        """metaso_search.py 不存在时的降级处理（直接调用）。"""
        api_key = os.environ.get("METASO_API_KEY", "")
        if not api_key:
            log.warning("[metaso] METASO_API_KEY 未配置，无法搜索")
            return []
        if httpx is None:
            return []
        try:
            r = httpx.post(
                "https://metaso.cn/api/v1/search",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"q": self.keyword, "scope": "all", "size": self.count,
                      "conciseSnippet": True, "format": "chat_completions"},
                timeout=15,
            )
            r.raise_for_status()
            return self._parse_metaso({"results": r.json().get("webpages", [])})
        except Exception as e:
            log.warning("[metaso] fallback 失败: %s", e)
            return []


# ─────────────────────────────────────────────────────────────────────────────
# 全局采集器注册表
# ─────────────────────────────────────────────────────────────────────────────

ALL_COLLECTORS: list[BaseCollector] = [
    # 关税域
    USTRCollector(),
    CBPCollector(),
    EUOfficialCollector(),
    WTOCollector(),
    ChinaCustomsCollector(),
    # 冲突域
    OFACCollector(),
    UNNewsCollector(),
    # 金融域
    ReutersTopCollector(),
    ReutersBizCollector(),
    IMFCollector(),
    FedCollector(),
    ECBCollector(),
    BISCollector(),
    ChinaNewsCollector(),
    # 综合
    Jin10Collector(),
]

DOMAIN_COLLECTORS: dict[str, list[BaseCollector]] = {
    "tariff": [USTRCollector(), CBPCollector(), EUOfficialCollector(),
               WTOCollector(), ChinaCustomsCollector()],
    "conflict": [OFACCollector(), UNNewsCollector()],
    "financial": [ReutersTopCollector(), ReutersBizCollector(), IMFCollector(),
                  FedCollector(), ECBCollector(), BISCollector(), ChinaNewsCollector()],
    "mixed": [Jin10Collector()],
}


# ─────────────────────────────────────────────────────────────────────────────
# 主采集入口
# ─────────────────────────────────────────────────────────────────────────────

def collect_all(
    hours: int = 48,
    domains: Optional[list[str]] = None,
    keyword: Optional[str] = None,
    user_id: str = "default",
    save: bool = False,
    important_only: bool = False,
) -> dict:
    """全量采集所有信源，过滤 + 去重 + 写库。

    Args:
        hours:        时间窗口（仅保留该范围内的条目）
        domains:      限定采集的域（tariff/conflict/financial），None=全部
        keyword:      额外附加米塔关键词搜索
        user_id:      触发用户
        save:         是否写入数据库
        important_only: 仅返回 important=1 的金十条目（快捷过滤）

    Returns:
        {"items": [...], "total": int, "sources": dict, "saved": int}
    """
    # 选定采集器
    if domains:
        collectors: list[BaseCollector] = []
        for d in domains:
            collectors.extend(DOMAIN_COLLECTORS.get(d, []))
        # 金十始终加入
        if not any(isinstance(c, Jin10Collector) for c in collectors):
            collectors.append(Jin10Collector())
    else:
        collectors = list(ALL_COLLECTORS)

    # 关键词驱动：追加米塔搜索
    if keyword:
        collectors.append(MetasoCollector(keyword=keyword, count=10))

    # 并发采集
    all_items: list[dict] = []
    source_stats: dict[str, int] = {}

    for collector in collectors:
        try:
            items = collector.collect()
            # 时间窗口过滤
            items = [i for i in items if _is_within(i.get("pub_time", ""), hours)]
            # important_only 过滤
            if important_only:
                items = [
                    i for i in items
                    if i.get("source_name") != "jin10" or i.get("jin10_important", 0) == 1
                ]
            source_stats[collector.source] = len(items)
            all_items.extend(items)
            if items:
                log.info("[%s] 采集 %d 条", collector.source, len(items))
        except Exception as e:
            log.error("[%s] 采集异常: %s", collector.source, e)
            source_stats[collector.source] = 0

    # 关键词相关性评分（有 keyword 时）
    if keyword:
        kw_tokens = keyword.lower().split()
        for item in all_items:
            text = f"{item.get('title', '')} {item.get('summary', '') or ''}"
            score = _score_text(text, kw_tokens)
            item["risk_score"] = max(item.get("risk_score", 0.0), score * 0.5)
            if keyword not in item.get("matched_keywords", []):
                item.setdefault("matched_keywords", []).append(keyword)

    # 本地去重（基于 id）
    seen: set[str] = set()
    unique_items = []
    for item in all_items:
        if item["id"] not in seen:
            seen.add(item["id"])
            unique_items.append(item)

    # 写库
    saved = 0
    if save and unique_items:
        try:
            # 添加路径以导入存储层
            sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
            from app.storage.risk_intel_store import upsert_items
            inserted, _ = upsert_items(unique_items)
            saved = inserted
        except ImportError:
            log.warning("[collector] 无法导入 risk_intel_store，未写库")

    return {
        "items": unique_items,
        "total": len(unique_items),
        "sources": source_stats,
        "saved": saved,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="风险情报采集器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 采集全部信源（最近 48 小时），保存到数据库
  python risk_intel_collector.py --hours 48 --save

  # 仅采集关税域 + 米塔关键词搜索
  python risk_intel_collector.py --domains tariff --keyword "美国加征关税" --save

  # 仅返回金十重要新闻
  python risk_intel_collector.py --important-only --pretty

  # JSON stdin 模式（供 Agent 调用）
  echo '{"hours": 24, "domains": ["conflict"], "save": true}' | \\
    python risk_intel_collector.py --stdin
        """,
    )
    parser.add_argument("--hours", type=int, default=48, help="时间窗口（小时）")
    parser.add_argument("--domains", type=str, help="域过滤（逗号分隔：tariff,conflict,financial）")
    parser.add_argument("--keyword", "-k", type=str, help="附加米塔关键词搜索")
    parser.add_argument("--user-id", type=str, default="default", help="触发用户 ID")
    parser.add_argument("--save", action="store_true", help="写入数据库")
    parser.add_argument("--important-only", action="store_true", help="仅金十重要新闻")
    parser.add_argument("--pretty", action="store_true", help="美化 JSON 输出")
    parser.add_argument("--stdin", action="store_true", help="从 stdin 读取 JSON 参数")

    args = parser.parse_args()

    if args.stdin:
        try:
            cfg = json.loads(sys.stdin.read())
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"stdin JSON 解析失败: {e}"}, ensure_ascii=False))
            sys.exit(1)
        hours = cfg.get("hours", 48)
        domains_raw = cfg.get("domains")
        keyword = cfg.get("keyword")
        user_id = cfg.get("user_id", "default")
        save = cfg.get("save", False)
        important_only = cfg.get("important_only", False)
    else:
        hours = args.hours
        domains_raw = args.domains
        keyword = args.keyword
        user_id = args.user_id
        save = args.save
        important_only = args.important_only

    # domains_raw 可能是 list（stdin JSON）或 str（CLI 参数）
    if isinstance(domains_raw, list):
        domains = [d.strip() for d in domains_raw if d]
    elif isinstance(domains_raw, str) and domains_raw:
        domains = [d.strip() for d in domains_raw.split(",")]
    else:
        domains = None

    result = collect_all(
        hours=hours,
        domains=domains,
        keyword=keyword,
        user_id=user_id,
        save=save,
        important_only=important_only,
    )

    indent = 2 if args.pretty else None
    # 输出时去掉大 content 字段以节省带宽
    output = {
        "total": result["total"],
        "saved": result["saved"],
        "sources": result["sources"],
        "items": [
            {k: v for k, v in item.items() if k != "_inner_source"}
            for item in result["items"][:100]  # 最多返回 100 条
        ],
    }
    print(json.dumps(output, ensure_ascii=False, indent=indent))


if __name__ == "__main__":
    main()
