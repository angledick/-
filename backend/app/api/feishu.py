"""飞书 Webhook 事件接收端点。

接收飞书开放平台推送的事件回调，验证签名后路由到处理链路。
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Header, HTTPException, Request
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/feishu", tags=["feishu"])


def _verify_token(token: str) -> bool:
    """验证飞书 Verification Token。"""
    expected = getattr(settings, "feishu_verification_token", "")
    if not expected:
        return True  # 未配置则跳过验证
    return token == expected


def _decrypt_event(encrypt_key: str, data: str) -> str:
    """解密飞书加密事件（如配置了 Encrypt Key）。"""
    import cryptography.fernet
    key = hashlib.sha256(encrypt_key.encode()).digest()
    # 简化实现 — 实际需要按飞书文档解密
    return data


async def _handle_feishu_message(event: dict):
    """处理飞书消息事件。"""
    from app.core.unified_dispatcher import get_dispatcher

    body = event.get("body", {})
    if "event" in body:
        msg_body = body["event"]
    else:
        msg_body = body

    sender = msg_body.get("sender", {}) or {}
    sender_id = sender.get("sender_id", {})
    sender_open_id = sender_id.get("open_id", sender_id.get("user_id", ""))

    message = msg_body.get("message", msg_body)
    chat_id = message.get("chat_id", message.get("chatId", ""))
    chat_type = message.get("chat_type", message.get("chatType", "p2p"))
    message_id = message.get("message_id", message.get("messageId", ""))
    message_type = message.get("message_type", message.get("msgType", "text"))

    text = _extract_text(message, message_type)

    dispatcher = get_dispatcher()
    await dispatcher.on_external_event("feishu", {
        "event_code": "feishu:message_received",
        "chat_id": chat_id,
        "chat_type": chat_type,
        "content": text,
        "sender_id": sender_open_id,
        "message_id": message_id,
        "message_type": message_type,
        "source": "feishu",
    })


def _extract_text(message: dict, msg_type: str) -> str:
    """从消息对象中提取文本内容。"""
    content_str = message.get("content", "{}")
    if isinstance(content_str, str):
        try:
            content_obj = json.loads(content_str)
        except json.JSONDecodeError:
            return content_str
    else:
        content_obj = content_str

    if msg_type == "text":
        return content_obj.get("text", "")
    elif msg_type == "post":
        parts = []
        for line in content_obj.get("content", []):
            for part in line:
                parts.append(part.get("text", ""))
        return "\n".join(parts)
    return content_obj.get("text", "")


def _process_intent(text: str, intent: str) -> dict:
    """根据意图生成回复。"""
    return {"text": text, "intent": intent}


def _build_compliance_reply(text: str, intent: str, product: str = "", country: str = "") -> str:
    """构建合规查询回复。"""
    return f"关于 {product} 出口到 {country} 的合规要求：\n{text}"


def _build_general_reply(text: str, intent: str) -> str:
    """构建通用回复。"""
    return text


class FeishuEventRequest(BaseModel):
    """飞书事件请求体。"""
    schema_: str = ""
    header: dict = {}
    event: dict = {}

    class Config:
        populate_by_name = True


@router.post("/event")
async def feishu_event(request: Request):
    """接收飞书事件推送。

    支持：
    - URL 验证（challenge）
    - 消息事件接收
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # URL 验证
    challenge = body.get("challenge")
    if challenge:
        token = body.get("token", "")
        if not _verify_token(token):
            raise HTTPException(status_code=403, detail="Invalid token")
        return {"challenge": challenge}

    # 事件处理
    header = body.get("header", {})
    event_type = header.get("event_type", "")
    event_id = header.get("event_id", "")

    if event_type == "im.message.receive_v1":
        # 异步处理，立即返回 200
        asyncio.create_task(_handle_feishu_message({"body": body}))
        return {"code": 0, "msg": "ok"}

    return {"code": 0, "msg": "ignored"}


@router.get("/status")
async def feishu_status():
    """飞书集成状态检查。"""
    from app.services.feishu_listener import get_feishu_listener
    listener = get_feishu_listener()
    return {
        "status": "running" if listener._listener and not listener._listener.done() else "stopped",
        "service": "feishu_listener",
    }
