"""三单一致性检查 — 销售订单 × 支付记录 × 物流/报关单数据对比。

三单定义：
  销售单  → sales_orders（商品、金额、收货人）
  资金单  → payment_records（支付金额、支付人）
  物流/报关 → logistics_orders + customs_declarations（申报价值、收货人、目的国）

对比维度：
  1. 金额一致性：订单金额 ≈ 支付金额 ≈ 申报价值（允许 ±10% 汇率误差）
  2. 收货人一致性：买家姓名 ≈ 报关收货人
  3. 商品数量一致性：订单数量 = 申报数量
  4. 目的国一致性：买家地址国 = 报关目的国 = 物流目的国
  5. 支付完整性：是否有完成的支付记录
"""

from __future__ import annotations

import json
import re
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_name(name: str) -> str:
    """标准化姓名用于对比（大小写、空格、特殊字符）。"""
    return re.sub(r"[^a-z0-9一-鿿]", "", name.lower().strip())


def _pct_diff(a: float, b: float) -> float:
    """两个金额的百分比差异。"""
    if max(a, b) == 0:
        return 0.0
    return abs(a - b) / max(a, b) * 100


def _get_country_from_address(address) -> str:
    """从地址对象/字符串提取国家代码。"""
    if isinstance(address, dict):
        return address.get("country", "").upper()
    if isinstance(address, str):
        try:
            d = json.loads(address)
            return d.get("country", "").upper()
        except Exception:
            return ""
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# 核心检查类
# ─────────────────────────────────────────────────────────────────────────────

