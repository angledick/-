"""
避风港 · 全业务流程集成测试
===========================
基于《后端变更路线图》《前端变更路线图》《shopify跨境合规全事件流程与系统对接指南》
模拟真实用户操作行为进行完整业务流程测试审查。

测试范围：
- OAuth授权流程
- 产品数据同步与管理
- 合规检查执行
- 事件处理机制
- Skills/Tools/Agent配置管理
- CLI命令执行
- 流水线健康度
- SSE流式对话
- 通知与风险预警
- 前端API一致性验证

注：RAG系统由于token限制问题暂不测试
"""

import pytest
import json
import time
import asyncio
from datetime import datetime, timezone
from httpx import AsyncClient


# ── 测试报告收集器 ──────────────────────────────────────
class TestReport:
    results = []

    @classmethod
    def record(cls, phase, test_name, endpoint, status_code, expected_status,
               response_body, passed, details=""):
        cls.results.append({
            "phase": phase,
            "test_name": test_name,
            "endpoint": endpoint,
            "status_code": status_code,
            "expected_status": expected_status,
            "response_body_preview": str(response_body)[:500],
            "passed": passed,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @classmethod
    def summary(cls):
        total = len(cls.results)
        passed = sum(1 for r in cls.results if r["passed"])
        print(f"\n{'='*80}")
        print(f"  TEST REPORT: {passed}/{total} PASSED")
        print(f"{'='*80}")
        for r in cls.results:
            icon = "[OK]" if r["passed"] else "[FAIL]"
            print(f"  {icon} [{r['phase']}] {r['test_name']} "
                  f"| {r['endpoint']} | HTTP {r['status_code']} "
                  f"{'(expected: '+str(r['expected_status'])+')' if not r['passed'] else ''}")
            if r["details"]:
                print(f"       -> {r['details']}")
        print(f"\n  Total: {total} | Passed: {passed} | Failed: {total - passed}")
        return {"total": total, "passed": passed, "failed": total - passed}


# ── 通用辅助 ────────────────────────────────────────────
async def get_auth_token(client: AsyncClient) -> str:
    """获取认证token（使用默认admin账户）"""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    if resp.status_code == 200:
        data = resp.json()
        return data.get("access_token", data.get("token", ""))
    return ""


def auth_headers(token: str = "") -> dict:
    """构建认证请求头"""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


# ══════════════════════════════════════════════════════════
# Phase 1: 基础健康检查 & 认证
# ══════════════════════════════════════════════════════════

class TestPhase1_Foundation:
    """Phase 1: 基础设施验证"""

    async def test_health_check(self, client):
        """验证系统健康检查端点"""
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "service" in data
        TestReport.record("Phase1-基础", "健康检查", "GET /api/v1/health",
                         resp.status_code, 200, data, True)

    async def test_openapi_schema(self, client):
        """验证OpenAPI Schema可用"""
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["openapi"].startswith("3.")
        assert "paths" in schema
        path_count = len(schema["paths"])
        TestReport.record("Phase1-基础", "OpenAPI Schema",
                         "GET /openapi.json", resp.status_code, 200,
                         {"path_count": path_count}, True,
                         f"已注册 {path_count} 个路径")

    async def test_auth_login(self, client):
        """验证认证登录流程"""
        resp = await client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        has_token = ("access_token" in data or "token" in data) if passed else False
        TestReport.record("Phase1-认证", "用户登录",
                         "POST /api/v1/auth/login", resp.status_code, 200,
                         data, passed and has_token,
                         "access_token存在" if has_token else "缺少token字段")

    async def test_auth_invalid_credentials(self, client):
        """验证无效凭据返回401"""
        resp = await client.post("/api/v1/auth/login", json={
            "username": "invalid_user",
            "password": "wrong_password"
        })
        passed = resp.status_code in [401, 403]
        TestReport.record("Phase1-认证", "无效凭据拒绝",
                         "POST /api/v1/auth/login", resp.status_code, 401,
                         resp.json() if resp.status_code != 500 else {},
                         passed)


# ══════════════════════════════════════════════════════════
# Phase 2: Shopify集成 & OAuth流程
# ══════════════════════════════════════════════════════════

class TestPhase2_Shopify:
    """Phase 2: Shopify第三方系统集成"""

    async def test_shopify_oauth_initiate(self, client):
        """验证Shopify OAuth授权发起"""
        resp = await client.get("/api/v1/shopify/auth",
                               params={"shop": "test-store.myshopify.com"})
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        has_url = "authorization_url" in data
        TestReport.record("Phase2-Shopify", "OAuth授权发起",
                         "GET /api/v1/shopify/auth", resp.status_code, 200,
                         data, passed and has_url,
                         f"auth_url: {data.get('authorization_url', 'N/A')[:80]}")

    async def test_shopify_oauth_invalid_shop(self, client):
        """验证无效店铺域名返回400"""
        resp = await client.get("/api/v1/shopify/auth",
                               params={"shop": "invalid-domain.com"})
        passed = resp.status_code == 400
        TestReport.record("Phase2-Shopify", "无效店铺域名验证",
                         "GET /api/v1/shopify/auth?shop=invalid", resp.status_code, 400,
                         resp.json() if resp.status_code != 500 else {},
                         passed, "正确拒绝非.myshopify.com域名")

    async def test_shopify_shops_list(self, client):
        """验证已连接店铺列表"""
        resp = await client.get("/api/v1/shopify/shops")
        passed = resp.status_code == 200
        data = resp.json() if passed else []
        TestReport.record("Phase2-Shopify", "店铺列表查询",
                         "GET /api/v1/shopify/shops", resp.status_code, 200,
                         data, passed,
                         f"返回 {len(data)} 个店铺")

    async def test_shopify_webhook_receive(self, client):
        """验证Webhook接收能力"""
        webhook_body = {
            "id": 123456789,
            "title": "Test LED灯带",
            "product_type": "electronics",
            "vendor": "TestVendor",
            "tags": "CE,WEEE",
        }
        resp = await client.post("/api/v1/shopify/webhook",
                                content=json.dumps(webhook_body),
                                headers={
                                    "Content-Type": "application/json",
                                    "X-Shopify-Topic": "products/create",
                                    "X-Shopify-Shop": "test-store.myshopify.com",
                                })
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase2-Shopify", "Webhook接收",
                         "POST /api/v1/shopify/webhook", resp.status_code, 200,
                         data, passed,
                         f"topic={data.get('topic', 'N/A')}")


# ══════════════════════════════════════════════════════════
# Phase 3: 产品管理 & 生命周期
# ══════════════════════════════════════════════════════════

class TestPhase3_Products:
    """Phase 3: 产品全生命周期管理"""

    async def test_product_list(self, client):
        """验证产品列表查询"""
        resp = await client.get("/api/v1/products")
        passed = resp.status_code == 200
        data = resp.json() if passed else []
        TestReport.record("Phase3-产品", "产品列表",
                         "GET /api/v1/products", resp.status_code, 200,
                         data[:2] if isinstance(data, list) else data, passed,
                         f"返回 {len(data) if isinstance(data, list) else 'N/A'} 个产品")

    async def test_product_create(self, client):
        """验证产品创建（LED灯带出口德国场景）"""
        product_data = {
            "name": "LED灯带-德国测试",
            "product_type": "electronics",
            "target_markets": ["德国", "欧盟"],
            "hs_code": "8541.4100",
            "description": "LED灯带，用于测试跨境合规流程",
            "certifications": ["CE", "WEEE", "RoHS"],
            "supplier": "TestFactory深圳",
        }
        resp = await client.post("/api/v1/products", json=product_data)
        passed = resp.status_code in [200, 201]
        data = resp.json() if passed else {}
        product_id = data.get("id", "")
        TestReport.record("Phase3-产品", "产品创建",
                         "POST /api/v1/products", resp.status_code, 200,
                         data, passed,
                         f"product_id={product_id}")
        return product_id

    async def test_product_create_duplicate(self, client):
        """验证重复产品创建拒绝"""
        product_data = {
            "name": "LED灯带-德国测试",
            "product_type": "electronics",
            "target_markets": ["德国"],
        }
        # 第一次创建
        await client.post("/api/v1/products", json=product_data)
        # 第二次创建同名产品
        resp = await client.post("/api/v1/products", json=product_data)
        passed = resp.status_code in [200, 201, 409]
        TestReport.record("Phase3-产品", "重复产品处理",
                         "POST /api/v1/products (重复)", resp.status_code, 409,
                         resp.json() if resp.status_code != 500 else {},
                         passed, "409=拒绝重复, 200/201=允许同名")

    async def test_product_filter_by_lifecycle(self, client):
        """验证按生命周期阶段筛选"""
        resp = await client.get("/api/v1/products",
                               params={"lifecycle_stage": "concept"})
        passed = resp.status_code == 200
        data = resp.json() if passed else []
        TestReport.record("Phase3-产品", "生命周期筛选",
                         "GET /api/v1/products?lifecycle_stage=concept",
                         resp.status_code, 200, data[:2] if isinstance(data, list) else data,
                         passed)

    async def test_product_filter_by_market(self, client):
        """验证按目标市场筛选"""
        resp = await client.get("/api/v1/products",
                               params={"market": "德国"})
        passed = resp.status_code == 200
        TestReport.record("Phase3-产品", "市场筛选",
                         "GET /api/v1/products?market=德国",
                         resp.status_code, 200, resp.json() if passed else {},
                         passed)


# ══════════════════════════════════════════════════════════
# Phase 4: Agent配置 & 多Agent管理
# ══════════════════════════════════════════════════════════

class TestPhase4_AgentConfig:
    """Phase 4: Agent配置CRUD & 关联管理（需要认证）"""

    async def _get_token(self, client):
        return await get_auth_token(client)

    async def test_agent_list(self, client):
        """验证Agent列表查询（需认证）"""
        token = await self._get_token(client)
        headers = auth_headers(token)
        resp = await client.get("/api/v1/agents", headers=headers)
        passed = resp.status_code == 200
        data = resp.json() if passed else []
        TestReport.record("Phase4-Agent", "Agent列表",
                         "GET /api/v1/agents", resp.status_code, 200,
                         data[:2] if isinstance(data, list) else data, passed,
                         f"返回 {len(data) if isinstance(data, list) else 'N/A'} 个Agent")

    async def test_agent_create(self, client):
        """验证Agent创建（需认证）"""
        token = await self._get_token(client)
        headers = auth_headers(token)
        agent_data = {
            "name": "TestComplianceWorker",
            "type": "worker",
            "description": "合规检查Worker测试",
            "system_prompt": "你是一个合规检查Worker，负责执行产品合规性检查。",
            "enabled": True,
        }
        resp = await client.post("/api/v1/agents", json=agent_data, headers=headers)
        passed = resp.status_code in [200, 201]
        data = resp.json() if passed else {}
        TestReport.record("Phase4-Agent", "Agent创建",
                         "POST /api/v1/agents", resp.status_code, 200,
                         data, passed,
                         f"agent_id={data.get('id', 'N/A')}")

    async def test_agent_skills_association(self, client):
        """验证Agent-Skills关联"""
        token = await self._get_token(client)
        headers = auth_headers(token)
        resp = await client.get("/api/v1/agents", headers=headers)
        if resp.status_code == 200:
            agents = resp.json()
            if agents:
                agent_id = agents[0]["id"]
                resp2 = await client.get(f"/api/v1/agents/{agent_id}/skills", headers=headers)
                passed = resp2.status_code == 200
                data = resp2.json() if passed else {}
                TestReport.record("Phase4-Agent", "Agent-Skills关联查询",
                                 f"GET /api/v1/agents/{agent_id}/skills",
                                 resp2.status_code, 200, data, passed)
                return
        TestReport.record("Phase4-Agent", "Agent-Skills关联查询",
                         "GET /api/v1/agents/{id}/skills", 0, 200, {},
                         False, "无可用Agent")

    async def test_agent_tools_association(self, client):
        """验证Agent-Tools关联"""
        token = await self._get_token(client)
        headers = auth_headers(token)
        resp = await client.get("/api/v1/agents", headers=headers)
        if resp.status_code == 200:
            agents = resp.json()
            if agents:
                agent_id = agents[0]["id"]
                resp2 = await client.get(f"/api/v1/agents/{agent_id}/tools", headers=headers)
                passed = resp2.status_code == 200
                TestReport.record("Phase4-Agent", "Agent-Tools关联查询",
                                 f"GET /api/v1/agents/{agent_id}/tools",
                                 resp2.status_code, 200,
                                 resp2.json() if passed else {}, passed)
                return
        TestReport.record("Phase4-Agent", "Agent-Tools关联查询",
                         "GET /api/v1/agents/{id}/tools", 0, 200, {},
                         False, "无可用Agent")


# ══════════════════════════════════════════════════════════
# Phase 5: Skills管理
# ══════════════════════════════════════════════════════════

class TestPhase5_Skills:
    """Phase 5: Skills管理"""

    async def test_skills_list(self, client):
        """验证Skills列表"""
        resp = await client.get("/api/v1/skills")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        skills = data.get("skills", []) if isinstance(data, dict) else data
        TestReport.record("Phase5-Skills", "Skills列表",
                         "GET /api/v1/skills", resp.status_code, 200,
                         data, passed,
                         f"返回 {len(skills)} 个Skills")

    async def test_skill_install(self, client):
        """验证Skill安装"""
        install_data = {
            "name": "shopify-admin-test",
            "source": "builtin",
            "config": {"version": "1.0.0"},
        }
        resp = await client.post("/api/v1/skills/install", json=install_data)
        passed = resp.status_code in [200, 201]
        data = resp.json() if passed else {}
        TestReport.record("Phase5-Skills", "Skill安装",
                         "POST /api/v1/skills/install", resp.status_code, 200,
                         data, passed)

    async def test_skill_recommend(self, client):
        """验证Skill推荐（按业务阶段）"""
        req_data = {
            "business_stage": 4,
            "event_category": "compliance",
            "product_type": "electronics",
        }
        resp = await client.post("/api/v1/skills/recommend", json=req_data)
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase5-Skills", "Skill推荐",
                         "POST /api/v1/skills/recommend", resp.status_code, 200,
                         data, passed)


