"""米塔AI搜索 MCP 工具 — 替代 WebSearch 的联网搜索能力。

为 Claude Agent SDK 注册 metaso_search 工具，通过米塔AI搜索API实现
实时联网搜索，无需依赖 Anthropic 的 WebSearch API。

API 文档: https://metaso.cn/search-api/playground
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# 延迟导入 SDK
_tool = None
_create_server = None


def _lazy_import():
    global _tool, _create_server
    if _tool is not None:
        return
    try:
        from claude_agent_sdk import tool as _t, create_sdk_mcp_server as _c
        _tool = _t
        _create_server = _c
    except ImportError:
        _tool = None


def _to_text_response(data: Any) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}]
    }


_METASO_TOOLS: list = []


def _register_tools():
    """注册米塔搜索工具（需 SDK 可用时调用）。"""
    global _METASO_TOOLS
    if _METASO_TOOLS:
        return _METASO_TOOLS
    _lazy_import()
    if _tool is None:
        return []

    from app.config import settings

    @_tool(
        "metaso_search",
        "联网搜索实时信息。当需要获取最新新闻、法规更新、市场动态等联网信息时使用此工具。返回搜索结果列表（标题、链接、摘要）。",
        {
            "q": {
                "type": "string",
                "description": "搜索查询语句，如 '欧盟 2026年 电子产品 新法规'",
            },
            "count": {
                "type": "number",
                "description": "返回结果数量（1-10，默认5）",
            },
        },
    )
    async def metaso_search(args: dict[str, Any]) -> dict:
        q = args.get("q", "")
        count = min(int(args.get("count", 5)), 10)

        if not q:
            return _to_text_response({"error": "搜索查询不能为空"})

        api_key = settings.metaso_api_key
        api_url = settings.metaso_api_url or "https://metaso.cn/api/v1/search"

        if not api_key:
            return _to_text_response({
                "error": "米塔搜索 API Key 未配置，请在 .env 中设置 METASO_API_KEY",
            })

        import httpx

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "q": q,
            "scope": "all",
            "size": count,
            "searchFile": False,
            "includeSummary": False,
            "conciseSnippet": True,
            "format": "chat_completions",
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(api_url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException:
            return _to_text_response({"error": "米塔搜索请求超时，请稍后重试"})
        except httpx.HTTPStatusError as e:
            return _to_text_response({"error": f"米塔搜索 HTTP 错误: {e.response.status_code}"})
        except Exception as e:
            return _to_text_response({"error": f"米塔搜索请求失败: {str(e)}"})

        # 解析返回
        webpages = data.get("webpages", [])
        results = []
        for wp in webpages:
            results.append({
                "title": wp.get("title", ""),
                "link": wp.get("link", ""),
                "snippet": wp.get("snippet", ""),
                "score": wp.get("score", ""),
            })

        return _to_text_response({
            "query": q,
            "total": len(results),
            "credits_used": data.get("credits", 0),
            "results": results,
        })

    _METASO_TOOLS = [metaso_search]
    logger.info("米塔搜索 MCP 工具已注册")
    return _METASO_TOOLS


# ── MCP Server 工厂 ───────────────────────────────

_metaso_server = None


def get_metaso_mcp_server():
    """获取米塔搜索 MCP Server 配置（单例）。"""
    global _metaso_server
    if _metaso_server is not None:
        return _metaso_server
    _lazy_import()
    if _create_server is None:
        raise ImportError("claude-agent-sdk 未安装")
    tools = _register_tools()
    _metaso_server = _create_server(
        name="metaso_search",
        version="1.0.0",
        tools=tools,
    )
    return _metaso_server
