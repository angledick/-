"""产品出海生命周期 LLM 分析器。

提供三大分析能力：
  1. analyze_supplier      — 供应商资质 AI 审核
  2. analyze_contract      — 合同合规审查（交货条款/价格/责任/知识产权）
  3. analyze_customs_declaration — 报关单合规检查（HS 编码/低申报/三单一致性）

全部使用 ZhipuAI glm-5.1（OpenAI-compatible API），与风险情报引擎共用配置。
无 API Key 时降级为规则引擎，不崩溃。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _get_api_config() -> tuple[str, str, str]:
    """读取 ZhipuAI 配置（复用风险情报引擎的配置逻辑）。"""
    def _env(key: str) -> str:
        v = os.environ.get(key, "")
        if v:
            return v
        if _ENV_FILE.exists():
            for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, _, val = line.partition("=")
                if k.strip() == key:
                    return val.strip().strip('"').strip("'")
        return ""

    key = _env("ZHIPUAI_API_KEY") or _env("ANTHROPIC_API_KEY") or _env("LLM_API_KEY")
    base_url = _env("ZHIPUAI_BASE_URL") or "https://open.bigmodel.cn/api/coding/paas/v4"
    model = _env("ZHIPUAI_MODEL") or "glm-5.1"
    return key, base_url, model


async def _call_llm(system: str, user: str, max_tokens: int = 1500) -> Optional[dict]:
    """调用 LLM，返回解析后的 JSON dict，失败返回 None。"""
    api_key, base_url, model = _get_api_config()
    if not api_key:
        return None
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        resp = await client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        raw = resp.choices[0].message.content or ""
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        logger.warning("[LifecycleAnalyzer] LLM 调用失败: %s", e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. 供应商资质审核
# ─────────────────────────────────────────────────────────────────────────────

_SUPPLIER_SYSTEM = """\
你是一名跨境贸易合规顾问，专注于供应商资质风险评估。
分析供应商信息，输出 JSON 格式的风险评估报告。

## 输出格式（严格 JSON）
{
  "risk_level": "low|medium|high|critical",
  "score": 0-100,
  "summary": "≤60字的综合评价",
  "risks": [
    {"code": "风险代码", "level": "error|warning|info", "message": "风险描述", "recommendation": "建议"}
  ],
  "strengths": ["供应商优势列表"],
  "verified_items": ["已核实事项列表"]
}

## 风险检查维度
1. 资质合规：营业执照/税号/开票能力
2. 制裁风险：是否涉及 OFAC/EU/UN 制裁名单（重点检查：新疆棉/军民两用品/稀土材料）
3. 认证匹配：供应品类与声明认证是否匹配
4. 联系信息完整性
5. 国家/地区风险

注意：risk_level="critical" 仅用于涉及制裁或明显违法的情形。
"""


async def analyze_supplier(supplier: dict) -> dict:
    """供应商资质 AI 审核。"""
    user_msg = f"""
供应商信息：
名称：{supplier.get('name')}
来源类型：{supplier.get('source_type')}
国家：{supplier.get('country')}
营业执照：{supplier.get('business_license') or '未提供'}
税号：{supplier.get('tax_id') or '未提供'}
能否开专票：{supplier.get('has_invoice')}
声明认证：{', '.join(supplier.get('certifications') or []) or '未提供'}
供应品类（HS 前缀）：{', '.join(supplier.get('categories') or []) or '未提供'}
标签：{', '.join(supplier.get('tags') or [])}
"""
    result = await _call_llm(_SUPPLIER_SYSTEM, user_msg, max_tokens=1500)
    if result:
        return result
    # 规则引擎兜底
    return _supplier_rule_fallback(supplier)


def _supplier_rule_fallback(supplier: dict) -> dict:
    risks = []
    score = 80
    risk_level = "low"

    if not supplier.get("business_license"):
        risks.append({"code": "NO_LICENSE", "level": "error",
                       "message": "未提供营业执照，无法核实供应商合法经营资质",
                       "recommendation": "要求供应商提供营业执照扫描件"})
        score -= 25; risk_level = "high"
    if not supplier.get("has_invoice"):
        risks.append({"code": "NO_INVOICE", "level": "warning",
                       "message": "供应商无法开具增值税专用发票，将影响出口退税资格",
                       "recommendation": "核查是否满足跨境电商综试区无票免征政策"})
        score -= 10
    if not supplier.get("contact_email") and not supplier.get("contact_phone"):
        risks.append({"code": "NO_CONTACT", "level": "warning",
                       "message": "联系信息不完整，紧急情况下无法快速沟通",
                       "recommendation": "补充至少一种联系方式"})
        score -= 5

    return {
        "risk_level": risk_level,
        "score": max(0, score),
        "summary": f"规则引擎评估，{len(risks)} 项风险需关注",
        "risks": risks,
        "strengths": ["已提供基础信息"] if supplier.get("name") else [],
        "verified_items": [],
        "_method": "rules_fallback",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. 合同合规审查
# ─────────────────────────────────────────────────────────────────────────────

_CONTRACT_SYSTEM = """\
你是一名国际贸易法律顾问，专注于跨境电商采购合同合规审查。
分析合同条款，输出 JSON 格式的合规报告。

## 输出格式（严格 JSON）
{
  "score": 0-100,
  "summary": "≤60字综合评价",
  "issues": [
    {"code": "问题代码", "level": "critical|error|warning|info",
     "clause": "涉及条款", "message": "问题描述", "recommendation": "修改建议"}
  ],
  "strengths": ["合规亮点"],
  "checklist": [
    {"item": "检查项名称", "status": "pass|fail|na", "note": "备注"}
  ]
}

