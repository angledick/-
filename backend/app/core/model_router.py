"""
模型路由器 (ModelRouter) — 根据任务类型自动选择最优模型。

职责：
  1. 任务分类: reasoning / fast / vision / embedding
  2. 模型选择: 根据任务类型和成本预算选择模型
  3. 负载均衡: 在同类模型间分发请求
  4. 降级策略: 主模型不可用时自动降级
  5. Token预算: 跟踪Token使用量

配置驱动:
  - data/config/model_routes.json — 模型路由配置
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from app.config import settings
from app.models.schemas import ModelConfig, ModelRouteRequest

DATA_DIR = Path(settings.data_dir)
CONFIG_FILE = DATA_DIR / "config" / "model_routes.json"


class ModelRouter:
    """模型路由器

    用法:
        router = ModelRouter()

        # 获取推理模型
        model = router.route("reasoning")
        print(model.model, model.provider)

        # 获取快速模型
        model = router.route("fast")

        # 获取视觉模型
        model = router.route("vision")

        # Token使用统计
        stats = router.get_usage_stats()
    """

    def __init__(self):
        self._routes: Dict[str, ModelConfig] = {}
        self._fallback_chain: Dict[str, List[str]] = {}
        self._usage_stats: Dict[str, int] = {}  # model -> token_count
        self._load_config()

    def _load_config(self):
        """加载模型路由配置"""
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                for role, config in data.get("routes", {}).items():
                    self._routes[role] = ModelConfig(**config)
                self._fallback_chain = data.get("fallback_chain", {})
                return
            except Exception:
                pass

        # 默认配置
        self._routes = {
            "reasoning": ModelConfig(
                role="reasoning",
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                api_key_env="ANTHROPIC_API_KEY",
                max_tokens=8192,
                temperature=0.3,
            ),
            "fast": ModelConfig(
                role="fast",
                provider="anthropic",
                model="claude-haiku-3-5",
                api_key_env="ANTHROPIC_API_KEY",
                max_tokens=4096,
                temperature=0.5,
            ),
            "vision": ModelConfig(
                role="vision",
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                api_key_env="ANTHROPIC_API_KEY",
                max_tokens=4096,
                temperature=0.3,
            ),
            "embedding": ModelConfig(
                role="embedding",
                provider="openai",
                model="text-embedding-3-small",
                api_key_env="OPENAI_API_KEY",
                max_tokens=1536,
            ),
        }
        self._fallback_chain = {
            "reasoning": ["fast"],
            "fast": ["reasoning"],
            "vision": ["reasoning"],
        }

    # ── 路由接口 ──────────────────────────────────

    def route(self, task_type: str) -> ModelConfig:
        """根据任务类型获取最优模型"""
        model = self._routes.get(task_type)
        if model:
            return model

        # 尝试降级
        fallbacks = self._fallback_chain.get(task_type, [])
        for fb in fallbacks:
            model = self._routes.get(fb)
            if model:
                return model

        # 最终降级到fast
        return self._routes.get("fast", ModelConfig(
            role="fast", provider="anthropic", model="claude-haiku-3-5"
        ))

    def get_model_for_task(self, task_type: str, timeout: int = 30) -> ModelConfig:
        """获取模型配置（含超时设置）"""
        model = self.route(task_type)
        # 返回带超时的副本
        return model.model_copy(update={"max_tokens": min(model.max_tokens, timeout * 100)})

    def get_all_routes(self) -> Dict[str, ModelConfig]:
        """获取所有路由配置"""
        return dict(self._routes)

    # ── 配置管理 ──────────────────────────────────

    async def update_route(self, role: str, config: ModelConfig) -> bool:
        """更新模型路由"""
        self._routes[role] = config
        await self._save_config()
        return True

    async def add_route(self, role: str, config: ModelConfig) -> bool:
        """添加模型路由"""
        self._routes[role] = config
        await self._save_config()
        return True

    async def remove_route(self, role: str) -> bool:
        """移除模型路由"""
        if role in self._routes:
            del self._routes[role]
            await self._save_config()
            return True
        return False

    async def set_fallback_chain(self, role: str, chain: List[str]) -> bool:
        """设置降级链"""
        self._fallback_chain[role] = chain
        await self._save_config()
        return True

    async def _save_config(self):
        """保存配置到文件"""
        data = {
            "routes": {role: config.model_dump() for role, config in self._routes.items()},
            "fallback_chain": self._fallback_chain,
        }
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── Token使用追踪 ──────────────────────────────────

    def record_usage(self, model: str, tokens: int):
        """记录Token使用量"""
        self._usage_stats[model] = self._usage_stats.get(model, 0) + tokens

    def get_usage_stats(self) -> Dict[str, Any]:
        """获取使用统计"""
        total = sum(self._usage_stats.values())
        return {
            "total_tokens": total,
            "by_model": dict(self._usage_stats),
            "routes": {role: config.model for role, config in self._routes.items()},
        }


# ── 全局单例 ──────────────────────────────────

_model_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """获取模型路由器单例"""
    global _model_router
    if _model_router is None:
        _model_router = ModelRouter()
    return _model_router
