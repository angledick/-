"""知识库API — /api/v1/knowledge

提供合规法规知识章节的 REST API。
数据来源: data/regulations.md（按 ## 标题分割的 Markdown 文档）
"""

import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.config import settings

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


def _load_sections():
    """解析 regulations.md 为知识章节列表。"""
    path = Path(settings.data_dir) / "regulations.md"
    if not path.exists():
        return []

    text = path.read_text("utf-8")
    # 按 ## 标题分割
    blocks = re.split(r"^## ", text, flags=re.MULTILINE)
    sections = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n", 1)
        title = lines[0].strip()
        content = lines[1].strip() if len(lines) > 1 else ""
        # 提取 tag（标题括号中的内容）
        tags = []
        tag_match = re.search(r"\((.+?)\)", title)
        if tag_match:
            tags.append(tag_match.group(1))
        # 检测市场
        markets = []
        if "欧盟" in content or "EU" in content.upper() or "CE" in content:
            markets.append("eu")
        if "德国" in content:
            markets.append("de")
        if "美国" in content or "FCC" in content or "FDA" in content:
            markets.append("us")
        if "日本" in content or "PSE" in content:
            markets.append("jp")
        sections.append({
            "id": title.lower().replace(" ", "_").replace("(", "").replace(")", ""),
            "title": title,
            "content": f"## {title}\n\n{content}",
            "tags": tags,
            "markets": markets or ["eu"],
            "updated_at": "",
        })
    return sections


_SECTIONS_CACHE: Optional[list] = None


def _get_sections():
    global _SECTIONS_CACHE
    if _SECTIONS_CACHE is None:
        _SECTIONS_CACHE = _load_sections()
    return _SECTIONS_CACHE


@router.get("/sections")
async def list_sections():
    """获取所有法规知识章节"""
    return {"sections": _get_sections()}


@router.get("/sections/{section_id}")
async def get_section(section_id: str):
    """获取指定法规知识章节"""
    for sec in _get_sections():
        if sec["id"] == section_id:
            return sec
    raise HTTPException(status_code=404, detail=f"Section not found: {section_id}")


@router.get("/search")
async def search_knowledge(q: str = Query(..., description="搜索关键词")):
    """搜索法规知识章节内容"""
    if not q:
        return {"results": []}
    q_lower = q.lower()
    results = []
    for sec in _get_sections():
        if q_lower in sec["title"].lower() or q_lower in sec["content"].lower():
            results.append(sec)
    return {"results": results}
