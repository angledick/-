"""
Integrations API — 第三方系统连接管理。

端点:
  GET    /api/v1/integrations              — 连接列表与状态
  POST   /api/v1/integrations              — 创建连接
  GET    /api/v1/integrations/providers    — Provider 模板列表
  GET    /api/v1/integrations/status       — 各 Provider 连接状态汇总
  POST   /api/v1/integrations/{provider}/auth — OAuth 授权
  GET    /api/v1/integrations/{provider}/callback — OAuth 回调
  GET    /api/v1/integrations/{conn_id}/status   — 连接健康状态
  POST   /api/v1/integrations/{conn_id}/sync    — 手动触发同步
  PUT    /api/v1/integrations/{conn_id}/config  — 更新连接配置
  DELETE /api/v1/integrations/{conn_id}         — 断开连接
  POST   /api/v1/integrations/{conn_id}/test    — 测试连接有效性
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Any, Dict, Optional

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


class CreateConnectionRequest(BaseModel):
    provider: str
    label: str = ""
    config: Dict[str, Any] = {}


class UpdateConfigRequest(BaseModel):
    config: Dict[str, Any] = {}


@router.get("", summary="连接列表与状态")
async def list_connections(provider: str = None):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    return {"connections": oauth.list_connections(provider=provider)}


@router.post("", summary="创建连接")
async def create_connection(req: CreateConnectionRequest):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    try:
        return oauth.create_connection(req.provider, req.label, req.config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/providers", summary="Provider模板列表")
async def list_providers():
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    return {"providers": oauth.get_provider_templates()}


@router.get("/status", summary="各Provider连接状态汇总")
async def status_summary():
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    return {"status": oauth.get_status_summary()}


@router.post("/{provider}/auth", summary="OAuth授权")
async def start_auth(provider: str, connection_id: str = ""):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    if connection_id:
        url = oauth.get_auth_url(connection_id)
        if url:
            return {"auth_url": url, "connection_id": connection_id}
    conn = oauth.create_connection(provider, label=f"{provider.title()} Auto")
    cid = conn["id"]
    url = oauth.get_auth_url(cid)
    return {"auth_url": url, "connection_id": cid}


@router.get("/{provider}/callback", summary="OAuth回调")
async def oauth_callback(provider: str, connection_id: str, code: str = "",
                         state: str = "", request: Request = None):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    params = dict(request.query_params) if request else {"code": code, "state": state}
    try:
        result = await oauth.handle_callback(connection_id, params)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{conn_id}/status", summary="连接健康状态")
async def connection_status(conn_id: str):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    conn = oauth.get_connection(conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return conn


@router.post("/{conn_id}/sync", summary="手动触发同步")
async def manual_sync(conn_id: str):
    from app.core.oauth_manager import get_oauth_manager
    from app.core.auto_pull_engine import get_auto_pull_engine
    oauth = get_oauth_manager()
    conn = oauth.get_connection(conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    engine = get_auto_pull_engine()
    result = await engine.manual_sync(conn["provider"], "products", conn_id)
    return result


@router.put("/{conn_id}/config", summary="更新连接配置")
async def update_connection_config(conn_id: str, req: UpdateConfigRequest):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    result = oauth.update_config(conn_id, req.config)
    if not result:
        raise HTTPException(status_code=404, detail="Connection not found")
    return result


@router.delete("/{conn_id}", summary="断开连接")
async def delete_connection(conn_id: str):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    if oauth.delete_connection(conn_id):
        return {"status": "disconnected", "connection_id": conn_id}
    raise HTTPException(status_code=404, detail="Connection not found")


@router.post("/{conn_id}/test", summary="测试连接有效性")
async def test_connection(conn_id: str):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    return await oauth.test_connection(conn_id)
