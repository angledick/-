"""风险情报存储层 — SQLite（复用 sessions.db）。

表结构：
  risk_intel_items      情报条目（含 FTS5 全文索引）
  risk_intel_keywords   用户关键词配置
  risk_intel_runs       检索执行记录
"""

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "sessions.db"

# ── 频道到风险域的快速映射（Jin10 channel → domain）──────────
JIN10_CHANNEL_DOMAIN: dict[int, str] = {
    1: "financial",   # 全球宏观
    2: "financial",   # 原油/商品
    3: "mixed",       # 快讯（综合，由分析器再判）
    5: "conflict",    # 外文快讯（多为地缘/冲突）
}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    # 开启 WAL 模式，并发读写更稳定
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ─────────────────────────────────────────────────────────────────────────────
# 建表（幂等）
# ─────────────────────────────────────────────────────────────────────────────

def _migrate_columns(conn: sqlite3.Connection) -> None:
    """为已有数据库添加新列（幂等，失败静默跳过）。"""
    _new_cols = [
        ("risk_intel_items", "llm_analysis",  "TEXT"),
        ("risk_intel_items", "llm_analyzed",  "INTEGER DEFAULT 0"),
        ("risk_intel_items", "llm_error",     "TEXT"),
    ]
    for table, col, col_type in _new_cols:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass  # 列已存在，跳过


