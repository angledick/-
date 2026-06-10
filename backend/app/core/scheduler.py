"""后台调度器 — 定时触发市场监控和指标收集。

依赖: APScheduler (AsyncIOScheduler)

数据流转:
  - 触发者: Scheduler
  - 被触发者: Worker 系统 → Claude Agent SDK / 本地 ProactiveEngine
  - 读取: L2 (产品列表) / L3 (用户偏好)
  - 写入: L5 (market_event) / risk_alerts
"""

import json
import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import settings

import yaml

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


# ── 任务-Worker 绑定 ────────────────────────────────
# 每个定时任务绑定到指定 Worker，Worker 调用 Claude Agent SDK 执行

BINDINGS_YAML = Path(settings.data_dir) / "scheduler" / "bindings.yaml"

TASK_WORKER_BINDINGS: Dict[str, Dict[str, Any]] = {}
"""
运行时的任务-Worker 绑定表。

格式: {
    "task_name": {
        "worker_code": "compliance_worker",
        "enabled": True,
    }
}
"""


def _load_bindings():
    """从 YAML 配置文件加载绑定。"""
    global TASK_WORKER_BINDINGS
    try:
        if BINDINGS_YAML.exists():
            data = yaml.safe_load(BINDINGS_YAML.read_text(encoding="utf-8"))
            bindings = data.get("bindings", {}) if isinstance(data, dict) else {}
            TASK_WORKER_BINDINGS.update(bindings)
            logger.info("已加载 %d 条任务-Worker 绑定", len(bindings))
    except Exception as e:
        logger.warning("加载任务-Worker 绑定失败: %s", e)


