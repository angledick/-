"""用户持久化存储 — SQLite（复用 sessions.db）。

表结构:
  users (id, username, hashed_pw, role, created_at)

角色: 'admin' | 'user'
"""

import time
import uuid
from typing import Optional

from passlib.context import CryptContext

from app.storage.session_store import _get_conn

_pwd_ctx = CryptContext(schemes=["sha256_crypt"], deprecated="auto")


# ── Schema ────────────────────────────────────────────────────────────────────

def _ensure_table():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          TEXT PRIMARY KEY,
            username    TEXT UNIQUE NOT NULL,
            hashed_pw   TEXT NOT NULL,
            role        TEXT NOT NULL DEFAULT 'user',
            created_at  INTEGER NOT NULL
        )
    """)
    conn.commit()


# ── 密码工具 ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


# ── CRUD ─────────────────────────────────────────────────────────────────────

def create_user(username: str, plain_password: str, role: str = "user") -> dict:
    """创建用户，返回用户 dict。用户名重复时抛出 ValueError。"""
    _ensure_table()
    conn = _get_conn()
    uid = str(uuid.uuid4())
    now = int(time.time())
    hashed = hash_password(plain_password)
    try:
        conn.execute(
            "INSERT INTO users (id, username, hashed_pw, role, created_at) VALUES (?,?,?,?,?)",
            (uid, username, hashed, role, now),
        )
        conn.commit()
    except Exception as e:
        if "UNIQUE" in str(e):
            raise ValueError(f"用户名 '{username}' 已存在")
        raise
    return {"id": uid, "username": username, "role": role, "created_at": now}


def get_user_by_username(username: str) -> Optional[dict]:
    _ensure_table()
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, username, hashed_pw, role, created_at FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[dict]:
    _ensure_table()
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, username, hashed_pw, role, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def list_users() -> list[dict]:
    _ensure_table()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, username, role, created_at FROM users ORDER BY created_at ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def delete_user(user_id: str) -> bool:
    _ensure_table()
    conn = _get_conn()
    cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    return cur.rowcount > 0


def update_role(user_id: str, role: str) -> bool:
    _ensure_table()
    conn = _get_conn()
    cur = conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    conn.commit()
    return cur.rowcount > 0


def update_password(user_id: str, new_plain: str) -> bool:
    _ensure_table()
    conn = _get_conn()
    hashed = hash_password(new_plain)
    cur = conn.execute("UPDATE users SET hashed_pw = ? WHERE id = ?", (hashed, user_id))
    conn.commit()
    return cur.rowcount > 0


def init_admin_if_empty():
    """若 users 表为空，自动创建默认 admin 账号（admin / admin123）。"""
    _ensure_table()
    conn = _get_conn()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        create_user("admin", "admin123", role="admin")
        import logging
        logging.getLogger(__name__).info(
            "已创建默认管理员账号: admin / admin123 — 请登录后立即修改密码！"
        )
