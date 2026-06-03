"""
操作链 / 事件链 / NLStore 集成测试
===================================
通过 ASGI 直连 HTTP 客户端验证 /api/v1/chains/* 与 /api/v1/nl-store/* 端点。
"""

import pytest


# ══════════════════════════════════════════════════════════
# 操作链测试
# ══════════════════════════════════════════════════════════

class TestActionChains:
    """操作链 CRUD 与状态流转"""

    @pytest.mark.asyncio
    async def test_list_action_chains_empty(self, client):
        """操作链列表默认返回空列表或已有数据"""
        resp = await client.get("/api/v1/chains/actions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_get_nonexistent_action_chain(self, client):
        """获取不存在的操作链应返回404"""
        resp = await client.get("/api/v1/chains/actions/nonexistent_chain_999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_nonexistent_action_trail(self, client):
        """获取不存在操作链的trail应返回404"""
        resp = await client.get("/api/v1/chains/actions/nonexistent_chain_999/trail")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════
# 事件链测试
# ══════════════════════════════════════════════════════════

class TestEventChains:
    """事件链 CRUD 与过滤"""

    @pytest.mark.asyncio
    async def test_list_event_chains(self, client):
        """事件链列表应返回列表"""
        resp = await client.get("/api/v1/chains/events")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_get_nonexistent_event_chain(self, client):
        """获取不存在的事件链应返回404"""
        resp = await client.get("/api/v1/chains/events/nonexistent_event_999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_event_missing_fields(self, client):
        """缺少必填字段创建事件应返回422"""
        resp = await client.post("/api/v1/chains/events", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_event_success(self, client):
        """创建事件链事件"""
        payload = {
            "chain_id": "test_event_chain_001",
            "source": "unit_test",
            "event_type": "regulation_change",
            "description_nl": "测试事件：欧盟更新GPSR法规",
            "severity": "medium",
            "tags": ["测试", "GPSR"]
        }
        resp = await client.post("/api/v1/chains/events", json=payload)
        # 可能是200或201
        assert resp.status_code in (200, 201)

    @pytest.mark.asyncio
    async def test_event_timeline(self, client):
        """事件时间线查询"""
        # 先确认链不存在时404
        resp = await client.get("/api/v1/chains/events/nonexistent_timeline/timeline")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_event_filter(self, client):
        """事件过滤查询"""
        resp = await client.get("/api/v1/chains/events/nonexistent_filter/filter")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════
# NLStore 测试
# ══════════════════════════════════════════════════════════

class TestNLStore:
    """NLStore 自然语言存储 CRUD"""

    @pytest.mark.asyncio
    async def test_list_namespace(self, client):
        """列出命名空间记录"""
        resp = await client.get("/api/v1/nl-store/test_integration_ns")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_get_nonexistent_record(self, client):
        """获取不存在的记录应返回404"""
        resp = await client.get("/api/v1/nl-store/test_integration_ns/no_such_key")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_and_read_record(self, client):
        """创建并读取NLStore记录"""
        payload = {
            "key": "test_record_001",
            "title": "集成测试记录",
            "content_nl": "这是一条通过HTTP接口创建的NLStore集成测试记录",
            "tags": ["test", "integration"]
        }
        # 创建
        resp = await client.post("/api/v1/nl-store/test_integration_ns", json=payload)
        assert resp.status_code in (200, 201)

        # 读取
        resp = await client.get("/api/v1/nl-store/test_integration_ns/test_record_001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "集成测试记录"

    @pytest.mark.asyncio
    async def test_update_record(self, client):
        """更新NLStore记录"""
        # 先创建
        create_payload = {
            "key": "test_update_001",
            "title": "待更新记录",
            "content_nl": "原始内容",
            "tags": ["update-test"]
        }
        await client.post("/api/v1/nl-store/test_integration_ns", json=create_payload)

        # 更新
        update_payload = {
            "title": "已更新记录",
            "content_nl": "更新后的内容",
            "tags": ["update-test", "updated"]
        }
        resp = await client.put("/api/v1/nl-store/test_integration_ns/test_update_001",
                                json=update_payload)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_record(self, client):
        """删除NLStore记录"""
        # 先创建
        create_payload = {
            "key": "test_delete_001",
            "title": "待删除记录",
            "content_nl": "即将删除",
            "tags": ["delete-test"]
        }
        await client.post("/api/v1/nl-store/test_integration_ns", json=create_payload)

        # 删除
        resp = await client.delete("/api/v1/nl-store/test_integration_ns/test_delete_001")
        assert resp.status_code == 200

        # 确认已删除
        resp = await client.get("/api/v1/nl-store/test_integration_ns/test_delete_001")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, client):
        """删除不存在的记录应返回404"""
        resp = await client.delete("/api/v1/nl-store/test_integration_ns/ghost_key_999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_search_missing_query(self, client):
        """搜索缺少q参数应返回422"""
        resp = await client.get("/api/v1/nl-store/search")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_with_query(self, client):
        """搜索功能基本验证"""
        resp = await client.get("/api/v1/nl-store/search", params={"q": "合规"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
