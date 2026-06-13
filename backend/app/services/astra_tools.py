"""合规工具定义 — 基于 Claude Agent SDK @tool 装饰器。

每个工具注册为 MCP 工具，通过 create_sdk_mcp_server() 提供给 Claude Agent SDK。
工具内部调用 compliance_rules 函数，使用 L0 数据（通过 registry.raw）。

数据流转:
  - Claude Agent SDK → MCP 协议 → in-process MCP Server → 工具函数 → compliance_rules
  - 所有工具同步执行，由 SDK 自动管理
"""

import json
from typing import Any

from app.core.compliance_rules import (
    lookup_hs,
    lookup_vat,
    get_certifications,
    get_risk_flags,
    get_logistics_flags,
    get_customs_documents,
    get_cultural_notes,
    check_compliance,
)
from app.knowledge.store import retrieve_context

# 延迟导入 claude_agent_sdk（允许在不安装 SDK 时降级）
_tool = None
_create_server = None


def _lazy_import():
    """延迟导入 claude_agent_sdk，避免未安装时崩溃。"""
    global _tool, _create_server
    if _tool is not None:
        return
    try:
        from claude_agent_sdk import tool as _t, create_sdk_mcp_server as _c
        _tool = _t
        _create_server = _c
    except ImportError:
        _tool = None  # 标记不可用


# ── 工具定义（使用 @tool 装饰器）─────────────────────


def _ensure_tools_available():
    _lazy_import()
    if _tool is None:
        raise ImportError("claude-agent-sdk 未安装，无法注册 MCP 工具")


def _to_text_response(data: Any) -> dict:
    """将结果转换为 MCP text content 响应。"""
    return {
        "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}]
    }


# 工具函数懒加载：只有在 SDK 可用时才创建
_COMPLIANCE_TOOLS: list = []


def _register_tools():
    """注册所有合规工具（需 SDK 可用时调用）。"""
    global _COMPLIANCE_TOOLS
    if _COMPLIANCE_TOOLS:
        return _COMPLIANCE_TOOLS
    _lazy_import()
    if _tool is None:
        return []

    from claude_agent_sdk import ToolAnnotations

    @_tool(
        "lookup_hs_code",
        "根据产品名称模糊匹配 HS 编码。返回 HS 编码、中文描述、英文描述和产品类别。",
        {"product_name": str},
        annotations=ToolAnnotations(maxResultSizeChars=2000),
    )
    async def lookup_hs_code(args: dict[str, Any]) -> dict:
        return _to_text_response(lookup_hs(args["product_name"]))

    @_tool(
        "lookup_vat_rate",
        "查询目标国家的标准 VAT 税率。返回百分比数值。",
        {"country": str},
    )
    async def lookup_vat_rate(args: dict[str, Any]) -> dict:
        rate = lookup_vat(args["country"])
        return _to_text_response({"country": args["country"], "vat_rate": rate})

    @_tool(
        "get_certifications",
        "查询目标国家出口所需的产品认证清单。",
        {
            "country": {"type": "string", "description": "目标国家名称（中文），如 德国、法国、美国"},
            "product_hint": {"type": "string", "description": "产品名称（可选，用于筛选相关认证）"},
        },
    )
    async def certifications(args: dict[str, Any]) -> dict:
        certs = get_certifications(args["country"], args.get("product_hint", ""))
        return _to_text_response({"country": args["country"], "certifications": certs})

    @_tool(
        "get_risk_flags",
        "评估产品出口目标国家的合规风险。返回风险提示列表。",
        {"country": str, "product": str},
    )
    async def risk_flags(args: dict[str, Any]) -> dict:
        flags = get_risk_flags(args["country"], args["product"])
        return _to_text_response({"country": args["country"], "product": args["product"], "risk_flags": flags})

    @_tool(
        "check_compliance",
        "运行完整的合规检查：HS 编码查询 + VAT 税率 + 认证要求 + 风险评估 + 出口待办清单。返回完整的合规结果字典。",
        {"product": str, "country": str},
        annotations=ToolAnnotations(maxResultSizeChars=8000),
    )
    async def compliance_check(args: dict[str, Any]) -> dict:
        result = check_compliance(args["product"], args["country"])
        return _to_text_response(result)

    @_tool(
        "retrieve_regulation_context",
        "从法规知识库检索与查询相关的法规条文。返回相关法规文本列表。",
        {
            "query": {"type": "string", "description": "检索查询语句，如 'LED灯 出口 德国 CE认证 要求'"},
            "top_k": {"type": "number", "description": "返回结果数量（默认 3）"},
        },
        annotations=ToolAnnotations(maxResultSizeChars=6000),
    )
    async def regulation_context(args: dict[str, Any]) -> dict:
        results = retrieve_context(args["query"], int(args.get("top_k", 3)))
        return _to_text_response({"results": results})

    @_tool(
        "get_logistics_requirements",
        "查询产品出口目标国家时的物流、运输限制和建议清关材料。",
        {"country": str, "product": str},
    )
    async def logistics_requirements(args: dict[str, Any]) -> dict:
        return _to_text_response({
            "country": args["country"],
            "product": args["product"],
            "logistics_flags": get_logistics_flags(args["country"], args["product"]),
            "customs_documents": get_customs_documents(args["country"], args["product"]),
        })

    @_tool(
        "get_cultural_notes",
        "查询目标市场的标签、本地化和文化注意事项。",
        {"country": str, "product": str},
    )
    async def cultural_notes(args: dict[str, Any]) -> dict:
        notes = get_cultural_notes(args["country"], args["product"])
        return _to_text_response({"country": args["country"], "product": args["product"], "cultural_notes": notes})

    _COMPLIANCE_TOOLS = [
        lookup_hs_code, lookup_vat_rate, certifications,
        risk_flags, compliance_check, regulation_context,
        logistics_requirements, cultural_notes,
    ]
    return _COMPLIANCE_TOOLS


