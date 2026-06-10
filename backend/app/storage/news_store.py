"""新闻监控数据存储 — SQLite。

表：
  monitored_news      原始新闻条目
  news_analyses       AI 分析结果
  news_keyword_config 用户关键词配置
"""

import json
import sqlite3
import time
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "sessions.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init():
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS monitored_news (
            id           TEXT PRIMARY KEY,
            time         TEXT NOT NULL,
            source       TEXT NOT NULL,
            title        TEXT NOT NULL,
            content      TEXT DEFAULT '',
            url          TEXT DEFAULT '',
            score        REAL DEFAULT 0,
            keywords_hit TEXT DEFAULT '[]',
            created_at   INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS news_analyses (
            news_id          TEXT PRIMARY KEY REFERENCES monitored_news(id),
            risk_direction   TEXT DEFAULT '中性',
            risk_level       TEXT DEFAULT 'low',
            affected_markets TEXT DEFAULT '[]',
            logic            TEXT DEFAULT '',
            confidence       REAL DEFAULT 0.5,
            analyzed_at      INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS news_keyword_config (
            user_id      TEXT PRIMARY KEY,
            keywords     TEXT NOT NULL DEFAULT '[]',
            high_words   TEXT NOT NULL DEFAULT '[]',
            updated_at   INTEGER NOT NULL
        );
        """)
        conn.commit()


_init()


# ── 新闻 CRUD ─────────────────────────────────────────────────────────

def upsert_news(items: list[dict]) -> int:
    """批量写入新闻，已存在的跳过。返回新增条数。"""
    if not items:
        return 0
    added = 0
    with _conn() as conn:
        for item in items:
            cur = conn.execute(
                "INSERT OR IGNORE INTO monitored_news "
                "(id, time, source, title, content, url, score, keywords_hit, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    item["id"], item["time"], item["source"],
                    item["title"], item.get("content", ""),
                    item.get("url", ""), item.get("score", 0),
                    json.dumps(item.get("keywords_hit", []), ensure_ascii=False),
                    int(time.time()),
                ),
            )
            added += cur.rowcount
        conn.commit()
    return added


def get_recent_news(hours: int = 48, limit: int = 100) -> list[dict]:
    cutoff = int(time.time()) - hours * 3600
    with _conn() as conn:
        rows = conn.execute(
            "SELECT n.*, a.risk_direction, a.risk_level, a.affected_markets, a.logic, a.confidence, a.analyzed_at "
            "FROM monitored_news n "
            "LEFT JOIN news_analyses a ON n.id = a.news_id "
            "WHERE n.created_at >= ? "
            "ORDER BY n.score DESC, n.created_at DESC LIMIT ?",
            (cutoff, limit),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["keywords_hit"]      = json.loads(d.get("keywords_hit") or "[]")
        d["affected_markets"]  = json.loads(d.get("affected_markets") or "[]")
        result.append(d)
    return result


def get_unanalyzed_news(limit: int = 50) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT n.* FROM monitored_news n "
            "LEFT JOIN news_analyses a ON n.id = a.news_id "
            "WHERE a.news_id IS NULL "
            "ORDER BY n.score DESC, n.created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["keywords_hit"] = json.loads(d.get("keywords_hit") or "[]")
        result.append(d)
    return result


# ── AI 分析 CRUD ──────────────────────────────────────────────────────

def save_analysis(analysis: dict) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO news_analyses "
            "(news_id, risk_direction, risk_level, affected_markets, logic, confidence, analyzed_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                analysis["news_id"],
                analysis.get("risk_direction", "中性"),
                analysis.get("risk_level", "low"),
                json.dumps(analysis.get("affected_markets", []), ensure_ascii=False),
                analysis.get("logic", ""),
                analysis.get("confidence", 0.5),
                int(time.time()),
            ),
        )
        conn.commit()


def get_direction_summary(hours: int = 24) -> dict:
    """统计最近 N 小时内各风险方向的新闻数量。"""
    cutoff = int(time.time()) - hours * 3600
    with _conn() as conn:
        rows = conn.execute(
            "SELECT risk_direction, COUNT(*) as cnt "
            "FROM news_analyses a "
            "JOIN monitored_news n ON n.id = a.news_id "
            "WHERE n.created_at >= ? GROUP BY risk_direction",
            (cutoff,),
        ).fetchall()
    summary = {"利多": 0, "利空": 0, "中性": 0, "total": 0}
    for r in rows:
        d, c = r["risk_direction"], r["cnt"]
        if d in summary:
            summary[d] = c
        summary["total"] += c
    return summary


# ── 关键词配置 ────────────────────────────────────────────────────────

_DEFAULT_KEYWORDS = [
    # 中文 — 宏观政策
    "降息", "加息", "降准", "美联储", "央行", "通胀", "CPI", "GDP",
    "贸易战", "关税", "制裁", "危机", "违约", "破产",
    # 中文 — 跨境合规
    "跨境电商", "出口管制", "GDPR", "CE认证", "欧盟法规", "合规",
    "清关", "海关", "进口税", "平台政策", "封号", "下架",
    # 英文 — 对应境外数据源 (Fed/WTO/ECB/BIS)
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


def get_keywords(user_id: str = "default") -> dict:
    with _conn() as conn:
        row = conn.execute(
            "SELECT keywords, high_words FROM news_keyword_config WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if row:
        return {
            "keywords":   json.loads(row["keywords"]),
            "high_words": json.loads(row["high_words"]),
        }
    return {"keywords": _DEFAULT_KEYWORDS, "high_words": _DEFAULT_HIGH}


def set_keywords(user_id: str, keywords: list[str], high_words: list[str]) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO news_keyword_config (user_id, keywords, high_words, updated_at) "
            "VALUES (?,?,?,?)",
            (user_id, json.dumps(keywords, ensure_ascii=False),
             json.dumps(high_words, ensure_ascii=False), int(time.time())),
        )
        conn.commit()