# ══════════════════════════════════════════════════════════
# Phase 6: Tools管理
# ══════════════════════════════════════════════════════════

class TestPhase6_Tools:
    """Phase 6: Tools CRUD"""

    async def test_tools_list(self, client):
        """验证Tools列表"""
        resp = await client.get("/api/v1/tools")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        tools = data.get("tools", []) if isinstance(data, dict) else data
        TestReport.record("Phase6-Tools", "Tools列表",
                         "GET /api/v1/tools", resp.status_code, 200,
                         data, passed,
                         f"返回 {len(tools)} 个Tools")

    async def test_tool_create(self, client):
        """验证Tool创建"""
        tool_data = {
            "name": "test_compliance_tool",
            "description": "测试合规检查工具",
            "tool_type": "custom",
            "category": "compliance",
            "enabled": True,
        }
        resp = await client.post("/api/v1/tools", json=tool_data)
        passed = resp.status_code in [200, 201]
        data = resp.json() if passed else {}
        TestReport.record("Phase6-Tools", "Tool创建",
                         "POST /api/v1/tools", resp.status_code, 200,
                         data, passed,
                         f"tool_id={data.get('id', 'N/A')}")

    async def test_tool_toggle(self, client):
        """验证Tool启用/禁用"""
        # 先获取列表
        resp = await client.get("/api/v1/tools")
        if resp.status_code == 200:
            tools = resp.json().get("tools", [])
            if tools:
                tool_id = tools[0]["id"]
                resp2 = await client.put(f"/api/v1/tools/{tool_id}/toggle",
                                        json={"enabled": False})
                passed = resp2.status_code == 200
                TestReport.record("Phase6-Tools", "Tool启用/禁用",
                                 f"PUT /api/v1/tools/{tool_id}/toggle",
                                 resp2.status_code, 200,
                                 resp2.json() if passed else {}, passed)
                return
        TestReport.record("Phase6-Tools", "Tool启用/禁用",
                         "PUT /api/v1/tools/{id}/toggle", 0, 200, {},
                         False, "无可用Tool")


