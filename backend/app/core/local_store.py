"""
自然语言本地存储 (NLStore) — 以自然语言为核心的本地文件存储层。

所有数据以 "自然语言描述 + 结构化元数据" 的格式存储，
人可直接阅读，机器可高效检索。

支持：
- 按 namespace 组织（products / sessions / memories / strategies）
- CRUD 操作（创建、读取、更新、删除、列出）
- 全文内容搜索
- 键值对与自然语言混合模式

存储方式：JSON 文件，按 namespace 目录组织。
"""

import json
import uuid
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Any

from app.config import settings

# ── 存储根目录 ──
NL_STORE_DIR = Path(settings.data_dir) / "nl_store"


class NLRecord:
    """
    自然语言存储记录。

    每条记录包含：
    - title: 短标题（一目了然）
    - content_nl: 自然语言正文（人可读）
    - metadata: 结构化元数据（机器可读）
    - tags: 标签（用于分类和检索）
    """

    def __init__(
        self,
        namespace: str,
        key: str,
        title: str,
        content_nl: str,
        metadata: Optional[dict] = None,
        tags: Optional[list[str]] = None,
    ):
        self.record_id = f"rec_{uuid.uuid4().hex[:8]}"
        self.namespace = namespace
        self.key = key
        self.title = title
        self.content_nl = content_nl
        self.metadata = metadata or {}
        self.tags = tags or []
        self.created_at: str = datetime.now(timezone.utc).isoformat()
        self.updated_at: str = self.created_at

    def update(self, **kwargs) -> None:
        """更新记录字段。"""
        for field in ("title", "content_nl", "metadata", "tags"):
            if field in kwargs:
                setattr(self, field, kwargs[field])
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "namespace": self.namespace,
            "key": self.key,
            "title": self.title,
            "content_nl": self.content_nl,
            "metadata": self.metadata,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class NLStore:
    """
    自然语言本地存储层。

    用法:
        store = NLStore()

        # 写入
        store.put(
            namespace="products",
            key="电子产品_德国",
            title="电子产品出口德国合规要求",
            content_nl="电子产品出口德国需要CE认证、WEEE注册...",
            tags=["电子产品", "德国", "CE认证"],
        )

        # 读取
        record = store.get("products", "电子产品_德国")
        print(record.content_nl)

        # 搜索
        results = store.search("CE认证")
        for r in results:
            print(r["title"], r["content_nl"][:100])

        # 列出
        all_products = store.list_namespace("products")
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self._base_dir = base_dir or NL_STORE_DIR
        self._cache: dict[str, list[NLRecord]] = {}  # namespace -> records

    # ── CRUD ──────────────────────────────────

    def put(
        self,
        namespace: str,
        key: str,
        title: str,
        content_nl: str,
        metadata: Optional[dict] = None,
        tags: Optional[list[str]] = None,
    ) -> NLRecord:
        """创建或更新一条记录。"""
        existing = self._find_local(namespace, key)
        if existing:
            existing.update(
                title=title,
                content_nl=content_nl,
                metadata=metadata,
                tags=tags,
            )
            record = existing
        else:
            record = NLRecord(
                namespace=namespace,
                key=key,
                title=title,
                content_nl=content_nl,
                metadata=metadata,
                tags=tags,
            )
            self._cache.setdefault(namespace, []).append(record)
        self._save_namespace(namespace)
        return record

    def get(self, namespace: str, key: str) -> Optional[NLRecord]:
        """按 namespace + key 读取记录。"""
        return self._find_local(namespace, key)

    def delete(self, namespace: str, key: str) -> bool:
        """删除一条记录。"""
        records = self._cache.get(namespace, [])
        for i, r in enumerate(records):
            if r.key == key:
                records.pop(i)
                self._save_namespace(namespace)
                return True
        return False

    def list_namespace(self, namespace: str) -> list[dict]:
        """列出某个 namespace 下所有记录摘要。"""
        self._load_namespace(namespace)
        return [
            {
                "key": r.key,
                "title": r.title,
                "tags": r.tags,
                "updated_at": r.updated_at,
            }
            for r in self._cache.get(namespace, [])
        ]

    # ── 搜索 ──────────────────────────────────

    def search(
        self,
        query: str,
        namespace: Optional[str] = None,
        max_results: int = 20,
    ) -> list[dict]:
        """
        全内容搜索（匹配 title + content_nl + tags）。
        基于简单的关键词/短语匹配，无需向量索引。

        参数:
            query: 搜索关键词
            namespace: 可选，限定搜索范围
            max_results: 最大结果数
        """
        keywords = re.findall(r"[\w\u4e00-\u9fff]+", query.lower())
        results = []

        namespaces = [namespace] if namespace else list(
            p.stem for p in self._base_dir.glob("*") if p.is_dir()
        )

        for ns in namespaces:
            self._load_namespace(ns)
            for record in self._cache.get(ns, []):
                text = (
                    record.title.lower()
                    + " "
                    + record.content_nl.lower()
                    + " "
                    + " ".join(record.tags).lower()
                )
                score = sum(1 for kw in keywords if kw in text)
                if score > 0:
                    results.append({
                        "namespace": ns,
                        "key": record.key,
                        "title": record.title,
                        "content_preview": record.content_nl[:150] + ("..." if len(record.content_nl) > 150 else ""),
                        "tags": record.tags,
                        "score": score,
                        "updated_at": record.updated_at,
                    })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]

    # ── 持久化 ──────────────────────────────────

    def _save_namespace(self, namespace: str) -> None:
        """将某个 namespace 的所有记录写入文件。"""
        ns_dir = self._base_dir / namespace
        ns_dir.mkdir(parents=True, exist_ok=True)
        records = self._cache.get(namespace, [])
        data = [r.to_dict() for r in records]
        # 写入一个合并文件，方便整体查看
        with open(ns_dir / "_all.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # 同时每一条记录单独写入，便于直接查看
        for r in records:
            path = ns_dir / f"{r.key}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(r.to_dict(), f, ensure_ascii=False, indent=2)

    def _load_namespace(self, namespace: str) -> None:
        """从文件加载某个 namespace 的记录。"""
        if namespace in self._cache and not self._cache[namespace]:
            return
        ns_dir = self._base_dir / namespace
        if not ns_dir.exists():
            self._cache[namespace] = []
            return
        all_path = ns_dir / "_all.json"
        if not all_path.exists():
            self._cache[namespace] = []
            return
        try:
            with open(all_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            records = []
            for item in data:
                record = NLRecord(
                    namespace=item["namespace"],
                    key=item["key"],
                    title=item["title"],
                    content_nl=item["content_nl"],
                    metadata=item.get("metadata"),
                    tags=item.get("tags", []),
                )
                record.record_id = item["record_id"]
                record.created_at = item["created_at"]
                record.updated_at = item["updated_at"]
                records.append(record)
            self._cache[namespace] = records
        except Exception:
            self._cache[namespace] = []

    def _find_local(self, namespace: str, key: str) -> Optional[NLRecord]:
        """在缓存中查找记录。"""
        self._load_namespace(namespace)
        for r in self._cache.get(namespace, []):
            if r.key == key:
                return r
        return None


# ── 全局单例 ──────────────────────────────

_store_instance: Optional[NLStore] = None


def get_store() -> NLStore:
    """获取全局 NLStore 实例（懒加载单例）。"""
    global _store_instance
    if _store_instance is None:
        _store_instance = NLStore()
    return _store_instance
