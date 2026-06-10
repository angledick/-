"""
OAuth API — 前端兼容 OAuth 别名路由。

端点:
  GET  /api/v1/oauth/providers      — OAuth 应用列表
  POST /api/v1/oauth/{conn_id}/test — 测试 OAuth 连接
  GET  /api/v1/oauth/status         — 各 Provider 连接状态
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/oauth", tags=["oauth"])


@router.get("/providers", summary="OAuth应用列表")
async def oauth_providers():
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    return {"providers": oauth.get_provider_templates()}


@router.post("/{conn_id}/test", summary="测试OAuth连接")
async def oauth_test(conn_id: str):
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    return await oauth.test_connection(conn_id)


@router.get("/status", summary="各Provider连接状态")
async def oauth_status():
    from app.core.oauth_manager import get_oauth_manager
    oauth = get_oauth_manager()
    return {"status": oauth.get_status_summary()}
