"""Compliance rule engine — SOP-based deterministic checks.

Architecture: Rule engine handles high-frequency, deterministic cases.
AstraAssistant handles fuzzy NLU and ambiguous queries. Neither crosses into the other's lane.

数据流转:
  - L0 hscodes/vat/cert_matrix → RuleEngine 读取（通过 registry.raw）
  - 使用条件: 用户明确指定产品+国家时，执行确定性合规检查
  - 写入: L5 event_store(action_chain)
  - 降级: 若 L0 数据不可用，返回空结果 + 标记，不报错
"""

from typing import Optional
from app.storage.layer_registry import registry


def lookup_hs(product_name: str) -> Optional[dict]:
    """Fuzzy match product name to HS code entry.

    数据源: L0 raw_store (data/raw/hs_codes/_all.json)
    使用条件: 合规检查需要匹配产品到 HS 编码时

    Returns:
        {"code": "9405.40", "description_cn": "LED灯具...", ...} or None
    """
    return registry.raw.lookup_hs(product_name)


def lookup_vat(country: str) -> float:
    """Look up standard VAT rate for target country.

    数据源: L0 raw_store (data/raw/vat_rates/_all.json)
    使用条件: 查询目标国家的 VAT 税率时

    Returns:
        VAT rate as percentage (e.g. 19.0 for Germany), 0.0 if unknown.
    """
    return registry.raw.lookup_vat(country)


def get_certifications(country: str, product_hint: str = "") -> list[str]:
    """Return required certifications for target country.

    数据源: L0 raw_store (data/raw/certifications/cert_matrix.json)
    使用条件: 查询目标国家所需产品认证时

    Args:
        country: Target market country name
        product_hint: Optional product description for filtering
    """
    return registry.raw.get_certifications(country)


def get_risk_flags(country: str, product: str = "") -> list[str]:
    """Return compliance risk flags."""
    flags = []

    # High-risk categories
    high_risk_keywords = ["\u533b\u7597", "\u7535\u6c60", "\u9502", "\u98df\u54c1", "\u836f\u54c1", "\u5316\u5986\u54c1"]
    if any(kw in product for kw in high_risk_keywords):
        flags.append(f"\u26a0\ufe0f \u300c{product}\u300d\u5c5e\u4e8e\u9ad8\u5408\u89c4\u98ce\u9669\u54c1\u7c7b\uff0c\u5efa\u8bae\u989d\u5916\u8fdb\u884c\u5b89\u5168\u68c0\u6d4b")

    # Country-specific risks
    if country in ("\u5fb7\u56fd", "\u6cd5\u56fd", "\u610f\u5927\u5229", "\u897f\u73ed\u7259", "\u8377\u5170", "\u6bd4\u5229\u65f6"):
        flags.append("\u26a0\ufe0f \u6b27\u76dfGPSR\u901a\u7528\u4ea7\u54c1\u5b89\u5168\u6cd5\u89c4(2024\u5e7412\u6708\u751f\u6548)\u6b63\u5728\u66ff\u6362\u539fGPSD\uff0c\u8bf7\u63d0\u524d\u51c6\u5907")
    if country == "\u82f1\u56fd":
        flags.append("\u26a0\ufe0f \u82f1\u56fd\u8131\u6b27\u540eUKCA\u8ba4\u8bc1\u4e0eCE\u8ba4\u8bc1\u4e0d\u4e92\u8ba4\uff0c\u9700\u5355\u72ec\u7533\u8bf7")
    if country == "\u7f8e\u56fd":
        flags.append("\u26a0\ufe0f \u7f8e\u56fd\u5404\u5ddeSales Tax\u7a0e\u7387\u4e0d\u540c\uff0c\u5efa\u8bae\u6309\u5dde\u72ec\u7acb\u6838\u7b97")

    # BATTERY special case
    if "\u7535\u6c60" in product or "\u9502" in product:
        flags.append("\u26a0\ufe0f \u542b\u9502\u7535\u6c60\u4ea7\u54c1\u9700\u989d\u5916\u63d0\u4f9bMSDS\u548cUN38.3\u68c0\u6d4b\u62a5\u544a")

    return flags


def get_logistics_flags(country: str, product: str = "") -> list[str]:
    """Return logistics and transport compliance hints."""
    flags = []
    battery_keywords = ["电池", "锂", "蓄电池", "充电宝"]
    electronics_keywords = ["LED", "灯", "手机", "摄像", "电子", "电器", "无线"]

    if any(kw in product for kw in battery_keywords):
        flags.extend([
            "含电池/锂电池产品需确认 UN38.3、MSDS、运输鉴定书是否齐备",
            "空运/海运需按危险品或限制货物规则选择包装、标签和承运渠道",
        ])

    if any(kw in product for kw in electronics_keywords):
        flags.append("电子电器产品建议提前核对电压、插头制式、能效标签和电磁兼容要求")

    if country in ("德国", "法国", "意大利", "西班牙", "荷兰", "比利时"):
        flags.append("欧盟市场建议准备欧盟责任人/授权代表信息，确保标签和说明书可追溯")

    if country == "美国":
        flags.append("美国市场需按州/平台要求核对 Sales Tax、FCC/UL 适用性和进口商信息")

    return flags


