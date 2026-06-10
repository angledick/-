"""
主动引擎 (ProactiveEngine) — 定时任务 + 心跳自检 + 洞察挖掘。

职责:
  1. 定时任务: 每日合规简报、认证到期预警、法规变更扫描
  2. 心跳自检: 每5分钟检查系统组件健康状态
  3. 洞察挖掘: 从产品数据和事件中挖掘跨产品洞察
  4. 主动推送: 根据洞察结果生成主动通知

参考:
  - QwenPaw 心跳: 系统自检 + 定时巡检
  - Grafana (74.1k⭐): 指标监控 + 告警阈值
  - PyOD (8.5k⭐): 50+异常检测算法，用于风险预警
  - 指南§6.6: 个性指标监听与预警
  - 指南§6.12.3: 跨产品洞察引擎
"""

import json
import logging
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from app.config import settings

logger = logging.getLogger(__name__)
from app.models.schemas import NotificationPayload

DATA_DIR = Path(settings.data_dir)


@dataclass
class HeartbeatStatus:
    """系统心跳状态"""
    timestamp: str = ""
    overall: str = "healthy"      # healthy/degraded/critical
    components: Dict[str, str] = field(default_factory=dict)
    uptime_seconds: int = 0
    last_heartbeat: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "overall": self.overall,
            "components": self.components,
            "uptime_seconds": self.uptime_seconds,
            "last_heartbeat": self.last_heartbeat,
        }


@dataclass
class Insight:
    """跨产品洞察"""
    insight_id: str = ""
    insight_type: str = ""        # common_risk/trend/anomaly/recommendation
    title: str = ""
    description: str = ""
    affected_products: List[str] = field(default_factory=list)
    severity: str = "low"
    suggestion: str = ""
    generated_at: str = ""

    def __post_init__(self):
        if not self.insight_id:
            self.insight_id = f"insight_{uuid.uuid4().hex[:8]}"
        if not self.generated_at:
            self.generated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "insight_type": self.insight_type,
            "title": self.title,
            "description": self.description,
            "affected_products": self.affected_products,
            "severity": self.severity,
            "suggestion": self.suggestion,
            "generated_at": self.generated_at,
        }