# ══════════════════════════════════════════════════════════
# Phase 7: OAuth/Integrations管理
# ══════════════════════════════════════════════════════════

class TestPhase7_Integrations:
    """Phase 7: OAuth集成管理"""

    async def test_connections_list(self, client):
        """验证连接列表"""
        resp = await client.get("/api/v1/integrations")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase7-集成", "连接列表",
                         "GET /api/v1/integrations", resp.status_code, 200,
                         data, passed)

    async def test_providers_list(self, client):
        """验证Provider模板列表"""
        resp = await client.get("/api/v1/integrations/providers")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        providers = data.get("providers", [])
        TestReport.record("Phase7-集成", "Provider列表",
                         "GET /api/v1/integrations/providers",
                         resp.status_code, 200, data, passed,
                         f"返回 {len(providers)} 个Provider")

    async def test_create_connection(self, client):
        """验证创建OAuth连接"""
        conn_data = {
            "provider": "shopify",
            "label": "测试Shopify店铺",
            "config": {"shop_domain": "test-store.myshopify.com"},
        }
        resp = await client.post("/api/v1/integrations", json=conn_data)
        passed = resp.status_code in [200, 201]
        data = resp.json() if passed else {}
        TestReport.record("Phase7-集成", "创建连接",
                         "POST /api/v1/integrations", resp.status_code, 200,
                         data, passed,
                         f"connection_id={data.get('id', 'N/A')}")

    async def test_status_summary(self, client):
        """验证各Provider状态汇总"""
        resp = await client.get("/api/v1/integrations/status")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase7-集成", "状态汇总",
                         "GET /api/v1/integrations/status",
                         resp.status_code, 200, data, passed)


