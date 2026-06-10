"""
Channels API — 频道适配器管理。

端点:
  GET    /api/v1/channels        — 频道列表
  POST   /api/v1/channels        — 注册频道
  PUT    /api/v1/channels/{name} — 更新频道配置
  DELETE /api/v1/channels/{name} — 注销频道
  POST   /api/v1/channels/send   — 发送通知
  POST   /api/v1/channels/broadcast — 广播消息
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List

router = APIRouter(prefix="/api/v1/channels", tags=["channels"])


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


@router.get("", summary="频道列表")
async def list_channels():
    from app.core.channel_adapter import get_channel_registry
    registry = get_channel_registry()
    return {"channels": registry.list_channels()}


@router.post("", summary="注册频道")
async def register_channel(req: RegisterChannelRequest):
    from app.core.channel_adapter import get_channel_registry
    registry = get_channel_registry()
    return registry.register(req.name, req.channel_type, req.config)


@router.delete("/{name}", summary="注销频道")
async def unregister_channel(name: str):
    from app.core.channel_adapter import get_channel_registry
    registry = get_channel_registry()
    if registry.unregister(name):
        return {"status": "unregistered", "name": name}
    raise HTTPException(status_code=404, detail="Channel not found")


class UpdateChannelRequest(BaseModel):
    config: Dict[str, Any]


@router.put("/{name}", summary="更新频道配置")
async def update_channel(name: str, req: UpdateChannelRequest):
    from app.core.channel_adapter import get_channel_registry
    registry = get_channel_registry()
    result = registry.update(name, req.config)
    if result is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return result


@router.post("/send", summary="发送通知")
async def send_notification(req: SendNotificationRequest):
    from app.core.channel_adapter import get_channel_registry
    registry = get_channel_registry()
    result = await registry.send_notification(req.channel, req.target, req.notification)
    if not result:
        raise HTTPException(status_code=404, detail="Channel not found")
    return result


@router.post("/broadcast", summary="广播消息")
async def broadcast_message(req: BroadcastRequest):
    from app.core.channel_adapter import get_channel_registry
    registry = get_channel_registry()
    results = await registry.broadcast(req.content, req.channels or None)
    return {"results": results}