def ensure_tables() -> None:
    """建表，幂等。启动时调用一次即可。"""
    with _conn() as conn:
        # ── 旧库在线列迁移（SQLite 不支持 ADD COLUMN IF NOT EXISTS，用 try/except）
        _migrate_columns(conn)
        conn.executescript("""
        -- ── 情报条目主表 ──────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS risk_intel_items (
            id                TEXT PRIMARY KEY,
            source_type       TEXT NOT NULL DEFAULT 'rss',
            source_name       TEXT NOT NULL,
            title             TEXT NOT NULL,
            summary           TEXT,
            url               TEXT,
            pub_time          TEXT,
            collected_at      TEXT NOT NULL,
            -- 三级分类
            risk_domain       TEXT,
            risk_category     TEXT,
            -- 量化
            risk_score        REAL DEFAULT 0.0,
            severity          TEXT DEFAULT 'low',
            sentiment         TEXT DEFAULT 'neutral',
            -- 市场关联
            affected_markets  TEXT DEFAULT '[]',
            affected_hs_codes TEXT DEFAULT '[]',
            -- 关键词溯源
            matched_keywords  TEXT DEFAULT '[]',
            trigger_source    TEXT DEFAULT 'auto',
            -- 金十特有字段
            jin10_id          TEXT,
            jin10_important   INTEGER DEFAULT 0,
            jin10_channel     TEXT DEFAULT '[]',
            -- 状态
            analyzed          INTEGER DEFAULT 0,
            alert_id          TEXT,
            headline_summary  TEXT,
            -- LLM 深度分析（新增字段，via ALTER TABLE 兼容旧库）
            llm_analysis      TEXT,
            llm_analyzed      INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_rii_domain    ON risk_intel_items(risk_domain);
        CREATE INDEX IF NOT EXISTS idx_rii_score     ON risk_intel_items(risk_score DESC);
        CREATE INDEX IF NOT EXISTS idx_rii_collected ON risk_intel_items(collected_at DESC);
        CREATE INDEX IF NOT EXISTS idx_rii_severity  ON risk_intel_items(severity);
        CREATE INDEX IF NOT EXISTS idx_rii_analyzed  ON risk_intel_items(analyzed);

        -- FTS5 全文索引（title + summary 可全文检索）
        CREATE VIRTUAL TABLE IF NOT EXISTS risk_intel_fts USING fts5(
            id       UNINDEXED,
            title,
            summary,
            content  = 'risk_intel_items',
            content_rowid = 'rowid',
            tokenize = 'unicode61'
        );

        -- FTS5 自动同步触发器
        CREATE TRIGGER IF NOT EXISTS risk_intel_fts_insert
            AFTER INSERT ON risk_intel_items BEGIN
                INSERT INTO risk_intel_fts(rowid, id, title, summary)
                VALUES (new.rowid, new.id, new.title, COALESCE(new.summary, ''));
            END;

        CREATE TRIGGER IF NOT EXISTS risk_intel_fts_delete
            AFTER DELETE ON risk_intel_items BEGIN
                INSERT INTO risk_intel_fts(risk_intel_fts, rowid, id, title, summary)
                VALUES ('delete', old.rowid, old.id, old.title, COALESCE(old.summary, ''));
            END;

        CREATE TRIGGER IF NOT EXISTS risk_intel_fts_update
            AFTER UPDATE ON risk_intel_items BEGIN
                INSERT INTO risk_intel_fts(risk_intel_fts, rowid, id, title, summary)
                VALUES ('delete', old.rowid, old.id, old.title, COALESCE(old.summary, ''));
                INSERT INTO risk_intel_fts(rowid, id, title, summary)
                VALUES (new.rowid, new.id, new.title, COALESCE(new.summary, ''));
            END;

        -- ── 用户关键词配置 ────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS risk_intel_keywords (
            id                TEXT PRIMARY KEY,
            user_id           TEXT NOT NULL,
            keyword           TEXT NOT NULL,
            label             TEXT,
            domain            TEXT DEFAULT 'all',
            auto_suggested    INTEGER DEFAULT 0,
            source_hint       TEXT,
            periodic_enabled  INTEGER DEFAULT 0,
            cron_expr         TEXT DEFAULT '0 */6 * * *',
            last_run_at       TEXT,
            next_run_at       TEXT,
            total_runs        INTEGER DEFAULT 0,
            total_hits        INTEGER DEFAULT 0,
            enabled           INTEGER DEFAULT 1,
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL,
            UNIQUE(user_id, keyword)
        );

        CREATE INDEX IF NOT EXISTS idx_rik_user   ON risk_intel_keywords(user_id);
        CREATE INDEX IF NOT EXISTS idx_rik_domain ON risk_intel_keywords(domain);
        CREATE INDEX IF NOT EXISTS idx_rik_periodic ON risk_intel_keywords(periodic_enabled);

        -- ── 检索执行记录 ──────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS risk_intel_runs (
            id             TEXT PRIMARY KEY,
            run_type       TEXT NOT NULL DEFAULT 'manual',
            keyword_id     TEXT,
            keyword        TEXT NOT NULL,
            user_id        TEXT,
            status         TEXT DEFAULT 'pending',
            items_found    INTEGER DEFAULT 0,
            items_new      INTEGER DEFAULT 0,
            alerts_created INTEGER DEFAULT 0,
            error_msg      TEXT,
            started_at     TEXT,
            finished_at    TEXT,
            created_at     TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_rir_keyword ON risk_intel_runs(keyword_id);
        CREATE INDEX IF NOT EXISTS idx_rir_status  ON risk_intel_runs(status);
        CREATE INDEX IF NOT EXISTS idx_rir_created ON risk_intel_runs(created_at DESC);
        """)


# ─────────────────────────────────────────────────────────────────────────────
# 情报条目 CRUD
# ─────────────────────────────────────────────────────────────────────────────

