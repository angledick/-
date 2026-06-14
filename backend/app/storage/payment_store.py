"""支付通道存储层 — SQLite（sessions.db）。

表：
  payment_channels  支付网关配置
  chargeback_events 拒付事件记录
"""

import json
import uuid
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "sessions.db"


def _conn():
    import sqlite3
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_tables() -> None:
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS payment_channels (
            id               TEXT PRIMARY KEY,
            provider         TEXT NOT NULL,
            display_name     TEXT NOT NULL,
            currency         TEXT DEFAULT '["USD"]',
            markets          TEXT DEFAULT '[]',
            status           TEXT DEFAULT 'pending_kyc',
            kyc_verified     INTEGER DEFAULT 0,
            webhook_url      TEXT DEFAULT '',
            test_mode        INTEGER DEFAULT 1,
            chargeback_rate  REAL DEFAULT 0.0,
            chargeback_limit REAL DEFAULT 0.8,
            pci_dss          INTEGER DEFAULT 0,
            compliance_notes TEXT DEFAULT '[]',
            last_tested_at   TEXT,
            test_result      TEXT,
            metadata         TEXT DEFAULT '{}',
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_pay_provider ON payment_channels(provider);
        CREATE INDEX IF NOT EXISTS idx_pay_status   ON payment_channels(status);

        CREATE TABLE IF NOT EXISTS chargeback_events (
            id          TEXT PRIMARY KEY,
            channel_id  TEXT NOT NULL,
            order_id    TEXT DEFAULT '',
            amount      REAL DEFAULT 0.0,
            currency    TEXT DEFAULT 'USD',
            reason      TEXT DEFAULT '',
            status      TEXT DEFAULT 'open',
            created_at  TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cb_channel ON chargeback_events(channel_id);
        """)


# ── CRUD ─────────────────────────────────────────────────────────────────────

PROVIDER_DEFAULTS = {
    "stripe":          {"display_name": "Stripe", "currency": ["USD","EUR","GBP"],
                        "markets": ["US","UK","EU"], "pci_dss": True},
    "paypal":          {"display_name": "PayPal", "currency": ["USD","EUR","CNY"],
                        "markets": ["US","EU","CN"], "pci_dss": True},
    "lianlian":        {"display_name": "连连支付", "currency": ["USD","EUR"],
                        "markets": ["US","EU","AU"], "pci_dss": False},
    "worldfirst":      {"display_name": "万里汇 WorldFirst", "currency": ["USD","EUR","GBP"],
                        "markets": ["US","UK","EU","AU"], "pci_dss": False},
    "shopify_payments":{"display_name": "Shopify Payments", "currency": ["USD","EUR","GBP","CAD","AUD"],
                        "markets": ["US","UK","EU","CA","AU"], "pci_dss": True},
    "alipay_global":   {"display_name": "支付宝国际版", "currency": ["USD","EUR"],
                        "markets": ["EU","AS"], "pci_dss": False},
}


def create_channel(data: dict) -> dict:
    now = _now()
    pid = f"pay_{uuid.uuid4().hex[:8]}"
    provider = data["provider"]
    defaults = PROVIDER_DEFAULTS.get(provider, {})
    with _conn() as conn:
        conn.execute("""INSERT INTO payment_channels VALUES (
            ?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,?,?,?)""",
            (pid, provider,
             data.get("display_name", defaults.get("display_name", provider)),
             json.dumps(data.get("currency", defaults.get("currency", ["USD"])), ensure_ascii=False),
             json.dumps(data.get("markets", defaults.get("markets", [])), ensure_ascii=False),
             data.get("status", "pending_kyc"),
             int(data.get("kyc_verified", False)),
             data.get("webhook_url", ""),
             int(data.get("test_mode", True)),
             float(data.get("chargeback_rate", 0.0)),
             float(data.get("chargeback_limit", 0.8)),
             int(data.get("pci_dss", defaults.get("pci_dss", False))),
             json.dumps([], ensure_ascii=False),
             json.dumps(data.get("metadata", {}), ensure_ascii=False),
             now, now))
    return get_channel(pid)


def get_channel(channel_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM payment_channels WHERE id=?", (channel_id,)).fetchone()
    return _row(row) if row else None


def list_channels(status: Optional[str] = None) -> list[dict]:
    where = "WHERE status=?" if status else ""
    params = [status] if status else []
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM payment_channels {where} ORDER BY created_at DESC", params
        ).fetchall()
    return [_row(r) for r in rows]


def update_channel(channel_id: str, updates: dict) -> Optional[dict]:
    allowed = {
        "display_name","currency","markets","status","kyc_verified",
        "webhook_url","test_mode","chargeback_rate","chargeback_limit",
        "pci_dss","compliance_notes","metadata",
    }
    fields = {k: v for k, v in updates.items() if k in allowed}
    for f in ("currency", "markets", "compliance_notes"):
        if f in fields and isinstance(fields[f], list):
            fields[f] = json.dumps(fields[f], ensure_ascii=False)
    if "metadata" in fields and isinstance(fields["metadata"], dict):
        fields["metadata"] = json.dumps(fields["metadata"], ensure_ascii=False)
    for f in ("kyc_verified", "test_mode", "pci_dss"):
        if f in fields: fields[f] = int(fields[f])
    if not fields:
        return get_channel(channel_id)
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k}=?" for k in fields)
    with _conn() as conn:
        conn.execute(f"UPDATE payment_channels SET {set_clause} WHERE id=?",
                     list(fields.values()) + [channel_id])
    return get_channel(channel_id)


def save_test_result(channel_id: str, success: bool, result: dict) -> bool:
    now = _now()
    status = "active" if success else "error"
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE payment_channels SET last_tested_at=?, test_result=?, status=?, updated_at=? WHERE id=?",
            (now, json.dumps(result, ensure_ascii=False), status, now, channel_id),
        )
        return cur.rowcount > 0


def add_chargeback_event(channel_id: str, order_id: str, amount: float, currency: str, reason: str) -> dict:
    eid = f"cb_{uuid.uuid4().hex[:8]}"
    now = _now()
    with _conn() as conn:
        conn.execute("INSERT INTO chargeback_events VALUES (?,?,?,?,?,?,'open',?)",
                     (eid, channel_id, order_id, amount, currency, reason, now))
        # 重新计算拒付率（简单：近30天 chargeback 数 / 1000 笔假设订单数）
        count = conn.execute(
            "SELECT COUNT(*) FROM chargeback_events WHERE channel_id=? AND created_at >= datetime('now','-30 days')",
            (channel_id,),
        ).fetchone()[0]
        rate = round(count / max(1, 100), 4) * 100  # 简化计算
        conn.execute("UPDATE payment_channels SET chargeback_rate=? WHERE id=?", (rate, channel_id))
    return {"id": eid, "channel_id": channel_id, "amount": amount, "reason": reason}


def get_chargeback_stats(channel_id: str, days: int = 30) -> dict:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM chargeback_events WHERE channel_id=? AND created_at >= datetime('now',? || ' days') ORDER BY created_at DESC",
            (channel_id, f"-{days}"),
        ).fetchall()
        channel = get_channel(channel_id)
    return {
        "channel_id": channel_id,
        "period_days": days,
        "count": len(rows),
        "total_amount": sum(r["amount"] for r in rows),
        "current_rate": channel.get("chargeback_rate", 0) if channel else 0,
        "limit": channel.get("chargeback_limit", 0.8) if channel else 0.8,
        "events": [dict(r) for r in rows[:10]],
    }


def _row(row) -> dict:
    if not row:
        return {}
    d = dict(row)
    for f in ("currency", "markets", "compliance_notes"):
        if isinstance(d.get(f), str):
            try: d[f] = json.loads(d[f])
            except: d[f] = []
    for f in ("metadata", "test_result"):
        if isinstance(d.get(f), str):
            try: d[f] = json.loads(d[f])
            except: d[f] = {}
    for f in ("kyc_verified", "test_mode", "pci_dss"):
        d[f] = bool(d.get(f, 0))
    return d


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


ensure_tables()
