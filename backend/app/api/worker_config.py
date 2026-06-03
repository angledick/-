"""Worker配置管理API — /api/v1/worker-config"""

from fastapi import APIRouter, HTTPException
from typing import Optional, List

from app.models.schemas import WorkerDefinition, WorkerStatus
from app.core.worker_registry import get_worker_registry
from app.core.qa_agent import get_qa_agent

router = APIRouter(prefix="/api/v1/worker-config", tags=["worker-config"])


@router.get("")
async def list_worker_configs(stage: Optional[str] = None):
    """列出所有Worker配置"""
    registry = get_worker_registry()
    if stage:
        workers = registry.get_workers_by_stage(stage)
    else:
        workers = registry.get_all_workers()
    return {"workers": [w.model_dump() for w in workers], "total": len(workers)}


@router.get("/status")
async def list_worker_statuses():
    """获取所有Worker运行时状态"""
    registry = get_worker_registry()
    statuses = registry.get_all_statuses()
    return {"statuses": [s.model_dump() for s in statuses]}


@router.get("/{worker_code}")
async def get_worker_config(worker_code: str):
    """获取Worker配置"""
    registry = get_worker_registry()
    worker = registry.get_worker(worker_code)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Worker {worker_code} 未定义")
    return worker


@router.get("/{worker_code}/status")
async def get_worker_status(worker_code: str):
    """获取Worker运行时状态"""
    registry = get_worker_registry()
    status = registry.get_worker_status(worker_code)
    if not status:
        raise HTTPException(status_code=404, detail=f"Worker {worker_code} 未定义")
    return status


@router.post("")
async def create_worker_config(worker_def: WorkerDefinition):
    """注册新Worker（QAAgent）"""
    agent = get_qa_agent()
    permission = agent.check_permission("register_worker")
    if not permission.allowed:
        raise HTTPException(status_code=403, detail=permission.reason)

    try:
        success = await agent.add_worker_type(
            worker_code=worker_def.worker_code,
            worker_name=worker_def.worker_name,
            business_stage=worker_def.business_stage,
            description=worker_def.description,
            available_skills=worker_def.available_skills,
            priority=worker_def.priority,
        )
        return {"success": success}
    except ValueError as e:
        if "已存在" in str(e):
            return {"success": True, "note": str(e)}
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{worker_code}")
async def update_worker_config(worker_code: str, updates: dict):
    """修改Worker配置（QAAgent）"""
    agent = get_qa_agent()
    permission = agent.check_permission("modify_worker")
    if not permission.allowed:
        raise HTTPException(status_code=403, detail=permission.reason)

    try:
        success = await agent.modify_worker_type(worker_code, **updates)
        return {"success": success}
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{worker_code}")
async def delete_worker_config(worker_code: str):
    """删除Worker（归档）"""
    agent = get_qa_agent()
    permission = agent.check_permission("delete_worker")
    if not permission.allowed:
        raise HTTPException(status_code=403, detail=permission.reason)

    try:
        success = await agent.delete_worker_type(worker_code)
        if not success:
            raise HTTPException(status_code=404, detail=f"Worker {worker_code} 不存在")
        return {"success": True}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
