"""
L4 会话记忆层 (Session Memory) — 维护多轮对话上下文。

数据流转：
  - 读取者: NLU (意图消歧)
  - 使用条件: 需要维持多轮对话上下文时
  - 写入者: chat.py / compliance.py（每轮问答结束）
  - 隔离粒度: 按用户/会话 (user_id / session_id)
  - TTL: 不做 TTL 清理，由业务层控制
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from app.config import settings


class SessionMemory:
    """会话记忆 — 多轮对话的上下文维护。"""

    def __init__(self):
        self._base = Path(settings.data_dir) / "session_memory"

    # ── 路径 ────────────────────────────────────

    def _session_path(self, user_id: str, session_id: str) -> Path:
        return self._base / user_id / "sessions" / f"{session_id}.json"

    # ── 写入 ────────────────────────────────────

    def save_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        compliance_result: Optional[dict] = None,
    ) -> None:
        """保存一轮对话消息。

        数据流时序:
          1. 用户发送消息
          2. NLU 解析（读取 L4 上下文）
          3. ComplianceRules + RAG 执行
          4. 回复组装完成 → 写入 L4 (本方法，保存问答对)
          5. 同时写入 L2 (合规档案) 和 L5 (事件链)

        Args:
            user_id: 用户标识
            session_id: 会话标识
            role: "user" 或 "assistant"
            content: 消息内容
            compliance_result: 关联的合规结果（仅 assistant 消息有此字段）
        """
        session = self._load_session(user_id, session_id)
        entry = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if compliance_result:
            entry["compliance_result"] = compliance_result
        session.setdefault("messages", []).append(entry)
        session["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._save_session(user_id, session_id, session)

    def save_context(
        self,
        user_id: str,
        session_id: str,
        key: str,
        value: str,
    ) -> None:
        """保存会话上下文（如当前产品/国家）。

        Args:
            user_id: 用户标识
            session_id: 会话标识
            key: 上下文键名（如 current_product, current_market）
            value: 上下文值
        """
        session = self._load_session(user_id, session_id)
        session[key] = value
        session["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_session(user_id, session_id, session)

    def _save_session(self, user_id: str, session_id: str, data: dict) -> None:
        dir_path = self._base / user_id / "sessions"
        dir_path.mkdir(parents=True, exist_ok=True)
        path = dir_path / f"{session_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── 读取 ────────────────────────────────────

    def _load_session(self, user_id: str, session_id: str) -> dict:
        path = self._session_path(user_id, session_id)
        if not path.exists():
            return {
                "session_id": session_id,
                "user_id": user_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "messages": [],
            }
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_context(self, user_id: str, session_id: str) -> dict:
        """获取完整会话上下文。

        Args:
            user_id: 用户标识
            session_id: 会话标识

        Returns:
            会话数据（含消息列表 + 上下文键值）
        """
        return self._load_session(user_id, session_id)

    def get_recent_messages(
        self,
        user_id: str,
        session_id: str,
        max_count: int = 10,
    ) -> list[dict]:
        """获取最近的 N 条消息。

        Args:
            user_id: 用户标识
            session_id: 会话标识
            max_count: 最大消息数

        Returns:
            消息列表（最新的在前）
        """
        session = self._load_session(user_id, session_id)
        messages = session.get("messages", [])
        return messages[-max_count:]

    def get_current_product(self, user_id: str, session_id: str) -> str:
        """获取会话当前上下文中的产品名称。"""
        session = self._load_session(user_id, session_id)
        return session.get("current_product", "")

    def get_current_market(self, user_id: str, session_id: str) -> str:
        """获取会话当前上下文中的目标市场。"""
        session = self._load_session(user_id, session_id)
        return session.get("current_market", "")
