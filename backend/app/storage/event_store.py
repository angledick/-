"""
L5 事件链层 (Event Store) — 系统事件 + 操作链，合并原有 event_chain + action_chain。

数据流转：
  - 写入者: 全部组件 — chat.py / compliance_rules.py / shopify webhook / scheduler
  - 读取者: 审计追踪 · Dashboard 事件时间线 · 决策回溯
  - 使用条件: 审计 / 事件监控 / 决策链路展示
  - 隔离粒度: 系统事件（全局）+ 操作链（按用户）
"""

import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Literal

from app.config import settings

Severity = Literal["low", "medium", "high", "critical"]


class EventRecord:
    """单条事件/操作记录（统一结构）。"""

    def __init__(
        self,
        event_type: str,
        source: str,
        description_nl: str,
        severity: Severity = "medium",
        payload: Optional[dict] = None,
        tags: Optional[list[str]] = None,
        user_id: str = "",
    ):
        self.event_id = f"evt_{uuid.uuid4().hex[:8]}"
        self.event_type = event_type
        self.source = source
        self.description_nl = description_nl
        self.severity = severity
        self.payload = payload or {}
        self.tags = tags or []
        self.user_id = user_id
        self.timestamp: str = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "description_nl": self.description_nl,
            "severity": self.severity,
            "payload": self.payload,
            "tags": self.tags,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
        }


