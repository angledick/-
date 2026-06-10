"""
Sync API — 自动拉取引擎管理。

端点:
  GET  /api/v1/sync/status              — 同步引擎状态
  POST /api/v1/sync/run                 — 手动触发同步
  GET  /api/v1/sync/jobs                — 同步任务列表
  GET  /api/v1/sync/logs                — 同步日志
  POST /api/v1/sync/tracking            — 注册物流追踪号
"""

from fastapi import APIRouter
from typing import Dict, Any, List

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


@router.get("/status", summary="同步引擎状态")
async def sync_status():
    from app.core.auto_pull_engine import get_auto_pull_engine
    engine = get_auto_pull_engine()
    return engine.get_status()


@router.post("/run", summary="手动触发同步")
async def run_sync(provider: str, sync_type: str, connection_id: str = ""):
    from app.core.auto_pull_engine import get_auto_pull_engine
    engine = get_auto_pull_engine()
    return await engine.manual_sync(provider, sync_type, connection_id)


@router.get("/jobs", summary="同步任务列表")
async def list_sync_jobs(provider: str = None, status: str = None, limit: int = 50):
    from app.core.auto_pull_engine import get_auto_pull_engine
    engine = get_auto_pull_engine()
    return {"jobs": engine.get_jobs(provider=provider, status=status, limit=limit)}


@router.get("/logs", summary="同步日志")
async def sync_logs(job_id: str = None, limit: int = 100):
    from app.core.auto_pull_engine import get_auto_pull_engine
    engine = get_auto_pull_engine()
    return {"logs": engine.get_logs(job_id=job_id, limit=limit)}


@router.post("/tracking", summary="注册物流追踪号")
async def register_tracking(tracking_numbers: List[Dict[str, Any]]):
    from app.core.auto_pull_engine import get_auto_pull_engine
    engine = get_auto_pull_engine()
    return engine.register_tracking_numbers(tracking_numbers)
