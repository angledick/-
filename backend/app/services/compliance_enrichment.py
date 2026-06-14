"""商品合规字段自动补足服务。

三层策略：
  1. 本地 HS 编码库匹配（hs_codes.json）— 快速、无需网络
  2. RAG 知识库搜索（法规/认证要求）— 已有 ChromaDB
  3. 在线搜索（Metaso）— 补足未知产品

输出合规字段建议，然后调用 shopify_api.update_product_compliance() 回写。
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# ── HS 编码本地库 ──

_HS_CACHE: Optional[list[dict]] = None
_HS_PATH = Path(settings.data_dir) / "hs_codes.json"


def _load_hs_codes() -> list[dict]:
    """加载本地 HS 编码库（带缓存）。"""
    global _HS_CACHE
    if _HS_CACHE is not None:
        return _HS_CACHE
    if not _HS_PATH.exists():
        logger.warning("HS 编码库不存在: %s", _HS_PATH)
        _HS_CACHE = []
        return _HS_CACHE
    try:
        data = json.loads(_HS_PATH.read_text(encoding="utf-8"))
        _HS_CACHE = data.get("hs_codes", [])
        logger.info("HS 编码库已加载: %d 条", len(_HS_CACHE))
        return _HS_CACHE
    except Exception as e:
        logger.error("加载 HS 编码库失败: %s", e)
        _HS_CACHE = []
        return _HS_CACHE


def match_hs_code(
    title: str = "",
    product_type: str = "",
    tags: str = "",
    vendor: str = "",
) -> Optional[dict]:
    """在本地 HS 编码库中匹配最合适的编码。

    匹配策略：
      1. 精确匹配 category == product_type
      2. 关键词匹配 description_cn / description_en
      3. 标签匹配

    Returns:
        {"code": "9405.40", "description_cn": "...", "description_en": "...", "category": "..."}
        或 None
    """
    codes = _load_hs_codes()
    if not codes:
        return None

    search_text = f"{title} {product_type} {tags} {vendor}".lower()

    # 策略1：product_type 精确匹配 category
    for c in codes:
        if product_type and c.get("category", "").lower() == product_type.lower():
            logger.info("HS 匹配(category精确): %s → %s", product_type, c["code"])
            return c

    # 策略2：关键词匹配描述
    keyword_map = {
        "led": "led",
        "灯": "灯",
        "phone": "智能手机",
        "手机": "智能手机",
        "camera": "摄像",
        "相机": "摄像",
        "battery": "锂",
        "电池": "锂",
        "cotton": "棉",
        "棉": "棉",
        "toy": "玩具",
        "玩具": "玩具",
        "cosmetic": "美容",
        "化妆": "美容",
        "circuit": "集成电路",
        "chip": "集成电路",
        "medical": "医疗",
        "医疗": "医疗",
    }

    for keyword, desc_fragment in keyword_map.items():
        if keyword in search_text:
            for c in codes:
                if desc_fragment in c.get("description_cn", ""):
                    logger.info("HS 匹配(关键词'%s'): %s → %s", keyword, desc_fragment, c["code"])
                    return c

    # 策略3：逐条全文匹配
    for c in codes:
        desc = f"{c.get('description_cn', '')} {c.get('description_en', '')}".lower()
        # 取标题中的前3个字做模糊匹配
        for word in [w for w in search_text.split() if len(w) > 2][:5]:
            if word in desc:
                logger.info("HS 匹配(全文'%s'): %s", word, c["code"])
                return c

    logger.info("HS 匹配未找到: title=%s type=%s", title, product_type)
    return None


# ── RAG 知识库搜索 ──

def search_regulations(
    product_type: str = "",
    market: str = "eu",
    query: str = "",
) -> list[dict]:
    """在 RAG 知识库中搜索适用的法规和认证要求。

    Returns:
        [{"text": "...", "regulation": "CE", "market": "eu", ...}, ...]
    """
    search_query = query or f"{product_type} 合规 认证 要求"
    try:
        from app.knowledge.store import search as rag_search
        results = rag_search(search_query, k=3, market=market)
        logger.info("RAG 搜索完成: query=%s results=%d", search_query, len(results))
        return results
    except Exception as e:
        logger.warning("RAG 搜索失败（可能 ChromaDB 未初始化）: %s", e)
        return []


# ── 在线搜索（Metaso）──

def online_search(query: str, count: int = 3) -> list[dict]:
    """使用 Metaso 在线搜索补充信息。

    Returns:
        [{"title": "...", "content": "...", "url": "..."}, ...]
    """
    api_key = os.environ.get("METASO_API_KEY", "") or getattr(settings, "metaso_api_key", "") or ""
    if not api_key:
        logger.warning("METASO_API_KEY 未配置，跳过在线搜索")
        return []

    tool_path = Path(settings.data_dir) / "tools" / "impl" / "metaso_search.py"
    if not tool_path.exists():
        logger.warning("Metaso 搜索工具不存在: %s", tool_path)
        return []

    try:
        # 调用 CLI 工具
        env = os.environ.copy()
        # 确保 METASO_API_KEY 传入子进程（.env 文件中的值不自动写入 os.environ）
        if not env.get("METASO_API_KEY"):
            env["METASO_API_KEY"] = api_key
        api_url = os.environ.get("METASO_API_URL", "") or getattr(settings, "metaso_api_url", "")
        if api_url and not env.get("METASO_API_URL"):
            env["METASO_API_URL"] = api_url
        result = subprocess.run(
            [sys.executable, str(tool_path), "--query", query, "--count", str(count)],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            results = data.get("results", [])
            logger.info("Metaso 在线搜索完成: query=%s results=%d", query, len(results))
            return results
        else:
            logger.warning("Metaso 搜索返回错误: %s", result.stderr[:200])
            return []
    except Exception as e:
        logger.warning("Metaso 搜索异常: %s", e)
        return []


# ── 综合规补足 ──

async def enrich_product_compliance(
    product_id: int,
    title: str = "",
    product_type: str = "",
    tags: str = "",
    vendor: str = "",
    market: str = "eu",
    use_online: bool = True,
) -> dict:
    """商品合规字段综合补足。

    自动执行：
      1. 本地 HS 编码匹配
      2. RAG 法规搜索
      3. （可选）在线搜索补足
      4. 回写 Shopify 合规字段

    Args:
        product_id: Shopify 商品 ID
        title / product_type / tags / vendor: 商品信息
        market: 目标市场（eu/us/uk/jp/kr）
        use_online: 是否启用在线搜索

    Returns:
        {
            "product_id": 123,
            "hs_code": "9405.40",
            "hs_source": "local_db",
            "regulations": [...],
            "online_results": [...],
            "updated": {"country_code_of_origin": "CN", ...},
            "warnings": [...],
        }
    """
    result: dict[str, Any] = {
        "product_id": product_id,
        "hs_code": None,
        "hs_source": None,
        "regulations": [],
        "online_results": [],
        "updated": {},
        "warnings": [],
    }

    # ── 第1层：本地 HS 编码匹配 ──
    hs = match_hs_code(title=title, product_type=product_type, tags=tags, vendor=vendor)
    if hs:
        result["hs_code"] = hs["code"]
        result["hs_source"] = "local_db"
        result["hs_description"] = hs.get("description_cn", "")
    elif use_online:
        # 本地没匹配到，尝试在线搜索
        online_hs = online_search(
            f"{title} HS code 海关编码 {product_type}",
            count=3,
        )
        if online_hs:
            result["online_results"] = online_hs[:2]
            result["hs_source"] = "online_search (需人工确认)"
            # 尝试从搜索结果中提取 HS 编码
            for item in online_hs:
                content = item.get("content", "") + item.get("title", "")
                import re
                hs_match = re.search(r"\b(\d{4}\.\d{2})\b", content)
                if hs_match:
                    result["hs_code"] = hs_match.group(1)
                    result["hs_source"] = "online_search"
                    break

    # ── 第2层：RAG 法规搜索 ──
    regulations = search_regulations(
        product_type=product_type,
        market=market,
        query=f"{title} {product_type} 合规认证 {market}",
    )
    result["regulations"] = [
        {
            "text": r.get("text", "")[:200] if isinstance(r, dict) else str(r)[:200],
            "source": "rag",
        }
        for r in regulations
    ]

    # ── 第3层：在线搜索补足（如果 RAG 结果不足）──
    if use_online and not regulations:
        online_regs = online_search(
            f"{title} {product_type} 跨境电商 合规 认证要求 {market}",
            count=3,
        )
        result["online_results"].extend(online_regs[:2])

    # ── 回写 Shopify ──
    update_data: dict[str, Any] = {}

    # 原产国：默认中国（跨境电商主要场景）
    update_data["country_code_of_origin"] = "CN"

    # HS 编码
    if result["hs_code"]:
        update_data["harmonized_system_code"] = result["hs_code"]

    if update_data:
        try:
            from app.services.shopify_api import update_product_compliance
            update_result = await update_product_compliance(
                product_id, **update_data,
            )
            result["updated"] = update_data
            result["update_result"] = {
                k: v for k, v in update_result.items()
                if k in ("variant", "warnings")
            }
            if update_result.get("warnings"):
                result["warnings"].extend(update_result["warnings"])
        except Exception as e:
            result["warnings"].append(f"Shopify 更新失败: {e}")

    logger.info(
        "商品 %s 合规补足完成: hs=%s(%s) regs=%d online=%d updated=%s",
        product_id,
        result["hs_code"],
        result["hs_source"],
        len(result["regulations"]),
        len(result["online_results"]),
        list(result["updated"].keys()),
    )
    return result
