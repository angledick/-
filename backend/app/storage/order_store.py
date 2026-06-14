"""销售订单存储层 — SQLite（sessions.db）。

表：
  sales_orders       销售订单主表
  payment_records    支付记录
  webhook_event_log  Webhook 幂等去重日志
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
    """建表，幂等。"""
    with _conn() as conn:
        conn.executescript("""
        -- ── 销售订单主表 ──────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS sales_orders (
            id                TEXT PRIMARY KEY,
            platform          TEXT NOT NULL DEFAULT 'manual',
            platform_order_id TEXT,
            product_id        TEXT,
            buyer_name        TEXT NOT NULL DEFAULT '',
            buyer_email       TEXT DEFAULT '',
            buyer_address     TEXT DEFAULT '{}',
            items             TEXT DEFAULT '[]',
            currency          TEXT DEFAULT 'USD',
            total_amount      REAL DEFAULT 0.0,
            status            TEXT DEFAULT 'pending',
            notes             TEXT DEFAULT '',
            metadata          TEXT DEFAULT '{}',
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_so_product   ON sales_orders(product_id);
        CREATE INDEX IF NOT EXISTS idx_so_status    ON sales_orders(status);
        CREATE INDEX IF NOT EXISTS idx_so_platform  ON sales_orders(platform, platform_order_id);

        -- ── 支付记录 ────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS payment_records (
            id           TEXT PRIMARY KEY,
            order_id     TEXT NOT NULL,
            channel_id   TEXT,
            payment_ref  TEXT,
            amount       REAL NOT NULL,
            currency     TEXT DEFAULT 'USD',
            payer_email  TEXT DEFAULT '',
            payer_name   TEXT DEFAULT '',
            status       TEXT DEFAULT 'pending',
            paid_at      TEXT,
            notes        TEXT DEFAULT '',
            created_at   TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_pr_order ON payment_records(order_id);
        CREATE INDEX IF NOT EXISTS idx_pr_ref   ON payment_records(payment_ref);

        -- ── Webhook 幂等去重 ─────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS webhook_event_log (
            event_id     TEXT PRIMARY KEY,
            provider     TEXT NOT NULL,
            payload_hash TEXT,
            processed_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_wel_provider ON webhook_event_log(provider);
        """)


# ─────────────────────────────────────────────────────────────────────────────
# 销售订单 CRUD
# ─────────────────────────────────────────────────────────────────────────────

def create_order(data: dict) -> dict:
    now = _now()
    oid = data.get("id") or f"order_{uuid.uuid4().hex[:8]}"
    with _conn() as conn:
        conn.execute(
            """INSERT INTO sales_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (oid,
             data.get("platform", "manual"),
             data.get("platform_order_id"),
             data.get("product_id"),
             data.get("buyer_name", ""),
             data.get("buyer_email", ""),
             json.dumps(data.get("buyer_address", {}), ensure_ascii=False),
             json.dumps(data.get("items", []), ensure_ascii=False),
             data.get("currency", "USD"),
             float(data.get("total_amount", 0)),
             data.get("status", "pending"),
             data.get("notes", ""),
             json.dumps(data.get("metadata", {}), ensure_ascii=False),
             now, now),
        )
    return get_order(oid)


def get_order(order_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM sales_orders WHERE id=?", (order_id,)
        ).fetchone()
    return _order_row(row) if row else None


def list_orders(
    product_id: Optional[str] = None,
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    clauses, params = [], []
    if product_id: clauses.append("product_id=?"); params.append(product_id)
    if platform:   clauses.append("platform=?");   params.append(platform)
    if status:     clauses.append("status=?");     params.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM sales_orders {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    return [_order_row(r) for r in rows]


def update_order(order_id: str, updates: dict) -> Optional[dict]:
    allowed = {"buyer_name", "buyer_email", "buyer_address", "items",
               "currency", "total_amount", "status", "notes", "metadata"}
    fields = {k: v for k, v in updates.items() if k in allowed}
    for f in ("buyer_address", "metadata"):
        if f in fields and isinstance(fields[f], dict):
            fields[f] = json.dumps(fields[f], ensure_ascii=False)
    if "items" in fields and isinstance(fields["items"], list):
        fields["items"] = json.dumps(fields["items"], ensure_ascii=False)
    if not fields:
        return get_order(order_id)
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k}=?" for k in fields)
    with _conn() as conn:
        conn.execute(
            f"UPDATE sales_orders SET {set_clause} WHERE id=?",
            list(fields.values()) + [order_id],
        )
    return get_order(order_id)


# ─────────────────────────────────────────────────────────────────────────────
# 支付记录 CRUD
# ─────────────────────────────────────────────────────────────────────────────

def add_payment(order_id: str, data: dict) -> dict:
    now = _now()
    pid = f"payrec_{uuid.uuid4().hex[:8]}"
    with _conn() as conn:
        conn.execute(
            "INSERT INTO payment_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, order_id,
             data.get("channel_id"),
             data.get("payment_ref"),
             float(data.get("amount", 0)),
             data.get("currency", "USD"),
             data.get("payer_email", ""),
             data.get("payer_name", ""),
             data.get("status", "completed"),
             data.get("paid_at", now),
             data.get("notes", ""),
             now),
        )
        # 自动把订单状态更新为 paid
        if data.get("status", "completed") == "completed":
            conn.execute(
                "UPDATE sales_orders SET status='paid', updated_at=? WHERE id=?",
                (now, order_id),
            )
    return {"id": pid, "order_id": order_id, **data}


def get_payments(order_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM payment_records WHERE order_id=? ORDER BY created_at DESC",
            (order_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_payment_summary(order_id: str) -> dict:
    """返回支付汇总（总已付金额、最新支付、支付状态）。"""
    payments = get_payments(order_id)
    completed = [p for p in payments if p["status"] == "completed"]
    total_paid = sum(p["amount"] for p in completed)
    order = get_order(order_id)
    return {
        "order_id": order_id,
        "total_amount": order["total_amount"] if order else 0,
        "total_paid": total_paid,
        "unpaid": max(0, (order["total_amount"] if order else 0) - total_paid),
        "payment_count": len(payments),
        "completed_count": len(completed),
        "latest_payment": payments[0] if payments else None,
        "fully_paid": total_paid >= (order["total_amount"] if order else 0) * 0.99,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Webhook 幂等控制
# ─────────────────────────────────────────────────────────────────────────────

def is_webhook_processed(event_id: str) -> bool:
    """检查 Webhook 事件是否已处理（幂等保障）。"""
    with _conn() as conn:
        row = conn.execute(
            "SELECT event_id FROM webhook_event_log WHERE event_id=?", (event_id,)
        ).fetchone()
    return row is not None


def mark_webhook_processed(event_id: str, provider: str, payload_hash: str = "") -> None:
    """标记 Webhook 事件为已处理。"""
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO webhook_event_log VALUES (?,?,?,?)",
                (event_id, provider, payload_hash, _now()),
            )
    except Exception:
        pass


def cleanup_webhook_log(days: int = 30) -> int:
    """清理过期的 Webhook 日志（默认保留 30 天）。"""
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM webhook_event_log WHERE processed_at < datetime('now', ? || ' days')",
            (f"-{days}",),
        )
        return cur.rowcount


# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────────────────────

def _order_row(row) -> dict:
    if not row:
        return {}
    d = dict(row)
    for f in ("items",):
        if isinstance(d.get(f), str):
            try: d[f] = json.loads(d[f])
            except: d[f] = []
    for f in ("buyer_address", "metadata"):
        if isinstance(d.get(f), str):
            try: d[f] = json.loads(d[f])
            except: d[f] = {}
    return d


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


ensure_tables()
