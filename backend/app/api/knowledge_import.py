"""知识库导入 API。

POST /api/v1/knowledge/upload         上传 PDF，后台向量化
POST /api/v1/knowledge/url            导入 URL，后台抓取 + 向量化
GET  /api/v1/knowledge/docs           列出已导入文档
DELETE /api/v1/knowledge/docs/{id}    删除文档（含 ChromaDB 向量）
GET  /api/v1/knowledge/stats          索引统计
POST /api/v1/knowledge/search         语义搜索预览（测试 RAG）
"""

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.services.doc_processor import process_pdf, process_url
from app.storage.knowledge_doc_store import (
    create_doc, list_docs, get_doc, delete_doc, update_status, get_stats,
)
from app.knowledge.store import upsert_documents, get_document_count, clear_collection, search

log = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge", tags=["knowledge"])

_ALLOWED_MIME = {"application/pdf", "application/octet-stream"}
_MAX_SIZE_MB  = 30


# ── 辅助：向量化并写入 ChromaDB ───────────────────────────────────────

def _index_chunks(doc_id: str, chunks: list[dict], market: str) -> None:
    """同步函数：将 chunks 写入 ChromaDB，更新 SQLite 状态。"""
    try:
        update_status(doc_id, "indexing")
        texts = [c["text"] for c in chunks]
        metas = [
            {
                "doc_id":          doc_id,
                "doc_type":        c.get("doc_type", ""),
                "regulation_name": c.get("regulation_name", c.get("filename", "")),
                "source_url":      c.get("source_url", ""),
                "market":          c.get("market", market),
                "page_hint":       str(c.get("page_hint", "")),
                "effective_date":  "",
                "tags":            "",
            }
            for c in chunks
        ]
        upsert_documents(texts, metas, market=market, regulation_id=doc_id)
        update_status(doc_id, "done", chunk_count=len(chunks))
        log.info("[knowledge] doc_id=%s 向量化完成: %d 块", doc_id, len(chunks))
    except Exception as e:
        log.error("[knowledge] 向量化失败 doc_id=%s: %s", doc_id, e)
        update_status(doc_id, "error", error_msg=str(e)[:200])


# ── 端点 ─────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    market: str = Form(default="custom"),
    regulation_name: str = Form(default=""),
    current_user: dict = Depends(get_current_user),
):
    """上传 PDF 文件，自动分块 + 向量化写入 ChromaDB。"""
    if file.content_type and file.content_type not in _ALLOWED_MIME:
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(400, "仅支持 PDF 文件")

    content = await file.read()
    if len(content) > _MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"文件过大，最大 {_MAX_SIZE_MB}MB")

    name = regulation_name or (file.filename or "未命名文档")
    doc  = create_doc(
        user_id=current_user["id"],
        doc_type="pdf",
        name=name,
        source_url=f"file://{file.filename}",
        market=market,
    )
    doc_id = doc["id"]

    def _run():
        try:
            chunks = process_pdf(content, file.filename or "upload.pdf",
                                 market=market, source_url=f"file://{file.filename}")
            for c in chunks:
                c["regulation_name"] = name
            _index_chunks(doc_id, chunks, market)
        except Exception as e:
            update_status(doc_id, "error", error_msg=str(e)[:200])

    background_tasks.add_task(_run)
    return {"doc_id": doc_id, "name": name, "status": "indexing",
            "message": "PDF 已接收，后台向量化中…"}


@router.post("/url")
async def import_url(
    background_tasks: BackgroundTasks,
    url: str = Form(...),
    market: str = Form(default="custom"),
    regulation_name: str = Form(default=""),
    current_user: dict = Depends(get_current_user),
):
    """从 URL 抓取内容（网页或 PDF），自动向量化。"""
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL 必须以 http:// 或 https:// 开头")

    doc = create_doc(
        user_id=current_user["id"],
        doc_type="url",
        name=regulation_name or url,
        source_url=url,
        market=market,
    )
    doc_id = doc["id"]

    def _run():
        try:
            chunks = process_url(url, market=market, regulation_name=regulation_name)
            _index_chunks(doc_id, chunks, market)
        except Exception as e:
            update_status(doc_id, "error", error_msg=str(e)[:200])

    background_tasks.add_task(_run)
    return {"doc_id": doc_id, "status": "indexing",
            "message": "URL 已接收，后台抓取 + 向量化中…"}


@router.get("/docs")
async def list_documents(
    current_user: dict = Depends(get_current_user),
):
    """列出当前用户已导入的文档。"""
    return list_docs(user_id=current_user["id"])


@router.delete("/docs/{doc_id}")
async def remove_document(
    doc_id: str,
    current_user: dict = Depends(get_current_user),
):
    """删除文档及其 ChromaDB 向量（按 doc_id 过滤删除）。"""
    doc = get_doc(doc_id)
    if not doc or doc["user_id"] != current_user["id"]:
        raise HTTPException(404, "文档不存在")

    # 从 ChromaDB 删除对应向量
    try:
        from app.knowledge.store import _init, _get_ef, get_collection
        market = doc.get("market", "custom")
        col = get_collection(market)
        results = col.get(where={"doc_id": doc_id})
        if results and results.get("ids"):
            col.delete(ids=results["ids"])
            log.info("[knowledge] 从 ChromaDB 删除 %d 块 doc_id=%s", len(results["ids"]), doc_id)
    except Exception as e:
        log.warning("[knowledge] ChromaDB 删除部分失败: %s", e)

    delete_doc(doc_id)
    return {"ok": True, "doc_id": doc_id}


@router.get("/stats")
async def knowledge_stats(
    current_user: dict = Depends(get_current_user),
):
    """知识库统计：文档数、向量块数、各市场分布。"""
    from app.knowledge.market_routing import MARKET_COLLECTIONS
    doc_stats = get_stats(user_id=current_user["id"])

    market_counts: dict[str, int] = {}
    for mkt in list(MARKET_COLLECTIONS.keys()) + ["custom"]:
        try:
            cnt = get_document_count(mkt)
            if cnt > 0:
                market_counts[mkt] = cnt
        except Exception:
            pass

    return {
        **doc_stats,
        "market_distribution": market_counts,
        "total_vectors": sum(market_counts.values()),
    }


class SearchQuery(BaseModel):
    query:  str
    market: str = ""
    top_k:  int = 5


@router.post("/search")
async def preview_search(
    req: SearchQuery,
    current_user: dict = Depends(get_current_user),
):
    """RAG 语义搜索预览：直接查询 ChromaDB，用于验证向量化效果。"""
    results = search(query=req.query, k=req.top_k, market=req.market)
    return {
        "query":   req.query,
        "results": results,
        "count":   len(results),
    }
