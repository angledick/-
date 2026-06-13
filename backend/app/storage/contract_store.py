"""合同存储层 — SQLite（sessions.db）+ Jinja2 模板渲染。

表：
  contracts         合同主记录
  contract_versions 版本历史
"""

import json
import uuid
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "sessions.db"
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "data" / "contracts" / "templates"


def _conn():
    import sqlite3
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_tables() -> None:
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS contracts (
            id                TEXT PRIMARY KEY,
            product_id        TEXT NOT NULL,
            supplier_id       TEXT NOT NULL,
            contract_type     TEXT NOT NULL DEFAULT 'purchase',
            template_id       TEXT NOT NULL,
            title             TEXT NOT NULL,
            version           INTEGER DEFAULT 1,
            status            TEXT DEFAULT 'draft',
            delivery_term     TEXT DEFAULT 'FOB',
            currency          TEXT DEFAULT 'USD',
            total_amount      REAL DEFAULT 0.0,
            payment_terms     TEXT DEFAULT '',
            delivery_date     TEXT DEFAULT '',
            quality_terms     TEXT DEFAULT '',
            content_html      TEXT DEFAULT '',
            content_vars      TEXT DEFAULT '{}',
            compliance_issues TEXT DEFAULT '[]',
            compliance_score  REAL DEFAULT 0.0,
            parties           TEXT DEFAULT '[]',
            signed_at         TEXT,
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_con_product  ON contracts(product_id);
        CREATE INDEX IF NOT EXISTS idx_con_supplier ON contracts(supplier_id);
        CREATE INDEX IF NOT EXISTS idx_con_status   ON contracts(status);

        CREATE TABLE IF NOT EXISTS contract_versions (
            id          TEXT PRIMARY KEY,
            contract_id TEXT NOT NULL,
            version     INTEGER NOT NULL,
            content_html TEXT DEFAULT '',
            content_vars TEXT DEFAULT '{}',
            change_note TEXT DEFAULT '',
            created_at  TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cv_contract ON contract_versions(contract_id);
        """)


# ── 模板 ─────────────────────────────────────────────────────────────────────

def list_templates() -> list[dict]:
    templates = []
    for f in sorted(_TEMPLATES_DIR.glob("*.html.j2")):
        tid = f.stem.replace(".html", "")
        meta_file = f.with_suffix(".json")
        meta = {}
        if meta_file.exists():
            try: meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except: pass
        templates.append({"id": tid, "name": meta.get("name", tid),
                          "description": meta.get("description", ""),
                          "variables": meta.get("variables", []),
                          "contract_type": meta.get("contract_type", "purchase")})
    return templates


def get_template(template_id: str) -> Optional[dict]:
    f = _TEMPLATES_DIR / f"{template_id}.html.j2"
    if not f.exists():
        return None
    meta_file = f.with_suffix(".json")
    meta = {}
    if meta_file.exists():
        try: meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except: pass
    return {"id": template_id, "content": f.read_text(encoding="utf-8"), **meta}


def render_template(template_id: str, variables: dict) -> str:
    """使用 Jinja2 渲染合同模板。"""
    tmpl = get_template(template_id)
    if not tmpl:
        raise ValueError(f"模板 {template_id} 不存在")
    try:
        from jinja2 import Environment
        env = Environment(autoescape=True)
        t = env.from_string(tmpl["content"])
        return t.render(**variables)
    except ImportError:
        # Jinja2 未安装时简单替换
        html = tmpl["content"]
        for k, v in variables.items():
            html = html.replace("{{ " + k + " }}", str(v))
        return html


# ── CRUD ─────────────────────────────────────────────────────────────────────

def create_contract(data: dict, rendered_html: str = "") -> dict:
    now = _now()
    cid = f"con_{uuid.uuid4().hex[:8]}"
    vars_json = json.dumps(data.get("content_vars", {}), ensure_ascii=False)
    with _conn() as conn:
        conn.execute("""INSERT INTO contracts VALUES (
            ?,?,?,?,?,?,1,'draft',?,?,?,?,?,?,?,?,?,0.0,?,NULL,?,?)""",
            (cid, data["product_id"], data["supplier_id"],
             data.get("contract_type", "purchase"), data["template_id"],
             data.get("title", "采购合同"),
             data.get("delivery_term", "FOB"), data.get("currency", "USD"),
             float(data.get("total_amount", 0)),
             data.get("payment_terms", ""), data.get("delivery_date", ""),
             data.get("quality_terms", ""),
             rendered_html, vars_json,
             json.dumps([], ensure_ascii=False),
             json.dumps(data.get("parties", []), ensure_ascii=False),
             now, now))
        # 写入版本 1
        conn.execute(
            "INSERT INTO contract_versions VALUES (?,?,1,?,?,'初始版本',?)",
            (f"cv_{uuid.uuid4().hex[:8]}", cid, rendered_html, vars_json, now))
    return get_contract(cid)


def get_contract(contract_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone()
    return _row(row) if row else None


def list_contracts(
    product_id: Optional[str] = None,
    supplier_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    clauses, params = [], []
    if product_id:  clauses.append("product_id=?");  params.append(product_id)
    if supplier_id: clauses.append("supplier_id=?"); params.append(supplier_id)
    if status:      clauses.append("status=?");      params.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM contracts {where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()
    return [_row(r) for r in rows]


def update_contract(contract_id: str, updates: dict) -> Optional[dict]:
    allowed = {
        "title","delivery_term","currency","total_amount","payment_terms",
        "delivery_date","quality_terms","content_html","content_vars",
        "status","parties",
    }
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return get_contract(contract_id)
    for f in ("content_vars", "parties"):
        if f in fields and isinstance(fields[f], (dict, list)):
            fields[f] = json.dumps(fields[f], ensure_ascii=False)
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k}=?" for k in fields)
    with _conn() as conn:
        conn.execute(f"UPDATE contracts SET {set_clause} WHERE id=?",
                     list(fields.values()) + [contract_id])
    return get_contract(contract_id)


def save_compliance_review(contract_id: str, issues: list, score: float) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE contracts SET compliance_issues=?, compliance_score=?, updated_at=? WHERE id=?",
            (json.dumps(issues, ensure_ascii=False), score, _now(), contract_id),
        )
        return cur.rowcount > 0


def sign_contract(contract_id: str) -> Optional[dict]:
    now = _now()
    with _conn() as conn:
        conn.execute(
            "UPDATE contracts SET status='signed', signed_at=?, updated_at=? WHERE id=?",
            (now, now, contract_id),
        )
    return get_contract(contract_id)


def get_versions(contract_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM contract_versions WHERE contract_id=? ORDER BY version DESC",
            (contract_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def add_version(contract_id: str, html: str, vars_dict: dict, note: str = "") -> dict:
    """升版并保存新版本快照。"""
    with _conn() as conn:
        cur_ver = conn.execute(
            "SELECT MAX(version) FROM contract_versions WHERE contract_id=?", (contract_id,)
        ).fetchone()[0] or 0
        new_ver = cur_ver + 1
        vid = f"cv_{uuid.uuid4().hex[:8]}"
        now = _now()
        conn.execute("INSERT INTO contract_versions VALUES (?,?,?,?,?,?,?)",
                     (vid, contract_id, new_ver, html,
                      json.dumps(vars_dict, ensure_ascii=False), note, now))
        conn.execute("UPDATE contracts SET version=?, content_html=?, updated_at=? WHERE id=?",
                     (new_ver, html, now, contract_id))
    return {"id": vid, "version": new_ver}


# ── 辅助 ─────────────────────────────────────────────────────────────────────

def _row(row) -> dict:
    if not row:
        return {}
    d = dict(row)
    for f in ("compliance_issues", "parties"):
        if isinstance(d.get(f), str):
            try: d[f] = json.loads(d[f])
            except: d[f] = []
    if isinstance(d.get("content_vars"), str):
        try: d["content_vars"] = json.loads(d["content_vars"])
        except: d["content_vars"] = {}
    return d


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


ensure_tables()
