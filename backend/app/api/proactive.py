"""
主动引擎 API — 系统心跳、跨产品洞察、合规简报、引擎统计。

端点:
  GET /api/v1/proactive/heartbeat   — 系统心跳
  GET /api/v1/proactive/insights    — 跨产品洞察
  GET /api/v1/proactive/brief       — 合规简报
  GET /api/v1/proactive/stats       — 引擎统计
"""

from fastapi import APIRouter, Query

router = APIRouter(tags=["proactive"])


@router.get("/api/v1/proactive/heartbeat", summary="系统心跳")
async def get_heartbeat():
    try:
        from app.core.proactive_engine import get_proactive_engine
        engine = get_proactive_engine()
        hb = engine.get_heartbeat()
        if hb:
            return hb
        result = await engine.heartbeat_check()
        return result.to_dict()
    except Exception as e:
        return {"overall": "unavailable", "error": str(e)}


@router.get("/api/v1/proactive/insights", summary="跨产品洞察")
async def get_insights():
    try:
        from app.core.proactive_engine import get_proactive_engine
        engine = get_proactive_engine()
        return {"insights": engine.get_insights()}
    except Exception as e:
        return {"insights": [], "error": str(e)}


@router.get("/api/v1/proactive/brief", summary="合规简报")
async def get_brief(limit: int = Query(7, ge=1, le=30)):
    try:
        from app.core.proactive_engine import get_proactive_engine
        engine = get_proactive_engine()
        return {"briefs": engine.get_brief_history(limit=limit)}
    except Exception as e:
        return {"briefs": [], "error": str(e)}


@router.get("/api/v1/proactive/stats", summary="引擎统计")
async def get_proactive_stats():
    try:
        from app.core.proactive_engine import get_proactive_engine
        engine = get_proactive_engine()
        return engine.get_stats()
    except Exception as e:
        return {"error": str(e)}
