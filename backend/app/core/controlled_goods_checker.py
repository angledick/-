"""管制品检测规则引擎（静态版）。

检测维度：
  1. 目的国制裁检查（7 个明确制裁国）
  2. HS 编码高危品类（军事/核/化武前体/稀土/加密）
  3. 供应商/商品名关键词（新疆棉、强迫劳动、稀土材料）
  4. 原产地敏感性检查

输出：list[dict] — 每项包含 level(error/warning/info) + code + message + recommendation

下期：对接 OFAC SDN XML、Commerce Entity List、REACH 化学品数据库
"""

from __future__ import annotations

from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# 制裁国清单（OFAC + UN + EU 共识制裁）
# ─────────────────────────────────────────────────────────────────────────────

SANCTIONED_COUNTRIES = {
    "IR": "伊朗",
    "KP": "朝鲜",
    "CU": "古巴",
    "SY": "叙利亚",
    "SD": "苏丹",
    "SS": "南苏丹",
    # 部分业务受限
    "RU": "俄罗斯（部分类别限制）",
    "BY": "白俄罗斯（部分类别限制）",
    "MM": "缅甸（部分类别限制）",
    "VE": "委内瑞拉（部分类别限制）",
}

PARTIAL_RESTRICTION_COUNTRIES = {"RU", "BY", "MM", "VE"}

# ─────────────────────────────────────────────────────────────────────────────
# HS 编码高危品类映射
# ─────────────────────────────────────────────────────────────────────────────

# 格式：前缀 → (level, category, note)
HS_HIGH_RISK: dict[str, tuple[str, str, str]] = {
    # 武器/弹药
    "93": ("error",   "weapons",      "武器弹药（HS 93章）通常禁止出口"),
    # 核材料/核反应堆
    "84": ("info",    "dual_use",     "大型机械设备，部分型号需出口许可证核查"),
    "2844": ("error", "nuclear",      "放射性材料/核燃料，严格管控"),
    "8401": ("error", "nuclear",      "核反应堆及零件"),
    # 化学武器前体（部分）
    "2903": ("warning","chemical",    "含氯有机物，部分品种受《化学武器公约》管制"),
    "2921": ("warning","chemical",    "胺类化合物，部分品种受管制"),
    "2931": ("warning","chemical",    "有机磷化合物，部分品种属化武前体"),
    # 加密技术
    "8543": ("warning","cryptography","含密码芯片产品，出口可能需商务部许可证"),
    "8517": ("info",   "telecom",     "通信设备，部分高频率或军用规格需许可证"),
    # 稀土/稀有金属
    "2805": ("warning","rare_earth",  "稀有金属（铯、铷等），中国实施出口配额"),
    "2846": ("warning","rare_earth",  "稀土化合物，受中国出口配额管制"),
    "7202": ("warning","rare_earth",  "铁合金，含稀土成分需核查出口资质"),
    # 航空/航天
    "8802": ("error",  "aerospace",   "航空器，严格出口许可管制"),
    "8803": ("error",  "aerospace",   "航空器零部件，受ITAR/EAR管控"),
    # 军民两用精密光学
    "9005": ("warning","optics",      "天文望远镜/夜视设备，部分军用规格受管制"),
    "9013": ("info",   "dual_use",    "激光设备，高功率型需核查出口分类"),
    # 生物医学
    "3002": ("warning","biological",  "血液/疫苗/病原体，生物安全管控"),
    # 卫星/导航
    "8526": ("warning","navigation",  "雷达/无线电导航设备，军用规格受ITAR管控"),
}

# ─────────────────────────────────────────────────────────────────────────────
# 新疆棉 / 强迫劳动 关键词
# ─────────────────────────────────────────────────────────────────────────────

XINJIANG_KEYWORDS = [
    "新疆", "xinjiang", "xj cotton", "uyghur",
    "维吾尔", "uighur", "ürümqi", "urumqi", "乌鲁木齐",
]

FORCED_LABOR_KEYWORDS = [
    "强迫劳动", "forced labor", "forced labour", "prison labor",
    "监狱劳工", "囚工",
]

# 纺织/服装 HS 前缀（新疆棉重点检查范围）
TEXTILE_HS_PREFIXES = {"50", "51", "52", "53", "54", "55", "56", "57",
                        "58", "59", "60", "61", "62", "63"}

# ─────────────────────────────────────────────────────────────────────────────
# 稀土关键词
# ─────────────────────────────────────────────────────────────────────────────