def _save_bindings():
    """持久化绑定到 YAML 文件。"""
    try:
        BINDINGS_YAML.parent.mkdir(parents=True, exist_ok=True)
        BINDINGS_YAML.write_text(
            yaml.dump({"bindings": TASK_WORKER_BINDINGS}, allow_unicode=True, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
    except Exception as e:
        logger.error("保存任务-Worker 绑定失败: %s", e)


def init_bindings():
    """初始化绑定：从 YAML 加载配置。"""
    _load_bindings()
    if not TASK_WORKER_BINDINGS:
        _save_bindings()
    logger.info("当前 %d 条任务-Worker 绑定", len(TASK_WORKER_BINDINGS))


def get_task_worker_binding(task_name: str) -> Optional[Dict[str, Any]]:
    """获取指定任务的 Worker 绑定配置。"""
    return TASK_WORKER_BINDINGS.get(task_name)


def get_all_task_worker_bindings() -> Dict[str, Dict[str, Any]]:
    """获取所有任务-Worker 绑定。"""
    return dict(TASK_WORKER_BINDINGS)


def set_task_worker_binding(task_name: str, worker_code: str, enabled: bool = True) -> bool:
    """设置任务-Worker 绑定。"""
    if task_name not in TASK_REGISTRY:
        return False
    TASK_WORKER_BINDINGS[task_name] = {
        "worker_code": worker_code,
        "enabled": enabled,
    }
    _save_bindings()
    logger.info("任务 '%s' 绑定到 Worker '%s' (SDK=%s)", task_name, worker_code, enabled)
    return True


# ── 可调度任务注册表 ────────────────────────────────

TASK_REGISTRY: Dict[str, Dict[str, Any]] = {}
"""
注册可被 QAAgent 或 API 动态调度的任务。

格式: {
    "task_name": {
        "name": "显示名称",
        "description": "任务描述",
        "default_trigger": "interval",  # 或 "cron"
        "default_args": {"minutes": 60},  # 默认触发参数
        "params": [{"name": "...", "type": "...", "desc": "..."}],  # 可选参数说明
    }
}
"""


def register_task(
    name: str,
    display_name: str,
    description: str,
    default_trigger: str = "interval",
    default_args: Optional[Dict[str, Any]] = None,
    params: Optional[list] = None,
    worker_code: Optional[str] = None,
):
    """注册一个可调度任务。

    Args:
        name: 任务名称（唯一标识）
        display_name: 显示名称
        description: 任务描述
        default_trigger: 默认触发器类型 (interval/cron)
        default_args: 默认触发器参数
        params: 可选参数说明
        worker_code: 绑定的默认 Worker 编码（优先于 DEFAULT_BINDINGS）
    """
    entry = {
        "name": display_name,
        "description": description,
        "default_trigger": default_trigger,
        "default_args": default_args or {},
        "params": params or [],
    }
    if worker_code:
        entry["default_worker"] = worker_code
        # 自动创建默认绑定
        if name not in TASK_WORKER_BINDINGS:
            TASK_WORKER_BINDINGS[name] = {"worker_code": worker_code, "enabled": True}
    TASK_REGISTRY[name] = entry


def get_available_tasks() -> Dict[str, Dict[str, Any]]:
    """获取所有可调度任务模板。"""
    return dict(TASK_REGISTRY)


def _import_task_func(task_name: str) -> Callable:
    """动态导入任务的可调用函数（回退机制）。

    优先返回 _execute_via_worker（走 Worker 分发），
    无绑定或禁用时回退到传统 Python 函数直接调用。
    """
    import importlib

    # 如果任务有 Worker 绑定且启用，返回 Worker 分发 wrapper
    binding = TASK_WORKER_BINDINGS.get(task_name)
    if binding and binding.get("enabled", True):
        async def _worker_wrapper():
            return await _execute_via_worker(task_name)
        return _worker_wrapper

    # 模块级函数映射（module:function）
    MODULE_FUNCS = {
        "poll_all_markets": ("app.core.scheduler", "poll_all_markets"),
        "collect_metrics": ("app.core.scheduler", "collect_metrics"),
    }
    if task_name in MODULE_FUNCS:
        mod_name, func_name = MODULE_FUNCS[task_name]
        mod = importlib.import_module(mod_name)
        return getattr(mod, func_name)

    # ProactiveEngine 实例方法
    PROACTIVE_METHODS = {
        "daily_compliance_brief": "daily_compliance_brief",
        "check_cert_expiry": "check_cert_expiry",
        "scan_regulation_changes": "scan_regulation_changes",
        "heartbeat_check": "heartbeat_check",
        "generate_cross_product_insights": "generate_cross_product_insights",
        "aggregate_global_metrics": "aggregate_global_metrics",
    }
    if task_name in PROACTIVE_METHODS:
        from app.core.proactive_engine import get_proactive_engine
        engine = get_proactive_engine()
        return getattr(engine, PROACTIVE_METHODS[task_name])

    # 如果绑定禁用，但仍有 Worker 配置，也尝试 Worker 分发
    if binding:
        async def _worker_fallback():
            return await _execute_via_worker(task_name)
        return _worker_fallback

    raise ValueError(f"未知任务: {task_name}")


def get_scheduler() -> Optional[AsyncIOScheduler]:
    """获取当前调度器实例。"""
    return _scheduler


async def start_scheduler():
    """应用启动时调用 — 初始化绑定、注册定时任务并启动调度器。

    所有任务通过 _execute_via_worker 分发到绑定的 Worker，
    Worker 使用 Claude Agent SDK 执行。
    """
    global _scheduler
    if not settings.scheduler_enabled:
        logger.info("Scheduler is disabled (scheduler_enabled=False)")
        return
    if _scheduler is not None:
        logger.warning("Scheduler already started")
        return

    # 初始化任务-Worker 绑定
    init_bindings()

    _scheduler = AsyncIOScheduler()

    # 所有定时任务通过 Worker 分发调度
    _scheduler.add_job(
        _execute_via_worker_wrapper("poll_all_markets"),
        "interval",
        minutes=settings.market_poll_interval_minutes,
        id="market_poll",
        replace_existing=True,
    )
    _scheduler.add_job(
        _execute_via_worker_wrapper("collect_metrics"),
        "interval",
        hours=6,
        id="metrics_collect",
        replace_existing=True,
    )
    _scheduler.add_job(
        _execute_via_worker_wrapper("daily_compliance_brief"),
        'cron', hour=9, minute=0,
        id='proactive_daily_brief',
        replace_existing=True,
    )
    _scheduler.add_job(
        _execute_via_worker_wrapper("check_cert_expiry"),
        'cron', hour=10, minute=0,
        id='proactive_cert_expiry',
        replace_existing=True,
    )
    _scheduler.add_job(
        _execute_via_worker_wrapper("scan_regulation_changes"),
        'interval', hours=1,
        id='proactive_regulation_scan',
        replace_existing=True,
    )
    _scheduler.add_job(
        _execute_via_worker_wrapper("heartbeat_check"),
        'interval', minutes=5,
        id='proactive_heartbeat',
        replace_existing=True,
    )
    _scheduler.add_job(
        _execute_via_worker_wrapper("generate_cross_product_insights"),
        'interval', hours=4,
        id='proactive_insights',
        replace_existing=True,
    )
    _scheduler.add_job(
        _execute_via_worker_wrapper("aggregate_global_metrics"),
        'interval', hours=12,
        id='proactive_global_metrics',
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        f"Scheduler started: {len(TASK_WORKER_BINDINGS)} tasks bound to Workers"
    )

    # 自动为所有已有产品注册产品级任务
    try:
        from app.core.product_storage import get_product_storage
        storage = get_product_storage()
        product_ids = storage.get_all_product_ids()
        if product_ids:
            for pid in product_ids:
                register_product_jobs(pid)
            logger.info("已为 %d 个产品注册产品级定时任务", len(product_ids))
        else:
            logger.info("暂无产品，跳过产品级任务注册")
    except Exception as e:
        logger.warning("自动注册产品级任务失败: %s", e)


async def _execute_via_worker(task_name: str) -> Any:
    """Worker 分发执行 — 定时任务的统一入口。

    执行流程:
      1. 查找 TASK_WORKER_BINDINGS 获取绑定的 Worker
      2. 若存在绑定且启用 → 调用 worker_registry.execute_worker_task()
         Worker 内部使用 Claude Agent SDK 执行
      3. 若无绑定或绑定禁用 → 回退到传统 Python 本地执行

    Args:
        task_name: 任务名称（对应 TASK_REGISTRY 的 key）

    Returns:
        任务执行结果
    """
    binding = TASK_WORKER_BINDINGS.get(task_name)

    if binding and binding.get("enabled", True):
        worker_code = binding["worker_code"]
        logger.info("Worker 分发: 任务 '%s' → Worker '%s' (SDK)", task_name, worker_code)
        try:
            from app.core.worker_registry import get_worker_registry
            registry = get_worker_registry()
            result = await registry.execute_worker_task(
                worker_code=worker_code,
                task_name=task_name,
                context={},
            )
            logger.info("Worker '%s' 执行任务 '%s' 完成", worker_code, task_name)
            return result
        except Exception as e:
            logger.warning("Worker '%s' 执行失败 (%s), 回退到本地执行", worker_code, e)
            # 回退到本地执行

    # 回退：本地传统执行
    logger.info("本地执行: 任务 '%s' (Python 直接调用)", task_name)
    func = _import_task_func(task_name)
    if asyncio.iscoroutinefunction(func):
        return await func()
    return func()


def _execute_via_worker_wrapper(task_name: str) -> Callable:
    """返回一个无参的 Callable，供 APScheduler add_job 使用。"""
    async def _wrapper():
        return await _execute_via_worker(task_name)
    _wrapper.__name__ = f"worker_{task_name}"
    _wrapper.__qualname__ = f"worker_{task_name}"
    return _wrapper


def _execute_product_worker_wrapper(task_name: str, product_id: str) -> Callable:
    """返回产品级任务的无参 Callable，自动注入 product_id 到执行上下文。"""
    async def _wrapper():
        binding = TASK_WORKER_BINDINGS.get(task_name)
        if binding and binding.get("enabled", True):
            worker_code = binding["worker_code"]
            from app.core.worker_registry import get_worker_registry
            registry = get_worker_registry()
            return await registry.execute_worker_task(
                worker_code=worker_code,
                task_name=task_name,
                context={"product_id": product_id},
            )
        # 回退：本地执行
        logger.info("本地执行(产品级): 任务 '%s' 产品 '%s'", task_name, product_id)
        func = _import_task_func(task_name)
        if asyncio.iscoroutinefunction(func):
            return await func()
        return func()
    short_id = product_id[:8] if len(product_id) > 8 else product_id
    _wrapper.__name__ = f"product_{task_name}_{short_id}"
    _wrapper.__qualname__ = _wrapper.__name__
    return _wrapper


# ── 产品级定时任务注册 ────────────────────────────

PRODUCT_TASK_DEFS = [
    {
        "task_name": "check_cert_expiry",
        "trigger_type": "cron",
        "trigger_args": {"hour": 10, "minute": 0},
    },
    {
        "task_name": "scan_regulation_changes",
        "trigger_type": "interval",
        "trigger_args": {"hours": 1},
    },
]
"""产品级定时任务的默认定义：每类产品任务在所有产品上自动创建。"""


def register_product_jobs(product_id: str):
    """为指定产品注册产品级定时任务。

    Args:
        product_id: 产品ID（如 p_led_de_001）

    每个产品会自动创建 check_cert_expiry 和 scan_regulation_changes
    两个专属定时任务，任务 ID 格式为 {task_type}_{product_id}。
    """
    scheduler = get_scheduler()
    if not scheduler:
        logger.warning("Scheduler not available, skipping product job registration")
        return

    count = 0
    for task_def in PRODUCT_TASK_DEFS:
        task_name = task_def["task_name"]
        trigger_type = task_def["trigger_type"]
        trigger_args = dict(task_def["trigger_args"])
        job_id = f"{task_name}_{product_id}"

        scheduler.add_job(
            _execute_product_worker_wrapper(task_name, product_id),
            trigger_type,
            id=job_id,
            name=f"{task_name}[{product_id[:12]}]",
            replace_existing=True,
            **trigger_args,
        )
        count += 1

    logger.info("已为产品 %s 注册 %d 个定时任务", product_id, count)


async def stop_scheduler():
    """应用关闭时调用 — 停止调度器。"""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")


# ── 定时任务函数 ──────────────────────────────────

async def poll_all_markets():
    """定时市场轮询 → AstraAssistant 联网搜索 → 影响分析 → 预警推送。

    对所有活跃用户执行一轮完整的风险扫描。
    """
    logger.info("Scheduler job: poll_all_markets started")
    try:
        from app.core.market_monitor import MarketMonitor
        from app.core.risk_alert import (
            create_alert, get_alerts, save_last_scan_time,
        )
        from app.services.ws_manager import ws_manager

        monitor = MarketMonitor()

        # 1. 获取所有活跃用户列表（简化：扫描 risk_alerts 目录）
        alerts_path = Path(settings.data_dir).resolve() / "risk_alerts"
        user_ids = []
        if alerts_path.exists():
            user_ids = [d.name for d in alerts_path.iterdir() if d.is_dir()]

        if not user_ids:
            # 默认用户
            user_ids = ["default"]

        for user_id in user_ids:
            # 2. AstraAssistant 联网搜索市场变更
            events = await monitor.poll_markets()

            for event in events:
                if not event.get("has_change"):
                    continue

                # 3. AstraAssistant 分析影响
                impacts = await monitor.analyze_impact(event)

                # 4. 生成预警
                alert = create_alert(
                    alert_type="regulation_change" if event.get("severity") in ("critical", "high") else "market_hotspot",
                    severity=event.get("severity", "medium"),
                    title=f"[{event.get('market', '?').upper()}] {event.get('summary', '法规变更')[:80]}",
                    description=event.get("summary", ""),
                    affected_markets=[event.get("market", "")],
                    affected_products=[i.get("product_id", "") for i in impacts if i.get("product_id")],
                    source=event.get("source", "Astra Market Monitor"),
                    source_url=event.get("source_url", ""),
                    user_ids=[user_id],
                )

                # 5. WebSocket 推送（如果用户在线）
                if ws_manager.is_connected(user_id):
                    await ws_manager.send_alert(user_id, alert)

            # 6. 更新扫描时间
            save_last_scan_time(user_id)

        logger.info(f"Scheduler job: poll_all_markets completed ({len(user_ids)} users)")

    except Exception as e:
        logger.error(f"Scheduler job: poll_all_markets failed: {e}", exc_info=True)


async def collect_metrics():
    """定时聚合指标（仅触发记录，数据实时读取）。"""
    logger.info("Scheduler job: collect_metrics started")
    try:
        from app.core.metrics import get_dashboard
        alerts_path = Path(settings.data_dir).resolve() / "risk_alerts"
        if alerts_path.exists():
            for user_dir in alerts_path.iterdir():
                if user_dir.is_dir():
                    user_id = user_dir.name
                    dashboard = get_dashboard(user_id)
                    logger.debug(
                        f"Metrics for {user_id}: "
                        f"products={dashboard['total_products']}, "
                        f"health={dashboard['health_score']:.1f}"
                    )
        logger.info("Scheduler job: collect_metrics completed")
    except Exception as e:
        logger.error(f"Scheduler job: collect_metrics failed: {e}", exc_info=True)


# ── 注册可调度任务模板（从 YAML 加载，无回退）──────────────────

TASKS_YAML = Path(settings.data_dir) / "scheduler" / "tasks.yaml"


def _register_tasks_from_yaml():
    """从 data/scheduler/tasks.yaml 加载任务定义。配置文件必须存在且正确。"""
    if not TASKS_YAML.exists():
        raise FileNotFoundError(
            f"任务配置文件不存在: {TASKS_YAML}\n"
            "请确保 data/scheduler/tasks.yaml 已创建"
        )
    data = yaml.safe_load(TASKS_YAML.read_text(encoding="utf-8"))
    tasks = data.get("tasks", [])
    if not tasks:
        raise ValueError(f"tasks.yaml 中未定义任何任务: {TASKS_YAML}")
    for t in tasks:
        register_task(
            name=t["task_name"],
            display_name=t.get("display_name", t["task_name"]),
            description=t.get("description", ""),
            default_trigger=t.get("default_trigger", "interval"),
            default_args=t.get("trigger_args", {}),
            worker_code=t.get("default_worker"),
        )
    logger.info("从 tasks.yaml 加载了 %d 个任务模板", len(tasks))


_register_tasks_from_yaml()

