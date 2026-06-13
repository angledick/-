"""合规数据查询与风险评分层 (Compliance Data & Scoring).

职责:
  - 合规数据查询: HS编码、VAT税率、认证矩阵（通过 L0 raw_store）
  - 风险规则评估: 风险标签、物流提示、单证清单、文化备注（从 JSON 配置驱动）
  - 风险评分: 确定性 0-100 评分 + 补救步骤生成

数据流转:
  - L0 hscodes/vat/cert_matrix → 合规数据层读取（通过 registry.raw）
  - 使用条件: 用户明确指定产品+国家时，执行确定性合规检查
  - 写入: L5 event_store(action_chain)
  - 显式错误: 配置/数据不可用时向上传播异常，禁止静默降级

规则数据源:
  - data/raw/compliance_rules/*.json — 风险关键词、物流规则、单证清单、文化备注、评分权重
"""

import json
from pathlib import Path
from typing import Optional
from app.storage.layer_registry import registry

# ── 规则数据加载 ────────────────────────────────────

_RULES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "compliance_rules"


def _load_rule(name: str) -> dict:
    """加载指定的合规规则 JSON 文件，缺失时抛出 FileNotFoundError"""
    path = _RULES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"合规规则文件缺失: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# 模块加载时读取所有规则（只读一次）
_risk_cfg = _load_rule("risk_keywords")
_logistics_cfg = _load_rule("logistics_rules")
_customs_cfg = _load_rule("customs_checklist")
_cultural_cfg = _load_rule("cultural_notes")
_score_cfg = _load_rule("score_weights")


# ── 数据查询（来自 L0 raw_store）─────────────────────


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


# ── 规则检查（从 JSON 配置驱动）─────────────────────


def _match_country(country: str, cfg_entry: dict) -> bool:
    """判断 country 是否匹配配置项（支持 countries 列表或直接键名）"""
    countries = cfg_entry.get("countries", [])
    return country in countries


def get_risk_flags(country: str, product: str = "") -> list[str]:
    """Return compliance risk flags."""
    flags = []

    # High-risk categories
    high_risk_keywords = _risk_cfg.get("high_risk_keywords", [])
    if any(kw in product for kw in high_risk_keywords):
        msg_tpl = _risk_cfg.get("high_risk_message", "⚠️ 「{product}」属高合规风险品类")
        flags.append(msg_tpl.replace("{product}", product))

    # Country-specific risks
    for key, entry in _risk_cfg.get("country_risks", {}).items():
        if "countries" in entry:
            if _match_country(country, entry):
                flags.append(entry["message"])
        elif country == key:
            flags.append(entry["message"])

    # BATTERY special case
    battery_keywords = _risk_cfg.get("battery_keywords", [])
    if any(kw in product for kw in battery_keywords):
        flags.append(_risk_cfg.get("battery_message", "⚠️ 含锂电池产品需额外提供MSDS和UN38.3检测报告"))

    return flags


def get_logistics_flags(country: str, product: str = "") -> list[str]:
    """Return logistics and transport compliance hints."""
    flags = []

    battery_keywords = _logistics_cfg.get("battery_keywords", [])
    if any(kw in product for kw in battery_keywords):
        flags.extend(_logistics_cfg.get("battery_flags", []))

    electronics_keywords = _logistics_cfg.get("electronics_keywords", [])
    if any(kw in product for kw in electronics_keywords):
        flags.append(_logistics_cfg.get("electronics_flag", ""))

    for key, entry in _logistics_cfg.get("country_flags", {}).items():
        if "countries" in entry:
            if _match_country(country, entry):
                flags.append(entry["message"])
        elif country == key:
            flags.append(entry["message"])

    return flags


def get_customs_documents(country: str, product: str = "") -> list[str]:
    """Return recommended customs clearance document checklist."""
    documents = list(_customs_cfg.get("base_documents", []))

    for cond in _customs_cfg.get("conditional_documents", []):
        if "countries" in cond and country in cond["countries"]:
            documents.extend(cond["documents"])
        if "product_keywords" in cond and any(kw in product for kw in cond["product_keywords"]):
            documents.extend(cond["documents"])

    return documents


def get_cultural_notes(country: str, product: str = "") -> list[str]:
    """Return lightweight cultural and labeling notes for pre-market review."""
    notes = []

    for key, entry in _cultural_cfg.get("country_notes", {}).items():
        if "countries" in entry:
            if _match_country(country, entry):
                notes.append(entry["message"])
        elif country == key:
            notes.append(entry["message"])

    for entry in _cultural_cfg.get("product_notes", []):
        if any(kw in product for kw in entry.get("keywords", [])):
            notes.append(entry["message"])

    return notes


def score_risk(
    hs_found: bool,
    certifications: list[str],
    risk_flags: list[str],
    logistics_flags: list[str],
    product: str = "",
) -> int:
    """Calculate a deterministic 0-100 risk score for UI and triage."""
    score = _score_cfg.get("base_score", 15)
    if not hs_found:
        score += _score_cfg.get("no_hs_penalty", 20)
    cert_max = _score_cfg.get("cert_max_count", 6)
    cert_w = _score_cfg.get("cert_weight", 4)
    score += min(len(certifications), cert_max) * cert_w
    score += len(risk_flags) * _score_cfg.get("risk_flag_weight", 12)
    score += len(logistics_flags) * _score_cfg.get("logistics_flag_weight", 5)
    high_risk_kws = _score_cfg.get("high_risk_keywords", [])
    if any(kw in product for kw in high_risk_kws):
        score += _score_cfg.get("high_risk_product_bonus", 15)
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
    """Run full compliance check — deterministic compliance data path.

    This is the primary MVP compliance pipeline:
      product + country -> HS lookup -> VAT lookup -> certifications -> risk flags

    数据流时序:
      1. 用户输入产品+国家
      2. -> 合规数据层读取 L0 (hscodes/vat/cert)
      3. -> 写入 L5 action_chain
      4. -> 组装 ComplianceResult

    Returns a dict ready to feed into ComplianceResult schema.
    """
    hs = lookup_hs(product)
    hs_code = hs["code"] if hs else ""
    hs_desc = hs["description_cn"] if hs else f"{product}（未精确匹配，建议人工确认HS编码）"

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
        f"确认HS编码 {hs_code or '(需人工核实)'}",
        f"准备{country}进口关税核算（VAT {vat}%）",
    ]
    checklist += [f"获取{c}" for c in certs[:3]]  # top-3 certs
    checklist += [f"准备{d}" for d in documents[:3]]
    checklist += [r.replace("⚠️ ", "") for r in risks]

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
