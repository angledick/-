"""会话持久化存储 — SQLite。

数据模型:
  sessions  (id, title, created_at, updated_at)
  messages  (id, session_id, role, content,
             compliance_result_json, intent_json,
             sources_json, created_at)

数据库文件: data/sessions.db
"""

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional

from app.config import settings

_DB_PATH = Path(settings.data_dir) / "sessions.db"
_conn: Optional[sqlite3.Connection] = None


def close_conn():
    """关闭全局 SQLite 连接（供测试 / 关闭时调用）。"""
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


# ── 初始化 ────────────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _init_schema(_conn)
    return _conn


def _init_schema(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            created_at  INTEGER NOT NULL,
            updated_at  INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id                      TEXT PRIMARY KEY,
            session_id              TEXT NOT NULL,
            role                    TEXT NOT NULL,
            content                 TEXT NOT NULL,
            compliance_result_json  TEXT,
            intent_json             TEXT,
            sources_json            TEXT,
            created_at              INTEGER NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_updated
            ON sessions(updated_at DESC);
    """)
    conn.commit()
    # 迁移：为旧表增加 user_id 列（若不存在）
    try:
        conn.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT DEFAULT NULL")
        conn.commit()
    except Exception:
        pass  # 列已存在，忽略


# ── 会话 CRUD ─────────────────────────────────────────────────────────────────

def create_session(title: str, user_id: Optional[str] = None) -> str:
    """创建新会话，返回 session_id。"""
    conn = _get_conn()
    sid = str(uuid.uuid4())
    now = int(time.time())
    conn.execute(
        "INSERT INTO sessions (id, title, created_at, updated_at, user_id) VALUES (?,?,?,?,?)",
        (sid, title[:80], now, now, user_id),
    )
    conn.commit()
    return sid


def list_sessions(limit: int = 50, user_id: Optional[str] = None) -> list[dict]:
    """返回最近 N 条会话摘要（按 updated_at 降序）。user_id 不为 None 时过滤。"""
    conn = _get_conn()
    if user_id:
        rows = conn.execute(
            """
            SELECT s.id, s.title, s.created_at, s.updated_at,
                   COUNT(m.id) AS message_count,
                   MAX(CASE WHEN m.role='user' THEN m.content END) AS last_user_msg
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            WHERE s.user_id = ?
            GROUP BY s.id
            ORDER BY s.updated_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT s.id, s.title, s.created_at, s.updated_at,
                   COUNT(m.id) AS message_count,
                   MAX(CASE WHEN m.role='user' THEN m.content END) AS last_user_msg
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            GROUP BY s.id
            ORDER BY s.updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    result = []
    for r in rows:
        preview = (r["last_user_msg"] or "")[:60]
        result.append({
            "id": r["id"],
            "title": r["title"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "message_count": r["message_count"],
            "preview": preview,
        })
    return result


def get_session(session_id: str) -> Optional[dict]:
    """返回会话 + 全部消息，若不存在返回 None。"""
    conn = _get_conn()
    session_row = conn.execute(
        "SELECT * FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if not session_row:
        return None

    msg_rows = conn.execute(
        "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    ).fetchall()

    messages = []
    for m in msg_rows:
        messages.append({
            "id": m["id"],
            "role": m["role"],
            "content": m["content"],
            "compliance_result": _load_json(m["compliance_result_json"]),
            "intent": _load_json(m["intent_json"]),
            "sources": _load_json(m["sources_json"]) or [],
            "created_at": m["created_at"],
        })

    return {
        "id": session_row["id"],
        "title": session_row["title"],
        "created_at": session_row["created_at"],
        "updated_at": session_row["updated_at"],
        "user_id": session_row["user_id"] if "user_id" in session_row.keys() else None,
        "messages": messages,
    }


def get_recent_messages(session_id: str, n: int = 6) -> list[dict]:
    """获取会话最近 N 条消息（供多轮上下文传递）。"""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT role, content FROM messages
        WHERE session_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (session_id, n),
    ).fetchall()
    # 逆序还原时间顺序
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def add_message(
    session_id: str,
    role: str,
    content: str,
    compliance_result: Optional[dict] = None,
    intent: Optional[dict] = None,
    sources: Optional[list] = None,
) -> str:
    """向会话添加一条消息，返回 message_id。同步更新 session.updated_at。"""
    conn = _get_conn()
    mid = str(uuid.uuid4())
    now = int(time.time())
    conn.execute(
        """
        INSERT INTO messages
            (id, session_id, role, content,
             compliance_result_json, intent_json, sources_json, created_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            mid, session_id, role, content,
            _dump_json(compliance_result),
            _dump_json(intent),
            _dump_json(sources or []),
            now,
        ),
    )
    conn.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id)
    )
    conn.commit()
    return mid


def delete_session(session_id: str) -> bool:
    """删除会话及其全部消息。返回是否成功删除（存在则 True）。"""
    conn = _get_conn()
    cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    return cur.rowcount > 0


def update_session_title(session_id: str, title: str):
    """更新会话标题。"""
    conn = _get_conn()
    conn.execute(
        "UPDATE sessions SET title = ? WHERE id = ?",
        (title[:80], session_id),
    )
    conn.commit()


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _dump_json(obj) -> Optional[str]:
    return json.dumps(obj, ensure_ascii=False) if obj is not None else None


def _load_json(s: Optional[str]):
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None
