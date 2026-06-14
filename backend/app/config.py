from typing import Any, Optional

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    # App
    app_name: str = "避风港"
    debug: bool = True

    # ════════════════════════════════════════════════════════════
    # Claude Agent SDK — 完整配置项
    # ════════════════════════════════════════════════════════════

    sdk_enabled: bool = True
    """是否启用 Claude Agent SDK。关闭后降级为本地规则引擎 + RAG。"""

    # ── API Key ────────────────────────────────────────────────
    anthropic_api_key: str = ""
    """Claude API Key（claude-agent-sdk 认证用）。"""

    # ── 会话与模型 ────────────────────────────────────────────
    sdk_session_id: str = ""
    """指定会话 ID（UUID），留空自动生成。"""
    sdk_resume_session: str = ""
    """要恢复的会话 ID（对应 /resume CLI 参数）。"""
    sdk_continue_conversation: bool = True
    """继续当前目录的最近对话（默认开启以复用历史上下文）。"""
    sdk_fork_session: bool = False
    """恢复时 fork 为新会话（不修改原会话）。"""

    sdk_model: str = ""
    """Claude 模型（如 claude-sonnet-4-5, claude-opus-4-5），空则用 CLI 默认。"""
    sdk_fallback_model: str = ""
    """主模型不可用时的备用模型。"""

    sdk_max_turns: int = 10
    """最大对话轮次（10=默认，0=无限制）。"""
    sdk_max_budget_usd: float = 0.0
    """最大美元预算（0=无限制）。"""

    # ── 工具与权限 ────────────────────────────────────────────
    sdk_allowed_tools: str = ""
    """自动批准的工具有列表，逗号分隔（如 Read,Write,Bash,Edit,Glob,Grep,WebSearch,WebFetch）。"""
    sdk_disallowed_tools: str = ""
    """禁止使用的工具列表，逗号分隔。"""
    sdk_permission_mode: str = "default"
    """
    权限模式：
    - default: 标准模式，危险操作弹窗（推荐）
    - acceptEdits: 自动接受文件编辑
    - bypassPermissions: 绕过全部权限检查
    - plan: 计划模式，不执行工具
    - dontAsk: 不弹窗，未预批准的拒绝
    - auto: 模型自动判断
    """

    # ── MCP 服务器 ────────────────────────────────────────────
    sdk_strict_mcp_config: bool = False
    """仅使用通过 SDK 传递的 MCP 服务器，忽略项目/全局 MCP 配置。"""

    # ── 钩子 ──────────────────────────────────────────────────
    sdk_include_hook_events: bool = True
    """在消息流中包含钩子生命周期事件（默认开启以支持事件追溯）。"""

    # ── 子代理 ────────────────────────────────────────────────
    sdk_agents_json: str = ""
    """
    子代理定义的 JSON 字符串。格式:
    {
      "agent_name": {
        "description": "代理描述",
        "prompt": "代理系统提示词",
        "skills": ["skill_name"],
        "memory": "project",
        "model": "claude-sonnet-4-5",
        "maxTurns": 20,
        "effort": "high",
        "background": false
      }
    }
    """

    # ── 技能 ──────────────────────────────────────────────────
    sdk_skills_json: str = ""
    """启用的技能列表 JSON（如 ["skill_a", "skill_b"] 或 "all"）。"""

    # ── 沙箱 ──────────────────────────────────────────────────
    sdk_sandbox_json: str = ""
    """沙箱设置 JSON。"""

    # ── 插件 ──────────────────────────────────────────────────
    sdk_plugins_json: str = ""
    """本地插件列表 JSON。"""

    # ── 额外 CLI 参数 ────────────────────────────────────────
    sdk_extra_args_json: str = ""
    """额外 CLI 参数的 JSON 对象。"""
    sdk_add_dirs_json: str = ""
    """Claude 可访问的额外目录 JSON 数组。"""

    # ── 环境变量 ──────────────────────────────────────────────
    sdk_env_json: str = ""
    """传递给 Claude Code 子进程的环境变量 JSON。"""

    # ── 高级 ──────────────────────────────────────────────────
    sdk_cli_path: str = "."
    """Claude Code CLI 可执行文件路径。默认为工程根目录以支持事件追溯。"""
    sdk_setting_sources_json: str = ""
    """设置加载源 JSON 数组（如 ["user", "project", "local"]）。"""
    sdk_betas_json: str = ""
    """Beta 功能 JSON 数组（如 ["context-1m-2025-08-07"]）。"""
    sdk_enable_file_checkpointing: bool = False
    """启用文件检查点追踪（用于 rewind 功能）。"""
    sdk_user: str = ""
    """关联的用户标识符。"""


    # ── 米塔AI搜索 ────────────────────────────────────────────
    metaso_api_key: str = ""
    """米塔AI搜索 API Key（用于联网搜索替代 WebSearch）。"""
    metaso_api_url: str = "https://metaso.cn/api/v1/search"
    """米塔AI搜索 API URL。"""

    # ── 工作目录 ──────────────────────────────────────────────
    sdk_cwd: str = "./"
    """Claude Code 工作目录（默认 ./）。"""

    # Database
    database_url: str = "postgresql+asyncpg://astra:astra@localhost:5432/astra"

    # Chroma
    chroma_persist_dir: str = "./data/chroma"

    # Cloud Embedding（OpenAI 兼容接口，用于知识库向量化）
    embedding_api_key: str = ""
    """云端 Embedding API Key（为空时回退 anthropic_api_key）。"""
    embedding_base_url: str = "https://api.openai.com/v1"
    """云端 Embedding API Base URL。"""
    embedding_model: str = "text-embedding-3-small"
    """云端 Embedding 模型名。"""

    # Knowledge
    data_dir: str = "./data"

    # Prompts (YAML 模板目录)
    prompt_dir: str = "./data/prompts"

    # Skills 目录
    skills_dir: str = "./data/skills"

    # Scheduler
    scheduler_enabled: bool = True
    market_poll_interval_minutes: int = 60

    # Shopify
    shopify_client_id: str = ""
    shopify_client_secret: str = ""
    shopify_domain: str = ""                    # 店铺域名，如 my-store.myshopify.com
    shopify_redirect_uri: str = "http://localhost:8000/api/v1/shopify/callback"
    shopify_scopes: str = "read_products,write_products"
    shopify_api_version: str = "2026-07"
    shopify_webhook_api_version: str = "2026-04"
    shopify_app_url: str = ""
    shopify_embedded: bool = False

    # Feishu / Lark
    feishu_app_id: str = ""
    feishu_app_secret: str = ""

    # 风险情报飞书通知
    risk_intel_feishu_chat_id: str = ""         # 严重/高危情报推送群 ID

    # Risk Alerts storage
    risk_alert_dir: str = "./data/risk_alerts"

    # ── JWT 认证 ──────────────────────────────────────────────
    jwt_secret: str = "astra-change-me-in-production-2024"
    jwt_expire_hours: int = 24



settings = Settings()

# ── 将 sdk_env_json 注入 os.environ ────────────────
# claude_agent_sdk 部分代码通过 os.environ 读取环境变量
# 此处注入确保 SDK 无论在 server 还是独立脚本中都能获取正确配置
import os
import json
if settings.sdk_env_json:
    try:
        _env_overrides = json.loads(settings.sdk_env_json)
        if isinstance(_env_overrides, dict):
            for _k, _v in _env_overrides.items():
                os.environ.setdefault(_k, str(_v))
    except (json.JSONDecodeError, TypeError):
        pass