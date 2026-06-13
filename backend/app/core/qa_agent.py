"""
QAAgent 系统自我管理智能体 — 负责系统配置管理、事件/Worker定义、健康诊断。

职责：
  1. 配置问答: 回答系统配置相关问题
  2. 事件管理: 注册/修改/删除事件类型
  3. Worker管理: 注册/修改/删除Worker类型
  4. 系统诊断: 健康检查、流水线调试
  5. 业务规则管理: 管理合规规则、通知规则
  6. 流程串联: 串联业务流程步骤

开源参考:
  - 自研，参考QwenPaw多智能体架构
  - 安全沙箱: 写操作需用户确认（guarded权限）

权限模型:
  - safe: 只读操作，无需审批
  - guarded: 写操作，需要用户确认
  - blocked: 危险操作，直接拒绝
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from app.config import settings
from app.models.schemas import (
    EventDefinition, WorkerDefinition, EventCategory,
    GuardResult, CLICommandResult
)

logger = logging.getLogger(__name__)

DATA_DIR = Path(settings.data_dir)


class QAAgent:
    """系统自我管理智能体

    工具集:
        - read_config: 读取系统配置 (safe)
        - write_config: 修改系统配置 (guarded)
        - query_events: 查询事件注册表 (safe)
        - register_event: 注册新事件类型 (guarded)
        - modify_event: 修改事件类型 (guarded)
        - delete_event: 删除事件类型 (guarded)
        - query_workers: 查询Worker注册表 (safe)
        - register_worker: 注册新Worker (guarded)
        - modify_worker: 修改Worker (guarded)
        - delete_worker: 删除Worker (guarded)
        - debug_pipeline: 调试事件管道 (safe)
        - health_check: 系统健康自检 (safe)
        - manage_rules: 管理业务规则 (guarded)
        - manage_notifications: 管理通知规则 (guarded)
        - query_scheduler: 查询定时任务列表 (safe)
        - schedule_job: 创建定时任务 (guarded)
        - modify_scheduler: 修改定时任务配置 (guarded)
        - remove_schedule: 删除定时任务 (guarded)
        - pause_schedule: 暂停定时任务 (guarded)
        - resume_schedule: 恢复定时任务 (guarded)
        - trigger_schedule: 立即触发定时任务 (guarded)
    """

    PERMISSIONS = {
        "read_config": "safe",
        "write_config": "guarded",
        "query_events": "safe",
        "register_event": "guarded",
        "modify_event": "guarded",
        "delete_event": "guarded",
        "query_workers": "safe",
        "register_worker": "guarded",
        "modify_worker": "guarded",
        "delete_worker": "guarded",
        "debug_pipeline": "safe",
        "health_check": "safe",
        "manage_rules": "guarded",
        "manage_notifications": "guarded",
        "query_scheduler": "safe",
        "schedule_job": "guarded",
        "modify_scheduler": "guarded",
        "remove_schedule": "guarded",
        "pause_schedule": "guarded",
        "resume_schedule": "guarded",
        "trigger_schedule": "guarded",
    }

    def __init__(self, event_registry=None, worker_registry=None):
        self._event_registry = event_registry
        self._worker_registry = worker_registry
        self._config_dir = DATA_DIR / "config"
        self._events_dir = DATA_DIR / "events" / "builtin"
        self._workers_dir = DATA_DIR / "workers" / "builtin"
        self._rules_dir = DATA_DIR / "rules"
        self._notification_config_file = DATA_DIR / "notifications" / "config.json"
        # 所有可扫描的配置目录（read_config 概览 + health_check）
        self._scan_dirs = [
            self._config_dir,
            self._events_dir,
            self._workers_dir,
            DATA_DIR / "skills",
            DATA_DIR / "tools",
            DATA_DIR / "agents",
            DATA_DIR / "scheduler",
            DATA_DIR / "models",
            DATA_DIR / "oauth",
            self._rules_dir,
            DATA_DIR / "notifications",
            DATA_DIR / "prompts",
            DATA_DIR / "event_chain",
            DATA_DIR / "stages",
        ]

    def set_registries(self, event_registry, worker_registry):
        """设置事件和Worker注册表（延迟注入，避免循环依赖）"""
        self._event_registry = event_registry
        self._worker_registry = worker_registry

    # ── 权限检查 ──────────────────────────────────

    def check_permission(self, tool: str) -> GuardResult:
        """检查工具调用权限"""
        permission = self.PERMISSIONS.get(tool, "blocked")

        if permission == "safe":
            return GuardResult(allowed=True)
        elif permission == "guarded":
            return GuardResult(allowed=True, need_confirm=True, reason=f"操作 {tool} 需要用户确认")
        else:
            return GuardResult(allowed=False, reason=f"操作 {tool} 被禁止")

    # ── 配置管理 ──────────────────────────────────

    async def read_config(self, config_path: str = None) -> Dict[str, Any]:
        """读取系统配置

        config_path 支持两种形式:
          - 相对路径 (如 'events/builtin/product_created.md') → 解析到 DATA_DIR 下
          - 省略 → 返回所有配置目录的文件概览
        """
        if config_path:
            # 从 DATA_DIR 解析
            file_path = DATA_DIR / config_path
            if not file_path.exists():
                return {"error": f"配置文件不存在: {config_path}"}
            # 安全检查: 禁止路径穿越
            try:
                file_path.resolve().relative_to(DATA_DIR.resolve())
            except ValueError:
                return {"error": f"非法路径: {config_path}"}
            try:
                if file_path.suffix == ".json":
                    return json.loads(file_path.read_text(encoding="utf-8"))
                elif file_path.suffix in (".yaml", ".yml"):
                    try:
                        import yaml
                        return yaml.safe_load(file_path.read_text(encoding="utf-8"))
                    except Exception:
                        return {"content": file_path.read_text(encoding="utf-8")}
                else:
                    return {"content": file_path.read_text(encoding="utf-8")}
            except Exception as e:
                return {"error": str(e)}

        # 返回配置概览（扫描所有配置子目录）
        configs = {}
        for scan_dir in self._scan_dirs:
            if scan_dir.exists():
                for f in scan_dir.rglob("*"):
                    if f.is_file() and not f.name.startswith("_"):
                        rel_path = str(f.relative_to(DATA_DIR))
                        configs[rel_path] = f.stat().st_size
        return {"config_files": configs}

    async def write_config(self, config_path: str, content: Any) -> bool:
        """写入系统配置（需要用户确认）

        config_path 支持相对路径，解析到 DATA_DIR 下对应的子目录。
        例如: 'events/builtin/custom_events.md' → data/events/builtin/custom_events.md
        """
        # 优先从 DATA_DIR 解析，兼容新目录结构
        file_path = DATA_DIR / config_path
        # 安全检查: 禁止路径穿越
        try:
            file_path.resolve().relative_to(DATA_DIR.resolve())
        except ValueError:
            raise ValueError(f"非法路径: {config_path}")

        file_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content, dict):
            if file_path.suffix in (".yaml", ".yml"):
                try:
                    import yaml
                    file_path.write_text(
                        yaml.dump(content, allow_unicode=True, default_flow_style=False),
                        encoding="utf-8",
                    )
                    return True
                except Exception:
                    pass
            file_path.write_text(
                json.dumps(content, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        else:
            file_path.write_text(str(content), encoding="utf-8")

        return True

    # ── 事件管理 ──────────────────────────────────

    async def add_event_type(
        self,
        event_code: str,
        event_name: str,
        business_stage: str,
        trigger_condition: str,
        related_worker: str = "",
        severity: str = "low",
        notify_strategy: List[str] = None,
    ) -> bool:
        """添加新事件类型"""
        if not self._event_registry:
            raise RuntimeError("事件注册表未初始化")

        # 验证唯一性
        if self._event_registry.get_event(event_code):
            raise ValueError(f"事件编码 {event_code} 已存在")

        # 验证关联Worker
        if related_worker and self._worker_registry:
            if not self._worker_registry.get_worker(related_worker):
                raise ValueError(f"Worker {related_worker} 不存在")

        event_def = EventDefinition(
            event_code=event_code,
            event_name=event_name,
            business_stage=business_stage,
            trigger_condition=trigger_condition,
            related_worker=related_worker,
            severity=severity,
            notify_strategy=notify_strategy or ["dashboard"],
        )

        return await self._event_registry.register_event(event_def)

    async def modify_event_type(self, event_code: str, **kwargs) -> bool:
        """修改事件类型"""
        if not self._event_registry:
            raise RuntimeError("事件注册表未初始化")

        event = self._event_registry.get_event(event_code)
        if not event:
            raise ValueError(f"事件 {event_code} 不存在")

        for key, value in kwargs.items():
            if hasattr(event, key) and key not in ("event_code", "created_at"):
                setattr(event, key, value)

        return await self._event_registry.update_event(event)

    async def delete_event_type(self, event_code: str) -> bool:
        """删除事件类型"""
        if not self._event_registry:
            raise RuntimeError("事件注册表未初始化")
        return await self._event_registry.delete_event(event_code)

    async def list_event_types(
        self, stage: str = None, category: EventCategory = None
    ) -> List[EventDefinition]:
        """列出事件类型"""
        if not self._event_registry:
            return []
        if stage:
            return self._event_registry.get_events_by_stage(stage)
        if category:
            return self._event_registry.get_events_by_category(category)
        return self._event_registry.get_all_events()

    # ── Worker管理 ──────────────────────────────────

    async def add_worker_type(
        self,
        worker_code: str,
        worker_name: str,
        business_stage: str,
        description: str,
        available_skills: List[str] = None,
        priority: int = 5,
    ) -> bool:
        """添加新Worker类型"""
        if not self._worker_registry:
            raise RuntimeError("Worker注册表未初始化")

        if self._worker_registry.get_worker(worker_code):
            raise ValueError(f"Worker编码 {worker_code} 已存在")

        worker_def = WorkerDefinition(
            worker_code=worker_code,
            worker_name=worker_name,
            business_stage=business_stage,
            description=description,
            available_skills=available_skills or [],
            priority=priority,
        )

        return await self._worker_registry.register_worker(worker_def)

    async def modify_worker_type(self, worker_code: str, **kwargs) -> bool:
        """修改Worker类型"""
        if not self._worker_registry:
            raise RuntimeError("Worker注册表未初始化")

        worker = self._worker_registry.get_worker(worker_code)
        if not worker:
            raise ValueError(f"Worker {worker_code} 不存在")

        for key, value in kwargs.items():
            if hasattr(worker, key) and key not in ("worker_code", "created_at"):
                setattr(worker, key, value)

        return await self._worker_registry.update_worker(worker)

    async def delete_worker_type(self, worker_code: str) -> bool:
        """删除Worker类型"""
        if not self._worker_registry:
            raise RuntimeError("Worker注册表未初始化")
        return await self._worker_registry.delete_worker(worker_code)

    async def list_worker_types(self, stage: str = None) -> List[WorkerDefinition]:
        """列出Worker类型"""
        if not self._worker_registry:
            return []
        if stage:
            return self._worker_registry.get_workers_by_stage(stage)
        return self._worker_registry.get_all_workers()

    # ── SDK 分析辅助 ──────────────────────────────

    async def _sdk_analyze(self, prompt_name: str, context: Dict[str, Any]) -> str:
        """通过 Claude SDK 执行智能分析。

        将数据上下文传给 Claude，返回分析结果文本。
        若 SDK 不可用，返回空字符串表示降级。
        """
        try:
            from app.services.astra_assistant import AstraAssistant, check_sdk
            if not check_sdk():
                return ""
            assistant = AstraAssistant()
            result = await assistant.run_task(
                prompt_name=prompt_name,
                context=context,
            )
            if isinstance(result, dict):
                return result.get("raw_text", "") or result.get("response", "") or json.dumps(result, ensure_ascii=False)
            return str(result)
        except Exception as e:
            logger.debug("SDK 分析不可用: %s", e)
            return ""

    # ── 系统诊断 ──────────────────────────────────

    async def health_check(self) -> Dict[str, Any]:
        """系统健康自检（含可选 SDK 智能分析）"""
        status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {},
            "overall": "healthy",
        }

        # 检查事件总线
        try:
            from app.core.event_bus import get_event_bus
            bus = get_event_bus()
            stats = bus.get_event_stats()
            status["checks"]["event_bus"] = {"status": "healthy", "stats": stats}
        except Exception as e:
            status["checks"]["event_bus"] = {"status": "error", "error": str(e)}
            status["overall"] = "degraded"

        # 检查产品存储
        try:
            from app.core.product_storage import get_product_storage
            storage = get_product_storage()
            count = storage.count_products()
            status["checks"]["product_storage"] = {"status": "healthy", "products": count}
        except Exception as e:
            status["checks"]["product_storage"] = {"status": "error", "error": str(e)}
            status["overall"] = "degraded"

        # 检查事件注册表
        try:
            if self._event_registry:
                events = self._event_registry.get_all_events()
                status["checks"]["event_registry"] = {"status": "healthy", "events": len(events)}
            else:
                status["checks"]["event_registry"] = {"status": "not_initialized"}
        except Exception as e:
            status["checks"]["event_registry"] = {"status": "error", "error": str(e)}

        # 检查Worker注册表
        try:
            if self._worker_registry:
                workers = self._worker_registry.get_all_workers()
                status["checks"]["worker_registry"] = {"status": "healthy", "workers": len(workers)}
            else:
                status["checks"]["worker_registry"] = {"status": "not_initialized"}
        except Exception as e:
            status["checks"]["worker_registry"] = {"status": "error", "error": str(e)}

        # 检查事件配置目录
        dir_path = self._events_dir
        if dir_path.exists():
            files = list(dir_path.glob("*.md"))
            status["checks"]["events_builtin"] = {"status": "healthy", "files": len(files)}
        else:
            status["checks"]["events_builtin"] = {"status": "missing"}

        # 检查Worker配置目录
        dir_path = self._workers_dir
        if dir_path.exists():
            files = list(dir_path.glob("*.md"))
            status["checks"]["workers_builtin"] = {"status": "healthy", "files": len(files)}
        else:
            status["checks"]["workers_builtin"] = {"status": "missing"}

        # 可选：Claude 智能分析健康报告
        if status.get("overall") != "healthy":
            analysis = await self._sdk_analyze("health_analysis", {
                "checks": status["checks"],
                "overall": status["overall"],
                "timestamp": status["timestamp"],
            })
            if analysis:
                status["analysis"] = analysis

        return status

    async def debug_pipeline(self, event_type: str = None) -> Dict[str, Any]:
        """调试事件管道"""
        result = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "steps": [],
        }

        # Step 1: 事件注册表查询
        if self._event_registry and event_type:
            event_def = self._event_registry.get_event(event_type)
            if event_def:
                result["steps"].append({
                    "step": "event_lookup",
                    "status": "found",
                    "data": event_def.model_dump(default=str),
                })
            else:
                result["steps"].append({
                    "step": "event_lookup",
                    "status": "not_found",
                    "suggestion": f"事件 {event_type} 未注册，可通过 add_event_type 注册",
                })

        # Step 2: 关联Worker查询
        if self._worker_registry and event_def:
            workers = self._worker_registry.get_workers_by_stage(event_def.business_stage)
            result["steps"].append({
                "step": "worker_lookup",
                "status": "found" if workers else "no_match",
                "workers": [w.worker_code for w in workers],
            })

        # Step 3: 事件总线状态
        try:
            from app.core.event_bus import get_event_bus
            bus = get_event_bus()
            recent = bus.get_recent_events(limit=5, severity="high")
            result["steps"].append({
                "step": "bus_check",
                "status": "healthy",
                "recent_high_severity": len(recent),
            })
        except Exception as e:
            result["steps"].append({
                "step": "bus_check",
                "status": "error",
                "error": str(e),
            })

        return result

    # ── 业务规则管理 ──────────────────────────────────

    async def get_rules(self, rule_type: str = None) -> Dict[str, Any]:
        """获取业务规则"""
        rules_dir = self._rules_dir
        if not rules_dir.exists():
            return {"rules": {}, "message": "暂无自定义规则"}

        rules = {}
        for f in rules_dir.glob("*.json"):
            if rule_type and f.stem != rule_type:
                continue
            try:
                rules[f.stem] = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                rules[f.stem] = {"error": "解析失败"}

        return {"rules": rules}

    async def set_rule(self, rule_type: str, rule_data: Dict[str, Any]) -> bool:
        """设置业务规则（含可选 SDK 语义验证）"""
        # SDK 验证：让 Claude 检查规则配置语义合理性
        analysis = await self._sdk_analyze("rule_validation", {
            "rule_type": rule_type,
            "rule_data": rule_data,
        })
        if analysis:
            logger.info("规则 '%s' 设置前 SDK 分析: %s", rule_type, analysis[:200])

        self._rules_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._rules_dir / f"{rule_type}.json"
        file_path.write_text(
            json.dumps(rule_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True

    async def manage_rules(self, action: str, rule_type: str = None, rule_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """高级规则管理：支持 SDK 智能分析变更

        Args:
            action: "list" | "get" | "set" | "delete"
            rule_type: 规则类型
            rule_data: 规则数据（set 时需要）
        """
        if action == "list":
            return await self.get_rules(rule_type)
        elif action == "get":
            rules = await self.get_rules(rule_type)
            if rule_type and rule_type in rules.get("rules", {}):
                return {"rule": rules["rules"][rule_type]}
            return rules
        elif action == "set" and rule_type and rule_data:
            ok = await self.set_rule(rule_type, rule_data)
            return {"success": ok, "rule_type": rule_type}
        elif action == "delete" and rule_type:
            file_path = self._rules_dir / f"{rule_type}.json"
            if file_path.exists():
                file_path.unlink()
            return {"success": True, "rule_type": rule_type}
        return {"error": f"无效操作: {action}"}

    # ── 通知配置管理 ──────────────────────────────────

    async def get_notification_config(self) -> Dict[str, Any]:
        """获取通知配置。配置文件必须存在。"""
        if not self._notification_config_file.exists():
            raise FileNotFoundError(
                f"通知配置文件不存在: {self._notification_config_file}\n"
                "请确保 data/notifications/config.json 已创建"
            )
        return json.loads(self._notification_config_file.read_text(encoding="utf-8"))

    async def set_notification_config(self, config: Dict[str, Any]) -> bool:
        """更新通知配置（含可选 SDK 智能验证）"""
        # SDK 验证：让 Claude 检查通知配置变更
        analysis = await self._sdk_analyze("notification_validation", {
            "config": config,
        })
        if analysis:
            logger.info("通知配置 SDK 分析: %s", analysis[:200])

        self._notification_config_file.parent.mkdir(parents=True, exist_ok=True)
        self._notification_config_file.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True

    async def manage_notifications(self, action: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """高级通知管理：支持 SDK 智能分析通知策略

        Args:
            action: "get" | "set"
            config: 通知配置（set 时需要）
        """
        if action == "get":
            return await self.get_notification_config()
        elif action == "set" and config:
            ok = await self.set_notification_config(config)
            return {"success": ok}
        return {"error": f"无效操作: {action}"}

    # ── 定时任务管理 ──────────────────────────────────

    async def query_scheduler(self) -> Dict[str, Any]:
        """查询所有定时任务状态"""
        from app.core.scheduler import get_scheduler
        scheduler = get_scheduler()
        if not scheduler:
            return {"enabled": False, "jobs": [], "message": "调度器未运行"}
        jobs = scheduler.get_jobs()
        return {
            "enabled": True,
            "jobs": [
                {
                    "id": j.id,
                    "name": j.name or j.id,
                    "trigger": str(type(j.trigger).__name__),
                    "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None,
                    "pending": j.pending,
                }
                for j in jobs
            ],
            "total": len(jobs),
        }

    async def schedule_job(
        self,
        task: str,
        trigger_type: str = "interval",
        trigger_args: Dict[str, Any] = None,
        job_id: str = None,
    ) -> Dict[str, Any]:
        """创建定时任务

        Args:
            task: 任务名称（使用 query_available_tasks 查看可用列表）
            trigger_type: "interval" 或 "cron"
            trigger_args: 触发器参数，如 {"minutes": 30} 或 {"hour": 9, "minute": 0}
            job_id: 自定义任务ID，不传则使用任务名
        """
        from app.core.scheduler import get_scheduler, _import_task_func
        scheduler = get_scheduler()
        if not scheduler:
            return {"success": False, "error": "调度器未运行"}

        try:
            func = _import_task_func(task)
            scheduler.add_job(
                func,
                trigger_type,
                id=job_id or task,
                name=task,
                replace_existing=True,
                **(trigger_args or {}),
            )
            return {
                "success": True,
                "job_id": job_id or task,
                "task": task,
                "trigger": trigger_type,
                "message": f"定时任务 '{task}' 创建成功",
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": f"创建失败: {e}"}

    async def query_available_tasks(self) -> Dict[str, Any]:
        """查询可调度的任务模板列表"""
        from app.core.scheduler import get_available_tasks
        tasks = get_available_tasks()
        return {"tasks": tasks, "total": len(tasks)}

    async def modify_scheduler(
        self,
        job_id: str,
        trigger_type: str = None,
        trigger_args: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """修改定时任务触发器配置

        Args:
            job_id: 任务ID
            trigger_type: 新的触发器类型（不传则保留原类型）
            trigger_args: 新的触发器参数
        """
        from app.core.scheduler import get_scheduler
        scheduler = get_scheduler()
        if not scheduler:
            return {"success": False, "error": "调度器未运行"}

        try:
            job = scheduler.get_job(job_id)
            if not job:
                return {"success": False, "error": f"任务 {job_id} 不存在"}

            if trigger_args:
                scheduler.reschedule_job(job_id, trigger=trigger_type or job.trigger, **trigger_args)
            return {
                "success": True,
                "job_id": job_id,
                "message": f"任务 '{job_id}' 配置已更新",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def remove_schedule(self, job_id: str) -> Dict[str, Any]:
        """删除定时任务"""
        from app.core.scheduler import get_scheduler
        scheduler = get_scheduler()
        if not scheduler:
            return {"success": False, "error": "调度器未运行"}
        try:
            scheduler.remove_job(job_id)
            return {"success": True, "job_id": job_id, "message": f"任务 '{job_id}' 已删除"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def pause_schedule(self, job_id: str) -> Dict[str, Any]:
        """暂停定时任务"""
        from app.core.scheduler import get_scheduler
        scheduler = get_scheduler()
        if not scheduler:
            return {"success": False, "error": "调度器未运行"}
        try:
            scheduler.pause_job(job_id)
            return {"success": True, "job_id": job_id, "status": "paused"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def resume_schedule(self, job_id: str) -> Dict[str, Any]:
        """恢复定时任务"""
        from app.core.scheduler import get_scheduler
        scheduler = get_scheduler()
        if not scheduler:
            return {"success": False, "error": "调度器未运行"}
        try:
            scheduler.resume_job(job_id)
            return {"success": True, "job_id": job_id, "status": "active"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def trigger_schedule(self, job_id: str) -> Dict[str, Any]:
        """立即触发定时任务"""
        from app.core.scheduler import get_scheduler
        scheduler = get_scheduler()
        if not scheduler:
            return {"success": False, "error": "调度器未运行"}
        try:
            from datetime import datetime
            scheduler.reschedule_job(job_id, next_run_time=datetime.now())
            return {"success": True, "job_id": job_id, "status": "triggered"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── CLI命令路由表 ────────────────────────────────

    async def _cmd_status(self, args: Dict[str, Any]) -> dict:
        health = await self.health_check()
        return {"output": json.dumps(health, ensure_ascii=False, indent=2)}

    async def _cmd_events(self, args: Dict[str, Any]) -> dict:
        events = await self.list_event_types()
        output = f"已注册事件: {len(events)}\n"
        for e in events[:20]:
            output += f"  [{e.severity}] {e.event_code}: {e.event_name}\n"
        return {"output": output}

    async def _cmd_workers(self, args: Dict[str, Any]) -> dict:
        workers = await self.list_worker_types()
        output = f"已注册Worker: {len(workers)}\n"
        for w in workers:
            output += f"  [P{w.priority}] {w.worker_code}: {w.worker_name}\n"
        return {"output": output}

    async def _cmd_debug(self, args: Dict[str, Any]) -> dict:
        event_type = args.get("event_type", "")
        result = await self.debug_pipeline(event_type)
        return {"output": json.dumps(result, ensure_ascii=False, indent=2)}

    async def _cmd_products(self, args: Dict[str, Any]) -> dict:
        from app.core.product_storage import get_product_storage
        storage = get_product_storage()
        products = storage.list_products(limit=20)
        output = f"产品总数: {storage.count_products()}\n"
        for p in products:
            output += f"  [{p.lifecycle_stage.value}] {p.id}: {p.name}\n"
        return {"output": output}

    async def _cmd_scheduler(self, args: Dict[str, Any]) -> dict:
        result = await self.query_scheduler()
        if not result.get("enabled"):
            return {"output": "调度器未运行\n"}
        output = f"调度器状态: 运行中\n定时任务总数: {result['total']}\n\n"
        for j in result["jobs"]:
            status = "⏸ 暂停" if j["pending"] else "▶ 运行"
            next_run = j["next_run_time"] or "—"
            output += f"  {status} [{j['id']}] {j['name']}\n"
            output += f"       触发器: {j['trigger']} | 下次执行: {next_run}\n"
        return {"output": output}

    async def _cmd_schedule(self, args: Dict[str, Any]) -> dict:
        task = args.get("task", "")
        action = args.get("action", "list")
        if action == "list":
            tasks = await self.query_available_tasks()
            output = f"可调度任务模板: {tasks['total']}\n"
            for name, info in tasks["tasks"].items():
                output += f"  • {name}: {info['description']}\n"
                output += f"    默认触发器: {info['default_trigger']} | 默认参数: {info['default_args']}\n"
            return {"output": output}
        elif action == "create" and task:
            result = await self.schedule_job(
                task=task,
                trigger_type=args.get("trigger_type", "interval"),
                trigger_args=args.get("trigger_args", {}),
                job_id=args.get("job_id"),
            )
            return {
                "output": result.get("message", "") if result["success"] else "",
                "success": result["success"],
                "error": result.get("error", "") if not result["success"] else "",
            }
        else:
            return {
                "success": False,
                "error": "用法: astra schedule action=list|create task=<任务名> trigger_type=interval|cron",
            }

    # 命令路由表: 命令名 → 处理方法
    CLI_COMMANDS: Dict[str, str] = {
        "astra status": "_cmd_status",
        "astra events": "_cmd_events",
        "astra workers": "_cmd_workers",
        "astra debug": "_cmd_debug",
        "astra products": "_cmd_products",
        "astra scheduler": "_cmd_scheduler",
        "astra schedule": "_cmd_schedule",
    }

    # ── CLI命令执行 ──────────────────────────────────

    async def execute_cli_command(self, command: str, args: Dict[str, Any] = None) -> CLICommandResult:
        """执行CLI命令 — 通过路由表分发，新增命令只需注册到 CLI_COMMANDS"""
        args = args or {}
        start_time = datetime.now(timezone.utc)

        try:
            handler_name = self.CLI_COMMANDS.get(command)
            if not handler_name:
                return CLICommandResult(
                    command=command,
                    success=False,
                    error=f"未知命令: {command}",
                )

            handler = getattr(self, handler_name)
            result = await handler(args)

            return CLICommandResult(
                command=command,
                success=result.get("success", True),
                output=result.get("output", ""),
                error=result.get("error", ""),
            )
        except Exception as e:
            return CLICommandResult(
                command=command,
                success=False,
                error=str(e),
            )
        finally:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            # 记录耗时（不阻塞）


# ── 全局单例 ──────────────────────────────────

_qa_agent: Optional[QAAgent] = None


def get_qa_agent() -> QAAgent:
    """获取QAAgent单例"""
    global _qa_agent
    if _qa_agent is None:
        _qa_agent = QAAgent()
    return _qa_agent
