"""事件配置管理API — /api/v1/event-config"""

from fastapi import APIRouter, HTTPException
from typing import Optional, List

from app.models.schemas import EventDefinition, EventCategory
from app.core.event_bus import get_event_registry
from app.core.qa_agent import get_qa_agent

router = APIRouter(prefix="/api/v1/event-config", tags=["event-config"])


@router.get("")
async def list_event_configs(stage: Optional[str] = None, category: Optional[str] = None):
    """列出所有事件配置"""
    registry = get_event_registry()
    if stage:
        events = registry.get_events_by_stage(stage)
    elif category:
        events = registry.get_events_by_category(EventCategory(category))
    else:
        events = registry.get_all_events()
    return {"events": [e.model_dump() for e in events], "total": len(events)}


@router.get("/{event_code}")
async def get_event_config(event_code: str):
    """获取事件配置"""
    registry = get_event_registry()
    event = registry.get_event(event_code)
    if not event:
        raise HTTPException(status_code=404, detail=f"事件 {event_code} 未定义")
    return event


@router.post("")
async def create_event_config(event_def: EventDefinition):
    """注册新事件类型（QAAgent）"""
    agent = get_qa_agent()
    permission = agent.check_permission("register_event")
    if not permission.allowed:
        raise HTTPException(status_code=403, detail=permission.reason)

    try:
        success = await agent.add_event_type(
            event_code=event_def.event_code,
            event_name=event_def.event_name,
            business_stage=event_def.business_stage,
            trigger_condition=event_def.trigger_condition,
            related_worker=event_def.related_worker,
            severity=event_def.severity,
            notify_strategy=event_def.notify_strategy,
        )
        return {"success": success}
    except ValueError as e:
        if "已存在" in str(e):
            return {"success": True, "note": str(e)}
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{event_code}")
async def update_event_config(event_code: str, updates: dict):
    """修改事件类型（QAAgent）"""
    agent = get_qa_agent()
    permission = agent.check_permission("modify_event")
    if not permission.allowed:
        raise HTTPException(status_code=403, detail=permission.reason)

    try:
        success = await agent.modify_event_type(event_code, **updates)
        return {"success": success}
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{event_code}")
async def delete_event_config(event_code: str):
    """删除事件类型（归档）"""
    agent = get_qa_agent()
    permission = agent.check_permission("delete_event")
    if not permission.allowed:
        raise HTTPException(status_code=403, detail=permission.reason)

    try:
        success = await agent.delete_event_type(event_code)
        if not success:
            raise HTTPException(status_code=404, detail=f"事件 {event_code} 不存在")
        return {"success": True}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