RARE_EARTH_KEYWORDS = [
    "稀土", "rare earth", "钕", "neodymium", "镝", "dysprosium",
    "铽", "terbium", "钴", "cobalt", "锂", "lithium", "镓", "gallium",
    "锗", "germanium", "钨", "tungsten", "钼", "molybdenum",
    "钕铁硼", "ndfeb", "permanent magnet", "永磁",
]

# ─────────────────────────────────────────────────────────────────────────────
# 核心检测逻辑
# ─────────────────────────────────────────────────────────────────────────────

class ControlledGoodsChecker:
    """管制品检测规则引擎。"""

    def check_destination(self, dest_country: str) -> list[dict]:
        """目的国制裁检查。"""
        issues = []
        country = dest_country.upper()
        if country in SANCTIONED_COUNTRIES:
            is_partial = country in PARTIAL_RESTRICTION_COUNTRIES
            issues.append({
                "rule":   "SANCTIONED_COUNTRY",
                "level":  "warning" if is_partial else "error",
                "code":   f"DEST_{country}",
                "message": f"目的国 {SANCTIONED_COUNTRIES[country]}（{country}）受国际制裁限制。"
                           + ("部分商品类别受限，请确认具体商品是否可出口。" if is_partial
                              else "禁止出口绝大多数商品。"),
                "recommendation": "咨询法律顾问确认具体商品的出口合规性",
                "data_source": "OFAC/EU/UN 制裁清单（静态版，2026）",
            })
        return issues

    def check_hs_code(self, hs_code: str) -> list[dict]:
        """HS 编码高危品类检测。"""
        issues = []
        hs = hs_code.replace(".", "").replace(" ", "")

        # 从最精确到最宽泛匹配
        matched = None
        for prefix_len in [6, 4, 2]:
            prefix = hs[:prefix_len]
            if prefix in HS_HIGH_RISK:
                matched = (prefix, HS_HIGH_RISK[prefix])
                break

        if matched:
            prefix, (level, category, note) = matched
            issues.append({
                "rule":   "HS_HIGH_RISK",
                "level":  level,
                "code":   f"HS_{category.upper()}",
                "message": f"HS 编码 {hs_code}（前缀 {prefix}）属于 {category} 类高风险品类。{note}",
                "recommendation": _get_hs_recommendation(category),
                "data_source": "ECCN/EAR/ITAR 管制品类映射（简化版）",
            })
        return issues

    def check_supplier(
        self,
        supplier_name: str,
        supplier_address: str = "",
        country: str = "",
    ) -> list[dict]:
        """供应商合规检查（制裁实体 + 新疆棉 + 强迫劳动）。"""
        issues = []
        text = f"{supplier_name} {supplier_address}".lower()

        # 新疆棉关键词检测
        xinjiang_hits = [kw for kw in XINJIANG_KEYWORDS if kw.lower() in text]
        if xinjiang_hits:
            issues.append({
                "rule":   "XINJIANG_COTTON",
                "level":  "error",
                "code":   "XINJIANG_SUPPLIER",
                "message": f"供应商信息包含新疆相关关键词（{xinjiang_hits[0]}）。美国《维吾尔强迫劳动预防法》(ULFPA) 假定新疆产品含强迫劳动成分，进口美国将被拒绝。",
                "recommendation": "提供供应链溯源文件，证明原材料非来自新疆；或更换供应商",
                "data_source": "ULFPA (Uyghur Forced Labor Prevention Act)",
            })

        # 强迫劳动关键词检测
        forced_hits = [kw for kw in FORCED_LABOR_KEYWORDS if kw.lower() in text]
        if forced_hits:
            issues.append({
                "rule":   "FORCED_LABOR",
                "level":  "error",
                "code":   "FORCED_LABOR_RISK",
                "message": f"供应商信息包含强迫劳动相关敏感词，存在供应链合规风险。",
                "recommendation": "进行第三方供应链审计（SGS/BV/Intertek）",
                "data_source": "ILO 核心劳工标准",
            })

        # 稀土关键词检测
        rare_hits = [kw for kw in RARE_EARTH_KEYWORDS if kw.lower() in text]
        if rare_hits:
            issues.append({
                "rule":   "RARE_EARTH",
                "level":  "warning",
                "code":   "RARE_EARTH_SUPPLIER",
                "message": f"供应商可能涉及稀土材料（{rare_hits[0]}）。中国对多种稀土实施出口配额管制。",
                "recommendation": "确认供应商持有相应出口许可证",
                "data_source": "中国商务部稀土出口管制规定",
            })

        return issues

    def check_product(
        self,
        hs_code: str,
        product_name: str,
        supplier_country: str = "CN",
        dest_country: str = "",
    ) -> list[dict]:
        """商品合规综合检查。"""
        issues = []
        hs = hs_code.replace(".", "")
        text = product_name.lower()

        # HS 编码检查
        issues.extend(self.check_hs_code(hs_code))

        # 纺织品 + 中国来源 → 新疆棉预警
        if hs[:2] in TEXTILE_HS_PREFIXES and supplier_country.upper() == "CN":
            if dest_country.upper() in ("US", "UK", "EU", "CA", "AU"):
                issues.append({
                    "rule":   "TEXTILE_XINJIANG_RISK",
                    "level":  "warning",
                    "code":   "TEXTILE_SUPPLY_CHAIN",
                    "message": f"纺织品（HS {hs_code}）从中国出口到 {dest_country or '欧美'}，需提供棉花来源证明，排查新疆棉成分。",
                    "recommendation": "申请 Higg FEM 认证或提供棉花溯源报告",
                    "data_source": "ULFPA / EU Due Diligence Directive",
                })

        # 稀土关键词 in 商品名
        rare_hits = [kw for kw in RARE_EARTH_KEYWORDS if kw.lower() in text]
        if rare_hits:
            issues.append({
                "rule":   "RARE_EARTH_PRODUCT",
                "level":  "warning",
                "code":   "RARE_EARTH_EXPORT",
                "message": f"商品名称包含稀土相关词汇（{rare_hits[0]}）。确认是否已申请出口许可证。",
                "recommendation": "向商务部申请稀土出口许可证",
                "data_source": "中国稀土出口管制",
            })

        return issues

    def full_check(
        self,
        hs_code: str,
        declared_name: str,
        dest_country: str,
        supplier_name: str = "",
        supplier_address: str = "",
        supplier_country: str = "CN",
    ) -> dict:
        """完整管制品检查入口，返回汇总结果。"""
        all_issues: list[dict] = []
        all_issues.extend(self.check_destination(dest_country))
        all_issues.extend(self.check_product(hs_code, declared_name, supplier_country, dest_country))
        if supplier_name or supplier_address:
            all_issues.extend(self.check_supplier(supplier_name, supplier_address, supplier_country))

        errors   = [i for i in all_issues if i["level"] == "error"]
        warnings = [i for i in all_issues if i["level"] == "warning"]

        return {
            "passed":   len(errors) == 0,
            "level":    "error" if errors else ("warning" if warnings else "pass"),
            "errors":   errors,
            "warnings": warnings,
            "infos":    [i for i in all_issues if i["level"] == "info"],
            "total":    len(all_issues),
            "summary":  (
                f"{len(errors)} 个严重问题，{len(warnings)} 个警告"
                if all_issues else "未发现管制品风险"
            ),
            "data_freshness": "2026-06-14（静态规则引擎，每季度更新）",
        }


