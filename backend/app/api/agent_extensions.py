"""
Agent 扩展关联 API — Agent 与 Skills/Tools/OAuth 的关联管理。

端点:
  GET    /agents/{agent_id}/skills    — 获取Agent关联Skills
  PUT    /agents/{agent_id}/skills    — 更新Agent关联Skills
  GET    /agents/{agent_id}/tools     — 获取Agent关联Tools
  PUT    /agents/{agent_id}/tools     — 更新Agent关联Tools
  GET    /agents/{agent_id}/oauth     — 获取Agent关联OAuth
  PUT    /agents/{agent_id}/oauth     — 更新Agent关联OAuth
  GET    /agents/{agent_id}/status    — Agent运行时状态
"""

import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List

from app.config import settings
from app.core.auth import get_current_user, require_admin
from app.storage.agent_config_store import get_agent

router = APIRouter(prefix="/api/v1", tags=["agent-extensions"])

_AGENT_EXT_FILE = Path(settings.data_dir) / "agents" / "extensions.json"


def _load_ext() -> dict:
    if _AGENT_EXT_FILE.exists():
        try:
            with open(_AGENT_EXT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_ext(data: dict):
    _AGENT_EXT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_AGENT_EXT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class AgentSkillsRequest(BaseModel):
    skill_ids: List[str] = []


class AgentToolsRequest(BaseModel):
    tool_ids: List[str] = []


class AgentOAuthRequest(BaseModel):
    connection_ids: List[str] = []


@router.get("/agents/{agent_id}/skills", summary="获取Agent关联Skills")
async def get_agent_skills(agent_id: str, _user: dict = Depends(get_current_user)):
    ext = _load_ext()
    agent_ext = ext.get(agent_id, {})
    return {"agent_id": agent_id, "skill_ids": agent_ext.get("skill_ids", [])}


@router.put("/agents/{agent_id}/skills", summary="更新Agent关联Skills")
async def update_agent_skills(agent_id: str, body: AgentSkillsRequest,
                              _admin: dict = Depends(require_admin)):
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    ext = _load_ext()
    ext.setdefault(agent_id, {})["skill_ids"] = body.skill_ids
    _save_ext(ext)
    return {"agent_id": agent_id, "skill_ids": body.skill_ids}


@router.get("/agents/{agent_id}/tools", summary="获取Agent关联Tools")
async def get_agent_tools(agent_id: str, _user: dict = Depends(get_current_user)):
    ext = _load_ext()
    agent_ext = ext.get(agent_id, {})
    return {"agent_id": agent_id, "tool_ids": agent_ext.get("tool_ids", [])}


@router.put("/agents/{agent_id}/tools", summary="更新Agent关联Tools")
async def update_agent_tools(agent_id: str, body: AgentToolsRequest,
                             _admin: dict = Depends(require_admin)):
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    ext = _load_ext()
    ext.setdefault(agent_id, {})["tool_ids"] = body.tool_ids
    _save_ext(ext)
    return {"agent_id": agent_id, "tool_ids": body.tool_ids}


@router.get("/agents/{agent_id}/oauth", summary="获取Agent关联OAuth")
async def get_agent_oauth(agent_id: str, _user: dict = Depends(get_current_user)):
    ext = _load_ext()
    agent_ext = ext.get(agent_id, {})
    return {"agent_id": agent_id, "connection_ids": agent_ext.get("connection_ids", [])}


@router.put("/agents/{agent_id}/oauth", summary="更新Agent关联OAuth")
async def update_agent_oauth(agent_id: str, body: AgentOAuthRequest,
                             _admin: dict = Depends(require_admin)):
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    ext = _load_ext()
    ext.setdefault(agent_id, {})["connection_ids"] = body.connection_ids
    _save_ext(ext)
    return {"agent_id": agent_id, "connection_ids": body.connection_ids}


@router.get("/agents/{agent_id}/status", summary="Agent运行时状态")
async def get_agent_status(agent_id: str, _user: dict = Depends(get_current_user)):
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    ext = _load_ext()
    agent_ext = ext.get(agent_id, {})
    return {
        "agent_id": agent_id,
        "name": agent["name"],
        "enabled": agent.get("enabled", False),
        "associated_skills": agent_ext.get("skill_ids", []),
        "associated_tools": agent_ext.get("tool_ids", []),
        "associated_oauth": agent_ext.get("connection_ids", []),
        "status": "active" if agent.get("enabled") else "inactive",
    }
