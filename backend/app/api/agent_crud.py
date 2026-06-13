"""
Agent CRUD API — Agent 配置的增删改查。

端点:
  GET    /agents              — Agent 列表（含预览）
  GET    /agents/{agent_id}   — Agent 完整配置
  POST   /agents              — 新建 Agent（admin）
  PUT    /agents/{agent_id}   — 更新 Agent（admin）
  DELETE /agents/{agent_id}   — 删除自定义 Agent（admin）
  PUT    /agents/{agent_id}/toggle — 启用/禁用 Agent（admin）
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.core.auth import get_current_user, require_admin
from app.models.schemas import SDKAgentConfig
from app.storage.agent_config_store import (
    list_agents,
    get_agent,
    upsert_agent,
    delete_agent,
    toggle_agent,
)

router = APIRouter(prefix="/api/v1", tags=["agent-config"])


# ── 请求/响应模型 ─────────────────────────────────────────────────────────────

class AgentResponse(BaseModel):
    id: str
    name: str
    type: str
    description: str
    system_prompt: str
    enabled: bool
    sort_order: int
    sdk_config: SDKAgentConfig = Field(default_factory=SDKAgentConfig)
    created_at: int
    updated_at: int


class AgentListItem(BaseModel):
    """列表视图（不含完整 system_prompt 以节省带宽）"""
    id: str
    name: str
    type: str
    description: str
    system_prompt_preview: str   # 前 80 字
    enabled: bool
    sort_order: int
    sdk_config: SDKAgentConfig = Field(default_factory=SDKAgentConfig)
    created_at: int
    updated_at: int


class AgentUpsertRequest(BaseModel):
    name: str
    type: str
    description: str = ""
    system_prompt: str
    enabled: bool = True
    sort_order: int = 99
    sdk_config: Optional[SDKAgentConfig] = None


class ToggleRequest(BaseModel):
    enabled: bool


# ── 端点 ──────────────────────────────────────────────────────────────────────

@router.get(
    "/agents",
    response_model=list[AgentListItem],
    summary="获取 Agent 配置列表（含预览）",
)
async def get_agents(_user: dict = Depends(get_current_user)):
    agents = list_agents()
    return [
        AgentListItem(
            id=a["id"],
            name=a["name"],
            type=a["type"],
            description=a.get("description", ""),
            system_prompt_preview=a["system_prompt"][:80] + ("…" if len(a["system_prompt"]) > 80 else ""),
            enabled=bool(a["enabled"]),
            sort_order=a.get("sort_order", 99),
            sdk_config=_parse_sdk_config(a.get("sdk_config", "{}")),
            created_at=a["created_at"],
            updated_at=a["updated_at"],
        )
        for a in agents
    ]


@router.get(
    "/agents/{agent_id}",
    response_model=AgentResponse,
    summary="获取 Agent 完整配置（含 system_prompt）",
)
async def get_agent_detail(agent_id: str, _user: dict = Depends(get_current_user)):
    # 排除保留字，避免吞噬 /agents/tasks 等子路由
    if agent_id in ("tasks", "workers", "templates"):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' 不存在")
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return AgentResponse(
        id=agent["id"],
        name=agent["name"],
        type=agent["type"],
        description=agent.get("description", ""),
        system_prompt=agent["system_prompt"],
        enabled=bool(agent["enabled"]),
        sort_order=agent.get("sort_order", 99),
        sdk_config=_parse_sdk_config(agent.get("sdk_config", "{}")),
        created_at=agent["created_at"],
        updated_at=agent["updated_at"],
    )


@router.post(
    "/agents",
    response_model=AgentResponse,
    summary="新建 Agent（admin）",
)
async def create_agent(body: AgentUpsertRequest, _admin: dict = Depends(require_admin)):
    row = upsert_agent(
        name=body.name,
        agent_type=body.type,
        description=body.description,
        system_prompt=body.system_prompt,
        enabled=body.enabled,
        sort_order=body.sort_order,
        sdk_config=json.dumps(body.sdk_config.model_dump()) if body.sdk_config else None,
    )
    return _to_response(row)


@router.put(
    "/agents/{agent_id}",
    response_model=AgentResponse,
    summary="更新 Agent（admin）",
)
async def update_agent(agent_id: str, body: AgentUpsertRequest, _admin: dict = Depends(require_admin)):
    existing = get_agent(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    row = upsert_agent(
        name=body.name,
        agent_type=body.type,
        description=body.description,
        system_prompt=body.system_prompt,
        enabled=body.enabled,
        sort_order=body.sort_order,
        agent_id=agent_id,
        sdk_config=json.dumps(body.sdk_config.model_dump()) if body.sdk_config else None,
    )
    return _to_response(row)


@router.delete("/agents/{agent_id}", summary="删除自定义 Agent（admin）")
async def remove_agent(agent_id: str, _admin: dict = Depends(require_admin)):
    ok = delete_agent(agent_id)
    if not ok:
        raise HTTPException(status_code=400, detail="内置 Agent 不可删除，或 Agent 不存在")
    return {"ok": True}


@router.put("/agents/{agent_id}/toggle", summary="启用/禁用 Agent（admin）")
async def toggle(agent_id: str, body: ToggleRequest, _admin: dict = Depends(require_admin)):
    ok = toggle_agent(agent_id, body.enabled)
    if not ok:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return {"ok": True, "enabled": body.enabled}


# ── 工具 ─────────────────────────────────────────────────────────────────────

def _parse_sdk_config(raw: str) -> SDKAgentConfig:
    """将数据库中的 sdk_config JSON 字符串解析为 SDKAgentConfig 对象"""
    if not raw or raw == "{}":
        return SDKAgentConfig()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return SDKAgentConfig(**data)
    except (json.JSONDecodeError, TypeError):
        pass
    return SDKAgentConfig()


def _to_response(row: dict) -> AgentResponse:
    return AgentResponse(
        id=row["id"],
        name=row["name"],
        type=row["type"],
        description=row.get("description", ""),
        system_prompt=row["system_prompt"],
        enabled=bool(row["enabled"]),
        sort_order=row.get("sort_order", 99),
        sdk_config=_parse_sdk_config(row.get("sdk_config", "{}")),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
