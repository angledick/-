"""
Plugins API（Phase 3.5）

/api/v1/plugins — 插件管理端点
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional

router = APIRouter(prefix="/api/v1/plugins", tags=["plugins"])


class InstallPluginRequest(BaseModel):
    source: str
    source_type: str = "pypi"
    config: Dict[str, Any] = {}


@router.get("", summary="已安装插件列表")
async def list_plugins():
    from app.core.plugin_manager import get_plugin_manager
    pm = get_plugin_manager()
    return {"plugins": pm.list_plugins()}


@router.post("", summary="安装插件")
async def install_plugin(req: InstallPluginRequest):
    from app.core.plugin_manager import get_plugin_manager
    pm = get_plugin_manager()
    try:
        result = await pm.install(req.source, req.source_type, req.config)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/recommended", summary="推荐插件清单")
async def recommended_plugins():
    from app.core.plugin_manager import get_plugin_manager
    pm = get_plugin_manager()
    return {"recommended": pm.get_recommended()}


@router.delete("/{plugin_id}", summary="卸载插件")
async def uninstall_plugin(plugin_id: str):
    from app.core.plugin_manager import get_plugin_manager
    pm = get_plugin_manager()
    if await pm.uninstall(plugin_id):
        return {"status": "uninstalled", "plugin_id": plugin_id}
    raise HTTPException(status_code=404, detail="Plugin not found")


@router.post("/{plugin_id}/audit", summary="安全审查")
async def audit_plugin(plugin_id: str):
    from app.core.plugin_manager import get_plugin_manager
    pm = get_plugin_manager()
    report = await pm.security_audit(plugin_id=plugin_id)
    return report.to_dict()


@router.post("/{plugin_id}/enable", summary="启用插件")
async def enable_plugin(plugin_id: str):
    from app.core.plugin_manager import get_plugin_manager
    pm = get_plugin_manager()
    result = await pm.enable(plugin_id)
    if not result:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return result


@router.post("/{plugin_id}/disable", summary="停用插件")
async def disable_plugin(plugin_id: str):
    from app.core.plugin_manager import get_plugin_manager
    pm = get_plugin_manager()
    result = await pm.disable(plugin_id)
    if not result:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return result