class EventStore:
    """事件链存储 — 合并系统和用户事件、操作链。"""

    def __init__(self):
        self._system_base = Path(settings.data_dir) / "event_chain" / "system_events"
        self._user_base = Path(settings.data_dir) / "event_chain" / "action_chains"

    # ── 路径 ────────────────────────────────────

    def _system_path(self, chain_id: str) -> Path:
        return self._system_base / f"{chain_id}.json"

    def _user_path(self, user_id: str) -> Path:
        return self._user_base / f"{user_id}.json"

    # ── 系统事件 ──────────────────────────────

    def add_system_event(
        self,
        chain_id: str,
        event_type: str,
        source: str,
        description_nl: str,
        severity: Severity = "medium",
        payload: Optional[dict] = None,
        tags: Optional[list[str]] = None,
    ) -> str:
        """添加一条系统事件（全局可见）。

        数据流时序:
          1. 外部事件发生（法规变更/Shopify webhook）
          2. → 写入 L5 system_events (本方法)
          3. Dashboard 读取 L5 展示事件时间线

        Args:
            chain_id: 事件链 ID（如 "eu_regulations_2026"）
            event_type: 事件类型（regulation_change / cert_update / shopify_webhook）
            source: 事件来源（EU_Official_Journal / Shopify）
            description_nl: 自然语言描述
            severity: 严重度
            payload: 负载数据
            tags: 标签

        Returns:
            event_id
        """
        event = EventRecord(event_type, source, description_nl, severity, payload, tags)
        chain = self._load_system_chain(chain_id)
        chain["events"].append(event.to_dict())
        chain["total_events"] = len(chain["events"])
        chain["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._system_base.mkdir(parents=True, exist_ok=True)
        with open(self._system_path(chain_id), "w", encoding="utf-8") as f:
            json.dump(chain, f, ensure_ascii=False, indent=2)

        return event.event_id

    def add_action_event(
        self,
        user_id: str,
        event_type: str,
        source: str,
        description_nl: str,
        severity: Severity = "medium",
        payload: Optional[dict] = None,
        tags: Optional[list[str]] = None,
    ) -> str:
        """添加一条用户操作事件（关联到用户）。

        数据流时序:
          1. 用户发起合规查询 / 导入 Shopify 产品
          2. 各组件依次执行 → 写入 L5 action_chains (本方法)
          3. 用户回溯决策链路时读取 L5

        Args:
            user_id: 用户标识
            event_type: 操作类型（user_query / rule_check / rag_retrieve / compliance_report）
            source: 来源组件名
            description_nl: 自然语言描述
            severity: 严重度
            payload: 负载数据
            tags: 标签

        Returns:
            event_id
        """
        event = EventRecord(
            event_type, source, description_nl, severity, payload, tags, user_id
        )
        chain = self._load_user_chain(user_id)
        chain["events"].append(event.to_dict())
        chain["total_events"] = len(chain["events"])
        chain["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._user_base.mkdir(parents=True, exist_ok=True)
        with open(self._user_path(user_id), "w", encoding="utf-8") as f:
            json.dump(chain, f, ensure_ascii=False, indent=2)

        return event.event_id

    # ── 读取 ────────────────────────────────────

    def get_system_events(self, chain_id: str) -> list[dict]:
        """获取系统事件链。"""
        chain = self._load_system_chain(chain_id)
        return chain.get("events", [])

    def get_user_events(self, user_id: str) -> list[dict]:
        """获取用户操作链。"""
        chain = self._load_user_chain(user_id)
        return chain.get("events", [])

    def filter_system_events(
        self,
        chain_id: str,
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        severity: Optional[Severity] = None,
        max_count: int = 100,
    ) -> list[dict]:
        """按条件筛选系统事件。"""
        events = self.get_system_events(chain_id)
        if event_type:
            events = [e for e in events if e.get("event_type") == event_type]
        if source:
            events = [e for e in events if e.get("source") == source]
        if severity:
            events = [e for e in events if e.get("severity") == severity]
        return events[:max_count]

    def get_all_chain_ids(self) -> list[str]:
        """列出所有系统事件链 ID。"""
        if not self._system_base.exists():
            return []
        return sorted([f.stem for f in self._system_base.glob("*.json")])

    # ── 内部加载 ──────────────────────────────

    def _load_system_chain(self, chain_id: str) -> dict:
        path = self._system_path(chain_id)
        if not path.exists():
            return {
                "chain_id": chain_id,
                "type": "system",
                "total_events": 0,
                "events": [],
            }
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_user_chain(self, user_id: str) -> dict:
        path = self._user_path(user_id)
        if not path.exists():
            return {
                "user_id": user_id,
                "type": "user_actions",
                "total_events": 0,
                "events": [],
            }
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ── 向后兼容适配 ──────────────────────────

    def migrate_from_old_dirs(self) -> dict:
        """从旧的 data/chains/actions/ 和 data/chains/events/ 迁移数据。

        旧结构（已存在）:
            data/chains/actions/{chain_id}.json
            data/chains/events/{chain_id}.json

        新结构:
            data/event_chain/system_events/{chain_id}.json
            data/event_chain/action_chains/{user_id}.json

        Returns:
            迁移统计
        """
        old_actions = Path(settings.data_dir) / "chains" / "actions"
        old_events = Path(settings.data_dir) / "chains" / "events"
        stats = {"actions_migrated": 0, "events_migrated": 0}

        # 迁移操作链（按文件逐个复制到 system_events）
        if old_actions.exists():
            for f in old_actions.glob("*.json"):
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                chain_id = data.get("chain_id", f.stem)
                dest = self._system_base / f"{chain_id}.json"
                if not dest.exists():
                    self._system_base.mkdir(parents=True, exist_ok=True)
                    with open(dest, "w", encoding="utf-8") as fp:
                        json.dump(data, fp, ensure_ascii=False, indent=2)
                    stats["actions_migrated"] += 1

        # 迁移事件链
        if old_events.exists():
            for f in old_events.glob("*.json"):
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                chain_id = data.get("chain_id", f.stem)
                dest = self._system_base / f"{chain_id}.json"
                if not dest.exists():
                    self._system_base.mkdir(parents=True, exist_ok=True)
                    with open(dest, "w", encoding="utf-8") as fp:
                        json.dump(data, fp, ensure_ascii=False, indent=2)
                    stats["events_migrated"] += 1

        return stats
