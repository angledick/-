"""产品出海生命周期 LLM 分析器 — 网关版。

所有调用均通过 LLMGateway（glm-5.1），配置统一由 routes.yaml 管理。

三大分析能力：
  1. analyze_supplier      — 供应商资质审核 + 风险评级
  2. analyze_contract      — 合同合规审查（交货/价格/知识产权/责任）
  3. analyze_customs_declaration — 报关合规检查（HS/低申报/三单一致性/IOSS）
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Prompts（针对 glm-5.1 推理模型优化，简洁直白指令优于冗长描述）
# ─────────────────────────────────────────────────────────────────────────────

_SUPPLIER_SYSTEM = """\
你是跨境贸易合规顾问，分析供应商资质风险。输出严格 JSON：
{
  "risk_level": "low|medium|high|critical",
  "score": 0-100,
  "summary": "≤50字综合评价",
  "risks": [{"code":"代码","level":"error|warning|info","message":"风险描述","recommendation":"建议"}],
  "strengths": ["优势列表"],
  "verified_items": ["已核实项目"]
}
检查维度：营业执照合法性、增值税专票资质（影响出口退税）、制裁名单风险（新疆棉/稀土/军民两用品）、认证与供应品类匹配度、联系信息完整性。
risk_level=critical 仅用于涉及制裁或明显违法。"""

_CONTRACT_SYSTEM = """\
你是国际贸易法律顾问，审查跨境电商采购合同合规性。输出严格 JSON：
{
  "score": 0-100,
  "summary": "≤50字综合评价",
  "issues": [{"code":"代码","level":"critical|error|warning|info","clause":"涉及条款","message":"问题","recommendation":"修改建议"}],
  "strengths": ["合规亮点"],
  "checklist": [{"item":"检查项","status":"pass|fail|na","note":"备注"}]
}
必检：贸易术语风险（EXW=买方全承/DDP=卖方进口资质）、汇率锁定/付款条件/交货期/质量验货/IP归属/违约赔偿/争议解决/管制品声明/资金链路合规。"""

_CUSTOMS_SYSTEM = """\
你是跨境电商报关合规专家，检查报关单合规性。输出严格 JSON：
{
  "passed": true|false,
  "issues": [{"code":"代码","level":"error|warning|info","message":"问题","recommendation":"建议"}]
}
检查：HS编码与品名匹配、低申报检测（市场价格合理性）、9610三单一致性（订单/支付/物流匹配）、出口许可证（军民两用/稀土/加密）、原产地真实性、欧盟IOSS/VAT、特殊品（锂电/液体/化学品）。"""


# ─────────────────────────────────────────────────────────────────────────────
# 1. 供应商资质审核
# ─────────────────────────────────────────────────────────────────────────────

async def analyze_supplier(supplier: dict) -> dict:
    """供应商资质 LLM 审核，不可用时降级为规则引擎。"""
    from app.core.llm_gateway import get_llm_gateway
    gw = get_llm_gateway()

    user_msg = (
        f"供应商：{supplier.get('name')}\n"
        f"类型：{supplier.get('source_type')} | 国家：{supplier.get('country')}\n"
        f"营业执照：{supplier.get('business_license') or '未提供'} | 税号：{supplier.get('tax_id') or '未提供'}\n"
        f"开增值税专票：{supplier.get('has_invoice')} | 认证：{', '.join(supplier.get('certifications') or []) or '无'}\n"
        f"供货品类（HS前缀）：{', '.join(supplier.get('categories') or []) or '未知'}\n"
        f"地址：{supplier.get('address') or '未提供'}"
    )

    result = await gw.chat_json(_SUPPLIER_SYSTEM, user_msg, role="lifecycle_analysis")
    if result:
        return result

    logger.info("[LifecycleAnalyzer] 供应商审核降级为规则引擎: %s", supplier.get("name"))
    return _supplier_rule_fallback(supplier)


# ─────────────────────────────────────────────────────────────────────────────
# 2. 合同合规审查
# ─────────────────────────────────────────────────────────────────────────────

async def analyze_contract(contract: dict) -> dict:
    """合同合规 LLM 审查，不可用时降级。"""
    import re
    from app.core.llm_gateway import get_llm_gateway
    gw = get_llm_gateway()

    # 提取合同核心文本
    html = contract.get("content_html", "")
    text = re.sub(r"<[^>]+>", " ", html)[:1800]
    vars_info = str(contract.get("content_vars", {}))[:300]

    user_msg = (
        f"合同类型：{contract.get('contract_type')} | 贸易术语：{contract.get('delivery_term')}\n"
        f"货币：{contract.get('currency')} | 金额：{contract.get('total_amount')}\n"
        f"付款：{contract.get('payment_terms') or '未填'} | 交货：{contract.get('delivery_date') or '未填'}\n"
        f"质量标准：{contract.get('quality_terms') or '未填'}\n"
        f"合同变量：{vars_info}\n"
        f"合同正文（节选）：\n{text}"
    )

    result = await gw.chat_json(_CONTRACT_SYSTEM, user_msg, role="lifecycle_analysis")
    if result:
        return result

    logger.info("[LifecycleAnalyzer] 合同审查降级为规则引擎")
    return _contract_rule_fallback(contract)


# ─────────────────────────────────────────────────────────────────────────────
# 3. 报关单合规检查
# ─────────────────────────────────────────────────────────────────────────────

async def analyze_customs_declaration(declaration: dict) -> dict:
    """报关单 LLM 合规检查，不可用时返回空（规则检查已在 customs.py 中完成）。"""
    from app.core.llm_gateway import get_llm_gateway
    gw = get_llm_gateway()

    user_msg = (
        f"报关模式：{declaration.get('mode')} | HS编码：{declaration.get('hs_code')}\n"
        f"申报品名：{declaration.get('declared_name')} | 品牌：{declaration.get('brand') or '未填'}\n"
        f"申报价值：{declaration.get('declared_value')} {declaration.get('declared_currency')}\n"
        f"数量：{declaration.get('quantity')} {declaration.get('unit')}\n"
        f"原产地：{declaration.get('origin_country')} → 目的国：{declaration.get('dest_country')}\n"
        f"发货方：{declaration.get('shipper_name') or '未填'}\n"
        f"收货方：{declaration.get('consignee_name') or '未填'} / {declaration.get('consignee_address') or '未填'}\n"
        f"IOSS号：{declaration.get('ioss_number') or '无'} | 单据：{', '.join(declaration.get('documents') or []) or '无'}\n"
        f"出口许可证：{declaration.get('export_license_no') or '无'} | 原产地证书：{declaration.get('co_cert_no') or '无'}"
    )

    result = await gw.chat_json(_CUSTOMS_SYSTEM, user_msg, role="lifecycle_analysis")
    return result or {"passed": True, "issues": [], "_method": "llm_unavailable"}


# ─────────────────────────────────────────────────────────────────────────────
# 规则兜底（LLM 不可用时）
# ─────────────────────────────────────────────────────────────────────────────

def _supplier_rule_fallback(supplier: dict) -> dict:
    risks, score = [], 80
    if not supplier.get("business_license"):
        risks.append({"code":"NO_LICENSE","level":"error","message":"未提供营业执照","recommendation":"要求提供营业执照扫描件"})
        score -= 25
    if not supplier.get("has_invoice"):
        risks.append({"code":"NO_INVOICE","level":"warning","message":"无增值税专票，影响出口退税","recommendation":"核查跨境综试区无票免征政策"})
        score -= 10
    if not supplier.get("contact_email") and not supplier.get("contact_phone"):
        risks.append({"code":"NO_CONTACT","level":"warning","message":"联系信息不完整","recommendation":"补充联系方式"})
        score -= 5
    return {"risk_level": "high" if score < 60 else "medium" if score < 80 else "low",
            "score": max(0, score), "summary": f"规则引擎评估，{len(risks)} 项需关注",
            "risks": risks, "strengths": [], "verified_items": [], "_method": "rules_fallback"}


def _contract_rule_fallback(contract: dict) -> dict:
    issues, score = [], 70
    dt = contract.get("delivery_term", "")
    if dt == "EXW":
        issues.append({"code":"EXW_RISK","level":"warning","clause":"贸易术语","message":"EXW 买方全承风险，需确认清关能力","recommendation":"建议改为 FOB 或 CIF"})
    elif dt == "DDP":
        issues.append({"code":"DDP_RISK","level":"warning","clause":"贸易术语","message":"DDP 卖方需承担目的地清关及进口税","recommendation":"核查是否具备目的国进口资质"})
    if not contract.get("payment_terms"):
        issues.append({"code":"NO_PAYMENT","level":"error","clause":"付款条件","message":"付款条件未填写","recommendation":"明确定金比例和尾款触发条件"}); score -= 20
    if not contract.get("delivery_date"):
        issues.append({"code":"NO_DELIVERY","level":"error","clause":"交货期","message":"未约定交货日期","recommendation":"明确具体交货日期"}); score -= 15
    return {"score": max(0, score), "summary": f"规则引擎初步审查，{len(issues)} 项问题",
            "issues": issues, "strengths": [], "checklist": [], "_method": "rules_fallback"}
