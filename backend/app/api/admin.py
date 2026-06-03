"""
后台管理 API — RBAC + 审批 + 后台配置 + 合规报表

/api/v1/rbac — RBAC管理
/api/v1/approvals — 审批管理
/api/v1/config/* — 后台配置（integrations/features/health/notifications）
/api/v1/reports — 合规报表
/api/v1/users — 用户管理扩展
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
# RBAC Router
# ═══════════════════════════════════════════════════════

rbac_router = APIRouter(prefix="/api/v1/rbac", tags=["rbac"])


class AssignRoleRequest(BaseModel):
    user_id: str
    username: str
    role: str


@rbac_router.get("/roles", summary="角色定义列表")
async def list_roles():
    from app.core.rbac import get_rbac_manager
    rbac = get_rbac_manager()
    return {"roles": rbac.get_roles()}


@rbac_router.post("/assign", summary="分配角色")
async def assign_role(req: AssignRoleRequest):
    from app.core.rbac import get_rbac_manager
    rbac = get_rbac_manager()
    try:
        return rbac.assign_role(req.user_id, req.username, req.role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@rbac_router.get("/users", summary="用户RBAC列表")
async def list_rbac_users():
    from app.core.rbac import get_rbac_manager
    rbac = get_rbac_manager()
    return {"users": rbac.list_users()}


@rbac_router.get("/users/{user_id}", summary="用户权限详情")
async def get_user_rbac(user_id: str):
    from app.core.rbac import get_rbac_manager
    rbac = get_rbac_manager()
    user = rbac.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@rbac_router.get("/users/{user_id}/permissions", summary="用户权限列表")
async def get_user_permissions(user_id: str):
    from app.core.rbac import get_rbac_manager
    rbac = get_rbac_manager()
    return {"user_id": user_id, "permissions": rbac.get_permissions(user_id)}


@rbac_router.post("/check", summary="权限检查")
async def check_permission(user_id: str, resource: str, action: str):
    from app.core.rbac import get_rbac_manager
    rbac = get_rbac_manager()
    allowed = rbac.check_permission(user_id, resource, action)
    return {"user_id": user_id, "resource": resource, "action": action, "allowed": allowed}


# ═══════════════════════════════════════════════════════
# Approvals Router
# ═══════════════════════════════════════════════════════

approvals_router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


class ApproveRequest(BaseModel):
    approver_id: str
    approver_name: str
    comment: str = ""


class CreateApprovalRequest(BaseModel):
    requester_id: str
    requester_name: str
    resource: str
    action: str
    details: Dict[str, Any] = {}


@approvals_router.get("", summary="审批列表")
async def list_approvals(status: str = None, requester_id: str = None, limit: int = 50):
    from app.core.rbac import get_approval_engine
    engine = get_approval_engine()
    return {"approvals": engine.list_requests(status=status, requester_id=requester_id, limit=limit)}


@approvals_router.post("", summary="创建审批请求")
async def create_approval(req: CreateApprovalRequest):
    from app.core.rbac import get_approval_engine
    engine = get_approval_engine()
    return engine.create_request(req.requester_id, req.requester_name, req.resource, req.action, req.details)


@approvals_router.post("/{approval_id}/approve", summary="审批通过")
async def approve(approval_id: str, req: ApproveRequest):
    from app.core.rbac import get_approval_engine
    engine = get_approval_engine()
    result = engine.approve(approval_id, req.approver_id, req.approver_name, req.comment)
    if not result:
        raise HTTPException(status_code=404, detail="Approval not found or already resolved")
    return result


@approvals_router.post("/{approval_id}/reject", summary="审批驳回")
async def reject(approval_id: str, req: ApproveRequest):
    from app.core.rbac import get_approval_engine
    engine = get_approval_engine()
    result = engine.reject(approval_id, req.approver_id, req.approver_name, req.comment)
    if not result:
        raise HTTPException(status_code=404, detail="Approval not found or already resolved")
    return result


@approvals_router.get("/rules", summary="审批规则")
async def approval_rules():
    from app.core.rbac import get_approval_engine
    engine = get_approval_engine()
    return {"rules": engine.get_rules()}


@approvals_router.get("/stats", summary="审批统计")
async def approval_stats():
    from app.core.rbac import get_approval_engine
    engine = get_approval_engine()
    return engine.get_stats()


# ═══════════════════════════════════════════════════════
# Config Router (扩展后台配置)
# ═══════════════════════════════════════════════════════

config_ext_router = APIRouter(prefix="/api/v1/config", tags=["config-ext"])


@config_ext_router.get("/integrations", summary="集成配置状态")
async def config_integrations():
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    return {"integrations": oauth.get_status_summary()}


@config_ext_router.put("/integrations/{provider}", summary="更新集成配置")
async def config_update_integration(provider: str, config: Dict[str, Any]):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    conns = oauth.list_connections(provider=provider)
    if not conns:
        raise HTTPException(status_code=404, detail=f"No {provider} connections found")
    conn_id = conns[0]["id"]
    result = oauth.update_config(conn_id, config)
    return result


@config_ext_router.get("/features", summary="功能开关列表")
async def config_features():
    import json
    from pathlib import Path
    from app.config import settings
    features_file = Path(settings.data_dir) / "config" / "features.json"
    if features_file.exists():
        try:
            with open(features_file, "r", encoding="utf-8") as f:
                return {"features": json.load(f)}
        except Exception as e:
            logger.warning("Failed to read features.json: %s", e)
    # 默认功能开关
    defaults = {
        "sse_streaming": True,
        "multi_agent": True,
        "memory_tree": True,
        "proactive_engine": True,
        "security_sandbox": True,
        "skill_registry": True,
        "plugin_system": True,
        "code_capability": True,
        "auto_pull": True,
        "channel_adapter": True,
        "rbac": True,
        "approval_flow": True,
    }
    return {"features": defaults}


@config_ext_router.put("/features/{key}", summary="功能开关切换")
async def config_toggle_feature(key: str, enabled: bool):
    import json
    from pathlib import Path
    from app.config import settings
    features_file = Path(settings.data_dir) / "config" / "features.json"
    features = {}
    if features_file.exists():
        try:
            with open(features_file, "r", encoding="utf-8") as f:
                features = json.load(f)
        except Exception as e:
            logger.warning("Failed to read features.json for update: %s", e)
    features[key] = enabled
    features_file.parent.mkdir(parents=True, exist_ok=True)
    with open(features_file, "w", encoding="utf-8") as f:
        json.dump(features, f, ensure_ascii=False, indent=2)
    return {"feature": key, "enabled": enabled}


@config_ext_router.get("/health", summary="健康检查")
async def config_health():
    """系统健康详细检查"""
    health = {
        "status": "ok",
        "components": {},
    }

    # 检查核心组件
    components = {
        "event_bus": "app.core.event_bus",
        "product_storage": "app.core.product_storage",
        "memory_tree": "app.core.memory_tree",
        "manager_agent": "app.core.manager_agent",
        "proactive_engine": "app.core.proactive_engine",
        "oauth_manager": "app.core.oauth_manager",
        "security_sandbox": "app.core.security_sandbox",
        "skill_registry": "app.core.skill_registry",
        "plugin_manager": "app.core.plugin_manager",
        "rbac": "app.core.rbac",
    }

    for name, module in components.items():
        try:
            __import__(module)
            health["components"][name] = "ok"
        except Exception as e:
            health["components"][name] = f"error: {str(e)[:50]}"

    ok_count = sum(1 for v in health["components"].values() if v == "ok")
    total = len(health["components"])
    health["summary"] = f"{ok_count}/{total} components healthy"
    health["status"] = "ok" if ok_count == total else "degraded"

    return health


@config_ext_router.get("/notifications", summary="通知规则配置")
async def config_notifications():
    from pathlib import Path
    import json
    from app.config import settings
    nf = Path(settings.data_dir) / "config" / "notification_rules.json"
    if nf.exists():
        with open(nf, "r", encoding="utf-8") as f:
            return {"rules": json.load(f)}
    return {"rules": []}


@config_ext_router.post("/notifications", summary="添加通知规则")
async def config_add_notification(rule: Dict[str, Any]):
    from pathlib import Path
    import json
    from app.config import settings
    nf = Path(settings.data_dir) / "config" / "notification_rules.json"
    rules = []
    if nf.exists():
        with open(nf, "r", encoding="utf-8") as f:
            rules = json.load(f)
    rules.append(rule)
    nf.parent.mkdir(parents=True, exist_ok=True)
    with open(nf, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)
    return rule


# ═══════════════════════════════════════════════════════
# Reports Router (合规报表)
# ═══════════════════════════════════════════════════════

reports_router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


class ExportRequest(BaseModel):
    format: str = "json"          # json / csv / pdf / excel
    filters: Dict[str, Any] = {}


@reports_router.get("", summary="合规报表列表")
async def list_reports():
    """生成可用报表清单"""
    return {
        "reports": [
            {"id": "compliance_overview", "name": "合规总览报告",
             "description": "所有产品合规状态汇总", "formats": ["json", "csv"]},
            {"id": "certification_status", "name": "认证状态报告",
             "description": "认证到期/有效/过期统计", "formats": ["json", "csv"]},
            {"id": "risk_assessment", "name": "风险评估报告",
             "description": "各风险等级产品分布与趋势", "formats": ["json", "csv"]},
            {"id": "regulation_changes", "name": "法规变更报告",
             "description": "近期法规变更及影响分析", "formats": ["json", "csv"]},
            {"id": "audit_trail", "name": "审计追踪报告",
             "description": "用户操作/审批/系统事件追踪", "formats": ["json", "csv"]},
            {"id": "pipeline_health", "name": "流水线健康报告",
             "description": "10阶段合规流水线健康度", "formats": ["json", "csv"]},
        ],
    }


@reports_router.post("/{report_id}/export", summary="导出报表")
async def export_report(report_id: str, req: ExportRequest):
    """导出指定报表"""
    report_data = await _generate_report(report_id, req.filters)
    if report_data is None:
        raise HTTPException(status_code=404, detail="Report not found")

    if req.format == "json":
        return {"report_id": report_id, "format": "json", "data": report_data}
    elif req.format == "csv":
        # 简化CSV导出
        import csv
        import io
        output = io.StringIO()
        if report_data and isinstance(report_data, list) and len(report_data) > 0:
            writer = csv.DictWriter(output, fieldnames=report_data[0].keys())
            writer.writeheader()
            writer.writerows(report_data)
        return {"report_id": report_id, "format": "csv", "content": output.getvalue()}
    else:
        return {"report_id": report_id, "format": req.format,
                "message": f"Export as {req.format} — data ready for conversion",
                "data": report_data}


async def _generate_report(report_id: str, filters: Dict) -> Any:
    """生成报表数据"""
    if report_id == "compliance_overview":
        try:
            from app.core.product_storage import get_product_storage
            storage = get_product_storage()
            products = storage.list_products()
            return [
                {"product_id": p.id, "name": p.name,
                 "lifecycle_stage": p.lifecycle_stage.value if hasattr(p.lifecycle_stage, 'value') else str(p.lifecycle_stage),
                 "risk_level": p.risk_level}
                for p in products
            ]
        except Exception:
            return [{"message": "Product storage not available"}]

    elif report_id == "certification_status":
        try:
            from app.core.proactive_engine import get_proactive_engine
            engine = get_proactive_engine()
            cert_data = await engine.check_cert_expiry()
            return cert_data.get("results", [])
        except Exception:
            return [{"message": "Certification data not available"}]

    elif report_id == "risk_assessment":
        try:
            from app.core.proactive_engine import get_proactive_engine
            engine = get_proactive_engine()
            metrics = await engine.aggregate_global_metrics()
            return [metrics]
        except Exception:
            return [{"message": "Risk data not available"}]

    elif report_id == "regulation_changes":
        return [{"message": "Regulation changes report", "recent_changes": []}]

    elif report_id == "audit_trail":
        try:
            from app.core.security_sandbox import get_security_sandbox
            sandbox = get_security_sandbox()
            events = sandbox.get_events(limit=100)
            return events
        except Exception:
            return [{"message": "Audit trail not available"}]

    elif report_id == "pipeline_health":
        try:
            from app.core.proactive_engine import get_proactive_engine
            engine = get_proactive_engine()
            metrics = await engine.aggregate_global_metrics()
            return [{"pipeline_health": metrics.get("system_health", "unknown")}]
        except Exception:
            return [{"message": "Pipeline data not available"}]

    return None
