"""
Compliance Service — 合规编排服务（完整管线编排 + 报告生成）。

职责:
  1. 迁入 chat.py 的 format_compliance_report / _empty_compliance_dict / _product_id
  2. 升级 full_compliance_pipeline: 集成事件总线 + 合规流水线 + 记忆树
  3. build_compliance_report: 统一报告生成（供 SSE / shopify.py / 导出共用）
  4. persist_compliance_memory: 合规结果持久化到记忆树

数据流转:
  用户消息 → NLU意图 → ComplianceService → RuleEngine → RAG → 记忆树 → 报告
"""

import hashlib
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from app.core.rule_engine import check_compliance, lookup_hs, lookup_vat, get_certifications
from app.core.nlu import parse_intent
from app.models.schemas import ComplianceResult


# ═══════════════════════════════════════════════════════
# 合规报告格式化（从 chat.py 迁入）
# ═══════════════════════════════════════════════════════

def format_compliance_report(product: str, country: str, result: dict) -> str:
    """Build human-readable markdown report from compliance check result."""
    lines = [
        f"## 📋 {product} → {country} 合规报告",
        "",
        f"### 🏷️ 商品归类",
        f"- HS编码: **{result['hs_code'] or '需人工核实'}**",
        f"- 品名: {result['hs_description']}",
        "",
        f"### 💰 税率",
        f"- {country}标准VAT: **{result['vat_rate']}%**",
        f"- 风险评分: **{result.get('risk_score', 0)}/100**",
        "",
        f"### 📜 认证要求 ({len(result['certifications'])}项)",
    ]
    for c in result["certifications"]:
        lines.append(f"- {c}")

    if result["risk_flags"]:
        lines.append("")
        lines.append("### ⚠️ 风险提示")
        for r in result["risk_flags"]:
            lines.append(f"- {r}")

    if result.get("logistics_flags"):
        lines.append("")
        lines.append("### 🚚 物流与运输")
        for item in result["logistics_flags"]:
            lines.append(f"- {item}")

    if result.get("customs_documents"):
        lines.append("")
        lines.append("### 🧾 清关材料建议")
        for item in result["customs_documents"]:
            lines.append(f"- {item}")

    if result.get("cultural_notes"):
        lines.append("")
        lines.append("### 🌐 市场与标签注意事项")
        for item in result["cultural_notes"]:
            lines.append(f"- {item}")

    if result.get("remediation_steps"):
        lines.append("")
        lines.append("### 🛠️ 整改建议")
        for item in result["remediation_steps"]:
            lines.append(f"- {item}")

    lines.append("")
    lines.append("### ✅ 出口待办清单")
    for i, item in enumerate(result["checklist"], 1):
        lines.append(f"{i}. {item}")

    return "\n".join(lines)


def empty_compliance_dict() -> dict:
    """Return a schema-valid empty compliance result for graceful fallback."""
    return {
        "hs_code": "",
        "hs_description": "（解析失败，建议补充产品材质、用途、型号后重试）",
        "vat_rate": 0.0,
        "certifications": [],
        "risk_level": "low",
        "risk_score": 0,
        "risk_flags": [],
        "logistics_flags": [],
        "customs_documents": [],
        "cultural_notes": [],
        "remediation_steps": ["补充产品用途、材质、是否带电/带无线功能后重新发起检查"],
        "checklist": [],
    }


def build_product_id(product: str, country: str) -> str:
    """Build a stable local product id for project memory."""
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", f"{product}_{country}").strip("_")
    digest = hashlib.sha1(f"{product}:{country}".encode("utf-8")).hexdigest()[:8]
    return f"{slug[:40] or 'product'}_{digest}"


# ═══════════════════════════════════════════════════════
# 完整合规管线
# ═══════════════════════════════════════════════════════

async def full_compliance_pipeline(message: str) -> dict:
    """End-to-end compliance check pipeline.

    1. Parse intent (NLU)
    2. Run rule engine (deterministic)
    3. Enrich with RAG context
    4. Persist to memory tree

    Returns:
        {
            intent: dict,
            compliance: dict | None,
            report: str | None,
            error: str | None,
        }
    """
    intent = parse_intent(message)
    product = intent.get("product", "")
    country = intent.get("target_country", "")

    if not product:
        return {
            "intent": intent,
            "error": "未能识别产品名称，请描述更具体一些",
            "compliance": None,
            "report": None,
        }

    # 规则引擎检查
    try:
        compliance_dict = check_compliance(product, country)
    except Exception:
        compliance_dict = empty_compliance_dict()

    # 生成报告
    report = format_compliance_report(product, country, compliance_dict)

    # RAG 补充
    rag_context = ""
    try:
        from app.core.rag import retrieve_context, format_context_for_assistant
        rag_results = retrieve_context(f"{product} 出口 {country} 合规要求")
        if rag_results:
            rag_context = format_context_for_assistant(rag_results)
            report += f"\n\n---\n{rag_context}"
    except Exception:
        pass

    return {
        "intent": intent,
        "compliance": compliance_dict,
        "report": report,
        "error": None,
    }


