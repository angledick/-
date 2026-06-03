"""
Tools CRUD API — 前端ToolPanel操作的后端支持。

端点:
  GET    /api/v1/tools              — Tools列表
  POST   /api/v1/tools              — 创建Tool
  GET    /api/v1/tools/{tool_id}    — Tool详情
  PUT    /api/v1/tools/{tool_id}    — 更新Tool
  DELETE /api/v1/tools/{tool_id}    — 删除Tool
  PUT    /api/v1/tools/{tool_id}/toggle — 启用/禁用Tool

参考: 路线图§6.9.2 Tools CRUD API
"""

import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.config import settings

DATA_DIR = Path(settings.data_dir)
TOOLS_FILE = DATA_DIR / "config" / "tools.json"

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


# ── 请求模型 ──────────────────────────────────

class ToolCreate(BaseModel):
    name: str
    description: str = ""
    tool_type: str = "custom"       # builtin/custom/skill_wrapper
    category: str = "general"       # compliance/logistics/certification/general
    config: Dict[str, Any] = {}
    enabled: bool = True


class ToolUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


# ── 辅助函数 ──────────────────────────────────

def _load_tools() -> List[Dict[str, Any]]:
    """加载Tools列表"""
    if not TOOLS_FILE.exists():
        return _init_default_tools()
    try:
        data = json.loads(TOOLS_FILE.read_text(encoding="utf-8"))
        return data.get("tools", [])
    except Exception:
        return []


def _save_tools(tools: List[Dict[str, Any]]):
    """保存Tools列表"""
    TOOLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOOLS_FILE.write_text(
        json.dumps({"tools": tools}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _init_default_tools() -> List[Dict[str, Any]]:
    """初始化默认Tools"""
    defaults = [
        {
            "id": "tool_compliance_check",
            "name": "合规检查",
            "description": "执行六阶段合规流水线检查",
            "tool_type": "builtin",
            "category": "compliance",
            "config": {"pipeline_mode": "6step", "auto_notify": True},
            "enabled": True,
        },
        {
            "id": "tool_cert_monitor",
            "name": "认证监控",
            "description": "监控产品认证到期状态",
            "tool_type": "builtin",
            "category": "certification",
            "config": {"advance_days": 30, "check_interval": "daily"},
            "enabled": True,
        },
        {
            "id": "tool_hs_lookup",
            "name": "HS编码查询",
            "description": "查询产品HS编码和关税税率",
            "tool_type": "builtin",
            "category": "compliance",
            "config": {"data_source": "hs_codes.json"},
            "enabled": True,
        },
        {
            "id": "tool_vat_query",
            "name": "VAT税率查询",
            "description": "查询各国VAT税率及IOSS规则",
            "tool_type": "builtin",
            "category": "compliance",
            "config": {"data_source": "vat_rates.json"},
            "enabled": True,
        },
        {
            "id": "tool_regulation_scan",
            "name": "法规变更扫描",
            "description": "扫描目标市场法规变更",
            "tool_type": "builtin",
            "category": "compliance",
            "config": {"scan_interval": "hourly", "markets": ["EU", "US"]},
            "enabled": True,
        },
        {
            "id": "tool_tracking_query",
            "name": "物流追踪",
            "description": "跨境物流单号追踪查询",
            "tool_type": "builtin",
            "category": "logistics",
            "config": {"provider": "17track", "free_tier": True},
            "enabled": True,
        },
    ]

    _save_tools(defaults)
    return defaults


# ── 端点 ──────────────────────────────────

@router.get("", summary="Tools列表")
async def list_tools(
    category: Optional[str] = None,
    enabled: Optional[bool] = None,
):
    """获取Tools列表"""
    tools = _load_tools()

    if category:
        tools = [t for t in tools if t.get("category") == category]
    if enabled is not None:
        tools = [t for t in tools if t.get("enabled") == enabled]

    return {"tools": tools, "total": len(tools)}


@router.post("", summary="创建Tool")
async def create_tool(req: ToolCreate):
    """创建新Tool"""
    tools = _load_tools()

    tool_id = f"tool_{uuid.uuid4().hex[:8]}"
    tool = {
        "id": tool_id,
        "name": req.name,
        "description": req.description,
        "tool_type": req.tool_type,
        "category": req.category,
        "config": req.config,
        "enabled": req.enabled,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    tools.append(tool)
    _save_tools(tools)

    return tool


@router.get("/{tool_id}", summary="Tool详情")
async def get_tool(tool_id: str):
    """获取Tool详情"""
    tools = _load_tools()
    for t in tools:
        if t["id"] == tool_id:
            return t
    raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")


@router.put("/{tool_id}", summary="更新Tool")
async def update_tool(tool_id: str, req: ToolUpdate):
    """更新Tool"""
    tools = _load_tools()

    for i, t in enumerate(tools):
        if t["id"] == tool_id:
            if req.name is not None:
                tools[i]["name"] = req.name
            if req.description is not None:
                tools[i]["description"] = req.description
            if req.category is not None:
                tools[i]["category"] = req.category
            if req.config is not None:
                tools[i]["config"] = {**tools[i].get("config", {}), **req.config}
            if req.enabled is not None:
                tools[i]["enabled"] = req.enabled
            tools[i]["updated_at"] = datetime.now(timezone.utc).isoformat()

            _save_tools(tools)
            return tools[i]

    raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")


@router.delete("/{tool_id}", summary="删除Tool")
async def delete_tool(tool_id: str):
    """删除Tool"""
    tools = _load_tools()
    original = len(tools)
    tools = [t for t in tools if t["id"] != tool_id]

    if len(tools) == original:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

    _save_tools(tools)
    return {"deleted": tool_id}


@router.put("/{tool_id}/toggle", summary="启用/禁用Tool")
async def toggle_tool(tool_id: str):
    """切换Tool启用/禁用状态"""
    tools = _load_tools()

    for i, t in enumerate(tools):
        if t["id"] == tool_id:
            tools[i]["enabled"] = not tools[i].get("enabled", True)
            tools[i]["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_tools(tools)
            return {
                "id": tool_id,
                "enabled": tools[i]["enabled"],
                "name": tools[i]["name"],
            }

    raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")