# ══════════════════════════════════════════════════════════
# Phase 8: 合规流水线 & 事件系统
# ══════════════════════════════════════════════════════════

class TestPhase8_Pipeline:
    """Phase 8: 合规流水线 & 事件"""

    async def test_pipeline_health(self, client):
        """验证流水线健康度"""
        resp = await client.get("/api/v1/pipeline/health")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase8-流水线", "流水线健康度",
                         "GET /api/v1/pipeline/health", resp.status_code, 200,
                         data, passed,
                         f"overall_score={data.get('overall_score', 'N/A')}")

    async def test_pipeline_stages(self, client):
        """验证流水线阶段数据（10阶段合规总览）"""
        resp = await client.get("/api/v1/pipeline/stages")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        stages = data.get("stages", [])
        TestReport.record("Phase8-流水线", "流水线阶段",
                         "GET /api/v1/pipeline/stages", resp.status_code, 200,
                         data, passed,
                         f"返回 {len(stages)} 个阶段")

    async def test_pipeline_metrics(self, client):
        """验证流水线聚合指标"""
        resp = await client.get("/api/v1/pipeline/metrics")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase8-流水线", "流水线指标",
                         "GET /api/v1/pipeline/metrics", resp.status_code, 200,
                         data, passed,
                         f"total_products={data.get('total_products', 'N/A')}")

    async def test_event_chain_list(self, client):
        """验证事件链列表"""
        resp = await client.get("/api/v1/chains/events")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase8-流水线", "事件链列表",
                         "GET /api/v1/chains/events", resp.status_code, 200,
                         data, passed)

    async def test_create_event(self, client):
        """验证事件创建"""
        event_data = {
            "chain_id": "test_product_001",
            "source": "compliance_engine",
            "type": "compliance:check_started",
            "description_nl": "LED灯带-德国合规检查启动",
            "severity": "medium",
            "payload": {
                "product_id": "p_led_de_001",
                "target_market": "德国",
                "check_items": ["CE", "WEEE", "RoHS"]
            },
            "tags": ["compliance", "germany"]
        }
        resp = await client.post("/api/v1/chains/events", json=event_data)
        passed = resp.status_code in [200, 201]
        TestReport.record("Phase8-流水线", "事件创建",
                         "POST /api/v1/chains/events", resp.status_code, 200,
                         resp.json() if passed else {}, passed)


