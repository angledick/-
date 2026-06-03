from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
import asyncio

# Windows Python 3.13+ 需要显式设置 ProactorEventLoopPolicy
# 否则 subprocess 创建会抛出 NotImplementedError
if hasattr(asyncio, 'WindowsProactorEventLoopPolicy'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# ── 确保 SDK 所需环境变量写入 os.environ ─────────────────
# claude_agent_sdk 内部通过 os.environ 读取 ANTHROPIC_API_KEY
# Pydantic 从 .env 文件加载到 settings 但不自动写入 os.environ
# （sdk_env_json 已在 config.py 中自动注入）
from app.config import settings
if settings.anthropic_api_key:
    os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)

# 原有路由（chat已删除，对话入口统一到streaming.py SSE流式）
from app.api import chains, shopify, risk, sessions, auth as auth_router, users, agent_config as agent_config_router, sdk_sessions
# OS级智能体新增路由
from app.api import products, events, pipeline, notifications, cli, rag, event_config, worker_config
# Phase 2 新增路由
from app.api import memory, metrics, tools, streaming
# Phase 3 新增路由
from app.api import skills, plugins, integrations, code_security, model_config as model_config_router
# Phase 3.5 新增路由（知识库）
from app.api import knowledge
# Phase 4 新增路由（后台管理）
from app.api import admin

# 定时任务管理
from app.api import scheduler_config

from app.core.scheduler import start_scheduler, stop_scheduler
from app.services.ws_manager import ws_manager
from app.services.astra_assistant import AstraAssistant

app = FastAPI(
    title="避风港 — OS级合规智能体",
    description="事件驱动 + 多Agent + 记忆树 + TokenJuice + QAAgent | 跨境合规全生命周期管理",
    version="4.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 原有路由注册（chat已移除，对话统一由streaming.py处理）────
app.include_router(chains.router)
app.include_router(shopify.router)
app.include_router(risk.router)
app.include_router(sessions.router)
app.include_router(auth_router.router)
app.include_router(users.router)
app.include_router(agent_config_router.router)
app.include_router(sdk_sessions.router)

# ── OS级智能体新增路由注册 ──────────────────────────
app.include_router(products.router)
app.include_router(events.router)
app.include_router(pipeline.router)
app.include_router(notifications.router)
app.include_router(cli.router)
app.include_router(rag.router)
app.include_router(event_config.router)
app.include_router(worker_config.router)

# ── Phase 2 新增路由注册 ─────────────────────────────
app.include_router(memory.router)
app.include_router(metrics.router)
app.include_router(tools.router)
app.include_router(streaming.router)

# ── Phase 3 新增路由注册 ─────────────────────────
app.include_router(skills.router)
app.include_router(plugins.router)
app.include_router(integrations.integrations_router)
app.include_router(integrations.oauth_router)
app.include_router(integrations.channels_router)
app.include_router(integrations.sync_router)
app.include_router(code_security.code_router)
app.include_router(code_security.security_router)

# ── Phase 3.5 知识库路由 ──────────────────────
app.include_router(knowledge.router)

# ── 定时任务管理路由 ────────────────────────────
app.include_router(scheduler_config.router)

# ── 模型配置路由 ────────────────────────────────
app.include_router(model_config_router.router)

# ── Phase 4 新增路由注册 ─────────────────────────
app.include_router(admin.rbac_router)
app.include_router(admin.approvals_router)
app.include_router(admin.config_ext_router)
app.include_router(admin.reports_router)


@app.get("/api/v1/health", tags=["health"], summary="Health Check")
async def health():
    return {"status": "ok", "service": "astra", "version": "4.0.0"}


@app.get("/api/v1/system/health", tags=["system"], summary="System Health")
async def system_health():
    """系统健康详细检查（QAAgent诊断）"""
    from app.core.qa_agent import get_qa_agent
    agent = get_qa_agent()
    return await agent.health_check()


# ── WebSocket 端点 ────────────────────────────────

@app.websocket("/api/v1/ws")
async def websocket_endpoint(ws: WebSocket, user_id: str = "default"):
    """WebSocket 实时推送端点。

    前端连接: new WebSocket(`ws://host/api/v1/ws?user_id={user_id}`)
    推送消息格式: { type: "alert" | "scan_update", payload: {...} }
    """
    await ws_manager.connect(user_id, ws)
    try:
        # 保持连接，直到客户端断开
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(user_id, ws)


# ── 生命周期 ──────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    """启动时初始化：SDK预加载 + 调度器 + 默认管理员 + 事件总线 + QAAgent"""
    # 预加载 Claude Agent SDK（提前暴露导入/配置问题，避免首次请求才报错）
    from app.services.astra_assistant import check_sdk, settings as astra_settings
    if check_sdk():
        try:
            import claude_agent_sdk  # noqa: F401
            log = logging.getLogger("uvicorn")
            log.info("Claude Agent SDK 已预加载 (v%s)", getattr(claude_agent_sdk, '__version__', 'unknown'))
        except Exception as e:
            log = logging.getLogger("uvicorn")
            log.warning("Claude Agent SDK 预加载失败: %s", e)
    
    await start_scheduler()
    from app.storage.user_store import init_admin_if_empty
    from app.storage.agent_config_store import init_default_agents
    init_admin_if_empty()
    init_default_agents()

    # 初始化OS级智能体核心组件
    from app.core.event_bus import get_event_bus, get_event_registry
    from app.core.worker_registry import get_worker_registry
    from app.core.qa_agent import get_qa_agent

    bus = get_event_bus()
    registry = get_event_registry()
    worker_reg = get_worker_registry()

    qa = get_qa_agent()
    qa.set_registries(registry, worker_reg)

    # 初始化Phase 2组件
    from app.core.manager_agent import get_manager_agent
    from app.core.proactive_engine import get_proactive_engine

    manager = get_manager_agent()
    proactive = get_proactive_engine()
    await proactive.setup_scheduled_tasks()

    # 初始化Phase 3组件
    from app.core.oauth_manager import get_oauth_manager
    from app.core.auto_pull_engine import get_auto_pull_engine
    from app.core.channel_adapter import get_channel_registry
    from app.core.security_sandbox import get_security_sandbox
    from app.core.skill_registry import get_skill_registry, get_skill_executor, get_skill_recommender
    from app.core.plugin_manager import get_plugin_manager, get_code_capability
    # Phase 4 组件
    from app.core.rbac import get_rbac_manager, get_approval_engine, get_operation_guard

    oauth = get_oauth_manager()
    auto_pull = get_auto_pull_engine()
    await auto_pull.start()
    channels = get_channel_registry()
    sandbox = get_security_sandbox()
    skill_reg = get_skill_registry()
    skill_exec = get_skill_executor()
    skill_rec = get_skill_recommender()
    plugin_mgr = get_plugin_manager()
    code_cap = get_code_capability()

    # Phase 4 初始化
    rbac = get_rbac_manager()
    approval = get_approval_engine()
    op_guard = get_operation_guard()


@app.on_event("shutdown")
async def on_shutdown():
    """停止调度器 + 停止自动拉取引擎。"""
    await stop_scheduler()
    from app.core.auto_pull_engine import get_auto_pull_engine
    auto_pull = get_auto_pull_engine()
    await auto_pull.stop()
