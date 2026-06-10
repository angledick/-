"""
后台配置 API — 集成配置、功能开关、健康检查、通知规则。

端点:
  GET  /api/v1/config/integrations           — 集成配置状态
  PUT  /api/v1/config/integrations/{provider} — 更新集成配置
  GET  /api/v1/config/features               — 功能开关列表
  PUT  /api/v1/config/features/{key}         — 功能开关切换
  GET  /api/v1/config/health                 — 健康检查
  GET  /api/v1/config/notifications          — 通知规则配置
  POST /api/v1/config/notifications          — 添加通知规则
  PUT  /api/v1/config/notifications/{id}     — 更新通知规则
  DELETE /api/v1/config/notifications/{id}   — 删除通知规则
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
import json
from pathlib import Path
import logging

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/config", tags=["config-ext"])


@router.get("/integrations", summary="集成配置状态")
async def config_integrations():
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    return {"integrations": oauth.get_status_summary()}


@router.put("/integrations/{provider}", summary="更新集成配置")
async def config_update_integration(provider: str, config: Dict[str, Any]):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    conns = oauth.list_connections(provider=provider)
    if not conns:
        raise HTTPException(status_code=404, detail=f"No {provider} connections found")
    conn_id = conns[0]["id"]
    result = oauth.update_config(conn_id, config)
    return result


@router.get("/features", summary="功能开关列表")
async def config_features():
    features_file = Path(settings.data_dir) / "config" / "features.json"
    if not features_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"功能开关配置不存在: {features_file}"
        )
    with open(features_file, "r", encoding="utf-8") as f:
        return {"features": json.load(f)}


@router.put("/features/{key}", summary="功能开关切换")
async def config_toggle_feature(key: str, enabled: bool):
    features_file = Path(settings.data_dir) / "config" / "features.json"
    if not features_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"功能开关配置不存在: {features_file}"
        )
    with open(features_file, "r", encoding="utf-8") as f:
        features = json.load(f)
    features[key] = enabled
    features_file.parent.mkdir(parents=True, exist_ok=True)
    with open(features_file, "w", encoding="utf-8") as f:
        json.dump(features, f, ensure_ascii=False, indent=2)
    return {"feature": key, "enabled": enabled}


@router.get("/health", summary="健康检查")
async def config_health():
    """系统健康详细检查"""
    health = {"status": "ok", "components": {}}
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


@router.get("/notifications", summary="通知规则配置")
async def config_notifications():
    nf = Path(settings.data_dir) / "notifications" / "rules.json"
    if nf.exists():
        with open(nf, "r", encoding="utf-8") as f:
            return {"rules": json.load(f)}
    return {"rules": []}


class NotificationRule(BaseModel):
    """通知规则模型"""
    id: Optional[str] = None
    event_code: str = ""
    channel: str = "dashboard"
    severity: str = "low"
    condition: str = ""
    enabled: bool = True
    description: str = ""


@router.post("/notifications", summary="添加通知规则")
async def config_add_notification(rule: NotificationRule):
    nf = Path(settings.data_dir) / "notifications" / "rules.json"
    rules = []
    if nf.exists():
        with open(nf, "r", encoding="utf-8") as f:
            rules = json.load(f)
    data = rule.model_dump()
    if not data.get("id"):
        import uuid
        data["id"] = f"rule_{uuid.uuid4().hex[:8]}"
    rules.append(data)
    nf.parent.mkdir(parents=True, exist_ok=True)
    with open(nf, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)
    return data


@router.put("/notifications/{rule_id}", summary="更新通知规则")
async def config_update_notification(rule_id: str, rule: NotificationRule):
    nf = Path(settings.data_dir) / "notifications" / "rules.json"
    if not nf.exists():
        raise HTTPException(status_code=404, detail="Rule not found")
    with open(nf, "r", encoding="utf-8") as f:
        rules = json.load(f)
    for i, r in enumerate(rules):
        if r.get("id") == rule_id:
            data = rule.model_dump()
            data["id"] = rule_id
            rules[i] = data
            with open(nf, "w", encoding="utf-8") as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)
            return data
    raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")


@router.delete("/notifications/{rule_id}", summary="删除通知规则")
async def config_delete_notification(rule_id: str):
    nf = Path(settings.data_dir) / "notifications" / "rules.json"
    if not nf.exists():
        raise HTTPException(status_code=404, detail="Rule not found")
    with open(nf, "r", encoding="utf-8") as f:
        rules = json.load(f)
    original = len(rules)
    rules = [r for r in rules if r.get("id") != rule_id]
    if len(rules) == original:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    with open(nf, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)
    return {"deleted": rule_id}