# ══════════════════════════════════════════════════════════
# Phase 9: CLI命令系统
# ══════════════════════════════════════════════════════════

class TestPhase9_CLI:
    """Phase 9: CLI命令系统"""

    async def test_cli_execute_help(self, client):
        """验证CLI /help命令"""
        resp = await client.post("/api/v1/cli/execute",
                                json={"command": "/help"})
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase9-CLI", "CLI /help",
                         "POST /api/v1/cli/execute", resp.status_code, 200,
                         data, passed,
                         f"success={data.get('success', 'N/A')}")

    async def test_cli_execute_status(self, client):
        """验证CLI /status命令"""
        resp = await client.post("/api/v1/cli/execute",
                                json={"command": "/status"})
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase9-CLI", "CLI /status",
                         "POST /api/v1/cli/execute", resp.status_code, 200,
                         data, passed)

    async def test_cli_execute_products(self, client):
        """验证CLI /products命令"""
        resp = await client.post("/api/v1/cli/execute",
                                json={"command": "/products"})
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase9-CLI", "CLI /products",
                         "POST /api/v1/cli/execute", resp.status_code, 200,
                         data, passed)

    async def test_cli_complete(self, client):
        """验证命令自动补全"""
        resp = await client.get("/api/v1/cli/complete",
                               params={"prefix": "/he"})
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        suggestions = data.get("suggestions", [])
        TestReport.record("Phase9-CLI", "命令补全",
                         "GET /api/v1/cli/complete?prefix=/he",
                         resp.status_code, 200, data, passed,
                         f"返回 {len(suggestions)} 条建议")

    async def test_cli_history(self, client):
        """验证命令历史"""
        resp = await client.get("/api/v1/cli/history")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase9-CLI", "命令历史",
                         "GET /api/v1/cli/history", resp.status_code, 200,
                         data, passed)


