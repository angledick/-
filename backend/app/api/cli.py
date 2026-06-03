"""CLI命令API — /api/v1/cli"""

import json
import time
from typing import Optional

from fastapi import APIRouter, Query

from app.models.schemas import (
    CLICommandRequest,
    CLICommandResult,
    CLICommand,
    CLICompleteResponse,
    CLIHistoryResponse,
    MagicCommandRequest,
)
from app.core.qa_agent import get_qa_agent

router = APIRouter(prefix="/api/v1/cli", tags=["cli"])

# ── 内置命令列表（返回给前端自动补全） ─────────────────

BUILTIN_COMMANDS: list[CLICommand] = [
    CLICommand(cmd="/help",    desc="查看可用命令",       category="系统"),
    CLICommand(cmd="/clear",  desc="清空对话历史",       category="对话"),
    CLICommand(cmd="/status", desc="查看系统状态",       category="系统"),
    CLICommand(cmd="/config", desc="查看当前配置",       category="配置"),
    CLICommand(cmd="/history",desc="查看命令历史",       category="系统"),
    CLICommand(cmd="/agent",  desc="切换当前 Agent",     category="配置", usage="/agent <name>"),
    CLICommand(cmd="/export", desc="导出合规报告",       category="工具", usage="/export <product_id>"),
    CLICommand(cmd="/events", desc="查看事件列表",       category="系统"),
    CLICommand(cmd="/workers",desc="查看 Worker 状态",   category="系统"),
    CLICommand(cmd="/products",desc="查看产品列表",      category="工具"),
    CLICommand(cmd="/retry",  desc="重新执行上一条命令", category="对话"),
]

# ── 命令执行历史（内存存储，重启清零） ─────────────────

_command_history: list[CLICommandResult] = []


def _record_history(result: CLICommandResult) -> None:
    """记录命令执行结果到历史"""
    _command_history.append(result)
    # 最多保留 100 条
    if len(_command_history) > 100:
        _command_history.pop(0)


@router.post("/execute", response_model=CLICommandResult)
async def execute_command(request: CLICommandRequest):
    """执行CLI命令（同时支持 `astra *` 系统命令和 `/` 魔法命令）"""
    cmd = request.command.strip()
    # 如果命令以 / 开头，自动路由到魔法命令处理器
    if cmd.startswith("/"):
        result = await _handle_magic_command(cmd)
        _record_history(CLICommandResult(**result))
        return result
    agent = get_qa_agent()
    result = await agent.execute_cli_command(cmd, request.args)
    _record_history(result)
    return result


@router.post("/magic")
async def execute_magic_command(request: MagicCommandRequest):
    """执行魔法命令"""
    result = await _handle_magic_command(request.command.strip())
    _record_history(CLICommandResult(**result))
    return result


def _is_magic_command(command: str) -> bool:
    """判断是否为魔法命令"""
    return command.startswith("/")


async def _handle_magic_command(command: str) -> dict:
    """处理魔法命令（以 / 开头的命令）"""
    start = time.time()

    if command == "/clear":
        return {"command": command, "success": True, "output": "会话已清除", "duration_ms": 0}
    elif command == "/retry":
        return {"command": command, "success": True, "output": "请重新输入您的问题", "duration_ms": 0}
    elif command == "/history":
        history_lines = [f"  {r.command}  {'✅' if r.success else '❌'}  ({r.duration_ms}ms)" for r in _command_history[-20:]]
        output = "最近命令历史:\n" + "\n".join(history_lines) if history_lines else "暂无命令历史"
        return {"command": command, "success": True, "output": output, "duration_ms": 0}
    elif command == "/help":
        lines = [f"  {c.cmd:<12} {c.desc}" for c in BUILTIN_COMMANDS]
        output = "可用命令:\n" + "\n".join(lines)
        return {"command": command, "success": True, "output": output, "duration_ms": 0}
    elif command == "/status":
        agent = get_qa_agent()
        health = await agent.health_check()
        return {"command": command, "success": True, "output": json.dumps(health, ensure_ascii=False, indent=2), "duration_ms": int((time.time() - start) * 1000)}
    elif command == "/events":
        agent = get_qa_agent()
        r = await agent.execute_cli_command("astra events")
        return {"command": command, "success": r.success, "output": r.output, "duration_ms": r.duration_ms}
    elif command == "/workers":
        agent = get_qa_agent()
        r = await agent.execute_cli_command("astra workers")
        return {"command": command, "success": r.success, "output": r.output, "duration_ms": r.duration_ms}
    elif command == "/products":
        agent = get_qa_agent()
        r = await agent.execute_cli_command("astra products")
        return {"command": command, "success": r.success, "output": r.output, "duration_ms": r.duration_ms}
    else:
        return {"command": command, "success": False, "error": f"未知魔法命令: {command}", "duration_ms": 0}


@router.get("/complete", response_model=CLICompleteResponse)
async def complete_command(prefix: str = Query("", description="命令前缀")):
    """CLI命令自动补全"""
    if not prefix:
        return CLICompleteResponse(suggestions=BUILTIN_COMMANDS, prefix=prefix)
    filtered = [c for c in BUILTIN_COMMANDS if c.cmd.lower().startswith(prefix.lower())]
    return CLICompleteResponse(suggestions=filtered or BUILTIN_COMMANDS, prefix=prefix)


@router.get("/history", response_model=CLIHistoryResponse)
async def get_command_history(limit: Optional[int] = Query(20, description="返回条数")):
    """获取CLI命令执行历史"""
    recent = _command_history[-limit:] if limit else _command_history
    return CLIHistoryResponse(history=list(recent))
