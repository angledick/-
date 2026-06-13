"""报关存储层 — SQLite（sessions.db）。

表：
  customs_declarations  报关单
  tariff_cache          关税税率缓存
"""

import json
import uuid
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "sessions.db"
_TARIFF_FILE = Path(__file__).parent.parent.parent / "data" / "customs" / "tariff_rates.json"


def _conn():
    import sqlite3
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_tables() -> None:
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS customs_declarations (
            id                TEXT PRIMARY KEY,
            product_id        TEXT NOT NULL,
            logistics_id      TEXT,
            mode              TEXT DEFAULT '9610',
            hs_code           TEXT NOT NULL,
            declared_name     TEXT NOT NULL,
            declared_value    REAL DEFAULT 0.0,
            declared_currency TEXT DEFAULT 'USD',
            quantity          INTEGER DEFAULT 1,
            unit              TEXT DEFAULT '件',
            origin_country    TEXT DEFAULT 'CN',
            dest_country      TEXT NOT NULL,
            duty_rate         REAL DEFAULT 0.0,
            calculated_duty   REAL DEFAULT 0.0,
            vat_applicable    INTEGER DEFAULT 0,
            ioss_number       TEXT,
            documents         TEXT DEFAULT '[]',
            compliance_checks TEXT DEFAULT '[]',
            status            TEXT DEFAULT 'draft',
            exception_reason  TEXT,
            submitted_at      TEXT,
            cleared_at        TEXT,
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_cust_product ON customs_declarations(product_id);
        CREATE INDEX IF NOT EXISTS idx_cust_status  ON customs_declarations(status);
        CREATE INDEX IF NOT EXISTS idx_cust_hs      ON customs_declarations(hs_code);
        """)


# ── 关税税率 ──────────────────────────────────────────────────────────────────

_tariff_cache: Optional[dict] = None


def get_tariff_rates() -> dict:
    global _tariff_cache
    if _tariff_cache is None:
        if _TARIFF_FILE.exists():
            try:
                _tariff_cache = json.loads(_TARIFF_FILE.read_text(encoding="utf-8"))
            except Exception:
                _tariff_cache = {}
        else:
            _tariff_cache = {}
    return _tariff_cache


def lookup_duty_rate(hs_code: str, dest_country: str) -> float:
    """查询关税税率（%）。先查本地缓存，返回 0.0 表示未知。"""
    rates = get_tariff_rates()
    # 精确匹配（8位） → 前4位 → 前2位
    for hs in [hs_code, hs_code[:4], hs_code[:2]]:
        r = rates.get(dest_country, {}).get(hs)
        if r is not None:
            return float(r)
    # 全局默认税率
    return float(rates.get(dest_country, {}).get("_default", 0.0))


def check_ioss_applicable(dest_country: str, declared_value_usd: float) -> bool:
    """判断是否需要 IOSS（欧盟 + 单票 ≤ €150）。"""
    EU_COUNTRIES = {
        "AT","BE","BG","CY","CZ","DE","DK","EE","ES","FI",
        "FR","GR","HR","HU","IE","IT","LT","LU","LV","MT",
        "NL","PL","PT","RO","SE","SI","SK",
    }
    EUR_USD_RATE = 1.08  # 近似汇率
    value_eur = declared_value_usd / EUR_USD_RATE
    return dest_country.upper() in EU_COUNTRIES and value_eur <= 150


# ── CRUD ─────────────────────────────────────────────────────────────────────

def create_declaration(data: dict) -> dict:
    now = _now()
    did = f"cust_{uuid.uuid4().hex[:8]}"
    hs = data.get("hs_code", "")
    dest = data.get("dest_country", "")
    value = float(data.get("declared_value", 0))
    duty_rate = lookup_duty_rate(hs, dest)
    calculated_duty = round(value * duty_rate / 100, 2)
    vat_applicable = int(check_ioss_applicable(dest, value))

    with _conn() as conn:
        conn.execute("""INSERT INTO customs_declarations VALUES (
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (did, data["product_id"], data.get("logistics_id"),
             data.get("mode", "9610"), hs,
             data.get("declared_name", ""),
             value, data.get("declared_currency", "USD"),
             int(data.get("quantity", 1)), data.get("unit", "件"),
             data.get("origin_country", "CN"), dest,
             duty_rate, calculated_duty, vat_applicable,
             data.get("ioss_number"),
             json.dumps(data.get("documents", []), ensure_ascii=False),
             json.dumps([], ensure_ascii=False),
             "draft", None, None, None, now, now))
    return get_declaration(did)


def get_declaration(declaration_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM customs_declarations WHERE id=?", (declaration_id,)).fetchone()
    return _row(row) if row else None


def list_declarations(
    product_id: Optional[str] = None,
    status: Optional[str] = None,
    dest_country: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    clauses, params = [], []
    if product_id:   clauses.append("product_id=?");   params.append(product_id)
    if status:       clauses.append("status=?");       params.append(status)
    if dest_country: clauses.append("dest_country=?"); params.append(dest_country)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM customs_declarations {where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()
    return [_row(r) for r in rows]


def save_compliance_checks(declaration_id: str, checks: list[dict]) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE customs_declarations SET compliance_checks=?, updated_at=? WHERE id=?",
            (json.dumps(checks, ensure_ascii=False), _now(), declaration_id),
        )
        return cur.rowcount > 0


def submit_declaration(declaration_id: str) -> Optional[dict]:
    now = _now()
    with _conn() as conn:
        conn.execute(
            "UPDATE customs_declarations SET status='submitted', submitted_at=?, updated_at=? WHERE id=?",
            (now, now, declaration_id),
        )
    return get_declaration(declaration_id)


def update_status(declaration_id: str, status: str, exception_reason: Optional[str] = None) -> Optional[dict]:
    now = _now()
    updates: dict = {"status": status, "updated_at": now}
    if status == "cleared":
        updates["cleared_at"] = now
    if exception_reason:
        updates["exception_reason"] = exception_reason
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with _conn() as conn:
        conn.execute(f"UPDATE customs_declarations SET {set_clause} WHERE id=?",
                     list(updates.values()) + [declaration_id])
    return get_declaration(declaration_id)


def calculate_duty(hs_code: str, dest_country: str, declared_value: float, currency: str = "USD") -> dict:
    """快速关税计算（供 API 直接调用，不写库）。"""
    rate = lookup_duty_rate(hs_code, dest_country)
    duty = round(declared_value * rate / 100, 2)
    ioss = check_ioss_applicable(dest_country, declared_value)
    return {
        "hs_code": hs_code,
        "dest_country": dest_country,
        "declared_value": declared_value,
        "currency": currency,
        "duty_rate_pct": rate,
        "calculated_duty": duty,
        "ioss_applicable": ioss,
        "ioss_tip": "需注册 IOSS 号并预收 VAT，否则买家二次缴税" if ioss else "",
    }


# ── 辅助 ─────────────────────────────────────────────────────────────────────

def _row(row) -> dict:
    if not row:
        return {}
    d = dict(row)
    for f in ("documents", "compliance_checks"):
        if isinstance(d.get(f), str):
            try: d[f] = json.loads(d[f])
            except: d[f] = []
    d["vat_applicable"] = bool(d.get("vat_applicable", 0))
    return d


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


ensure_tables()