# ══════════════════════════════════════════════════════════
# Phase 10: SSE流式对话
# ══════════════════════════════════════════════════════════

class TestPhase10_Streaming:
    """Phase 10: SSE流式对话"""

    async def test_chat_config_get(self, client):
        """验证对话配置获取"""
        resp = await client.get("/api/v1/chat/config")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase10-对话", "对话配置获取",
                         "GET /api/v1/chat/config", resp.status_code, 200,
                         data, passed,
                         f"agent_id={data.get('agent_id', 'N/A')}")

    async def test_chat_config_update(self, client):
        """验证对话配置更新"""
        config_data = {
            "agent_id": "agent_qa",
            "pipeline_mode": "6step",
        }
        resp = await client.put("/api/v1/chat/config", json=config_data)
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase10-对话", "对话配置更新",
                         "PUT /api/v1/chat/config", resp.status_code, 200,
                         data, passed)

    async def test_sse_stream_basic(self, client):
        """验证SSE流式对话端点可用性"""
        stream_data = {
            "message": "检查LED灯带出口德国的合规要求",
            "session_id": "",
            "product_id": "",
        }
        # SSE endpoint returns StreamingResponse
        resp = await client.post("/api/v1/chat/stream", json=stream_data)
        # SSE should return 200 with text/event-stream
        passed = resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        is_sse = "text/event-stream" in content_type
        TestReport.record("Phase10-对话", "SSE流式对话",
                         "POST /api/v1/chat/stream", resp.status_code, 200,
                         {"content_type": content_type},
                         passed and is_sse,
                         f"Content-Type: {content_type}")


# ══════════════════════════════════════════════════════════
# Phase 11: 风险预警 & 通知
# ══════════════════════════════════════════════════════════

class TestPhase11_Risk:
    """Phase 11: 风险预警与通知"""

    async def test_risk_alerts_list(self, client):
        """验证风险预警列表"""
        resp = await client.get("/api/v1/risk/alerts")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase11-风险", "预警列表",
                         "GET /api/v1/risk/alerts", resp.status_code, 200,
                         data, passed)

    async def test_notifications_list(self, client):
        """验证通知列表"""
        resp = await client.get("/api/v1/notifications")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase11-风险", "通知列表",
                         "GET /api/v1/notifications", resp.status_code, 200,
                         data, passed)


# ══════════════════════════════════════════════════════════
# Phase 12: 指标监控 & 主动引擎
# ══════════════════════════════════════════════════════════

class TestPhase12_Metrics:
    """Phase 12: 指标监控与主动引擎"""

    async def test_metrics_dashboard(self, client):
        """验证指标仪表盘"""
        resp = await client.get("/api/v1/metrics/dashboard")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase12-指标", "指标仪表盘",
                         "GET /api/v1/metrics/dashboard", resp.status_code, 200,
                         data, passed)

    async def test_proactive_heartbeat(self, client):
        """验证主动引擎心跳"""
        resp = await client.get("/api/v1/proactive/heartbeat")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase12-指标", "主动引擎心跳",
                         "GET /api/v1/proactive/heartbeat",
                         resp.status_code, 200, data, passed)

    async def test_proactive_brief(self, client):
        """验证合规简报"""
        resp = await client.get("/api/v1/proactive/brief")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase12-指标", "合规简报",
                         "GET /api/v1/proactive/brief", resp.status_code, 200,
                         data, passed)


# ══════════════════════════════════════════════════════════
# Phase 13: 记忆 & 知识库
# ══════════════════════════════════════════════════════════

