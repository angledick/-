"""
Agent 纯文件初始化器 — 从 data/agents/*.md 加载 Agent 定义。

职责：
  1. 启动时扫描 data/agents/ 目录的 .md 文件，加载所有 Agent 定义
  2. 零 SQLite 依赖，零硬编码
  3. 支持热加载（TTL 缓存）
  4. 与 agent_config_store.py 共享 agent_md_loader.py 作为底层数据源

启动流程位置：
  基础设施 (DB/Chroma) → 配置加载器 → 事件预绑定 → Worker 初始化 → Agent 初始化
"""

import logging
from typing import Optional

from app.storage.agent_md_loader import load_all_agents, get_agent, get_agent_by_type

logger = logging.getLogger(__name__)


class AgentInitializer:
    """Agent 文件初始化器"""

    def __init__(self):
        self._initialized = False
        self._agent_count = 0

    def scan_and_load(self) -> int:
        """扫描 data/agents/ 目录，加载所有 Agent 定义。

        Returns:
            加载的 Agent 数量
        """
        agents = load_all_agents(force=True)
        self._agent_count = len(agents)
        self._initialized = True

        for agent in agents:
            agent_type = agent.get("type", "unknown")
            agent_name = agent.get("name", "Untitled")
            enabled = agent.get("enabled", True)
            status = "enabled" if enabled else "disabled"
            logger.info(
                "Agent [%s] %s (%s) — %s",
                agent_type, agent_name, agent.get("id", "?"), status,
            )

        logger.info(
            "Agent 初始化完成: 共加载 %d 个 Agent（来源: data/agents/*.md）",
            self._agent_count,
        )
        return self._agent_count

    def get_agent_count(self) -> int:
        return self._agent_count

    @property
    def initialized(self) -> bool:
        return self._initialized


# ── 单例 ─────────────────────────────────────────────

_agent_initializer: Optional[AgentInitializer] = None


def get_agent_initializer() -> AgentInitializer:
    global _agent_initializer
    if _agent_initializer is None:
        _agent_initializer = AgentInitializer()
    return _agent_initializer