async def build_compliance_report(
    product: str,
    country: str,
    intent: Optional[dict] = None,
    include_rag: bool = True,
) -> dict:
    """统一合规报告生成（供 SSE / shopify.py / 导出共用）。

    Args:
        product: 产品名称
        country: 目标国家
        intent: NLU 解析结果（可选，不传则自动解析）
        include_rag: 是否包含 RAG 补充

    Returns:
        {
            compliance_dict: dict,
            compliance_result: ComplianceResult,
            report: str,
            rag_results: list,
            product_id: str,
        }
    """
    if not intent:
        intent = parse_intent(f"{product}出口{country}")

    # 规则引擎
    try:
        compliance_dict = check_compliance(product, country)
        compliance_result = ComplianceResult(**compliance_dict)
    except Exception:
        compliance_dict = empty_compliance_dict()
        compliance_result = ComplianceResult(**compliance_dict)

    # 格式化报告
    report = format_compliance_report(product, country, compliance_dict)

    # RAG 补充
    rag_results = []
    if include_rag:
        try:
            from app.core.rag import retrieve_context, format_context_for_assistant
            rag_results = retrieve_context(f"{product} 出口 {country} 合规要求")
            if rag_results:
                report += f"\n\n---\n{format_context_for_assistant(rag_results)}"
        except Exception:
            pass

    product_id = build_product_id(product, country)

    return {
        "compliance_dict": compliance_dict,
        "compliance_result": compliance_result,
        "report": report,
        "rag_results": rag_results,
        "product_id": product_id,
    }


# ═══════════════════════════════════════════════════════
# 记忆持久化
# ═══════════════════════════════════════════════════════

async def persist_compliance_memory(
    product: str,
    country: str,
    compliance_dict: dict,
    report: str,
    session_id: Optional[str] = None,
    user_id: str = "default",
    product_id: Optional[str] = None,
) -> None:
    """合规结果持久化 — 写入记忆树 + 会话存储 + 项目记忆。

    非阻断: 任何存储失败不影响主流程。
    """
    try:
        # 1. 会话存储（L4）
        from app.storage.layer_registry import registry
        sid = session_id or f"session_{hashlib.sha1(report[:50].encode()).hexdigest()[:8]}"
        registry.session.save_message(user_id, sid, "user", f"{product}出口{country}合规检查")
        registry.session.save_message(user_id, sid, "assistant", report, compliance_dict)
        registry.session.save_context(user_id, sid, "current_product", product)
        registry.session.save_context(user_id, sid, "current_market", country)
    except Exception:
        pass

    try:
        # 2. 项目记忆（L2）
        from app.storage.layer_registry import registry
        pid = product_id or build_product_id(product, country)
        registry.project.save_compliance_record(
            product_id=pid,
            product_name=product,
            target_market=country,
            result=compliance_dict,
            session_id=session_id or "",
        )
    except Exception:
        pass

    try:
        # 3. 记忆树（L0-L3）
        from app.core.memory_tree import MemoryTree
        pid = product_id or build_product_id(product, country)
        tree = MemoryTree(pid)
        risk_level = compliance_dict.get("risk_level", "unknown")
        risk_score = compliance_dict.get("risk_score", 0)
        await tree.append_fragment(
            source="compliance",
            content=(
                f"合规检查: {product}→{country}, "
                f"HS={compliance_dict.get('hs_code', 'N/A')}, "
                f"VAT={compliance_dict.get('vat_rate', 0)}%, "
                f"风险={risk_level}({risk_score}/100), "
                f"认证{len(compliance_dict.get('certifications', []))}项"
            ),
            metadata={
                "event_type": f"compliance:check_{'passed' if risk_level != 'high' else 'failed'}",
                "risk_level": risk_level,
                "risk_score": risk_score,
                "hs_code": compliance_dict.get("hs_code", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception:
        pass