def upsert_items(items: list[dict]) -> tuple[int, int]:
    """批量写入情报条目，基于 (source_name, title, pub_time) 去重。

    Returns:
        (inserted, skipped)
    """
    inserted = 0
    skipped = 0
    with _conn() as conn:
        for item in items:
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO risk_intel_items (
                        id, source_type, source_name, title, summary, url,
                        pub_time, collected_at,
                        risk_domain, risk_category,
                        risk_score, severity, sentiment,
                        affected_markets, affected_hs_codes,
                        matched_keywords, trigger_source,
                        jin10_id, jin10_important, jin10_channel,
                        analyzed, alert_id, headline_summary
                    ) VALUES (
                        :id, :source_type, :source_name, :title,
                        :summary, :url, :pub_time, :collected_at,
                        :risk_domain, :risk_category,
                        :risk_score, :severity, :sentiment,
                        :affected_markets, :affected_hs_codes,
                        :matched_keywords, :trigger_source,
                        :jin10_id, :jin10_important, :jin10_channel,
                        :analyzed, :alert_id, :headline_summary
                    )""",
                    {
                        "id": item.get("id", ""),
                        "source_type": item.get("source_type", "rss"),
                        "source_name": item.get("source_name", ""),
                        "title": item.get("title", "")[:500],
                        "summary": item.get("summary") or item.get("content"),
                        "url": item.get("url"),
                        "pub_time": item.get("pub_time") or item.get("time"),
                        "collected_at": item.get("collected_at", _now()),
                        "risk_domain": item.get("risk_domain"),
                        "risk_category": item.get("risk_category"),
                        "risk_score": float(item.get("risk_score", 0.0)),
                        "severity": item.get("severity", "low"),
                        "sentiment": item.get("sentiment", "neutral"),
                        "affected_markets": json.dumps(
                            item.get("affected_markets", []), ensure_ascii=False
                        ),
                        "affected_hs_codes": json.dumps(
                            item.get("affected_hs_codes", []), ensure_ascii=False
                        ),
                        "matched_keywords": json.dumps(
                            item.get("matched_keywords", []), ensure_ascii=False
                        ),
                        "trigger_source": item.get("trigger_source", "auto"),
                        "jin10_id": item.get("jin10_id"),
                        "jin10_important": int(item.get("jin10_important", 0)),
                        "jin10_channel": json.dumps(
                            item.get("jin10_channel", [])
                        ),
                        "analyzed": int(item.get("analyzed", 0)),
                        "alert_id": item.get("alert_id"),
                        "headline_summary": item.get("headline_summary"),
                    },
                )
                if conn.execute("SELECT changes()").fetchone()[0] > 0:
                    inserted += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1
    return inserted, skipped


def update_item_analysis(item_id: str, analysis: dict) -> bool:
    """将分析结果回写到条目（analyzer 调用）。"""
    with _conn() as conn:
        cur = conn.execute(
            """UPDATE risk_intel_items SET
                risk_domain      = :risk_domain,
                risk_category    = :risk_category,
                risk_score       = :risk_score,
                severity         = :severity,
                sentiment        = :sentiment,
                affected_markets = :affected_markets,
                affected_hs_codes= :affected_hs_codes,
                headline_summary = :headline_summary,
                analyzed         = 1
            WHERE id = :id""",
            {
                "id": item_id,
                "risk_domain": analysis.get("risk_domain"),
                "risk_category": analysis.get("risk_category"),
                "risk_score": float(analysis.get("risk_score", 0.0)),
                "severity": analysis.get("severity", "low"),
                "sentiment": analysis.get("sentiment", "neutral"),
                "affected_markets": json.dumps(
                    analysis.get("affected_markets", []), ensure_ascii=False
                ),
                "affected_hs_codes": json.dumps(
                    analysis.get("affected_hs_codes", []), ensure_ascii=False
                ),
                "headline_summary": analysis.get("headline_summary"),
            },
        )
        return cur.rowcount > 0


def link_alert(item_id: str, alert_id: str) -> bool:
    """关联预警 ID 到情报条目。"""
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE risk_intel_items SET alert_id = ? WHERE id = ?",
            (alert_id, item_id),
        )
        return cur.rowcount > 0


def get_unanalyzed_items(limit: int = 30) -> list[dict]:
    """拉取未分析条目，供 analyzer 批处理。"""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT * FROM risk_intel_items
               WHERE analyzed = 0
               ORDER BY collected_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_llm_pending_items(
    limit: int = 20,
    min_score: float = 0.0,
    hours: int = 720,
) -> list[dict]:
    """拉取待 LLM 分析的条目（规则引擎已标注，但 LLM 未分析）。

    优先返回高分（risk_score 降序）+最新（collected_at 降序）。
    """
    since = _ts_ago(hours)
    with _conn() as conn:
        rows = conn.execute(
            """SELECT * FROM risk_intel_items
               WHERE llm_analyzed = 0
                 AND analyzed = 1
                 AND risk_score >= ?
                 AND collected_at >= ?
               ORDER BY risk_score DESC, collected_at DESC
               LIMIT ?""",
            (min_score, since, limit),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_llm_analysis(item_id: str, result: dict) -> bool:
    """将 LLM 分析结果写回条目。

    Args:
        item_id: 条目 ID
        result:  LLM 输出 dict，包含：
                   headline_summary  – ≤30字标题摘要
                   summary           – ≤100字事件概述
                   impact            – ≤80字影响分析
                   actions           – list[str] 建议行动
                   risk_domain       – 校正后的域分类
                   risk_category     – 校正后的二级分类
                   risk_score        – LLM 打分（0-1）
                   severity          – 严重度
                   affected_markets  – 市场列表
                   affected_hs_codes – HS 编码列表
                   confidence        – 置信度（0-1）
                   error             – 错误信息（失败时）
    """
    # 构建 llm_analysis JSON 快照（前端直接消费）
    llm_blob = json.dumps({
        "summary":           result.get("summary", ""),
        "impact":            result.get("impact", ""),
        "actions":           result.get("actions", []),
        "confidence":        float(result.get("confidence", 0.5)),
        "analyzed_at":       _now(),
        "model":             result.get("_model", ""),
    }, ensure_ascii=False)

    with _conn() as conn:
        cur = conn.execute(
            """UPDATE risk_intel_items SET
                llm_analysis      = ?,
                llm_analyzed      = ?,
                llm_error         = ?,
                headline_summary  = COALESCE(?, headline_summary),
                risk_domain       = COALESCE(?, risk_domain),
                risk_category     = COALESCE(?, risk_category),
                risk_score        = CASE WHEN ? > 0 THEN ? ELSE risk_score END,
                severity          = COALESCE(?, severity),
                affected_markets  = CASE WHEN ? != '[]' THEN ? ELSE affected_markets END,
                affected_hs_codes = CASE WHEN ? != '[]' THEN ? ELSE affected_hs_codes END
               WHERE id = ?""",
            (
                llm_blob,
                0 if result.get("error") else 1,
                result.get("error"),
                result.get("headline_summary"),
                result.get("risk_domain"),
                result.get("risk_category"),
                float(result.get("risk_score", 0)),
                float(result.get("risk_score", 0)),
                result.get("severity"),
                json.dumps(result.get("affected_markets", []), ensure_ascii=False),
                json.dumps(result.get("affected_markets", []), ensure_ascii=False),
                json.dumps(result.get("affected_hs_codes", []), ensure_ascii=False),
                json.dumps(result.get("affected_hs_codes", []), ensure_ascii=False),
                item_id,
            ),
        )
        return cur.rowcount > 0


def get_analysis_stats() -> dict:
    """返回 LLM 分析队列统计。"""
    with _conn() as conn:
        row = conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN llm_analyzed = 1 THEN 1 ELSE 0 END) as done,
                SUM(CASE WHEN llm_analyzed = 0 AND analyzed = 1 THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN llm_error IS NOT NULL THEN 1 ELSE 0 END) as errors
               FROM risk_intel_items"""
        ).fetchone()
    return dict(row) if row else {"total": 0, "done": 0, "pending": 0, "errors": 0}


