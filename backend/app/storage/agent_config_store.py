"""多 Agent 配置存储 — 基于 .md 文件（替代 SQLite）。

所有 Agent 数据源统一为 data/agents/*.md 文件，零硬编码，零 SQLite 依赖。
Agent 类型及默认 system prompt 通过 .md 文件驱动：
  - qa              QA 系统管理 Agent（默认，权限最高功能最全）
  - general         通用合规 Agent（核心，覆盖 NLU + 问答）
  - export_law      出境法律 Agent
  - tax             税务 Agent
  - culture         民俗文化 Agent
  - cert            认证标准 Agent
  - custom_*        用户自定义
"""

import logging
from typing import Optional

from app.storage.agent_md_loader import (
    load_all_agents,
    get_agent as md_get_agent,
    get_agent_by_type as md_get_agent_by_type,
    save_agent_md,
    delete_agent_md,
    get_general_system_prompt as md_get_general_system_prompt,
)

logger = logging.getLogger(__name__)


# ── 前端兼容 — 同名字段映射 ─────────────────────────────────────────────────

def list_agents(enabled_only: bool = False) -> list[dict]:
    """获取 Agent 列表（从 .md 文件）。"""
    agents = load_all_agents()
    if enabled_only:
        agents = [a for a in agents if a.get("enabled")]
    return agents


def get_agent(agent_id: str) -> Optional[dict]:
    """获取单 Agent 配置（从 .md 文件）。"""
    return md_get_agent(agent_id)


def get_agent_by_type(agent_type: str) -> Optional[dict]:
    """按类型获取 Agent。"""
    return md_get_agent_by_type(agent_type)


def upsert_agent(
    name: str,
    agent_type: str,
    description: str,
    system_prompt: str,
    enabled: bool = True,
    sort_order: int = 99,
    agent_id: Optional[str] = None,
    sdk_config: Optional[str] = None,
) -> dict:
    """新建或更新 Agent（写入 .md 文件）。"""
    import json
    import uuid
    import time

    aid = agent_id or f"agent_{uuid.uuid4().hex[:8]}"
    now = int(time.time())
    agent_data = {
        "id": aid,
        "name": name,
        "type": agent_type,
        "description": description,
        "system_prompt": system_prompt,
        "enabled": enabled,
        "sort_order": sort_order,
        "sdk_config": sdk_config or "{}",
        "created_at": now,
        "updated_at": now,
    }

    # 如果是更新已有 Agent，拷贝现有关联配置
    existing = md_get_agent(aid)
    if existing:
        agent_data["tools"] = existing.get("tools", [])
        agent_data["skills"] = existing.get("skills", [])
        agent_data["oauth_connections"] = existing.get("oauth_connections", [])

    save_agent_md(agent_data)

    # 返回完整 row（与旧 API 兼容）
    return agent_data


def delete_agent(agent_id: str) -> bool:
    """删除自定义 Agent（内置 Agent 不可删除）。"""
    # 内置 Agent 保护
    builtin_types = {"qa", "general", "export_law", "tax", "culture", "certification"}
    agent = md_get_agent(agent_id)
    if agent and agent.get("type") in builtin_types:
        logger.warning("Attempted to delete builtin agent: %s", agent_id)
        return False
    return delete_agent_md(agent_id)


def toggle_agent(agent_id: str, enabled: bool) -> bool:
    """启用/禁用 Agent。"""
    agent = md_get_agent(agent_id)
    if not agent:
        return False
    agent["enabled"] = enabled
    save_agent_md(agent)
    return True


def get_general_system_prompt() -> str:
    """获取通用合规 Agent 的 system prompt（用于 NLU 意图解析）。"""
    return md_get_general_system_prompt()


# ── 空初始化（兼容旧启动流程） ───────────────────────────────────────────────

def init_default_agents():
    """空操作 — Agent 配置已由 .md 文件驱动，无需 SQLite 初始化。"""
    logger.info("Agent 配置由 data/agents/*.md 驱动，跳过 SQLite 初始化")
    pass