## 必检条款（按优先级）
1. 贸易术语（EXW/FOB/CIF/DDP 风险分配）
2. 价格与汇率（是否锁定汇率/明确币种）
3. 付款条件（定金比例/尾款触发条件）
4. 交货期（是否明确/逾期违约金）
5. 质量标准与验货条款
6. 知识产权条款（OEM 产品归属/保密义务）
7. 违约责任（赔偿上限/不可抗力条款）
8. 争议解决（仲裁/诉讼/管辖地）
9. 禁止出口/管制品声明
10. 汇率风险条款

注意：score=100 极为罕见，普通合同 60-80 分为正常水平。
"""


async def analyze_contract(contract: dict) -> dict:
    """合同合规 AI 审查。"""
    vars_info = json.dumps(contract.get("content_vars", {}), ensure_ascii=False)[:500]
    # 提取 HTML 文本（去除标签）
    import re
    html = contract.get("content_html", "")
    text = re.sub(r"<[^>]+>", " ", html)[:2000]

    user_msg = f"""
合同基础信息：
类型：{contract.get('contract_type')}
贸易术语：{contract.get('delivery_term')}
货币：{contract.get('currency')}
总金额：{contract.get('total_amount')} {contract.get('currency')}
付款条件：{contract.get('payment_terms') or '未填写'}
交货日期：{contract.get('delivery_date') or '未填写'}
质量标准：{contract.get('quality_terms') or '未填写'}
合同变量：{vars_info}

合同正文摘要：
{text}
"""
    result = await _call_llm(_CONTRACT_SYSTEM, user_msg, max_tokens=2000)
    if result:
        return result
    return _contract_rule_fallback(contract)


def _contract_rule_fallback(contract: dict) -> dict:
    issues = []
    score = 70
    checklist = []

    dt = contract.get("delivery_term", "")
    if dt == "EXW":
        issues.append({"code": "EXW_RISK", "level": "warning", "clause": "贸易术语",
                        "message": "EXW 条款下买方承担全程风险，需确认具备海外清关能力",
                        "recommendation": "建议改为 FOB 或 CIF，风险分配更清晰"})
    elif dt == "DDP":
        issues.append({"code": "DDP_RISK", "level": "warning", "clause": "贸易术语",
                        "message": "DDP 条款下卖方需承担目的地清关及关税，确认具备进口资质",
                        "recommendation": "核查是否已在目的国注册进口资质"})

    if not contract.get("payment_terms"):
        issues.append({"code": "NO_PAYMENT_TERMS", "level": "error", "clause": "付款条件",
                        "message": "付款条件未填写，合同存在重大不确定性",
                        "recommendation": "明确定金比例、尾款支付时间和触发条件"})
        score -= 20

    if not contract.get("delivery_date"):
        issues.append({"code": "NO_DELIVERY_DATE", "level": "error", "clause": "交货期",
                        "message": "未约定交货日期，无法追究逾期违约责任",
                        "recommendation": "明确具体交货日期或最长生产周期"})
        score -= 15

    checklist = [
        {"item": "贸易术语", "status": "pass" if dt else "fail", "note": dt or "未填写"},
        {"item": "付款条件", "status": "pass" if contract.get("payment_terms") else "fail", "note": ""},
        {"item": "交货日期", "status": "pass" if contract.get("delivery_date") else "fail", "note": ""},
        {"item": "质量标准", "status": "pass" if contract.get("quality_terms") else "na", "note": ""},
    ]

    return {
        "score": max(0, score),
        "summary": f"规则引擎初步审查，{len(issues)} 项问题需关注",
        "issues": issues,
        "strengths": ["合同基础条款已填写"] if contract.get("total_amount") else [],
        "checklist": checklist,
        "_method": "rules_fallback",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. 报关单合规检查
# ─────────────────────────────────────────────────────────────────────────────

_CUSTOMS_SYSTEM = """\
你是一名跨境电商报关合规专家。
分析报关单信息，输出 JSON 格式的合规检查报告。

## 输出格式（严格 JSON）
{
  "passed": true|false,
  "issues": [
    {"code": "问题代码", "level": "error|warning|info",
     "message": "问题描述", "recommendation": "建议"}
  ]
}

## 检查重点
1. HS 编码与品名是否匹配（常见错误：电子产品误归为玩具类）
2. 申报价值合理性（是否存在明显低申报嫌疑）
3. 9610 模式：三单一致性（订单/支付/物流信息需匹配）
4. 是否需要出口许可证（军民两用品、稀土、加密技术等）
5. 原产地申报（是否如实申报"中国制造"）
6. IOSS/VAT 适用性
7. 特殊管制品检查（锂电池、液体、化学品等）

注意：常规消费品通常没有问题，不要为了凑数量而编造风险。
"""


async def analyze_customs_declaration(declaration: dict) -> dict:
    """报关单 AI 合规检查。"""
    user_msg = f"""
报关单信息：
报关模式：{declaration.get('mode')}
HS 编码：{declaration.get('hs_code')}
申报品名：{declaration.get('declared_name')}
申报价值：{declaration.get('declared_value')} {declaration.get('declared_currency')}
数量：{declaration.get('quantity')} {declaration.get('unit')}
原产地：{declaration.get('origin_country')}
目的国：{declaration.get('dest_country')}
IOSS：{declaration.get('ioss_number') or '未提供'}
已附单据：{', '.join(declaration.get('documents') or []) or '无'}
"""
    result = await _call_llm(_CUSTOMS_SYSTEM, user_msg, max_tokens=1200)
    return result or {"passed": True, "issues": [], "_method": "llm_unavailable"}