def search_items(
    query: Optional[str] = None,
    domain: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    markets: Optional[list[str]] = None,
    min_score: float = 0.0,
    hours: int = 168,
    page: int = 1,
    size: int = 20,
    source_name: Optional[str] = None,
    jin10_only: bool = False,
    important_only: bool = False,
) -> dict:
    """多维过滤检索情报条目。

    Args:
        query:         FTS5 全文检索关键词（支持中文）
        domain:        tariff | conflict | financial
        category:      二级分类
        severity:      逗号分隔多值，如 "high,critical"
        markets:       市场列表，交集过滤
        min_score:     最低风险分（0.0~1.0）
        hours:         时间窗口（默认 7 天）
        page/size:     分页
        source_name:   信源过滤（如 'jin10'）
        jin10_only:    仅金十数据
        important_only: 仅金十 important=1 的条目
    Returns:
        {"items": [...], "total": int, "page": int, "size": int, "has_next": bool}
    """
    since = _ts_ago(hours)
    params: list = []
    where_clauses: list[str] = ["collected_at >= ?"]
    params.append(since)

    # FTS5 全文检索
    fts_ids: Optional[set[str]] = None
    if query:
        try:
            with _conn() as conn:
                fts_rows = conn.execute(
                    "SELECT id FROM risk_intel_fts WHERE risk_intel_fts MATCH ?",
                    (query,),
                ).fetchall()
            fts_ids = {r["id"] for r in fts_rows}
            if not fts_ids:
                return {"items": [], "total": 0, "page": page, "size": size, "has_next": False}
        except Exception:
            # FTS5 不可用时降级为 LIKE
            where_clauses.append("(title LIKE ? OR summary LIKE ?)")
            like_q = f"%{query}%"
            params.extend([like_q, like_q])

    if fts_ids is not None:
        placeholders = ",".join("?" * len(fts_ids))
        where_clauses.append(f"id IN ({placeholders})")
        params.extend(list(fts_ids))

    if domain:
        where_clauses.append("risk_domain = ?")
        params.append(domain)

    if category:
        where_clauses.append("risk_category = ?")
        params.append(category)

    if severity:
        sev_list = [s.strip() for s in severity.split(",")]
        phs = ",".join("?" * len(sev_list))
        where_clauses.append(f"severity IN ({phs})")
        params.extend(sev_list)

    if min_score > 0:
        where_clauses.append("risk_score >= ?")
        params.append(min_score)

    if source_name:
        where_clauses.append("source_name = ?")
        params.append(source_name)

    if jin10_only:
        where_clauses.append("source_name = 'jin10'")

    if important_only:
        where_clauses.append("jin10_important = 1")

    where_sql = " AND ".join(where_clauses)

    with _conn() as conn:
        # 市场过滤（JSON 数组中包含任意目标市场）
        if markets:
            # SQLite 无 JSON_EACH 数组操作，用 LIKE 拼接
            market_clauses = " OR ".join(
                "affected_markets LIKE ?" for _ in markets
            )
            where_sql += f" AND ({market_clauses})"
            for m in markets:
                params.append(f'%"{m}"%')

        total_row = conn.execute(
            f"SELECT COUNT(*) FROM risk_intel_items WHERE {where_sql}", params
        ).fetchone()
        total = total_row[0] if total_row else 0

        offset = (page - 1) * size
        rows = conn.execute(
            f"""SELECT * FROM risk_intel_items
                WHERE {where_sql}
                ORDER BY risk_score DESC, collected_at DESC
                LIMIT ? OFFSET ?""",
            params + [size, offset],
        ).fetchall()

    items = [_row_to_dict(r) for r in rows]
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "has_next": (page * size) < total,
    }


