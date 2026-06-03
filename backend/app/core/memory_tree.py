"""
4层级记忆树 (MemoryTree) — 基于SQLite的产品级记忆存储。

层级结构:
  L0: 原始片段 — 合规检查记录、事件链条目、人工备注、系统日志
  L1: 话题摘要 — WEEE认证到期、欧盟CE标志检查、退货率异常
  L2: 领域概览 — 合规领域、认证领域、订单领域、售后领域
  L3: 全局索引 — 产品整体概况、关键事件时间线、风险状态总览

存储:
  data/products/{product_id}/memory/memory.db

开源参考:
  - OpenHuman 记忆树: 4层级化摘要树 + SQLite存储
  - Obsidian Wiki输出: 导出为.md文件支持双链[[wikilink]]
"""

import sqlite3
import uuid
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from app.config import settings

DATA_DIR = Path(settings.data_dir)


# SQLite Schema
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS fragments (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,
    embedding_id TEXT,
    parent_id TEXT,
    FOREIGN KEY (parent_id) REFERENCES summaries(id)
);

CREATE TABLE IF NOT EXISTS summaries (
    id TEXT PRIMARY KEY,
    level INTEGER NOT NULL CHECK(level IN (1, 2, 3)),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    parent_id TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    child_count INTEGER DEFAULT 0,
    FOREIGN KEY (parent_id) REFERENCES summaries(id)
);

