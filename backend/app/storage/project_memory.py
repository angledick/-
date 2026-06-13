"""
L2 项目/产品记忆层 (Project Memory) — 存储产品合规档案。

数据流转：
  - 读取者: 历史查询 · Dashboard · 合规报告页面
  - 使用条件: 查看某产品的历史合规记录时
  - 写入者: compliance.py / chat.py（每次合规检查完成）
  - 隔离粒度: 按对应产品（product_id）
"""

import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from app.config import settings


class ProjectMemory:
    """项目/产品记忆 — 每个产品的合规档案。"""

    def __init__(self):
        self._base = Path(settings.data_dir) / "project_memory"

    # ── 路径 ────────────────────────────────────

    def _product_dir(self, product_id: str) -> Path:
        return self._base / product_id

    def _product_path(self, product_id: str) -> Path:
        return self._product_dir(product_id) / "compliance.json"

    # ── 写入 ────────────────────────────────────

    def save_compliance_record(
        self,
        product_id: str,
        product_name: str,
        target_market: str,
        result: dict,
        session_id: str = "",
    ) -> str:
        """保存一次合规检查结果到产品档案。

        数据流时序:
          1. ComplianceRules + RAG 完成检查
          2. 组装 ComplianceResult
          3. → 写入 L2 (本方法)
          4. → 写入 L4 session_memory
          5. → 写入 L5 event_chain (action_chain)

        Args:
            product_id: 产品标识（可由前端生成或基于产品名哈希）
            product_name: 产品名称
            target_market: 目标市场
            result: ComplianceResult 的 dict 形式
            session_id: 关联的会话 ID

        Returns:
            check_id (用于回查)
        """
        check_id = f"chk_{uuid.uuid4().hex[:8]}"
        record = {
            "check_id": check_id,
            "product_name": product_name,
            "target_market": target_market,
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": result,
        }

        self._product_dir(product_id).mkdir(parents=True, exist_ok=True)
        path = self._product_path(product_id)

        # 追加到历史
        history = self._load_history(product_id)
        history.append(record)

        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "product_id": product_id,
                "product_name": product_name,
                "checks": history,
            }, f, ensure_ascii=False, indent=2)

        return check_id

    # ── 读取 ────────────────────────────────────

    def _load_history(self, product_id: str) -> list[dict]:
        """加载产品合规历史。"""
        path = self._product_path(product_id)
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("checks", [])

    def get_compliance_history(self, product_id: str) -> list[dict]:
        """获取产品的全部合规检查历史。

        Args:
            product_id: 产品标识

        Returns:
            历史记录列表（按时间排序）
        """
        return self._load_history(product_id)

    def get_latest_check(self, product_id: str) -> Optional[dict]:
        """获取产品的最新一次合规检查结果。

        Args:
            product_id: 产品标识

        Returns:
            最新的合规记录，无历史返回 None
        """
        history = self._load_history(product_id)
        return history[-1] if history else None

    def list_products(self) -> list[dict]:
        """列出所有有合规记录的产品摘要。"""
        if not self._base.exists():
            return []
        products = []
        for d in sorted(self._base.iterdir()):
            if d.is_dir():
                path = d / "compliance.json"
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    products.append({
                        "product_id": d.name,
                        "product_name": data.get("product_name", ""),
                        "total_checks": len(data.get("checks", [])),
                        "last_check": data.get("checks", [{}])[-1].get("timestamp", ""),
                    })
        return products