class ProactiveEngine:
    """主动引擎 — 定时任务 + 心跳 + 洞察

    用法:
        engine = ProactiveEngine()

        # 启动定时任务
        await engine.setup_scheduled_tasks()

        # 手动触发
        brief = await engine.daily_compliance_brief()
        cert_alerts = await engine.check_cert_expiry()
        reg_changes = await engine.scan_regulation_changes()
        heartbeat = await engine.heartbeat_check()

        # 获取洞察
        insights = await engine.generate_cross_product_insights()

    开源参考:
      - Grafana (74.1k⭐): 实时监控指标趋势/告警阈值
      - PyOD (8.5k⭐): 异常检测算法引擎
      - 指南§6.12.3: 跨产品洞察（每4小时聚合，每天洞察报告）
    """

    def __init__(self):
        self._start_time = datetime.now(timezone.utc)
        self._heartbeat: Optional[HeartbeatStatus] = None
        self._insights: List[Insight] = []
        self._brief_history: List[Dict[str, Any]] = []
        self._alert_history: List[Dict[str, Any]] = []

        # 全局记忆和指标路径
        self._global_memory_path = DATA_DIR / "global" / "memory"
        self._global_metrics_path = DATA_DIR / "global" / "metrics"
        self._global_events_path = DATA_DIR / "global" / "events"

        # 确保目录存在
        self._global_memory_path.mkdir(parents=True, exist_ok=True)
        self._global_metrics_path.mkdir(parents=True, exist_ok=True)
        self._global_events_path.mkdir(parents=True, exist_ok=True)

    # ── 定时任务设置 ──────────────────────────────────

    # ── SDK 报告生成辅助 ──────────────────────────

    async def _generate_with_claude(self, prompt_name: str, context: Dict[str, Any]) -> str:
        """通过 Claude SDK 生成报告/分析内容。

        使用 AstraAssistant.run_task() 委托 Claude 执行，
        Claude 可调用 Bash/WebSearch/Read 等工具补充数据。
        """
        try:
            from app.services.astra_assistant import AstraAssistant, check_sdk
            if not check_sdk():
                return ""
            assistant = AstraAssistant()
            result = await assistant.run_task(
                prompt_name=prompt_name,
                context=context,
            )
            if isinstance(result, dict):
                return result.get("raw_text", "") or result.get("response", "") or json.dumps(result, ensure_ascii=False)
            return str(result)
        except Exception as e:
            logger.debug("SDK 报告生成不可用: %s", str(e)[:100])
            return ""

    # ── 每日合规简报 ──────────────────────────────────

    async def daily_compliance_brief(self) -> Dict[str, Any]:
        """每日合规简报

        生成内容:
          - 当前活跃产品数量与分布
          - 待处理预警数量
          - 近期合规检查通过率
          - 认证到期预警
          - 法规变更摘要

        推送渠道: Dashboard + Email（参考指南§6.5.2通知触发策略）
        """
        brief = {
            "type": "daily_brief",
            "date": date.today().isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "active_products": 0,
                "pending_alerts": 0,
                "compliance_pass_rate": 0,
                "cert_expiry_warnings": 0,
                "regulation_changes": 0,
            },
            "highlights": [],
            "recommendations": [],
        }

        # 统计产品数量
        try:
            from app.core.product_storage import get_product_storage
            storage = get_product_storage()
            products = storage.list_products()
            brief["summary"]["active_products"] = len([
                p for p in products
                if hasattr(p, 'lifecycle_stage') and p.lifecycle_stage in ("active", "fulfilling")
            ])
        except Exception:
            pass

        # 统计待处理预警
        try:
            alerts_path = self._global_events_path / "bus.json"
            if alerts_path.exists():
                data = json.loads(alerts_path.read_text(encoding="utf-8"))
                pending = [e for e in data if isinstance(e, dict) and e.get("severity") in ("high", "critical")]
                brief["summary"]["pending_alerts"] = len(pending)
        except Exception:
            pass

        # SDK 智能分析：Claude 生成合规简报叙事报告
        sdk_report = await self._generate_with_claude("daily_compliance_brief", {
            "summary": brief["summary"],
            "date": brief["date"],
        })
        if sdk_report:
            brief["sdk_report"] = sdk_report

        # 添加建议
        if brief["summary"]["pending_alerts"] > 0:
            brief["recommendations"].append(
                f"当前有{brief['summary']['pending_alerts']}条高优先级预警待处理，建议优先查看"
            )

        if brief["summary"]["cert_expiry_warnings"] > 0:
            brief["recommendations"].append(
                f"有{brief['summary']['cert_expiry_warnings']}个认证即将到期，建议批量续期"
            )

        # 推送通知
        try:
            from app.core.notification_engine import get_notification_engine
            engine = get_notification_engine()
            await engine.send(
                NotificationPayload(
                    type="daily_brief",
                    title=f"每日合规简报 — {date.today().isoformat()}",
                    message=json.dumps(brief, ensure_ascii=False, default=str),
                    severity="low",
                ),
                channels=["dashboard"],
            )
        except Exception:
            pass

        # 记录历史
        self._brief_history.append(brief)
        if len(self._brief_history) > 30:
            self._brief_history = self._brief_history[-30:]

        return brief

    # ── 认证到期预警 ──────────────────────────────────

    async def check_cert_expiry(self) -> Dict[str, Any]:
        """检查所有产品的认证到期状态

        参考指南§6.5.2:
          - 30天内到期: severity=high, channels=[dashboard, email]
          - 已过期: severity=critical, channels=[dashboard, email, skills_push]

        开源参考:
          - Grafana告警阈值: warning(30天) / critical(0天)
        """
        result = {
            "type": "cert_expiry_check",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "warnings": [],
            "expired": [],
            "total_checked": 0,
        }

        try:
            from app.core.product_storage import get_product_storage
            storage = get_product_storage()
            products = storage.list_products()

            for product in products:
                if not hasattr(product, 'product_id'):
                    continue

                result["total_checked"] += 1
                product_id = product.product_id

                # 读取产品元数据中的认证信息
                meta_path = DATA_DIR / "products" / product_id / "memory" / "metadata.json"
                if not meta_path.exists():
                    continue

                try:
                    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    continue

                certs = metadata.get("certifications", [])
                for cert in certs:
                    if not isinstance(cert, dict):
                        continue
                    expiry = cert.get("expiry_date")
                    if not expiry:
                        continue

                    try:
                        expiry_date = datetime.fromisoformat(expiry.replace("Z", "+00:00")).date()
                        days_remaining = (expiry_date - date.today()).days
                    except (ValueError, TypeError):
                        continue

                    cert_name = cert.get("name", "未知认证")

                    if days_remaining < 0:
                        # 已过期
                        result["expired"].append({
                            "product_id": product_id,
                            "product_name": getattr(product, 'product_name', product_id),
                            "cert_name": cert_name,
                            "expiry_date": expiry,
                            "days_overdue": abs(days_remaining),
                        })

                    elif days_remaining <= 30:
                        # 即将到期
                        result["warnings"].append({
                            "product_id": product_id,
                            "product_name": getattr(product, 'product_name', product_id),
                            "cert_name": cert_name,
                            "expiry_date": expiry,
                            "days_remaining": days_remaining,
                        })

        except Exception as e:
            result["error"] = str(e)

        # 发布预警事件
        if result["expired"] or result["warnings"]:
            try:
                from app.core.event_bus import get_event_bus
                bus = get_event_bus()

                for item in result["expired"]:
                    await bus.publish_raw({
                        "type": "certification:expired",
                        "source": "proactive_engine",
                        "data": item,
                        "severity": "critical",
                    })

                for item in result["warnings"]:
                    await bus.publish_raw({
                        "type": "certification:expiring",
                        "source": "proactive_engine",
                        "data": item,
                        "severity": "high",
                    })
            except Exception:
                pass

            # 推送通知
            try:
                from app.core.notification_engine import get_notification_engine
                engine = get_notification_engine()

                if result["expired"]:
                    await engine.send(
                        NotificationPayload(
                            type="certification_expiry",
                            title="认证过期紧急告警",
                            message=f"有{len(result['expired'])}个认证已过期",
                            severity="critical",
                        ),
                        channels=["dashboard", "websocket"],
                    )

                if result["warnings"]:
                    await engine.send(
                        NotificationPayload(
                            type="certification_expiry",
                            title="认证到期预警",
                            message=f"有{len(result['warnings'])}个认证30天内到期",
                            severity="high",
                        ),
                        channels=["dashboard"],
                    )
            except Exception:
                pass

        self._alert_history.append(result)
        if len(self._alert_history) > 90:
            self._alert_history = self._alert_history[-90:]

        return result

    # ── 法规变更扫描 ──────────────────────────────────

    async def scan_regulation_changes(self) -> Dict[str, Any]:
        """扫描法规变更

        集成MarketMonitor进行法规变更检测，
        发现变更后自动匹配受影响产品并发布全局事件。

        参考指南§6.12.2: 全局知识库更新
        """
        result = {
            "type": "regulation_scan",
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "changes": [],
            "affected_products": {},
        }

        try:
            from app.core.market_monitor import MarketMonitor
            monitor = MarketMonitor()

            # 调用MarketMonitor扫描变更
            changes = await monitor.scan_changes() if hasattr(monitor, 'scan_changes') else []

            for change in changes:
                if isinstance(change, dict):
                    result["changes"].append(change)

                    # 匹配受影响产品
                    market = change.get("market", "")
                    if market:
                        try:
                            from app.core.product_storage import get_product_storage
                            storage = get_product_storage()
                            affected = storage.list_products(market=market)
                            result["affected_products"][market] = [
                                getattr(p, 'product_id', str(p)) for p in affected
                            ]
                        except Exception:
                            pass

        except Exception:
            pass

        # SDK 联网搜索：Claude 使用 WebSearch 扫描法规变更
        sdk_changes_raw = await self._generate_with_claude("regulation_scan", {
            "local_changes_count": len(result["changes"]),
            "scanned_at": result["scanned_at"],
        })
        if sdk_changes_raw:
            result["sdk_scan_report"] = sdk_changes_raw

        # 发布全局事件
        if result["changes"]:
            try:
                from app.core.event_bus import get_event_bus
                bus = get_event_bus()

                for change in result["changes"]:
                    await bus.publish_raw({
                        "type": "regulation:updated",
                        "source": "proactive_engine",
                        "data": change,
                        "severity": "high" if change.get("impact_level") == "high" else "medium",
                    })
            except Exception:
                pass

            # 更新全局记忆
            self._update_global_memory_regulations(result["changes"])

        return result

    # ── 心跳自检 ──────────────────────────────────

    async def heartbeat_check(self) -> HeartbeatStatus:
        """系统心跳自检 — 每5分钟

        检查组件:
          - event_bus: 事件总线状态
          - product_storage: 产品存储可访问性
          - worker_registry: Worker注册表
          - memory_tree: 记忆树数据库
          - notification_engine: 通知引擎
          - scheduler: 调度器
        """
        now = datetime.now(timezone.utc)
        uptime = int((now - self._start_time).total_seconds())

        components = {}

        # 检查事件总线
        try:
            from app.core.event_bus import get_event_bus
            bus = get_event_bus()
            components["event_bus"] = "healthy" if bus else "degraded"
        except Exception:
            components["event_bus"] = "unavailable"

        # 检查产品存储
        try:
            from app.core.product_storage import get_product_storage
            storage = get_product_storage()
            products = storage.list_products(limit=1)
            components["product_storage"] = "healthy"
        except Exception:
            components["product_storage"] = "degraded"

        # 检查Worker注册表
        try:
            from app.core.worker_registry import get_worker_registry
            reg = get_worker_registry()
            workers = reg.get_all_workers()
            components["worker_registry"] = "healthy" if workers else "degraded"
        except Exception:
            components["worker_registry"] = "unavailable"

        # 检查通知引擎
        try:
            from app.core.notification_engine import get_notification_engine
            ne = get_notification_engine()
            components["notification_engine"] = "healthy" if ne else "degraded"
        except Exception:
            components["notification_engine"] = "unavailable"

        # 检查调度器
        try:
            from app.core.scheduler import get_scheduler
            scheduler = get_scheduler()
            components["scheduler"] = "healthy" if scheduler else "degraded"
        except Exception:
            components["scheduler"] = "unavailable"

        # 计算整体健康
        statuses = list(components.values())
        if all(s == "healthy" for s in statuses):
            overall = "healthy"
        elif any(s == "unavailable" for s in statuses):
            overall = "critical"
        else:
            overall = "degraded"

        self._heartbeat = HeartbeatStatus(
            timestamp=now.isoformat(),
            overall=overall,
            components=components,
            uptime_seconds=uptime,
            last_heartbeat=now.isoformat(),
        )

        # 异常时告警
        if overall != "healthy":
            try:
                from app.core.notification_engine import get_notification_engine
                engine = get_notification_engine()
                await engine.send(
                    NotificationPayload(
                        type="system:health_alert",
                        title=f"系统健康告警 — {overall}",
                        message=json.dumps(self._heartbeat.to_dict(), ensure_ascii=False, default=str),
                        severity="high" if overall == "critical" else "medium",
                    ),
                    channels=["dashboard"],
                )
            except Exception:
                pass

        # 更新全局记忆系统健康
        self._update_global_memory_health(self._heartbeat)

        return self._heartbeat

    # ── 跨产品洞察 ──────────────────────────────────

    async def generate_cross_product_insights(self) -> List[Dict[str, Any]]:
        """生成跨产品洞察

        参考指南§6.12.3:
          - 共同风险: 多产品面临同类认证到期
          - 趋势分析: 合规健康度趋势
          - 批量建议: 可批量处理的操作

        触发频率: 每4小时执行，每天生成一次完整报告
        """
        insights: List[Insight] = []

        try:
            from app.core.product_storage import get_product_storage
            storage = get_product_storage()
            products = storage.list_products()

            if len(products) < 2:
                return []

            # 按市场分组
            market_groups: Dict[str, List] = {}
            for p in products:
                markets = getattr(p, 'target_markets', []) or []
                for m in markets:
                    market_groups.setdefault(m, []).append(p)

            # 检测: 多产品同市场风险
            for market, prods in market_groups.items():
                if len(prods) >= 3:
                    insights.append(Insight(
                        insight_type="market_concentration",
                        title=f"{market}市场产品集中度分析",
                        description=f"当前在{market}市场有{len(prods)}个产品在售",
                        affected_products=[getattr(p, 'product_id', str(p)) for p in prods],
                        severity="low",
                        suggestion=f"建议关注{market}市场法规变更对批量产品的影响",
                    ))

            # 检测: 认证到期聚集
            cert_expiry_groups: Dict[str, List[str]] = {}
            for p in products:
                meta_path = DATA_DIR / "products" / getattr(p, 'product_id', '') / "memory" / "metadata.json"
                if not meta_path.exists():
                    continue
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    for cert in meta.get("certifications", []):
                        if isinstance(cert, dict) and cert.get("name"):
                            cert_expiry_groups.setdefault(cert["name"], []).append(
                                getattr(p, 'product_id', str(p))
                            )
                except Exception:
                    continue

            for cert_name, pids in cert_expiry_groups.items():
                if len(pids) >= 2:
                    insights.append(Insight(
                        insight_type="common_risk",
                        title=f"{cert_name}认证多产品关联",
                        description=f"有{len(pids)}个产品使用{cert_name}认证",
                        affected_products=pids,
                        severity="medium",
                        suggestion=f"建议批量办理{cert_name}续期，降低重复操作成本",
                    ))

        except Exception:
            pass

        # SDK 深入分析：Claude 基于产品数据生成深层洞察
        if insights:
            sdk_insight = await self._generate_with_claude("cross_product_insights", {
                "insights": [i.to_dict() for i in insights],
                "total_products": len(products) if 'products' in dir() else 0,
            })
            if sdk_insight:
                insights.append(Insight(
                    insight_type="sdk_analysis",
                    title="Claude AI 深度洞察",
                    description=sdk_insight[:500],
                    severity="medium",
                    suggestion="详情请查看 SDK 分析全文",
                ))

        # 保存洞察
        self._insights = insights

        # 持久化到全局记忆
        self._persist_insights(insights)

        return [i.to_dict() for i in insights]

    # ── 全局指标聚合 ──────────────────────────────────

    async def aggregate_global_metrics(self) -> Dict[str, Any]:
        """聚合全局指标

        参考指南§6.12.4:
          - 纳管产品总数
          - 全系统合规健康度
          - 高风险产品占比
          - 待处理预警数
          - 认证到期分布
          - 平均退货率/拒付率
          - 市场覆盖率
        """
        agg = {
            "aggregated_at": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "total_managed_products": 0,
                "system_health_score": 0,
                "high_risk_product_ratio": 0,
                "pending_alerts": 0,
                "cert_expiry_distribution": {},
                "avg_return_rate": 0,
                "avg_chargeback_rate": 0,
                "market_coverage": [],
            },
        }

        try:
            from app.core.product_storage import get_product_storage
            storage = get_product_storage()
            products = storage.list_products()

            agg["metrics"]["total_managed_products"] = len(products)

            # 市场覆盖
            markets = set()
            health_scores = []
            for p in products:
                ms = getattr(p, 'target_markets', []) or []
                markets.update(ms)

                # 基于生命周期阶段计算产品健康度
                stage_rank = {
                    "active": 100, "review": 70, "pending": 50,
                    "risk": 30, "end": 10, "draft": 40,
                }
                stage = getattr(p, 'lifecycle_stage', '') or getattr(p, 'status', '')
                score = stage_rank.get(stage, 50)

                # 风险降级
                risk = getattr(p, 'risk_level', '') or ''
                if risk in ('high', 'critical'):
                    score = max(score - 30, 0)
                elif risk == 'medium':
                    score = max(score - 10, 0)

                health_scores.append(score)

            agg["metrics"]["market_coverage"] = sorted(list(markets))

            if health_scores:
                agg["metrics"]["system_health_score"] = round(
                    sum(health_scores) / len(health_scores), 1
                )

        except Exception:
            pass

        # 持久化
        agg_path = self._global_metrics_path / "agg_metrics.json"
        try:
            agg_path.write_text(
                json.dumps(agg, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception:
            pass

        return agg

    # ── 内置指标模板（对齐指南§6.6.1） ──────────────────────────────────

    BUILTIN_METRICS = {
        "health_score": {
            "name": "合规健康度",
            "formula": "通过产品数/总产品数×100%",
            "threshold_warning": 80,
            "threshold_critical": 60,
            "refresh": "realtime",
        },
        "cert_expiry_density": {
            "name": "认证到期密度",
            "formula": "30天内到期的认证数",
            "threshold_warning": 3,
            "threshold_critical": 5,
            "refresh": "daily",
        },
        "risk_product_ratio": {
            "name": "风险产品占比",
            "formula": "高风险产品/总在售产品",
            "threshold_warning": 10,
            "threshold_critical": 25,
            "refresh": "realtime",
        },
        "order_consistency_rate": {
            "name": "三单一致率",
            "formula": "三单匹配订单/总订单",
            "threshold_warning": 95,
            "threshold_critical": 90,
            "refresh": "daily",
        },
        "avg_check_latency": {
            "name": "平均检查响应时间",
            "formula": "合规检查平均耗时(ms)",
            "threshold_warning": 5000,
            "threshold_critical": 10000,
            "refresh": "hourly",
        },
        "chargeback_rate": {
            "name": "拒付率",
            "formula": "拒付订单/总订单",
            "threshold_warning": 0.8,
            "threshold_critical": 1.5,
            "refresh": "daily",
        },
        "return_rate": {
            "name": "退货率",
            "formula": "退货订单/总订单",
            "threshold_warning": 5,
            "threshold_critical": 10,
            "refresh": "daily",
        },
        "dsar_response_time": {
            "name": "申诉响应时效",
            "formula": "DSAR请求平均响应时间(小时)",
            "threshold_warning": 24,
            "threshold_critical": 48,
            "refresh": "daily",
        },
    }

    def get_builtin_metrics(self) -> Dict[str, Any]:
        """获取内置指标模板清单"""
        return dict(self.BUILTIN_METRICS)

    # ── 状态查询 ──────────────────────────────────

    def get_heartbeat(self) -> Optional[Dict[str, Any]]:
        """获取最新心跳状态"""
        return self._heartbeat.to_dict() if self._heartbeat else None

    def get_insights(self) -> List[Dict[str, Any]]:
        """获取最近洞察"""
        return [i.to_dict() for i in self._insights]

    def get_brief_history(self, limit: int = 7) -> List[Dict[str, Any]]:
        """获取简报历史"""
        return self._brief_history[-limit:]

    def get_alert_history(self, limit: int = 30) -> List[Dict[str, Any]]:
        """获取预警历史"""
        return self._alert_history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """获取引擎统计"""
        return {
            "uptime_seconds": int((datetime.now(timezone.utc) - self._start_time).total_seconds()),
            "heartbeat_count": 1 if self._heartbeat else 0,
            "insights_count": len(self._insights),
            "brief_history_count": len(self._brief_history),
            "alert_history_count": len(self._alert_history),
            "builtin_metrics_count": len(self.BUILTIN_METRICS),
        }

    # ── 内部辅助 ──────────────────────────────────

    def _update_global_memory_regulations(self, changes: List[Dict]):
        """更新全局记忆中的法规变更"""
        try:
            mem_path = self._global_memory_path / "global_memory.json"
            memory = {}
            if mem_path.exists():
                memory = json.loads(mem_path.read_text(encoding="utf-8"))

            shared = memory.setdefault("shared_context", {})
            recent = shared.setdefault("recent_regulation_changes", [])
            recent.extend(changes)

            # 保留最近50条
            if len(recent) > 50:
                shared["recent_regulation_changes"] = recent[-50:]

            memory["last_updated"] = datetime.now(timezone.utc).isoformat()
            mem_path.write_text(
                json.dumps(memory, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _update_global_memory_health(self, heartbeat: HeartbeatStatus):
        """更新全局记忆中的系统健康"""
        try:
            mem_path = self._global_memory_path / "global_memory.json"
            memory = {}
            if mem_path.exists():
                memory = json.loads(mem_path.read_text(encoding="utf-8"))

            shared = memory.setdefault("shared_context", {})
            shared["system_health"] = {
                "status": heartbeat.overall,
                "last_check": heartbeat.timestamp,
                "components": heartbeat.components,
            }
            memory["last_updated"] = datetime.now(timezone.utc).isoformat()
            mem_path.write_text(
                json.dumps(memory, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _persist_insights(self, insights: List[Insight]):
        """持久化洞察到全局记忆"""
        try:
            mem_path = self._global_memory_path / "global_memory.json"
            memory = {}
            if mem_path.exists():
                memory = json.loads(mem_path.read_text(encoding="utf-8"))

            memory["cross_product_insights"] = {
                "common_risks": [
                    {
                        "risk": i.title,
                        "affected_products": i.affected_products,
                        "suggestion": i.suggestion,
                    }
                    for i in insights if i.insight_type == "common_risk"
                ],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            mem_path.write_text(
                json.dumps(memory, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception:
            pass


# ── 单例管理 ──────────────────────────────────

_engine_instance: Optional[ProactiveEngine] = None


def get_proactive_engine() -> ProactiveEngine:
    """获取全局ProactiveEngine单例"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ProactiveEngine()
    return _engine_instance
