from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
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
from app.api import chains, shopify, risk, sessions, auth as auth_router, users, agent_config as agent_config_router, agent_crud as agent_crud_router, agent_extensions as agent_extensions_router, sdk_sessions
# OS级智能体新增路由
from app.api import products, events, pipeline, notifications, cli, rag, event_config, worker_config
# Phase 2 新增路由
from app.api import memory, metrics, tools, chat_stream, agent_tasks, proactive
# Phase 3 新增路由
from app.api import skills, plugins, integrations, oauth, channels, sync, code_security, model_config as model_config_router
# Phase 3.5 新增路由（知识库）
from app.api import knowledge
# Phase 3.6 新增路由（RAG知识导入 + 新闻监控）
from app.api import knowledge_import, news_monitor
# Phase 4 新增路由（后台管理）
from app.api import admin_rbac, admin_approvals, admin_config as admin_config_router, admin_reports

# 定时任务管理
from app.api import scheduler_config

from app.core.scheduler import start_scheduler, stop_scheduler
from app.services.ws_manager import ws_manager
from app.services.astra_assistant import AstraAssistant


# ── 生命周期 ──────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化：配置加载器 → 事件预绑定 → Worker → Agent → SDK/组件"""
    _log = logging.getLogger("uvicorn")

    # ── 1. 基础设施 ────────────────────────────
    _log.info("[启动] Phase 1: 基础设施初始化")
    from app.storage.user_store import init_admin_if_empty
    init_admin_if_empty()

    # ── 2. 配置文件加载器 ────────────────────────
    _log.info("[启动] Phase 2: 配置加载器 (文件系统)")
    _log.info("  Agent 配置: data/agents/*.md")
    _log.info("  Skills 配置: data/skills/_registry.yaml")
    _log.info("  Tools 配置: data/tools/_registry.yaml")
    _log.info("  Events 配置: data/events/builtin/*.md")
    _log.info("  Workers 配置: data/workers/builtin/builtin_workers.md")
    _log.info("  Scheduler 绑定: data/scheduler/bindings.yaml")
    _log.info("  Stages 参考: data/stages/*.yaml (文档参考，事件定义由 events/builtin/*.md 驱动)")
    _log.info("  OAuth Provider 配置: data/oauth/providers.yaml")
    _log.info("  Model 路由配置: data/models/routes.yaml")

    # ── 3. 事件-配置预绑定 ────────────────────────
    _log.info("[启动] Phase 3: 事件-配置预绑定")
    from app.core.event_bus import get_event_bus, get_event_registry
    from app.core.worker_registry import get_worker_registry
    registry = get_event_registry()
    worker_reg = get_worker_registry()
    _log.info("  事件注册表: %d 个事件定义", len(registry.get_all_events()))
    _log.info("  Worker 注册表: %d 个 Worker", len(worker_reg.get_all_workers()))

    # ── 4. Agent 初始化 ──────────────────────────
    _log.info("[启动] Phase 4: Agent 初始化 (文件驱动)")
    from app.core.agent_initializer import get_agent_initializer
    from app.storage.agent_config_store import init_default_agents
    agent_init = get_agent_initializer()
    agent_count = agent_init.scan_and_load()
    init_default_agents()  # 空操作（兼容旧流程）
    _log.info("  Agent 初始化完成: %d 个 Agent", agent_count)

    # ── 5. 预加载 Claude Agent SDK ────────────────
    from app.services.astra_assistant import check_sdk, settings as astra_settings
    if check_sdk():
        try:
            import claude_agent_sdk  # noqa: F401
            _log.info("Claude Agent SDK 已预加载 (v%s)", getattr(claude_agent_sdk, '__version__', 'unknown'))
        except Exception as e:
            _log.warning("Claude Agent SDK 预加载失败: %s", e)

    # ── 6. 核心组件初始化 ──────────────────────────
    from app.core.qa_agent import get_qa_agent
    qa = get_qa_agent()
    qa.set_registries(registry, worker_reg)

    # ── 7. Phase 2 组件 ─────────────────────────
    from app.core.manager_agent import get_manager_agent
    from app.core.proactive_engine import get_proactive_engine
    manager = get_manager_agent()
    proactive = get_proactive_engine()

    # 绑定 ManagerAgent 到事件总线（全局监听，事件驱动调度）
    bus = get_event_bus()
    bus.on_all(manager.on_event)
    _log.info("  ManagerAgent 已绑定到事件总线 (on_all)")

    # ── 8. Phase 3 组件 ─────────────────────────
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

    # ── 9. 调度器（最后启动） ──────────────────────
    await start_scheduler()

    _log.info("=" * 50)
    _log.info("[启动完成] 避风港 OS级合规智能体 v4.0.0")
    _log.info("=" * 50)

    yield  # ── 应用运行中 ──

    # ── 关闭清理 ──────────────────────────────────
    await stop_scheduler()
    from app.core.auto_pull_engine import get_auto_pull_engine
    auto_pull = get_auto_pull_engine()
    await auto_pull.stop()
    # 关闭 session_store 全局 SQLite 连接
    from app.storage.session_store import close_conn
    close_conn()


app = FastAPI(
    title="避风港 — OS级合规智能体",
    description="事件驱动 + 多Agent + 记忆树 + TokenJuice + QAAgent | 跨境合规全生命周期管理",
    version="4.0.0",
    lifespan=lifespan,
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
app.include_router(agent_config_router.router)       # exec (chat)
app.include_router(agent_crud_router.router)          # CRUD
app.include_router(agent_extensions_router.router)     # extensions (skills/tools/oauth)
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
app.include_router(chat_stream.router)
app.include_router(agent_tasks.router)
app.include_router(proactive.router)

# ── Phase 3 新增路由注册 ─────────────────────────
app.include_router(skills.router)
app.include_router(plugins.router)
app.include_router(integrations.router)
app.include_router(oauth.router)
app.include_router(channels.router)
app.include_router(sync.router)
app.include_router(code_security.code_router)
app.include_router(code_security.security_router)

# ── Phase 3.5 知识库路由 ──────────────────────
app.include_router(knowledge.router)

# ── Phase 3.6 RAG知识导入 + 新闻监控 ──────────────
app.include_router(knowledge_import.router)
app.include_router(news_monitor.router)

# ── 定时任务管理路由 ────────────────────────────
app.include_router(scheduler_config.router)

# ── 模型配置路由 ────────────────────────────────
app.include_router(model_config_router.router)

# ── Phase 4 新增路由注册 ─────────────────────────
app.include_router(admin_rbac.router)
app.include_router(admin_approvals.router)
app.include_router(admin_config_router.router)
app.include_router(admin_reports.router)


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
    推送消息格式: { type: str, payload: {...} }

    已支持消息类型:
      session_update  → 会话列表变更（创建/删除），前端 invalidate queries
      new_message     → 新 AI 回复消息，前端追加到会话
      alert           → 风险预警通知
      scan_update     → 扫描进度更新
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


# ── 生命周期（已迁移到 lifespan）──────────────────────────