def get_customs_documents(country: str, product: str = "") -> list[str]:
    """Return recommended customs clearance document checklist."""
    documents = [
        "商业发票（Commercial Invoice）",
        "装箱单（Packing List）",
        "运输单据（提单/Air Waybill/快递面单）",
        "产品规格书与材质说明",
        "HS 编码归类依据",
    ]

    if country in ("德国", "法国", "意大利", "西班牙", "荷兰", "比利时", "英国"):
        documents.extend([
            "符合性声明（DoC，如适用）",
            "CE/UKCA 技术文件摘要（如适用）",
            "包装法/EPR 注册信息（如适用）",
        ])

    if any(kw in product for kw in ["电池", "锂", "蓄电池"]):
        documents.extend(["MSDS", "UN38.3 测试报告", "危险品/非危鉴定书"])

    if any(kw in product for kw in ["玩具", "儿童"]):
        documents.append("玩具安全测试报告（EN71/CPSIA 等，按市场适用）")

    return documents


def get_cultural_notes(country: str, product: str = "") -> list[str]:
    """Return lightweight cultural and labeling notes for pre-market review."""
    notes = []
    if country in ("德国", "法国", "意大利", "西班牙", "荷兰", "比利时"):
        notes.append("面向欧盟消费者销售时，建议提供目标国语言标签、警示语和售后联系信息")
    if country == "德国":
        notes.append("德国消费者对环保回收、包装法和产品可维修性较敏感，宣传文案应避免夸大环保声明")
    if country == "法国":
        notes.append("法国市场建议优先准备法语说明书、Triman 回收标识和消费者保护信息")
    if country == "日本":
        notes.append("日本市场重视包装完整度、日文说明和售后响应，电器类需特别核对 PSE 标识")
    if country == "韩国":
        notes.append("韩国市场建议准备韩文标签和 KC/KCC 标识说明，避免遗漏进口商信息")
    if country == "美国":
        notes.append("美国市场需注意州级标签、儿童产品警告语和平台合规声明差异")
    if any(kw in product for kw in ["儿童", "玩具", "婴儿"]):
        notes.append("儿童相关产品需避免小部件、误食、年龄分级和警示语缺失导致的平台下架风险")
    return notes


def score_risk(
    hs_found: bool,
    certifications: list[str],
    risk_flags: list[str],
    logistics_flags: list[str],
    product: str = "",
) -> int:
    """Calculate a deterministic 0-100 risk score for UI and triage."""
    score = 15
    if not hs_found:
        score += 20
    score += min(len(certifications), 6) * 4
    score += len(risk_flags) * 12
    score += len(logistics_flags) * 5
    if any(kw in product for kw in ["医疗", "电池", "锂", "食品", "药品", "化妆品", "儿童", "玩具"]):
        score += 15
    return max(0, min(score, 100))


def risk_level_from_score(score: int) -> str:
    """Map numeric risk score to UI risk level."""
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def build_remediation_steps(
    hs_code: str,
    certifications: list[str],
    risk_flags: list[str],
    logistics_flags: list[str],
) -> list[str]:
    """Build prioritized remediation steps from deterministic findings."""
    steps = []
    if not hs_code:
        steps.append("先完成 HS 编码人工复核，避免税则、认证和清关路径全部偏移")
    if certifications:
        steps.append(f"按优先级准备核心认证材料：{', '.join(certifications[:3])}")
    if logistics_flags:
        steps.append("将物流限制项同步给货代/承运商，确认包装、标签和运输渠道")
    if risk_flags:
        steps.append("针对风险提示逐项补充证明文件，并保留可追溯记录")
    if not steps:
        steps.append("保留当前合规资料，并按目标市场法规变更进行周期性复核")
    return steps


def check_compliance(product: str, country: str) -> dict:
    """Run full compliance check — deterministic rule engine path.

    This is the primary MVP compliance pipeline:
      product + country -> HS lookup -> VAT lookup -> certifications -> risk flags

    数据流时序:
      1. 用户输入产品+国家
      2. -> RL RuleEngine 读取 L0 (hscodes/vat/cert)
      3. -> 写入 L5 action_chain
      4. -> 组装 ComplianceResult

    Returns a dict ready to feed into ComplianceResult schema.
    """
    hs = lookup_hs(product)
    hs_code = hs["code"] if hs else ""
    hs_desc = hs["description_cn"] if hs else f"{product}\uff08\u672a\u7cbe\u786e\u5339\u914d\uff0c\u5efa\u8bae\u4eba\u5de5\u786e\u8ba4HS\u7f16\u7801\uff09"

    vat = lookup_vat(country)
    certs = get_certifications(country, product)
    risks = get_risk_flags(country, product)
    logistics = get_logistics_flags(country, product)
    documents = get_customs_documents(country, product)
    cultural_notes = get_cultural_notes(country, product)
    risk_score = score_risk(bool(hs), certs, risks, logistics, product)
    remediation_steps = build_remediation_steps(hs_code, certs, risks, logistics)

    # Build checklist
    checklist = [
        f"\u786e\u8ba4HS\u7f16\u7801 {hs_code or '(\u9700\u4eba\u5de5\u6838\u5b9e)'}",
        f"\u51c6\u5907{country}\u8fdb\u53e3\u5173\u7a0e\u6838\u7b97\uff08VAT {vat}%\uff09",
    ]
    checklist += [f"\u83b7\u53d6{c}" for c in certs[:3]]  # top-3 certs
    checklist += [f"\u51c6\u5907{d}" for d in documents[:3]]
    checklist += [r.replace("\u26a0\ufe0f ", "") for r in risks]

    return {
        "hs_code": hs_code,
        "hs_description": hs_desc,
        "vat_rate": vat,
        "certifications": certs,
        "risk_level": risk_level_from_score(risk_score),
        "risk_score": risk_score,
        "risk_flags": risks,
        "logistics_flags": logistics,
        "customs_documents": documents,
        "cultural_notes": cultural_notes,
        "remediation_steps": remediation_steps,
        "checklist": checklist,
    }