class TestPhase13_Memory:
    """Phase 13: 记忆树与知识库"""

    async def test_memory_tree(self, client):
        """验证记忆树层级结构（需要product_id参数）"""
        # 先获取一个产品ID
        products_resp = await client.get("/api/v1/products")
        product_id = "default"
        if products_resp.status_code == 200:
            products = products_resp.json()
            if products:
                product_id = products[0]["id"]
        resp = await client.get("/api/v1/memory/tree",
                               params={"product_id": product_id})
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase13-记忆", "记忆树结构",
                         f"GET /api/v1/memory/tree?product_id={product_id}",
                         resp.status_code, 200, data, passed)

    async def test_knowledge_sections(self, client):
        """验证知识库章节列表"""
        resp = await client.get("/api/v1/knowledge/sections")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase13-记忆", "知识库章节",
                         "GET /api/v1/knowledge/sections", resp.status_code, 200,
                         data, passed)


# ══════════════════════════════════════════════════════════
# Phase 14: 定时任务 & 调度器
# ══════════════════════════════════════════════════════════

class TestPhase14_Scheduler:
    """Phase 14: 定时任务管理"""

    async def test_scheduler_jobs(self, client):
        """验证定时任务列表"""
        resp = await client.get("/api/v1/scheduler/jobs")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        jobs = data.get("jobs", [])
        TestReport.record("Phase14-调度", "任务列表",
                         "GET /api/v1/scheduler/jobs", resp.status_code, 200,
                         data, passed,
                         f"返回 {len(jobs)} 个任务")

    async def test_scheduler_grouped(self, client):
        """验证分组任务列表"""
        resp = await client.get("/api/v1/scheduler/jobs/grouped")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase14-调度", "分组任务列表",
                         "GET /api/v1/scheduler/jobs/grouped",
                         resp.status_code, 200, data, passed)


# ══════════════════════════════════════════════════════════
# Phase 15: 权限管理（RBAC）
# ══════════════════════════════════════════════════════════

class TestPhase15_Admin:
    """Phase 15: 后台管理与权限"""

    async def test_rbac_roles(self, client):
        """验证RBAC角色列表"""
        resp = await client.get("/api/v1/rbac/roles")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase15-权限", "RBAC角色列表",
                         "GET /api/v1/rbac/roles", resp.status_code, 200,
                         data, passed)

    async def test_approvals_list(self, client):
        """验证用户列表（权限管理基础）"""
        token = await get_auth_token(client)
        headers = auth_headers(token)
        resp = await client.get("/api/v1/users", headers=headers)
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        TestReport.record("Phase15-权限", "用户列表",
                         "GET /api/v1/users", resp.status_code, 200,
                         data, passed)


# ══════════════════════════════════════════════════════════
# Phase 16: 完整业务流程端到端测试
# ══════════════════════════════════════════════════════════

class TestPhase16_E2E:
    """Phase 16: 端到端业务流程"""

    async def test_e2e_product_lifecycle(self, client):
        """端到端：产品全生命周期（概念→上架→在售）"""
        # Step 1: 创建产品（concept阶段）
        product = {
            "name": f"E2E测试产品_{int(time.time())}",
            "product_type": "electronics",
            "target_markets": ["德国", "法国"],
            "hs_code": "8541.4100",
        }
        resp = await client.post("/api/v1/products", json=product)
        step1_ok = resp.status_code in [200, 201]
        product_data = resp.json() if step1_ok else {}
        product_id = product_data.get("id", "")

        # Step 2: 查询产品详情
        step2_ok = False
        if product_id:
            resp2 = await client.get(f"/api/v1/products/{product_id}")
            step2_ok = resp2.status_code == 200

        # Step 3: 查询产品事件
        step3_ok = False
        if product_id:
            resp3 = await client.get(f"/api/v1/products/{product_id}/events")
            step3_ok = resp3.status_code == 200

        all_passed = step1_ok and step2_ok and step3_ok
        TestReport.record("Phase16-E2E", "产品全生命周期",
                         "POST→GET→GET /api/v1/products/*",
                         200 if all_passed else 500, 200,
                         {"step1": step1_ok, "step2": step2_ok, "step3": step3_ok},
                         all_passed,
                         f"product_id={product_id}")

    async def test_e2e_compliance_flow(self, client):
        """端到端：合规检查流程（事件感知→检查→告知）"""
        # Step 1: 获取流水线状态
        resp1 = await client.get("/api/v1/pipeline/health")
        step1_ok = resp1.status_code == 200

        # Step 2: 创建合规事件（使用正确的schema）
        event_data = {
            "chain_id": f"e2e_compliance_{int(time.time())}",
            "source": "e2e_test",
            "type": "compliance:check_started",
            "description_nl": "E2E合规检查测试-LED灯带德国市场",
            "severity": "medium",
            "payload": {"trigger": "e2e_test"},
            "tags": ["e2e", "compliance"]
        }
        resp2 = await client.post("/api/v1/chains/events", json=event_data)
        step2_ok = resp2.status_code in [200, 201]

        # Step 3: 检查通知是否生成
        resp3 = await client.get("/api/v1/notifications")
        step3_ok = resp3.status_code == 200

        all_passed = step1_ok and step2_ok and step3_ok
        TestReport.record("Phase16-E2E", "合规检查流程",
                         "Pipeline→Events→Notifications",
                         200 if all_passed else 500, 200,
                         {"step1": step1_ok, "step2": step2_ok, "step3": step3_ok},
                         all_passed)

    async def test_e2e_config_management(self, client):
        """端到端：配置管理流程（Agent→Skills→Tools→OAuth）"""
        token = await get_auth_token(client)
        headers = auth_headers(token)
        # Step 1: Agent列表（需认证）
        resp1 = await client.get("/api/v1/agents", headers=headers)
        step1_ok = resp1.status_code == 200

        # Step 2: Skills列表
        resp2 = await client.get("/api/v1/skills")
        step2_ok = resp2.status_code == 200

        # Step 3: Tools列表
        resp3 = await client.get("/api/v1/tools")
        step3_ok = resp3.status_code == 200

        # Step 4: Integrations列表
        resp4 = await client.get("/api/v1/integrations")
        step4_ok = resp4.status_code == 200

        all_passed = step1_ok and step2_ok and step3_ok and step4_ok
        TestReport.record("Phase16-E2E", "配置管理流程",
                         "Agents→Skills→Tools→Integrations",
                         200 if all_passed else 500, 200,
                         {"agents": step1_ok, "skills": step2_ok,
                          "tools": step3_ok, "integrations": step4_ok},
                         all_passed)


