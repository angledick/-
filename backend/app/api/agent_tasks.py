"""
Agent 任务管理 API — 任务提交、进度监控、用户干预。

端点:
  GET    /api/v1/agents/tasks                 — 活跃任务列表
  POST   /api/v1/agents/tasks                 — 提交任务
  GET    /api/v1/agents/tasks/{group_id}      — 任务进度
  POST   /api/v1/agents/tasks/{group_id}/intervene — 用户干预
  GET    /api/v1/agents/workers               — Worker 状态
  GET    /api/v1/agents/templates             — 任务分解模板
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

router = APIRouter(tags=["agent-tasks"])


# ── 请求模型 ──────────────────────────────────

class TaskSubmitRequest(BaseModel):
    task: str
    context: Dict[str, Any] = {}
    created_by: str = "user"
    template_key: Optional[str] = None


class InterventionRequest(BaseModel):
    action: str           # cancel_group/cancel_subtask/pause/resume/retry
    subtask_id: Optional[str] = None
    reason: str = ""


# ═══════════════════════════════════════════════════════
# Agent 任务管理
# ═══════════════════════════════════════════════════════

@router.get("/api/v1/agents/tasks", summary="活跃任务列表")
async def list_active_tasks():
    try:
        from app.core.manager_agent import get_manager_agent
        manager = get_manager_agent()
        return {"tasks": manager.get_active_groups()}
    except Exception as e:
        return {"tasks": [], "error": str(e)}


@router.post("/api/v1/agents/tasks", summary="提交任务")
async def submit_task(req: TaskSubmitRequest):
    try:
        from app.core.manager_agent import get_manager_agent
        manager = get_manager_agent()
        group = await manager.submit_task(
            task=req.task,
            context=req.context,
            created_by=req.created_by,
            template_key=req.template_key,
        )
        return group.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/agents/tasks/{group_id}", summary="任务进度")
async def get_task_progress(group_id: str):
    try:
        from app.core.manager_agent import get_manager_agent
        manager = get_manager_agent()
        progress = await manager.monitor_progress(group_id)
        return progress
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/agents/tasks/{group_id}/intervene", summary="用户干预")
async def intervene_task(group_id: str, req: InterventionRequest):
    try:
        from app.core.manager_agent import get_manager_agent
        manager = get_manager_agent()
        result = await manager.user_intervention(
            group_id=group_id,
            action=req.action,
            subtask_id=req.subtask_id,
            reason=req.reason,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/agents/workers", summary="Worker状态")
async def get_worker_status():
    try:
        from app.core.manager_agent import get_manager_agent
        manager = get_manager_agent()
        return {"workers": manager.get_worker_status()}
    except Exception as e:
        return {"workers": [], "error": str(e)}


@router.get("/api/v1/agents/templates", summary="任务分解模板")
async def list_task_templates():
    try:
        from app.core.task_decomposer import get_task_decomposer
        decomposer = get_task_decomposer()
        return {"templates": decomposer.list_templates()}
    except Exception as e:
        return {"templates": [], "error": str(e)}
