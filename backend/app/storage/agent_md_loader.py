"""
Agent .md 文件加载器 — 从 data/agents/*.md 读取 Agent 配置。

替代 agent_config_store.py 中的 SQLite + DEFAULT_AGENTS 硬编码方案。
所有 Agent 数据源统一为 .md 文件，零硬编码，零 SQLite 依赖。
"""

import os
import re
import json
import time
import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

AGENTS_DIR = Path(__file__).parent.parent / "data" / "agents"


# ── .md 解析 ──────────────────────────────────────────────────────────────────

def parse_agent_md(file_path: Path) -> Optional[dict]:
    """解析单个 Agent .md 文件，返回 agent 配置字典。

    格式:
        ---
        (YAML front-matter)
        ---
        (system_prompt body)
    """
    if not file_path.exists():
        logger.warning("Agent .md not found: %s", file_path)
        return None

    content = file_path.read_text(encoding="utf-8")

    # 解析 front-matter
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not match:
        logger.warning("Invalid Agent .md format (no front-matter): %s", file_path)
        return None

    try:
        front_matter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        logger.warning("Failed to parse YAML front-matter in %s: %s", file_path, e)
        return None

    if not front_matter or not front_matter.get("name"):
        logger.warning("Agent .md missing required 'name' field: %s", file_path)
        return None

    system_prompt = match.group(2).strip()
    agent_id = f"agent_{front_matter.get('type', 'custom')}"
    now = int(time.time())

    return {
        "id": agent_id,
        "name": front_matter["name"],
        "type": front_matter.get("type", "custom"),
        "description": front_matter.get("description", ""),
        "system_prompt": system_prompt,
        "enabled": front_matter.get("enabled", True),
        "sort_order": front_matter.get("sort_order", 99),
        "sdk_config": json.dumps(front_matter.get("sdk_config", {"enabled": True})),
        "tools": front_matter.get("tools", []),
        "skills": front_matter.get("skills", []),
        "oauth_connections": front_matter.get("oauth_connections", []),
        "created_at": now,
        "updated_at": now,
    }


# ── 加载器 ────────────────────────────────────────────────────────────────────

_agent_cache: dict[str, dict] = {}
_cache_timestamp: float = 0
_CACHE_TTL = 5.0  # 秒


def _scan_agents() -> dict[str, dict]:
    """扫描 data/agents/ 目录，返回 {agent_id: agent_dict}。

    跳过 _template.md，只加载 .md 文件。
    """
    agents = {}
    if not AGENTS_DIR.exists():
        logger.warning("Agent directory not found: %s", AGENTS_DIR)
        return agents

    for f in sorted(AGENTS_DIR.glob("*.md")):
        if f.name.startswith("_"):
            continue  # 跳过模板
        agent = parse_agent_md(f)
        if agent:
            agents[agent["id"]] = agent
            logger.debug("Loaded agent: %s (%s)", agent["id"], f.name)

    return agents


def _ensure_cache(force: bool = False):
    """确保缓存已加载。"""
    global _agent_cache, _cache_timestamp
    now = time.time()
    if force or not _agent_cache or (now - _cache_timestamp > _CACHE_TTL):
        _agent_cache = _scan_agents()
        _cache_timestamp = now


def load_all_agents(force: bool = False) -> list[dict]:
    """加载所有 Agent 配置。"""
    _ensure_cache(force)
    return list(_agent_cache.values())


def get_agent(agent_id: str) -> Optional[dict]:
    """获取单个 Agent 配置。"""
    _ensure_cache()
    return _agent_cache.get(agent_id)


def get_agent_by_type(agent_type: str) -> Optional[dict]:
    """按类型获取 Agent。"""
    _ensure_cache()
    for a in _agent_cache.values():
        if a["type"] == agent_type and a["enabled"]:
            return a
    return None


# ── 写入支持（CRUD API 使用） ────────────────────────────────────────────────

def save_agent_md(agent_data: dict) -> Path:
    """将 Agent 配置写入 .md 文件。

    用于 CRUD API 的新建/更新操作。
    """
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    agent_type = agent_data.get("type", "custom")
    agent_name = agent_data.get("name", "Untitled")
    file_name = f"{agent_type}.md" if agent_type != "custom" else f"custom_{agent_data.get('id', 'unknown')[:8]}.md"
    file_path = AGENTS_DIR / file_name

    # 避免覆盖内置 Agent
    if file_path.exists() and file_name not in (f.name for f in AGENTS_DIR.glob("*.md") if not f.name.startswith("_")):
        # 自定义 Agent，用 id 命名
        file_path = AGENTS_DIR / f"custom_{agent_data.get('id', 'unknown')[:8]}.md"

    front_matter = {
        "name": agent_name,
        "type": agent_type,
        "enabled": agent_data.get("enabled", True),
        "sort_order": agent_data.get("sort_order", 99),
        "sdk_config": json.loads(agent_data.get("sdk_config", "{}")) if isinstance(agent_data.get("sdk_config"), str) else agent_data.get("sdk_config", {"enabled": True}),
        "skills": agent_data.get("skills", []),
        "tools": agent_data.get("tools", []),
        "oauth_connections": agent_data.get("oauth_connections", []),
    }

    system_prompt = agent_data.get("system_prompt", "")
    yaml_str = yaml.dump(front_matter, allow_unicode=True, default_flow_style=False, sort_keys=False)

    content = f"---\n{yaml_str}---\n\n{system_prompt}\n"
    file_path.write_text(content, encoding="utf-8")

    # 清除缓存
    global _cache_timestamp
    _cache_timestamp = 0

    logger.info("Saved agent .md: %s", file_path)
    return file_path


def delete_agent_md(agent_id: str) -> bool:
    """删除自定义 Agent 的 .md 文件。"""
    load_all_agents(force=True)
    agent = _agent_cache.get(agent_id)
    if not agent:
        return False

    agent_type = agent.get("type", "custom")
    file_name = f"{agent_type}.md"
    file_path = AGENTS_DIR / file_name

    if file_path.exists():
        file_path.unlink()
        logger.info("Deleted agent .md: %s", file_path)
        global _cache_timestamp
        _cache_timestamp = 0
        return True
    return False


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def get_general_system_prompt() -> str:
    """获取通用合规 Agent 的 system_prompt（用于 NLU 意图解析）。"""
    agent = get_agent_by_type("general")
    if agent:
        return agent["system_prompt"]
    return (
        "你是一个出口合规意图解析器。分析用户消息，提取结构化信息。\n\n"
        '返回严格JSON:\n{\n  "product": "产品中文名称",\n'
        '  "target_country": "目标出口国家中文名",\n'
        '  "action": "export_check | cert_query | tax_query | general",\n'
        '  "confidence": 0.0~1.0\n}'
    )
