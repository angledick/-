"""RAG管理API — /api/v1/rag"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List

from app.models.schemas import RAGStatusResponse, RAGSearchRequest, RAGSearchResult

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


@router.get("/status", response_model=RAGStatusResponse)
async def get_rag_status():
    """获取RAG系统状态"""
    try:
        from app.knowledge.store import get_document_count, _EMBED_MODEL
        from app.knowledge.market_routing import get_all_collections
        from app.config import settings
        import asyncio

        collections = list(get_all_collections())
        # 文档计数获取带超时保护（避免embedding模型加载阻塞）
        try:
            total_docs = await asyncio.wait_for(
                asyncio.to_thread(get_document_count),
                timeout=5.0,
            )
        except (asyncio.TimeoutError, Exception):
            total_docs = -1  # -1 表示未能获取

        return RAGStatusResponse(
            collections=collections,
            total_documents=total_docs,
            embedding_model=_EMBED_MODEL,
            chroma_path=settings.chroma_persist_dir,
            status="healthy" if total_docs >= 0 else "degraded",
        )
    except Exception as e:
        return RAGStatusResponse(status="error", embedding_model=str(e))


@router.post("/search", response_model=List[RAGSearchResult])
async def search_rag(request: RAGSearchRequest):
    """RAG语义搜索"""
    try:
        from app.knowledge.store import search as knowledge_search
        results = knowledge_search(request.query, k=request.top_k, market=request.market or "")
        search_results = []
        for r in results:
            if isinstance(r, dict):
                search_results.append(RAGSearchResult(
                    content=r.get("content", ""),
                    source=r.get("source", ""),
                    market=r.get("market", request.market or ""),
                    score=r.get("score", 0.0),
                    metadata=r.get("metadata", {}),
                ))
            else:
                search_results.append(RAGSearchResult(content=str(r)))
        return search_results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG搜索失败: {str(e)}")


@router.post("/reindex")
async def reindex_rag():
    """重建RAG索引"""
    try:
        from app.knowledge.store import clear_collection, get_or_create_all_collections
        from app.knowledge.market_routing import get_all_collections
        for name in get_all_collections():
            market = name.replace("_knowledge", "")
            clear_collection(market)
        get_or_create_all_collections()
        return {"success": True, "message": "RAG索引重建完成"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG索引重建失败: {str(e)}")


@router.get("/models")
async def get_rag_models():
    """获取RAG模型路由配置"""
    from app.core.model_router import get_model_router
    router = get_model_router()
    embedding = router.route("embedding")
    return {
        "embedding_model": embedding.model_dump(),
        "all_routes": {role: cfg.model_dump() for role, cfg in router.get_all_routes().items()},
    }


@router.get("/token-juice/stats")
async def get_token_juice_stats():
    """获取TokenJuice压缩统计"""
    from app.core.token_juice import get_token_juice
    juice = get_token_juice()
    return juice.get_stats()
