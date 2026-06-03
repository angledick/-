"""RAG pipeline: retrieve + format context for Claude.

1. Query → search vector store for relevant regulation chunks
2. Format results as context string with full source citations
"""

from app.knowledge.store import search, get_document_count


def retrieve_context(query: str, top_k: int = 3) -> list[dict]:
    """Retrieve relevant regulation context for a query.

    Returns:
        List of result dicts: {text, score, regulation_name, source_url, ...}
    """
    if get_document_count() == 0:
        return []
    return search(query, k=top_k)


def format_context_for_assistant(retrieved: list[dict]) -> str:
    """Format retrieved chunks as a prompt context block with source citations.

    Output example:
        ## 相关法规参考 (知识库检索)

        [1] General Product Safety Regulation (GPSR) 2023/988/EU  (相关度: 0.87)
        来源: https://eur-lex.europa.eu/...
        <chunk text>
    """
    if not retrieved:
        return "（知识库中暂未找到相关法规信息）"

    lines = ["## 相关法规参考 (知识库检索)", ""]
    for i, item in enumerate(retrieved, 1):
        name = item.get("regulation_name") or f"市场: {item.get('market', '')}"
        score = item.get("score", 0)
        lines.append(f"**[{i}]** {name}  (相关度: {score:.2f})")

        url = item.get("source_url", "")
        if url:
            lines.append(f"来源: {url}")

        eff = item.get("effective_date", "")
        if eff:
            lines.append(f"生效: {eff}")

        lines.append("")
        lines.append(item["text"])
        lines.append("")

    return "\n".join(lines)


def enrich_with_rag(query: str) -> str:
    """Full RAG enrichment: retrieve → format → return context string."""
    retrieved = retrieve_context(query)
    return format_context_for_assistant(retrieved)
