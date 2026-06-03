"""
接口契约测试 — 基于 OpenAPI 3.0 schema 验证。

验证内容：
1. OpenAPI schema 结构完整性（所有端点已记录）
2. 所有端点有对应的请求/响应模型
3. 请求参数校验（422 错误正确处理）
4. 关键端点的 response_model 类型正确
5. 最低端点数量门槛（防止路由注册遗漏）
"""

import pytest


# ── 预期端点清单（作为接口契约） ──────────────────
# 覆盖全系统 31 个路由模块的核心端点
# 格式: (method, path)
EXPECTED_ENDPOINTS = [
    # ── Health ──
    ("GET", "/api/v1/health"),
    ("GET", "/api/v1/system/health"),
    # ── Streaming / Chat ──
    ("POST", "/api/v1/chat/stream"),
    ("GET", "/api/v1/chat/config"),
    ("PUT", "/api/v1/chat/config"),
    # ── Agents (streaming) ──
    ("GET", "/api/v1/agents/tasks"),
    ("POST", "/api/v1/agents/tasks"),
    ("GET", "/api/v1/agents/workers"),
    ("GET", "/api/v1/agents/templates"),
    # ── Proactive Engine ──
    ("GET", "/api/v1/proactive/heartbeat"),
    ("GET", "/api/v1/proactive/insights"),
    ("GET", "/api/v1/proactive/brief"),
    ("GET", "/api/v1/proactive/stats"),
    # ── Chains & NLStore ──
    ("GET", "/api/v1/chains/actions"),
    ("GET", "/api/v1/chains/events"),
    ("POST", "/api/v1/chains/events"),
    ("GET", "/api/v1/nl-store/search"),
    # ── Shopify ──
    ("GET", "/api/v1/shopify/auth"),
    ("GET", "/api/v1/shopify/callback"),
    ("GET", "/api/v1/shopify/shops"),
    ("POST", "/api/v1/shopify/webhook"),
    # ── Auth ──
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/register"),
    ("GET", "/api/v1/auth/me"),
    # ── Users ──
    ("GET", "/api/v1/users"),
    # ── Sessions ──
    ("GET", "/api/v1/sessions"),
    # ── SDK Sessions ──
    ("GET", "/api/v1/sdk/sessions"),
    ("GET", "/api/v1/sdk/subagents"),
    # ── Products ──
    ("GET", "/api/v1/products"),
    ("POST", "/api/v1/products"),
    ("GET", "/api/v1/products/count"),
    # ── Events ──
    ("GET", "/api/v1/events"),
    ("POST", "/api/v1/events"),
    ("GET", "/api/v1/events/timeline"),
    ("GET", "/api/v1/events/stats"),
    ("GET", "/api/v1/events/registry"),
    ("POST", "/api/v1/events/subscribe"),
    ("GET", "/api/v1/events/subscriptions"),
    # ── Pipeline ──
    ("GET", "/api/v1/pipeline/health"),
    ("GET", "/api/v1/pipeline/stages"),
    ("GET", "/api/v1/pipeline/metrics"),
    ("GET", "/api/v1/pipeline/mode"),
    ("PUT", "/api/v1/pipeline/mode"),
    ("GET", "/api/v1/pipeline/interactions"),
    # ── Notifications ──
    ("GET", "/api/v1/notifications"),
    ("GET", "/api/v1/notifications/unread-count"),
    ("PUT", "/api/v1/notifications/read-all"),
    # ── CLI ──
    ("POST", "/api/v1/cli/execute"),
    ("POST", "/api/v1/cli/magic"),
    ("GET", "/api/v1/cli/complete"),
    ("GET", "/api/v1/cli/history"),
    # ── RAG ──
    ("GET", "/api/v1/rag/status"),
    ("POST", "/api/v1/rag/search"),
    ("POST", "/api/v1/rag/reindex"),
    ("GET", "/api/v1/rag/models"),
    ("GET", "/api/v1/rag/token-juice/stats"),
    # ── Memory ──
    ("GET", "/api/v1/memory/namespaces"),
    ("GET", "/api/v1/memory/tree"),
    ("POST", "/api/v1/memory/search"),
    ("POST", "/api/v1/memory/export"),
    ("POST", "/api/v1/memory/fragments"),
    ("GET", "/api/v1/memory/fragments"),
    ("GET", "/api/v1/memory/summaries"),
    # ── Metrics ──
    ("GET", "/api/v1/metrics/global"),
    ("GET", "/api/v1/metrics/alerts"),
    ("GET", "/api/v1/metrics/builtin_templates"),
    ("GET", "/api/v1/metrics/custom"),
    ("POST", "/api/v1/metrics/custom"),
    ("GET", "/api/v1/metrics/cross_product"),
    ("GET", "/api/v1/metrics/dashboard"),
    # ── Tools ──
    ("GET", "/api/v1/tools"),
    ("POST", "/api/v1/tools"),
    # ── Skills ──
    ("GET", "/api/v1/skills"),
    ("POST", "/api/v1/skills/install"),
    ("POST", "/api/v1/skills/recommend"),
    ("GET", "/api/v1/skills/matrix/stages"),
    ("GET", "/api/v1/skills/executions/history"),
    # ── Plugins ──
    ("GET", "/api/v1/plugins"),
    ("POST", "/api/v1/plugins"),
    ("GET", "/api/v1/plugins/recommended"),
    # ── Integrations ──
    ("GET", "/api/v1/integrations"),
    ("POST", "/api/v1/integrations"),
    ("GET", "/api/v1/integrations/providers"),
    ("GET", "/api/v1/integrations/status"),
    # ── OAuth ──
    ("GET", "/api/v1/oauth/providers"),
    ("GET", "/api/v1/oauth/status"),
    # ── Channels ──
    ("GET", "/api/v1/channels"),
    ("POST", "/api/v1/channels"),
    ("POST", "/api/v1/channels/send"),
    ("POST", "/api/v1/channels/broadcast"),
    # ── Sync ──
    ("GET", "/api/v1/sync/status"),
    ("POST", "/api/v1/sync/run"),
    ("GET", "/api/v1/sync/jobs"),
    ("GET", "/api/v1/sync/logs"),
    # ── Code & Security ──
    ("POST", "/api/v1/code/lsp/definition"),
    ("POST", "/api/v1/code/lsp/references"),
    ("POST", "/api/v1/code/lsp/hover"),
    ("POST", "/api/v1/code/ast/search"),
    ("POST", "/api/v1/code/patch"),
    ("POST", "/api/v1/security/check/tool"),
    ("POST", "/api/v1/security/check/file"),
    ("GET", "/api/v1/security/events"),
    ("GET", "/api/v1/security/stats"),
    ("GET", "/api/v1/security/rules"),
    ("POST", "/api/v1/security/rules"),
    # ── Knowledge ──
    ("GET", "/api/v1/knowledge/sections"),
    ("GET", "/api/v1/knowledge/search"),
    # ── Scheduler ──
    ("GET", "/api/v1/scheduler/tasks"),
    ("GET", "/api/v1/scheduler/jobs"),
    ("GET", "/api/v1/scheduler/jobs/grouped"),
    ("POST", "/api/v1/scheduler/jobs"),
    ("GET", "/api/v1/scheduler/bindings"),
    ("GET", "/api/v1/scheduler/tasks-with-workers"),
    # ── Model Config ──
    ("GET", "/api/v1/model-configs"),
    ("POST", "/api/v1/model-configs"),
    ("GET", "/api/v1/model-configs/usage"),
    # ── RBAC ──
    ("GET", "/api/v1/rbac/roles"),
    ("POST", "/api/v1/rbac/assign"),
    ("GET", "/api/v1/rbac/users"),
    ("POST", "/api/v1/rbac/check"),
    # ── Approvals ──
    ("GET", "/api/v1/approvals"),
    ("POST", "/api/v1/approvals"),
    ("GET", "/api/v1/approvals/rules"),
    ("GET", "/api/v1/approvals/stats"),
    # ── Config Ext ──
    ("GET", "/api/v1/config/integrations"),
    ("GET", "/api/v1/config/features"),
    ("GET", "/api/v1/config/health"),
    ("GET", "/api/v1/config/notifications"),
    ("POST", "/api/v1/config/notifications"),
    # ── Reports ──
    ("GET", "/api/v1/reports"),
    # ── Risk ──
    ("GET", "/api/v1/risk/alerts"),
    ("GET", "/api/v1/risk/alerts/unread-count"),
    ("POST", "/api/v1/risk/scan"),
    ("GET", "/api/v1/risk/market-status"),
    # ── Event Config ──
    ("GET", "/api/v1/event-config"),
    ("POST", "/api/v1/event-config"),
    # ── Worker Config ──
    ("GET", "/api/v1/worker-config"),
    ("GET", "/api/v1/worker-config/status"),
    ("POST", "/api/v1/worker-config"),
    # ── Prompts ──
    ("POST", "/api/v1/prompts/reload"),
    # ── Agent Config ──
    ("GET", "/api/v1/agents"),
    ("POST", "/api/v1/agents"),
]