class ThreeWayChecker:
    """三单一致性检查器。"""

    # 允许的金额误差阈值（汇率波动 + 运费四舍五入）
    AMOUNT_TOLERANCE_PCT = 10.0
    # 允许的申报价值最低比例（低于订单金额 70% 判定低申报风险）
    LOW_DECLARATION_THRESHOLD = 0.70

    def check(
        self,
        order_id: Optional[str] = None,
        declaration_id: Optional[str] = None,
        logistics_id: Optional[str] = None,
    ) -> dict:
        """执行三单一致性完整检查。

        至少需要 order_id 或 declaration_id 其中一个。
        返回：
            {
                "passed": bool,
                "checks": list[dict],      # 每项检查结果
                "summary": str,
                "high_risk": bool,         # 是否存在严重问题（如低申报）
            }
        """
        checks: list[dict] = []

        # 加载数据
        order      = self._load_order(order_id)
        declaration = self._load_declaration(declaration_id)
        logistics  = self._load_logistics(logistics_id)
        payments   = self._load_payments(order_id) if order_id else []

        # ── 检查 1: 支付完整性 ─────────────────────────────────────────────
        if order:
            checks.append(self._check_payment_completeness(order, payments))

        # ── 检查 2: 订单 vs 支付金额 ──────────────────────────────────────
        if order and payments:
            checks.append(self._check_order_payment_amount(order, payments))

        # ── 检查 3: 申报价值 vs 订单金额 ──────────────────────────────────
        if order and declaration:
            checks.append(self._check_amount_vs_declaration(order, declaration))

        # ── 检查 4: 收货人一致性 ───────────────────────────────────────────
        if order and declaration:
            checks.append(self._check_consignee(order, declaration))

        # ── 检查 5: 数量一致性 ────────────────────────────────────────────
        if order and declaration:
            checks.append(self._check_quantity(order, declaration))

        # ── 检查 6: 目的国一致性 ──────────────────────────────────────────
        if order and declaration:
            checks.append(self._check_destination_country(order, declaration, logistics))

        # ── 检查 7: 物流单与报关单关联 ────────────────────────────────────
        if declaration and logistics:
            checks.append(self._check_logistics_linkage(declaration, logistics))

        # 汇总
        errors   = [c for c in checks if c["level"] == "error"]
        warnings = [c for c in checks if c["level"] == "warning"]
        passed   = all(c["level"] in ("pass", "info", "na") for c in checks)
        high_risk = any(c.get("code") in ("LOW_DECLARATION", "PAYMENT_MISSING") for c in checks)

        return {
            "passed":    passed,
            "high_risk": high_risk,
            "error_count":   len(errors),
            "warning_count": len(warnings),
            "checks":    checks,
            "summary": (
                f"三单一致性：{len(errors)} 项严重问题，{len(warnings)} 项警告"
                if not passed
                else "三单一致性验证通过 ✓"
            ),
            "checked_at": self._now(),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 各项具体检查
    # ─────────────────────────────────────────────────────────────────────────

    def _check_payment_completeness(self, order: dict, payments: list) -> dict:
        """支付完整性：是否有已完成的支付记录。"""
        completed = [p for p in payments if p.get("status") == "completed"]
        if not completed:
            if not payments:
                return {
                    "rule": "PAYMENT_COMPLETENESS",
                    "level": "warning",
                    "code": "PAYMENT_MISSING",
                    "message": "订单无支付记录，无法验证资金流",
                    "recommendation": "请补录支付记录，确保三单资金流匹配",
                    "found": "无", "expected": "至少 1 条已完成支付",
                }
            return {
                "rule": "PAYMENT_COMPLETENESS",
                "level": "warning",
                "code": "PAYMENT_PENDING",
                "message": f"订单有 {len(payments)} 条支付记录，但均未完成（状态非 completed）",
                "recommendation": "确认支付状态，完成后方可报关",
                "found": [p["status"] for p in payments], "expected": "completed",
            }
        total_paid = sum(p["amount"] for p in completed)
        return {
            "rule": "PAYMENT_COMPLETENESS",
            "level": "pass",
            "code": "PAYMENT_OK",
            "message": f"支付完整，累计已付 {total_paid} {completed[0].get('currency','USD')}",
            "found": total_paid, "expected": order.get("total_amount", 0),
        }

    def _check_order_payment_amount(self, order: dict, payments: list) -> dict:
        """订单金额 vs 支付金额。"""
        completed = [p for p in payments if p.get("status") == "completed"]
        if not completed:
            return {"rule": "ORDER_PAYMENT_AMOUNT", "level": "na", "code": "NO_PAYMENT",
                    "message": "无已完成支付记录，跳过金额对比"}
        total_paid = sum(p["amount"] for p in completed)
        order_amt  = float(order.get("total_amount", 0))
        diff_pct   = _pct_diff(order_amt, total_paid)
        if diff_pct > self.AMOUNT_TOLERANCE_PCT:
            return {
                "rule": "ORDER_PAYMENT_AMOUNT",
                "level": "error",
                "code": "AMOUNT_MISMATCH",
                "message": f"订单金额（{order_amt}）与支付金额（{total_paid}）差异 {diff_pct:.1f}%，超过允许阈值 {self.AMOUNT_TOLERANCE_PCT}%",
                "recommendation": "核实是否有部分退款或溢缴，更新支付记录",
                "found": total_paid, "expected": order_amt, "diff_pct": round(diff_pct, 1),
            }
        return {
            "rule": "ORDER_PAYMENT_AMOUNT",
            "level": "pass",
            "code": "AMOUNT_OK",
            "message": f"订单金额与支付金额一致（差异 {diff_pct:.1f}%）",
            "found": total_paid, "expected": order_amt,
        }

    def _check_amount_vs_declaration(self, order: dict, declaration: dict) -> dict:
        """订单金额 vs 报关申报价值（低申报检测）。"""
        order_amt   = float(order.get("total_amount", 0))
        decl_value  = float(declaration.get("declared_value", 0))
        if order_amt <= 0:
            return {"rule": "AMOUNT_VS_DECLARATION", "level": "na", "code": "NO_ORDER_AMOUNT",
                    "message": "订单金额为 0，跳过低申报检测"}
        diff_pct = _pct_diff(order_amt, decl_value)
        ratio    = decl_value / order_amt if order_amt > 0 else 1.0

        if ratio < self.LOW_DECLARATION_THRESHOLD:
            return {
                "rule": "AMOUNT_VS_DECLARATION",
                "level": "error",
                "code": "LOW_DECLARATION",
                "message": f"申报价值（{decl_value} {declaration.get('declared_currency','USD')}）"
                           f"仅为订单金额（{order_amt}）的 {ratio*100:.0f}%，低申报比例超过阈值。"
                           f"目的国海关可处 2-5 倍罚款并扣货。",
                "recommendation": "按实际成交价申报；若有合理折扣须附证明文件",
                "found": decl_value, "expected": order_amt, "ratio": round(ratio, 2),
            }
        if diff_pct > self.AMOUNT_TOLERANCE_PCT:
            return {
                "rule": "AMOUNT_VS_DECLARATION",
                "level": "warning",
                "code": "AMOUNT_DIFF_WARN",
                "message": f"申报价值与订单金额差异 {diff_pct:.1f}%，超过 {self.AMOUNT_TOLERANCE_PCT}% 阈值，建议核查",
                "recommendation": "确认汇率转换是否正确；差异过大可能引起海关质疑",
                "found": decl_value, "expected": order_amt, "diff_pct": round(diff_pct, 1),
            }
        return {
            "rule": "AMOUNT_VS_DECLARATION",
            "level": "pass",
            "code": "DECLARATION_VALUE_OK",
            "message": f"申报价值与订单金额一致（差异 {diff_pct:.1f}%）",
            "found": decl_value, "expected": order_amt,
        }

    def _check_consignee(self, order: dict, declaration: dict) -> dict:
        """收货人一致性：买家姓名 ≈ 报关收货人。"""
        buyer_name     = order.get("buyer_name", "")
        consignee_name = declaration.get("consignee_name", "")

        if not consignee_name:
            return {
                "rule": "CONSIGNEE",
                "level": "warning",
                "code": "CONSIGNEE_MISSING",
                "message": "报关单未填写收货人姓名，无法进行三单比对",
                "recommendation": "在报关单中填写收货人（Consignee）信息",
                "found": "", "expected": buyer_name,
            }

        buyer_norm     = _normalize_name(buyer_name)
        consignee_norm = _normalize_name(consignee_name)

        # 容错：一方包含另一方（如"John Smith" vs "Smith, John"）
        if buyer_norm and consignee_norm:
            match = (buyer_norm == consignee_norm or
                     buyer_norm in consignee_norm or
                     consignee_norm in buyer_norm)
        else:
            match = False

        if not match:
            return {
                "rule": "CONSIGNEE",
                "level": "error",
                "code": "CONSIGNEE_MISMATCH",
                "message": f"买家姓名（'{buyer_name}'）与报关收货人（'{consignee_name}'）不一致。"
                           "可能导致海关质疑商业真实性。",
                "recommendation": "核实是否代收货，如有需附委托书；或修正报关单收货人",
                "found": consignee_name, "expected": buyer_name,
            }
        return {
            "rule": "CONSIGNEE",
            "level": "pass",
            "code": "CONSIGNEE_OK",
            "message": f"收货人一致：'{buyer_name}'",
        }

    def _check_quantity(self, order: dict, declaration: dict) -> dict:
        """数量一致性：订单总数 vs 报关申报数量。"""
        items = order.get("items", [])
        if isinstance(items, str):
            try: items = json.loads(items)
            except: items = []
        order_qty = sum(int(i.get("qty", 0)) for i in items)
        decl_qty  = int(declaration.get("quantity", 0))

        if order_qty == 0 or decl_qty == 0:
            return {"rule": "QUANTITY", "level": "na", "code": "QTY_ZERO",
                    "message": "订单或报关单数量为 0，跳过数量对比"}

        if order_qty != decl_qty:
            return {
                "rule": "QUANTITY",
                "level": "warning",
                "code": "QUANTITY_MISMATCH",
                "message": f"订单总数量（{order_qty}）与申报数量（{decl_qty}）不一致",
                "recommendation": "确认是否分批发货；若是，报关单需注明分批信息",
                "found": decl_qty, "expected": order_qty,
            }
        return {
            "rule": "QUANTITY",
            "level": "pass",
            "code": "QUANTITY_OK",
            "message": f"数量一致：{order_qty} 件",
        }

    def _check_destination_country(
        self, order: dict, declaration: dict, logistics: Optional[dict]
    ) -> dict:
        """目的国一致性：买家地址 = 报关目的国 = 物流目的国。"""
        buyer_addr  = order.get("buyer_address", {})
        buyer_country   = _get_country_from_address(buyer_addr)
        decl_country    = declaration.get("dest_country", "").upper()
        logi_country    = logistics.get("dest_country", "").upper() if logistics else ""

        mismatches = []
        if buyer_country and decl_country and buyer_country != decl_country:
            mismatches.append(f"买家地址({buyer_country}) ≠ 报关目的国({decl_country})")
        if logi_country and decl_country and logi_country != decl_country:
            mismatches.append(f"物流目的国({logi_country}) ≠ 报关目的国({decl_country})")

        if mismatches:
            return {
                "rule": "DESTINATION_COUNTRY",
                "level": "error",
                "code": "COUNTRY_MISMATCH",
                "message": "目的国不一致：" + "；".join(mismatches),
                "recommendation": "核实发货目的地，更正报关单或物流单的目的国",
                "found": {"order": buyer_country, "declaration": decl_country, "logistics": logi_country},
            }
        return {
            "rule": "DESTINATION_COUNTRY",
            "level": "pass",
            "code": "COUNTRY_OK",
            "message": f"目的国一致：{decl_country}",
        }

    def _check_logistics_linkage(self, declaration: dict, logistics: dict) -> dict:
        """物流单与报关单关联检查。"""
        decl_logi_id = declaration.get("logistics_id")
        logi_id      = logistics.get("id")
        if decl_logi_id != logi_id:
            return {
                "rule": "LOGISTICS_LINKAGE",
                "level": "warning",
                "code": "LOGISTICS_NOT_LINKED",
                "message": f"报关单关联的物流单（{decl_logi_id}）与当前物流单（{logi_id}）不一致",
                "recommendation": "更新报关单的 logistics_id 字段",
            }
        if not logistics.get("tracking_number"):
            return {
                "rule": "LOGISTICS_LINKAGE",
                "level": "warning",
                "code": "NO_TRACKING",
                "message": "物流单尚无运单号，9610 报关要求运单号与报关单信息匹配",
                "recommendation": "填入实际运单号后再提交报关",
            }
        return {
            "rule": "LOGISTICS_LINKAGE",
            "level": "pass",
            "code": "LOGISTICS_LINKED",
            "message": f"物流单已关联，运单号 {logistics['tracking_number']}",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 数据加载
    # ─────────────────────────────────────────────────────────────────────────

    def _load_order(self, order_id: Optional[str]) -> Optional[dict]:
        if not order_id:
            return None
        try:
            from app.storage.order_store import get_order
            return get_order(order_id)
        except Exception:
            return None

    def _load_declaration(self, declaration_id: Optional[str]) -> Optional[dict]:
        if not declaration_id:
            return None
        try:
            from app.storage.customs_store import get_declaration
            return get_declaration(declaration_id)
        except Exception:
            return None

    def _load_logistics(self, logistics_id: Optional[str]) -> Optional[dict]:
        if not logistics_id:
            return None
        try:
            from app.storage.logistics_store import get_order
            return get_order(logistics_id)
        except Exception:
            return None

    def _load_payments(self, order_id: Optional[str]) -> list:
        if not order_id:
            return []
        try:
            from app.storage.order_store import get_payments
            return get_payments(order_id)
        except Exception:
            return []

    def _now(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─────────────────────────────────────────────────────────────────────────────
# 单例
# ─────────────────────────────────────────────────────────────────────────────

_checker: Optional[ThreeWayChecker] = None


def get_three_way_checker() -> ThreeWayChecker:
    global _checker
    if _checker is None:
        _checker = ThreeWayChecker()
    return _checker
