"""通知渠道配置存储 — SQLite。

支持渠道：feishu（飞书）、wecom（企业微信）
每个用户可配置多个渠道，每个渠道独立开关。
"""

import json
import sqlite3
import time
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "sessions.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(_DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def _init():
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS notify_channels (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            channel     TEXT NOT NULL,        -- feishu | wecom
            name        TEXT NOT NULL,        -- 用户自定义名称，如"合规预警群"
            webhook_url TEXT NOT NULL,
            enabled     INTEGER DEFAULT 1,
            min_level   TEXT DEFAULT 'medium', -- low | medium | high | critical
            updated_at  INTEGER NOT NULL
        );
        """)
        conn.commit()


_init()

import uuid as _uuid


def list_channels(user_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM notify_channels WHERE user_id=? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_channel(channel_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM notify_channels WHERE id=?", (channel_id,)).fetchone()
    return dict(row) if row else None


def upsert_channel(user_id: str, channel: str, name: str, webhook_url: str,
                   enabled: bool = True, min_level: str = "medium",
                   channel_id: str | None = None) -> dict:
    cid = channel_id or str(_uuid.uuid4())
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO notify_channels "
            "(id, user_id, channel, name, webhook_url, enabled, min_level, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (cid, user_id, channel, name, webhook_url, int(enabled), min_level, int(time.time())),
        )
        conn.commit()
    return get_channel(cid)  # type: ignore


def delete_channel(channel_id: str) -> bool:
    with _conn() as conn:
        cur = conn.execute("DELETE FROM notify_channels WHERE id=?", (channel_id,))
        conn.commit()
    return cur.rowcount > 0


def set_enabled(channel_id: str, enabled: bool) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE notify_channels SET enabled=?, updated_at=? WHERE id=?",
            (int(enabled), int(time.time()), channel_id),
        )
        conn.commit()


def get_active_channels(user_id: str, severity: str = "medium") -> list[dict]:
    """返回所有已启用且 min_level ≤ severity 的渠道。"""
    _LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    sev_val = _LEVEL_ORDER.get(severity, 1)
    channels = list_channels(user_id)
    return [
        c for c in channels
        if c["enabled"] and _LEVEL_ORDER.get(c["min_level"], 1) <= sev_val
    ]
