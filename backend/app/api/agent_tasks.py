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


class ResumeApprovalRequest(BaseModel):
    instructions: str = ""   # 人工处理意见


# ═══════════════════════════════════════════════════════
# Agent 任务管理
# ═══════════════════════════════════════════════════════

@router.get("/api/v1/agents/diagnose", summary="诊断事件链路状态")
async def diagnose_event_chain():
    """诊断事件→Worker 链路是否正常连接。"""
    result = {}
    # 1. 检查 EventBus 全局处理器
    try:
        from app.core.event_bus import get_event_bus
        bus = get_event_bus()
        result["bus_global_handlers"] = len(bus._global_handlers)
        result["bus_global_handler_names"] = [
            getattr(h, '__name__', repr(h)) for h in bus._global_handlers
        ]
    except Exception as e:
        result["bus_error"] = str(e)

    # 2. 检查 ManagerAgent 状态
    try:
        from app.core.manager_agent import get_manager_agent
        manager = get_manager_agent()
        result["manager_task_groups"] = len(manager._task_groups)
        result["manager_has_on_event"] = hasattr(manager, 'on_event')
        # 检查 event_registry
        reg = manager._event_registry
        result["registry_loaded"] = reg is not None
        if reg:
            ed = reg.get_event("risk:fraud_detected")
            result["fraud_event_def"] = ed is not None
            if ed:
                result["fraud_related_worker"] = ed.related_worker
                result["fraud_severity"] = ed.severity
    except Exception as e:
        result["manager_error"] = str(e)

    return result


@router.post("/api/v1/agents/test-danger", summary="直接测试危险事件暂停")
async def test_danger_event_directly():
    """直接调用 submit_event_task 测试 pending_approval 是否生效。
    不经过 EventBus，直接测试 ManagerAgent 内部逻辑。
    """
    try:
        from app.core.manager_agent import get_manager_agent
        manager = get_manager_agent()

        # 直接调用 submit_event_task
        group = await manager.submit_event_task(
            event_type="risk:fraud_detected",
            event_data={
                "chat_id": "oc_c0a0a056f96abaf03cc6605b9fc26e4b",
                "product_id": "test_001",
                "risk_score": 95,
                "description": "[直接测试] 欺诈风险检测",
            },
        )

        return {
            "group_id": group.group_id,
            "status": group.status,
            "is_pending_approval": group.status == "pending_approval",
            "pause_reason": group.context.get("pause_reason", "") if isinstance(group.context, dict) else "",
            "subtask_count": len(group.subtasks),
            "task_description": group.task_description,
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


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


@router.get("/api/v1/agents/tasks/pending", summary="待审批任务组列表")
async def list_pending_groups():
    """获取等待人工审批的任务组（危险事件闭环）。"""
    try:
        from app.core.manager_agent import get_manager_agent
        manager = get_manager_agent()
        return {"pending": manager.get_pending_groups()}
    except Exception as e:
        return {"pending": [], "error": str(e)}


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


@router.post("/api/v1/agents/tasks/{group_id}/resume", summary="恢复待审批任务组")
async def resume_pending_group(group_id: str, req: ResumeApprovalRequest):
    """恢复等待人工审批的任务组（危险事件闭环）。

    用户在飞书回复处理意见后调用此接口，恢复任务组执行。
    """
    try:
        from app.core.manager_agent import get_manager_agent
        manager = get_manager_agent()
        ok = await manager.resume_pending_group(group_id, req.instructions)
        if ok:
            return {"success": True, "group_id": group_id, "status": "running"}
        else:
            raise HTTPException(status_code=404, detail=f"任务组 {group_id} 不存在")
    except HTTPException:
        raise
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
