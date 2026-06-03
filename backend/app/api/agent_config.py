"""多 Agent 配置 API — admin 可管理，user 只读。

Phase 3扩展: Agent关联Skills/Tools/OAuth配置 + Agent运行时状态
"""

import json
import time
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from app.core.auth import get_current_user, require_admin
from app.models.schemas import SDKAgentConfig
from app.storage.agent_config_store import (
    list_agents,
    get_agent,
    upsert_agent,
    delete_agent,
    toggle_agent,
)
from app.services.astra_assistant import AstraAssistant, check_sdk

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
    "/agents/tasks",
    summary="获取活跃任务列表",
)
async def get_agent_tasks():
    """返回 ManagerAgent 当前活跃任务组"""
    from app.core.manager_agent import get_manager_agent
    manager = get_manager_agent()
    stats = manager.get_stats()
    return {"tasks": list(manager._task_groups.values()), "stats": stats}


@router.get(
    "/agents/workers",
    summary="获取Worker状态列表",
)
async def get_agent_workers():
    """返回所有Worker运行时状态"""
    from app.core.worker_registry import get_worker_registry
    registry = get_worker_registry()
    workers = registry.get_all_statuses()
    return {"workers": [w.model_dump() for w in workers]}


@router.get(
    "/agents/templates",
    summary="获取任务分解模板列表",
)
async def get_agent_templates():
    """返回可用任务分解模板"""
    from app.core.task_decomposer import get_task_decomposer
    decomposer = get_task_decomposer()
    templates = decomposer.list_templates()
    return {"templates": templates}


@router.get(
    "/agents/{agent_id}",
    response_model=AgentResponse,
    summary="获取 Agent 完整配置（含 system_prompt）",
)
async def get_agent_detail(agent_id: str, _user: dict = Depends(get_current_user)):
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


# ── Agent关联配置 (Phase 3 扩展) ──────────────────────────────────────────

_AGENT_EXT_FILE = Path("data/config/agent_extensions.json")


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


# ── Agent 执行（通过 Claude SDK） ──────────────────────────────────────────

class AgentChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


@router.post("/agents/{agent_id}/chat", summary="以 Agent 身份对话")
async def agent_chat(agent_id: str, body: AgentChatRequest, _user: dict = Depends(get_current_user)):
    """以指定 Agent 的 system_prompt 驱动 Claude SDK 对话。

    Agent 可使用 Claude Code 全部工具（Bash/Read/Write/WebSearch 等）。
    """
    if not check_sdk():
        raise HTTPException(status_code=503, detail="claude-agent-sdk 未安装")
    assistant = AstraAssistant()
    try:
        result = await assistant.run_as_agent(
            agent_id=agent_id,
            message=body.message,
            session_id=body.session_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_id}/chat/stream", summary="以 Agent 身份流式对话")
async def agent_chat_stream(agent_id: str, body: AgentChatRequest, _user: dict = Depends(get_current_user)):
    """以指定 Agent 身份进行 SSE 流式对话。"""
    if not check_sdk():
        raise HTTPException(status_code=503, detail="claude-agent-sdk 未安装")

    from fastapi.responses import StreamingResponse
    from app.api.streaming import _sse_event

    assistant = AstraAssistant()

    async def event_generator():
        try:
            yield _sse_event("thinking", {"content": f"正在以 Agent 身份分析...", "depth": 1})
            async for event in assistant.run_as_agent_stream(
                agent_id=agent_id,
                message=body.message,
                session_id=body.session_id,
            ):
                if event["type"] == "text":
                    yield _sse_event("token", {"content": event["content"]})
                elif event["type"] == "tool_use":
                    yield _sse_event("skill_start", {
                        "skill": event["tool_name"],
                        "args": event["tool_input"],
                    })
                elif event["type"] == "tool_result":
                    yield _sse_event("skill_end", {
                        "skill": event["tool_name"],
                        "result": event.get("content"),
                        "status": "success",
                    })
                elif event["type"] == "thinking":
                    yield _sse_event("thinking", {"content": event["content"]})
                elif event["type"] == "error":
                    yield _sse_event("error", {"code": "agent_error", "message": event["error"]})
                    return
            yield _sse_event("done", {"finish_reason": "complete"})
        except Exception as e:
            yield _sse_event("error", {"code": "internal_error", "message": str(e)[:200]})
            yield _sse_event("done", {"finish_reason": "error"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


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
