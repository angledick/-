"""
Integrations + OAuth API（Phase 3.5）

/api/v1/integrations — 第三方系统连接管理
/api/v1/oauth — 前端兼容OAuth别名
/api/v1/channels — 频道适配器管理
/api/v1/sync — 自动拉取引擎
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

# ── Integrations Router ─────────────────────────

integrations_router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


class CreateConnectionRequest(BaseModel):
    provider: str
    label: str = ""
    config: Dict[str, Any] = {}


class UpdateConfigRequest(BaseModel):
    config: Dict[str, Any] = {}


@integrations_router.get("", summary="连接列表与状态")
async def list_connections(provider: str = None):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    return {"connections": oauth.list_connections(provider=provider)}


@integrations_router.post("", summary="创建连接")
async def create_connection(req: CreateConnectionRequest):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    try:
        return oauth.create_connection(req.provider, req.label, req.config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@integrations_router.get("/providers", summary="Provider模板列表")
async def list_providers():
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    return {"providers": oauth.get_provider_templates()}


@integrations_router.get("/status", summary="各Provider连接状态汇总")
async def status_summary():
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    return {"status": oauth.get_status_summary()}


@integrations_router.post("/{provider}/auth", summary="OAuth授权")
async def start_auth(provider: str, connection_id: str = ""):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    if connection_id:
        url = oauth.get_auth_url(connection_id)
        if url:
            return {"auth_url": url, "connection_id": connection_id}
    # 如果没有connection_id，先创建一个
    conn = oauth.create_connection(provider, label=f"{provider.title()} Auto")
    cid = conn["id"]
    url = oauth.get_auth_url(cid)
    return {"auth_url": url, "connection_id": cid}


@integrations_router.get("/{provider}/callback", summary="OAuth回调")
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


@integrations_router.get("/{conn_id}/status", summary="连接健康状态")
async def connection_status(conn_id: str):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    conn = oauth.get_connection(conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return conn


@integrations_router.post("/{conn_id}/sync", summary="手动触发同步")
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


@integrations_router.put("/{conn_id}/config", summary="更新连接配置")
async def update_connection_config(conn_id: str, req: UpdateConfigRequest):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    result = oauth.update_config(conn_id, req.config)
    if not result:
        raise HTTPException(status_code=404, detail="Connection not found")
    return result


@integrations_router.delete("/{conn_id}", summary="断开连接")
async def delete_connection(conn_id: str):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    if oauth.delete_connection(conn_id):
        return {"status": "disconnected", "connection_id": conn_id}
    raise HTTPException(status_code=404, detail="Connection not found")


@integrations_router.post("/{conn_id}/test", summary="测试连接有效性")
async def test_connection(conn_id: str):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    return await oauth.test_connection(conn_id)


# ── OAuth兼容别名路由 ──────────────────────────

oauth_router = APIRouter(prefix="/api/v1/oauth", tags=["oauth"])


@oauth_router.get("/providers", summary="OAuth应用列表")
async def oauth_providers():
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    return {"providers": oauth.get_provider_templates()}


@oauth_router.post("/{conn_id}/test", summary="测试OAuth连接")
async def oauth_test(conn_id: str):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    return await oauth.test_connection(conn_id)


@oauth_router.get("/status", summary="各Provider连接状态")
async def oauth_status():
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    return {"status": oauth.get_status_summary()}


# ── Channels Router ──────────────────────────────

channels_router = APIRouter(prefix="/api/v1/channels", tags=["channels"])


class RegisterChannelRequest(BaseModel):
    name: str
    channel_type: str  # feishu / dingtalk / slack / email / webhook
    config: Dict[str, Any] = {}


class SendNotificationRequest(BaseModel):
    channel: str
    target: str
    notification: Dict[str, Any] = {}


class BroadcastRequest(BaseModel):
    content: str
    channels: List[str] = []


@channels_router.get("", summary="频道列表")
async def list_channels():
    from app.core.channel_adapter import get_channel_registry
    registry = get_channel_registry()
    return {"channels": registry.list_channels()}


@channels_router.post("", summary="注册频道")
async def register_channel(req: RegisterChannelRequest):
    from app.core.channel_adapter import get_channel_registry
    registry = get_channel_registry()
    return registry.register(req.name, req.channel_type, req.config)


@channels_router.delete("/{name}", summary="注销频道")
async def unregister_channel(name: str):
    from app.core.channel_adapter import get_channel_registry
    registry = get_channel_registry()
    if registry.unregister(name):
        return {"status": "unregistered", "name": name}
    raise HTTPException(status_code=404, detail="Channel not found")


@channels_router.post("/send", summary="发送通知")
async def send_notification(req: SendNotificationRequest):
    from app.core.channel_adapter import get_channel_registry
    registry = get_channel_registry()
    result = await registry.send_notification(req.channel, req.target, req.notification)
    if not result:
        raise HTTPException(status_code=404, detail="Channel not found")
    return result


@channels_router.post("/broadcast", summary="广播消息")
async def broadcast_message(req: BroadcastRequest):
    from app.core.channel_adapter import get_channel_registry
    registry = get_channel_registry()
    results = await registry.broadcast(req.content, req.channels or None)
    return {"results": results}


# ── Sync Router ──────────────────────────────────

sync_router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


@sync_router.get("/status", summary="同步引擎状态")
async def sync_status():
    from app.core.auto_pull_engine import get_auto_pull_engine
    engine = get_auto_pull_engine()
    return engine.get_status()


@sync_router.post("/run", summary="手动触发同步")
async def run_sync(provider: str, sync_type: str, connection_id: str = ""):
    from app.core.auto_pull_engine import get_auto_pull_engine
    engine = get_auto_pull_engine()
    return await engine.manual_sync(provider, sync_type, connection_id)


@sync_router.get("/jobs", summary="同步任务列表")
async def list_sync_jobs(provider: str = None, status: str = None, limit: int = 50):
    from app.core.auto_pull_engine import get_auto_pull_engine
    engine = get_auto_pull_engine()
    return {"jobs": engine.get_jobs(provider=provider, status=status, limit=limit)}


@sync_router.get("/logs", summary="同步日志")
async def sync_logs(job_id: str = None, limit: int = 100):
    from app.core.auto_pull_engine import get_auto_pull_engine
    engine = get_auto_pull_engine()
    return {"logs": engine.get_logs(job_id=job_id, limit=limit)}


@sync_router.post("/tracking", summary="注册物流追踪号")
async def register_tracking(tracking_numbers: List[Dict[str, Any]]):
    from app.core.auto_pull_engine import get_auto_pull_engine
    engine = get_auto_pull_engine()
    return engine.register_tracking_numbers(tracking_numbers)