# ─────────────────────────────────────────────────────────────────────────────
# 辅助
# ─────────────────────────────────────────────────────────────────────────────

def _get_hs_recommendation(category: str) -> str:
    recs = {
        "weapons":      "武器类商品需获得出口许可证，并向商务部申报",
        "nuclear":      "核材料出口须经国家核安全局审批，流程复杂，建议咨询专业律师",
        "chemical":     "核查 CAS 号是否在《化学武器公约》附表中，如在须申请出口许可",
        "cryptography": "向商务部信息化产品出口许可证受理机构申请批准",
        "aerospace":    "航空器及零部件受 ITAR 管制，需申请国务院 State Dept 许可",
        "dual_use":     "核查商品是否列入《两用物项出口管制清单》",
        "rare_earth":   "联系商务部稀土办公室核实出口配额状态",
        "optics":       "高性能光学/激光设备需申请出口许可",
        "biological":   "生物样品出口须经国家卫健委审批",
        "navigation":   "军用规格导航设备受 ITAR 管控，需国务院许可",
        "telecom":      "核查频率许可证要求，高频通信设备需特别申报",
    }
    return recs.get(category, "建议咨询专业出口合规律师")


# ─────────────────────────────────────────────────────────────────────────────
# 单例
# ─────────────────────────────────────────────────────────────────────────────

_checker: Optional[ControlledGoodsChecker] = None


def get_controlled_goods_checker() -> ControlledGoodsChecker:
    global _checker
    if _checker is None:
        _checker = ControlledGoodsChecker()
    return _checker
