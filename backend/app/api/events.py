"""事件管理API — /api/v1/events"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any

from app.models.schemas import EventRecord, EventCategory, EventCreateOSRequest, EventSubscriptionRequest
from app.core.event_bus import get_event_bus, get_event_registry

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("")
async def list_events(
    limit: int = Query(50, ge=1, le=500),
    category: Optional[str] = None,
    product_id: Optional[str] = None,
    severity: Optional[str] = None,
):
    """获取最近的全局事件"""
    bus = get_event_bus()
    cat = EventCategory(category) if category else None
    events = bus.get_recent_events(limit=limit, category=cat, product_id=product_id, severity=severity)
    return {"events": [e.model_dump() for e in events], "total": len(events)}


@router.post("")
async def publish_event(request: EventCreateOSRequest):
    """发布事件到全局总线"""
    bus = get_event_bus()
    event = await bus.publish_raw({
        "type": request.type,
        "source": request.source,
        "category": request.category.value if request.category else None,
        "product_id": request.product_id,
        "business_stage": request.business_stage,
        "data": request.data,
        "severity": request.severity,
    })
    return event


@router.get("/timeline")
async def get_event_timeline(limit: int = Query(20, ge=1, le=100)):
    """获取事件时间线"""
    bus = get_event_bus()
    return {"timeline": bus.get_event_timeline(limit=limit)}


@router.get("/stats")
async def get_event_stats():
    """获取事件统计"""
    bus = get_event_bus()
    return bus.get_event_stats()


@router.get("/registry")
async def list_event_definitions(stage: Optional[str] = None, category: Optional[str] = None):
    """列出事件定义"""
    registry = get_event_registry()
    if stage:
        events = registry.get_events_by_stage(stage)
    elif category:
        events = registry.get_events_by_category(EventCategory(category))
    else:
        events = registry.get_all_events()
    return {"events": [e.model_dump() for e in events], "total": len(events)}


@router.get("/registry/{event_code}")
async def get_event_definition(event_code: str):
    """获取事件定义"""
    registry = get_event_registry()
    event = registry.get_event(event_code)
    if not event:
        raise HTTPException(status_code=404, detail=f"事件 {event_code} 未定义")
    return event


# ── 订阅管理 ──────────────────────────────────

@router.post("/subscribe")
async def create_subscription(request: EventSubscriptionRequest):
    """创建事件订阅"""
    bus = get_event_bus()
    sub_id = await bus.subscribe(
        subscriber=request.subscriber,
        subscription_type=request.subscription_type,
        filter_config=request.filter,
        channels=request.channels,
    )
    return {"subscription_id": sub_id}


@router.delete("/subscribe/{sub_id}")
async def remove_subscription(sub_id: str):
    """取消事件订阅"""
    bus = get_event_bus()
    success = await bus.unsubscribe(sub_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"订阅 {sub_id} 不存在")
    return {"success": True}


@router.get("/subscriptions")
async def list_subscriptions():
    """列出所有订阅"""
    bus = get_event_bus()
    return {"subscriptions": bus.get_subscriptions()}
