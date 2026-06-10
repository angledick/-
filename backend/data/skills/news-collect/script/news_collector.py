#!/usr/bin/env python3
"""新闻采集器 — 独立可执行工具脚本。

Agent 可通过 Python 命令传参运行:
  python data/tools/impl/news_collector.py --hours 48 --user-id default
  python data/tools/impl/news_collector.py --hours 24 --pretty

也可通过 JSON stdin 传参:
  echo '{"hours": 48, "user_id": "default"}' | python news_collector.py --stdin

已验证可用的数据源：
  FedCollector        美联储新闻 RSS                     ✅
  ChinaNewsCollector  中国新闻网财经 RSS                  ✅
  Jin10Collector      金十数据 flash_newest.js            ✅
  WTOCollector        WTO 新闻 RSS                       待确认
  BISCollector        国际清算银行 RSS                    待确认
  ECBCollector        欧洲央行 RSS                        待确认

输出: JSON 格式到 stdout（采集结果列表 + 存储统计）
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

try:
    import feedparser
except ImportError:
    feedparser = None  # type: ignore

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

log = logging.getLogger(__name__)

SOURCE_WEIGHTS: dict[str, int] = {
    "fed": 10,
    "wto": 9,
    "bis": 9,
    "ecb": 9,
    "chinanews": 8,
    "jin10": 8,
    "default": 3,
}

# 英文关键词（用于匹配 Fed/WTO/BIS/ECB 等英文新闻）
_EN_KEYWORDS_HIGH = [
    "tariff", "sanction", "export control", "ban", "embargo",
    "interest rate", "rate hike", "rate cut", "inflation",
    "regulation", "compliance", "customs", "import duty",
    "trade war", "restriction", "blacklist", "entity list",
]
_EN_KEYWORDS_STD = [
    "trade", "market", "policy", "monetary", "fiscal",
    "economy", "gdp", "employment", "consumer", "supply chain",
    "semiconductor", "technology", "export", "import",
]


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _make_id(source: str, title: str, pub_time: str) -> str:
    raw = f"{source}:{title}:{pub_time}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _parse_time(time_str: str) -> str:
    if not time_str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        dt = parsedate_to_datetime(time_str)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return time_str


def _filter_by_hours(items: list[dict], hours: int) -> list[dict]:
    cutoff = time.time() - hours * 3600
    result = []
    for item in items:
        try:
            t = item.get("time", "")
            if t:
                dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
                if dt.timestamp() < cutoff:
                    continue
        except Exception:
            pass
        result.append(item)
    return result


def _score_item(title: str, content: str, source: str,
                keywords: list[str], high_words: list[str]) -> tuple[int, list[str]]:
    text = (title + " " + content).lower()
    base = SOURCE_WEIGHTS.get(source, SOURCE_WEIGHTS["default"])
    hits: list[str] = []
    for kw in high_words:
        if kw.lower() in text:
            hits.append(kw)
            base += 5
    for kw in keywords:
        if kw.lower() in text and kw not in hits:
            hits.append(kw)
            base += 2
    for kw in _EN_KEYWORDS_HIGH:
        if kw in text and kw not in hits:
            hits.append(kw)
            base += 4
    for kw in _EN_KEYWORDS_STD:
        if kw in text and kw not in hits:
            hits.append(kw)
            base += 1
    return base, hits


# ── 采集器基类 ────────────────────────────────────────────────────────

class BaseCollector:
    source = "unknown"

    def collect(self) -> list[dict]:
        raise NotImplementedError

    def _rss(self, url: str) -> list[dict]:
        if feedparser is None:
            log.warning("feedparser 未安装，跳过 %s", self.source)
            return []
        try:
            feed = feedparser.parse(url)
            items = []
            for entry in feed.entries[:30]:
                title = _strip_html(entry.get("title", ""))
                if not title:
                    continue
                pub = entry.get("published", entry.get("updated", ""))
                content = _strip_html(entry.get("summary", ""))[:400]
                items.append({
                    "id": _make_id(self.source, title, pub),
                    "time": _parse_time(pub),
                    "source": self.source,
                    "title": title,
                    "content": content,
                    "url": entry.get("link", ""),
                })
            return items
        except Exception as e:
            log.warning("[%s] RSS 采集失败: %s", self.source, e)
            return []


class FedCollector(BaseCollector):
    source = "fed"

    def collect(self) -> list[dict]:
        return self._rss("https://www.federalreserve.gov/feeds/press_all.xml")


class ChinaNewsCollector(BaseCollector):
    source = "chinanews"

    def collect(self) -> list[dict]:
        return self._rss("https://www.chinanews.com.cn/rss/finance.xml")


class Jin10Collector(BaseCollector):
    source = "jin10"

    def collect(self) -> list[dict]:
        if httpx is None:
            return []
        try:
            r = httpx.get(
                "https://www.jin10.com/flash_newest.js",
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                    "Referer": "https://www.jin10.com/",
                },
                timeout=10,
                follow_redirects=True,
            )
            if r.status_code != 200:
                return []
            raw = r.text.strip()
            json_str = re.sub(r"^var \w+ = ", "", raw).rstrip(";")
            items_raw = json.loads(json_str)
            items = []
            for d in items_raw:
                data = d.get("data", {})
                content = _strip_html(data.get("content") or data.get("title") or "").strip()
                if not content:
                    continue
                pub = d.get("time", "")
                items.append({
                    "id": _make_id("jin10", content, pub),
                    "time": _parse_time(pub),
                    "source": "jin10",
                    "title": content[:120],
                    "content": content,
                    "url": "https://www.jin10.com/",
                })
            return items
        except Exception as e:
            log.warning("[jin10] 采集失败: %s", e)
            return []


class WTOCollector(BaseCollector):
    source = "wto"

    def collect(self) -> list[dict]:
        return self._rss("https://www.wto.org/english/news_e/rss_e.xml")


class BISCollector(BaseCollector):
    source = "bis"

    def collect(self) -> list[dict]:
        return self._rss("https://www.bis.org/rss/home.rss")


class ECBCollector(BaseCollector):
    source = "ecb"

    def collect(self) -> list[dict]:
        return self._rss("https://www.ecb.europa.eu/rss/news.html")


ALL_COLLECTORS: list[BaseCollector] = [
    FedCollector(),
    ChinaNewsCollector(),
    Jin10Collector(),
    # WTOCollector(),   # RSS 返回 HTML，需代理
    # BISCollector(),   # 404
    # ECBCollector(),   # 404
]

_SLOW_SOURCES = {"fed", "wto", "bis", "ecb"}
_SLOW_HOURS = 168
_FAST_HOURS = 48


# ── 默认关键词 ────────────────────────────────────────────────────────

_DEFAULT_KEYWORDS = [
    "降息", "加息", "降准", "美联储", "央行", "通胀", "CPI", "GDP",
    "贸易战", "关税", "制裁", "危机", "违约", "破产",
    "跨境电商", "出口管制", "GDPR", "CE认证", "欧盟法规", "合规",
    "清关", "海关", "进口税", "平台政策", "封号", "下架",
    "tariff", "sanction", "export control", "trade restriction",
    "interest rate", "rate decision", "inflation", "monetary policy",
    "regulation", "compliance", "customs duty", "import ban",
    "trade war", "blacklist", "entity list", "embargo",
    "ecommerce", "cross-border", "market access",
]
_DEFAULT_HIGH = [
    "降息", "加息", "制裁", "危机", "违约", "出口管制",
    "sanction", "export control", "tariff", "rate hike", "rate cut", "embargo",
]


def _get_keywords(user_id: str = "default") -> dict:
    """获取关键词配置（尝试从 storage 读取，失败则用默认）。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
        from app.storage.news_store import get_keywords
        return get_keywords(user_id)
    except Exception:
        return {"keywords": _DEFAULT_KEYWORDS, "high_words": _DEFAULT_HIGH}


