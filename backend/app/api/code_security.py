"""
Code API + Security API（Phase 3.5）

/api/v1/code — 编码能力端点（LSP/AST/Patch）
/api/v1/security — 安全沙箱端点
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

# ── Code Router ──────────────────────────────────

code_router = APIRouter(prefix="/api/v1/code", tags=["code"])


class LSPRequest(BaseModel):
    file: str
    line: int
    col: int


class ASTSearchRequest(BaseModel):
    pattern: str
    file_pattern: str = "**/*.py"


class PatchRequest(BaseModel):
    patch: str


@code_router.post("/lsp/definition", summary="LSP跳转到定义")
async def lsp_definition(req: LSPRequest):
    from app.core.plugin_manager import get_code_capability
    cc = get_code_capability()
    result = await cc.lsp_jump(req.file, req.line, req.col)
    return result.to_dict()


@code_router.post("/lsp/references", summary="查找引用")
async def lsp_references(req: ASTSearchRequest):
    from app.core.plugin_manager import get_code_capability
    cc = get_code_capability()
    results = await cc.ast_search(req.pattern, req.file_pattern)
    return {"references": results}


@code_router.post("/lsp/hover", summary="悬停提示")
async def lsp_hover(req: LSPRequest):
    from app.core.plugin_manager import get_code_capability
    cc = get_code_capability()
    definition = await cc.lsp_jump(req.file, req.line, req.col)
    return {"symbol": definition.symbol, "doc": definition.doc, "file": definition.file}


@code_router.post("/ast/search", summary="AST模式搜索")
async def ast_search(req: ASTSearchRequest):
    from app.core.plugin_manager import get_code_capability
    cc = get_code_capability()
    results = await cc.ast_search(req.pattern, req.file_pattern)
    return {"nodes": results}


@code_router.post("/patch", summary="应用代码变更")
async def apply_patch(req: PatchRequest):
    from app.core.plugin_manager import get_code_capability
    cc = get_code_capability()
    return await cc.apply_patch(req.patch)


# ── Security Router ──────────────────────────────

security_router = APIRouter(prefix="/api/v1/security", tags=["security"])


class ToolCheckRequest(BaseModel):
    tool_name: str
    command: str = ""
    args: Dict[str, Any] = {}


class FileCheckRequest(BaseModel):
    file_path: str
    operation: str = "read"


class SkillScanRequest(BaseModel):
    content: str
    skill_name: str = ""


class AddRuleRequest(BaseModel):
    name: str
    description: str = ""
    guard_type: str = "tool"
    pattern: str = ""
    threat_level: str = "medium"
    action: str = "block"


@security_router.post("/check/tool", summary="检查工具调用安全性")
async def check_tool(req: ToolCheckRequest):
    from app.core.security_sandbox import get_security_sandbox
    sandbox = get_security_sandbox()
    event = sandbox.check_tool_call(req.tool_name, req.command, req.args)
    return event.to_dict()


@security_router.post("/check/file", summary="检查文件访问安全性")
async def check_file(req: FileCheckRequest):
    from app.core.security_sandbox import get_security_sandbox
    sandbox = get_security_sandbox()
    event = sandbox.check_file_access(req.file_path, req.operation)
    return event.to_dict()


@security_router.post("/scan/skill", summary="技能安全扫描")
async def scan_skill(req: SkillScanRequest):
    from app.core.security_sandbox import get_security_sandbox
    sandbox = get_security_sandbox()
    event = sandbox.scan_skill(req.content, req.skill_name)
    return event.to_dict()


@security_router.get("/events", summary="安全事件日志")
async def security_events(guard_type: str = None, threat_level: str = None, limit: int = 100):
    from app.core.security_sandbox import get_security_sandbox
    sandbox = get_security_sandbox()
    return {"events": sandbox.get_events(guard_type=guard_type, threat_level=threat_level, limit=limit)}


@security_router.get("/stats", summary="安全统计")
async def security_stats():
    from app.core.security_sandbox import get_security_sandbox
    sandbox = get_security_sandbox()
    return sandbox.get_stats()


@security_router.get("/rules", summary="防护规则列表")
async def list_rules():
    from app.core.security_sandbox import get_security_sandbox
    sandbox = get_security_sandbox()
    return {"rules": sandbox.list_rules()}


@security_router.post("/rules", summary="添加防护规则")
async def add_rule(req: AddRuleRequest):
    from app.core.security_sandbox import get_security_sandbox
    sandbox = get_security_sandbox()
    return sandbox.add_rule(req.dict())


@security_router.delete("/rules/{rule_id}", summary="删除防护规则")
async def delete_rule(rule_id: str):
    from app.core.security_sandbox import get_security_sandbox
    sandbox = get_security_sandbox()
    if sandbox.remove_rule(rule_id):
        return {"status": "deleted", "rule_id": rule_id}
    raise HTTPException(status_code=404, detail="Rule not found")