CREATE INDEX IF NOT EXISTS idx_fragments_source ON fragments(source);
CREATE INDEX IF NOT EXISTS idx_fragments_parent ON fragments(parent_id);
CREATE INDEX IF NOT EXISTS idx_fragments_created ON fragments(created_at);
CREATE INDEX IF NOT EXISTS idx_summaries_level ON summaries(level);
CREATE INDEX IF NOT EXISTS idx_summaries_parent ON summaries(parent_id);
"""


class MemoryTree:
    """4层级记忆树 — SQLite存储

    用法:
        tree = MemoryTree("p_led_de_001")

        # 追加原始片段
        await tree.append_fragment(
            source="compliance",
            content="LED灯带通过德国CE认证检查，风险评分15/100",
            metadata={"event_type": "compliance:check_passed"}
        )

        # 获取层级摘要
        l3 = await tree.get_summary(level=3)  # 全局索引
        l2 = await tree.get_summary(level=2)  # 领域概览列表
        l1 = await tree.get_summary(level=1)  # 话题摘要列表

        # 导出Obsidian Wiki
        await tree.export_to_obsidian("output/wiki/")
    """

    def __init__(self, product_id: str, db_path: str = None):
        self.product_id = product_id
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = DATA_DIR / "products" / product_id / "memory" / "memory.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化SQLite数据库"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()

    # ── L0: 原始片段 ──────────────────────────────────

    async def append_fragment(
        self,
        source: str,
        content: str,
        metadata: Dict[str, Any] = None,
        parent_id: str = None,
    ) -> str:
        """追加L0原始片段

        Args:
            source: 来源 (compliance/event/note/manual/system)
            content: 原始内容（建议≤3k tokens）
            metadata: JSON元数据
            parent_id: 聚类归属的L1话题ID
        Returns:
            片段ID
        """
        frag_id = uuid.uuid4().hex[:12]
        meta_json = json.dumps(metadata or {}, ensure_ascii=False, default=str)

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO fragments (id, source, content, metadata, parent_id) VALUES (?, ?, ?, ?, ?)",
                (frag_id, source, content, meta_json, parent_id),
            )
            conn.commit()

        # 异步触发L1摘要更新（简化实现：每10个新片段触发一次）
        await self._maybe_update_summaries(source)

        return frag_id

    def get_fragments(
        self,
        source: str = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """查询L0片段"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if source:
                rows = conn.execute(
                    "SELECT * FROM fragments WHERE source = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (source, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM fragments ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            return [dict(r) for r in rows]

    def count_fragments(self, source: str = None) -> int:
        """统计片段数"""
        with sqlite3.connect(str(self.db_path)) as conn:
            if source:
                return conn.execute(
                    "SELECT COUNT(*) FROM fragments WHERE source = ?", (source,)
                ).fetchone()[0]
            return conn.execute("SELECT COUNT(*) FROM fragments").fetchone()[0]

    # ── L1-L3: 摘要管理 ──────────────────────────────────

    async def upsert_summary(
        self,
        level: int,
        title: str,
        content: str,
        parent_id: str = None,
        summary_id: str = None,
    ) -> str:
        """创建或更新摘要

        Args:
            level: 摘要层级 1/2/3
            title: 摘要标题
            content: 摘要内容
            parent_id: 父摘要ID
            summary_id: 指定ID（更新时）
        """
        sid = summary_id or uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT INTO summaries (id, level, title, content, parent_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       title=excluded.title, content=excluded.content,
                       parent_id=excluded.parent_id, updated_at=excluded.updated_at
                """,
                (sid, level, title, content, parent_id, now, now),
            )

            # 更新父节点的child_count
            if parent_id:
                conn.execute(
                    "UPDATE summaries SET child_count = (SELECT COUNT(*) FROM summaries WHERE parent_id = ?) WHERE id = ?",
                    (parent_id, parent_id),
                )
            conn.commit()

        return sid

    def get_summaries(self, level: int, parent_id: str = None) -> List[Dict[str, Any]]:
        """获取指定层级的摘要列表"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if parent_id:
                rows = conn.execute(
                    "SELECT * FROM summaries WHERE level = ? AND parent_id = ? ORDER BY updated_at DESC",
                    (level, parent_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM summaries WHERE level = ? ORDER BY updated_at DESC",
                    (level,),
                ).fetchall()
            return [dict(r) for r in rows]

    def get_summary_by_id(self, summary_id: str) -> Optional[Dict[str, Any]]:
        """获取摘要详情"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM summaries WHERE id = ?", (summary_id,)).fetchone()
            return dict(row) if row else None

    # ── 层级结构浏览 ──────────────────────────────────

    def get_tree_structure(self) -> Dict[str, Any]:
        """获取记忆树层级结构"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row

            l3 = [dict(r) for r in conn.execute("SELECT * FROM summaries WHERE level = 3").fetchall()]
            l2 = [dict(r) for r in conn.execute("SELECT * FROM summaries WHERE level = 2").fetchall()]
            l1 = [dict(r) for r in conn.execute("SELECT * FROM summaries WHERE level = 1").fetchall()]
            l0_count = conn.execute("SELECT COUNT(*) FROM fragments").fetchone()[0]

        return {
            "product_id": self.product_id,
            "L3_global_index": l3,
            "L2_domain_overview": l2,
            "L1_topic_summary": l1,
            "L0_fragment_count": l0_count,
        }

    def search_fragments(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索记忆片段（LIKE匹配，后续可升级为向量搜索）"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM fragments WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Obsidian Wiki导出 ──────────────────────────────────

    async def export_to_obsidian(self, output_dir: str) -> Dict[str, int]:
        """导出为Obsidian Wiki格式

        生成结构:
          output_dir/
          ├── 00_全局索引.md
          ├── 01_合规领域/
          │   ├── 概览.md
          │   └── WEEE认证到期.md
          ├── 02_认证领域/
          └── ...
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        stats = {"files": 0, "summaries": 0, "fragments": 0}

        # L3 全局索引
        l3_summaries = self.get_summaries(level=3)
        if l3_summaries:
            content = f"# {self.product_id} 全局索引\n\n"
            content += l3_summaries[0]["content"]
            content += f"\n\n---\n更新时间: {l3_summaries[0]['updated_at']}\n"
            (out / "00_全局索引.md").write_text(content, encoding="utf-8")
            stats["files"] += 1

        # L2 领域概览
        l2_summaries = self.get_summaries(level=2)
        for i, summary in enumerate(l2_summaries):
            domain_dir = out / f"{i+1:02d}_{summary['title']}"
            domain_dir.mkdir(exist_ok=True)

            # 领域概览文件
            overview_content = f"# {summary['title']}\n\n{summary['content']}\n"
            overview_content += f"\n---\n更新时间: {summary['updated_at']}\n"
            (domain_dir / "概览.md").write_text(overview_content, encoding="utf-8")
            stats["files"] += 1
            stats["summaries"] += 1

            # L1 话题摘要
            l1_summaries = self.get_summaries(level=1, parent_id=summary["id"])
            for topic in l1_summaries:
                topic_content = f"# {topic['title']}\n\n{topic['content']}\n"
                # 添加双链
                topic_content += f"\n[[{summary['title']}/概览]]\n"
                safe_name = topic["title"].replace("/", "_").replace("\\", "_")[:50]
                (domain_dir / f"{safe_name}.md").write_text(topic_content, encoding="utf-8")
                stats["files"] += 1
                stats["summaries"] += 1

        return stats

    # ── 内部方法 ──────────────────────────────────

    async def _maybe_update_summaries(self, source: str):
        """检查是否需要自动更新摘要"""
        count = self.count_fragments(source)

        # 每10个新片段，自动更新L1话题摘要
        if count % 10 == 0 and count > 0:
            await self._auto_generate_l1_summary(source)

    async def _auto_generate_l1_summary(self, source: str):
        """自动生成L1话题摘要（从最近的片段聚合）"""
        fragments = self.get_fragments(source=source, limit=10)
        if not fragments:
            return

        # 简单聚合：取最近片段的内容前200字符作为摘要
        content_parts = []
        for f in fragments:
            meta = json.loads(f.get("metadata", "{}")) if f.get("metadata") else {}
            content_parts.append(f"- [{f['created_at'][:19]}] {f['content'][:100]}")

        summary_content = "\n".join(content_parts)
        title = f"{source}相关记录（{len(fragments)}条）"

        # 查找或创建对应的L1摘要
        existing = self.get_summaries(level=1)
        matched = [s for s in existing if source in s.get("title", "")]

        if matched:
            await self.upsert_summary(
                level=1,
                title=title,
                content=summary_content,
                parent_id=matched[0].get("parent_id"),
                summary_id=matched[0]["id"],
            )
        else:
            # 先创建L2领域
            l2_list = self.get_summaries(level=2)
            l2_id = None
            for l2 in l2_list:
                if source in l2.get("title", "").lower():
                    l2_id = l2["id"]
                    break

            if not l2_id and l2_list:
                l2_id = l2_list[0]["id"]

            await self.upsert_summary(
                level=1, title=title, content=summary_content, parent_id=l2_id
            )

    def get_stats(self) -> Dict[str, Any]:
        """获取记忆树统计"""
        with sqlite3.connect(str(self.db_path)) as conn:
            l0 = conn.execute("SELECT COUNT(*) FROM fragments").fetchone()[0]
            l1 = conn.execute("SELECT COUNT(*) FROM summaries WHERE level = 1").fetchone()[0]
            l2 = conn.execute("SELECT COUNT(*) FROM summaries WHERE level = 2").fetchone()[0]
            l3 = conn.execute("SELECT COUNT(*) FROM summaries WHERE level = 3").fetchone()[0]

        return {
            "product_id": self.product_id,
            "L0_fragments": l0,
            "L1_topic_summaries": l1,
            "L2_domain_overviews": l2,
            "L3_global_index": l3,
            "total_nodes": l0 + l1 + l2 + l3,
        }


# ── 工厂函数 ──────────────────────────────────

_memory_trees: Dict[str, MemoryTree] = {}


def get_memory_tree(product_id: str) -> MemoryTree:
    """获取产品的记忆树单例"""
    if product_id not in _memory_trees:
        _memory_trees[product_id] = MemoryTree(product_id)
    return _memory_trees[product_id]
