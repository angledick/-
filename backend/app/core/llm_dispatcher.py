"""LLM 决策调度器 — glm-5.1 驱动的自动处置系统。

职责：
  - 风险情报：LLM 判断是否需要预警、预警级别、推荐处置行动
  - 生命周期：LLM 判断各阶段是否可以推进、阻塞原因、下一步建议
  - 批量扫描：定期对待审核资产（供应商/合同/报关单）触发 LLM 处置

调度任务（绑定到 scheduler）：
  lifecycle_llm_scan    每小时   扫描未 LLM 审核的供应商/合同/报关单
  risk_intel_dispatch   每 30 分钟 对高分情报进行 LLM 决策调度
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 调度 Prompts
# ─────────────────────────────────────────────────────────────────────────────

_RISK_DISPATCH_SYSTEM = """\
你是跨境合规风险处置专家。基于风险情报分析结果，给出具体的处置决策。
输出严格 JSON：
{
  "action": "alert|watch|ignore|escalate",
  "priority": "urgent|high|normal|low",
  "notify_roles": ["admin"|"operator"|"compliance"],
  "next_steps": ["≤3条具体行动，每条≤25字"],
  "auto_actions": ["可自动执行的系统操作，如：suspend_shipment/block_supplier/flag_order"],
  "reasoning": "≤60字决策理由",
  "deadline_hours": 24
}
action 说明：alert=立即预警，watch=持续关注，ignore=无需处理，escalate=升级处理。
auto_actions 仅填写系统可执行的操作，不填不确定的。"""

_LIFECYCLE_DISPATCH_SYSTEM = """\
你是跨境出海生命周期管理顾问。基于当前阶段状态，给出推进决策。
输出严格 JSON：
{
  "can_proceed": true|false,
  "current_stage": "当前阶段",
  "recommended_next_stage": "建议进入的下一阶段|null",
  "blockers": ["阻塞原因，每条≤25字"],
  "actions": ["需要完成的行动，每条≤25字"],
  "auto_triggers": ["可自动触发的系统操作"],
  "risk_flags": ["风险标记"],
  "reasoning": "≤80字判断理由"
}"""

_BATCH_SCAN_SYSTEM = """\
你是合规批量扫描助手。快速判断资产是否存在需要人工介入的问题。
输出严格 JSON：
{
  "needs_review": true|false,
  "urgency": "immediate|soon|routine",
  "issues": ["发现的问题，每条≤30字"],
  "recommendation": "≤50字建议"
}"""


# ─────────────────────────────────────────────────────────────────────────────
# 调度器主类
# ─────────────────────────────────────────────────────────────────────────────

class LLMDispatcher:
    """LLM 驱动的处置决策引擎。"""

    # ── 风险情报处置 ──────────────────────────────────────────────────────────

    async def dispatch_risk_intel(self, item: dict) -> dict:
        """对单条风险情报做 LLM 处置决策。"""
        from app.core.llm_gateway import get_llm_gateway
        gw = get_llm_gateway()

        llm_analysis = item.get("llm_analysis") or {}
        user_msg = (
            f"情报域：{item.get('risk_domain')} | 分类：{item.get('risk_category')}\n"
            f"风险分：{item.get('risk_score')} | 严重度：{item.get('severity')}\n"
            f"标题：{item.get('headline_summary') or item.get('title','')}\n"
            f"概述：{llm_analysis.get('summary','')}\n"
            f"影响：{llm_analysis.get('impact','')}\n"
            f"受影响市场：{', '.join(item.get('affected_markets',[]))}\n"
            f"受影响HS编码：{', '.join(item.get('affected_hs_codes',[]))}\n"
            f"来源：{item.get('source_name')} | 时间：{item.get('pub_time','')[:10]}"
        )

        result = await gw.chat_json(_RISK_DISPATCH_SYSTEM, user_msg, role="dispatch")
        if not result:
            # 规则降级：高分情报默认 alert
            score = float(item.get("risk_score", 0))
            return {
                "action": "alert" if score >= 0.7 else ("watch" if score >= 0.4 else "ignore"),
                "priority": "high" if score >= 0.7 else "normal",
                "notify_roles": ["admin"] if score >= 0.7 else [],
                "next_steps": ["查看情报详情", "评估对业务影响"],
                "auto_actions": [],
                "reasoning": f"规则引擎降级：risk_score={score:.2f}",
                "deadline_hours": 24,
                "_method": "rules_fallback",
            }

        # 执行自动操作
        await self._execute_auto_actions(result.get("auto_actions", []), item)
        return result

    async def batch_dispatch_risk_intel(self, limit: int = 30) -> dict:
        """批量对高分未处置的风险情报执行 LLM 决策。"""
        from app.storage.risk_intel_store import search_items
        # 找已 LLM 分析但未创建预警的高分情报
        feed = search_items(min_score=0.6, hours=48, page=1, size=limit)
        items = [i for i in feed["items"] if i.get("llm_analyzed") == 1 and not i.get("alert_id")]

        if not items:
            logger.debug("[LLMDispatcher] 无待处置风险情报")
            return {"dispatched": 0, "total_scanned": feed["total"]}

        dispatched = 0
        for item in items[:10]:  # 单批最多 10 条
            try:
                decision = await self.dispatch_risk_intel(item)
                if decision.get("action") in ("alert", "escalate"):
                    await self._create_risk_alert_from_decision(item, decision)
                    dispatched += 1
            except Exception as e:
                logger.error("[LLMDispatcher] 风险情报处置失败: %s", e)

        return {"dispatched": dispatched, "total_scanned": len(items)}

    # ── 生命周期阶段推进决策 ──────────────────────────────────────────────────

    async def dispatch_lifecycle_stage(
        self,
        product: dict,
        current_stage: str,
        context: dict = None,
    ) -> dict:
        """对产品当前生命周期阶段做 LLM 推进决策。"""
        from app.core.llm_gateway import get_llm_gateway
        gw = get_llm_gateway()

        ctx = context or {}
        user_msg = (
            f"产品：{product.get('name')} | HS编码：{product.get('hs_code','未知')}\n"
            f"目标市场：{', '.join(product.get('target_markets', []) or [])}\n"
            f"当前阶段：{current_stage}\n"
            f"合规状态：{product.get('compliance_status','unknown')}\n"
            f"风险等级：{product.get('risk_level','unknown')}\n"
            f"关联供应商：{ctx.get('supplier_name','未知')} | 风险：{ctx.get('supplier_risk_level','unknown')}\n"
            f"合同状态：{ctx.get('contract_status','无')} | 合规分：{ctx.get('contract_score','N/A')}\n"
            f"报关状态：{ctx.get('customs_status','无')} | 物流状态：{ctx.get('logistics_status','无')}\n"
            f"支付通道：{ctx.get('payment_status','未配置')}\n"
            f"待解决问题：{', '.join(ctx.get('open_issues', [])) or '无'}"
        )

        result = await gw.chat_json(_LIFECYCLE_DISPATCH_SYSTEM, user_msg, role="dispatch")
        if not result:
            return {
                "can_proceed": False,
                "current_stage": current_stage,
                "recommended_next_stage": None,
                "blockers": ["LLM 不可用，请手动评估"],
                "actions": ["检查各项关联信息后手动推进"],
                "auto_triggers": [],
                "risk_flags": [],
                "reasoning": "LLM 不可用，降级为手动模式",
                "_method": "rules_fallback",
            }
        return result

    # ── 批量生命周期扫描 ──────────────────────────────────────────────────────

    async def scan_lifecycle_assets(self) -> dict:
        """批量扫描待 LLM 审核的生命周期资产（供应商/合同/报关单）。"""
        stats = {"suppliers": 0, "contracts": 0, "customs": 0, "errors": 0}

        # 1. 扫描未 AI 审核的供应商
        try:
            from app.storage.supplier_store import list_suppliers, save_ai_review
            from app.core.lifecycle_analyzer import analyze_supplier
            suppliers = [s for s in list_suppliers(status="active", limit=10)
                         if not s.get("ai_review")]
            for s in suppliers[:5]:
                try:
                    result = await analyze_supplier(s)
                    save_ai_review(s["id"], result)
                    await self._push_ws("supplier_reviewed", {
                        "supplier_id": s["id"], "name": s["name"],
                        "risk_level": result.get("risk_level"), "score": result.get("score"),
                    })
                    stats["suppliers"] += 1
                except Exception as e:
                    logger.error("[LLMDispatcher] 供应商扫描失败 %s: %s", s.get("id"), e)
                    stats["errors"] += 1
        except Exception as e:
            logger.error("[LLMDispatcher] 供应商批量扫描异常: %s", e)

        # 2. 扫描 draft 状态且未合规审查的合同
        try:
            from app.storage.contract_store import list_contracts, save_compliance_review
            from app.core.lifecycle_analyzer import analyze_contract
            contracts = [c for c in list_contracts(status="draft", limit=10)
                         if c.get("compliance_score", 0) == 0]
            for c in contracts[:5]:
                try:
                    result = await analyze_contract(c)
                    save_compliance_review(c["id"], result.get("issues", []), result.get("score", 0))
                    await self._push_ws("contract_reviewed", {
                        "contract_id": c["id"], "title": c["title"],
                        "score": result.get("score"), "issues": len(result.get("issues", [])),
                    })
                    stats["contracts"] += 1
                except Exception as e:
                    logger.error("[LLMDispatcher] 合同扫描失败 %s: %s", c.get("id"), e)
                    stats["errors"] += 1
        except Exception as e:
            logger.error("[LLMDispatcher] 合同批量扫描异常: %s", e)

        # 3. 扫描 submitted 状态且无合规检查的报关单
        try:
            from app.storage.customs_store import list_declarations, save_compliance_checks
            from app.core.lifecycle_analyzer import analyze_customs_declaration
            declarations = [d for d in list_declarations(status="submitted", limit=10)
                            if not d.get("compliance_checks")]
            for d in declarations[:5]:
                try:
                    result = await analyze_customs_declaration(d)
                    issues = result.get("issues", [])
                    save_compliance_checks(d["id"], issues)
                    await self._push_ws("customs_reviewed", {
                        "declaration_id": d["id"], "passed": result.get("passed", True),
                        "issues": len(issues),
                    })
                    stats["customs"] += 1
                except Exception as e:
                    logger.error("[LLMDispatcher] 报关单扫描失败 %s: %s", d.get("id"), e)
                    stats["errors"] += 1
        except Exception as e:
            logger.error("[LLMDispatcher] 报关单批量扫描异常: %s", e)

        logger.info("[LLMDispatcher] 生命周期扫描完成: %s", stats)
        return stats

    # ── 内部辅助 ──────────────────────────────────────────────────────────────

    async def _execute_auto_actions(self, actions: list[str], context: dict) -> None:
        """执行 LLM 决定的自动操作。"""
        for action in actions:
            action = action.lower().strip()
            logger.info("[LLMDispatcher] 执行自动操作: %s", action)
            try:
                if action == "flag_order" and context.get("order_id"):
                    from app.storage.order_store import update_order
                    update_order(context["order_id"], {"status": "flagged"})
                elif action == "suspend_shipment" and context.get("logistics_id"):
                    from app.storage.logistics_store import update_status
                    update_status(context["logistics_id"], "exception")
                elif action == "block_supplier" and context.get("supplier_id"):
                    from app.storage.supplier_store import update_supplier
                    update_supplier(context["supplier_id"], {"status": "suspended"})
            except Exception as e:
                logger.warning("[LLMDispatcher] 自动操作失败 %s: %s", action, e)

    async def _create_risk_alert_from_decision(self, item: dict, decision: dict) -> None:
        """基于 LLM 决策创建预警。"""
        try:
            from app.core.risk_alert import create_alert
            from app.storage.risk_intel_store import link_alert
            alert = create_alert(
                alert_type="risk_intel",
                severity=item.get("severity", "medium"),
                title=f"[LLM调度] {item.get('headline_summary') or item.get('title','')[:60]}",
                description=(
                    f"决策：{decision.get('action')} | 优先级：{decision.get('priority')}\n"
                    f"理由：{decision.get('reasoning','')}\n"
                    f"建议行动：{'; '.join(decision.get('next_steps',[]))}"
                ),
                affected_markets=item.get("affected_markets", []),
                source=item.get("source_name", ""),
                source_url=item.get("url", ""),
            )
            if alert.get("alert_id") and item.get("id"):
                link_alert(item["id"], alert["alert_id"])
            await self._push_ws("risk_dispatch_alert", {
                "intel_id": item.get("id"),
                "alert_id": alert.get("alert_id"),
                "action": decision.get("action"),
                "priority": decision.get("priority"),
                "next_steps": decision.get("next_steps", []),
            })
        except Exception as e:
            logger.error("[LLMDispatcher] 创建决策预警失败: %s", e)

    @staticmethod
    async def _push_ws(event_type: str, payload: dict) -> None:
        try:
            from app.services.ws_manager import ws_manager
            await ws_manager.broadcast({"type": event_type, "payload": payload})
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# 单例
# ─────────────────────────────────────────────────────────────────────────────

_dispatcher: Optional[LLMDispatcher] = None

def get_llm_dispatcher() -> LLMDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = LLMDispatcher()
    return _dispatcher
