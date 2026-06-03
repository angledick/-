"""
记忆树浏览API — 前端Phase 3记忆树层级结构浏览。

端点:
  GET  /api/v1/memory/tree              — 记忆树层级结构
  GET  /api/v1/memory/tree/{node_id}    — 指定记忆节点详情
  POST /api/v1/memory/search            — 语义搜索记忆
  POST /api/v1/memory/export            — 导出Obsidian Wiki格式
  POST /api/v1/memory/fragments         — 追加L0原始片段
  GET  /api/v1/memory/fragments         — 查询L0片段
  GET  /api/v1/memory/summaries         — 查询L1-L3摘要

参考: 指南§6.11.4 产品记忆库, 路线图§6.6.1
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


# ── 请求/响应模型 ──────────────────────────────────

class FragmentCreate(BaseModel):
    product_id: str
    source: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    parent_id: Optional[str] = None


class MemorySearchRequest(BaseModel):
    product_id: str
    query: str
    source: Optional[str] = None
    limit: int = 20


class MemoryExportRequest(BaseModel):
    product_id: str
    output_dir: Optional[str] = None


# ── 记忆树端点 ──────────────────────────────────

@router.get("/namespaces", summary="获取命名空间列表")
async def list_namespaces():
    """获取 NLStore 中所有命名空间"""
    from app.core.local_store import get_store, NL_STORE_DIR
    # 扫描 nl_store 目录获取命名空间
    namespaces: List[str] = []
    if NL_STORE_DIR.exists():
        namespaces = sorted(
            p.name for p in NL_STORE_DIR.iterdir()
            if p.is_dir() and not p.name.startswith('.')
        )
    return {"namespaces": namespaces}


@router.get("/tree", summary="记忆树层级结构")
async def get_memory_tree(
    product_id: str = Query(..., description="产品ID"),
    level: Optional[int] = Query(None, ge=1, le=3, description="摘要层级(1-3)"),
):
    """获取记忆树层级结构（按产品/时间维度）"""
    from app.core.memory_tree import get_memory_tree
    tree = get_memory_tree(product_id)

    structure = tree.get_tree_structure()

    if level:
        # 仅返回指定层级
        filtered = {
            k: v for k, v in structure.items()
            if k == f"L{level}" or k == "L0"
        }
        return {"product_id": product_id, "tree": filtered}

    return {"product_id": product_id, "tree": structure}


@router.get("/tree/{node_id}", summary="记忆节点详情")
async def get_memory_node(
    node_id: str,
    product_id: str = Query(..., description="产品ID"),
):
    """获取指定记忆节点详情与关联事件"""
    from app.core.memory_tree import get_memory_tree
    tree = get_memory_tree(product_id)

    # 尝试从fragments查找
    fragments = tree.get_fragments(limit=1000)
    for f in fragments:
        if f["id"] == node_id:
            return {"type": "fragment", "node": f}

    # 尝试从summaries查找
    for lvl in (1, 2, 3):
        summaries = tree.get_summaries(level=lvl)
        for s in summaries:
            if s["id"] == node_id:
                return {"type": "summary", "node": s}

    raise HTTPException(status_code=404, detail=f"Memory node {node_id} not found")


@router.post("/search", summary="语义搜索记忆")
async def search_memory(req: MemorySearchRequest):
    """语义搜索记忆树（基于关键词匹配 + 全文搜索）"""
    from app.core.memory_tree import get_memory_tree
    tree = get_memory_tree(req.product_id)

    # 全文搜索fragments
    fragments = tree.get_fragments(source=req.source, limit=500)
    query_lower = req.query.lower()
    matched = [
        f for f in fragments
        if query_lower in f.get("content", "").lower()
        or query_lower in f.get("source", "").lower()
    ]

    # 搜索summaries
    summary_matched = []
    for lvl in (1, 2, 3):
        summaries = tree.get_summaries(level=lvl)
        for s in summaries:
            if query_lower in s.get("title", "").lower() or query_lower in s.get("content", "").lower():
                summary_matched.append(s)

    return {
        "product_id": req.product_id,
        "query": req.query,
        "fragments": matched[:req.limit],
        "summaries": summary_matched[:req.limit],
        "total_matches": len(matched) + len(summary_matched),
    }


@router.post("/export", summary="导出Obsidian Wiki")
async def export_memory(req: MemoryExportRequest):
    """导出记忆树为Obsidian Wiki格式"""
    from app.core.memory_tree import get_memory_tree
    from pathlib import Path

    tree = get_memory_tree(req.product_id)
    output_dir = req.output_dir or f"output/wiki/{req.product_id}"

    result = await tree.export_to_obsidian(output_dir)
    return {
        "product_id": req.product_id,
        "output_dir": output_dir,
        "exported": result,
    }


@router.post("/fragments", summary="追加L0原始片段")
async def create_fragment(req: FragmentCreate):
    """追加L0原始片段到记忆树"""
    from app.core.memory_tree import get_memory_tree
    tree = get_memory_tree(req.product_id)

    frag_id = await tree.append_fragment(
        source=req.source,
        content=req.content,
        metadata=req.metadata,
        parent_id=req.parent_id,
    )
    return {"fragment_id": frag_id, "product_id": req.product_id}


@router.get("/fragments", summary="查询L0片段")
async def list_fragments(
    product_id: str = Query(..., description="产品ID"),
    source: Optional[str] = Query(None, description="来源过滤"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """查询L0原始片段"""
    from app.core.memory_tree import get_memory_tree
    tree = get_memory_tree(product_id)

    fragments = tree.get_fragments(source=source, limit=limit, offset=offset)
    total = tree.count_fragments(source=source)

    return {
        "product_id": product_id,
        "fragments": fragments,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/summaries", summary="查询L1-L3摘要")
async def list_summaries(
    product_id: str = Query(..., description="产品ID"),
    level: Optional[int] = Query(None, ge=1, le=3, description="层级过滤"),
):
    """查询L1-L3摘要"""
    from app.core.memory_tree import get_memory_tree
    tree = get_memory_tree(product_id)

    result = {}
    levels = [level] if level else [1, 2, 3]
    for lvl in levels:
        summaries = tree.get_summaries(level=lvl)
        result[f"L{lvl}"] = summaries

    return {"product_id": product_id, "summaries": result}


# ── NLStore catch-all 路由（必须放在最后，避免拦截上方具体路径） ───

@router.get("/{ns}", summary="列出命名空间下记录")
async def list_ns_records(ns: str):
    """列出指定命名空间下的所有 NLRecord"""
    from app.core.local_store import get_store
    store = get_store()
    store._load_namespace(ns)
    records = store._cache.get(ns, [])
    return {"records": [r.to_dict() for r in records]}


@router.get("/{ns}/{key:path}", summary="获取单条记录")
async def get_ns_record(ns: str, key: str):
    """获取指定命名空间下的单条 NLRecord"""
    from app.core.local_store import get_store
    store = get_store()
    record = store.get(ns, key)
    if not record:
        raise HTTPException(status_code=404, detail=f"Record {ns}/{key} not found")
    return record.to_dict()
