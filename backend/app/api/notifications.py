"""通知API — /api/v1/notifications"""

from fastapi import APIRouter, Query
from typing import Optional, List

from app.models.schemas import NotificationPayload
from app.core.notification_engine import get_notification_engine

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    product_id: Optional[str] = None,
    is_read: Optional[bool] = None,
    severity: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """获取通知列表"""
    engine = get_notification_engine()
    notifications = engine.get_notifications(
        product_id=product_id, is_read=is_read, severity=severity,
        limit=limit, offset=offset,
    )
    return {"notifications": [n.model_dump() for n in notifications], "total": len(notifications)}


@router.get("/unread-count")
async def get_unread_count(product_id: Optional[str] = None):
    """获取未读通知数"""
    engine = get_notification_engine()
    return {"count": engine.get_unread_count(product_id)}


@router.put("/{notification_id}/read")
async def mark_read(notification_id: str):
    """标记通知为已读"""
    engine = get_notification_engine()
    success = engine.mark_read(notification_id)
    return {"success": success}


@router.put("/read-all")
async def mark_all_read(product_id: Optional[str] = None):
    """标记所有通知为已读"""
    engine = get_notification_engine()
    count = engine.mark_all_read(product_id)
    return {"marked_read": count}
