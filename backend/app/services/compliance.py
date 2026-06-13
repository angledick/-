"""
Compliance Service — 合规报告生成与记忆持久化。

职责:
  1. format_compliance_report: 合规报告 Markdown 格式化
  2. build_compliance_report: 统一报告生成（供 SSE / shopify.py / 导出共用）
  3. persist_compliance_memory: 合规结果持久化到记忆树

数据流转:
  用户消息 → NLU意图 → ComplianceRules(Tool) → RAG → 报告 → 记忆树
"""

import hashlib
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from app.core.compliance_rules import check_compliance
from app.api.chat_stream import parse_intent
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


def build_product_id(product: str, country: str) -> str:
    """Build a stable local product id for project memory."""
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", f"{product}_{country}").strip("_")
    digest = hashlib.sha1(f"{product}:{country}".encode("utf-8")).hexdigest()[:8]
    return f"{slug[:40] or 'product'}_{digest}"


async def _sdk_enhance_report(
    product: str, country: str, compliance_dict: dict, report: str
) -> str:
    """委托 SDK 对确定性检查结果做补充分析和风险提示。"""
    from app.services.astra_assistant import AstraAssistant
    assistant = AstraAssistant()
    sdk_result = await assistant.run_task(
        prompt_name="compliance_report_enhance",
        context={
            "product": product,
            "country": country,
            "hs_code": compliance_dict.get("hs_code", "未知"),
            "risk_level": compliance_dict.get("risk_level", "unknown"),
            "risk_score": str(compliance_dict.get("risk_score", 0)),
            "certifications": ", ".join(compliance_dict.get("certifications", [])) or "无",
            "risk_flags": ", ".join(compliance_dict.get("risk_flags", [])) or "无",
        },
    )
    if isinstance(sdk_result, dict):
        enhance_lines = ["\n---\n", "### 🤖 AI 深度分析\n"]
        if sdk_result.get("risk_interpretation"):
            enhance_lines.append(f"**风险解读:** {sdk_result['risk_interpretation']}\n")
        if sdk_result.get("cert_gaps"):
            enhance_lines.append("**认证缺口:**")
            for gap in sdk_result["cert_gaps"]:
                enhance_lines.append(f"- {gap}")
        if sdk_result.get("hidden_risks"):
            enhance_lines.append("\n**隐藏风险:**")
            for risk in sdk_result["hidden_risks"]:
                enhance_lines.append(f"- {risk}")
        if sdk_result.get("priority_actions"):
            enhance_lines.append("\n**优先行动:**")
            for i, action in enumerate(sdk_result["priority_actions"], 1):
                enhance_lines.append(f"{i}. {action}")
        if sdk_result.get("overall_advice"):
            enhance_lines.append(f"\n**综合建议:** {sdk_result['overall_advice']}")
        if len(enhance_lines) > 3:
            return report + "\n".join(enhance_lines)
    return report


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
    compliance_dict = check_compliance(product, country)
    compliance_result = ComplianceResult(**compliance_dict)

    # 格式化报告
    report = format_compliance_report(product, country, compliance_dict)

    # RAG 补充
    rag_results = []
    if include_rag:
        from app.knowledge.store import retrieve_context, format_context_for_assistant
        rag_results = retrieve_context(f"{product} 出口 {country} 合规要求")
        if rag_results:
            report += f"\n\n---\n{format_context_for_assistant(rag_results)}"

    # SDK 增强分析
    report = await _sdk_enhance_report(product, country, compliance_dict, report)

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
    """合规结果持久化 — 写入记忆树 + 会话存储 + 项目记忆。"""
    # 1. 会话存储（L4）
    from app.storage.layer_registry import registry
    sid = session_id or f"session_{hashlib.sha1(report[:50].encode()).hexdigest()[:8]}"
    registry.session.save_message(user_id, sid, "user", f"{product}出口{country}合规检查")
    registry.session.save_message(user_id, sid, "assistant", report, compliance_dict)
    registry.session.save_context(user_id, sid, "current_product", product)
    registry.session.save_context(user_id, sid, "current_market", country)

    # 2. 项目记忆（L2）
    pid = product_id or build_product_id(product, country)
    registry.project.save_compliance_record(
        product_id=pid,
        product_name=product,
        target_market=country,
        result=compliance_dict,
        session_id=session_id or "",
    )

    # 3. 记忆树（L0-L3）
    from app.core.memory_tree import MemoryTree
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
