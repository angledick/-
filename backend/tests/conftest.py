"""
conftest.py — 全局测试fixture配置
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client():
    """创建异步HTTP测试客户端（ASGI直连，无需启动服务器）"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