# ── 主采集入口 ────────────────────────────────────────────────────────

def collect_all(user_id: str = "default", hours: int = _FAST_HOURS) -> list[dict]:
    """采集全部数据源，关键词过滤 + 评分。"""
    cfg = _get_keywords(user_id)
    keywords = cfg["keywords"]
    high_words = cfg["high_words"]

    all_items: list[dict] = []
    for collector in ALL_COLLECTORS:
        try:
            items = collector.collect()
            h = _SLOW_HOURS if collector.source in _SLOW_SOURCES else hours
            items = _filter_by_hours(items, h)
            all_items.extend(items)
            log.info("[%s] 采集 %d 条（时间窗 %dh）", collector.source, len(items), h)
        except Exception as e:
            log.warning("[%s] 采集异常: %s", collector.source, e)

    # 去重
    seen: set[str] = set()
    unique: list[dict] = []
    for item in all_items:
        if item["id"] not in seen:
            seen.add(item["id"])
            unique.append(item)

    # 评分 + 关键词命中
    for item in unique:
        score, hits = _score_item(
            item["title"], item.get("content", ""),
            item["source"], keywords, high_words,
        )
        item["score"] = score
        item["keywords_hit"] = hits

    # 保留：命中关键词 OR 高权重来源
    filtered = [
        i for i in unique
        if i["keywords_hit"] or SOURCE_WEIGHTS.get(i["source"], 0) >= 7
    ]
    filtered.sort(key=lambda x: x["score"], reverse=True)
    return filtered[:150]


# ── CLI 入口 ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="新闻采集器 — 多数据源 RSS/HTTP 采集 + 关键词评分",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--hours", type=int, default=48, help="采集时间窗口（小时）")
    parser.add_argument("--user-id", type=str, default="default", help="用户ID（关键词配置）")
    parser.add_argument("--stdin", action="store_true", help="从 stdin 读取 JSON 参数")
    parser.add_argument("--pretty", action="store_true", help="美化 JSON 输出")
    parser.add_argument("--save", action="store_true", help="将结果写入 news_store（需 app 可导入）")

    args = parser.parse_args()

    if args.stdin:
        try:
            stdin_data = json.loads(sys.stdin.read())
            hours = stdin_data.get("hours", 48)
            user_id = stdin_data.get("user_id", "default")
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"stdin JSON 解析失败: {e}"}, ensure_ascii=False))
            sys.exit(1)
    else:
        hours = args.hours
        user_id = args.user_id

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    items = collect_all(user_id=user_id, hours=hours)

    # 可选：写入存储
    saved = 0
    if args.save:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
            from app.storage.news_store import upsert_news
            saved = upsert_news(items)
        except Exception as e:
            log.warning("写入 news_store 失败: %s", e)

    result = {
        "total_collected": len(items),
        "saved": saved,
        "items": items,
    }

    indent = 2 if args.pretty else None
    print(json.dumps(result, ensure_ascii=False, indent=indent))


if __name__ == "__main__":
    main()
