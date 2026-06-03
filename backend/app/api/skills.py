"""
Skills API（Phase 3.5）

/api/v1/skills — Skills管理端点
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


# ── Request Models ────────────────────────────────


class InstallRequest(BaseModel):
    name: str
    source: str = "builtin"
    source_url: str = ""
    config: Dict[str, Any] = {}


class ExecuteRequest(BaseModel):
    args: Dict[str, Any] = {}
    timeout: int = 30


class ConfigUpdateRequest(BaseModel):
    config: Dict[str, Any] = {}


class RecommendRequest(BaseModel):
    business_stage: Optional[int] = None
    event_category: Optional[str] = None
    product_type: Optional[str] = None


# ── Endpoints ─────────────────────────────────────


@router.get("", summary="Skills列表")
async def list_skills(status: str = None, stage: int = None):
    from app.core.skill_registry import get_skill_registry
    registry = get_skill_registry()
    return {"skills": registry.list_skills(status=status, stage=stage)}


@router.post("/install", summary="安装Skill")
async def install_skill(req: InstallRequest):
    from app.core.skill_registry import get_skill_registry
    registry = get_skill_registry()
    try:
        result = registry.install_skill(req.name, req.source, req.source_url, req.config)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{skill_id}", summary="Skill详情")
async def get_skill(skill_id: str):
    from app.core.skill_registry import get_skill_registry
    registry = get_skill_registry()
    skill = registry.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


@router.post("/{skill_id}/install", summary="通过ID安装Skill")
async def install_skill_by_id(skill_id: str, req: InstallRequest = None):
    from app.core.skill_registry import get_skill_registry
    registry = get_skill_registry()
    req = req or InstallRequest(name=skill_id)
    return registry.install_skill(req.name, req.source, req.source_url, req.config)


@router.post("/{skill_id}/refresh", summary="刷新Skill文件")
async def refresh_skill(skill_id: str):
    from app.core.skill_registry import get_skill_registry
    registry = get_skill_registry()
    skill = registry.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"status": "refreshed", "skill_id": skill_id}


@router.post("/{skill_id}/execute", summary="执行Skill")
async def execute_skill(skill_id: str, req: ExecuteRequest):
    from app.core.skill_registry import get_skill_registry, get_skill_executor
    registry = get_skill_registry()
    skill = registry.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    executor = get_skill_executor()
    return await executor.execute(skill["name"], req.args, req.timeout)


@router.get("/{skill_id}/status", summary="Skill执行状态")
async def skill_status(skill_id: str):
    from app.core.skill_registry import get_skill_executor
    executor = get_skill_executor()
    execs = executor.get_executions(skill_id=skill_id, limit=10)
    return {"skill_id": skill_id, "recent_executions": execs}


@router.get("/{skill_id}/config", summary="获取Skill配置")
async def get_skill_config(skill_id: str):
    from app.core.skill_registry import get_skill_registry
    registry = get_skill_registry()
    skill = registry.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"skill_id": skill_id, "config": skill.get("config", {})}


@router.put("/{skill_id}/config", summary="更新Skill配置")
async def update_skill_config(skill_id: str, req: ConfigUpdateRequest):
    from app.core.skill_registry import get_skill_registry
    registry = get_skill_registry()
    result = registry.update_config(skill_id, req.config)
    if not result:
        raise HTTPException(status_code=404, detail="Skill not found")
    return result


@router.delete("/{skill_id}", summary="删除/卸载Skill")
async def delete_skill(skill_id: str):
    from app.core.skill_registry import get_skill_registry
    registry = get_skill_registry()
    if registry.uninstall_skill(skill_id):
        return {"status": "uninstalled", "skill_id": skill_id}
    raise HTTPException(status_code=404, detail="Skill not found")


@router.post("/recommend", summary="获取Skill推荐")
async def recommend_skills(req: RecommendRequest):
    from app.core.skill_registry import get_skill_recommender
    recommender = get_skill_recommender()
    context = {}
    if req.business_stage:
        context["business_stage"] = req.business_stage
    if req.event_category:
        context["event_category"] = req.event_category
    if req.product_type:
        context["product_type"] = req.product_type
    return {"recommendations": recommender.recommend_by_context(context)}


@router.get("/matrix/stages", summary="Skills×阶段映射矩阵")
async def get_stage_matrix():
    from app.core.skill_registry import get_skill_registry
    registry = get_skill_registry()
    return {"matrix": registry.get_stage_matrix(), "cross_stage": registry.get_cross_stage_skills()}


@router.get("/executions/history", summary="执行历史")
async def get_execution_history(skill_name: str = None, limit: int = 50):
    from app.core.skill_registry import get_skill_executor
    executor = get_skill_executor()
    return {"executions": executor.get_executions(skill_name=skill_name, limit=limit)}
