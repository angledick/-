"""QAAgent 系统管理工具 — 基于 Claude Agent SDK @tool 装饰器。

将 QAAgent 的全部 22+ 系统管理能力注册为 MCP 工具，
通过 create_sdk_mcp_server() 注入 Claude Agent SDK，
使 Claude 可直接调用系统管理功能。

工具权限模型（与 QAAgent 一致）:
  - safe:     只读操作，无需审批
  - guarded:  写操作，需要用户确认

工具清单:
  配置管理:          read_config (safe) / write_config (guarded)
  事件管理:          list_events (safe) / register_event (guarded)
                     modify_event (guarded) / delete_event (guarded)
  Worker管理:        list_workers (safe) / register_worker (guarded)
                     modify_worker (guarded) / delete_worker (guarded)
  系统诊断:          health_check (safe) / debug_pipeline (safe)
  业务规则:          get_rules (safe) / set_rule (guarded) / manage_rules (guarded)
  通知管理:          get_notification_config (safe) / set_notification_config (guarded)
  定时任务:          query_scheduler (safe) / schedule_job (guarded)
                     modify_scheduler (guarded) / remove_schedule (guarded)
                     pause_schedule (guarded) / resume_schedule (guarded)
                     trigger_schedule (guarded)
  CLI命令:           execute_cli_command (guarded)
"""

import json
from typing import Any

_tool = None
_create_server = None


def _lazy_import():
    """延迟导入 claude_agent_sdk，避免未安装时崩溃。"""
    global _tool, _create_server
    if _tool is not None:
        return
    try:
        from claude_agent_sdk import tool as _t, create_sdk_mcp_server as _c
        _tool = _t
        _create_server = _c
    except ImportError:
        _tool = None  # 标记不可用


def _ensure_tools_available():
    _lazy_import()
    if _tool is None:
        raise ImportError("claude-agent-sdk 未安装，无法注册 MCP 工具")


def _to_text_response(data: Any) -> dict:
    """将结果转换为 MCP text content 响应。"""
    return {
        "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}]
    }


_QA_TOOLS: list = []


