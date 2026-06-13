"""
L0 原始数据存储层 (Raw Store) — 读取 data/raw/ 下的静态数据文件。

数据流转：
  - 读取者: ComplianceRules (compliance_rules.py)
  - 使用条件: 确定性合规检查时需要匹配 HS 编码 / VAT / 认证矩阵
  - 读取时机: 模块加载时缓存到内存，后续不走磁盘
  - 来源文件: data/raw/hs_codes/*.json, vat_rates/*.json, certifications/*.json
  - Regulations: data/raw/regulations/*.md → 由 Knowledge Loader 读取后向量化到 L1
"""

import json
from pathlib import Path
from typing import Optional

from app.config import settings


class RawStore:
    """L0 原始数据存储层。"""

    def __init__(self):
        self._base = Path(settings.data_dir) / "raw"
        self._cache: dict[str, dict] = {}

    # ── 缓存管理 ──────────────────────────────

    def _load(self, category: str, filename: str) -> dict:
        """按分类 + 文件名读取 JSON 文件，结果缓存到内存。"""
        cache_key = f"{category}/{filename}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self._base / category / filename
        if not path.exists():
            return {}

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._cache[cache_key] = data
        return data

    def invalidate_cache(self, category: str = "", filename: str = "") -> None:
        """清除指定缓存（热加载用）。category/filename 都为空则清全部。"""
        if not category and not filename:
            self._cache.clear()
        elif category and filename:
            self._cache.pop(f"{category}/{filename}", None)
        elif category:
            keys = [k for k in self._cache if k.startswith(f"{category}/")]
            for k in keys:
                self._cache.pop(k, None)

    # ── HS 编码 ──────────────────────────────

    def load_hs_codes(self) -> list[dict]:
        """读取 HS 编码数据。"""
        data = self._load("hs_codes", "_all.json")
        return data.get("hs_codes", [])

    def lookup_hs(self, product_name: str) -> Optional[dict]:
        """模糊匹配产品名到 HS 编码。

        Args:
            product_name: 产品中文名称

        Returns:
            HS 编码条目 dict 或 None
        """
        codes = self.load_hs_codes()
        product_lower = product_name.lower()
        aliases = {
            "锂电池": ["锂离子蓄电池", "电池"],
            "电池": ["锂离子蓄电池"],
            "笔记本": ["便携式数据处理设备"],
            "电脑": ["数据处理设备"],
            "灯": ["LED灯具", "照明装置"],
            "玩具": ["玩具"],
            "摄像头": ["摄像机", "数码相机"],
        }
        for entry in codes:
            desc = entry.get("description_cn", "").lower()
            if product_lower in desc or any(
                kw in desc for kw in product_lower.split()
            ):
                return entry
            for key, alias_list in aliases.items():
                if key in product_name:
                    for alias in alias_list:
                        if alias.lower() in desc:
                            return entry
        return None

    # ── VAT 税率 ──────────────────────────────

    def load_vat_rates(self) -> dict[str, dict]:
        """读取 VAT 税率数据。"""
        return self._load("vat_rates", "_all.json")

    def lookup_vat(self, country: str) -> float:
        """按国家名查询 VAT 税率。

        Args:
            country: 目标国家

        Returns:
            VAT 百分比税率，未知返回 0.0
        """
        rates = self.load_vat_rates()
        entry = rates.get(country, {})
        return entry.get("standard", 0.0)

    # ── 认证矩阵 ──────────────────────────────

    def load_cert_matrix(self) -> dict[str, list[str]]:
        """读取认证矩阵（国家 → 所需认证列表）。"""
        return self._load("certifications", "cert_matrix.json")

    def get_certifications(self, country: str) -> list[str]:
        """按国家查询所需认证。

        Args:
            country: 目标国家

        Returns:
            认证列表，未知国家返回德国标准（最保守）
        """
        matrix = self.load_cert_matrix()
        return matrix.get(country, matrix.get("德国", []))

    def _resolve_path(self, category: str, filename: str) -> Path:
        # 用于 compliance_rules.py 数据路径解析
        return self._base / category / filename
