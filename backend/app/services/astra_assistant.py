"""AstraAssistant — 基于 Claude Agent SDK 的完整封装。

将 Claude Code 的全部能力（CLI 工具、联网搜索、文件操作、多步推理、持久会话、
子代理、钩子、MCP 工具、技能、沙箱）封装为统一的助手级智能体，
并集成持久化记忆系统（L0-L4）。

系统定位:
  - 基于 claude-agent-sdk（Claude Code SDK Python）
  - 助手级智能体，非简单对答
  - 覆盖 SDK 全部功能：会话管理、子代理、钩子、MCP 工具、技能、沙箱、CLI 操作
  - 扩展 SDK 能力：合规 MCP 工具、法规知识库、规则引擎、持久化记忆

使用方式:
    assistant = AstraAssistant()
    # SDK 会话管理（CLI 级功能）
    sessions = await assistant.list_sessions()
    msgs = await assistant.get_session_messages("session-uuid")
    # 多轮对话
    result = await assistant.chat("LED灯出口德国需要什么认证？")
    # 流式对话
    async for event in assistant.chat_stream("介绍欧盟CE认证"):
        ...
    # 子代理
    agents = await assistant.list_subagents()
"""

import asyncio
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Optional, Dict

from app.config import settings
from app.services.prompt_loader import render_prompt

logger = logging.getLogger(__name__)


class AstraAssistantError(Exception):
    """AstraAssistant 调用异常。"""

    def __init__(self, message: str, original: Optional[Exception] = None):
        super().__init__(message)
        self.original = original


# ── 合规助手系统提示词 ─────────────────────────────

ASTRA_SYSTEM_PROMPT = """你是"避风港"跨境合规智能助手，基于 Claude Agent SDK 运行。

## 核心职责
帮助跨境电商卖家分析目标市场的合规要求，涵盖 HS 编码、VAT 税率、产品认证、
风险评估、清关文件、文化适配等。

## 可用工具
你拥有完整的 Claude Code 工具链：
- **Read/Glob/Grep**: 读取和搜索项目文件  
- **WebSearch/WebFetch**: 联网搜索最新法规信息  
- **Bash**: 执行终端命令（数据分析、脚本执行）  
- **Edit/Write**: 编辑和创建文件（生成合规报告文档）  

以及专有的合规检查工具（通过 MCP 注入）：
- **lookup_hs_code**: 根据产品名称查询 HS 编码  
- **lookup_vat_rate**: 查询目标国家的标准 VAT 税率  
- **get_certifications**: 查询产品出口认证要求  
- **get_risk_flags**: 评估合规风险  
- **check_compliance**: 完整合规检查（HS+VAT+认证+风险+物流）  
- **retrieve_regulation_context**: 从法规知识库检索相关条文  
- **get_logistics_requirements**: 物流与清关要求  
- **get_cultural_notes**: 目标市场的文化适配注意事项  

## 工作方式
1. 理解用户需求（产品 + 目标市场）  
2. 使用合规工具获取结构化数据  
3. 必要时联网搜索最新法规动态  
4. 综合分析，给出可执行的合规建议  
5. 支持输出结构化合规报告（Markdown / JSON）  

## 输出风格
- 专业、简洁、有层次  
- 优先使用工具获取准确数据  
- 对不确定信息明确标注需要进一步核实  
- 支持使用子代理处理复杂任务  
"""

# 合规 MCP 工具在 SDK 中的名称格式
_COMPLIANCE_MCP_PREFIX = "mcp__compliance__"
COMPLIANCE_TOOL_NAMES = [
    f"{_COMPLIANCE_MCP_PREFIX}lookup_hs_code",
    f"{_COMPLIANCE_MCP_PREFIX}lookup_vat_rate",
    f"{_COMPLIANCE_MCP_PREFIX}get_certifications",
    f"{_COMPLIANCE_MCP_PREFIX}get_risk_flags",
    f"{_COMPLIANCE_MCP_PREFIX}check_compliance",
    f"{_COMPLIANCE_MCP_PREFIX}retrieve_regulation_context",
    f"{_COMPLIANCE_MCP_PREFIX}get_logistics_requirements",
    f"{_COMPLIANCE_MCP_PREFIX}get_cultural_notes",
]

# Agent关联Tool → MCP Server 工厂映射
# tool_id → (模块导入路径, 工厂函数名)
_AGENT_TOOL_MCP_REGISTRY: dict[str, tuple[str, str]] = {
    "tool_metaso_search": ("app.services.metaso_search", "get_metaso_mcp_server"),
    "tool_compliance_check": ("app.services.astra_tools", "get_compliance_mcp_server"),
    "tool_hs_lookup": ("app.services.astra_tools", "get_compliance_mcp_server"),
    "tool_vat_query": ("app.services.astra_tools", "get_compliance_mcp_server"),
    "tool_regulation_scan": ("app.services.astra_tools", "get_compliance_mcp_server"),
}


# ── SDK 可用性检查 ────────────────────────────────

def check_sdk() -> bool:
    """检查 claude-agent-sdk 是否已安装。"""
    try:
        import claude_agent_sdk  # noqa: F401
        return True
    except ImportError:
        return False


def _ensure_sdk():
    """确保 SDK 可用，否则抛错。"""
    if not check_sdk():
        raise AstraAssistantError(
            "claude-agent-sdk 未安装，请执行: pip install claude-agent-sdk"
        )


def _parse_json_setting(raw: str, default: Any = None) -> Any:
    """解析 JSON 配置项。空字符串返回默认值。"""
    if not raw or not raw.strip():
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("JSON 配置解析失败: %s", raw[:80])
        return default


# ── UUID 验证 ──────────────────────────────────

_UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)


def _is_valid_uuid(value: str) -> bool:
    """检查字符串是否为标准 UUID 格式。"""
    return bool(_UUID_PATTERN.match(value))


# ════════════════════════════════════════════════════════════════
# AstraAssistant — 完整封装
# ════════════════════════════════════════════════════════════════