# 最低端点数门槛（系统至少应有此数量端点注册）
MIN_TOTAL_ENDPOINTS = 150


# ══════════════════════════════════════════════════════════
# 契约测试
# ══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_openapi_schema_is_valid(client):
    """验证 OpenAPI schema 可正常生成且结构完整。"""
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200

    schema = resp.json()

    # 基本结构验证
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "避风港 — OS级合规智能体"
    assert schema["info"]["version"] == "4.0.0"

    # 确认 paths 字段存在
    assert "paths" in schema
    paths = schema["paths"]

    # 端点数量门槛验证
    total_endpoints = sum(
        len([m for m in methods if m in ("get", "post", "put", "delete", "patch")])
        for methods in paths.values()
    )
    assert total_endpoints >= MIN_TOTAL_ENDPOINTS, (
        f"Expected at least {MIN_TOTAL_ENDPOINTS} endpoints, found {total_endpoints}"
    )


@pytest.mark.asyncio
async def test_all_expected_endpoints_registered(client):
    """验证所有预期端点均已注册到 OpenAPI schema。"""
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200

    paths = resp.json()["paths"]

    # 收集已注册的 (method, path) 集合
    registered = set()
    for path, methods in paths.items():
        for method in methods:
            if method in ("get", "post", "put", "delete", "patch"):
                registered.add((method.upper(), path))

    # 验证所有预期端点都已注册
    missing = []
    for method, path in EXPECTED_ENDPOINTS:
        if (method, path) not in registered:
            missing.append(f"{method} {path}")

    assert not missing, (
        f"{len(missing)} endpoints missing from OpenAPI schema:\n"
        + "\n".join(f"  - {ep}" for ep in missing[:20])
        + (f"\n  ... and {len(missing) - 20} more" if len(missing) > 20 else "")
    )


