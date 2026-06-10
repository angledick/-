"""Sessions API — 会话历史管理（需要登录）。

端点:
  GET    /api/v1/sessions         → list[SessionSummary]（user 只看自己的，admin 看全部）
  GET    /api/v1/sessions/{id}    → Session（含全部消息）
  DELETE /api/v1/sessions/{id}    → {"ok": true}
"""

from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user
from app.models.schemas import Session, SessionSummary, SessionMessage, ComplianceResult
from app.storage import session_store

router = APIRouter(prefix="/api/v1", tags=["sessions"])


@router.get(
    "/sessions",
    response_model=list[SessionSummary],
    summary="获取会话列表",
    description="user 只返回自己的会话，admin 返回全部（最近 50 条）。",
)
async def list_sessions(current_user: dict = Depends(get_current_user)):
    user_id = None if current_user["role"] == "admin" else current_user["id"]
    rows = session_store.list_sessions(limit=50, user_id=user_id)
    return [SessionSummary(**r) for r in rows]


@router.get(
    "/sessions/{session_id}",
    response_model=Session,
    summary="获取单个会话",
    description="返回会话基本信息 + 全部消息（含合规结果）。",
)
async def get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    data = session_store.get_session(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 非 admin 只能查看自己的会话
    if current_user["role"] != "admin" and data.get("user_id") != current_user["id"]:
        raise HTTPException(status_code=403, detail="无权限查看此会话")

    messages = []
    for m in data["messages"]:
        cr = m.get("compliance_result")
        messages.append(SessionMessage(
            id=m["id"],
            role=m["role"],
            content=m["content"],
            compliance_result=ComplianceResult(**cr) if cr else None,
            intent=m.get("intent"),
            sources=m.get("sources") or [],
            created_at=m["created_at"],
        ))

    return Session(
        id=data["id"],
        title=data["title"],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        messages=messages,
    )


@router.delete(
    "/sessions/{session_id}",
    summary="删除会话",
    description="删除指定会话及其全部消息。",
)
async def delete_session(session_id: str, current_user: dict = Depends(get_current_user)):
    data = session_store.get_session(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="会话不存在")
    if current_user["role"] != "admin" and data.get("user_id") != current_user["id"]:
        raise HTTPException(status_code=403, detail="无权限删除此会话")
    session_store.delete_session(session_id)

    # 发布会话删除事件
    try:
        from app.core.event_bus import get_event_bus
        await get_event_bus().publish_raw({
            "type": "session:deleted",
            "source": "sessions_api",
            "data": {"session_id": session_id, "user_id": data.get("user_id")},
        })
    except Exception:
        pass

    return {"ok": True}