# ── MCP Server 工厂 ───────────────────────────────

_compliance_server = None


def get_compliance_mcp_server():
    """获取合规 MCP Server 配置（单例）。"""
    global _compliance_server
    if _compliance_server is not None:
        return _compliance_server
    _lazy_import()
    if _create_server is None:
        raise ImportError("claude-agent-sdk 未安装")
    tools = _register_tools()
    _compliance_server = _create_server(
        name="compliance",
        version="1.0.0",
        tools=tools,
    )
    return _compliance_server


def get_compliance_tools_raw() -> list:
    """直接获取合规工具列表（无需 MCP Server）。"""
    return _register_tools()


# ── 向后兼容 ───────────────────────────────────────

# 保留 TOOL_FUNCTIONS 映射以供直接调用
TOOL_FUNCTIONS: dict[str, callable] = {
    "lookup_hs_code": lambda args: _to_text_response(lookup_hs(args["product_name"])),
    "lookup_vat_rate": lambda args: _to_text_response({"country": args["country"], "vat_rate": lookup_vat(args["country"])}),
    "get_certifications": lambda args: _to_text_response({
        "country": args["country"],
        "certifications": get_certifications(args["country"], args.get("product_hint", "")),
    }),
    "get_risk_flags": lambda args: _to_text_response(get_risk_flags(args["country"], args["product"])),
    "check_compliance": lambda args: _to_text_response(check_compliance(args["product"], args["country"])),
    "retrieve_regulation_context": lambda args: _to_text_response({
        "results": retrieve_context(args["query"], int(args.get("top_k", 3))),
    }),
    "get_logistics_requirements": lambda args: _to_text_response({
        "country": args["country"],
        "product": args["product"],
        "logistics_flags": get_logistics_flags(args["country"], args["product"]),
        "customs_documents": get_customs_documents(args["country"], args["product"]),
    }),
    "get_cultural_notes": lambda args: _to_text_response(get_cultural_notes(args["country"], args["product"])),
}

ALL_MCP_TOOLS = list(TOOL_FUNCTIONS.keys())

ALL_MCP_TOOL_SCHEMAS = [
    {"name": "lookup_hs_code", "description": "根据产品名称模糊匹配 HS 编码",
     "input_schema": {"type": "object", "properties": {"product_name": {"type": "string"}}}},
    {"name": "lookup_vat_rate", "description": "查询目标国家的标准 VAT 税率",
     "input_schema": {"type": "object", "properties": {"country": {"type": "string"}}}},
    {"name": "get_certifications", "description": "查询目标国家出口所需的产品认证清单",
     "input_schema": {"type": "object", "properties": {"country": {"type": "string"}, "product_hint": {"type": "string"}}}},
    {"name": "check_compliance", "description": "运行完整的合规检查",
     "input_schema": {"type": "object", "properties": {"product": {"type": "string"}, "country": {"type": "string"}}}},
]


def get_tool(name: str) -> dict | None:
    """按名称查找工具定义。"""
    for tool in ALL_MCP_TOOL_SCHEMAS:
        if tool["name"] == name:
            return tool
    return None


async def call_tool(name: str, args: dict) -> Any:
    """异步执行工具函数（向后兼容）。"""
    import asyncio
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        raise ValueError(f"Unknown tool: {name}")
    return await asyncio.to_thread(func, args)
