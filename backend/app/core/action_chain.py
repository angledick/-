"""
操作链 (ActionChain) — 追踪系统每一步操作的完整链路。

每条操作以自然语言描述记录，形成可追溯的决策链条。
支持：追加操作、完成操作、浏览/回溯操作链、可视化链图。

存储方式：JSON 文件，按 session/chain_id 组织。
"""

import json
import uuid
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Any

from app.config import settings

# ── 存储目录 ──
ACTIONS_DIR = Path(settings.data_dir) / "chains" / "actions"


class ActionNode:
    """单个操作节点"""

    def __init__(
        self,
        chain_id: str,
        action_type: str,
        description_nl: str,
        agent: str,
        parent_id: Optional[str] = None,
        input_data: Optional[dict] = None,
        output_data: Optional[dict] = None,
    ):
        self.action_id = f"act_{uuid.uuid4().hex[:8]}"
        self.chain_id = chain_id
        self.parent_id = parent_id
        self.type = action_type
        self.description_nl = description_nl
        self.agent = agent
        self.input = input_data or {}
        self.output = output_data or {}
        self.status: str = "pending"
        self.timestamp: str = datetime.now(timezone.utc).isoformat()
        self.duration_ms: int = 0
        self._start_time: float = 0.0

    def start(self) -> None:
        """标记操作开始（记录计时起点）"""
        self._start_time = time.perf_counter()
        self.status = "running"

    def complete(self, output_data: dict, status: str = "success") -> None:
        """标记操作完成（记录耗时）"""
        if self._start_time:
            self.duration_ms = int((time.perf_counter() - self._start_time) * 1000)
        self.output = output_data
        self.status = status

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "chain_id": self.chain_id,
            "parent_id": self.parent_id,
            "type": self.type,
            "description_nl": self.description_nl,
            "agent": self.agent,
            "input": self.input,
            "output": self.output,
            "status": self.status,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
        }


class ActionChain:
    """
    操作链 — 记录和回溯一次交互中所有操作步骤。

    用法:
        chain = ActionChain("session_xxx")
        a1 = chain.add_action("nlu_parse", "解析用户输入意图...", "NLU")
        a1.start()
        # ... do work ...
        a1.complete({"intent": "export_check"})
        chain.save()

        # 回溯整条链路
        for node in chain.get_chain():
            print(node["description_nl"])
    """

    def __init__(self, chain_id: Optional[str] = None):
        self.chain_id = chain_id or f"chain_{uuid.uuid4().hex[:12]}"
        self._nodes: list[ActionNode] = []
        self._dirty: bool = False

    # ── 操作方法 ──────────────────────────────────

    def add_action(
        self,
        action_type: str,
        description_nl: str,
        agent: str,
        parent_id: Optional[str] = None,
        input_data: Optional[dict] = None,
    ) -> ActionNode:
        """添加一个新操作节点到链尾。"""
        if not parent_id and self._nodes:
            parent_id = self._nodes[-1].action_id
        node = ActionNode(
            chain_id=self.chain_id,
            action_type=action_type,
            description_nl=description_nl,
            agent=agent,
            parent_id=parent_id,
            input_data=input_data,
        )
        self._nodes.append(node)
        self._dirty = True
        return node

    def get_node(self, action_id: str) -> Optional[ActionNode]:
        """按 ID 查找操作节点。"""
        for n in self._nodes:
            if n.action_id == action_id:
                return n
        return None

    # ── 持久化 ──────────────────────────────────

    def save(self) -> None:
        """保存操作链到本地 JSON 文件。"""
        ACTIONS_DIR.mkdir(parents=True, exist_ok=True)
        path = ACTIONS_DIR / f"{self.chain_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        self._dirty = False

    # ── 查询 ──────────────────────────────────

    def get_chain(self) -> list[dict]:
        """获取整条操作链（按时间排序）。"""
        return [n.to_dict() for n in self._nodes]

    def get_trail(self) -> list[str]:
        """
        获取自然语言描述链（用于回溯展示）。
        结果示例:
          [
            "第1步: NLU 解析用户输入 → 产品=电子产品, 国家=德国",
            "第2步: 规则引擎执行合规检查 → HS编码=8542.39, VAT=19%",
            "第3步: RAG 检索法规知识 → 匹配到 CE/WEEE/GDPR 要求",
          ]
        """
        trail = []
        for i, n in enumerate(self._nodes, 1):
            prefix = "✅" if n.status == "success" else "⏳" if n.status == "running" else "❌"
            ms = f" ({n.duration_ms}ms)" if n.duration_ms else ""
            trail.append(f"{prefix} 第{i}步: [{n.agent}] {n.description_nl}{ms}")
        return trail

    def to_dict(self) -> dict:
        return {
            "chain_id": self.chain_id,
            "total_actions": len(self._nodes),
            "status": self._calc_status(),
            "actions": self.get_chain(),
            "trail": self.get_trail(),
        }

    def _calc_status(self) -> str:
        if not self._nodes:
            return "empty"
        statuses = {n.status for n in self._nodes}
        if "failed" in statuses:
            return "failed"
        if "running" in statuses:
            return "running"
        if all(s == "success" for s in statuses):
            return "completed"
        return "partial"

    # ── 类方法：加载已有链 ──────────────────────

    @classmethod
    def load(cls, chain_id: str) -> Optional["ActionChain"]:
        """从本地 JSON 文件加载已有的操作链。"""
        path = ACTIONS_DIR / f"{chain_id}.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        chain = cls(chain_id=chain_id)
        for a in data.get("actions", []):
            node = ActionNode(
                chain_id=chain_id,
                action_type=a["type"],
                description_nl=a["description_nl"],
                agent=a["agent"],
                parent_id=a.get("parent_id"),
                input_data=a.get("input"),
                output_data=a.get("output"),
            )
            node.action_id = a["action_id"]
            node.status = a["status"]
            node.timestamp = a["timestamp"]
            node.duration_ms = a.get("duration_ms", 0)
            chain._nodes.append(node)
        chain._dirty = False
        return chain

    @classmethod
    def list_chains(cls, max_count: int = 20) -> list[dict]:
        """列出最近的操作链摘要。"""
        path = ACTIONS_DIR
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
                    "total_actions": data.get("total_actions", 0),
                    "status": data.get("status", "unknown"),
                    "trail_preview": data.get("trail", [])[:3],
                    "updated_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                })
            except Exception:
                continue
        return summaries
