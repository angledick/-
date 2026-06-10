"""ChromaDB vector store for compliance knowledge — multi-collection, cloud embedding.

数据流转:
  L1 知识库层:
    - 按市场分 collection: eu_knowledge, us_knowledge, jp_knowledge, kr_knowledge
    - Embedding: Cloud OpenAI-compatible API（text-embedding-3-small 等）
    - 写入: init_knowledge.py → upsert_documents()
    - 读取: RAG (rag.py) → search()
    - 降级: ChromaDB 不可用 → 返回空结果，不阻塞主流程
"""

import logging

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

from app.config import settings
from app.knowledge.market_routing import get_collection_name, get_all_collections

log = logging.getLogger(__name__)

# 云端 Embedding 模型（通过 settings 配置）
_EMBED_MODEL = ""  # 将在 _get_ef 中从 settings 读取

_client = None
_collections: dict[str, object] = {}
_ef = None   # embedding function（首次使用时懒加载，避免启动时下载模型）


def _get_ef() -> OpenAIEmbeddingFunction:
    """懒加载 cloud embedding function。"""
    global _ef
    if _ef is None:
        api_key = settings.embedding_api_key or settings.anthropic_api_key
        _ef = OpenAIEmbeddingFunction(
            api_key=api_key,
            api_base=settings.embedding_base_url,
            model_name=settings.embedding_model,
        )
        log.info("Cloud embedding 已初始化: model=%s base=%s",
                 settings.embedding_model, settings.embedding_base_url)
    return _ef


def _init():
    """Lazy-init ChromaDB persistent client."""
    global _client
    if _client is not None:
        return
    _client = chromadb.PersistentClient(
        path=settings.chroma_persist_dir,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def get_collection(market: str = "eu"):
    """获取指定市场的 ChromaDB collection（含 embedding function）。"""
    _init()
    name = get_collection_name(market)
    if name not in _collections:
        _collections[name] = _client.get_or_create_collection(
            name=name,
            embedding_function=_get_ef(),
            metadata={"hnsw:space": "cosine", "market": market},
        )
    return _collections[name]


def get_or_create_all_collections() -> dict[str, object]:
    """确保所有市场 collection 存在，返回 {name: collection} 映射。"""
    _init()
    for name in get_all_collections():
        if name not in _collections:
            market_code = name.replace("_knowledge", "")
            _collections[name] = _client.get_or_create_collection(
                name=name,
                embedding_function=_get_ef(),
                metadata={"hnsw:space": "cosine", "market": market_code},
            )
    return _collections


def upsert_documents(
    chunks: list[str],
    metadatas: list[dict],
    market: str = "eu",
    regulation_id: str = "",
):
    """幂等写入文档块到指定市场 collection。

    使用 {regulation_id}_{chunk_index} 作为 ID，重复运行不会产生重复文档。
    Embedding 由 Cloud Embedding API 自动生成。

    Args:
        chunks:        文本块列表
        metadatas:     与 chunks 等长的元数据列表（含 regulation_id / source_url 等）
        market:        市场代码
        regulation_id: 法规 ID，用于构造 chunk ID（为空时用 market_hash）
    """
    if not chunks:
        return
    col = get_collection(market)
    reg_id = regulation_id or metadatas[0].get("regulation_id", market)
    ids = [f"{reg_id}_{i}" for i in range(len(chunks))]
    col.upsert(ids=ids, documents=chunks, metadatas=metadatas)


# 向后兼容旧接口（init_knowledge.py 旧代码可能调用）
def add_documents(
    chunks: list[str],
    embeddings: list[list[float]],
    metadata: list[dict] = None,
    market: str = "eu",
):
    """向后兼容：接受外部 embeddings，但内部实际使用 upsert + 自动 embedding。

    注意: embeddings 参数已被忽略；ChromaDB 使用 Cloud Embedding API 自动向量化。
    """
    col = get_collection(market)
    start = col.count()
    ids = [f"{market}_chunk_{start + i}" for i in range(len(chunks))]
    col.upsert(
        ids=ids,
        documents=chunks,
        metadatas=metadata or [{"market": market}] * len(chunks),
    )


def search(query: str, k: int = 5, market: str = "") -> list[dict]:
    """语义搜索相关法规知识块。

    Args:
        query:  查询文本（中文/英文均可）
        k:      返回最大结果数
        market: 市场代码。为空时自动推断，推断无结果时搜全库

    Returns:
        [{"text", "score", "market", "regulation_name", "source_url", ...}, ...]
    """
    if market:
        col = get_collection(market)
        return _query_col(col, query, k, market)

    from app.knowledge.market_routing import detect_market_from_query
    detected = detect_market_from_query(query)
    results = _query_col(get_collection(detected), query, k, detected)
    if results:
        return results

    # 推断无结果 → 查全库（用 get_collection 触发懒加载，不依赖缓存）
    from app.knowledge.market_routing import MARKET_COLLECTIONS
    all_results: list[dict] = []
    for mkt in MARKET_COLLECTIONS:
        try:
            col = get_collection(mkt)
            all_results.extend(_query_col(col, query, k, mkt))
        except Exception:
            pass
    all_results.sort(key=lambda x: x["score"], reverse=True)
    return all_results[:k]


def _query_col(col, query: str, k: int, market: str) -> list[dict]:
    """内部：对单个 collection 执行语义查询，透传完整 metadata。"""
    try:
        if col.count() == 0:
            return []
        results = col.query(
            query_texts=[query],
            n_results=min(k, col.count()),
            include=["documents", "distances", "metadatas"],
        )
    except Exception as e:
        log.warning("ChromaDB query failed for market=%s: %s", market, e)
        return []

    docs     = results.get("documents", [[]])[0] or []
    dists    = results.get("distances",  [[]])[0] or []
    metas    = results.get("metadatas",  [[]])[0] or []

    items = []
    for doc, dist, meta in zip(docs, dists, metas):
        meta = meta or {}
        items.append({
            "text":             doc,
            "score":            round(1 - dist, 4),
            "market":           meta.get("market", market),
            "regulation_id":    meta.get("regulation_id", ""),
            "regulation_name":  meta.get("regulation_name", ""),
            "source_url":       meta.get("source_url", ""),
            "effective_date":   meta.get("effective_date", ""),
            "tags":             meta.get("tags", ""),
        })
    return items


def get_document_count(market: str = "") -> int:
    """获取文档数（market 为空时返回全库总和）。"""
    from app.knowledge.market_routing import MARKET_COLLECTIONS
    if market:
        try:
            return get_collection(market).count()
        except Exception:
            return 0
    # 必须通过 get_collection() 触发懒加载，不能直接访问 _collections
    total = 0
    for m in MARKET_COLLECTIONS:
        try:
            total += get_collection(m).count()
        except Exception:
            pass
    return total


def clear_collection(market: str = ""):
    """清空指定市场 collection（market 为空时清空全部）。"""
    if market:
        col = get_collection(market)
        ids = col.get()["ids"]
        if ids:
            col.delete(ids=ids)
        return
    for name in get_all_collections():
        col = _collections.get(name)
        if col:
            ids = col.get()["ids"]
            if ids:
                col.delete(ids=ids)
