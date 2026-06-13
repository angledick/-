"""供应商存储层 — SQLite（复用 sessions.db）。

表：
  suppliers        供应商基础信息
  supplier_ratings 评分记录
"""

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "sessions.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_tables() -> None:
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id                TEXT PRIMARY KEY,
            name              TEXT NOT NULL,
            source_type       TEXT NOT NULL DEFAULT 'factory',
            contact_name      TEXT DEFAULT '',
            contact_phone     TEXT DEFAULT '',
            contact_email     TEXT DEFAULT '',
            address           TEXT DEFAULT '',
            country           TEXT DEFAULT 'CN',
            business_license  TEXT DEFAULT '',
            tax_id            TEXT DEFAULT '',
            has_invoice       INTEGER DEFAULT 0,
            certifications    TEXT DEFAULT '[]',
            categories        TEXT DEFAULT '[]',
            rating            REAL DEFAULT 0.0,
            risk_level        TEXT DEFAULT 'unknown',
            status            TEXT DEFAULT 'active',
            tags              TEXT DEFAULT '[]',
            ai_review         TEXT,
            ai_review_at      TEXT,
            metadata          TEXT DEFAULT '{}',
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_sup_status   ON suppliers(status);
        CREATE INDEX IF NOT EXISTS idx_sup_country  ON suppliers(country);
        CREATE INDEX IF NOT EXISTS idx_sup_type     ON suppliers(source_type);

        CREATE TABLE IF NOT EXISTS supplier_ratings (
            id          TEXT PRIMARY KEY,
            supplier_id TEXT NOT NULL,
            user_id     TEXT NOT NULL,
            score       REAL NOT NULL,
            dimensions  TEXT DEFAULT '{}',
            comment     TEXT DEFAULT '',
            created_at  TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_srat_supplier ON supplier_ratings(supplier_id);
        """)


# ── CRUD ─────────────────────────────────────────────────────────────────────

def create_supplier(data: dict) -> dict:
    now = _now()
    sid = data.get("id") or f"sup_{uuid.uuid4().hex[:8]}"
    record = {
        "id": sid,
        "name": data["name"],
        "source_type": data.get("source_type", "factory"),
        "contact_name": data.get("contact_name", ""),
        "contact_phone": data.get("contact_phone", ""),
        "contact_email": data.get("contact_email", ""),
        "address": data.get("address", ""),
        "country": data.get("country", "CN"),
        "business_license": data.get("business_license", ""),
        "tax_id": data.get("tax_id", ""),
        "has_invoice": int(data.get("has_invoice", False)),
        "certifications": json.dumps(data.get("certifications", []), ensure_ascii=False),
        "categories": json.dumps(data.get("categories", []), ensure_ascii=False),
        "rating": float(data.get("rating", 0.0)),
        "risk_level": data.get("risk_level", "unknown"),
        "status": data.get("status", "active"),
        "tags": json.dumps(data.get("tags", []), ensure_ascii=False),
        "metadata": json.dumps(data.get("metadata", {}), ensure_ascii=False),
        "created_at": now,
        "updated_at": now,
    }
    with _conn() as conn:
        conn.execute("""INSERT INTO suppliers VALUES (
            :id,:name,:source_type,:contact_name,:contact_phone,:contact_email,
            :address,:country,:business_license,:tax_id,:has_invoice,
            :certifications,:categories,:rating,:risk_level,:status,:tags,
            NULL,NULL,:metadata,:created_at,:updated_at)""", record)
    return get_supplier(sid)


def get_supplier(supplier_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM suppliers WHERE id=?", (supplier_id,)).fetchone()
    return _row(row) if row else None


def list_suppliers(
    status: Optional[str] = None,
    source_type: Optional[str] = None,
    country: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    clauses, params = [], []
    if status:      clauses.append("status=?");      params.append(status)
    if source_type: clauses.append("source_type=?"); params.append(source_type)
    if country:     clauses.append("country=?");     params.append(country)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM suppliers {where} ORDER BY rating DESC, created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    return [_row(r) for r in rows]


def update_supplier(supplier_id: str, updates: dict) -> Optional[dict]:
    allowed = {
        "name","source_type","contact_name","contact_phone","contact_email",
        "address","country","business_license","tax_id","has_invoice",
        "certifications","categories","rating","risk_level","status","tags","metadata",
    }
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return get_supplier(supplier_id)
    # JSON 序列化列表/dict
    for k in ("certifications","categories","tags","metadata"):
        if k in fields and isinstance(fields[k], (list, dict)):
            fields[k] = json.dumps(fields[k], ensure_ascii=False)
    if "has_invoice" in fields:
        fields["has_invoice"] = int(fields["has_invoice"])
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k}=?" for k in fields)
    with _conn() as conn:
        conn.execute(
            f"UPDATE suppliers SET {set_clause} WHERE id=?",
            list(fields.values()) + [supplier_id],
        )
    return get_supplier(supplier_id)


def save_ai_review(supplier_id: str, review: dict) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE suppliers SET ai_review=?, ai_review_at=?, risk_level=?, updated_at=? WHERE id=?",
            (json.dumps(review, ensure_ascii=False), _now(),
             review.get("risk_level", "unknown"), _now(), supplier_id),
        )
        return cur.rowcount > 0


def add_rating(supplier_id: str, user_id: str, score: float, dimensions: dict = None, comment: str = "") -> dict:
    rid = f"rat_{uuid.uuid4().hex[:8]}"
    now = _now()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO supplier_ratings VALUES (?,?,?,?,?,?,?)",
            (rid, supplier_id, user_id, score, json.dumps(dimensions or {}, ensure_ascii=False), comment, now),
        )
        # 更新供应商平均评分
        avg = conn.execute(
            "SELECT AVG(score) FROM supplier_ratings WHERE supplier_id=?", (supplier_id,)
        ).fetchone()[0] or 0.0
        conn.execute("UPDATE suppliers SET rating=?, updated_at=? WHERE id=?", (round(avg, 2), now, supplier_id))
    return {"id": rid, "supplier_id": supplier_id, "score": score, "comment": comment}


# ── 辅助 ─────────────────────────────────────────────────────────────────────

def _row(row) -> dict:
    if not row:
        return {}
    d = dict(row)
    for f in ("certifications", "categories", "tags"):
        if isinstance(d.get(f), str):
            try: d[f] = json.loads(d[f])
            except: d[f] = []
    for f in ("metadata",):
        if isinstance(d.get(f), str):
            try: d[f] = json.loads(d[f])
            except: d[f] = {}
    for f in ("ai_review",):
        if isinstance(d.get(f), str):
            try: d[f] = json.loads(d[f])
            except: pass
    d["has_invoice"] = bool(d.get("has_invoice", 0))
    return d


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


ensure_tables()