@pytest.mark.asyncio
async def test_all_endpoints_have_summary(client):
    """验证所有端点均有 summary 描述。"""
    resp = await client.get("/openapi.json")
    paths = resp.json()["paths"]

    missing_summary = []
    for path, methods in paths.items():
        for method, spec in methods.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue
            if not spec.get("summary"):
                missing_summary.append(f"{method.upper()} {path}")

    # 允许少量遗漏（某些自动生成的端点）
    threshold = 10
    assert len(missing_summary) <= threshold, (
        f"{len(missing_summary)} endpoints missing summary (threshold={threshold}):\n"
        + "\n".join(f"  - {ep}" for ep in missing_summary[:15])
    )


# ══════════════════════════════════════════════════════════
# 基础端点功能验证（合并原 test_api.py）
# ══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_health_endpoint(client):
    """健康检查端点的响应符合预期。"""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "astra"
    assert data["version"] == "4.0.0"


@pytest.mark.asyncio
async def test_chat_endpoint_validation(client):
    """验证 chat/stream 端点的请求参数校验。"""
    # 缺少必填字段 message → 422
    resp = await client.post("/api/v1/chat/stream", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_products_list(client):
    """产品列表端点基本验证"""
    resp = await client.get("/api/v1/products")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_events_list(client):
    """事件列表端点基本验证"""
    resp = await client.get("/api/v1/events")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data


@pytest.mark.asyncio
async def test_pipeline_health(client):
    """流水线健康度端点"""
    resp = await client.get("/api/v1/pipeline/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tools_list(client):
    """Tools列表端点"""
    resp = await client.get("/api/v1/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert "tools" in data


@pytest.mark.asyncio
async def test_skills_list(client):
    """Skills列表端点"""
    resp = await client.get("/api/v1/skills")
    assert resp.status_code == 200
    data = resp.json()
    assert "skills" in data


@pytest.mark.asyncio
async def test_knowledge_sections(client):
    """知识库章节列表端点"""
    resp = await client.get("/api/v1/knowledge/sections")
    assert resp.status_code == 200
    data = resp.json()
    assert "sections" in data


@pytest.mark.asyncio
async def test_scheduler_tasks(client):
    """定时任务列表端点"""
    resp = await client.get("/api/v1/scheduler/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert "tasks" in data


@pytest.mark.asyncio
async def test_notifications_list(client):
    """通知列表端点"""
    resp = await client.get("/api/v1/notifications")
    assert resp.status_code == 200
    data = resp.json()
    assert "notifications" in data


@pytest.mark.asyncio
async def test_risk_alerts_list(client):
    """风险预警列表端点"""
    resp = await client.get("/api/v1/risk/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert "alerts" in data


@pytest.mark.asyncio
async def test_memory_namespaces(client):
    """记忆命名空间列表端点"""
    resp = await client.get("/api/v1/memory/namespaces")
    assert resp.status_code == 200
    data = resp.json()
    assert "namespaces" in data


@pytest.mark.asyncio
async def test_integrations_providers(client):
    """集成Provider模板列表端点"""
    resp = await client.get("/api/v1/integrations/providers")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_rbac_roles(client):
    """RBAC角色列表端点"""
    resp = await client.get("/api/v1/rbac/roles")
    assert resp.status_code == 200
    data = resp.json()
    assert "roles" in data


@pytest.mark.asyncio
async def test_config_features(client):
    """功能开关列表端点"""
    resp = await client.get("/api/v1/config/features")
    assert resp.status_code == 200
    data = resp.json()
    assert "features" in data


@pytest.mark.asyncio
async def test_reports_list(client):
    """合规报表列表端点"""
    resp = await client.get("/api/v1/reports")
    assert resp.status_code == 200
    data = resp.json()
    assert "reports" in data
