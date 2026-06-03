"""
事件驱动合规流水线 (EventDrivenComplianceFlow) — 六阶段闭环。

六阶段流水线（对齐指南§6.15）:
  感知 → 检查 → 推荐 → 告知 → 交互 → 处理

模块复用:
  - 感知: EventChain + MarketMonitor + GlobalEventBus
  - 检查: RuleEngine + RAG
  - 推荐: Skill推荐器 + 规则引擎
  - 告知: NotificationEngine
  - 交互: AstraAssistant + Skills
  - 处理: ActionChain + 结果回写

开源参考:
  - 工作流编排: n8n (191k⭐) / Temporal (14k⭐)
  - 指标监控: Grafana (74.1k⭐)
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from app.config import settings
from app.models.schemas import (
    EventRecord, EventCategory, DataSourceInfo,
    CheckResult, RecommendAction, CompliancePipelineResult,
    NotificationPayload, PipelineStageStatus, PipelineHealthResponse,
)


class EventDrivenComplianceFlow:
    """事件驱动合规流（六阶段闭环）

    用法:
        flow = EventDrivenComplianceFlow()
        result = await flow.execute(event_record)

        # 查看完整流水线结果
        print(result.check_result.risk_level)
        print(result.recommendations)
        print(result.notifications_sent)
    """

    def __init__(self):
        self._pipeline_mode = "6step"  # 或 "5step"（合并推荐+告知）
        self._pending_interactions: Dict[str, Dict] = {}  # 等待用户交互的状态

    # ── 主执行入口 ──────────────────────────────────

    async def execute(self, trigger_event: EventRecord) -> CompliancePipelineResult:
        """执行六阶段闭环

        Args:
            trigger_event: 触发合规流水线的事件
        Returns:
            CompliancePipelineResult 完整流水线结果
        """
        result = CompliancePipelineResult(
            event=trigger_event,
            pipeline_mode=self._pipeline_mode,
            status="running",
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        try:
            # Step 1: 感知
            enriched = await self._perceive(trigger_event)

            # Step 2: 检查
            check_result = await self._check(enriched)
            result.check_result = check_result

            # Step 3: 推荐
            recommendations = await self._recommend(enriched, check_result)
            result.recommendations = recommendations

            # Step 4: 告知
            if self._pipeline_mode == "6step":
                notifications = await self._notify(enriched, check_result, recommendations)
                result.notifications_sent = notifications

            # Step 5: 交互（异步等待用户响应）
            # 此处生成推荐操作等待用户确认，不阻塞流水线
            interaction_id = await self._prepare_interaction(enriched, check_result, recommendations)

            # Step 6: 处理（在用户确认后执行，此处记录待处理状态）
            result.status = "awaiting_interaction" if interaction_id else "completed"
            result.completed_at = datetime.now(timezone.utc).isoformat()

            # 填充数据血缘（对标§6.10.3规范）
            from app.models.schemas import DataSourceInfo
            trigger_event.data_sources = DataSourceInfo(
                read=[
                    "L0:hs_codes",
                    "L0:regulations",
                    "L1:knowledge_base",
                    "L2:product_memory",
                ],
                write=[
                    "L2:product_memory",
                    "L5:event_chain",
                    "product:events",
                ],
            )

            # 发布流水线完成事件
            await self._publish_pipeline_event(trigger_event, result)

        except Exception as e:
            result.status = "error"
            result.completed_at = datetime.now(timezone.utc).isoformat()
            result.process_result = {"error": str(e)}

        return result

    async def execute_5step(self, trigger_event: EventRecord) -> CompliancePipelineResult:
        """执行5阶段流水线（推荐与告知合并）"""
        old_mode = self._pipeline_mode
        self._pipeline_mode = "5step"
        try:
            return await self.execute(trigger_event)
        finally:
            self._pipeline_mode = old_mode

    # ── 用户交互处理 ──────────────────────────────────

    async def handle_user_action(
        self, interaction_id: str, action: str, confirmed: bool = True
    ) -> CompliancePipelineResult:
        """处理用户交互响应

        Args:
            interaction_id: 交互ID
            action: 用户选择的操作
            confirmed: 是否确认执行
        """
        pending = self._pending_interactions.get(interaction_id)
        if not pending:
            raise ValueError(f"交互 {interaction_id} 不存在或已过期")

        result = pending["result"]

        if confirmed:
            # 执行处理
            process_result = await self._process(action, pending)
            result.process_result = process_result
            result.user_action = action
            result.status = "completed"
        else:
            result.status = "rejected"
            result.user_action = f"rejected:{action}"

        # 清理
        del self._pending_interactions[interaction_id]
        result.completed_at = datetime.now(timezone.utc).isoformat()

        return result

    # ── 六阶段实现 ──────────────────────────────────

    async def _perceive(self, event: EventRecord) -> Dict[str, Any]:
        """Step 1: 感知 — 接收事件并补充上下文"""
        enriched = {
            "event": event,
            "product_id": event.product_id,
            "business_stage": event.business_stage,
            "market_data": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 补充产品信息
        if event.product_id:
            try:
                from app.core.product_storage import get_product_storage
                storage = get_product_storage()
                product = storage.get_product(event.product_id)
                if product:
                    enriched["product"] = product.model_dump()
                    enriched["target_markets"] = product.target_markets
                    enriched["hs_code"] = product.hs_code
            except Exception:
                pass

        # 补充市场数据（MarketMonitor）
        try:
            from app.core.market_monitor import MarketMonitor
            monitor = MarketMonitor()
            market_context = monitor.get_market_context(
                enriched.get("product", {}).get("product_type", ""),
                enriched.get("target_markets", ["欧盟"])[0] if enriched.get("target_markets") else "欧盟",
            )
            enriched["market_data"] = market_context if isinstance(market_context, dict) else {}
        except Exception:
            pass

        return enriched

    async def _check(self, enriched: Dict[str, Any]) -> CheckResult:
        """Step 2: 检查 — RuleEngine执行规则检查 + RAG检索法规"""
        event = enriched.get("event")
        product = enriched.get("product", {})
        target_markets = enriched.get("target_markets", ["欧盟"])
        target_market = target_markets[0] if target_markets else "欧盟"

        check_result = CheckResult(
            passed=True,
            risk_level="low",
            risk_score=0,
        )

        # RuleEngine 合规检查
        try:
            from app.core.rule_engine import check_compliance
            product_info = {
                "name": product.get("name", ""),
                "product_type": product.get("product_type", ""),
                "hs_code": enriched.get("hs_code", product.get("hs_code", "")),
            }
            rule_result = check_compliance(product_info, target_market)

            if isinstance(rule_result, dict):
                check_result.risk_level = rule_result.get("risk_level", "low")
                check_result.risk_score = rule_result.get("risk_score", 0)
                check_result.regulations = rule_result.get("certifications", [])
                check_result.rule_results = [rule_result]
                check_result.passed = rule_result.get("risk_level") != "high"
        except Exception:
            pass

        # RAG 法规检索（超时保护：5s内未返回则跳过）
        try:
            from app.knowledge.store import search as knowledge_search
            query = f"{product.get('product_type', '')} {target_market} 合规要求"
            rag_results = await asyncio.wait_for(
                asyncio.to_thread(knowledge_search, query, 3),
                timeout=5.0,
            )
            if rag_results:
                for r in rag_results:
                    if isinstance(r, dict):
                        check_result.regulations.append(r.get("text", "")[:100])
        except (Exception, asyncio.TimeoutError):
            pass

        return check_result

    async def _recommend(
        self, enriched: Dict[str, Any], check_result: CheckResult
    ) -> List[RecommendAction]:
        """Step 3: 推荐 — 基于检查结果生成推荐操作"""
        recommendations = []

        if check_result.risk_level == "high":
            recommendations.append(RecommendAction(
                action="立即执行整改",
                confidence=0.9,
                skill="compliance_remediation",
                expected_result="降低风险等级",
                risk_level="medium",
            ))

        if check_result.risk_score > 60:
            recommendations.append(RecommendAction(
                action="申请专业合规咨询",
                confidence=0.85,
                skill="consultation_booking",
                expected_result="获取专业合规建议",
            ))

        # 根据缺失认证推荐
        for reg in check_result.regulations:
            if "CE" in str(reg) or "认证" in str(reg):
                recommendations.append(RecommendAction(
                    action=f"准备{reg}认证材料",
                    confidence=0.8,
                    skill="cert_preparation",
                    expected_result=f"完成{reg}认证申请",
                ))

        # 默认推荐
        if not recommendations:
            recommendations.append(RecommendAction(
                action="继续保持当前合规状态",
                confidence=0.95,
                expected_result="维持低风险运营",
            ))

        return recommendations

    async def _notify(
        self,
        enriched: Dict[str, Any],
        check_result: CheckResult,
        recommendations: List[RecommendAction],
    ) -> List[str]:
        """Step 4: 告知 — 通知引擎推送结果到多渠道"""
        notifications_sent = []
        event = enriched.get("event")
        product = enriched.get("product", {})

        # 创建通知payload
        severity = "high" if check_result.risk_level in ("high", "critical") else "low"
        notification = NotificationPayload(
            type="compliance_check",
            title=f"合规检查结果: {product.get('name', 'Unknown')}",
            message=f"风险等级: {check_result.risk_level}, 评分: {check_result.risk_score}/100",
            product_id=event.product_id if event else None,
            severity=severity,
        )

        # 通过通知引擎发送
        try:
            from app.core.notification_engine import get_notification_engine
            engine = get_notification_engine()
            await engine.send(notification)
            notifications_sent.append(f"dashboard:{notification.id}")
        except Exception:
            notifications_sent.append(f"pending:{notification.id}")

        return notifications_sent

    async def _prepare_interaction(
        self,
        enriched: Dict[str, Any],
        check_result: CheckResult,
        recommendations: List[RecommendAction],
    ) -> Optional[str]:
        """Step 5: 交互准备 — 生成待确认操作"""
        if not recommendations:
            return None

        interaction_id = f"interact_{uuid.uuid4().hex[:8]}"
        self._pending_interactions[interaction_id] = {
            "enriched": enriched,
            "check_result": check_result,
            "recommendations": [r.model_dump() for r in recommendations],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": CompliancePipelineResult(
                event=enriched.get("event", EventRecord(
                    id="unknown", type="unknown", category=EventCategory.system, source="pipeline"
                )),
                check_result=check_result,
                recommendations=recommendations,
                status="awaiting_interaction",
            ),
        }

        return interaction_id

    async def _process(self, action: str, pending: Dict) -> Dict[str, Any]:
        """Step 6: 处理 — 执行用户确认的操作"""
        result = {
            "action": action,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
        }

        # 通过ActionChain记录操作
        try:
            from app.core.action_chain import ActionChain
            chain = ActionChain(chain_id=f"pipeline_{uuid.uuid4().hex[:8]}")
            chain.append(
                type="compliance_action",
                description_nl=f"执行合规操作: {action}",
                agent="ComplianceFlow",
                input_data={"action": action},
                output_data=result,
            )
            chain.save()
            result["action_chain_id"] = chain.chain_id
        except Exception:
            pass

        return result

    async def _publish_pipeline_event(
        self, trigger_event: EventRecord, result: CompliancePipelineResult
    ):
        """发布流水线完成事件"""
        try:
            from app.core.event_bus import get_event_bus
            bus = get_event_bus()
            await bus.publish_raw({
                "type": "compliance:pipeline_completed",
                "source": "compliance_flow",
                "product_id": trigger_event.product_id,
                "business_stage": trigger_event.business_stage,
                "severity": "low" if result.status == "completed" else "medium",
                "data": {
                    "status": result.status,
                    "pipeline_mode": result.pipeline_mode,
                    "risk_level": result.check_result.risk_level if result.check_result else "unknown",
                    "recommendations_count": len(result.recommendations),
                },
            })
        except Exception:
            pass

    # ── 流水线健康度 ──────────────────────────────────

    async def get_pipeline_health(self) -> PipelineHealthResponse:
        """获取流水线健康度（按产品生命周期阶段过滤）"""
        from app.core.product_storage import get_product_storage
        from app.models.schemas import ProductLifecycleStage
        storage = get_product_storage()

        stages = []
        stage_names = [
            (1, "建站与环境"), (2, "选品设计"), (3, "供应商审核"),
            (4, "商品上架"), (5, "支付配置"), (6, "订单处理"),
            (7, "出口报关"), (8, "进口清关"), (9, "售后退货"), (10, "财务结算"),
        ]

        # 10个业务阶段 → 产品生命周期阶段映射
        stage_to_lifecycle = {
            1: ProductLifecycleStage.CONCEPT,
            2: ProductLifecycleStage.DESIGN,
            3: ProductLifecycleStage.SOURCING,
            4: ProductLifecycleStage.READY,
            5: ProductLifecycleStage.ACTIVE,
            6: ProductLifecycleStage.ACTIVE,
            7: ProductLifecycleStage.ACTIVE,
            8: ProductLifecycleStage.FULFILLING,
            9: ProductLifecycleStage.AFTERSALE,
            10: ProductLifecycleStage.END,
        }

        total_score = 0
        for stage_num, stage_name in stage_names:
            lifecycle = stage_to_lifecycle.get(stage_num)
            products_in_stage = storage.list_products(
                lifecycle_stage=lifecycle, limit=1000
            )
            total = len(products_in_stage)
            passed = sum(1 for p in products_in_stage if p.compliance_status == "passed")
            risk = sum(1 for p in products_in_stage if p.risk_level == "high" or p.risk_level == "critical")

            pass_rate = passed / total if total > 0 else 1.0
            status = "healthy" if pass_rate > 0.8 else ("warning" if pass_rate > 0.5 else "critical")

            stages.append(PipelineStageStatus(
                stage_number=stage_num,
                stage_name=stage_name,
                pass_rate=pass_rate,
                total_products=total,
                passed_products=passed,
                risk_products=risk,
                status=status,
            ))
            total_score += pass_rate * 10

        overall = total_score / len(stage_names) if stage_names else 0

        return PipelineHealthResponse(
            overall_score=round(overall, 1),
            stages=stages,
        )


# ── 全局单例 ──────────────────────────────────

_compliance_flow: Optional[EventDrivenComplianceFlow] = None


def get_compliance_flow() -> EventDrivenComplianceFlow:
    """获取合规流水线单例"""
    global _compliance_flow
    if _compliance_flow is None:
        _compliance_flow = EventDrivenComplianceFlow()
    return _compliance_flow
