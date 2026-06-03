"""
L3 用户记忆层 (User Memory) — 存储用户画像/偏好/历史。

数据流转：
  - 读取者: NLU (解析意图时辅助消歧)
  - 使用条件: 需要用户个性化上下文时
  - 写入者: 用户主动设置 / AstraAssistant 推理后提取
  - 隔离粒度: 按用户 (user_id)
"""

import json
from pathlib import Path
from typing import Optional

from app.config import settings


class UserMemory:
    """用户记忆 — 用户画像/偏好/历史查询。"""

    def __init__(self):
        self._base = Path(settings.data_dir) / "user_memory"

    # ── 路径 ────────────────────────────────────

    def _user_path(self, user_id: str) -> Path:
        return self._base / user_id / "profile.json"

    # ── 写入 ────────────────────────────────────

    def save_profile(self, user_id: str, profile: dict) -> None:
        """保存/更新用户画像。

        Args:
            user_id: 用户标识
            profile: 用户画像数据

        数据流时序:
          1. 用户首次交互或手动设置偏好
          2. → 写入 L3 (本方法)
          3. AstraAssistant/NLU 后续读取 L3 以辅助意图解析和个性化
        """
        dir_path = self._base / user_id
        dir_path.mkdir(parents=True, exist_ok=True)

        path = self._user_path(user_id)
        existing = self.load_profile(user_id) or {}
        existing.update(profile)
        # 保留合并后的完整数据
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    def update_preferred_markets(self, user_id: str, markets: list[str]) -> None:
        """更新用户常用目标市场。"""
        profile = self.load_profile(user_id) or {}
        profile["preferred_markets"] = list(set(markets))
        self.save_profile(user_id, profile)

    def record_search(self, user_id: str, product_name: str) -> None:
        """记录用户的最新搜索（最多保留 10 条）。"""
        profile = self.load_profile(user_id) or {}
        recent = profile.get("recent_searches", [])
        recent = [p for p in recent if p != product_name]
        recent.insert(0, product_name)
        profile["recent_searches"] = recent[:10]
        self.save_profile(user_id, profile)

    # ── 读取 ────────────────────────────────────

    def load_profile(self, user_id: str) -> Optional[dict]:
        """加载用户画像。

        Args:
            user_id: 用户标识

        Returns:
            用户画像 dict，不存在返回 None
        """
        path = self._user_path(user_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
