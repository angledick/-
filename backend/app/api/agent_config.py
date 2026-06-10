"""
Agent 执行 API — 以指定 Agent 身份通过 Claude SDK 对话。

端点:
  POST /agents/{agent_id}/chat         — 以 Agent 身份对话
  POST /agents/{agent_id}/chat/stream  — 以 Agent 身份流式对话
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.auth import get_current_user
from app.services.astra_assistant import AstraAssistant, check_sdk

router = APIRouter(prefix="/api/v1", tags=["agent-exec"])


class AgentChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


@router.post("/agents/{agent_id}/chat", summary="以 Agent 身份对话")
async def agent_chat(agent_id: str, body: AgentChatRequest, _user: dict = Depends(get_current_user)):
    """以指定 Agent 的 system_prompt 驱动 Claude SDK 对话。"""
    if not check_sdk():
        raise HTTPException(status_code=503, detail="claude-agent-sdk 未安装")
    assistant = AstraAssistant()
    try:
        result = await assistant.run_as_agent(
            agent_id=agent_id,
            message=body.message,
            session_id=body.session_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_id}/chat/stream", summary="以 Agent 身份流式对话")
async def agent_chat_stream(agent_id: str, body: AgentChatRequest, _user: dict = Depends(get_current_user)):
    """以指定 Agent 身份进行 SSE 流式对话。"""
    if not check_sdk():
        raise HTTPException(status_code=503, detail="claude-agent-sdk 未安装")

    from fastapi.responses import StreamingResponse
    from app.api.chat_stream import _sse_event

    assistant = AstraAssistant()

    async def event_generator():
        try:
            yield _sse_event("thinking", {"content": f"正在以 Agent 身份分析...", "depth": 1})
            async for event in assistant.run_as_agent_stream(
                agent_id=agent_id,
                message=body.message,
                session_id=body.session_id,
            ):
                if event["type"] == "text":
                    yield _sse_event("token", {"content": event["content"]})
                elif event["type"] == "tool_use":
                    yield _sse_event("skill_start", {
                        "skill": event["tool_name"],
                        "args": event["tool_input"],
                    })
                elif event["type"] == "tool_result":
                    yield _sse_event("skill_end", {
                        "skill": event["tool_name"],
                        "result": event.get("content"),
                        "status": "success",
                    })
                elif event["type"] == "thinking":
                    yield _sse_event("thinking", {"content": event["content"]})
                elif event["type"] == "error":
                    yield _sse_event("error", {"code": "agent_error", "message": event["error"]})
                    return
            yield _sse_event("done", {"finish_reason": "complete"})
        except Exception as e:
            yield _sse_event("error", {"code": "internal_error", "message": str(e)[:200]})
            yield _sse_event("done", {"finish_reason": "error"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
