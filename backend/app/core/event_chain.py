"""
事件链 (EventChain) — 记录系统内外部发生的所有重要事件。

每条事件以自然语言描述记录，形成可追溯的事件时间线。
支持：追加事件、按来源/类型/严重度筛选、事件链回溯。

存储方式：JSON 文件，按事件源/日期组织。
"""

import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Literal

from app.config import settings

# ── 存储目录 ──
EVENTS_DIR = Path(settings.data_dir) / "chains" / "events"

Severity = Literal["low", "medium", "high", "critical"]


class EventNode:
    """单个事件节点"""

    def __init__(
        self,
        chain_id: str,
        source: str,
        event_type: str,
        description_nl: str,
        severity: Severity = "medium",
        payload: Optional[dict] = None,
        tags: Optional[list[str]] = None,
    ):
        self.event_id = f"evt_{uuid.uuid4().hex[:8]}"
        self.chain_id = chain_id
        self.source = source
        self.type = event_type
        self.description_nl = description_nl
        self.severity = severity
        self.payload = payload or {}
        self.tags = tags or []
        self.timestamp: str = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "chain_id": self.chain_id,
            "source": self.source,
            "type": self.type,
            "description_nl": self.description_nl,
            "severity": self.severity,
            "payload": self.payload,
            "tags": self.tags,
            "timestamp": self.timestamp,
        }


class EventChain:
    """
    事件链 — 按来源/主题组织的事件序列。

    用法:
        chain = EventChain("eu_regulations_2026")
        chain.add_event(
            source="EU_Official_Journal",
            event_type="regulation_change",
            description_nl="欧盟更新GPSR法规...",
            severity="high",
            tags=["欧盟", "GPSR"],
        )
        chain.save()

        # 筛选高严重度事件
        high = chain.filter(severity="high")
    """

    def __init__(self, chain_id: str):
        self.chain_id = chain_id
        self._events: list[EventNode] = []

    # ── 操作方法 ──────────────────────────────────

    def add_event(
        self,
        source: str,
        event_type: str,
        description_nl: str,
        severity: Severity = "medium",
        payload: Optional[dict] = None,
        tags: Optional[list[str]] = None,
    ) -> EventNode:
        """添加一个新事件到链尾。"""
        event = EventNode(
            chain_id=self.chain_id,
            source=source,
            event_type=event_type,
            description_nl=description_nl,
            severity=severity,
            payload=payload,
            tags=tags,
        )
        self._events.append(event)
        return event

    # ── 持久化 ──────────────────────────────────

    def save(self) -> None:
        """保存事件链到本地 JSON 文件。"""
        EVENTS_DIR.mkdir(parents=True, exist_ok=True)
        path = EVENTS_DIR / f"{self.chain_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    # ── 查询与筛选 ──────────────────────────────

    def get_events(self) -> list[dict]:
        """获取所有事件。"""
        return [e.to_dict() for e in self._events]

    def filter(
        self,
        source: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[Severity] = None,
        tags: Optional[list[str]] = None,
        max_count: int = 100,
    ) -> list[dict]:
        """按条件筛选事件。"""
        results = self._events
        if source:
            results = [e for e in results if e.source == source]
        if event_type:
            results = [e for e in results if e.type == event_type]
        if severity:
            results = [e for e in results if e.severity == severity]
        if tags:
            results = [e for e in results if any(t in e.tags for t in tags)]
        return [e.to_dict() for e in results[:max_count]]

    def get_timeline(self) -> list[str]:
        """
        获取自然语言事件时间线（用于展示）。
        结果示例:
          [
            "🔴 [高] 2026-05-24 欧盟更新GPSR法规，新增电子产品附加安全要求",
            "🟡 [中] 2026-05-23 CE认证申请流程更新，增加能效报告要求",
          ]
        """
        timeline = []
        icons = {"critical": "🚨", "high": "🔴", "medium": "🟡", "low": "🟢"}
        for e in sorted(self._events, key=lambda x: x.timestamp, reverse=True):
            icon = icons.get(e.severity, "⚪")
            ts = e.timestamp[:19]  # trim to seconds
            timeline.append(f"{icon} [{e.severity.title()}] {ts} {e.description_nl}")
        return timeline

    def to_dict(self) -> dict:
        return {
            "chain_id": self.chain_id,
            "total_events": len(self._events),
            "events": self.get_events(),
            "timeline": self.get_timeline(),
        }

    # ── 类方法：加载已有链 ──────────────────────

    @classmethod
    def load(cls, chain_id: str) -> Optional["EventChain"]:
        """从本地 JSON 文件加载已有事件链。"""
        path = EVENTS_DIR / f"{chain_id}.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        chain = cls(chain_id=chain_id)
        for e in data.get("events", []):
            event = EventNode(
                chain_id=chain_id,
                source=e["source"],
                event_type=e["type"],
                description_nl=e["description_nl"],
                severity=e.get("severity", "medium"),
                payload=e.get("payload"),
                tags=e.get("tags"),
            )
            event.event_id = e["event_id"]
            event.timestamp = e["timestamp"]
            chain._events.append(event)
        return chain

    @classmethod
    def list_chains(cls, max_count: int = 20) -> list[dict]:
        """列出最近的事件链摘要。"""
        path = EVENTS_DIR
        if not path.exists():
            return []
        files = sorted(path.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        summaries = []
        for f in files[:max_count]:
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                summaries.append({
                    "chain_id": data.get("chain_id", f.stem),
                    "total_events": data.get("total_events", 0),
                    "timeline_preview": data.get("timeline", [])[:3],
                    "updated_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                })
            except Exception:
                continue
        return summaries
