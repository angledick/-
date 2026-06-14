"""物流存储层 — SQLite（sessions.db）。

表：
  logistics_orders   物流单
  logistics_events   物流轨迹事件
  logistics_carriers 承运商配置
"""

import json
import uuid
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "sessions.db"

VALID_STATUSES = [
    "pending", "picked_up", "in_transit", "customs_export",
    "customs_import", "out_for_delivery", "delivered", "exception", "returned",
]

CARRIERS = {
    "dhl":        {"name": "DHL Express", "tracking_url": "https://www.dhl.com/tracking?id={num}"},
    "fedex":      {"name": "FedEx", "tracking_url": "https://www.fedex.com/tracking?tracknumbers={num}"},
    "ups":        {"name": "UPS", "tracking_url": "https://www.ups.com/track?tracknum={num}"},
    "sf_express": {"name": "顺丰国际", "tracking_url": "https://www.sf-express.com/cn/tc/dynamic_function/waybill/#search/bill-number:{num}"},
    "ems":        {"name": "EMS", "tracking_url": "https://track.ems.com.cn/?mailNo={num}"},
    "cainiao":    {"name": "菜鸟国际", "tracking_url": "https://global.cainiao.com/detail.htm?mailNoList={num}"},
    "17track":    {"name": "17TRACK 通用", "tracking_url": "https://www.17track.net/en/track?nums={num}"},
    "aftership":  {"name": "AfterShip", "tracking_url": "https://track.aftership.com/{num}"},
}


def _conn():
    import sqlite3
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_tables() -> None:
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS logistics_orders (
            id                       TEXT PRIMARY KEY,
            product_id               TEXT NOT NULL,
            order_id                 TEXT DEFAULT '',
            carrier                  TEXT NOT NULL,
            tracking_number          TEXT DEFAULT '',
            service_type             TEXT DEFAULT '国际快件',
            incoterm                 TEXT DEFAULT 'FOB',
            origin_country           TEXT DEFAULT 'CN',
            dest_country             TEXT NOT NULL,
            status                   TEXT DEFAULT 'pending',
            estimated_delivery       TEXT,
            insured                  INTEGER DEFAULT 0,
            insured_value            REAL DEFAULT 0.0,
            customs_declaration_id   TEXT,
            weight_kg                REAL DEFAULT 0.0,
            dimensions               TEXT DEFAULT '{}',
            freight_cost             REAL DEFAULT 0.0,
            freight_currency         TEXT DEFAULT 'USD',
            metadata                 TEXT DEFAULT '{}',
            created_at               TEXT NOT NULL,
            updated_at               TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_log_product  ON logistics_orders(product_id);
        CREATE INDEX IF NOT EXISTS idx_log_status   ON logistics_orders(status);
        CREATE INDEX IF NOT EXISTS idx_log_carrier  ON logistics_orders(carrier);
        CREATE INDEX IF NOT EXISTS idx_log_tracking ON logistics_orders(tracking_number);

        CREATE TABLE IF NOT EXISTS logistics_events (
            id          TEXT PRIMARY KEY,
            order_id    TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            location    TEXT DEFAULT '',
            description TEXT DEFAULT '',
            status_code TEXT DEFAULT '',
            raw         TEXT DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_le_order ON logistics_events(order_id);
        """)


# ── CRUD ─────────────────────────────────────────────────────────────────────

def create_order(data: dict) -> dict:
    now = _now()
    oid = f"logi_{uuid.uuid4().hex[:8]}"
    with _conn() as conn:
        conn.execute("""INSERT INTO logistics_orders VALUES (
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (oid, data["product_id"], data.get("order_id", ""),
             data["carrier"], data.get("tracking_number", ""),
             data.get("service_type", "国际快件"), data.get("incoterm", "FOB"),
             data.get("origin_country", "CN"), data["dest_country"],
             "pending", None,
             int(data.get("insured", False)), float(data.get("insured_value", 0)),
             data.get("customs_declaration_id"),
             float(data.get("weight_kg", 0)),
             json.dumps(data.get("dimensions", {}), ensure_ascii=False),
             float(data.get("freight_cost", 0)),
             data.get("freight_currency", "USD"),
             json.dumps(data.get("metadata", {}), ensure_ascii=False),
             now, now))
    return get_order(oid)


def get_order(order_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM logistics_orders WHERE id=?", (order_id,)).fetchone()
    return _row(row) if row else None


def list_orders(
    product_id: Optional[str] = None,
    status: Optional[str] = None,
    carrier: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    clauses, params = [], []
    if product_id: clauses.append("product_id=?"); params.append(product_id)
    if status:     clauses.append("status=?");     params.append(status)
    if carrier:    clauses.append("carrier=?");    params.append(carrier)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM logistics_orders {where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()
    return [_row(r) for r in rows]


def update_status(order_id: str, status: str, estimated_delivery: Optional[str] = None) -> Optional[dict]:
    if status not in VALID_STATUSES:
        raise ValueError(f"无效状态: {status}")
    updates = {"status": status, "updated_at": _now()}
    if estimated_delivery:
        updates["estimated_delivery"] = estimated_delivery
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with _conn() as conn:
        conn.execute(f"UPDATE logistics_orders SET {set_clause} WHERE id=?",
                     list(updates.values()) + [order_id])
    return get_order(order_id)


def add_tracking_event(order_id: str, timestamp: str, location: str,
                        description: str, status_code: str = "", raw: dict = None) -> dict:
    eid = f"le_{uuid.uuid4().hex[:8]}"
    with _conn() as conn:
        conn.execute("INSERT INTO logistics_events VALUES (?,?,?,?,?,?,?)",
                     (eid, order_id, timestamp, location, description, status_code,
                      json.dumps(raw or {}, ensure_ascii=False)))
        conn.execute("UPDATE logistics_orders SET updated_at=? WHERE id=?", (_now(), order_id))
    return {"id": eid, "order_id": order_id, "timestamp": timestamp,
            "location": location, "description": description}


def get_tracking_events(order_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM logistics_events WHERE order_id=? ORDER BY timestamp DESC",
            (order_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def save_tracking_result(order_id: str, events: list[dict], current_status: str) -> None:
    """将 17TRACK / AfterShip 返回的轨迹批量写入。"""
    with _conn() as conn:
        for e in events:
            eid = f"le_{uuid.uuid4().hex[:8]}"
            conn.execute("INSERT OR IGNORE INTO logistics_events VALUES (?,?,?,?,?,?,?)",
                         (eid, order_id,
                          e.get("timestamp", _now()),
                          e.get("location", ""),
                          e.get("description", e.get("message", "")),
                          e.get("status_code", ""),
                          json.dumps(e, ensure_ascii=False)))
        if current_status in VALID_STATUSES:
            conn.execute("UPDATE logistics_orders SET status=?, updated_at=? WHERE id=?",
                         (current_status, _now(), order_id))


def list_carriers() -> list[dict]:
    return [{"code": k, **v} for k, v in CARRIERS.items()]


# ── 辅助 ─────────────────────────────────────────────────────────────────────

def _row(row) -> dict:
    if not row:
        return {}
    d = dict(row)
    for f in ("dimensions", "metadata"):
        if isinstance(d.get(f), str):
            try: d[f] = json.loads(d[f])
            except: d[f] = {}
    d["insured"] = bool(d.get("insured", 0))
    return d


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


ensure_tables()