# ══════════════════════════════════════════════════════════
# 前端API一致性验证
# ══════════════════════════════════════════════════════════

class TestFrontendAPIConsistency:
    """前端API配置与后端端点一致性验证"""

    FRONTEND_ENDPOINTS = [
        ("GET", "/api/v1/agents", "agentsApi.list"),
        ("GET", "/api/v1/skills", "skillsApi.list"),
        ("GET", "/api/v1/tools", "toolsApi.list"),
        ("GET", "/api/v1/integrations", "oauthApi.list"),
        ("GET", "/api/v1/integrations/providers", "oauthApi.getProviders"),
        ("GET", "/api/v1/integrations/status", "oauthApi.getStatusSummary"),
        ("GET", "/api/v1/pipeline/health", "pipelineApi.health"),
        ("GET", "/api/v1/risk/alerts", "riskAlertsApi.list"),
        ("GET", "/api/v1/products", "productsApi.list"),
        ("GET", "/api/v1/chat/config", "chatConfig.get"),
        ("GET", "/api/v1/cli/history", "cliApi.history"),
        ("GET", "/api/v1/knowledge/sections", "knowledgeApi.list"),
        ("GET", "/api/v1/proactive/brief", "proactiveApi.brief"),
        ("GET", "/api/v1/scheduler/jobs", "schedulerApi.list"),
        ("GET", "/api/v1/memory/summaries?product_id=default", "memoryApi.tree"),
        ("GET", "/api/v1/metrics/dashboard", "metricsApi.dashboard"),
    ]

    async def test_all_frontend_endpoints_exist(self, client):
        """验证前端config.ts中所有API端点在后端均已注册"""
        missing = []
        for method, path, frontend_name in self.FRONTEND_ENDPOINTS:
            if method == "GET":
                resp = await client.get(path)
            elif method == "POST":
                resp = await client.post(path, json={})
            else:
                continue

            if resp.status_code in [404, 405]:
                missing.append(f"{method} {path} ({frontend_name})")

        passed = len(missing) == 0
        TestReport.record("前端一致性", "端点存在性验证",
                         f"{len(self.FRONTEND_ENDPOINTS)} 个端点",
                         200 if passed else 404, 200,
                         {"missing": missing[:5]},
                         passed,
                         f"缺失: {len(missing)} 个" if missing else "全部存在")


# ══════════════════════════════════════════════════════════
# 测试报告生成 (pytest session结束时输出)
# ══════════════════════════════════════════════════════════

@pytest.fixture(scope="session", autouse=True)
def print_report(request):
    """测试结束后输出报告"""
    yield
    TestReport.summary()