class AstraAssistant:
    """避风港合规智能助手 — 基于 Claude Agent SDK 的完整封装。

    覆盖 Claude Agent SDK 全部能力:
    - 会话管理：list_sessions / get_session_messages / delete / fork / rename / tag
    - 多轮对话：ClaudeSDKClient + hooks + MCP 工具
    - 子代理：AgentDefinition（可通过配置定义自定义子代理）
    - 钩子系统：PreToolUse / PostToolUse / UserPromptSubmit / SubagentStart/Stop
    - MCP 工具：合规工具 + 自定义
    - 技能：Skills 配置
    - 沙箱：Sandbox 设置
    - 插件：Plugin 加载
    - 权限管理：permission_mode / can_use_tool / allowed_tools
    - CLI 功能：session store / file checkpointing
    - 流式对话：streaming
    - 记忆系统：通过 hooks 注入 L0-L4 上下文
    """

    def __init__(self):
        # 持久化 SDK Client 会话: session_id → ClaudeSDKClient
        self._clients: dict[str, Any] = {}
        # 合规 MCP Server（懒加载单例）
        self._mcp_server: Any = None
        self._mcp_server_ready: bool = False

    # ── SDK 可用性 ─────────────────────────────────

    def _sdk_available(self) -> bool:
        """SDK + API Key 是否均可用。"""
        return bool(
            settings.sdk_enabled
            and check_sdk()
            and settings.anthropic_api_key
        )

    # ── MCP Server ─────────────────────────────────

    def _get_mcp_server(self):
        """获取合规 MCP Server 配置（单例，缓存在实例级）。"""
        if self._mcp_server_ready:
            return self._mcp_server
        if not check_sdk():
            self._mcp_server_ready = True
            self._mcp_server = None
            return None
        try:
            from app.services.astra_tools import get_compliance_mcp_server
            self._mcp_server = get_compliance_mcp_server()
        except ImportError:
            self._mcp_server = None
        self._mcp_server_ready = True
        return self._mcp_server

    # ── ClaudeAgentOptions 构建 ────────────────────

    def _build_tools_config(
        self,
        mcp_server: Any,
        extra_tools: Optional[list[str]] = None,
    ) -> tuple[Any, list[str], list[str]]:
        """构建工具配置: tools_conf / allowed / disallowed"""
        tools_conf: Any = {"type": "preset", "preset": "claude_code"}

        allowed = []
        if settings.sdk_allowed_tools:
            allowed = [t.strip() for t in settings.sdk_allowed_tools.split(",") if t.strip()]
        else:
            allowed = ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebSearch", "WebFetch"]
        if extra_tools:
            allowed.extend(extra_tools)
        if mcp_server:
            allowed.extend(COMPLIANCE_TOOL_NAMES)

        disallowed = []
        if settings.sdk_disallowed_tools:
            disallowed = [t.strip() for t in settings.sdk_disallowed_tools.split(",") if t.strip()]

        return tools_conf, allowed, disallowed

    def _build_session_config(
        self,
        session_id: Optional[str] = None,
    ) -> tuple[Optional[str], Optional[bool], Optional[bool], Optional[bool]]:
        """构建会话参数: session_id / resume / continue / fork"""
        raw_session_id = session_id or settings.sdk_session_id or None
        session_id_val = (
            raw_session_id
            if (raw_session_id and _is_valid_uuid(raw_session_id))
            else None
        )
        resume_val = settings.sdk_resume_session or None
        continue_val = settings.sdk_continue_conversation
        fork_val = settings.sdk_fork_session
        if session_id_val and not fork_val:
            if not resume_val and not continue_val:
                resume_val = True
        return session_id_val, resume_val, continue_val, fork_val

    def _build_mcp_servers(
        self,
        mcp_server: Any,
        agent_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """构建 MCP Server 字典: compliance + qa_agent + Agent关联工具"""
        mcp_servers: dict[str, Any] = {}
        if mcp_server:
            mcp_servers["compliance"] = mcp_server

        # QAAgent 专属：注入系统管理 MCP Server
        if agent_id == "agent_qa":
            try:
                from app.core.qa_tools import get_qa_mcp_server
                qa_mcp = get_qa_mcp_server()
                if qa_mcp:
                    mcp_servers["qa_agent"] = qa_mcp
                    logger.info("QAAgent 系统管理 MCP Server 已注入")
            except Exception as e:
                logger.debug("QAAgent MCP Server 注入失败: %s", e)

        # Agent关联工具 → MCP Server 注入
        if agent_id:
            try:
                import json as _json
                from pathlib import Path as _Path
                _ext_file = _Path(settings.data_dir) / "agents" / "extensions.json"
                if _ext_file.exists():
                    _ext_data = _json.loads(_ext_file.read_text(encoding="utf-8"))
                    _agent_ext = _ext_data.get(agent_id, {})
                    _tool_ids = _agent_ext.get("tool_ids", [])
                    for _tool_id in _tool_ids:
                        if _tool_id in _AGENT_TOOL_MCP_REGISTRY:
                            _mod_path, _factory_name = _AGENT_TOOL_MCP_REGISTRY[_tool_id]
                            import importlib
                            _mod = importlib.import_module(_mod_path)
                            _factory = getattr(_mod, _factory_name)
                            _mcp = _factory()
                            if _mcp:
                                _key = _tool_id.replace("tool_", "")
                                mcp_servers[_key] = _mcp
                                logger.info("Agent关联工具 MCP Server 已注入: %s", _tool_id)
            except Exception as e:
                logger.debug("Agent关联工具 MCP 注入失败: %s", e)

        return mcp_servers

    def build_options(
        self,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        extra_tools: Optional[list[str]] = None,
        extra_env: Optional[dict[str, str]] = None,
        agent_id: Optional[str] = None,
    ) -> Optional[Any]:
        """构建完整的 ClaudeAgentOptions。

        从 settings 中读取 SDK 配置，合并运行时参数，返回 ClaudeAgentOptions 实例。
        返回值可用于 query() 或 ClaudeSDKClient。

        Args:
            session_id: 指定会话 UUID（留空自动生成）
            model: Claude 模型名
            system_prompt: 系统提示词（覆盖默认）
            extra_tools: 额外自动批准的工具
            extra_env: 额外环境变量
            agent_id: 当前使用的 Agent ID（用于注入特定 Agent 的 MCP 工具）

        Returns:
            ClaudeAgentOptions 或 None（SDK 不可用时）
        """
        if not self._sdk_available():
            return None

        from claude_agent_sdk import ClaudeAgentOptions, AgentDefinition

        mcp_server = self._get_mcp_server()

        # ── 工具配置 ─────────────────
        tools_conf, allowed, disallowed = self._build_tools_config(mcp_server, extra_tools)

        # ── 环境变量 ─────────────────
        env = {"ANTHROPIC_API_KEY": settings.anthropic_api_key}
        extra_env_raw = _parse_json_setting(settings.sdk_env_json, {})
        if isinstance(extra_env_raw, dict):
            env.update(extra_env_raw)
        if extra_env:
            env.update(extra_env)

        # ── 会话参数 ─────────────────
        session_id_val, resume_val, continue_val, fork_val = self._build_session_config(session_id)

        # ── 子代理定义 ─────────────────
        agents_val: Optional[dict[str, Any]] = None
        agents_raw = _parse_json_setting(settings.sdk_agents_json, {})
        if isinstance(agents_raw, dict) and agents_raw:
            agents_val = {}
            for name, defn in agents_raw.items():
                if isinstance(defn, dict):
                    agents_val[name] = AgentDefinition(
                        description=defn.get("description", ""),
                        prompt=defn.get("prompt", ""),
                        skills=defn.get("skills"),
                        memory=defn.get("memory"),
                        model=defn.get("model"),
                        maxTurns=defn.get("maxTurns"),
                        effort=defn.get("effort"),
                        background=defn.get("background", False),
                        permissionMode=defn.get("permissionMode"),
                    )

        # ── 技能 ─────────────────
        skills_val: Any = None
        skills_raw = _parse_json_setting(settings.sdk_skills_json, None)
        if skills_raw is not None:
            if isinstance(skills_raw, list):
                skills_val = skills_raw
            elif skills_raw == "all":
                skills_val = "all"

        # ── 沙箱 ─────────────────
        sandbox_val: Any = None
        sandbox_raw = _parse_json_setting(settings.sdk_sandbox_json, None)
        if sandbox_raw is not None and isinstance(sandbox_raw, dict):
            from claude_agent_sdk import SandboxSettings
            sandbox_val = SandboxSettings(
                enabled=sandbox_raw.get("enabled", False),
                autoAllow=sandbox_raw.get("autoAllow"),
            )

        # ── 插件 ─────────────────
        plugins_val: Any = []
        plugins_raw = _parse_json_setting(settings.sdk_plugins_json, [])
        if isinstance(plugins_raw, list):
            from claude_agent_sdk import SdkPluginConfig
            for p in plugins_raw:
                if isinstance(p, dict):
                    plugins_val.append(
                        SdkPluginConfig(
                            type=p.get("type", "local"),
                            path=p.get("path", ""),
                        )
                    )

        # ── 额外 CLI 参数 ─────────────────
        extra_args_val: dict[str, Any] = {}
        extra_args_raw = _parse_json_setting(settings.sdk_extra_args_json, {})
        if isinstance(extra_args_raw, dict):
            extra_args_val.update(extra_args_raw)
        if settings.sdk_enable_file_checkpointing:
            extra_args_val["enable-file-checkpointing"] = None

        # ── 额外目录 ─────────────────
        add_dirs_val: list[Path | str] = []
        add_dirs_raw = _parse_json_setting(settings.sdk_add_dirs_json, [])
        if isinstance(add_dirs_raw, list):
            add_dirs_val = [Path(d) if isinstance(d, str) and ("\\" in d or "/" in d) else d for d in add_dirs_raw]

        # ── 设置源 ─────────────────
        setting_sources_val: Any = None
        setting_sources_raw = _parse_json_setting(settings.sdk_setting_sources_json, None)
        if setting_sources_raw is not None and isinstance(setting_sources_raw, list):
            setting_sources_val = setting_sources_raw

        # ── Beta 功能 ─────────────────
        betas_val: list[str] = []
        betas_raw = _parse_json_setting(settings.sdk_betas_json, [])
        if isinstance(betas_raw, list):
            betas_val = betas_raw

        # ── 模型 ─────────────────
        model_val = model or settings.sdk_model or None
        fallback_val = settings.sdk_fallback_model or None

        # ── System Prompt ─────────────────
        if not system_prompt:
            system_prompt = ASTRA_SYSTEM_PROMPT

        # ── MCP Servers ─────────────────
        mcp_servers = self._build_mcp_servers(mcp_server, agent_id)

        # ── 钩子（整合记忆系统） ─────────────────
        hooks = self._build_memory_hooks()

        # ── Agent 级 SDK 配置覆盖 ─────────────────
        if agent_id and agent_id != "agent_qa":
            try:
                from app.storage.agent_config_store import get_agent
                from app.models.schemas import SDKAgentConfig
                agent_row = get_agent(agent_id)
                if agent_row:
                    raw_sdk = agent_row.get("sdk_config", "{}")
                    if raw_sdk and raw_sdk != "{}":
                        import json
                        data = json.loads(raw_sdk)
                        if isinstance(data, dict):
                            ac = SDKAgentConfig(**data)
                            if ac.model:
                                model_val = ac.model
                            if ac.max_turns is not None:
                                settings.sdk_max_turns = ac.max_turns
                            if ac.permission_mode:
                                settings.sdk_permission_mode = ac.permission_mode
                            if ac.allowed_tools is not None:
                                allowed = ac.allowed_tools
                            if ac.disallowed_tools is not None:
                                disallowed = ac.disallowed_tools
                            if ac.include_hook_events is not None:
                                settings.sdk_include_hook_events = ac.include_hook_events
                            if ac.skills is not None:
                                skills_val = ac.skills if len(ac.skills) > 0 else "all"
                            if ac.agents is not None:
                                from claude_agent_sdk import AgentDefinition
                                agents_val = {}
                                for name, defn in ac.agents.items():
                                    if isinstance(defn, dict):
                                        agents_val[name] = AgentDefinition(
                                            description=defn.get("description", ""),
                                            prompt=defn.get("prompt", ""),
                                            skills=defn.get("skills"),
                                            memory=defn.get("memory"),
                                            model=defn.get("model"),
                                            maxTurns=defn.get("maxTurns"),
                                            effort=defn.get("effort"),
                                            background=defn.get("background", False),
                                            permissionMode=defn.get("permissionMode"),
                                        )
            except Exception as e:
                logger.debug("加载 Agent SDK 配置失败: %s", e)

        # ── 构建 Options ─────────────────
        return ClaudeAgentOptions(
            tools=tools_conf,
            allowed_tools=allowed,
            disallowed_tools=disallowed,
            system_prompt=system_prompt,
            mcp_servers=mcp_servers,
            strict_mcp_config=settings.sdk_strict_mcp_config,
            permission_mode=settings.sdk_permission_mode,
            max_turns=settings.sdk_max_turns if settings.sdk_max_turns > 0 else None,
            max_budget_usd=settings.sdk_max_budget_usd if settings.sdk_max_budget_usd > 0 else None,
            model=model_val,
            fallback_model=fallback_val,
            session_id=session_id_val,
            resume=resume_val,
            continue_conversation=continue_val,
            fork_session=fork_val,
            cwd=settings.sdk_cwd or "./",
            cli_path=settings.sdk_cli_path or None,
            env=env,
            extra_args=extra_args_val or {},
            add_dirs=add_dirs_val if add_dirs_val else None,
            setting_sources=setting_sources_val,
            skills=skills_val,
            agents=agents_val,
            sandbox=sandbox_val,
            plugins=plugins_val,
            betas=betas_val,
            user=settings.sdk_user or None,
            include_hook_events=settings.sdk_include_hook_events,
            hooks=hooks if hooks else None,
        )

    # ── 记忆系统钩子 ───────────────────────────────

    def _build_memory_hooks(self) -> Optional[dict[str, list[Any]]]:
        """构建记忆系统 Hook：在 PreToolUse 注入上下文。

        通过钩子系统将 Astra 的 L0-L4 记忆层注入到 Claude 的工作流中。
        """
        if not check_sdk():
            return None
        from claude_agent_sdk import HookMatcher

        async def _pre_tool_memory_inject(input_data: dict, tool_use_id: str, context: dict) -> dict:
            """在工具调用前注入记忆上下文。"""
            # 从 context 中获取会话信息
            session_id = context.get("session_id", "")
            if not session_id:
                return {}
            try:
                from app.storage.layer_registry import registry
                memory_context = []
                # L4: 会话上下文 —— 最近的对话
                recent_msgs = registry.session.get_recent_messages(
                    context.get("user", "default"), session_id, max_count=3
                )
                if recent_msgs:
                    memory_context.append(
                        "会话上下文（最近消息）:\n"
                        + "\n".join(
                            f"{m['role']}: {m['content'][:200]}"
                            for m in recent_msgs
                        )
                    )
                # L3: 用户偏好
                profile = registry.user.load_profile(context.get("user", "default"))
                if profile:
                    preferred = profile.get("preferred_markets", [])
                    recents = profile.get("recent_searches", [])
                    if preferred:
                        memory_context.append(f"用户关注的市场: {', '.join(preferred)}")
                    if recents:
                        memory_context.append(f"用户最近搜索: {', '.join(recents[:3])}")

                if memory_context:
                    return {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "contextMessages": [
                                {
                                    "role": "system",
                                    "content": "\n---\n".join(memory_context),
                                }
                            ],
                        }
                    }
            except Exception as e:
                logger.debug("记忆注入钩子异常: %s", e)
            return {}

        return {
            "PreToolUse": [
                HookMatcher(matcher="*", hooks=[_pre_tool_memory_inject]),
            ],
        }

    # ── 会话管理（SDK CLI 功能） ────────────────────

    async def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        """列出 SDK 会话列表（对应 CLI /sessions list）。

        返回会话摘要列表，包含 session_id、模型、消息数、上次使用时间等。
        """
        _ensure_sdk()
        from claude_agent_sdk import list_sessions
        return list_sessions(limit=limit)

    async def get_session_info(self, session_id: str) -> Optional[dict[str, Any]]:
        """获取单次会话的详细信息（对应 CLI /sessions info）。"""
        _ensure_sdk()
        from claude_agent_sdk import get_session_info
        return get_session_info(session_id)

    async def get_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        """获取会话消息列表（对应 CLI /sessions messages）。"""
        _ensure_sdk()
        from claude_agent_sdk import get_session_messages
        return get_session_messages(session_id)

    async def delete_session(self, session_id: str) -> bool:
        """删除指定会话（对应 CLI /sessions delete）。"""
        _ensure_sdk()
        from claude_agent_sdk import delete_session
        return delete_session(session_id)

    async def fork_session(self, session_id: str) -> dict[str, Any]:
        """Fork 指定会话为新会话（对应 CLI /sessions fork）。

        返回新会话的信息。
        """
        _ensure_sdk()
        from claude_agent_sdk import fork_session
        result = fork_session(session_id)
        return {"new_session_id": result.new_session_id, "forked_from": session_id}

    async def rename_session(self, session_id: str, name: str) -> bool:
        """重命名会话（对应 CLI /sessions rename）。"""
        _ensure_sdk()
        from claude_agent_sdk import rename_session
        return rename_session(session_id, name)

    async def tag_session(self, session_id: str, tags: list[str]) -> bool:
        """为会话添加标签（对应 CLI /sessions tag）。"""
        _ensure_sdk()
        from claude_agent_sdk import tag_session
        return tag_session(session_id, tags)

    # ── 子代理管理 ────────────────────────────────

    async def list_subagents(self, session_id: Optional[str] = None) -> list[dict[str, Any]]:
        """列出会话中的子代理（对应 CLI /subagents list）。"""
        _ensure_sdk()
        from claude_agent_sdk import list_subagents
        return list_subagents(session_id=session_id)

    async def get_subagent_messages(self, subagent_id: str) -> list[dict[str, Any]]:
        """获取指定子代理的消息（对应 CLI /subagents messages）。"""
        _ensure_sdk()
        from claude_agent_sdk import get_subagent_messages
        return get_subagent_messages(subagent_id)

    # ── 多轮对话 ────────────────────────────────

    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        context: Optional[dict] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """多轮对话 — 使用 Claude Agent SDK 处理用户消息。

        Claude 可使用联网搜索 + CLI 命令 + 多步推理 + 合规工具处理合规查询。
        每个 session_id 对应一个持久化 SDK Client，维持多轮上下文。

        Args:
            message: 用户消息
            session_id: 会话 ID（未提供则自动创建）
            context: 额外上下文（注入系统提示词）
            model: Claude 模型
            system_prompt: 自定义系统提示词
            agent_id: 当前 Agent ID（用于注入专属 MCP 工具）

        Returns:
            dict:
              - "response": Claude 生成的文本回复
              - "structured_result": 结构化输出（如果有）
              - "tools_used": 本次调用的工具名列表
              - "session_id": 当前会话 ID
              - "usage": token 使用统计
        """
        if not self._sdk_available():
            return self._mock_chat_result(message)

        # 确定 session_id
        sid = session_id
        if not sid:
            import uuid
            sid = str(uuid.uuid4())

        # 构造完整 prompt
        system = system_prompt or ASTRA_SYSTEM_PROMPT
        if context:
            extra = render_prompt("chat_compliance", **(context or {}))
            if extra:
                system = f"{system}\n\n{extra}"
        full_prompt = f"{system}\n\n用户消息: {message}"

        return await self._chat_with_session_inner(sid, full_prompt, model, agent_id=agent_id)

    async def chat_with_progress(
        self,
        message: str,
        session_id: Optional[str] = None,
        context: Optional[dict] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        agent_id: Optional[str] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> dict[str, Any]:
        """带进度回调的对话 — 用于飞书消息的流式处理。

        SDK 每产生一条中间消息（工具调用、任务进度），
        通过 on_progress 回调实时通知。
        """
        if not self._sdk_available():
            return self._mock_chat_result(message)

        sid = session_id
        if not sid:
            sid = str(uuid.uuid4())

        system = system_prompt or ASTRA_SYSTEM_PROMPT
        if context:
            extra = render_prompt("chat_compliance", **(context or {}))
            if extra:
                system = f"{system}\n\n{extra}"
        full_prompt = f"{system}\n\n用户消息: {message}"

        return await self._chat_with_session_inner(
            sid, full_prompt, model, agent_id=agent_id, on_progress=on_progress,
        )

    async def chat_stream(
        self,
        message: str,
        session_id: Optional[str] = None,
        context: Optional[dict] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """流式多轮对话 — 逐事件推送。

        事件类型:
        - {"type": "delta", "content": "..."} — 文本片段
        - {"type": "tool_use", "tool_name": "...", "tool_input": {...}} — 工具调用
        - {"type": "tool_result", "tool_name": "...", "result": {...}} — 工具结果
        - {"type": "task_start", "description": "..."} — 任务开始
        - {"type": "task_progress", "description": "..."} — 任务进度
        - {"type": "task_end", "status": "...", "summary": "..."} — 任务结束
        - {"type": "complete", "result": "..."} — 完成
        - {"type": "error", "error": "..."} — 错误
        """
        if not self._sdk_available():
            yield {"type": "complete", "result": self._mock_chat_result(message)["response"]}
            return

        sid = session_id
        if not sid:
            import uuid
            sid = str(uuid.uuid4())

        system = system_prompt or ASTRA_SYSTEM_PROMPT
        if context:
            extra = render_prompt("chat_compliance", **(context or {}))
            if extra:
                system = f"{system}\n\n{extra}"

        # Agent关联了米塔搜索工具时，提示 Claude 使用 metaso_search
        _has_metaso = False
        if agent_id and settings.metaso_api_key:
            try:
                import json as _json
                from pathlib import Path as _Path
                _ext_file_chat = _Path(settings.data_dir) / "agents" / "extensions.json"
                if _ext_file_chat.exists():
                    _ext_data_chat = _json.loads(_ext_file_chat.read_text(encoding="utf-8"))
                    _agent_ext_chat = _ext_data_chat.get(agent_id, {})
                    if "tool_metaso_search" in _agent_ext_chat.get("tool_ids", []):
                        _has_metaso = True
            except Exception:
                pass
        if _has_metaso:
            metaso_hint = (
                "\n\n## 联网搜索说明\n"
                "⚠️ 重要：WebSearch 工具在当前环境下不可用（API限制），请勿使用。\n"
                "如需联网搜索最新信息（如法规更新、市场动态、新闻等），请使用 metaso_search 工具:\n"
                "- metaso_search(q=\"搜索关键词\", count=5)\n"
                "- 参数: q=查询语句, count=返回数量(1-10)\n"
                "- 返回: 标题、链接、摘要的搜索结果列表"
            )
            system = f"{system}{metaso_hint}"

        full_prompt = f"{system}\n\n用户消息: {message}"

        client = self._get_or_create_client(sid, model=model, agent_id=agent_id)
        if client is None:
            yield {"type": "error", "error": "SDK 不可用或会话创建失败"}
            return

        try:
            # 首次使用需要 connect
            if not hasattr(client, '_transport') or client._transport is None:
                await client.connect()
            await client.query(full_prompt)
            async for msg in self._stream_client_messages(client):
                yield msg
        except Exception as e:
            yield {"type": "error", "error": str(e)}

    async def close_session(self, session_id: str) -> None:
        """关闭指定会话，释放 SDK Client 资源。"""
        client = self._clients.pop(session_id, None)
        if client:
            try:
                await client.disconnect()
            except Exception:
                pass
            logger.info("会话 %s 已关闭", session_id)

    async def close_all_sessions(self):
        """关闭所有会话，释放全部资源。"""
        for sid in list(self._clients.keys()):
            await self.close_session(sid)

    # ── 一次性任务（基于 query()） ─────────────────

    async def run_task(
        self,
        prompt_name: str,
        context: Optional[dict] = None,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """执行一次性任务（基于 SDK query()）。

        适合无需持久化会话的后台任务。

        Args:
            prompt_name: prompt 模板名（对应 data/prompts/{name}.yaml）
            context: 模板上下文变量
            model: 使用的模型

        Returns:
            结构化结果
        """
        if not self._sdk_available():
            return self._mock_response(prompt_name)

        task = render_prompt(prompt_name, **(context or {}))
        options = self.build_options(model=model)
        if options is None:
            return self._mock_response(prompt_name)

        # Windows 兼容：在独立的 ProactorEventLoop 线程中运行 SDK
        # uvicorn --reload 模式可能使用 SelectorEventLoop，不支持 subprocess
        def _run_query_sync():
            import subprocess as _sp
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(
                    self._execute_query_in_loop(task, options)
                )
            finally:
                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception:
                    pass
                loop.close()

        try:
            result = await asyncio.to_thread(_run_query_sync)
            return result
        except Exception as e:
            import traceback as _tb
            logger.error("SDK query 失败详情:\n%s", _tb.format_exc())
            raise AstraAssistantError(f"Claude Agent SDK query 失败: {e}") from e

    async def _execute_query_in_loop(
        self,
        task: str,
        options: Any,
    ) -> dict[str, Any]:
        """在新的 ProactorEventLoop 中执行 SDK query。"""
        from claude_agent_sdk import query
        from claude_agent_sdk.types import ResultMessage, AssistantMessage, TextBlock

        logger.info("SDK query 启动: cli_path=%s, model=%s, cwd=%s", options.cli_path, options.model, options.cwd)

        result_text = ""
        async for msg in query(prompt=task, options=options):
            if isinstance(msg, ResultMessage) and msg.result:
                result_text = msg.result or ""
            elif isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        result_text += block.text

        return self._parse_result(result_text, task)

    async def run_task_stream(
        self,
        prompt_name: str,
        context: Optional[dict] = None,
        model: Optional[str] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """流式执行一次性任务。"""
        if not self._sdk_available():
            yield {"type": "complete"}
            return

        task = render_prompt(prompt_name, **(context or {}))
        options = self.build_options(model=model)
        if options is None:
            yield {"type": "complete"}
            return

        from claude_agent_sdk import query
        from claude_agent_sdk.types import (
            ResultMessage, AssistantMessage, TextBlock,
            TaskStartedMessage, TaskProgressMessage, TaskNotificationMessage,
        )

        try:
            async for msg in query(prompt=task, options=options):
                if isinstance(msg, ResultMessage):
                    yield {"type": "complete", "result": msg.result}
                    return
                elif isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            yield {"type": "delta", "content": block.text}
                elif isinstance(msg, TaskStartedMessage):
                    yield {"type": "task_start", "description": msg.description}
                elif isinstance(msg, TaskProgressMessage):
                    yield {"type": "task_progress", "description": msg.description}
                elif isinstance(msg, TaskNotificationMessage):
                    yield {"type": "task_end", "status": msg.status, "summary": msg.summary}
        except Exception as e:
            yield {"type": "error", "error": str(e)}

    # ── Agent 执行 ────────────────────────────────

    async def run_as_agent(
        self,
        agent_id: str,
        message: str,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """以指定 Agent 的身份运行对话。

        从 agent_config_store 加载该 Agent 的 system_prompt，
        替代默认的 ASTRA_SYSTEM_PROMPT 后调用 chat()。

        Args:
            agent_id: Agent 配置 ID（如 "agent_general"）
            message: 用户消息
            session_id: 会话 ID
            model: Claude 模型

        Returns:
            与 chat() 相同格式的响应
        """
        from app.storage.agent_config_store import get_agent
        agent = get_agent(agent_id)
        if not agent:
            raise AstraAssistantError(f"Agent '{agent_id}' 不存在或已禁用")
        system_prompt = agent["system_prompt"]
        logger.info("以 Agent '%s' (%s) 身份执行对话", agent_id, agent.get("name", ""))
        return await self.chat(
            message=message,
            session_id=session_id,
            model=model,
            system_prompt=system_prompt,
            agent_id=agent_id,
        )

    async def run_as_agent_stream(
        self,
        agent_id: str,
        message: str,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """以指定 Agent 的身份运行流式对话。

        用法与 run_as_agent 相同，但返回 SSE 事件流。
        """
        from app.storage.agent_config_store import get_agent
        agent = get_agent(agent_id)
        if not agent:
            raise AstraAssistantError(f"Agent '{agent_id}' 不存在或已禁用")
        system_prompt = agent["system_prompt"]
        logger.info("以 Agent '%s' (%s) 身份执行流式对话", agent_id, agent.get("name", ""))
        async for event in self.chat_stream(
            message=message,
            session_id=session_id,
            model=model,
            system_prompt=system_prompt,
            agent_id=agent_id,
        ):
            yield event

    # ── 内部方法 ─────────────────────────────────

    def _get_or_create_client(
        self, session_id: str, model: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Optional[Any]:
        """获取或创建 SDK Client。"""
        client = self._clients.get(session_id)
        if client is not None:
            return client

        if not self._sdk_available():
            return None

        from claude_agent_sdk import ClaudeSDKClient

        options = self.build_options(session_id=session_id, model=model, agent_id=agent_id)
        if options is None:
            return None

        try:
            client = ClaudeSDKClient(options=options)
            # 不在 __init__ 中 connect；由调用方在 async 上下文中 connect
            self._clients[session_id] = client
            logger.info("创建 SDK 客户端（待连接） %s", session_id)
            return client
        except Exception as e:
            logger.error("创建 SDK 客户端失败 %s: %s", session_id, e)
            return None

    async def _chat_with_session(
        self,
        session_id: str,
        full_prompt: str,
        model: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """通过 ClaudeSDKClient 进行多轮对话。"""
        from claude_agent_sdk.types import (
            ResultMessage, AssistantMessage, TextBlock,
            SystemMessage,
        )

        client = self._get_or_create_client(session_id, model=model, agent_id=agent_id)
        if client is None:
            return self._mock_chat_result(full_prompt[:100])

        try:
            # 首次使用需要 connect
            if not hasattr(client, '_transport') or client._transport is None:
                await client.connect()

            await client.query(full_prompt)

            result_text = ""
            tools_used: list[str] = []
            current_session_id: Optional[str] = None
            usage: Optional[dict] = None

            async for msg in self._stream_client_messages(client):
                if msg["type"] == "text":
                    result_text += msg["content"]
                elif msg["type"] == "tool_use":
                    tools_used.append(msg["tool_name"])
                elif msg["type"] == "system_init":
                    current_session_id = msg.get("session_id", session_id)
                elif msg["type"] == "usage":
                    usage = msg.get("data")

            return {
                "response": result_text,
                "structured_result": None,
                "tools_used": tools_used,
                "session_id": current_session_id or session_id,
                "usage": usage,
            }

        except Exception as e:
            await self.close_session(session_id)
            raise AstraAssistantError(f"Claude 对话失败: {e}") from e

    async def _chat_with_session_inner(
        self,
        session_id: str,
        full_prompt: str,
        model: Optional[str] = None,
        agent_id: Optional[str] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> dict[str, Any]:
        """带进度回调的内部对话方法。

        直接消费 receive_response() 流，每收到一条消息就通过 on_progress 回调。
        在 ProactorEventLoop 中运行（Windows 兼容）。
        """
        from claude_agent_sdk.types import (
            ResultMessage, AssistantMessage, TextBlock,
            ToolUseBlock, ToolResultBlock, ThinkingBlock,
        )

        client = self._get_or_create_client(session_id, model=model, agent_id=agent_id)
        if client is None:
            return self._mock_chat_result(full_prompt[:100])

        # 在 ProactorEventLoop 中运行 SDK
        def _run_sync():
            import subprocess as _sp
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(
                    self._run_sdk_in_loop(client, full_prompt, on_progress)
                )
            finally:
                # 先断开 client 连接，停止 SDK 子进程传输层
                try:
                    if hasattr(client, 'disconnect'):
                        loop.run_until_complete(client.disconnect())
                except Exception:
                    pass
                # 静默关闭异步生成器（SDK 内部 SubprocessCLITransport._read_messages_impl
                # 可能在子进程未完全退出时仍处于 running 状态，导致 aclose 报 RuntimeError。
                # 这是 Windows + Claude Agent SDK 已知问题，不影响实际结果。）
                import logging as _logging
                _asyncio_logger = _logging.getLogger('asyncio')
                _old_level = _asyncio_logger.level
                _asyncio_logger.setLevel(_logging.CRITICAL)
                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception:
                    pass
                finally:
                    _asyncio_logger.setLevel(_old_level)
                loop.close()

        try:
            result = await asyncio.to_thread(_run_sync)
            return result
        except Exception as e:
            await self.close_session(session_id)
            raise AstraAssistantError(f"SDK 执行失败: {e}") from e

    async def _run_sdk_in_loop(
        self,
        client: Any,
        full_prompt: str,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> dict[str, Any]:
        """在事件循环中运行 SDK 并收集结果。"""
        from claude_agent_sdk.types import (
            ResultMessage, AssistantMessage, TextBlock,
            ToolUseBlock, ToolResultBlock,
        )

        if not hasattr(client, '_transport') or client._transport is None:
            await client.connect()

        await client.query(full_prompt)

        result_text = ""
        tools_used: list[str] = []
        usage: Optional[dict] = None
        last_tool_result: str = ""

        # 安全消费 receive_response 流
        # Windows 下 aclose 可能抛 RuntimeError，需要捕获
        gen = client.receive_response()
        try:
            async for msg in gen:
                if isinstance(msg, ResultMessage):
                    usage = {
                        "cost_usd": getattr(msg, "total_cost_usd", None),
                        "input_tokens": getattr(msg, "input_tokens", None),
                        "output_tokens": getattr(msg, "output_tokens", None),
                    }
                    continue

                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            text = block.text or ""
                            result_text += text
                            if on_progress and text.strip():
                                on_progress(text)
                        elif isinstance(block, ToolUseBlock):
                            tool_name = block.name or ""
                            tools_used.append(tool_name)
                            if on_progress:
                                progress_text = self._format_tool_progress(block)
                                on_progress(progress_text)
                        elif isinstance(block, ToolResultBlock):
                            content = self._format_tool_result(block)
                            if content:
                                last_tool_result = content
                                if on_progress:
                                    on_progress(f"📋 {content[:300]}")
        except RuntimeError as e:
            if "aclose" in str(e) or "already running" in str(e):
                logger.debug("SDK receive_response 关闭异常 (Windows 已知问题，已忽略): %s", e)
            else:
                raise
        finally:
            # 尝试安全关闭生成器
            try:
                await gen.aclose()
            except Exception:
                pass

        # 兜底：SDK 无 TextBlock 时用最后一条工具结果
        if not result_text and last_tool_result:
            result_text = last_tool_result

        return {
            "response": result_text,
            "structured_result": None,
            "tools_used": tools_used,
            "session_id": None,
            "usage": usage,
        }

    @staticmethod
    def _format_tool_progress(block) -> str:
        """将工具调用格式化为可读的进度消息。"""
        name = getattr(block, 'name', '') or ''
        inp = getattr(block, 'input', {}) or {}

        if name == 'Bash':
            desc = inp.get('description', '') or inp.get('command', '')
            if desc:
                return f"🔧 执行: {desc}"
            return f"🔧 执行命令"
        elif name in ('Read', 'Write', 'Edit'):
            path = inp.get('file_path', '') or inp.get('path', '')
            if path:
                return f"🔧 {name}: {path}"
            return f"🔧 {name}"
        elif name == 'Glob':
            pattern = inp.get('pattern', '') or inp.get('query', '')
            return f"🔧 Glob: {pattern}"
        elif name in ('WebSearch', 'WebFetch'):
            query = inp.get('query', '') or inp.get('url', '')
            return f"🔧 {name}: {query}"
        elif name == 'Grep':
            return f"🔧 搜索: {inp.get('pattern', '')}"
        else:
            return f"🔧 {name}"

    @staticmethod
    def _format_tool_result(block) -> str:
        """将工具结果格式化为可读文本。"""
        content = getattr(block, 'content', None)
        if content is None:
            return ""
        if isinstance(content, str):
            if content in ("tool ran successfully", "Tool ran successfully"):
                return ""
            return content[:300]
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    if item not in ("tool ran successfully",):
                        parts.append(item[:200])
                elif isinstance(item, dict):
                    text = item.get('text', '')
                    if text:
                        parts.append(text[:200])
            return " | ".join(parts)[:300]
        return str(content)[:300]

    async def _stream_client_messages(
        self, client: Any
    ) -> AsyncIterator[dict[str, Any]]:
        """将 ClaudeSDKClient 消息流转换为统一事件格式。"""
        from claude_agent_sdk.types import (
            ResultMessage, AssistantMessage, TextBlock,
            SystemMessage, UserMessage, ToolUseBlock,
            TaskStartedMessage, TaskProgressMessage, TaskNotificationMessage,
            ToolResultBlock, ThinkingBlock, Message,
        )

        # 安全消费 receive_response，捕获 Windows aclose 异常
        gen = client.receive_response()
        try:
            async for msg in gen:
                if isinstance(msg, ResultMessage):
                    yield {"type": "usage", "data": {
                        "cost_usd": getattr(msg, "total_cost_usd", None),
                        "input_tokens": getattr(msg, "input_tokens", None),
                        "output_tokens": getattr(msg, "output_tokens", None),
                    }}
                    return

                elif isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            yield {"type": "text", "content": block.text}
                        elif isinstance(block, ToolUseBlock):
                            yield {
                                "type": "tool_use",
                                "tool_name": block.name,
                                "tool_input": block.input,
                            }
                        elif isinstance(block, ToolResultBlock):
                            yield {
                                "type": "tool_result",
                                "tool_name": getattr(block, "tool_use_id", ""),
                                "content": block.content if hasattr(block, "content") else None,
                            }
                        elif isinstance(block, ThinkingBlock):
                            yield {"type": "thinking", "content": block.thinking}

                elif isinstance(msg, SystemMessage):
                    subtype = getattr(msg, "subtype", None) or getattr(msg, "type", "")
                    if subtype == "init":
                        data = getattr(msg, "data", {}) or {}
                        yield {
                            "type": "system_init",
                            "session_id": data.get("session_id", ""),
                        }

                elif isinstance(msg, TaskStartedMessage):
                    yield {"type": "task_start", "description": getattr(msg, "description", "")}
                elif isinstance(msg, TaskProgressMessage):
                    yield {"type": "task_progress", "description": getattr(msg, "description", "")}
                elif isinstance(msg, TaskNotificationMessage):
                    yield {
                        "type": "task_end",
                        "status": getattr(msg, "status", ""),
                        "summary": getattr(msg, "summary", ""),
                    }
        except RuntimeError as e:
            if "aclose" in str(e) or "already running" in str(e):
                logger.debug("SDK stream 关闭异常 (Windows 已知问题): %s", e)
            else:
                raise
        finally:
            try:
                await gen.aclose()
            except Exception:
                pass

    # ── 工具方法 ────────────────────────────────

    def _parse_result(self, raw: str, task: str = "") -> dict:
        """解析 Claude 返回的文本，尝试提取 JSON。"""
        text = raw.strip() if raw else ""
        if not text:
            return {"raw_text": "", "task": task[:100]}

        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.startswith("json"):
                text = text[4:].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        import re
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return {"raw_text": text, "task": task[:100]}

    def _mock_response(self, prompt_name: str = "") -> dict:
        """SDK 不可用时的 mock 响应。"""
        return {
            "mock": True,
            "prompt_name": prompt_name,
            "message": (
                f"AstraAssistant disabled (sdk_enabled={settings.sdk_enabled}, "
                f"api_key={'set' if settings.anthropic_api_key else 'not set'}). "
                f"Would run prompt '{prompt_name}'."
            ),
        }

    def _mock_chat_result(self, user_message: str) -> dict:
        """SDK 不可用时的 mock 对话响应。"""
        return {
            "response": (
                f"📋 合规查询分析\n\n"
                f"已收到您的查询: **{user_message}**\n\n"
                f"> *Claude Agent SDK 未启用，使用降级处理。*\n"
                f"> 配置 ANTHROPIC_API_KEY 后，本系统将使用 Claude Code 的全部能力：\n"
                f"> - 联网搜索最新法规\n"
                f"> - 多步推理与合规分析\n"
                f"> - 自定义合规工具链\n"
                f"> - 文件操作与报告生成\n"
                f"> - 子代理并行处理\n"
                f"> - 持久化会话与记忆"
            ),
            "structured_result": None,
            "tools_used": [],
            "session_id": None,
        }