def get_item(item_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM risk_intel_items WHERE id = ?", (item_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_heatmap_data(hours: int = 168) -> dict:
    """返回风险热力图聚合数据。"""
    since = _ts_ago(hours)
    with _conn() as conn:
        # 按域统计
        domain_rows = conn.execute(
            """SELECT risk_domain,
                      COUNT(*) as cnt,
                      SUM(CASE WHEN severity='critical' THEN 1 ELSE 0 END) as critical,
                      SUM(CASE WHEN severity='high'     THEN 1 ELSE 0 END) as high,
                      AVG(risk_score) as avg_score
               FROM risk_intel_items
               WHERE collected_at >= ? AND risk_domain IS NOT NULL
               GROUP BY risk_domain""",
            (since,),
        ).fetchall()

        # 趋势（按天分组）
        trend_rows = conn.execute(
            """SELECT DATE(collected_at) as date,
                      risk_domain,
                      COUNT(*) as cnt
               FROM risk_intel_items
               WHERE collected_at >= ? AND risk_domain IS NOT NULL
               GROUP BY date, risk_domain
               ORDER BY date ASC""",
            (since,),
        ).fetchall()

        # 按市场统计（展开 JSON 数组较慢，用近似：统计包含市场字符串的条目数）
        top_markets_rows = conn.execute(
            """SELECT affected_markets FROM risk_intel_items
               WHERE collected_at >= ? AND affected_markets != '[]'""",
            (since,),
        ).fetchall()

        # 最近 critical 条目
        latest_critical = conn.execute(
            """SELECT id, title, risk_domain, risk_category, risk_score,
                      source_name, collected_at, headline_summary, url
               FROM risk_intel_items
               WHERE collected_at >= ? AND severity = 'critical'
               ORDER BY collected_at DESC LIMIT 5""",
            (since,),
        ).fetchall()

    # 组装 by_domain
    by_domain: dict = {}
    for r in domain_rows:
        d = r["risk_domain"] or "unknown"
        by_domain[d] = {
            "count": r["cnt"],
            "critical": r["critical"],
            "high": r["high"],
            "avg_score": round(float(r["avg_score"] or 0), 3),
        }

    # 组装 trend（透视）
    trend_map: dict[str, dict] = {}
    for r in trend_rows:
        date = r["date"]
        if date not in trend_map:
            trend_map[date] = {"date": date}
        trend_map[date][r["risk_domain"]] = r["cnt"]
    trend = list(trend_map.values())

    # 统计 top markets
    market_counter: dict[str, int] = {}
    for r in top_markets_rows:
        try:
            markets_list = json.loads(r["affected_markets"])
            for m in markets_list:
                market_counter[m] = market_counter.get(m, 0) + 1
        except Exception:
            pass
    top_markets = sorted(
        [{"market": k, "count": v} for k, v in market_counter.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    return {
        "by_domain": by_domain,
        "trend": trend,
        "top_markets": top_markets,
        "latest_critical": [_row_to_dict(r) for r in latest_critical],
        "generated_at": _now(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 关键词 CRUD
# ─────────────────────────────────────────────────────────────────────────────

def add_keyword(
    user_id: str,
    keyword: str,
    label: Optional[str] = None,
    domain: str = "all",
    auto_suggested: bool = False,
    source_hint: Optional[str] = None,
    periodic_enabled: bool = False,
    cron_expr: str = "0 */6 * * *",
) -> dict:
    """新增关键词，重复则返回已有记录。"""
    now = _now()
    kid = str(uuid.uuid4())
    with _conn() as conn:
        try:
            conn.execute(
                """INSERT INTO risk_intel_keywords
                   (id, user_id, keyword, label, domain,
                    auto_suggested, source_hint,
                    periodic_enabled, cron_expr,
                    created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    kid, user_id, keyword, label, domain,
                    int(auto_suggested), source_hint,
                    int(periodic_enabled), cron_expr,
                    now, now,
                ),
            )
        except sqlite3.IntegrityError:
            # 关键词已存在，返回已有记录
            row = conn.execute(
                "SELECT * FROM risk_intel_keywords WHERE user_id=? AND keyword=?",
                (user_id, keyword),
            ).fetchone()
            return _row_to_dict(row) if row else {}

        row = conn.execute(
            "SELECT * FROM risk_intel_keywords WHERE id=?", (kid,)
        ).fetchone()
    return _row_to_dict(row) if row else {}


def get_keywords(
    user_id: str,
    domain: Optional[str] = None,
    periodic_only: bool = False,
) -> list[dict]:
    """查询用户关键词列表。"""
    clauses = ["user_id = ?", "enabled = 1"]
    params: list = [user_id]
    if domain and domain != "all":
        clauses.append("(domain = ? OR domain = 'all')")
        params.append(domain)
    if periodic_only:
        clauses.append("periodic_enabled = 1")
    where = " AND ".join(clauses)
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM risk_intel_keywords WHERE {where} ORDER BY created_at DESC",
            params,
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_all_periodic_keywords() -> list[dict]:
    """获取所有启用周期检索的关键词（跨用户，供调度器使用）。"""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT * FROM risk_intel_keywords
               WHERE periodic_enabled = 1 AND enabled = 1
               ORDER BY last_run_at ASC NULLS FIRST""",
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_keyword(keyword_id: str, user_id: str, updates: dict) -> Optional[dict]:
    """更新关键词配置。"""
    allowed = {
        "label", "domain", "periodic_enabled", "cron_expr", "enabled"
    }
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return None
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [keyword_id, user_id]
    with _conn() as conn:
        cur = conn.execute(
            f"UPDATE risk_intel_keywords SET {set_clause} WHERE id=? AND user_id=?",
            values,
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT * FROM risk_intel_keywords WHERE id=?", (keyword_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def touch_keyword_run(keyword_id: str, hits: int = 0) -> None:
    """更新关键词的最后执行时间和命中次数。"""
    with _conn() as conn:
        conn.execute(
            """UPDATE risk_intel_keywords
               SET last_run_at  = ?,
                   total_runs   = total_runs + 1,
                   total_hits   = total_hits + ?,
                   updated_at   = ?
               WHERE id = ?""",
            (_now(), hits, _now(), keyword_id),
        )


def delete_keyword(keyword_id: str, user_id: str) -> bool:
    """软删除（设 enabled=0）。"""
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE risk_intel_keywords SET enabled=0, updated_at=? WHERE id=? AND user_id=?",
            (_now(), keyword_id, user_id),
        )
        return cur.rowcount > 0


# ─────────────────────────────────────────────────────────────────────────────
# 执行记录 CRUD
# ─────────────────────────────────────────────────────────────────────────────

def create_run(
    keyword: str,
    run_type: str = "manual",
    keyword_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> str:
    """创建执行记录，返回 run_id。"""
    run_id = str(uuid.uuid4())
    now = _now()
    with _conn() as conn:
        conn.execute(
            """INSERT INTO risk_intel_runs
               (id, run_type, keyword_id, keyword, user_id,
                status, created_at, started_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (run_id, run_type, keyword_id, keyword, user_id, "running", now, now),
        )
    return run_id


def finish_run(
    run_id: str,
    items_found: int,
    items_new: int,
    alerts_created: int = 0,
    error_msg: Optional[str] = None,
) -> None:
    """完成执行记录。"""
    status = "failed" if error_msg else "done"
    with _conn() as conn:
        conn.execute(
            """UPDATE risk_intel_runs SET
               status         = ?,
               items_found    = ?,
               items_new      = ?,
               alerts_created = ?,
               error_msg      = ?,
               finished_at    = ?
               WHERE id = ?""",
            (status, items_found, items_new, alerts_created, error_msg, _now(), run_id),
        )


def get_runs(
    user_id: Optional[str] = None,
    keyword_id: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    clauses = []
    params: list = []
    if user_id:
        clauses.append("user_id = ?")
        params.append(user_id)
    if keyword_id:
        clauses.append("keyword_id = ?")
        params.append(keyword_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM risk_intel_runs {where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_run(run_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM risk_intel_runs WHERE id=?", (run_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────────────────────

def _now() -> str:
    """返回当前 ISO8601 时间字符串。"""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts_ago(hours: int) -> str:
    """返回 N 小时前的 ISO8601 时间字符串。"""
    from datetime import datetime, timezone, timedelta
    dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    d = dict(row)
    # JSON 字段反序列化
    for field in ("affected_markets", "affected_hs_codes", "matched_keywords", "jin10_channel"):
        if field in d and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except Exception:
                d[field] = []
    # llm_analysis 解析为 dict
    if "llm_analysis" in d and isinstance(d["llm_analysis"], str):
        try:
            d["llm_analysis"] = json.loads(d["llm_analysis"])
        except Exception:
            d["llm_analysis"] = None
    return d
