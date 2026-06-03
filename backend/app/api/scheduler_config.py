"""定时任务管理 API — /api/v1/scheduler

提供 APScheduler 定时任务的查看、暂停、恢复、立即触发等功能。
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException

from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

router = APIRouter(prefix="/api/v1/scheduler", tags=["scheduler"])


# ── 任务范围检测 ──────────────────────────────────

GLOBAL_JOB_IDS = {
    "market_poll", "metrics_collect",
    "proactive_daily_brief", "proactive_cert_expiry",
    "proactive_regulation_scan", "proactive_heartbeat",
    "proactive_insights", "proactive_global_metrics",
}

PRODUCT_TASK_PREFIXES = [
    "check_cert_expiry_",
    "scan_regulation_changes_",
]


def _detect_job_scope(job_id: str) -> Tuple[str, Optional[str]]:
    """检测任务范围（global/product）和关联产品ID。"""
    if job_id in GLOBAL_JOB_IDS:
        return "global", None
    for prefix in PRODUCT_TASK_PREFIXES:
        if job_id.startswith(prefix):
            product_id = job_id[len(prefix):]
            return "product", product_id
    m = re.match(r'^(.+?)_(p_[a-z0-9_]+)$', job_id)
    if m:
        return "product", m.group(2)
    return "global", None


@router.get("/tasks")
async def list_available_tasks():
    """获取所有可调度的任务模板"""
    from app.core.scheduler import get_available_tasks
    tasks = get_available_tasks()
    return {"tasks": tasks}


def _serialize_job(job) -> Dict[str, Any]:
    """将 APScheduler Job 序列化为字典。"""
    trigger = job.trigger
    trigger_info: Dict[str, Any] = {"type": "unknown"}

    if isinstance(trigger, IntervalTrigger):
        trigger_info["type"] = "interval"
        trigger_info["interval_seconds"] = int(trigger.interval.total_seconds())
        days = trigger.interval.days
        hours, rem = divmod(trigger.interval.seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f"{days}天")
        if hours:
            parts.append(f"{hours}小时")
        if minutes:
            parts.append(f"{minutes}分钟")
        if seconds:
            parts.append(f"{seconds}秒")
        trigger_info["interval_human"] = "".join(parts) or "0秒"
    elif isinstance(trigger, CronTrigger):
        trigger_info["type"] = "cron"
        cron_parts = []
        for field in trigger.fields:
            if str(field) != "*":
                cron_parts.append(f"{field.name}={field}")
        trigger_info["expression"] = " ".join(str(f) for f in trigger.fields)
        trigger_info["cron_human"] = ", ".join(cron_parts) if cron_parts else "每分钟"

    scope, product_id = _detect_job_scope(job.id)
    return {
        "id": job.id,
        "name": job.name or job.id,
        "func_ref": job.func_ref or "",
        "trigger": trigger_info,
        "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        "pending": job.pending,
        "coalesce": job.coalesce,
        "max_instances": job.max_instances,
        "misfire_grace_time": job.misfire_grace_time,
        "scope": scope,
        "product_id": product_id,
    }


@router.get("/jobs")
async def list_jobs():
    """获取所有定时任务列表"""
    from app.core.scheduler import get_scheduler
    scheduler = get_scheduler()
    if not scheduler:
        return {"jobs": [], "enabled": False}
    jobs = scheduler.get_jobs()
    return {
        "jobs": [_serialize_job(j) for j in jobs],
        "enabled": True,
    }


@router.get("/jobs/grouped")
async def list_grouped_jobs():
    """获取按维度分组的定时任务

    返回:
        global: 全局级任务列表
        products: 按产品ID分组的任务字典
        product_meta: 产品元数据（名称、合规状态等）
    """
    from app.core.scheduler import get_scheduler
    from app.core.product_storage import get_product_storage

    scheduler = get_scheduler()
    if not scheduler:
        return {"global": [], "products": {}, "product_meta": {}, "enabled": False}

    jobs = scheduler.get_jobs()
    global_jobs = []
    product_jobs: Dict[str, list] = {}

    for job in jobs:
        serialized = _serialize_job(job)
        if serialized["scope"] == "global":
            global_jobs.append(serialized)
        else:
            pid = serialized["product_id"]
            if pid:
                product_jobs.setdefault(pid, []).append(serialized)

    # 获取产品元数据
    product_meta = {}
    try:
        storage = get_product_storage()
        for pid in product_jobs:
            product = storage.get_product(pid)
            if product:
                product_meta[pid] = {
                    "id": product.id,
                    "name": product.name,
                    "target_markets": product.target_markets,
                    "lifecycle_stage": product.lifecycle_stage.value if hasattr(product.lifecycle_stage, 'value') else product.lifecycle_stage,
                    "compliance_status": product.compliance_status,
                    "health_score": product.health_score,
                }
    except Exception:
        pass

    return {
        "global": global_jobs,
        "products": product_jobs,
        "product_meta": product_meta,
        "enabled": True,
    }


@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str):
    """暂停指定定时任务"""
    from app.core.scheduler import get_scheduler
    scheduler = get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not running")
    try:
        scheduler.pause_job(job_id)
        return {"ok": True, "job_id": job_id, "status": "paused"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Job not found: {e}")


@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str):
    """恢复指定定时任务"""
    from app.core.scheduler import get_scheduler
    scheduler = get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not running")
    try:
        scheduler.resume_job(job_id)
        return {"ok": True, "job_id": job_id, "status": "active"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Job not found: {e}")


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """删除指定定时任务"""
    from app.core.scheduler import get_scheduler
    scheduler = get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not running")
    try:
        scheduler.remove_job(job_id)
        return {"ok": True, "job_id": job_id, "status": "removed"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Delete failed: {e}")


@router.post("/jobs")
async def create_job(body: Dict[str, Any]):
    """创建定时任务

    Body:
        task: 任务名称（来自 /tasks 列表）
        trigger_type: "interval" | "cron"
        trigger_args: 触发器参数字典
        job_id: 可选，自定义ID
        replace_existing: 可选，是否替换已有同名任务
    """
    from app.core.scheduler import get_scheduler, _import_task_func
    scheduler = get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not running")

    task_name = body.get("task", "")
    trigger_type = body.get("trigger_type", "interval")
    trigger_args = body.get("trigger_args", {})
    job_id = body.get("job_id", task_name)
    replace_existing = body.get("replace_existing", True)

    if not task_name:
        raise HTTPException(status_code=400, detail="task is required")

    try:
        func = _import_task_func(task_name)
        scheduler.add_job(
            func,
            trigger_type,
            id=job_id,
            name=task_name,
            replace_existing=replace_existing,
            **trigger_args,
        )
        return {"ok": True, "job_id": job_id, "task": task_name, "trigger": trigger_type}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Create job failed: {e}")


@router.post("/jobs/{job_id}/trigger")
async def trigger_job(job_id: str):
    """立即触发指定定时任务

    使用 modify_job 的 next_run_time 参数让任务立即执行一次，
    执行完毕后恢复原有调度计划。
    """
    from app.core.scheduler import get_scheduler
    scheduler = get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not running")
    try:
        from datetime import datetime
        scheduler.modify_job(job_id, next_run_time=datetime.now())
        return {"ok": True, "job_id": job_id, "status": "triggered"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Trigger failed: {e}")


# ── 任务-Worker 绑定管理 ──────────────────────────────


@router.get("/bindings")
async def list_bindings():
    """获取所有任务-Worker 绑定配置

    返回每个定时任务绑定的 Worker 编码及 SDK 启用状态。
    支持通过前端管理界面动态修改绑定。
    """
    from app.core.scheduler import (
        get_all_task_worker_bindings,
        get_available_tasks,
    )
    bindings = get_all_task_worker_bindings()
    tasks = get_available_tasks()

    # 合并任务信息和绑定信息
    result = []
    for task_name, task_info in tasks.items():
        binding = bindings.get(task_name, {})
        entry = {
            "task_name": task_name,
            "display_name": task_info.get("name", task_name),
            "description": task_info.get("description", ""),
            "default_trigger": task_info.get("default_trigger", "interval"),
            "worker_code": binding.get("worker_code", ""),
            "sdk_enabled": binding.get("enabled", True),
        }
        result.append(entry)

    return {"bindings": result, "total": len(result)}


@router.get("/tasks-with-workers")
async def list_tasks_with_workers():
    """获取任务列表及可用 Worker（供前端绑定配置使用）"""
    from app.core.scheduler import get_available_tasks, get_all_task_worker_bindings
    from app.core.worker_registry import get_worker_registry

    tasks = get_available_tasks()
    bindings = get_all_task_worker_bindings()

    # 获取所有可用 Worker
    registry = get_worker_registry()
    workers = registry.get_all_workers()
    available_workers = [
        {
            "worker_code": w.worker_code,
            "worker_name": w.worker_name,
            "description": w.description,
            "sdk_enabled": w.sdk_enabled,
            "business_stage": w.business_stage,
        }
        for w in workers
    ]

    task_list = []
    for task_name, task_info in tasks.items():
        binding = bindings.get(task_name, {})
        task_list.append({
            "task_name": task_name,
            "display_name": task_info.get("name", task_name),
            "description": task_info.get("description", ""),
            "default_trigger": task_info.get("default_trigger", "interval"),
            "default_args": task_info.get("default_args", {}),
            "bound_worker": binding.get("worker_code", ""),
            "sdk_enabled": binding.get("enabled", True),
        })

    return {
        "tasks": task_list,
        "available_workers": available_workers,
        "total_tasks": len(task_list),
        "total_workers": len(available_workers),
    }


@router.put("/bindings/{task_name}")
async def update_binding(task_name: str, body: Dict[str, Any]):
    """更新任务-Worker 绑定

    Body:
        worker_code: Worker 编码
        enabled: 是否启用 SDK 执行（可选，默认 True）

    示例:
        PUT /api/v1/scheduler/bindings/daily_compliance_brief
        {"worker_code": "compliance_worker", "enabled": true}
    """
    from app.core.scheduler import set_task_worker_binding, get_available_tasks

    tasks = get_available_tasks()
    if task_name not in tasks:
        raise HTTPException(
            status_code=404,
            detail=f"任务 '{task_name}' 不存在",
        )

    worker_code = body.get("worker_code", "")
    if not worker_code:
        raise HTTPException(status_code=400, detail="worker_code 是必填项")

    # 验证 Worker 是否存在
    from app.core.worker_registry import get_worker_registry
    registry = get_worker_registry()
    worker = registry.get_worker(worker_code)
    if not worker:
        raise HTTPException(
            status_code=404,
            detail=f"Worker '{worker_code}' 不存在",
        )

    enabled = body.get("enabled", True)
    success = set_task_worker_binding(task_name, worker_code, enabled=enabled)

    if not success:
        raise HTTPException(status_code=500, detail="更新绑定失败")

    return {
        "ok": True,
        "task_name": task_name,
        "worker_code": worker_code,
        "enabled": enabled,
        "message": f"任务 '{task_name}' 已绑定到 Worker '{worker_code}' (SDK={'开启' if enabled else '关闭'})",
    }
