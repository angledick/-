"""用户导入文档的元数据存储 — SQLite。

只记录文档的元信息和向量化状态；实际向量存在 ChromaDB 里。
"""

import json
import sqlite3
import time
import uuid
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "sessions.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(_DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def _init():
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS knowledge_docs (
            id            TEXT PRIMARY KEY,
            user_id       TEXT NOT NULL,
            doc_type      TEXT NOT NULL,        -- pdf | url
            name          TEXT NOT NULL,        -- 用户可见名称
            source_url    TEXT DEFAULT '',      -- 原始 URL 或文件名
            market        TEXT DEFAULT 'custom',
            chunk_count   INTEGER DEFAULT 0,
            status        TEXT DEFAULT 'pending', -- pending | indexing | done | error
            error_msg     TEXT DEFAULT '',
            created_at    INTEGER NOT NULL,
            updated_at    INTEGER NOT NULL
        );
        """)
        conn.commit()


_init()


def create_doc(user_id: str, doc_type: str, name: str,
               source_url: str = "", market: str = "custom") -> dict:
    doc_id = str(uuid.uuid4())
    now = int(time.time())
    with _conn() as conn:
        conn.execute(
            "INSERT INTO knowledge_docs (id,user_id,doc_type,name,source_url,market,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (doc_id, user_id, doc_type, name, source_url, market, now, now),
        )
        conn.commit()
    return get_doc(doc_id)  # type: ignore


def get_doc(doc_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM knowledge_docs WHERE id=?", (doc_id,)).fetchone()
    return dict(row) if row else None


def list_docs(user_id: str | None = None) -> list[dict]:
    with _conn() as conn:
        if user_id:
            rows = conn.execute(
                "SELECT * FROM knowledge_docs WHERE user_id=? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM knowledge_docs ORDER BY created_at DESC",
            ).fetchall()
    return [dict(r) for r in rows]


def update_status(doc_id: str, status: str, chunk_count: int = 0, error_msg: str = "") -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE knowledge_docs SET status=?, chunk_count=?, error_msg=?, updated_at=? WHERE id=?",
            (status, chunk_count, error_msg, int(time.time()), doc_id),
        )
        conn.commit()


def delete_doc(doc_id: str) -> bool:
    with _conn() as conn:
        cur = conn.execute("DELETE FROM knowledge_docs WHERE id=?", (doc_id,))
        conn.commit()
    return cur.rowcount > 0


def get_stats(user_id: str | None = None) -> dict:
    with _conn() as conn:
        q = "SELECT status, COUNT(*) FROM knowledge_docs"
        params: tuple = ()
        if user_id:
            q += " WHERE user_id=?"
            params = (user_id,)
        q += " GROUP BY status"
        rows = conn.execute(q, params).fetchall()

        total_chunks = conn.execute(
            "SELECT SUM(chunk_count) FROM knowledge_docs" +
            (" WHERE user_id=?" if user_id else ""),
            params,
        ).fetchone()[0] or 0

    stats: dict = {"done": 0, "pending": 0, "error": 0, "total_chunks": total_chunks}
    for row in rows:
        stats[row[0]] = row[1]
    stats["total_docs"] = sum(v for k, v in stats.items() if k not in ("total_chunks",))
    return stats