def _register_tools():
    """注册所有 QAAgent 系统管理工具。"""
    global _QA_TOOLS
    if _QA_TOOLS:
        return _QA_TOOLS
    _lazy_import()
    if _tool is None:
        return []

    from claude_agent_sdk import ToolAnnotations

    # ═══════════════════════════════════════════════════════
    # 1. 配置管理
    # ═══════════════════════════════════════════════════════

    @_tool(
        "read_config",
        "读取系统配置文件内容。返回指定配置文件的内容或配置目录概览。",
        {"config_path": {"type": "string", "description": "配置文件相对路径（如 events/compliance_event.json），留空返回所有配置文件列表"}},
        annotations=ToolAnnotations(maxResultSizeChars=8000),
    )
    async def read_config_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        result = await agent.read_config(args.get("config_path"))
        return _to_text_response(result)

    @_tool(
        "write_config",
        "写入系统配置文件（需要用户确认）。用于修改系统配置、事件定义、Worker定义等。",
        {"config_path": {"type": "string", "description": "配置文件相对路径（如 events/compliance_event.json）"}, "content": {"type": "object", "description": "要写入的配置内容（JSON对象）"}},
        annotations=ToolAnnotations(maxResultSizeChars=2000),
    )
    async def write_config_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        ok = await agent.write_config(args["config_path"], args["content"])
        return _to_text_response({"success": ok, "config_path": args["config_path"]})

    # ═══════════════════════════════════════════════════════
    # 2. 事件管理
    # ═══════════════════════════════════════════════════════

    @_tool(
        "list_events",
        "查询所有已注册事件类型。可按业务阶段或事件类别筛选。返回事件定义列表。",
        {"stage": {"type": "string", "description": "按业务阶段筛选（如 compliance、logistics、marketing），可选"}, "category": {"type": "string", "description": "按事件类别筛选（如 product_lifecycle、compliance_check、risk_alert），可选"}},
    )
    async def list_events_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        from app.models.schemas import EventCategory
        stage = args.get("stage")
        category = EventCategory(args["category"]) if args.get("category") else None
        events = await agent.list_event_types(stage=stage, category=category)
        return _to_text_response({
            "total": len(events),
            "events": [e.model_dump() for e in events],
        })

    @_tool(
        "register_event",
        "注册新的业务事件类型（需要用户确认）。定义触发条件和关联Worker。",
        {
            "event_code": {"type": "string", "description": "事件唯一编码，如 compliance_check_requested"},
            "event_name": {"type": "string", "description": "事件中文名称，如 合规检查请求"},
            "business_stage": {"type": "string", "description": "所属业务阶段，如 compliance、logistics"},
            "trigger_condition": {"type": "string", "description": "触发条件描述"},
            "related_worker": {"type": "string", "description": "关联Worker编码（可选）"},
            "severity": {"type": "string", "description": "严重级别: low/medium/high/critical"},
        },
    )
    async def register_event_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        try:
            ok = await agent.add_event_type(
                event_code=args["event_code"],
                event_name=args["event_name"],
                business_stage=args["business_stage"],
                trigger_condition=args["trigger_condition"],
                related_worker=args.get("related_worker", ""),
                severity=args.get("severity", "low"),
                notify_strategy=args.get("notify_strategy"),
            )
            return _to_text_response({"success": ok, "event_code": args["event_code"]})
        except (ValueError, RuntimeError) as e:
            return _to_text_response({"success": False, "error": str(e)})

    @_tool(
        "modify_event",
        "修改已注册事件类型的配置（需要用户确认）。可按需更新事件名称、触发条件、关联Worker等。",
        {
            "event_code": {"type": "string", "description": "要修改的事件编码"},
            "event_name": {"type": "string", "description": "新事件名称（可选）"},
            "trigger_condition": {"type": "string", "description": "新触发条件（可选）"},
            "severity": {"type": "string", "description": "新严重级别: low/medium/high/critical（可选）"},
            "related_worker": {"type": "string", "description": "新关联Worker编码（可选）"},
            "notify_strategy": {"type": "array", "items": {"type": "string"}, "description": "新通知策略列表（可选）"},
        },
    )
    async def modify_event_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        try:
            kwargs = {k: v for k, v in args.items() if k != "event_code" and v is not None}
            ok = await agent.modify_event_type(args["event_code"], **kwargs)
            return _to_text_response({"success": ok, "event_code": args["event_code"]})
        except (ValueError, RuntimeError) as e:
            return _to_text_response({"success": False, "error": str(e)})

    @_tool(
        "delete_event",
        "删除已注册事件类型（需要用户确认）。执行后不可恢复。",
        {"event_code": {"type": "string", "description": "要删除的事件编码"}},
    )
    async def delete_event_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        try:
            ok = await agent.delete_event_type(args["event_code"])
            return _to_text_response({"success": ok, "event_code": args["event_code"]})
        except RuntimeError as e:
            return _to_text_response({"success": False, "error": str(e)})

    # ═══════════════════════════════════════════════════════
    # 3. Worker管理
    # ═══════════════════════════════════════════════════════

    @_tool(
        "list_workers",
        "查询所有已注册Worker类型。可按业务阶段筛选。返回Worker定义列表（含可用Skills和优先级）。",
        {"stage": {"type": "string", "description": "按业务阶段筛选（可选）"}},
    )
    async def list_workers_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        stage = args.get("stage")
        workers = await agent.list_worker_types(stage=stage)
        return _to_text_response({
            "total": len(workers),
            "workers": [w.model_dump() for w in workers],
        })

    @_tool(
        "register_worker",
        "注册新的Worker执行单元（需要用户确认）。定义Worker的职责、可用Skills和优先级。",
        {
            "worker_code": {"type": "string", "description": "Worker唯一编码"},
            "worker_name": {"type": "string", "description": "Worker中文名称"},
            "business_stage": {"type": "string", "description": "所属业务阶段"},
            "description": {"type": "string", "description": "Worker职责描述"},
            "available_skills": {"type": "array", "items": {"type": "string"}, "description": "可用技能列表"},
            "priority": {"type": "number", "description": "优先级（1-10，1最高）"},
        },
    )
    async def register_worker_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        try:
            ok = await agent.add_worker_type(
                worker_code=args["worker_code"],
                worker_name=args["worker_name"],
                business_stage=args["business_stage"],
                description=args["description"],
                available_skills=args.get("available_skills", []),
                priority=args.get("priority", 5),
            )
            return _to_text_response({"success": ok, "worker_code": args["worker_code"]})
        except (ValueError, RuntimeError) as e:
            return _to_text_response({"success": False, "error": str(e)})

    @_tool(
        "modify_worker",
        "修改已注册Worker类型配置（需要用户确认）。",
        {
            "worker_code": {"type": "string", "description": "Worker编码"},
            "worker_name": {"type": "string", "description": "新名称（可选）"},
            "description": {"type": "string", "description": "新描述（可选）"},
            "available_skills": {"type": "array", "items": {"type": "string"}, "description": "新技能列表（可选）"},
            "priority": {"type": "number", "description": "新优先级（可选）"},
        },
    )
    async def modify_worker_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        try:
            kwargs = {k: v for k, v in args.items() if k != "worker_code" and v is not None}
            ok = await agent.modify_worker_type(args["worker_code"], **kwargs)
            return _to_text_response({"success": ok, "worker_code": args["worker_code"]})
        except (ValueError, RuntimeError) as e:
            return _to_text_response({"success": False, "error": str(e)})

    @_tool(
        "delete_worker",
        "删除已注册Worker类型（需要用户确认）。执行后不可恢复。",
        {"worker_code": {"type": "string", "description": "要删除的Worker编码"}},
    )
    async def delete_worker_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        try:
            ok = await agent.delete_worker_type(args["worker_code"])
            return _to_text_response({"success": ok, "worker_code": args["worker_code"]})
        except RuntimeError as e:
            return _to_text_response({"success": False, "error": str(e)})

    # ═══════════════════════════════════════════════════════
    # 4. 系统诊断
    # ═══════════════════════════════════════════════════════

    @_tool(
        "health_check",
        "执行系统健康自检。检查事件总线、产品存储、事件注册表、Worker注册表等核心组件的运行状态，返回整体健康评分和诊断详情。",
        {},
        annotations=ToolAnnotations(maxResultSizeChars=6000),
    )
    async def health_check_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        return _to_text_response(await agent.health_check())

    @_tool(
        "debug_pipeline",
        "调试事件管道。查看指定事件的完整链路：事件注册 → Worker绑定 → 总线状态。帮助排查事件流问题。",
        {"event_type": {"type": "string", "description": "要调试的事件编码（可选，留空返回管道概览）"}},
        annotations=ToolAnnotations(maxResultSizeChars=6000),
    )
    async def debug_pipeline_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        return _to_text_response(await agent.debug_pipeline(args.get("event_type")))

    # ═══════════════════════════════════════════════════════
    # 5. 业务规则管理
    # ═══════════════════════════════════════════════════════

    @_tool(
        "get_rules",
        "获取业务规则配置。可按规则类型筛选。返回规则内容（JSON格式）。",
        {"rule_type": {"type": "string", "description": "规则类型（如 compliance_scoring），可选"}},
    )
    async def get_rules_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        return _to_text_response(await agent.get_rules(args.get("rule_type")))

    @_tool(
        "manage_rules",
        "高级规则管理：增删改查业务规则（修改需要用户确认）。支持 SDK 智能分析规则变更。",
        {
            "action": {"type": "string", "description": "操作类型: list | get | set | delete"},
            "rule_type": {"type": "string", "description": "规则类型（set/delete 时必填）"},
            "rule_data": {"type": "object", "description": "规则数据（set 时需要）"},
        },
    )
    async def manage_rules_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        return _to_text_response(await agent.manage_rules(
            action=args["action"],
            rule_type=args.get("rule_type"),
            rule_data=args.get("rule_data"),
        ))

    # ═══════════════════════════════════════════════════════
    # 6. 通知管理
    # ═══════════════════════════════════════════════════════

    @_tool(
        "get_notification_config",
        "获取通知渠道配置。返回当前通知策略：渠道（dashboard/websocket/email/webhook）和严重级别路由。",
        {},
    )
    async def get_notification_config_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        return _to_text_response(await agent.get_notification_config())

    @_tool(
        "manage_notifications",
        "管理通知配置（修改需要用户确认）。可启用/禁用通知渠道，配置严重级别路由，设置免打扰时段。",
        {
            "action": {"type": "string", "description": "操作类型: get | set"},
            "config": {"type": "object", "description": "通知配置（set 时需要）"},
        },
    )
    async def manage_notifications_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        return _to_text_response(await agent.manage_notifications(
            action=args["action"],
            config=args.get("config"),
        ))

    # ═══════════════════════════════════════════════════════
    # 7. 定时任务管理
    # ═══════════════════════════════════════════════════════

    @_tool(
        "query_scheduler",
        "查询所有定时任务状态。返回调度器运行状态和所有已注册任务列表（含下次执行时间）。",
        {},
    )
    async def query_scheduler_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        return _to_text_response(await agent.query_scheduler())

    @_tool(
        "query_available_tasks",
        "查询可调度的任务模板列表。返回所有可以设置为定时任务的系统任务模板。",
        {},
    )
    async def query_available_tasks_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        return _to_text_response(await agent.query_available_tasks())

    @_tool(
        "schedule_job",
        "创建定时任务（需要用户确认）。支持 interval（间隔）和 cron（表达式）两种触发器模式。",
        {
            "task": {"type": "string", "description": "任务名称（用 query_available_tasks 查看可用列表）"},
            "trigger_type": {"type": "string", "description": "触发器类型: interval | cron"},
            "trigger_args": {"type": "object", "description": "触发器参数，如 {\"minutes\": 30} 或 {\"hour\": 9, \"minute\": 0}"},
            "job_id": {"type": "string", "description": "自定义任务ID（可选）"},
        },
    )
    async def schedule_job_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        return _to_text_response(await agent.schedule_job(
            task=args["task"],
            trigger_type=args.get("trigger_type", "interval"),
            trigger_args=args.get("trigger_args", {}),
            job_id=args.get("job_id"),
        ))

    @_tool(
        "modify_scheduler",
        "修改定时任务触发器配置（需要用户确认）。可修改触发器类型和参数。",
        {
            "job_id": {"type": "string", "description": "要修改的任务ID"},
            "trigger_type": {"type": "string", "description": "新触发器类型: interval | cron（可选）"},
            "trigger_args": {"type": "object", "description": "新触发器参数（可选）"},
        },
    )
    async def modify_scheduler_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        return _to_text_response(await agent.modify_scheduler(
            job_id=args["job_id"],
            trigger_type=args.get("trigger_type"),
            trigger_args=args.get("trigger_args"),
        ))

    @_tool(
        "remove_schedule",
        "删除定时任务（需要用户确认）。从调度器中移除指定任务。",
        {"job_id": {"type": "string", "description": "要删除的任务ID"}},
    )
    async def remove_schedule_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        return _to_text_response(await agent.remove_schedule(args["job_id"]))

    @_tool(
        "pause_schedule",
        "暂停定时任务（需要用户确认）。暂停后任务不会自动触发，可随时恢复。",
        {"job_id": {"type": "string", "description": "要暂停的任务ID"}},
    )
    async def pause_schedule_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        return _to_text_response(await agent.pause_schedule(args["job_id"]))

    @_tool(
        "resume_schedule",
        "恢复已暂停的定时任务（需要用户确认）。任务将按原触发器配置继续执行。",
        {"job_id": {"type": "string", "description": "要恢复的任务ID"}},
    )
    async def resume_schedule_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        return _to_text_response(await agent.resume_schedule(args["job_id"]))

    @_tool(
        "trigger_schedule",
        "立即触发定时任务（需要用户确认）。手动触发指定任务立即执行一次，不影响原有调度计划。",
        {"job_id": {"type": "string", "description": "要立即触发的任务ID"}},
    )
    async def trigger_schedule_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        return _to_text_response(await agent.trigger_schedule(args["job_id"]))

    # ═══════════════════════════════════════════════════════
    # 8. CLI命令执行
    # ═══════════════════════════════════════════════════════

    @_tool(
        "execute_cli_command",
        "执行 Astra 系统 CLI 命令（需要用户确认）。支持: astra status / astra events / astra workers / astra debug / astra products / astra scheduler / astra schedule。",
        {
            "command": {"type": "string", "description": "CLI命令，如 astra status、astra events"},
            "args": {"type": "object", "description": "命令参数（可选），如 {\"event_type\": \"compliance_check_requested\"}"},
        },
    )
    async def execute_cli_command_tool(args: dict) -> dict:
        from app.core.qa_agent import get_qa_agent
        agent = get_qa_agent()
        result = await agent.execute_cli_command(
            command=args["command"],
            args=args.get("args", {}),
        )
        return _to_text_response({
            "success": result.success,
            "output": result.output,
            "error": result.error,
        })

    # ── 注册所有工具 ──
    _QA_TOOLS = [
        # 配置
        read_config_tool, write_config_tool,
        # 事件
        list_events_tool, register_event_tool, modify_event_tool, delete_event_tool,
        # Worker
        list_workers_tool, register_worker_tool, modify_worker_tool, delete_worker_tool,
        # 诊断
        health_check_tool, debug_pipeline_tool,
        # 规则
        get_rules_tool, manage_rules_tool,
        # 通知
        get_notification_config_tool, manage_notifications_tool,
        # 调度
        query_scheduler_tool, query_available_tasks_tool,
        schedule_job_tool, modify_scheduler_tool, remove_schedule_tool,
        pause_schedule_tool, resume_schedule_tool, trigger_schedule_tool,
        # CLI
        execute_cli_command_tool,
    ]
    return _QA_TOOLS


# ── MCP Server 工厂 ──────────────────────────────

_qa_server = None


def get_qa_mcp_server():
    """获取 QAAgent MCP Server 配置（单例）。"""
    global _qa_server
    if _qa_server is not None:
        return _qa_server
    _lazy_import()
    if _create_server is None:
        raise ImportError("claude-agent-sdk 未安装")
    tools = _register_tools()
    _qa_server = _create_server(
        name="qa_agent",
        version="1.0.0",
        tools=tools,
    )
    return _qa_server


def get_qa_tools_raw() -> list:
    """直接获取 QAAgent 工具列表（无需 MCP Server）。"""
    return _register_tools()
