"""
L1 知识库增强 — ChromaDB 按市场分 collection。

原方案：单一 collection "astra_knowledge"
新方案：按市场分 collection: "eu_knowledge", "us_knowledge", "jp_knowledge", "kr_knowledge"

数据流转：
  - 读取者: RAG (rag.py)
  - 使用条件: 规则引擎无法覆盖时，检索相关法规知识辅助回答
  - 写入者: init_knowledge.py / scheduler 定时任务
  - 隔离粒度: 按市场分 collection
"""

from typing import Optional


# ── Collection 名称映射 ──────────────────────────

MARKET_COLLECTIONS = {
    "eu": "eu_knowledge",
    "de": "de_knowledge",   # 德国本地法（ElektroG / VerpackG）
    "us": "us_knowledge",
    "jp": "jp_knowledge",
    "kr": "kr_knowledge",
}

# 默认 collection（兼容旧数据）
DEFAULT_COLLECTION = "eu_knowledge"


def get_collection_name(market: str) -> str:
    """根据市场代码获取对应的 ChromaDB collection 名称。

    Args:
        market: 市场代码（eu/us/jp/kr），不区分大小写

    Returns:
        ChromaDB collection 名称
    """
    return MARKET_COLLECTIONS.get(market.lower(), DEFAULT_COLLECTION)


def get_all_collections() -> list[str]:
    """获取所有市场的 collection 名称列表。"""
    return list(MARKET_COLLECTIONS.values())


def detect_market_from_query(query: str) -> str:
    """从查询文本中推断目标市场代码。

    用于 RAG 路由：根据用户提问中的关键词自动选择对应市场的 knowledge collection。

    Args:
        query: 用户查询文本

    Returns:
        市场代码（eu/us/jp/kr）
    """
    query_lower = query.lower()
    # DE 关键词（德国本地法，优先于泛 EU）
    if any(kw in query_lower for kw in ["verpackg", "elektrog", "lucid", "ear基金", "grüner punkt", "包装法注册", "德国包装"]):
        return "de"
    # EU 关键词
    if any(kw in query_lower for kw in ["欧盟", "欧洲", "德国", "法国", "意大利", "荷兰", "比利时", "西班牙", "ce", "weee", "rohs"]):
        return "eu"
    # US 关键词
    if any(kw in query_lower for kw in ["美国", "fcc", "ul", "fda"]):
        return "us"
    # JP 关键词
    if any(kw in query_lower for kw in ["日本", "pse", "vcci"]):
        return "jp"
    # KR 关键词
    if any(kw in query_lower for kw in ["韩国", "kc", "kcc"]):
        return "kr"
    # 默认 EU（最保守）
    return "eu"
