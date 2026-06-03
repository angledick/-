"""SDK 会话管理 API — 暴露 Claude Agent SDK 的 CLI 级会话操作。

提供 RESTful 接口让前端可以使用 SDK 的完整会话管理功能：
会话列表、信息查看、消息历史、删除、Fork、重命名、打标签等。

对应 Claude Code CLI 命令:
  /sessions list      → GET  /api/v1/sdk/sessions
  /sessions info      → GET  /api/v1/sdk/sessions/{id}
  /sessions messages  → GET  /api/v1/sdk/sessions/{id}/messages
  /sessions delete    → DELETE /api/v1/sdk/sessions/{id}
  /sessions fork      → POST /api/v1/sdk/sessions/{id}/fork
  /sessions rename    → POST /api/v1/sdk/sessions/{id}/rename
  /sessions tag       → POST /api/v1/sdk/sessions/{id}/tag
  /subagents list     → GET  /api/v1/sdk/subagents
  /subagents messages → GET  /api/v1/sdk/subagents/{id}/messages
"""

from fastapi import APIRouter, HTTPException, Query

from app.services.astra_assistant import AstraAssistant, check_sdk

router = APIRouter(prefix="/api/v1", tags=["sdk"])

_assistant = AstraAssistant()


def _require_sdk():
    if not check_sdk():
        raise HTTPException(
            status_code=503,
            detail="claude-agent-sdk 未安装，无法使用会话管理功能。请执行: pip install claude-agent-sdk",
        )


@router.get(
    "/sdk/sessions",
    summary="会话列表",
    description="列出所有 SDK 会话（对应 CLI /sessions list）。返回会话摘要。",
)
async def list_sessions(limit: int = Query(20, description="最大返回数")):
    _require_sdk()
    try:
        return await _assistant.list_sessions(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {e}")


@router.get(
    "/sdk/sessions/{session_id}",
    summary="会话详情",
    description="获取指定会话的详细信息（对应 CLI /sessions info）。",
    responses={404: {"description": "会话不存在"}},
)
async def get_session_info(session_id: str):
    _require_sdk()
    try:
        info = await _assistant.get_session_info(session_id)
        if info is None:
            raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
        return info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话信息失败: {e}")


@router.get(
    "/sdk/sessions/{session_id}/messages",
    summary="会话消息",
    description="获取指定会话的消息历史（对应 CLI /sessions messages）。",
    responses={404: {"description": "会话不存在"}},
)
async def get_session_messages(session_id: str):
    _require_sdk()
    try:
        msgs = await _assistant.get_session_messages(session_id)
        return msgs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话消息失败: {e}")


@router.delete(
    "/sdk/sessions/{session_id}",
    summary="删除会话",
    description="删除指定会话（对应 CLI /sessions delete）。",
    responses={404: {"description": "会话不存在"}},
)
async def delete_session(session_id: str):
    _require_sdk()
    try:
        result = await _assistant.delete_session(session_id)
        return {"status": "deleted", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除会话失败: {e}")


@router.post(
    "/sdk/sessions/{session_id}/fork",
    summary="Fork 会话",
    description="从指定会话 fork 出一个新会话（对应 CLI /sessions fork）。",
)
async def fork_session(session_id: str):
    _require_sdk()
    try:
        result = await _assistant.fork_session(session_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fork 会话失败: {e}")


@router.post(
    "/sdk/sessions/{session_id}/rename",
    summary="重命名会话",
    description="重命名指定会话（对应 CLI /sessions rename）。",
)
async def rename_session(session_id: str, name: str = Query(..., description="新名称")):
    _require_sdk()
    try:
        await _assistant.rename_session(session_id, name)
        return {"status": "renamed", "session_id": session_id, "name": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重命名会话失败: {e}")


@router.post(
    "/sdk/sessions/{session_id}/tag",
    summary="标记会话",
    description="为会话添加标签（对应 CLI /sessions tag）。",
)
async def tag_session(
    session_id: str,
    tags: str = Query(..., description="逗号分隔的标签列表"),
):
    _require_sdk()
    try:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        await _assistant.tag_session(session_id, tag_list)
        return {"status": "tagged", "session_id": session_id, "tags": tag_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"标记会话失败: {e}")


@router.get(
    "/sdk/subagents",
    summary="子代理列表",
    description="列出会话中的子代理（对应 CLI /subagents list）。",
)
async def list_subagents(session_id: str = Query(None, description="按会话筛选")):
    _require_sdk()
    try:
        return await _assistant.list_subagents(session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取子代理列表失败: {e}")


@router.get(
    "/sdk/subagents/{subagent_id}/messages",
    summary="子代理消息",
    description="获取指定子代理的消息（对应 CLI /subagents messages）。",
)
async def get_subagent_messages(subagent_id: str):
    _require_sdk()
    try:
        return await _assistant.get_subagent_messages(subagent_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取子代理消息失败: {e}")
